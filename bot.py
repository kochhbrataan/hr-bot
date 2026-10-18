import os
import re
import html
import time
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from telebot import TeleBot, custom_filters
from telebot.handler_backends import State, StatesGroup
from telebot.storage import StateMemoryStorage
from telebot.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    MenuButtonCommands,
    MenuButtonWebApp,
    ReplyKeyboardMarkup,
    WebAppInfo,
)

import db

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x]
MINI_APP_URL = os.getenv("MINI_APP_URL", "")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/data/uploads")
# Часовой пояс для утренних сообщений (Казахстан = +5). Можно поменять переменной TZ_OFFSET_HOURS
TZ = timezone(timedelta(hours=int(os.getenv("TZ_OFFSET_HOURS", "5"))))

# ======================= НАСТРОЙКИ ТЕКСТОВ (меняйте здесь) =======================

# Ссылки для кнопки «База знаний»: (название, адрес)
KB_LINKS = [
    ("📖 Корпоративный портал", "https://example.com"),
    ("📋 Правила компании", "https://example.com"),
    ("🛠 Confluence", "https://example.com"),
]

# Вопросы и ответы для кнопки «Частые вопросы»: (вопрос, ответ)
FAQ = [
    ("Как взять справку?", "Через кнопку «📦 Заказать пропуск/технику»."),
    ("Как оформить отпуск?", "Согласуйте с руководителем и подайте заявку в ERP за 2 недели."),
]

# ======================= КНОПКИ МЕНЮ =======================

BTN_KB = "📚 База знаний & Сайты"
BTN_STATUS = "📋 Статус онбординга"
BTN_FAQ = "❓ Частые вопросы (FAQ)"
BTN_ORDER = "📦 Заказать пропуск/технику"
BTN_HR = "📞 Связаться с HR"

BTN_PANEL = "👑 Панель HR & Аналитика"
BTN_RISK = "📊 Отчет по рискам увольнения"

EMPLOYEE_BUTTONS = {BTN_KB, BTN_STATUS, BTN_FAQ, BTN_ORDER, BTN_HR}

bot = TeleBot(TOKEN, state_storage=StateMemoryStorage(), parse_mode="HTML")
bot.add_custom_filter(custom_filters.StateFilter(bot))
esc = html.escape


class OnboardStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_position = State()
    waiting_for_birthday = State()
    waiting_for_doc = State()
    taking_test_q1 = State()
    taking_test_q2 = State()
    taking_test_q3 = State()
    completed = State()
    waiting_for_admin_message = State()
    waiting_for_request_text = State()


ACTIVE = [OnboardStates.completed, None]


def get_main_menu_markup(is_admin=False):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    if is_admin:
        markup.add(KeyboardButton(BTN_PANEL), KeyboardButton(BTN_RISK))
    else:
        markup.add(
            KeyboardButton(BTN_KB),
            KeyboardButton(BTN_STATUS),
            KeyboardButton(BTN_FAQ),
            KeyboardButton(BTN_ORDER),
            KeyboardButton(BTN_HR),
        )
    return markup


# ======================= ВСПОМОГАТЕЛЬНОЕ =======================

def is_admin_id(user_id):
    return user_id in ADMIN_IDS


def employee_ok(user_id):
    """Сотрудник существует, не админ и не уволен."""
    if is_admin_id(user_id):
        return False
    user = db.get_user(user_id)
    return bool(user) and user[7] != "fired"


def set_menu_button(chat_id, is_admin):
    """Админу показываем кнопку открытия панели, сотрудникам — ничего лишнего."""
    try:
        if is_admin and MINI_APP_URL.startswith("https://"):
            bot.set_chat_menu_button(chat_id, MenuButtonWebApp("Панель", WebAppInfo(url=MINI_APP_URL)))
        else:
            bot.set_chat_menu_button(chat_id, MenuButtonCommands())
    except Exception as e:
        print(f"Menu button error for {chat_id}: {e}")


