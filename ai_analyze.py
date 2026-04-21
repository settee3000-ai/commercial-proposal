#!/usr/bin/env python3
"""
Анализ дизайн-проекта с помощью Claude API.
Принимает изображения + ТЗ, возвращает список мебели в JSON.
"""
from __future__ import annotations

import json
import sys
import base64
import os
from pathlib import Path


MODEL = "claude-sonnet-4-5"

SYSTEM_PROMPT = """Ты — эксперт по мягкой мебели фабрики Settee. Анализируешь дизайн-проекты и формируешь список мебели для коммерческого предложения.

Фабрика Settee производит ТОЛЬКО мягкую мебель:
- Диваны (угловые, прямые, модульные, софы)
- Кресла
- Кровати (с мягким изголовьем, с подъёмным механизмом)
- Пуфы, банкетки, скамьи
- Стулья с мягкой обивкой
- Мягкие стеновые панели
- Изголовья кроватей

Стандартное описание позиции:
- Изготовление по чертежу
- Каркас: массив/фанера (для диванов, кресел)
- Наполнение: резинотканевые ремни, вязкоэластичная пена, холкон (для мягкой мебели)
- Опоры: скрытые 30 мм (если применимо)
- Материал обивки: на согласовании

Возвращай ТОЛЬКО валидный JSON — массив объектов. Никакого текста до или после.
Формат каждого объекта:
{
  "name": "Название позиции",
  "room": "Название комнаты",
  "dimensions": "ШxГxВ в мм",
  "quantity": 1,
  "description": "Изготовление по чертежу. Каркас: ... Наполнение: ... Материал обивки: на согласовании"
}

ВАЖНО: Определяй ТОЛЬКО мягкую мебель из категорий Settee. Игнорируй корпусную мебель (шкафы, комоды, тумбы, стеллажи), светильники, сантехнику, декор, ковры, шторы."""


def encode_image(path: str) -> tuple[str, str]:
    """Кодирует изображение в base64, сжимая если нужно. Возвращает (base64, media_type)."""
    try:
        from PIL import Image
        import io
        img = Image.open(path)
        # Сжимаем до 1200px — Claude хорошо работает с таким размером
        if img.width > 1200 or img.height > 1200:
            img.thumbnail((1200, 1200), Image.LANCZOS)
        if img.mode == "RGBA":
            img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode("utf-8"), "image/jpeg"
    except Exception:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8"), "image/jpeg"


def _load_api_key() -> str:
    """Загружает API-ключ из .env или переменной окружения."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("ANTHROPIC_API_KEY="):
                return line.split("=", 1)[1].strip()
    return ""


def analyze(image_paths: list[str], task_text: str) -> list[dict]:
    """Анализирует изображения + ТЗ и возвращает список мебели."""
    api_key = _load_api_key()
    if not api_key:
        sys.stderr.write("ANTHROPIC_API_KEY не настроен\n")
        return []

    try:
        import anthropic
    except ImportError:
        sys.stderr.write("anthropic SDK не установлен\n")
        return []

    # Готовим контент с изображениями
    content = []
    for path in image_paths[:8]:  # максимум 8 изображений
        if not Path(path).exists():
            continue
        img_b64, media_type = encode_image(path)
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": img_b64,
            },
        })

    if not content:
        sys.stderr.write("Нет изображений для анализа\n")
        return []

    content.append({
        "type": "text",
        "text": f"Техническое задание:\n{task_text}\n\nПроанализируй изображения и составь список мягкой мебели Settee. Верни только JSON массив.",
    })

    try:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content}],
        )

        text = msg.content[0].text
        items = _extract_json(text)
        return items

    except Exception as e:
        sys.stderr.write(f"Claude API error: {e}\n")
        return []


def _extract_json(text: str) -> list[dict]:
    """Извлекает JSON массив из текста ответа."""
    text = text.strip()
    # Убираем markdown code blocks если есть
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "items" in data:
            return data["items"]
    except json.JSONDecodeError:
        pass

    start = text.find("[")
    end = text.rfind("]")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass

    return []


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 ai_analyze.py <image1> [image2...] <task_text>")
        sys.exit(1)

    task = sys.argv[-1]
    imgs = sys.argv[1:-1]
    result = analyze(imgs, task)
    print(json.dumps(result, ensure_ascii=False, indent=2))
