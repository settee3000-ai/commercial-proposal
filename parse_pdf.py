"""
Парсер PDF дизайн-проекта для извлечения списка мебели.
"""
from __future__ import annotations

import re
from typing import Optional

import pdfplumber


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
    """
    Пытается найти мебельные позиции в таблицах.
    Ищет столбцы с названиями, количеством и размерами.
    """
    items = []
    for table in tables:
        if not table or len(table) < 2:
            continue

        header = table[0]
        if not header:
            continue

        # Пытаемся определить индексы столбцов по заголовкам
        name_idx = _find_column(header, ["наименование", "название", "позиция", "мебель", "предмет", "артикул"])
        qty_idx = _find_column(header, ["кол", "шт", "количество", "кол-во"])
        dim_idx = _find_column(header, ["размер", "габарит", "шхгхв", "ширина", "длина"])
        room_idx = _find_column(header, ["комната", "помещение", "зона", "room"])

        if name_idx is None:
            continue

        for row in table[1:]:
            if not row or name_idx >= len(row):
                continue
            name = (row[name_idx] or "").strip()
            if not name:
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
    Резервный метод: извлекает мебель из неструктурированного текста.
    Ищет типичные мебельные названия.
    """
    furniture_keywords = [
        r"(диван\S*)", r"(кресл\S*)", r"(стол\S*)", r"(стул\S*)", r"(шкаф\S*)",
        r"(комод\S*)", r"(кроват\S*)", r"(тумб\S*)", r"(полк\S*)", r"(стеллаж\S*)",
        r"(зеркал\S*)", r"(светильник\S*)", r"(люстр\S*)", r"(ковр\S*)", r"(торшер\S*)",
        r"(бар\S*стойк\S*)", r"(консол\S*)", r"(пуф\S*)", r"(банкетк\S*)",
        r"(витрин\S*)", r"(гардероб\S*)", r"(буфет\S*)", r"(этажерк\S*)",
    ]

    items = []
    seen = set()
    pattern = "|".join(furniture_keywords)

    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        matches = re.findall(pattern, line, re.IGNORECASE)
        if matches:
            name = line[:120].strip()
            if name.lower() not in seen:
                seen.add(name.lower())
                items.append({
                    "name": name,
                    "quantity": 1,
                    "dimensions": "",
                    "room": "",
                    "description": "",
                    "price": 0,
                })

    return items


def parse_pdf(pdf_path: str) -> list[dict]:
    """
    Основная функция: парсит PDF и возвращает список мебели.
    Сначала пробует таблицы, если не найдено — текстовый поиск.
    """
    tables = extract_tables_from_pdf(pdf_path)
    items = parse_furniture_from_tables(tables)

    if not items:
        text = extract_text_from_pdf(pdf_path)
        items = parse_furniture_from_text(text)

    if not items:
        text = extract_text_from_pdf(pdf_path)
        print("\n⚠ Мебель не найдена автоматически.")
        print("Извлечённый текст из PDF (первые 2000 символов):\n")
        print(text[:2000])
        print("\n...Заполните items.json вручную или скорректируйте парсер.\n")

    return items


def _find_column(header: list[str | None], keywords: list[str]) -> int | None:
    """Ищет индекс столбца по ключевым словам в заголовке."""
    for i, cell in enumerate(header):
        if cell:
            cell_lower = cell.lower().strip()
            for kw in keywords:
                if kw in cell_lower:
                    return i
    return None


def _parse_int(value: str | None, default: int = 1) -> int:
    """Парсит число из строки."""
    if not value:
        return default
    nums = re.findall(r"\d+", str(value))
    return int(nums[0]) if nums else default
