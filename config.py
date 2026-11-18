# ======================================
# config.py — Завантаження конфігурації з .env
# ======================================

import os
from dotenv import load_dotenv

# Завантажуємо змінні середовища з файлу .env
load_dotenv()


def _require(name: str) -> str:
    """Повертає значення змінної середовища або кидає помилку, якщо не знайдено."""
    value = os.getenv(name)
    if not value:
        raise EnvironmentError(
            f"❌ Обов'язкова змінна середовища '{name}' не знайдена. "
            f"Перевір файл .env"
        )
    return value


# Токен Telegram-бота
BOT_TOKEN: str = _require("BOT_TOKEN")

# Дані для підключення до Supabase
SUPABASE_URL: str = _require("SUPABASE_URL")
SUPABASE_KEY: str = _require("SUPABASE_KEY")

# Ключ API для Google Gemini (починається з "AIza", береться на aistudio.google.com/apikey)
GEMINI_API_KEY: str = _require("GEMINI_API_KEY")

# Модель Gemini. Lite-модель — найшвидша й найекономніша для безкоштовного тарифу.
# (gemini-1.5 та gemini-2.5-flash-lite Google для нових користувачів уже закрив)
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

# Часовий пояс для планувальника нагадувань
TIMEZONE: str = os.getenv("TIMEZONE", "Europe/Kiev")

# Час щоденного нагадування (за замовчуванням 18:00)
REMINDER_HOUR: int = int(os.getenv("REMINDER_HOUR", "18"))
REMINDER_MINUTE: int = int(os.getenv("REMINDER_MINUTE", "0"))
