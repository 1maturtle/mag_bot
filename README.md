# 🎓 Telegram-бот для допомоги з домашніми завданнями

Розумний Telegram-бот для учнів на Python 3.12, який допомагає організовувати навчальний процес.

## ✨ Можливості

| Функція | Опис |
|--------|------|
| 📚 **Зберігання ДЗ** | Додавання завдань текстом покроково |
| 🎤 **Голосовий ввід** | Надиктовуй завдання голосом — Gemini розпізнає та структурує |
| ⏰ **Нагадування** | Щодня о 18:00 отримуєш зведення незавершених завдань |
| 🧠 **AI тести** | Gemini генерує тест по твоєму ДЗ та перевіряє знання |
| 💪 **Мотивація** | Персоналізований фідбек та підтримка після кожної відповіді |
| 📊 **Прогрес** | Статистика результатів тестів |

## 🛠️ Стек технологій

- **[Aiogram 3](https://docs.aiogram.dev/)** — асинхронний фреймворк для Telegram Bot API (FSM)
- **[Supabase](https://supabase.com/)** — PostgreSQL хмарна база даних
- **[Google Gemini API](https://aistudio.google.com/)** — AI для тестів, фідбеку та транскрипції голосу
- **[APScheduler](https://apscheduler.readthedocs.io/)** — фонові нагадування

## 📁 Структура проекту

```
maga/
├── main.py                  # Головна точка входу
├── config.py                # Конфігурація та змінні середовища
├── database.py              # Взаємодія із Supabase
├── ai_service.py            # Інтеграція з Gemini API
├── states.py                # FSM стани (Aiogram)
├── scheduler.py             # Планувальник нагадувань
├── handlers/
│   ├── __init__.py
│   ├── start.py             # /start, /help, головне меню
│   ├── tasks.py             # Управління завданнями та тести
│   └── voice.py             # Обробка голосових повідомлень
├── supabase_schema.sql      # SQL схема для Supabase
├── requirements.txt
├── .env_example             # Шаблон змінних середовища
└── README.md
```

## 🚀 Встановлення та запуск

### 1. Клонування / підготовка проекту

```bash
git clone https://github.com/<your-username>/mag_bot.git
cd mag_bot
```

### 2. Встановлення залежностей

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Налаштування змінних середовища

```bash
# Скопіюй шаблон
copy .env_example .env
```

Відкрий `.env` та заповни реальними значеннями:

```env
BOT_TOKEN=твій_токен_від_BotFather
SUPABASE_URL=https://твій-проект.supabase.co
SUPABASE_KEY=твій_anon_ключ_supabase
GEMINI_API_KEY=твій_ключ_gemini
```

### 4. Налаштування бази даних у Supabase

1. Відкрий [Supabase Dashboard](https://supabase.com/dashboard)
2. Перейди до **SQL Editor** → **New query**
3. Вставте вміст файлу [`supabase_schema.sql`](supabase_schema.sql)
4. Натисни **Run**

> ⚠️ **Важливо:** Використовуй **Service Role Key** (не anon key) для `SUPABASE_KEY`, оскільки ввімкнено RLS. Знайдеш у Settings → API → `service_role secret`.

### 5. Запуск бота

```bash
python main.py
```

## 🔑 Де отримати ключі

| Ключ | Де отримати |
|------|-------------|
| `BOT_TOKEN` | [@BotFather](https://t.me/BotFather) у Telegram → `/newbot` |
| `SUPABASE_URL` | Supabase Dashboard → Settings → API → Project URL |
| `SUPABASE_KEY` | Supabase Dashboard → Settings → API Keys → **Secret key** (`sb_secret_...`) або legacy `service_role`. Publishable (`sb_publishable_...`) не підійде |
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/apikey) — ключ починається з `AIza` |

## 🗄️ Схема бази даних

```
users           tasks              quiz_results
─────────       ─────────────      ─────────────
id (PK)         id (PK, UUID)      id (PK, UUID)
telegram_id ◄── telegram_id (FK)   telegram_id (FK) ──► users
username        subject            task_id (FK) ──► tasks
full_name       description        score
created_at      deadline           feedback
                status             created_at
                created_at
```

## 🎤 Як працює голосовий ввід

1. Користувач натискає **🎤 Голосове завдання** або надсилає голосове повідомлення
2. Бот завантажує `.ogg` файл через Telegram Bot API
3. Аудіо передається в **Gemini** (за замовчуванням `gemini-2.5-flash`, змінюється через `GEMINI_MODEL`) напряму в запиті
4. Gemini транскрибує мовлення та витягує:
   - 📖 Предмет (Математика, Фізика, тощо)
   - 📝 Опис завдання
   - ⏰ Дедлайн (у природньому тексті → ISO 8601)
5. Користувач підтверджує розпізнані дані
6. Завдання зберігається в Supabase

## ⚙️ Додаткові налаштування

В `.env` можна додати:
```env
TIMEZONE=Europe/Kiev       # Часовий пояс для нагадувань
REMINDER_HOUR=18           # Година нагадування (0-23)
REMINDER_MINUTE=0          # Хвилини нагадування
```

## 📝 Ліцензія

MIT License