def setup_menu_buttons():
    """При запуске выставляет кнопки меню всем уже известным пользователям."""
    time.sleep(5)
    try:
        for admin_id in ADMIN_IDS:
            set_menu_button(admin_id, True)
            time.sleep(0.1)
        for u in db.get_all_users():
            if u[0] not in ADMIN_IDS:
                set_menu_button(u[0], False)
                time.sleep(0.1)
    except Exception as e:
        print(f"setup_menu_buttons error: {e}")


def send_long(chat_id, blocks, header=""):
    """Отправляет список блоков текста, разбивая на сообщения до лимита Telegram."""
    text = header
    for block in blocks:
        if len(text) + len(block) + 2 > 3800:
            bot.send_message(chat_id, text)
            text = ""
        text += block + "\n\n"
    if text.strip():
        bot.send_message(chat_id, text)


# ======================= ЕЖЕДНЕВНЫЕ СООБЩЕНИЯ =======================

def poll_markup():
    markup = InlineKeyboardMarkup(row_width=5)
    markup.add(
        InlineKeyboardButton("1 😞", callback_data="poll_1"),
        InlineKeyboardButton("2 😕", callback_data="poll_2"),
        InlineKeyboardButton("3 😐", callback_data="poll_3"),
        InlineKeyboardButton("4 😊", callback_data="poll_4"),
        InlineKeyboardButton("5 🔥", callback_data="poll_5"),
    )
    return markup


def send_daily(now):
    today_str = now.strftime("%m-%d")
    for u in db.get_all_users():
        u_id, full_name, role, status, bday = u[0], u[2], u[4], u[7], u[8]
        if u_id in ADMIN_IDS or role == "admin" or status == "fired":
            continue

        if bday and bday.endswith(today_str):
            try:
                bot.send_message(
                    u_id,
                    f"🎉🎂 <b>С днём рождения, {esc(full_name or 'Коллега')}!</b>\nКоманда компании искренне поздравляет тебя!",
                )
            except Exception:
                pass

        try:
            bot.send_message(
                u_id,
                "📊 <b>Ежедневный пульс-опрос</b>\nКак твоё настроение от 1 до 5?",
                reply_markup=poll_markup(),
            )
        except Exception:
            pass
        time.sleep(0.05)


def background_scheduler():
    last_sent = None
    while True:
        try:
            now = datetime.now(TZ)
            today = now.strftime("%Y-%m-%d")
            if now.hour == 10 and last_sent != today:
                last_sent = today
                send_daily(now)
            time.sleep(30)
        except Exception as e:
            print(f"Background scheduler error: {e}")
            time.sleep(60)


# ======================= /start И ОНБОРДИНГ =======================

@bot.message_handler(commands=["start"])
def cmd_start(message):
    if message.chat.type != "private":
        return
    user_id = message.from_user.id
    chat_id = message.chat.id
    username = message.from_user.username
    is_admin = is_admin_id(user_id)
    user = db.get_user(user_id)

    # --- Администратор ---
    if is_admin:
        if not user:
            db.create_user(user_id, username, "admin")
        else:
            db.update_user(user_id, role="admin")
        bot.delete_state(user_id, chat_id)
        set_menu_button(chat_id, True)
        bot.send_message(
            chat_id,
            "👑 <b>Панель администратора</b>\n\nОткройте панель HR или посмотрите отчёт по рискам.",
            reply_markup=get_main_menu_markup(is_admin=True),
        )
        return

    # --- Сотрудник ---
    set_menu_button(chat_id, False)

    if user and user[7] == "fired":
        bot.send_message(chat_id, "Ваш аккаунт деактивирован. Обратитесь в HR-отдел.")
        return

    if not user:
        db.create_user(user_id, username, "newcomer")
        user = None

    if not user or not user[2]:
        bot.send_message(chat_id, "👋 <b>Добро пожаловать в компанию!</b>\n\nВведите ваши <b>ФИО</b> полностью:")
        bot.set_state(user_id, OnboardStates.waiting_for_name, chat_id)
    else:
        bot.send_message(
            chat_id,
            f"С возвращением, {esc(user[2])}!",
            reply_markup=get_main_menu_markup(is_admin=False),
        )
        bot.set_state(user_id, OnboardStates.completed, chat_id)


