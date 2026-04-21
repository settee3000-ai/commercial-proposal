#!/usr/bin/env python3
"""
Извлекает рендеры из PDF дизайн-проекта.
Вызывается как subprocess из app.py.
Выводит JSON: {"Гостиная": ["images/thumbs/xxx.png"], ...}
"""
import sys
import json
from pathlib import Path

def main():
    if len(sys.argv) < 4:
        print("{}")
        return

    pdf_path = sys.argv[1]
    project_id = sys.argv[2]
    thumbs_dir = Path(sys.argv[3])
    thumbs_dir.mkdir(parents=True, exist_ok=True)

    try:
        import fitz
    except ImportError:
        sys.stderr.write("PyMuPDF not installed\n")
        print("{}")
        return

    try:
        from PIL import Image
    except ImportError:
        sys.stderr.write("Pillow not installed\n")
        print("{}")
        return

    import io

    room_mapping = [
        ("мастер", "Мастер-спальня"), ("спальн", "Мастер-спальня"),
        ("гостин", "Гостиная"), ("кухн", "Кухня-столовая"),
        ("столов", "Кухня-столовая"), ("кабинет", "Кабинет"),
        ("детск", "Детская"), ("прихож", "Прихожая"),
        ("гардероб", "Гардеробная"), ("постироч", "Постирочная"),
        ("санузел", "Санузел"),
    ]

    room_renders = {}
    render_index = 0

    doc = fitz.open(pdf_path)

    for i in range(len(doc)):
        page = doc[i]
        text = page.get_text()
        text_lower = text.lower()

        if "3d-визуализация помещени" not in text_lower:
            continue
        if "ведомость" in text_lower or "план " in text_lower or len(text) > 1000:
            continue

        room_name = None
        for pattern, rname in room_mapping:
            if pattern in text_lower:
                room_name = rname
                break

        if not room_name:
            continue

        pix = page.get_pixmap(dpi=100)
        img_data = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_data))
        ratio = 600 / img.width
        img = img.resize((600, int(img.height * ratio)), Image.LANCZOS)
        img_name = f"{project_id}_{render_index}.png"
        img.save(str(thumbs_dir / img_name), "PNG", optimize=True)
        img_path = f"images/thumbs/{img_name}"
        render_index += 1

        room_renders.setdefault(room_name, []).append(img_path)

    doc.close()

    sys.stderr.write(f"Extracted {render_index} renders for {len(room_renders)} rooms\n")
    print(json.dumps(room_renders, ensure_ascii=False))


if __name__ == "__main__":
    main()
