"""
Генератор PDF коммерческого предложения с помощью fpdf2.
Формат: фото слева, описание справа — как в оригинальном КП Settee.
"""
from __future__ import annotations

from pathlib import Path
from datetime import datetime

from fpdf import FPDF
from PIL import Image as PILImage
import tempfile

# Фирменные цвета Settee
BRAND = (212, 145, 30)       # #D4911E — золотисто-оранжевый
DARK = (60, 50, 40)          # тёмно-коричневый для текста
GRAY = (120, 120, 120)
LIGHT_GRAY = (200, 200, 200)
BG_LIGHT = (252, 249, 244)   # тёплый светлый фон
WHITE = (255, 255, 255)

# Ширины колонок: Фото | Наименование/размер | Кол-во | Цена | Общая стоимость
COL_PHOTO = 45
COL_NAME = 65
COL_QTY = 20
COL_PRICE = 28
COL_TOTAL = 32
ROW_HEIGHT = 52  # высота строки с фото


class ProposalPDF(FPDF):
    """PDF-документ коммерческого предложения."""

    def __init__(self, company: dict, currency: str = "₽"):
        super().__init__()
        self.company = company
        self.currency = currency
        self._logo_path = None
        self._base_dir = Path(__file__).parent

        logo = self._base_dir / company.get("logo_path", "static/logo.png")
        if logo.exists():
            self._logo_path = str(logo)

        font_dir = self._base_dir / "fonts"
        if (font_dir / "DejaVuSans.ttf").exists():
            self.add_font("DejaVu", "", str(font_dir / "DejaVuSans.ttf"), uni=True)
            self.add_font("DejaVu", "B", str(font_dir / "DejaVuSans-Bold.ttf"), uni=True)
            self.font_family_name = "DejaVu"
        else:
            self.font_family_name = None

    def _set_font(self, style: str = "", size: int = 10):
        if self.font_family_name:
            self.set_font(self.font_family_name, style, size)
        else:
            self.set_font("Helvetica", style, size)

    def header(self):
        if self.page_no() == 1:
            return  # титульная страница — без стандартного header
        start_y = self.get_y()
        if self._logo_path:
            self.image(self._logo_path, x=10, y=start_y, h=10)
            self.set_y(start_y + 12)
        else:
            self._set_font("B", 16)
            self.set_text_color(*BRAND)
            self.cell(0, 8, self.company["name"], new_x="LMARGIN", new_y="NEXT")

        self._set_font("", 8)
        self.set_text_color(*GRAY)
        self.cell(0, 4, f'{self.company["phone"]}  |  {self.company["email"]}  |  {self.company["address"]}',
                  new_x="LMARGIN", new_y="NEXT")

        self.set_draw_color(*BRAND)
        self.set_line_width(0.8)
        y = self.get_y() + 2
        self.line(10, y, 200, y)
        self.set_y(y + 4)

    def footer(self):
        if self.page_no() == 1:
            return  # титульная страница — без стандартного footer
        self.set_y(-15)
        self._set_font("", 7)
        self.set_text_color(*LIGHT_GRAY)
        self.cell(0, 10, f'Страница {self.page_no()}/{{nb}}  |  {self.company["name"]}',
                  align="C")


def _fmt(num: float) -> str:
    return f"{num:,.0f}".replace(",", " ")


def _draw_table_header(pdf: ProposalPDF, currency: str):
    """Рисует заголовок таблицы."""
    pdf.set_fill_color(*BRAND)
    pdf.set_text_color(*WHITE)
    pdf._set_font("B", 8)

    headers = [
        ("Фото", COL_PHOTO, "C"),
        ("Наименование/размер", COL_NAME, "C"),
        ("Кол-во", COL_QTY, "C"),
        ("Цена", COL_PRICE, "C"),
        ("Общая\nстоимость", COL_TOTAL, "C"),
    ]
    h = 10
    y = pdf.get_y()
    x = pdf.l_margin
    for label, w, align in headers:
        pdf.set_xy(x, y)
        pdf.cell(w, h, "", border=0, fill=True)
        # Центрируем текст вертикально
        if "\n" in label:
            lines = label.split("\n")
            pdf.set_xy(x, y + 1)
            pdf.cell(w, 4, lines[0], align=align)
            pdf.set_xy(x, y + 5)
            pdf.cell(w, 4, lines[1], align=align)
        else:
            pdf.set_xy(x, y + 2)
            pdf.cell(w, 6, label, align=align)
        x += w
    pdf.set_y(y + h)


