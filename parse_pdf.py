"""
Парсер PDF дизайн-проекта для извлечения списка мебели.
Работает с архитектурными альбомами (планы, развёртки, визуализации)
и с табличными спецификациями.
"""
from __future__ import annotations

import re
from typing import Optional

import pdfplumber


# Мебель, которую производит Settee (мягкая мебель)
SETTEE_FURNITURE = {
    "диван": {"description": "Изготовление по чертежу. Каркас: массив/фанера. Наполнение: резинотканевые ремни, вязкоэластичная пена, холкон. Опоры: скрытые 30 мм. Материал обивки: на согласовании"},
    "софа": {"description": "Изготовление по чертежу. Каркас: массив/фанера. Наполнение: резинотканевые ремни, вязкоэластичная пена, холкон. Опоры: скрытые 30 мм. Материал обивки: на согласовании"},
    "кресл": {"description": "Изготовление по чертежу. Каркас: массив/фанера. Наполнение: резинотканевые ремни, вязкоэластичная пена, холкон. Материал обивки: на согласовании"},
    "кроват": {"description": "Изготовление по чертежу. Материал обивки: на согласовании"},
    "пуф": {"description": "Изготовление по чертежу. Материал обивки: на согласовании"},
    "банкетк": {"description": "Изготовление по чертежу. Материал обивки: на согласовании"},
    "скамь": {"description": "Изготовление по чертежу. Материал обивки: на согласовании"},
    "топчан": {"description": "Изготовление по чертежу. Каркас: массив/фанера. Материал обивки: на согласовании"},
    "изголовь": {"description": "Изготовление по чертежу. Материал обивки: на согласовании"},
    "стул": {"description": "Изготовление по чертежу. Каркас: массив/фанера. Материал обивки: на согласовании"},
}

# Слова, которые точно НЕ мебель (шум из чертежей)
NOISE_PATTERNS = [
    r"^\d+$",                   # просто числа
    r"^[.\-\s]+$",              # точки, тире
    r"^\d+[\s×xх\*]\d+",       # размеры типа "1200x800"
    r"^h\s*=",                  # высоты h=
    r"^H\s*=",
    r"сущ\.",                   # "сущ. потолок"
    r"ГКЛ",
    r"штукатурка",
    r"керамогранит",
    r"паркет",
    r"монтаж",
    r"демонтаж",
    r"вывод",
    r"розетк",
    r"выключател",
    r"кабель",
    r"потолок",
    r"карниз",
    r"карман",
    r"радиатор",
    r"кондио",
    r"инсталляц",
    r"стояк",
    r"труб",
    r"подсветк",
    r"электри",
    r"вентиляц",
    r"гидроизол",
    r"утеплен",
    r"перегородк",
    r"проем",
    r"откос",
    r"плинтус",
    r"лист\s*\d",
    r"см\.\s*лист",
    r"узел\s*\d",
    r"формат\s*а",
    r"масштаб",
    r"дизайнер",
    r"разработ",
    r"стадия",
    r"примечан",
    r"условные\s*обозначен",
    r"артикул",
    r"noken",
    r"fima",
    r"alice",
    r"radaway",
    r"viega",
    r"brenta",
    r"salini",
    r"aledo",
    r"martinelli",
    r"lumina",
    r"gervasoni",
    r"miniforms",
    r"смесител",
    r"унитаз",
    r"раковин",
    r"душ[а-я]*\b",
    r"ванн[а-я]*\b",
    r"полотенце",
    r"клавиш",
    r"сиденье",
    r"излив",
    r"кронштейн",
    r"лоток",
    r"шланг",
    r"бра\s",
    r"светильник",
    r"торшер",
    r"люстр",
    r"столешниц",
    r"экспликац",
    r"помещени[йе]",
    r"площадь",
    r"м²",
]

# Список помещений для распознавания комнат
ROOM_PATTERNS = [
    (r"мастер.спальн", "Мастер-спальня"),
    (r"спальн", "Мастер-спальня"),
    (r"гостин", "Гостиная"),
    (r"кухн", "Кухня-столовая"),
    (r"столов", "Кухня-столовая"),
    (r"кабинет", "Кабинет"),
    (r"детск", "Детская"),
    (r"прихож", "Прихожая"),
    (r"коридор", "Коридор"),
    (r"гардероб", "Гардеробная"),
    (r"постироч", "Постирочная"),
    (r"балкон", "Балкон"),
    (r"лоджи", "Лоджия"),
    (r"санузел", "Санузел"),
    (r"ванн", "Ванная"),
]


