# HR Bot с Telegram Mini App

Полнофункциональный HR-бот с Telegram Mini App админки для управления сотрудниками.

## Структура проекта

```
.
├── db.py                 # Работа с SQLite базой
├── bot.py               # Логика Telegram бота
├── app.py               # FastAPI для Mini App
├── main.py              # Точка входа приложения
├── templates/
│   └── index.html       # Админка Mini App (Tailwind + JS)
├── requirements.txt     # Python зависимости
├── amvera.yml          # Конфигурация для Amvera
├── Dockerfile          # Для локального деплоя
└── .gitignore
```

## Локальный запуск

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 2. Переменные окружения

Создайте файл `.env`:

```env
BOT_TOKEN=8627644011:AAHjMALXr2eRBQbkeaO3VSwy7k-i4-Ks160
ADMIN_IDS=8405756128
MINI_APP_URL=http://localhost:8000
DB_PATH=/data/hr_bot.db
UPLOAD_DIR=/data/uploads
PORT=8000
```

### 3. Запуск

```bash
python main.py
```

Бот будет доступен на `http://localhost:8000`

## Деплой на Amvera

### 1. Подготовка

Убедитесь, что у вас есть:
- Git репозиторий
- Аккаунт на Amvera

### 2. Создание приложения

1. Перейдите на Amvera и создайте новое приложение
2. Подключите ваш Git репозиторий
3. В переменные окружения добавьте:
   - `BOT_TOKEN` - токен вашего Telegram бота
   - `ADMIN_IDS` - ID администраторов (через запятую)
   - `MINI_APP_URL` - публичный URL приложения (будет выдан Amvera)

### 3. Деплой

Amvera автоматически:
- Создаст persistent volume `/data` для базы и загрузок
- Выполнит `python -c "import db; db.init_db()"`
- Запустит `python main.py`

## Функционал

### Для сотрудников

- 📋 Онбординг с тестом
- 📚 База знаний и сайты
- 📋 Статус онбординга
- ❓ Часто задаваемые вопросы
- 📦 Заказ пропусков и техники
- 📞 Связь с HR
- 📊 Ежедневный пульс-опрос вовлеченности

### Для админа

- 👑 Mini App панель управления
  - Список всех сотрудников
  - Статус онбординга каждого
  - Оценка вовлеченности (красным подсвечиваются < 3⭐)
  - Кнопка увольнения сотрудника
- 📢 Массовая рассылка
- 📊 Отчет по рискам выгорания и увольнения
- 🔔 Уведомления о днях рождения

## API endpoints

- `GET /` - HTML админка
- `GET /api/users?init_data=...` - Список сотрудников (требует валидации)
- `POST /api/broadcast?init_data=...` - Отправить рассылку
- `POST /api/fire?init_data=...` - Уволить сотрудника

## Безопасность

- Все API endpoints защищены HMAC-SHA256 валидацией Telegram initData
- Только администраторы могут использовать Mini App
- Все данные хранятся в SQLite на постоянном хранилище

## Структура базы данных

### Таблица `users`

- `user_id` - ID Telegram пользователя
- `username` - юзернейм в Telegram
- `full_name` - полное имя сотрудника
- `position` - должность
- `role` - роль (newcomer, admin, dismissed)
- `doc_path` - путь к загруженному документу
- `test_score` - результат теста (0-3)
- `status` - статус (started, completed, fired)
- `birthday` - дата рождения (MM-DD)
- `last_activity` - время последней активности
- `engagement_avg` - средняя оценка вовлеченности (1-5)

### Таблица `requests`

- `request_id` - ID заявки
- `user_id` - ID сотрудника
- `request_type` - тип заявки
- `request_text` - текст заявки
- `status` - статус (pending, completed)

## Разработка

### Добавление нового функционала

Структура позволяет легко расширять:

- Добавляйте обработчики в `bot.py`
- Добавляйте API endpoints в `app.py`
- Обновляйте UI в `templates/index.html`
- Используйте функции из `db.py` для работы с БД

### Логирование

Используйте встроенные `print()` для логирования - все выводится в консоль Amvera.
