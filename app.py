import os
import html
import hmac
import hashlib
import json
from typing import Optional
from urllib.parse import parse_qsl

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse

import db

load_dotenv()
app = FastAPI()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x]


def validate_init_data(init_data: str) -> Optional[dict]:
    """Проверка подписи Telegram WebApp initData (HMAC-SHA256)."""
    try:
        # parse_qsl сам декодирует значения (%7B -> {), как требует Telegram
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))

        hash_value = parsed.pop("hash", "")
        if not hash_value:
            return None

        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))

        secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

        if not hmac.compare_digest(calculated_hash, hash_value):
            return None

        return parsed
    except Exception as e:
        print(f"Validation error: {e}")
        return None


def require_admin(init_data: str) -> int:
    """Проверяет подпись и что пользователь есть в ADMIN_IDS. Возвращает его ID."""
    validated = validate_init_data(init_data)
    if not validated:
        raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        user_id = json.loads(validated.get("user", "{}")).get("id")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user data")

    if user_id not in ADMIN_IDS:
        raise HTTPException(status_code=403, detail="Forbidden")
    return user_id


@app.get("/")
def get_index():
    # index.html лежит в корне проекта рядом с app.py
    return FileResponse(os.path.join(BASE_DIR, "index.html"))


@app.get("/api/users")
def get_users(init_data: str = Query(...)):
    require_admin(init_data)

    users = db.get_all_users()
    result = []
    for u in users:
        # Уволенных и самих администраторов в списке сотрудников не показываем
        if u[7] == "fired" or u[4] == "admin" or u[0] in ADMIN_IDS:
            continue
        avg = float(u[10] or 0)
        result.append({
            "user_id": u[0],
            "full_name": u[2] or "Без имени",
            "position": u[3] or "-",
            "test_score": u[6] or 0,
            "status": u[7],
            "engagement_avg": avg,
            "risk": 0 < avg < 3.0,
        })
    return result


@app.post("/api/broadcast")
def broadcast(data: dict, init_data: str = Query(...)):
    require_admin(init_data)

    from bot import bot

    text = (data.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text is required")

    users = db.get_active_users()
    success = 0

    for u in users:
        try:
            # Текст экранируем: бот отправляет сообщения в режиме HTML
            bot.send_message(u[0], f"📢 <b>Объявление от HR:</b>\n\n{html.escape(text)}")
            success += 1
        except Exception as e:
            print(f"Broadcast to {u[0]} failed: {e}")

    return {"success": success, "total": len(users)}


@app.post("/api/fire")
def fire_user(data: dict, init_data: str = Query(...)):
    require_admin(init_data)

    target_id = data.get("target_id")
    if not target_id:
        raise HTTPException(status_code=400, detail="target_id is required")

    db.fire_user(target_id)

    from bot import bot
    try:
        bot.send_message(target_id, "⚠️ Ваш аккаунт деактивирован администратором.")
    except Exception as e:
        print(f"Fire notify {target_id} failed: {e}")

    return {"success": True}
