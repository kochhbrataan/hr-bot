"""Демо-сотрудники для показа проекта.

Включается переменной окружения DEMO_DATA:
  DEMO_DATA=on     - добавить демо-сотрудников
  DEMO_DATA=clear  - убрать их из панели (помечаются уволенными)

У демо-сотрудников Telegram ID начинаются с 9000000000, настоящих людей с такими ID нет.
"""
from datetime import datetime, timedelta

import db

BASE_ID = 9_000_000_000

# (ФИО, должность, вовлечённость, баллы теста, статус онбординга, день рождения MM-DD)
DEMO = [
    ("Айгерим Сейтказиева", "Менеджер по продажам", 4.8, 3, "completed", "03-14"),
    ("Данияр Омаров", "Backend-разработчик", 4.5, 3, "completed", "07-02"),
    ("Мария Лебедева", "HR-менеджер", 4.2, 3, "completed", "11-21"),
    ("Ержан Нурпеисов", "Аналитик данных", 3.9, 2, "completed", "01-30"),
    ("Ольга Ковалёва", "Бухгалтер", 3.6, 2, "completed", "09-09"),
    ("Тимур Жаксыбеков", "Специалист поддержки", 3.3, 3, "completed", "05-17"),
    ("Анна Волкова", "Дизайнер интерфейсов", 3.1, 2, "completed", "12-05"),
    ("Сергей Петров", "Тестировщик", 2.8, 1, "completed", "04-26"),
    ("Динара Касымова", "Маркетолог", 2.5, 2, "started", "08-13"),
    ("Андрей Смирнов", "Менеджер проектов", 2.2, 1, "started", "02-08"),
    ("Асель Бекова", "Администратор офиса", 1.9, 1, "completed", "10-03"),
    ("Николай Фёдоров", "Системный администратор", 1.6, 0, "started", "06-24"),
    ("Жанна Исмаилова", "Юрист", 4.0, 3, "completed", "01-11"),
    ("Виктор Морозов", "Логист", 3.4, 2, "completed", "03-29"),
    ("Камила Рахимова", "Стажёр-аналитик", 0.0, 0, "started", "08-30"),
    ("Павел Громов", "Руководитель отдела продаж", 4.9, 3, "completed", "07-19"),
    ("Салтанат Мусина", "SMM-специалист", 2.7, 2, "completed", "12-28"),
    ("Игорь Белов", "DevOps-инженер", 3.7, 3, "completed", "05-05"),
]


def _update(user_id, **fields):
    """Обновляет сотрудника. Если в базе нет поля position - сохраняет остальное."""
    try:
        db.update_user(user_id, **fields)
    except Exception:
        fields.pop("position", None)
        db.update_user(user_id, **fields)


def seed():
    created = 0
    for i, (name, position, eng, score, status, bday) in enumerate(DEMO, start=1):
        user_id = BASE_ID + i
        try:
            if not db.get_user(user_id):
                db.create_user(user_id, f"demo_user_{i}", "newcomer")
                created += 1
            last_seen = (datetime.now() - timedelta(days=i % 6, hours=i)).strftime("%Y-%m-%d %H:%M")
            _update(
                user_id,
                full_name=name,
                position=position,
                birthday=bday,
                test_score=score,
                status=status,
                engagement_avg=eng,
                last_activity=last_seen,
            )
        except Exception as e:
            print(f"Demo user {user_id} error: {e}")
    print(f"Демо-данные: добавлено {created}, всего демо-сотрудников {len(DEMO)}")


def clear():
    for i in range(1, len(DEMO) + 1):
        user_id = BASE_ID + i
        try:
            if db.get_user(user_id):
                db.fire_user(user_id)
        except Exception as e:
            print(f"Demo clear {user_id} error: {e}")
    print("Демо-сотрудники убраны из панели")