def extract_text_from_pdf(pdf_path: str) -> str:
    """Извлекает весь текст из PDF."""
    pages_text = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages_text.append(text)
    return "\n\n--- Страница ---\n\n".join(pages_text)


def extract_tables_from_pdf(pdf_path: str) -> list[list[list[str]]]:
    """Извлекает таблицы из PDF."""
    all_tables = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            if tables:
                all_tables.extend(tables)
    return all_tables


def parse_furniture_from_tables(tables: list[list[list[str]]]) -> list[dict]:
    """Пытается найти мебельные позиции в таблицах."""
    items = []
    for table in tables:
        if not table or len(table) < 2:
            continue

        header = table[0]
        if not header:
            continue

        name_idx = _find_column(header, ["наименование", "название", "позиция", "мебель", "предмет"])
        qty_idx = _find_column(header, ["кол", "шт", "количество", "кол-во"])
        dim_idx = _find_column(header, ["размер", "габарит", "шхгхв", "ширина", "длина"])
        room_idx = _find_column(header, ["комната", "помещение", "зона", "room"])

        if name_idx is None:
            continue

        for row in table[1:]:
            if not row or name_idx >= len(row):
                continue
            name = (row[name_idx] or "").strip()
            if not name or _is_noise(name):
                continue

            item = {
                "name": name,
                "quantity": _parse_int(row[qty_idx] if qty_idx is not None and qty_idx < len(row) else None, default=1),
                "dimensions": (row[dim_idx] if dim_idx is not None and dim_idx < len(row) else None) or "",
                "room": (row[room_idx] if room_idx is not None and room_idx < len(row) else None) or "",
                "description": "",
                "price": 0,
            }
            items.append(item)

    return items


def parse_furniture_from_text(text: str) -> list[dict]:
    """
    Извлекает мебель из текста архитектурного PDF.
    Фильтрует шум из чертежей, ищет только реальные мебельные позиции.
    """
    items = []
    seen = set()

    # Ищем упоминания мебели в контексте плана расстановки
    for line in text.split("\n"):
        line = line.strip()
        if not line or len(line) < 3 or len(line) > 150:
            continue

        # Пропускаем шум
        if _is_noise(line):
            continue

        # Ищем мебельные ключевые слова
        line_lower = line.lower()
        matched_key = None
        for key in SETTEE_FURNITURE:
            if key in line_lower:
                matched_key = key
                break

        if not matched_key:
            continue

        # Формируем чистое название
        name = _clean_furniture_name(line, matched_key)
        if not name or len(name) < 3:
            continue

        name_key = name.lower()
        if name_key in seen:
            continue
        seen.add(name_key)

        # Извлекаем размеры из строки
        dimensions = _extract_dimensions(line)

        # Определяем комнату из контекста
        room = _guess_room_from_context(text, line)

        item = {
            "name": name,
            "quantity": 1,
            "dimensions": dimensions,
            "room": room,
            "description": SETTEE_FURNITURE.get(matched_key, {}).get("description", ""),
            "price": 0,
        }
        items.append(item)

    return items


def parse_pdf(pdf_path: str) -> list[dict]:
    """
    Основная функция: парсит PDF и возвращает список мебели.
    Фокус на мягкой мебели Settee: диваны, кресла, кровати, пуфы, банкетки.
    """
    text = extract_text_from_pdf(pdf_path)

    # Сначала пробуем таблицы
    tables = extract_tables_from_pdf(pdf_path)
    items = parse_furniture_from_tables(tables)

    # Фильтруем — оставляем только мебель
    if items:
        items = _filter_only_furniture(items)

    # Если таблицы не дали мебель — парсим текст
    if not items:
        items = parse_furniture_from_text(text)

    # Дедупликация
    items = _deduplicate(items)

    if not items:
        print("\n⚠ Мебель не найдена автоматически.")
        print("Добавьте позиции вручную в редакторе.\n")

    return items


def _filter_only_furniture(items: list[dict]) -> list[dict]:
    """Оставляет только позиции, похожие на мебель Settee."""
    result = []
    for item in items:
        name_lower = item["name"].lower()
        # Проверяем, содержит ли название мебельное ключевое слово
        is_furniture = False
        for key in SETTEE_FURNITURE:
            if key in name_lower:
                is_furniture = True
                if not item.get("description"):
                    item["description"] = SETTEE_FURNITURE[key]["description"]
                break
        if is_furniture and not _is_noise(item["name"]):
            result.append(item)
    return result


