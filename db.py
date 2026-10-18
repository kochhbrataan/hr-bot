import sqlite3
import os
from contextlib import contextmanager
from typing import Any, List, Optional, Tuple

DB_PATH = os.getenv("DB_PATH", "/data/hr_bot.db")

def init_db():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            position TEXT,
            role TEXT DEFAULT 'newcomer',
            doc_path TEXT,
            test_score INTEGER DEFAULT 0,
            status TEXT DEFAULT 'started',
            birthday TEXT,
            last_activity TEXT,
            engagement_avg REAL DEFAULT 5.0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS requests (
            request_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            request_type TEXT,
            request_text TEXT,
            status TEXT DEFAULT 'pending'
        )
    """)
    conn.commit()
    conn.close()

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    try:
        yield conn
    finally:
        conn.close()

def execute_query(query: str, params: Tuple = (), fetchone: bool = False, fetchall: bool = False) -> Any:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        result = None
        if fetchone:
            result = cursor.fetchone()
        elif fetchall:
            result = cursor.fetchall()
        conn.commit()
        return result

def get_user(user_id: int) -> Optional[Tuple]:
    return execute_query("SELECT * FROM users WHERE user_id = ?", (user_id,), fetchone=True)

def create_user(user_id: int, username: str, role: str = "newcomer"):
    execute_query(
        "INSERT INTO users (user_id, username, role) VALUES (?, ?, ?)",
        (user_id, username, role)
    )

def update_user(user_id: int, **kwargs):
    for key, value in kwargs.items():
        execute_query(f"UPDATE users SET {key} = ? WHERE user_id = ?", (value, user_id))

def get_all_users() -> List[Tuple]:
    return execute_query("SELECT * FROM users", fetchall=True)

def get_active_users() -> List[Tuple]:
    return execute_query("SELECT * FROM users WHERE status != 'fired'", fetchall=True)

def create_request(user_id: int, request_type: str, request_text: str):
    execute_query(
        "INSERT INTO requests (user_id, request_type, request_text) VALUES (?, ?, ?)",
        (user_id, request_type, request_text)
    )

def fire_user(user_id: int):
    execute_query(
        "UPDATE users SET status = 'fired', role = 'dismissed' WHERE user_id = ?",
        (user_id,)
    )