@bot.message_handler(state=OnboardStates.waiting_for_name, content_types=["text"])
def process_name(message):
    user_id = message.from_user.id
    name = (message.text or "").strip()
    if len(name) < 3 or len(name) > 100:
        bot.send_message(message.chat.id, "Введите ФИО полностью, например: Иванов Иван Иванович")
        return
    db.update_user(user_id, full_name=name)
    bot.send_message(message.chat.id, "💼 Укажите вашу <b>должность</b>:")
    bot.set_state(user_id, OnboardStates.waiting_for_position, message.chat.id)


@bot.message_handler(state=OnboardStates.waiting_for_position, content_types=["text"])
def process_position(message):
    user_id = message.from_user.id
    position = (message.text or "").strip()
    if len(position) < 2 or len(position) > 100:
        bot.send_message(message.chat.id, "Напишите должность коротко, например: Менеджер по продажам")
        return
    try:
        db.update_user(user_id, position=position)
    except Exception as e:
        print(f"Could not save position: {e}")
    bot.send_message(message.chat.id, "📅 Теперь укажите <b>дату рождения</b> в формате <code>ДД.ММ.ГГГГ</code>:")
    bot.set_state(user_id, OnboardStates.waiting_for_birthday, message.chat.id)


@bot.message_handler(state=OnboardStates.waiting_for_birthday, content_types=["text"])
def process_birthday(message):
    user_id = message.from_user.id
    try:
        dt = datetime.strptime((message.text or "").strip(), "%d.%m.%Y")
        if dt.year < 1940 or dt.year > datetime.now().year - 14:
            raise ValueError("year out of range")
    except ValueError:
        bot.send_message(message.chat.id, "Не получилось распознать дату. Пример: <code>25.08.1995</code>")
        return

    db.update_user(user_id, birthday=dt.strftime("%m-%d"))
    bot.send_message(
        message.chat.id,
        "✅ Принято!\n\nЗагрузите <b>фото или скан паспорта / трудового договора</b>:",
    )
    bot.set_state(user_id, OnboardStates.waiting_for_doc, message.chat.id)


@bot.message_handler(state=OnboardStates.waiting_for_doc, content_types=["document", "photo"])
def process_document(message):
    user_id = message.from_user.id
    try:
        if message.document:
            file_info = bot.get_file(message.document.file_id)
            file_name = message.document.file_name or "document"
        else:
            file_info = bot.get_file(message.photo[-1].file_id)
            file_name = f"photo_{user_id}.jpg"

        safe_name = re.sub(r"[^\w.\-]", "_", os.path.basename(file_name))
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        data = bot.download_file(file_info.file_path)
        save_path = os.path.join(UPLOAD_DIR, f"{user_id}_{safe_name}")
        with open(save_path, "wb") as f:
            f.write(data)
        db.update_user(user_id, doc_path=save_path)
    except Exception as e:
        print(f"Document save error: {e}")
        bot.send_message(message.chat.id, "Не удалось сохранить файл. Попробуйте отправить ещё раз.")
        return

    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("A) Корпоративный мессенджер", callback_data="test_q1_a"),
        InlineKeyboardButton("B) Личная почта", callback_data="test_q1_b"),
        InlineKeyboardButton("C) Социальные сети", callback_data="test_q1_c"),
    )
    bot.send_message(
        message.chat.id,
        "📄 Документ сохранён!\n\n<b>Вопрос 1:</b> Какой основной инструмент для коммуникаций?",
        reply_markup=markup,
    )
    bot.set_state(user_id, OnboardStates.taking_test_q1, message.chat.id)


