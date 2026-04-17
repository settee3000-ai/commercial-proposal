"""
Генератор PDF коммерческого предложения с помощью fpdf2.
Формат: фото слева, описание справа — как в оригинальном КП Settee.
"""
from __future__ import annotations

from pathlib import Path
from datetime import datetime

from fpdf import FPDF

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
ROW_HEIGHT = 45  # высота строки с фото


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


def _draw_item_row(pdf: ProposalPDF, item: dict, currency: str):
    """Рисует одну строку позиции с фото."""
    x_start = pdf.l_margin
    y_start = pdf.get_y()

    # Проверяем, хватает ли места на странице
    if y_start + ROW_HEIGHT > pdf.h - 25:
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
        img_h = ROW_HEIGHT - pad * 2
        pdf.image(img_path, x=x_start + pad, y=y_start + pad, w=img_w, h=img_h)

    # --- Наименование / описание ---
    x_name = x_start + COL_PHOTO
    pdf._set_font("B", 9)
    pdf.set_text_color(*DARK)

    # Название
    pdf.set_xy(x_name + 2, y_start + 2)
    name_with_dims = item["name"]
    if item.get("dimensions"):
        name_with_dims += f': {item["dimensions"]} мм.'
    pdf.multi_cell(COL_NAME - 4, 4, name_with_dims, new_x="LEFT", new_y="NEXT")

    # Описание — каждая строка через точку на новой строке
    if item.get("description"):
        pdf._set_font("", 7)
        pdf.set_text_color(*GRAY)
        desc_y = pdf.get_y() + 1
        pdf.set_xy(x_name + 2, desc_y)
        desc_lines = item["description"].split(". ")
        for line in desc_lines:
            line = line.strip().rstrip(".")
            if line:
                pdf.set_x(x_name + 2)
                pdf.cell(COL_NAME - 4, 3.5, line, new_x="LMARGIN", new_y="NEXT")

    # --- Кол-во ---
    x_qty = x_name + COL_NAME
    pdf._set_font("", 9)
    pdf.set_text_color(*DARK)
    pdf.set_xy(x_qty, y_start + ROW_HEIGHT / 2 - 3)
    pdf.cell(COL_QTY, 6, f'{item["quantity"]} шт.', align="C")

    # --- Цена ---
    x_price = x_qty + COL_QTY
    pdf.set_xy(x_price, y_start + ROW_HEIGHT / 2 - 3)
    if item["price"] > 0:
        pdf.cell(COL_PRICE, 6, f'{_fmt(item["price"])} р.', align="C")
    else:
        pdf.cell(COL_PRICE, 6, "—", align="C")

    # --- Общая стоимость ---
    x_total = x_price + COL_PRICE
    pdf.set_xy(x_total, y_start + ROW_HEIGHT / 2 - 3)
    if item["total"] > 0:
        pdf.cell(COL_TOTAL, 6, f'{_fmt(item["total"])} р.', align="C")
    else:
        pdf.cell(COL_TOTAL, 6, "—", align="C")

    pdf.set_y(y_start + ROW_HEIGHT)


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
