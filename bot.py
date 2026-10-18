import os
import threading
from datetime import datetime
from dotenv import load_dotenv
from telebot import TeleBot, custom_filters
from telebot.handler_backends import State, StatesGroup
from telebot.storage import StateMemoryStorage
from telebot.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)
import db
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "").split(","))) if os.getenv("ADMIN_IDS") else []
MINI_APP_URL = os.getenv("MINI_APP_URL", "http://localhost:8000")

bot = TeleBot(TOKEN, state_storage=StateMemoryStorage())

class OnboardStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_birthday = State()
    waiting_for_doc = State()
    taking_test_q1 = State()
    taking_test_q2 = State()
    taking_test_q3 = State()
    completed = State()
    waiting_for_admin_message = State()
    waiting_for_request_text = State()

def get_main_menu_markup(is_admin=False):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    if is_admin:
        markup.add(
            KeyboardButton("👑 Панель HR & Аналитика"),
            KeyboardButton("📢 Сделать рассылку"),
            KeyboardButton("📊 Отчет по рискам увольнения"),
        )
    else:
        markup.add(
            KeyboardButton("📚 База знаний & Сайты"),
            KeyboardButton("📋 Статус онбординга"),
            KeyboardButton("❓ Частые вопросы (FAQ)"),
            KeyboardButton("📦 Заказать пропуск/технику"),
            KeyboardButton("📞 Связаться с HR"),
        )
    return markup

def background_scheduler():
    while True:
        try:
            now = datetime.now()
            if now.hour == 10 and now.minute == 0:
                today_str = now.strftime("%m-%d")
                users = db.get_all_users()

                for u in users:
                    u_id, _, full_name, _, _, _, _, _, bday, _, _ = u
                    if bday and bday.endswith(today_str):
                        try:
                            bot.send_message(u_id, f"🎉🎂 **С днем рождения, {full_name or 'Коллега'}!**\nКоманда компании искренне поздравляет тебя!", parse_mode="Markdown")
                        except:
                            pass

                    try:
                        markup = InlineKeyboardMarkup(row_width=5)
                        markup.add(
                            InlineKeyboardButton("1 😞", callback_data="poll_1"),
                            InlineKeyboardButton("2 😕", callback_data="poll_2"),
                            InlineKeyboardButton("3 😐", callback_data="poll_3"),
                            InlineKeyboardButton("4 😊", callback_data="poll_4"),
                            InlineKeyboardButton("5 🔥", callback_data="poll_5"),
                        )
                        bot.send_message(u_id, "📊 **Ежедневный пульс-опрос:**\nКак твое настроение от 1 до 5?", reply_markup=markup, parse_mode="Markdown")
                    except:
                        pass

                import time
                time.sleep(3660)
            else:
                import time
                time.sleep(30)
        except Exception as e:
            print(f"Background scheduler error: {e}")
            import time
            time.sleep(60)

@bot.message_handler(commands=["start"])
def cmd_start(message):
    user_id = message.from_user.id
    username = message.from_user.username
    is_admin = user_id in ADMIN_IDS
    role = "admin" if is_admin else "newcomer"

    user = db.get_user(user_id)
    if not user:
        db.create_user(user_id, username, role)
        if is_admin:
            bot.send_message(message.chat.id, "👑 **Панель администратора активирована.**", reply_markup=get_main_menu_markup(is_admin=True), parse_mode="Markdown")
        else:
            bot.send_message(message.chat.id, "👋 **Добро пожаловать в компанию!**\n\nПожалуйста, введи свои **ФИО** и должность:", parse_mode="Markdown")
            bot.set_state(user_id, OnboardStates.waiting_for_name, message.chat.id)
    else:
        db.update_user(user_id, role=role)
        if is_admin:
            bot.send_message(message.chat.id, "👑 Панель администратора:", reply_markup=get_main_menu_markup(is_admin=True))
        else:
            bot.send_message(message.chat.id, f"С возвращением, {user[2] or 'Коллега'}!", reply_markup=get_main_menu_markup(is_admin=False))
            bot.set_state(user_id, OnboardStates.completed, message.chat.id)