@bot.message_handler(state=OnboardStates.waiting_for_doc, content_types=["text"])
def doc_wrong_type(message):
    bot.send_message(message.chat.id, "Пришлите, пожалуйста, фото или файл документа.")


# ======================= ТЕСТ =======================

def test_user_or_stop(call):
    """Не даём проходить тест повторно и уволенным."""
    user = db.get_user(call.from_user.id)
    if not user or user[7] in ("completed", "fired"):
        bot.answer_callback_query(call.id, "Тест уже завершён")
        return None
    return user


@bot.callback_query_handler(func=lambda call: call.data.startswith("test_q1_"))
def process_test_q1(call):
    if not test_user_or_stop(call):
        return
    user_id = call.from_user.id
    score = 1 if call.data == "test_q1_a" else 0
    db.update_user(user_id, test_score=score)

    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("A) У руководителя или в ERP", callback_data="test_q2_a"),
        InlineKeyboardButton("B) В поисковике Google", callback_data="test_q2_b"),
        InlineKeyboardButton("C) Спросить у коллеги", callback_data="test_q2_c"),
    )
    bot.answer_callback_query(call.id)
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="✅ Ответ принят!\n\n<b>Вопрос 2:</b> Где оформляется отпуск?",
        reply_markup=markup,
    )
    bot.set_state(user_id, OnboardStates.taking_test_q2, call.message.chat.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("test_q2_"))
def process_test_q2(call):
    user = test_user_or_stop(call)
    if not user:
        return
    user_id = call.from_user.id
    current = user[6] or 0
    score = current + 1 if call.data == "test_q2_a" else current
    db.update_user(user_id, test_score=score)

    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("A) Корпоративная почта и мессенджер", callback_data="test_q3_a"),
        InlineKeyboardButton("B) Личный Telegram", callback_data="test_q3_b"),
    )
    bot.answer_callback_query(call.id)
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="✅ Ответ принят!\n\n<b>Вопрос 3:</b> Какие каналы приоритетны?",
        reply_markup=markup,
    )
    bot.set_state(user_id, OnboardStates.taking_test_q3, call.message.chat.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("test_q3_"))
def process_test_q3(call):
    user = test_user_or_stop(call)
    if not user:
        return
    user_id = call.from_user.id
    current = user[6] or 0
    score = current + 1 if call.data == "test_q3_a" else current
    db.update_user(user_id, test_score=score, status="completed")

    bot.answer_callback_query(call.id, "Тест завершён!")
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"🎉 <b>Онбординг завершён!</b>\n\nВаш результат: <b>{score}/3 баллов</b>.",
    )
    bot.send_message(call.message.chat.id, "Главное меню:", reply_markup=get_main_menu_markup(is_admin=False))
    bot.set_state(user_id, OnboardStates.completed, call.message.chat.id)


# ======================= ПУЛЬС-ОПРОС =======================

@bot.callback_query_handler(func=lambda call: call.data.startswith("poll_"))
def process_poll(call):
    try:
        score = int(call.data.replace("poll_", ""))
    except ValueError:
        return
    if score < 1 or score > 5:
        return

    user_id = call.from_user.id
    user = db.get_user(user_id)
    if not user or user[7] == "fired":
        bot.answer_callback_query(call.id)
        return

    current_avg = user[10] if user[10] else 5.0
    new_avg = round((current_avg + score) / 2, 1)
    db.update_user(
        user_id,
        engagement_avg=new_avg,
        last_activity=datetime.now(TZ).strftime("%Y-%m-%d %H:%M"),
    )

    bot.answer_callback_query(call.id, "Спасибо за обратную связь! ❤️")
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"📊 <b>Опрос принят!</b> Ваша оценка: {score}/5.",
    )


# ======================= МЕНЮ СОТРУДНИКА =======================