def _item_dim_label(item: dict) -> str:
    """Формирует строку 'Название: ШхВхГ мм' без дублирования 'мм'."""
    name = item["name"]
    dims = (item.get("dimensions") or "").strip().rstrip(".").strip()
    if not dims:
        return name
    if "мм" not in dims.lower():
        dims += " мм"
    return f"{name}: {dims}"


def _compute_row_height(pdf: ProposalPDF, item: dict) -> float:
    """Вычисляет минимально необходимую высоту строки под фактический текст."""
    name_line_h = 4
    desc_line_h = 3.5

    pdf._set_font("B", 9)
    name_lines = pdf.multi_cell(
        COL_NAME - 4, name_line_h, _item_dim_label(item),
        dry_run=True, output="LINES",
    )
    text_h = 2 + len(name_lines) * name_line_h

    if item.get("description"):
        pdf._set_font("", 7)
        desc_lines = pdf.multi_cell(
            COL_NAME - 6, desc_line_h, item["description"],
            dry_run=True, output="LINES",
        )
        text_h += 1 + len(desc_lines) * desc_line_h

    text_h += 2
    return max(ROW_HEIGHT, text_h)


def _draw_item_row(pdf: ProposalPDF, item: dict, currency: str):
    """Рисует одну строку позиции с фото."""
    x_start = pdf.l_margin
    row_h = _compute_row_height(pdf, item)
    y_start = pdf.get_y()

    # Проверяем, хватает ли места на странице
    if y_start + row_h > pdf.h - 25:
        pdf.add_page()
        _draw_table_header(pdf, currency)
        y_start = pdf.get_y()

    # Тонкая линия сверху
    pdf.set_draw_color(*LIGHT_GRAY)
    pdf.set_line_width(0.2)
    pdf.line(x_start, y_start, x_start + COL_PHOTO + COL_NAME + COL_QTY + COL_PRICE + COL_TOTAL, y_start)

    # --- Фото ---
    img_path = None
    if item.get("image"):
        p = Path(__file__).parent / item["image"]
        if p.exists():
            img_path = str(p)

    if img_path:
        pad = 2
        img_w = COL_PHOTO - pad * 2
        img_h = min(row_h - pad * 2, 50)
        img_y = y_start + pad + max(0, (row_h - pad * 2 - img_h) / 2)
        pdf.image(img_path, x=x_start + pad, y=img_y,
                  w=img_w, h=img_h, keep_aspect_ratio=True)

    # --- Наименование / описание ---
    x_name = x_start + COL_PHOTO
    pdf._set_font("B", 9)
    pdf.set_text_color(*DARK)

    # Название
    pdf.set_xy(x_name + 2, y_start + 2)
    pdf.multi_cell(COL_NAME - 4, 4, _item_dim_label(item), new_x="LEFT", new_y="NEXT")

    # Описание — с сохранением переносов из исходника
    if item.get("description"):
        pdf._set_font("", 7)
        pdf.set_text_color(*GRAY)
        desc_y = pdf.get_y() + 1
        pdf.set_xy(x_name + 2, desc_y)
        pdf.multi_cell(COL_NAME - 6, 3.5, item["description"], new_x="LEFT", new_y="NEXT")

    # --- Кол-во ---
    x_qty = x_name + COL_NAME
    pdf._set_font("", 9)
    pdf.set_text_color(*DARK)
    pdf.set_xy(x_qty, y_start + row_h / 2 - 3)
    pdf.cell(COL_QTY, 6, f'{item["quantity"]} шт.', align="C")

    # --- Цена ---
    x_price = x_qty + COL_QTY
    pdf.set_xy(x_price, y_start + row_h / 2 - 3)
    if item["price"] > 0:
        pdf.cell(COL_PRICE, 6, f'{_fmt(item["price"])} р.', align="C")
    else:
        pdf.cell(COL_PRICE, 6, "—", align="C")

    # --- Общая стоимость ---
    x_total = x_price + COL_PRICE
    pdf.set_xy(x_total, y_start + row_h / 2 - 3)
    if item["total"] > 0:
        pdf.cell(COL_TOTAL, 6, f'{_fmt(item["total"])} р.', align="C")
    else:
        pdf.cell(COL_TOTAL, 6, "—", align="C")

    pdf.set_y(y_start + row_h)


