import os
import threading

import uvicorn

import db
import demo_data
from bot import start_polling, background_scheduler, setup_menu_buttons


def run_app():
    uvicorn.run("app:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), log_level="info")


if __name__ == "__main__":
    db.init_db()

    # Демо-сотрудники для показа проекта: переменная DEMO_DATA=on или DEMO_DATA=clear
    demo_mode = os.getenv("DEMO_DATA", "").strip().lower()
    if demo_mode == "on":
        demo_data.seed()
    elif demo_mode == "clear":
        demo_data.clear()

    # Бот
    threading.Thread(target=start_polling, daemon=True).start()
    # Ежедневные сообщения: пульс-опрос и поздравления с днём рождения
    threading.Thread(target=background_scheduler, daemon=True).start()
    # Кнопка панели у админов, у сотрудников её нет
    threading.Thread(target=setup_menu_buttons, daemon=True).start()

    # Сайт мини-приложения
    run_app()