@bot.message_handler(state=OnboardStates.waiting_for_name, content_types=["text"])
def process_name(message):
    user_id = message.from_user.id
    db.update_user(user_id, full_name=message.text)
    bot.send_message(message.chat.id, "📅 Теперь укажи свою **дату рождения** в формате `ДД.ММ.ГГГГ`:", parse_mode="Markdown")
    bot.set_state(user_id, OnboardStates.waiting_for_birthday, message.chat.id)

@bot.message_handler(state=OnboardStates.waiting_for_birthday, content_types=["text"])
def process_birthday(message):
    user_id = message.from_user.id
    try:
        parts = message.text.strip().split(".")
        bday_db = f"{parts[1]}-{parts[0]}"
    except:
        bday_db = "01-01"
    
    db.update_user(user_id, birthday=bday_db)
    bot.send_message(message.chat.id, "✅ Принято!\n\nЗагрузи **фото или скан паспорта / трудового договора**:", parse_mode="Markdown")
    bot.set_state(user_id, OnboardStates.waiting_for_doc, message.chat.id)

@bot.message_handler(state=OnboardStates.waiting_for_doc, content_types=["document", "photo"])
def process_document(message):
    user_id = message.from_user.id
    file_info = None
    
    if message.document:
        file_info = bot.get_file(message.document.file_id)
        file_name = message.document.file_name
    elif message.photo:
        file_info = bot.get_file(message.photo[-1].file_id)
        file_name = f"photo_{user_id}.jpg"
    
    if file_info:
        uploaded_dir = os.getenv("UPLOAD_DIR", "/data/uploads")
        os.makedirs(uploaded_dir, exist_ok=True)
        downloaded_file = bot.download_file(file_info.file_path)
        save_path = os.path.join(uploaded_dir, f"{user_id}_{file_name}")
        with open(save_path, "wb") as f:
            f.write(downloaded_file)
        db.update_user(user_id, doc_path=save_path)
    
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("A) Корпоративный мессенджер", callback_data="test_q1_a"),
        InlineKeyboardButton("B) Личная почта", callback_data="test_q1_b"),
        InlineKeyboardButton("C) Социальные сети", callback_data="test_q1_c"),
    )
    bot.send_message(message.chat.id, "📄 Документ успешно сохранен!\n\n**Вопрос 1:** Какой основной инструмент для коммуникаций?", reply_markup=markup, parse_mode="Markdown")
    bot.set_state(user_id, OnboardStates.taking_test_q1, message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("test_q1_"))
def process_test_q1(call):
    user_id = call.from_user.id
    score = 1 if call.data == "test_q1_a" else 0
    db.update_user(user_id, test_score=score)
    
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("A) У руководителя или в ERP", callback_data="test_q2_a"),
        InlineKeyboardButton("B) В поисковике Google", callback_data="test_q2_b"),
        InlineKeyboardButton("C) Спросить у коллеги", callback_data="test_q2_c"),
    )
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="✅ Ответ принят!\n\n**Вопрос 2:** Где оформляется отпуск?", reply_markup=markup, parse_mode="Markdown")
    bot.set_state(user_id, OnboardStates.taking_test_q2, call.message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("test_q2_"))
def process_test_q2(call):
    user_id = call.from_user.id
    user = db.get_user(user_id)
    current_score = user[6] if user else 0
    score = current_score + 1 if call.data == "test_q2_a" else current_score
    db.update_user(user_id, test_score=score)
    
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("A) Корпоративная почта и мессенджер", callback_data="test_q3_a"),
        InlineKeyboardButton("B) Личный Telegram", callback_data="test_q3_b"),
    )
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="✅ Ответ принят!\n\n**Вопрос 3:** Какие каналы приоритетны?", reply_markup=markup, parse_mode="Markdown")
    bot.set_state(user_id, OnboardStates.taking_test_q3, call.message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("test_q3_"))
