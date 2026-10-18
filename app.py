import os
from dotenv import load_dotenv
import hmac
import hashlib
import json
from typing import Optional
from datetime import datetime
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import db
load_dotenv()
app = FastAPI()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "").split(","))) if os.getenv("ADMIN_IDS") else []

def validate_init_data(init_data: str) -> Optional[dict]:
    """Validate Telegram WebApp initData using HMAC-SHA256"""
    try:
        parsed_data = dict(pair.split("=") for pair in init_data.split("&") if "=" in pair)
        
        hash_value = parsed_data.pop("hash", "")
        if not hash_value:
            return None
        
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed_data.items()))
        
        secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        
        if calculated_hash != hash_value:
            return None
        
        return parsed_data
    except Exception as e:
        print(f"Validation error: {e}")
        return None

@app.get("/")
def get_index():
    return FileResponse("templates/index.html")

@app.get("/api/users")
def get_users(init_data: str = Query(...)):
    validated = validate_init_data(init_data)
    if not validated:
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    try:
        user_data = json.loads(validated.get("user", "{}"))
        user_id = user_data.get("id")
        
        if user_id not in ADMIN_IDS:
            raise HTTPException(status_code=403, detail="Forbidden")
    except:
        raise HTTPException(status_code=400, detail="Invalid user data")
    
    users = db.get_all_users()
    return [
        {
            "user_id": u[0],
            "full_name": u[2] or "Без имени",
            "position": u[3] or "-",
            "test_score": u[6],
            "status": u[7],
            "engagement_avg": u[10],
            "risk": u[10] < 3.0
        }
        for u in users if u[7] != "fired"
    ]

@app.post("/api/broadcast")
def broadcast(data: dict, init_data: str = Query(...)):
    validated = validate_init_data(init_data)
    if not validated:
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    try:
        user_data = json.loads(validated.get("user", "{}"))
        user_id = user_data.get("id")
        
        if user_id not in ADMIN_IDS:
            raise HTTPException(status_code=403, detail="Forbidden")
    except:
        raise HTTPException(status_code=400, detail="Invalid user data")
    
    from bot import bot
    
    text = data.get("text", "")
    if not text:
        raise HTTPException(status_code=400, detail="Text is required")
    
    users = db.get_active_users()
    success = 0
    
    for u in users:
        try:
            bot.send_message(u[0], f"📢 **Объявление от HR:**\n\n{text}", parse_mode="Markdown")
            success += 1
        except:
            pass
    
    return {"success": success, "total": len(users)}

@app.post("/api/fire")
def fire_user(data: dict, init_data: str = Query(...)):
    validated = validate_init_data(init_data)
    if not validated:
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    try:
        user_data = json.loads(validated.get("user", "{}"))
        user_id = user_data.get("id")
        
        if user_id not in ADMIN_IDS:
            raise HTTPException(status_code=403, detail="Forbidden")
    except:
        raise HTTPException(status_code=400, detail="Invalid user data")
    
    target_id = data.get("target_id")
    if not target_id:
        raise HTTPException(status_code=400, detail="target_id is required")
    
    db.fire_user(target_id)
    
    from bot import bot
    try:
        bot.send_message(target_id, "⚠️ Ваш аккаунт деактивирован администратором.")
    except:
        pass
    
    return {"success": True}