def _prepare_cover_image(image_path: str, target_w: float, target_h: float) -> str:
    """Мягко обрезает фото под область обложки, не превращая его в узкую полосу.

    Если исходник значительно отличается от целевого соотношения, ограничиваем
    степень обрезки коэффициентом 1.35 — получаем естественный кадр без
    экстремального вытягивания.
    """
    img = PILImage.open(image_path)
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")
    w, h = img.size
    target_aspect = target_w / target_h
    src_aspect = w / h
    max_crop = 1.35

    if src_aspect > target_aspect:
        limit_aspect = max(target_aspect, src_aspect / max_crop)
        new_w = int(h * limit_aspect)
        left = (w - new_w) // 2
        crop_box = (left, 0, left + new_w, h)
    else:
        limit_aspect = min(target_aspect, src_aspect * max_crop)
        new_h = int(w / limit_aspect)
        top = (h - new_h) // 2
        crop_box = (0, top, w, top + new_h)

    cropped = img.crop(crop_box)
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    cropped.save(tmp.name, "PNG")
    return tmp.name


def _draw_cover_page(pdf: ProposalPDF, company: dict, client_name: str,
                     project_name: str, proposal_date: str,
                     cover_image: str = None):
    """Рисует титульную страницу: слева вертикальное фото, справа серая панель."""
    page_w = pdf.w
    page_h = pdf.h

    # Левая половина — фото, правая — серый блок с текстом
    photo_w = page_w * 0.5
    right_x = photo_w
    right_w = page_w - photo_w
    pad = 14
    text_x = right_x + pad
    text_w = right_w - pad * 2

    GRAY_BG = (236, 233, 229)
    LINK_BLUE = (52, 102, 178)

    # --- Фон всей страницы: тёплый серый ---
    pdf.set_fill_color(*GRAY_BG)
    pdf.rect(0, 0, page_w, page_h, style="F")

    # --- Фото слева, вписано с сохранением пропорций и центрировано ---
    if cover_image and Path(cover_image).exists():
        try:
            tmp_img = _prepare_cover_image(cover_image, photo_w, page_h)
            pdf.image(tmp_img, x=0, y=0, w=photo_w, h=page_h,
                      keep_aspect_ratio=True)
            Path(tmp_img).unlink(missing_ok=True)
        except Exception:
            pass

    # --- Логотип сверху справа ---
    logo_top = 22
    if pdf._logo_path:
        pdf.image(pdf._logo_path, x=text_x, y=logo_top, w=min(40, text_w))

    # --- Заголовок "Предварительный просчёт" ---
    heading_y = page_h * 0.30
    pdf._set_font("", 18)
    pdf.set_text_color(*DARK)
    pdf.set_xy(text_x, heading_y)
    pdf.multi_cell(text_w, 8, "Предварительный просчёт",
                   align="L", new_x="LEFT", new_y="NEXT")

    # --- Опциональная подпись для клиента ---
    if client_name and client_name.strip() and client_name.strip() != "(копия)":
        pdf._set_font("", 10)
        pdf.set_text_color(*GRAY)
        pdf.set_xy(text_x, pdf.get_y() + 3)
        pdf.multi_cell(text_w, 5, f"Для: {client_name.strip()}",
                       align="L", new_x="LEFT", new_y="NEXT")

    # --- Контакты (менеджер, дата, сайт) — ниже середины ---
    info_y = page_h * 0.58
    line_gap = 10

    pdf._set_font("", 10)
    pdf.set_text_color(*DARK)

    manager = company.get("project_manager_phone") or company.get("phone", "")
    pdf.set_xy(text_x, info_y)
    pdf.multi_cell(text_w, 5, f"Менеджер: {manager}",
                   align="L", new_x="LEFT", new_y="NEXT")
    info_y = pdf.get_y() + line_gap - 5

    pdf.set_xy(text_x, info_y)
    pdf.multi_cell(text_w, 5, proposal_date,
                   align="L", new_x="LEFT", new_y="NEXT")
    info_y = pdf.get_y() + line_gap - 5

    website = company.get("website", "")
    if website:
        pdf.set_xy(text_x, info_y)
        pdf.set_text_color(*LINK_BLUE)
        pdf.multi_cell(text_w, 5, website,
                       align="L", new_x="LEFT", new_y="NEXT", link=website)


