#!/usr/bin/env python3
"""
Веб-приложение Settee — генератор коммерческих предложений.
Каждое КП сохраняется как проект с возможностью повторного редактирования.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from datetime import datetime

from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
from werkzeug.utils import secure_filename

from parse_pdf import parse_pdf
from generate_pdf import generate_proposal_pdf

app = Flask(__name__)

BASE_DIR = Path(__file__).parent
app.config["UPLOAD_FOLDER"] = BASE_DIR / "uploads"
app.config["OUTPUT_FOLDER"] = BASE_DIR / "output"
app.config["IMAGES_FOLDER"] = BASE_DIR / "images" / "thumbs"
app.config["PROJECTS_FOLDER"] = BASE_DIR / "projects"
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

for folder in [app.config["UPLOAD_FOLDER"], app.config["OUTPUT_FOLDER"],
               app.config["IMAGES_FOLDER"], app.config["PROJECTS_FOLDER"]]:
    folder.mkdir(parents=True, exist_ok=True)

CONFIG_FILE = BASE_DIR / "config.json"


def load_config():
    with open(CONFIG_FILE, encoding="utf-8") as f:
        return json.load(f)


# --- Проекты ---

def list_projects():
    """Возвращает список всех сохранённых проектов."""
    projects = []
    for f in sorted(app.config["PROJECTS_FOLDER"].glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
            total = sum(
                item.get("price", 0) * item.get("quantity", 1)
                for room in data.get("rooms", [])
                for item in room.get("items", [])
            )
            item_count = sum(len(room.get("items", [])) for room in data.get("rooms", []))
            projects.append({
                "id": f.stem,
                "client_name": data.get("client_name", ""),
                "project_name": data.get("project_name", ""),
                "updated": datetime.fromtimestamp(f.stat().st_mtime).strftime("%d.%m.%Y %H:%M"),
                "total": total,
                "item_count": item_count,
            })
        except Exception:
            pass
    return projects


def load_project(project_id):
    path = app.config["PROJECTS_FOLDER"] / f"{project_id}.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


def save_project(project_id, data):
    path = app.config["PROJECTS_FOLDER"] / f"{project_id}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def delete_project_file(project_id):
    path = app.config["PROJECTS_FOLDER"] / f"{project_id}.json"
    if path.exists():
        path.unlink()


# --- Маршруты ---

@app.route("/")
def index():
    """Главная — список проектов."""
    projects = list_projects()
    return render_template("projects.html", projects=projects)


@app.route("/new")
def new_project():
    """Создать новый проект."""
    project_id = uuid.uuid4().hex[:12]
    data = {
        "client_name": "",
        "project_name": "",
        "discount_percent": 0,
        "rooms": [],
    }
    save_project(project_id, data)
    return redirect(url_for("edit_project", project_id=project_id))


@app.route("/edit/<project_id>")
def edit_project(project_id):
    """Редактирование проекта."""
    data = load_project(project_id)
    if data is None:
        return redirect(url_for("index"))
    config = load_config()
    return render_template("app.html",
                           project_id=project_id,
                           rooms=data.get("rooms", []),
                           client_name=data.get("client_name", ""),
                           project_name=data.get("project_name", ""),
                           discount_percent=data.get("discount_percent", 0),
                           config=config)


@app.route("/duplicate/<project_id>")
def duplicate_project(project_id):
    """Дублировать проект."""
    data = load_project(project_id)
    if data is None:
        return redirect(url_for("index"))
    new_id = uuid.uuid4().hex[:12]
    data["client_name"] = data.get("client_name", "") + " (копия)"
    save_project(new_id, data)
    return redirect(url_for("edit_project", project_id=new_id))


@app.route("/api/project/<project_id>/save", methods=["POST"])
def api_save_project(project_id):
    """Сохранить проект."""
    data = request.json
    save_project(project_id, data)
    return jsonify({"status": "ok"})


@app.route("/api/project/<project_id>/delete", methods=["POST"])
def api_delete_project(project_id):
    """Удалить проект."""
    delete_project_file(project_id)
    return jsonify({"status": "ok"})


@app.route("/api/upload-pdf/<project_id>", methods=["POST"])
def upload_pdf(project_id):
    if "file" not in request.files:
        return jsonify({"error": "Нет файла"}), 400

    file = request.files["file"]
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Нужен PDF файл"}), 400

    filename = secure_filename(file.filename) or "project.pdf"
    filepath = app.config["UPLOAD_FOLDER"] / filename
    file.save(str(filepath))

    items = parse_pdf(str(filepath))

    # Извлекаем рендеры
    try:
        import fitz
        doc = fitz.open(str(filepath))
        thumbs_dir = app.config["IMAGES_FOLDER"]
        img_index = 0
        for i in range(len(doc.pages)):
            page = doc[i]
            text = page.get_text()
            if "визуализация" in text.lower():
                pix = page.get_pixmap(dpi=150)
                from PIL import Image
                import io
                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data))
                ratio = 600 / img.width
                img = img.resize((600, int(img.height * ratio)), Image.LANCZOS)
                img_name = f"{project_id}_{img_index}.png"
                img.save(str(thumbs_dir / img_name), "PNG", optimize=True)
                if img_index < len(items):
                    items[img_index]["image"] = f"images/thumbs/{img_name}"
                img_index += 1
        doc.close()
    except Exception:
        pass

    rooms_dict = {}
    for item in items:
        room_name = item.pop("room", "") or "Основное"
        rooms_dict.setdefault(room_name, []).append(item)

    rooms = [{"name": name, "items": room_items} for name, room_items in rooms_dict.items()]

    # Сохраняем в проект
    data = load_project(project_id) or {}
    data["rooms"] = rooms
    if not data.get("project_name"):
        data["project_name"] = Path(file.filename).stem
    save_project(project_id, data)

    return jsonify({"status": "ok", "rooms": rooms, "count": len(items)})


@app.route("/api/upload-image", methods=["POST"])
def upload_image():
    if "file" not in request.files:
        return jsonify({"error": "Нет файла"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "Нет имени файла"}), 400

    ext = Path(file.filename).suffix.lower()
    if ext not in (".png", ".jpg", ".jpeg", ".webp"):
        return jsonify({"error": "Нужно изображение (PNG, JPG)"}), 400

    img_name = f"{uuid.uuid4().hex[:8]}{ext}"
    filepath = app.config["IMAGES_FOLDER"] / img_name
    file.save(str(filepath))

    try:
        from PIL import Image
        img = Image.open(str(filepath))
        if img.width > 600:
            ratio = 600 / img.width
            img = img.resize((600, int(img.height * ratio)), Image.LANCZOS)
            img.save(str(filepath), optimize=True)
    except Exception:
        pass

    return jsonify({"status": "ok", "path": f"images/thumbs/{img_name}"})


@app.route("/api/generate/<project_id>", methods=["POST"])
def generate(project_id):
    data = request.json
    config = load_config()

    rooms = data.get("rooms", [])
    client_name = data.get("client_name", "Клиент")
    project_name = data.get("project_name", "")
    discount = data.get("discount_percent", 0)

    # Сохраняем проект
    save_project(project_id, data)

    output_name = f"КП_{project_id}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    output_path = str(app.config["OUTPUT_FOLDER"] / output_name)

    generate_proposal_pdf(
        rooms=rooms,
        company=config["company"],
        client_name=client_name,
        project_name=project_name,
        discount_percent=discount,
        currency=config["proposal"].get("currency", "₽"),
        validity_days=config["proposal"].get("validity_days", 30),
        vat_included=config["proposal"].get("vat_included", False),
        output_path=output_path,
    )

    return jsonify({"status": "ok", "filename": output_name})


@app.route("/download/<filename>")
def download(filename):
    filepath = app.config["OUTPUT_FOLDER"] / filename
    if filepath.exists():
        return send_file(str(filepath), as_attachment=True)
    return "Файл не найден", 404


@app.route("/images/thumbs/<filename>")
def serve_image(filename):
    filepath = app.config["IMAGES_FOLDER"] / filename
    if filepath.exists():
        return send_file(str(filepath))
    return "", 404


if __name__ == "__main__":
    app.run(debug=True, port=5050)