@bot.message_handler(func=lambda m: m.text == BTN_KB, state=ACTIVE)
def kb_handler(message):
    if not employee_ok(message.from_user.id):
        return
    links = "\n".join(f'<a href="{esc(url)}">{esc(title)}</a>' for title, url in KB_LINKS)
    bot.send_message(message.chat.id, f"📚 <b>База знаний</b>\n\n{links}", disable_web_page_preview=True)


@bot.message_handler(func=lambda m: m.text == BTN_STATUS, state=ACTIVE)
def status_handler(message):
    if not employee_ok(message.from_user.id):
        return
    user = db.get_user(message.from_user.id)
    done = user[7] == "completed"
    eng = user[10]
    text = (
        "👤 <b>Ваш профиль</b>\n\n"
        f"• ФИО: {esc(user[2] or 'Не указано')}\n"
        f"• Должность: {esc(user[3] or 'Не указана')}\n"
        f"• Тест: {user[6] or 0} / 3 баллов\n"
        f"• Онбординг: {'пройден ✅' if done else 'в процессе ⏳'}\n"
        f"• Вовлечённость: {eng if eng else '—'}⭐"
    )
    bot.send_message(message.chat.id, text)


@bot.message_handler(func=lambda m: m.text == BTN_FAQ, state=ACTIVE)
def faq_handler(message):
    if not employee_ok(message.from_user.id):
        return
    items = "\n\n".join(f"🔹 <b>{esc(q)}</b>\n{esc(a)}" for q, a in FAQ)
    bot.send_message(message.chat.id, f"💡 <b>Справочный центр</b>\n\n{items}")


@bot.message_handler(func=lambda m: m.text == BTN_ORDER, state=ACTIVE)
def request_item(message):
    if not employee_ok(message.from_user.id):
        return
    bot.send_message(message.chat.id, "📦 Опишите, что нужно заказать (ноутбук, пропуск, справка):")
    bot.set_state(message.from_user.id, OnboardStates.waiting_for_request_text, message.chat.id)


def cancel_to_menu(message):
    bot.send_message(message.chat.id, "Отменено.", reply_markup=get_main_menu_markup(is_admin=False))
    bot.set_state(message.from_user.id, OnboardStates.completed, message.chat.id)


@bot.message_handler(state=OnboardStates.waiting_for_request_text, content_types=["text"])
def process_request(message):
    if message.text in EMPLOYEE_BUTTONS:
        return cancel_to_menu(message)

    user_id = message.from_user.id
    user = db.get_user(user_id)
    full_name = user[2] if user and user[2] else "Не указано"
    username = f"@{user[1]}" if user and user[1] else "нет username"

    db.create_request(user_id, "Имущество/Документ", message.text)

    for admin_id in ADMIN_IDS:
        try:
            bot.send_message(
                admin_id,
                f"📦 <b>Новая заявка!</b>\n\n• Сотрудник: {esc(full_name)} ({esc(username)})\n"
                f"• ID: <code>{user_id}</code>\n\n<b>Запрос:</b>\n{esc(message.text)}",
            )
        except Exception:
            pass

    bot.send_message(message.chat.id, "✅ Заявка передана администраторам!", reply_markup=get_main_menu_markup(is_admin=False))
    bot.set_state(user_id, OnboardStates.completed, message.chat.id)


@bot.message_handler(func=lambda m: m.text == BTN_HR, state=ACTIVE)
def contact_hr(message):
    if not employee_ok(message.from_user.id):
        return
    bot.send_message(message.chat.id, "✍️ Напишите ваше сообщение для HR-отдела:")
    bot.set_state(message.from_user.id, OnboardStates.waiting_for_admin_message, message.chat.id)


