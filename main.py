# ======================================
# main.py — Головна точка входу Telegram-бота
# ======================================
# Telegram-бот для допомоги з домашніми завданнями
# Запуск: python main.py
# ======================================

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from config import BOT_TOKEN
from scheduler import setup_scheduler

# Підключаємо роутери (обробники)
from handlers import start, tasks, voice, chat

# ──────────────────────────────────────────────────────────────
# НАЛАШТУВАННЯ ЛОГУВАННЯ
# ──────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        # Виводимо в консоль
        logging.StreamHandler(sys.stdout),
        # Зберігаємо у файл
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)

# Зменшуємо шум від сторонніх бібліотек
logging.getLogger("aiogram").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.INFO)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# ІНІЦІАЛІЗАЦІЯ БОТА ТА ДИСПЕТЧЕРА
# ──────────────────────────────────────────────────────────────

async def main() -> None:
    """
    Головна асинхронна функція запуску бота.

    Порядок запуску:
    1. Ініціалізація Bot та Dispatcher
    2. Підключення роутерів обробників
    3. Запуск планувальника APScheduler
    4. Запуск polling (прослуховування оновлень)
    """
    logger.info("🚀 Запускаємо Telegram-бота для домашніх завдань...")

    # Ініціалізуємо бота з підтримкою HTML форматування за замовчуванням
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # Ініціалізуємо диспетчер із пам'яттю для FSM станів
    # Для production рекомендується використати RedisStorage
    dp = Dispatcher(storage=MemoryStorage())

    # ── Реєструємо роутери (порядок важливий!) ──
    # Спершу голосовий роутер (він перехоплює F.voice для будь-якого стану)
    dp.include_router(voice.router)
    # Потім роутер завдань (FSM стани, кнопки меню)
    dp.include_router(tasks.router)
    # Потім стартовий роутер (команди /start, /help, /menu)
    dp.include_router(start.router)
    # Останнім — вільний чат з ШІ: отримує лише текст, який не обробили інші роутери
    dp.include_router(chat.router)

    logger.info("✅ Роутери підключено: voice → tasks → start → chat")

    # ── Легенда команд у меню Telegram (кнопка «Меню» біля поля вводу) ──
    await bot.set_my_commands([
        BotCommand(command="start", description="Перезапуск і головне меню"),
        BotCommand(command="menu", description="Показати меню"),
        BotCommand(command="new", description="Почати розмову з помічником заново"),
        BotCommand(command="help", description="Довідка: що вміє бот"),
    ])

    # ── Налаштовуємо та запускаємо планувальник ──
    scheduler = setup_scheduler(bot)
    scheduler.start()
    logger.info("✅ Планувальник APScheduler запущено")

    # ── Видаляємо вебхуки (якщо були) та запускаємо polling ──
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("🤖 Бот запущений! Слухаємо оновлення...")

    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
        )
    finally:
        # Зупиняємо планувальник при завершенні роботи
        scheduler.shutdown(wait=False)
        await bot.session.close()
        logger.info("🛑 Бот зупинено.")


# ──────────────────────────────────────────────────────────────
# ТОЧКА ВХОДУ
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Бот зупинено вручну (Ctrl+C)")
    except Exception as e:
        logger.critical(f"💥 Критична помилка запуску: {e}", exc_info=True)
        sys.exit(1)
