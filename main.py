import os
import threading
import uvicorn
import db
from bot import start_polling

def run_app():
    uvicorn.run("app:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), log_level="info")

if __name__ == "__main__":
    db.init_db()
    
    bot_thread = threading.Thread(target=start_polling, daemon=True)
    bot_thread.start()
    
    run_app()