@bot.message_handler(state=OnboardStates.waiting_for_admin_message, content_types=["text"])
def process_hr_message(message):
    if message.text in EMPLOYEE_BUTTONS:
        return cancel_to_menu(message)

    user_id = message.from_user.id
    user = db.get_user(user_id)
    full_name = user[2] if user and user[2] else "Не указано"
    username = f"@{user[1]}" if user and user[1] else "нет username"

    for admin_id in ADMIN_IDS:
        try:
            bot.send_message(
                admin_id,
                f"🚨 <b>Сообщение от сотрудника!</b>\n\n• ФИО: {esc(full_name)}\n• Username: {esc(username)}\n"
                f"• ID: <code>{user_id}</code>\n\n<b>Текст:</b>\n{esc(message.text)}",
            )
        except Exception:
            pass

    bot.send_message(message.chat.id, "✅ Сообщение отправлено HR!", reply_markup=get_main_menu_markup(is_admin=False))
    bot.set_state(user_id, OnboardStates.completed, message.chat.id)


# ======================= МЕНЮ АДМИНА (сотрудники его не видят) =======================

@bot.message_handler(func=lambda m: m.text == BTN_PANEL, state=ACTIVE)
def admin_panel(message):
    # Сотрудникам не отвечаем вообще: для них этой функции как будто нет
    if not is_admin_id(message.from_user.id):
        return
    if not MINI_APP_URL.startswith("https://"):
        bot.send_message(message.chat.id, "Адрес панели не настроен. Добавьте переменную MINI_APP_URL в Amvera.")
        return
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("👑 Открыть панель", web_app=WebAppInfo(url=MINI_APP_URL)))
    bot.send_message(message.chat.id, "Панель управления персоналом:", reply_markup=markup)


@bot.message_handler(func=lambda m: m.text == BTN_RISK, state=ACTIVE)
def risk_analysis(message):
    if not is_admin_id(message.from_user.id):
        return

    blocks = []
    for u in db.get_all_users():
        u_id, name, role, score, status, eng = u[0], u[2], u[4], u[6], u[7], u[10]
        if status == "fired" or role == "admin" or u_id in ADMIN_IDS:
            continue

        score = score or 0
        eng = float(eng or 0)
        reasons = []
        if score < 2:
            reasons.append("низкий балл за тест")
        if 0 < eng < 3.0:
            reasons.append("низкая вовлечённость")
        if status != "completed":
            reasons.append("не завершил онбординг")

        if reasons:
            eng_text = f"{eng:.1f}⭐" if eng else "нет оценок"
            blocks.append(
                f"🚨 <b>{esc(name or 'Без имени')}</b> (ID: <code>{u_id}</code>)\n"
                f"Факторы: {esc(', '.join(reasons))}\nВовлечённость: {eng_text}"
            )

    if not blocks:
        bot.send_message(message.chat.id, "⚠️ <b>Анализ рисков</b>\n\n✅ Сотрудников в зоне риска не обнаружено.")
    else:
        send_long(message.chat.id, blocks, header="⚠️ <b>Анализ рисков выгорания</b>\n\n")


# ======================= ВСЁ ОСТАЛЬНОЕ =======================

@bot.message_handler(content_types=["text"], state=ACTIVE)
def fallback(message):
    if message.chat.type != "private":
        return
    if message.text and message.text.startswith("/"):
        return

    user_id = message.from_user.id
    if is_admin_id(user_id):
        bot.send_message(message.chat.id, "Выберите действие в меню 👇", reply_markup=get_main_menu_markup(is_admin=True))
        return

    user = db.get_user(user_id)
    if not user or not user[2]:
        bot.send_message(message.chat.id, "Чтобы начать, нажмите /start")
        return
    if user[7] == "fired":
        bot.send_message(message.chat.id, "Ваш аккаунт деактивирован. Обратитесь в HR-отдел.")
        return
    bot.send_message(message.chat.id, "Выберите действие в меню 👇", reply_markup=get_main_menu_markup(is_admin=False))


def start_polling():
    try:
        bot.infinity_polling(skip_pending=True)
    except Exception as e:
        print(f"Bot polling error: {e}")
