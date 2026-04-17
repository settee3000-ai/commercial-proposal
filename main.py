#!/usr/bin/env python3
"""
Генератор коммерческих предложений по мебели из дизайн-проекта.

Использование:
  1. Парсинг PDF и создание черновика:
     python main.py parse input/design_project.pdf

  2. Редактирование items.json — добавьте цены и скорректируйте позиции

  3. Генерация PDF:
     python main.py generate --client "Иванов И.И." --project "Квартира на Тверской"
"""

import json
import sys
from pathlib import Path

from parse_pdf import parse_pdf
from generate_pdf import generate_proposal_pdf

ITEMS_FILE = "items.json"
CONFIG_FILE = "config.json"


def load_config() -> dict:
    with open(CONFIG_FILE, encoding="utf-8") as f:
        return json.load(f)


def cmd_parse(pdf_path: str):
    """Парсит PDF и сохраняет черновик items.json для редактирования."""
    if not Path(pdf_path).exists():
        print(f"Ошибка: файл {pdf_path} не найден")
        sys.exit(1)

    print(f"Парсинг {pdf_path}...")
    items = parse_pdf(pdf_path)
    print(f"Найдено позиций: {len(items)}")

    # Группируем по комнатам
    rooms_dict: dict[str, list] = {}
    for item in items:
        room_name = item.pop("room", "") or "Основное"
        rooms_dict.setdefault(room_name, []).append(item)

    rooms = [{"name": name, "items": room_items} for name, room_items in rooms_dict.items()]

    # Сохраняем для редактирования
    with open(ITEMS_FILE, "w", encoding="utf-8") as f:
        json.dump(rooms, f, ensure_ascii=False, indent=2)

    print(f"\nСохранено в {ITEMS_FILE}")
    print("Теперь отредактируйте файл:")
    print("  - Проверьте/исправьте названия мебели")
    print("  - Укажите цены (поле 'price')")
    print("  - Скорректируйте количество (поле 'quantity')")
    print("  - Добавьте размеры (поле 'dimensions')")
    print("  - Распределите по комнатам при необходимости")
    print(f"\nЗатем запустите: python main.py generate --client \"Имя клиента\"")


def cmd_generate(client_name: str, project_name: str = ""):
    """Генерирует PDF коммерческого предложения из items.json."""
    if not Path(ITEMS_FILE).exists():
        print(f"Ошибка: {ITEMS_FILE} не найден. Сначала запустите: python main.py parse <pdf>")
        sys.exit(1)

    config = load_config()

    with open(ITEMS_FILE, encoding="utf-8") as f:
        rooms = json.load(f)

    # Проверяем, что цены заполнены
    total_items = sum(len(r["items"]) for r in rooms)
    priced_items = sum(1 for r in rooms for item in r["items"] if item.get("price", 0) > 0)

    if priced_items == 0:
        print("⚠ Ни одна позиция не имеет цены — генерируем черновик.")

    if priced_items < total_items:
        print(f"⚠ Цены указаны у {priced_items} из {total_items} позиций. Позиции без цены будут с нулевой суммой.")

    output_path = generate_proposal_pdf(
        rooms=rooms,
        company=config["company"],
        client_name=client_name,
        project_name=project_name,
        discount_percent=config["proposal"].get("discount_percent", 0),
        currency=config["proposal"].get("currency", "₽"),
        validity_days=config["proposal"].get("validity_days", 30),
        vat_included=config["proposal"].get("vat_included", True),
    )

    print(f"PDF создан: {output_path}")


def cmd_demo():
    """Создаёт демо items.json с примером данных для тестирования."""
    demo_rooms = [
        {
            "name": "Гостиная",
            "items": [
                {"name": "Диван угловой", "description": "Ткань, серый, раскладной", "dimensions": "280×180×85", "quantity": 1, "price": 89000},
                {"name": "Журнальный стол", "description": "Дуб, круглый", "dimensions": "Ø80×45", "quantity": 1, "price": 24000},
                {"name": "Кресло", "description": "Велюр, зелёный", "dimensions": "75×80×90", "quantity": 2, "price": 32000},
                {"name": "Стеллаж открытый", "description": "Металл + дерево, 5 полок", "dimensions": "120×35×180", "quantity": 1, "price": 18500},
                {"name": "Торшер напольный", "description": "Латунь, абажур лён", "dimensions": "Ø40×165", "quantity": 1, "price": 12000},
                {"name": "Ковёр", "description": "Шерсть, ручная работа", "dimensions": "200×300", "quantity": 1, "price": 45000},
            ],
        },
        {
            "name": "Спальня",
            "items": [
                {"name": "Кровать двуспальная", "description": "С подъёмным механизмом, экокожа", "dimensions": "180×200", "quantity": 1, "price": 65000},
                {"name": "Тумба прикроватная", "description": "2 ящика, шпон ореха", "dimensions": "50×40×55", "quantity": 2, "price": 14000},
                {"name": "Шкаф-купе", "description": "3 двери, зеркальные фасады", "dimensions": "240×60×240", "quantity": 1, "price": 78000},
                {"name": "Комод", "description": "4 ящика, плавное закрывание", "dimensions": "120×45×85", "quantity": 1, "price": 34000},
            ],
        },
        {
            "name": "Кухня-столовая",
            "items": [
                {"name": "Обеденный стол", "description": "Раздвижной, керамика", "dimensions": "160(220)×90×76", "quantity": 1, "price": 52000},
                {"name": "Стул обеденный", "description": "Дерево, мягкое сиденье", "dimensions": "45×52×88", "quantity": 6, "price": 8500},
                {"name": "Барный стул", "description": "Поворотный, экокожа", "dimensions": "42×45×105", "quantity": 3, "price": 11000},
            ],
        },
    ]

    with open(ITEMS_FILE, "w", encoding="utf-8") as f:
        json.dump(demo_rooms, f, ensure_ascii=False, indent=2)

    print(f"Демо-данные сохранены в {ITEMS_FILE}")
    print(f"Запустите: python main.py generate --client \"Иванов И.И.\" --project \"Квартира на Тверской\"")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    command = sys.argv[1]

    if command == "parse":
        if len(sys.argv) < 3:
            print("Использование: python main.py parse <путь_к_pdf>")
            sys.exit(1)
        cmd_parse(sys.argv[2])

    elif command == "generate":
        client = ""
        project = ""
        i = 2
        while i < len(sys.argv):
            if sys.argv[i] == "--client" and i + 1 < len(sys.argv):
                client = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == "--project" and i + 1 < len(sys.argv):
                project = sys.argv[i + 1]
                i += 2
            else:
                i += 1

        if not client:
            print("Укажите имя клиента: python main.py generate --client \"Имя\"")
            sys.exit(1)

        cmd_generate(client, project)

    elif command == "demo":
        cmd_demo()

    else:
        print(f"Неизвестная команда: {command}")
        print("Доступные команды: parse, generate, demo")
        sys.exit(1)


if __name__ == "__main__":
    main()