def _is_noise(text: str) -> bool:
    """Проверяет, является ли строка шумом из чертежей."""
    text_lower = text.lower().strip()

    # Слишком короткое или числовое
    if len(text_lower) < 3:
        return True
    if re.match(r"^\d+[\s.,]*\d*$", text_lower):
        return True

    for pattern in NOISE_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return True

    # Строка состоит в основном из цифр и спецсимволов
    alpha_count = sum(1 for c in text_lower if c.isalpha())
    if alpha_count < 3:
        return True

    return False


def _clean_furniture_name(line: str, matched_key: str) -> str:
    """Извлекает чистое название мебели из строки чертежа."""
    line = line.strip()

    # Убираем размеры из названия
    line = re.sub(r"\d+[\s]*[×xхX\*][\s]*\d+(?:[\s]*[×xхX\*][\s]*\d+)?(?:\s*мм\.?)?", "", line)

    # Убираем одиночные числа в начале и конце
    line = re.sub(r"^\d+[\s.,]*", "", line)
    line = re.sub(r"[\s.,]*\d+$", "", line)

    # Убираем переносы строк
    line = re.sub(r"\n+", " ", line)

    # Убираем лишние пробелы
    line = re.sub(r"\s+", " ", line).strip()

    # Если строка начинается со слов-мусора типа "от", "для", "из", "до", "по", "к"
    # перед мебельным словом — убираем мусор до ключевого слова
    key_pos = line.lower().find(matched_key)
    if key_pos > 0:
        # Проверяем, есть ли перед ключевым словом только предлоги/мусор
        prefix = line[:key_pos].strip().lower()
        noise_prefixes = ["от", "для", "из", "до", "по", "к", "с", "за", "в", "на", "у"]
        if prefix in noise_prefixes or len(prefix) <= 2:
            line = line[key_pos:]

    # Если строка слишком длинная — берём до первой точки или запятой после 20 символов
    if len(line) > 50:
        # Ищем конец первого предложения
        for sep in [",", ".", ";", "\n"]:
            pos = line.find(sep, 15)
            if 15 < pos < 60:
                line = line[:pos]
                break
        if len(line) > 60:
            line = line[:60].rsplit(" ", 1)[0]

    line = line.strip(" ,.-;")

    # Первая буква заглавная
    if line:
        line = line[0].upper() + line[1:]

    return line


def _extract_dimensions(line: str) -> str:
    """Извлекает размеры из строки (например, '1800×2000')."""
    # Ищем паттерн ЧИСЛОxЧИСЛО или ЧИСЛО*ЧИСЛО
    match = re.search(r"(\d{3,5})\s*[×xхX\*]\s*(\d{3,5})(?:\s*[×xхX\*]\s*(\d{3,5}))?", line)
    if match:
        parts = [match.group(1), match.group(2)]
        if match.group(3):
            parts.append(match.group(3))
        return "×".join(parts)
    return ""


def _guess_room_from_context(full_text: str, furniture_line: str) -> str:
    """Пытается определить комнату по контексту вокруг строки с мебелью."""
    # Ищем позицию строки в тексте
    pos = full_text.find(furniture_line)
    if pos < 0:
        return ""

    # Смотрим контекст — 500 символов до и после
    context = full_text[max(0, pos - 500):pos + 500].lower()

    for pattern, room_name in ROOM_PATTERNS:
        if re.search(pattern, context, re.IGNORECASE):
            return room_name

    return ""


def _deduplicate(items: list[dict]) -> list[dict]:
    """Убирает дублирующиеся позиции."""
    seen = set()
    result = []
    for item in items:
        key = item["name"].lower().strip()
        # Убираем совсем одинаковые
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _find_column(header: list, keywords: list[str]):
    """Ищет индекс столбца по ключевым словам в заголовке."""
    for i, cell in enumerate(header):
        if cell:
            cell_lower = cell.lower().strip()
            for kw in keywords:
                if kw in cell_lower:
                    return i
    return None


def _parse_int(value, default: int = 1) -> int:
    """Парсит число из строки."""
    if not value:
        return default
    nums = re.findall(r"\d+", str(value))
    return int(nums[0]) if nums else default