def process_test_q3(call):
    user_id = call.from_user.id
    user = db.get_user(user_id)
    current_score = user[6] if user else 0
    score = current_score + 1 if call.data == "test_q3_a" else current_score
    db.update_user(user_id, test_score=score, status="completed")
    
    bot.answer_callback_query(call.id, "Тест завершен!")
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=f"🎉 **Онбординг завершен!**\n\nТвой результат: **{score}/3 баллов**.", parse_mode="Markdown")
    
    is_admin = user_id in ADMIN_IDS
    bot.send_message(call.message.chat.id, "Главное меню:", reply_markup=get_main_menu_markup(is_admin=is_admin))
    bot.set_state(user_id, OnboardStates.completed, call.message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("poll_"))
def process_poll(call):
    score = int(call.data.replace("poll_", ""))
    user_id = call.from_user.id
    user = db.get_user(user_id)
    current_avg = user[10] if user and user[10] else 5.0
    new_avg = round((current_avg + score) / 2, 1)
    
    db.update_user(user_id, engagement_avg=new_avg, last_activity=datetime.now().strftime("%Y-%m-%d %H:%M"))
    
    bot.answer_callback_query(call.id, "Спасибо за обратную связь! ❤️")
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=f"📊 **Опрос принят!** Твоя оценка: {score}/5.")

@bot.message_handler(func=lambda msg: msg.text == "📚 База знаний & Сайты", state=[OnboardStates.completed, None])
def kb_handler(message):
    if message.from_user.id in ADMIN_IDS:
        return
    text = "📚 **База знаний:**\n\n📖 [Корпоративный портал](https://example.com)\n📋 [Правила компании](https://example.com)\n🛠 [Confluence](https://example.com)"
    bot.send_message(message.chat.id, text, parse_mode="Markdown", disable_web_page_preview=True)

@bot.message_handler(func=lambda msg: msg.text == "📋 Статус онбординга", state=[OnboardStates.completed, None])
def status_handler(message):
    if message.from_user.id in ADMIN_IDS:
        return
    user = db.get_user(message.from_user.id)
    if user:
        status_text = f"👤 **Твой профиль:**\n\n• ФИО: {user[2] or 'Не указано'}\n• Тест: {user[6]} / 3 баллов\n• Статус: {'Пройден ✅' if user[7] == 'completed' else 'В процессе ⏳'}\n• Вовлеченность: {user[10]}⭐"
        bot.send_message(message.chat.id, status_text, parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "❓ Частые вопросы (FAQ)", state=[OnboardStates.completed, None])
def faq_handler(message):
    if message.from_user.id in ADMIN_IDS:
        return
    faq_text = "💡 **Справочный центр:**\n\n🔹 **Как взять справку?**\nЧерез кнопку «Заказать пропуск/технику».\n\n🔹 **Как оформить отпуск?**\nСогласуйте с руководителем, подайте в ERP за 2 недели."
    bot.send_message(message.chat.id, faq_text, parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "📦 Заказать пропуск/технику", state=[OnboardStates.completed, None])
def request_item(message):
    if message.from_user.id in ADMIN_IDS:
        return
    bot.send_message(message.chat.id, "📦 Опишите, что нужно заказать (ноутбук, пропуск, справка):")
    bot.set_state(message.from_user.id, OnboardStates.waiting_for_request_text, message.chat.id)

@bot.message_handler(state=OnboardStates.waiting_for_request_text, content_types=["text"])
def process_request(message):
    user_id = message.from_user.id
    user = db.get_user(user_id)
    full_name = user[2] if user and user[2] else "Не указано"
    username = f"@{user[1]}" if user and user[1] else "нет username"
    
    db.create_request(user_id, "Имущество/Документ", message.text)
    
    for admin_id in ADMIN_IDS:
        try:
            bot.send_message(admin_id, f"📦 **Новая заявка!**\n\n• Сотрудник: {full_name} ({username})\n• ID: `{user_id}`\n\n**Запрос:**\n{message.text}", parse_mode="Markdown")
        except:
            pass
    
    bot.send_message(message.chat.id, "✅ Заявка передана администраторам!", reply_markup=get_main_menu_markup(is_admin=False))
    bot.set_state(user_id, OnboardStates.completed, message.chat.id)

