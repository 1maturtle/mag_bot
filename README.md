# 🎓 Telegram-бот для допомоги з домашніми завданнями

Розумний Telegram-бот для учнів на Python 3.12, який допомагає організовувати навчальний процес:
зберігає домашні завдання, розпізнає їх з голосу, нагадує про дедлайни, генерує тести
та відповідає на питання як ШІ-помічник.

Працює на безкоштовних тарифах: Telegram Bot API, Supabase Free та Gemini API Free Tier.

## ✨ Можливості

| Функція | Опис |
|--------|------|
| 💬 **ШІ-помічник** | Просто напиши питання — бот відповідає як навчальний помічник: пояснює теми, розбирає задачі, допомагає спланувати ДЗ. Пам'ятає контекст розмови та бачить активні завдання учня |
| 📚 **Зберігання ДЗ** | Покрокове додавання завдань текстом, позначення виконаним |
| 🎤 **Голосовий ввід** | Надиктовуй завдання голосом — Gemini розпізнає предмет, опис і дедлайн |
| ⏰ **Нагадування** | Щодня о 18:00 — зведення незавершених завдань |
| 🧠 **ШІ-тести** | Gemini генерує тест із 5 питань за обраним ДЗ і дає фідбек після кожної відповіді |
| 📊 **Прогрес** | Статистика результатів тестів |
| 📅 **Перевірка дедлайнів** | Дедлайн лише актуальний: не в минулому і не далі ніж на рік; розуміє «завтра», «25.12», «в п'ятницю» |

## 🤖 Команди бота

| Команда | Дія |
|---------|-----|
| `/start` | Перезапуск і головне меню |
| `/menu` | Показати меню |
| `/new` | Почати розмову з помічником заново |
| `/help` | Довідка по всіх можливостях |

## 🛠️ Стек технологій

- **[Aiogram 3](https://docs.aiogram.dev/)** — асинхронний фреймворк для Telegram Bot API (FSM)
- **[Supabase](https://supabase.com/)** — хмарна база даних PostgreSQL
- **[Google Gemini API](https://aistudio.google.com/)** (SDK `google-genai`) — чат, тести, фідбек, розпізнавання голосу та дат
- **[APScheduler](https://apscheduler.readthedocs.io/)** — щоденні нагадування

## 📁 Структура проєкту

```
mag_bot/
├── main.py                  # Точка входу: бот, роутери, меню команд, планувальник
├── config.py                # Конфігурація зі змінних середовища (.env)
├── database.py              # Робота із Supabase
├── ai_service.py            # Інтеграція з Gemini: чат, тести, голос, дати
├── deadlines.py             # Розбір і перевірка дедлайнів
├── states.py                # FSM-стани (Aiogram)
├── scheduler.py             # Щоденні нагадування
├── handlers/
│   ├── start.py             # /start, /help, /menu, головне меню, легенда
│   ├── tasks.py             # Завдання, тести, прогрес
│   ├── voice.py             # Голосові повідомлення
│   └── chat.py              # Вільний чат з ШІ-помічником, /new
├── supabase_schema.sql      # SQL-схема бази даних
├── requirements.txt
├── .env_example             # Шаблон змінних середовища
└── LICENSE
```

## 🚀 Встановлення та запуск (Windows)

### 1. Клонування

```powershell
git clone https://github.com/1maturtle/mag_bot.git
cd mag_bot
```

### 2. Встановлення залежностей

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Змінні середовища

```powershell
copy .env_example .env
```

Відкрий `.env` і заповни своїми значеннями (див. [Де отримати ключі](#-де-отримати-ключі)):

```env
BOT_TOKEN=токен_від_BotFather
SUPABASE_URL=https://твій-проєкт.supabase.co
SUPABASE_KEY=ключ_supabase
GEMINI_API_KEY=ключ_gemini
```

> ⚠️ Файл `.env` містить секрети й не потрапляє в Git (див. `.gitignore`). Ніколи не публікуй його.

### 4. База даних у Supabase

1. Відкрий [Supabase Dashboard](https://supabase.com/dashboard) і створи проєкт
2. **SQL Editor** → **New query**
3. Встав вміст [`supabase_schema.sql`](supabase_schema.sql) і натисни **Run**

### 5. Запуск

```powershell
python main.py
```

Бот працює, поки відкрите вікно терміналу. Зупинка — `Ctrl+C`.

## 🔑 Де отримати ключі

| Ключ | Де отримати |
|------|-------------|
| `BOT_TOKEN` | [@BotFather](https://t.me/BotFather) у Telegram → `/newbot` |
| `SUPABASE_URL` | Supabase Dashboard → Project Settings → Data API → Project URL |
| `SUPABASE_KEY` | Project Settings → API Keys → **Secret key** (`sb_secret_...`). Publishable key (`sb_publishable_...`) підійде лише якщо в таблицях налаштовано RLS-політики для ролі `anon` |
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/apikey) → Create API key. Безкоштовно, якщо до проєкту не підключено оплату |

## 🗄️ Схема бази даних

```
users              tasks                       quiz_results
──────────────     ─────────────────────       ──────────────────
id (PK) ◄───────── user_id (FK)                id (PK)
  = Telegram ID    id (PK)            users ◄─ user_id (FK)
username           subject                     topic
created_at         description                 score            (к-сть правильних)
                   deadline  ("ДД.ММ.РРРР ГГ:ХХ")  total_questions
                   status    (active/completed)    created_at
                   result_description
                   created_at
```

## 🎤 Як працює голосовий ввід

1. Користувач надсилає голосове повідомлення (або натискає **🎤 Голосове завдання**)
2. Бот завантажує `.ogg`-файл через Telegram Bot API
3. Аудіо передається в Gemini напряму в запиті
4. Gemini транскрибує мовлення та витягує предмет, опис і дедлайн
5. Дедлайн перевіряється на актуальність; користувач підтверджує розпізнані дані
6. Завдання зберігається в Supabase

## ⚙️ Додаткові налаштування

У `.env` можна додати:

```env
GEMINI_MODEL=gemini-3.5-flash-lite   # Модель Gemini
TIMEZONE=Europe/Kiev                 # Часовий пояс для нагадувань
REMINDER_HOUR=18                     # Година нагадування (0-23)
REMINDER_MINUTE=0                    # Хвилини нагадування
```

## 📝 Ліцензія

[MIT](LICENSE)