def generate_proposal_pdf(
    rooms: list[dict],
    company: dict,
    client_name: str,
    project_name: str = "",
    proposal_number: str = "",
    discount_percent: float = 0,
    currency: str = "₽",
    validity_days: int = 30,
    vat_included: bool = True,
    output_path: str = "output/proposal.pdf",
    template_dir: str = "templates",
    cover_image: str = "",
) -> str:
    """Генерирует PDF коммерческого предложения."""

    # Рассчитываем итоги
    total_qty = 0
    for room in rooms:
        room_total = 0
        for item in room["items"]:
            item["total"] = item["price"] * item["quantity"]
            room_total += item["total"]
            total_qty += item["quantity"]
        room["subtotal"] = room_total

    subtotal = sum(r["subtotal"] for r in rooms)
    discount_amount = subtotal * discount_percent / 100
    grand_total = subtotal - discount_amount

    if not proposal_number:
        proposal_number = f"КП-{datetime.now().strftime('%Y%m%d-%H%M')}"

    proposal_date = datetime.now().strftime("%d.%m.%Y")

    production_days = 65

    # --- Создаём PDF ---
    pdf = ProposalPDF(company, currency)
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)

    # --- Определяем обложку ---
    if not cover_image:
        # Берём первое доступное фото из позиций
        base = Path(__file__).parent
        for room in rooms:
            for item in room["items"]:
                if item.get("image"):
                    p = base / item["image"]
                    if p.exists():
                        cover_image = str(p)
                        break
            if cover_image:
                break

    # --- Титульная страница ---
    pdf.add_page()
    _draw_cover_page(pdf, company, client_name, project_name, proposal_date,
                     cover_image=cover_image)

    # --- Страница с содержимым ---
    pdf.add_page()

    # Заголовок
    pdf._set_font("B", 14)
    pdf.set_text_color(*DARK)
    pdf.cell(0, 10, "КОММЕРЧЕСКОЕ ПРЕДЛОЖЕНИЕ", align="C", new_x="LMARGIN", new_y="NEXT")

    pdf._set_font("", 9)
    pdf.set_text_color(*GRAY)
    pdf.cell(0, 5, f"{proposal_number} от {proposal_date}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    # Блок клиента
    pdf.set_fill_color(*BG_LIGHT)
    pdf.set_draw_color(*BRAND)
    x = pdf.get_x()
    y = pdf.get_y()
    block_h = 18 if project_name else 12
    pdf.rect(x, y, 190, block_h, style="F")
    pdf.set_line_width(1.5)
    pdf.line(x, y, x, y + block_h)

    pdf._set_font("", 7)
    pdf.set_text_color(*GRAY)
    pdf.set_xy(x + 4, y + 1)
    pdf.cell(0, 4, "КЛИЕНТ")
    pdf._set_font("B", 11)
    pdf.set_text_color(*DARK)
    pdf.set_xy(x + 4, y + 5)
    pdf.cell(0, 5, client_name)
    if project_name:
        pdf._set_font("", 8)
        pdf.set_text_color(100, 100, 100)
        pdf.set_xy(x + 4, y + 11)
        pdf.cell(0, 5, f"Проект: {project_name}")

    pdf.set_y(y + block_h + 5)

    # Условия перед таблицей
    pdf._set_font("", 8)
    pdf.set_text_color(*GRAY)
    pdf.cell(0, 4, f"* Услуги доставки и установки не включены в стоимость.", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 4, f"* Срок изготовления до {production_days} рабочих дней.", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    # Заголовок таблицы
    _draw_table_header(pdf, currency)

    # --- Позиции ---
    for room in rooms:
        for item in room["items"]:
            _draw_item_row(pdf, item, currency)

    # --- Итого ---
    y = pdf.get_y()
    pdf.set_draw_color(*DARK)
    pdf.set_line_width(0.4)
    total_w = COL_PHOTO + COL_NAME + COL_QTY + COL_PRICE + COL_TOTAL
    pdf.line(pdf.l_margin, y, pdf.l_margin + total_w, y)

    pdf._set_font("", 9)
    pdf.set_text_color(*DARK)
    pdf.set_xy(pdf.l_margin, y + 2)
    pdf.cell(COL_PHOTO + COL_NAME, 7, "Итого без скидки:", align="R")
    pdf.cell(COL_QTY, 7, f"{total_qty} шт.", align="C")
    pdf.cell(COL_PRICE, 7, "", align="C")
    pdf.cell(COL_TOTAL, 7, f"{_fmt(subtotal)} р.", align="C")
    pdf.set_xy(pdf.l_margin, y + 9)

    if discount_percent > 0:
        pdf.set_text_color(231, 76, 60)
        pdf._set_font("", 9)
        pdf.cell(COL_PHOTO + COL_NAME + COL_QTY + COL_PRICE, 7,
                 f"Скидка {discount_percent:.0f}%:  -{_fmt(discount_amount)} р.", align="R")
        pdf.ln(8)
        pdf.set_xy(pdf.l_margin, pdf.get_y())

    pdf.set_draw_color(*BRAND)
    pdf.set_line_width(0.6)
    pdf.line(pdf.l_margin + COL_PHOTO + COL_NAME, pdf.get_y(),
             pdf.l_margin + total_w, pdf.get_y())
    pdf.ln(2)

    pdf._set_font("B", 12)
    pdf.set_text_color(*BRAND)
    pdf.cell(COL_PHOTO + COL_NAME + COL_QTY + COL_PRICE, 10, "ИТОГО:", align="R")
    pdf.cell(COL_TOTAL, 10, f"{_fmt(grand_total)} р.", align="C")
    pdf.ln(14)

    # --- Условия внизу ---
    pdf.set_fill_color(*BG_LIGHT)
    pdf._set_font("B", 9)
    pdf.set_text_color(*DARK)
    pdf.cell(0, 6, "УСЛОВИЯ", fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf._set_font("", 8)
    pdf.set_text_color(100, 100, 100)
    conditions = [
        f"Предложение действительно {validity_days} дней с даты составления",
        f"Срок изготовления до {production_days} рабочих дней",
        "Услуги доставки и установки не включены в стоимость",
        "Условия оплаты: по согласованию",
    ]
    for cond in conditions:
        pdf.cell(5, 5, "")
        pdf.cell(0, 5, f"- {cond}", new_x="LMARGIN", new_y="NEXT")

    # Сохраняем
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    pdf.output(output_path)

    return output_path