@bot.message_handler(func=lambda msg: msg.text == "📞 Связаться с HR", state=[OnboardStates.completed, None])
def contact_hr(message):
    if message.from_user.id in ADMIN_IDS:
        return
    bot.send_message(message.chat.id, "✍️ Напишите ваше сообщение для HR-отдела:")
    bot.set_state(message.from_user.id, OnboardStates.waiting_for_admin_message, message.chat.id)

@bot.message_handler(state=OnboardStates.waiting_for_admin_message, content_types=["text"])
def process_hr_message(message):
    user_id = message.from_user.id
    user = db.get_user(user_id)
    full_name = user[2] if user and user[2] else "Не указано"
    username = f"@{user[1]}" if user and user[1] else "нет username"
    
    for admin_id in ADMIN_IDS:
        try:
            bot.send_message(admin_id, f"🚨 **Сообщение от сотрудника!**\n\n• ФИО: {full_name}\n• Username: {username}\n• ID: `{user_id}`\n\n**Текст:**\n{message.text}", parse_mode="Markdown")
        except:
            pass
    
    bot.send_message(message.chat.id, "✅ Сообщение отправлено HR!", reply_markup=get_main_menu_markup(is_admin=False))
    bot.set_state(user_id, OnboardStates.completed, message.chat.id)

@bot.message_handler(func=lambda msg: msg.text == "👑 Панель HR & Аналитика", state=[OnboardStates.completed, None])
def admin_panel(message):
    if message.from_user.id not in ADMIN_IDS:
        bot.send_message(message.chat.id, "❌ У вас нет доступа.")
        return
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("👑 Открыть панель", web_app=WebAppInfo(url=MINI_APP_URL)))
    bot.send_message(message.chat.id, "Откройте панель управления персоналом:", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "📊 Отчет по рискам увольнения", state=[OnboardStates.completed, None])
def risk_analysis(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    users = db.get_all_users()
    report = "⚠️ **Анализ рисков выгорания:**\n\n"
    risk_found = False
    
    for u in users:
        u_id, _, name, _, _, _, score, status, _, _, eng = u
        reasons = []
        if score < 2:
            reasons.append("Низкий балл за тест")
        if eng < 3.0:
            reasons.append("Низкая вовлеченность")
        if status == "started":
            reasons.append("Не завершил онбординг")
        
        if reasons:
            risk_found = True
            report += f"🚨 **{name or 'Без имени'}** (ID: `{u_id}`)\n   Факторы: {', '.join(reasons)}\n   Вовлеченность: {eng}⭐\n\n"
    
    if not risk_found:
        report += "✅ Сотрудников в зоне риска не обнаружено."
    
    bot.send_message(message.chat.id, report, parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "📢 Сделать рассылку", state=[OnboardStates.completed, None])
def broadcast_prompt(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    msg = bot.send_message(message.chat.id, "📢 Введите текст для массовой рассылки:")
    bot.register_next_step_handler(msg, execute_broadcast)

def execute_broadcast(message):
    text = message.text
    users = db.get_active_users()
    success, failed = 0, 0
    
    for u in users:
        try:
            bot.send_message(u[0], f"📢 **Объявление от HR:**\n\n{text}", parse_mode="Markdown")
            success += 1
        except:
            failed += 1
    
    bot.send_message(message.chat.id, f"✅ Рассылка завершена!\nУспешно: {success}\nНе удалось: {failed}")

bot.add_custom_filter(custom_filters.StateFilter(bot))

def start_polling():
    try:
        bot.infinity_polling()
    except Exception as e:
        print(f"Bot polling error: {e}")
