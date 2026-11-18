# ======================================
# handlers/start.py — Вітання та головне меню
# ======================================

import logging
from html import escape

from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)
from aiogram.fsm.context import FSMContext

import database as db

logger = logging.getLogger(__name__)

# Роутер для стартових команд
router = Router(name="start")


# Легенда: короткий перелік усього, що вміє бот (показується в /start, /help
# і у відповідь на невідому команду)
LEGEND_TEXT = (
    "🗺 <b>Що я вмію:</b>\n\n"
    "💬 <b>Просто напиши мені</b> — відповім як ШІ-помічник: поясню тему, "
    "розберу задачу, допоможу спланувати ДЗ\n"
    "📚 <b>Мої завдання</b> — список активних ДЗ\n"
    "➕ <b>Додати завдання</b> — додати ДЗ текстом\n"
    "🎤 <b>Голосове завдання</b> — або просто надішли голосове\n"
    "🧠 <b>Пройти тест</b> — ШІ-тест за твоїм ДЗ\n"
    "📊 <b>Мій прогрес</b> — статистика тестів\n\n"
    "<b>Команди:</b>\n"
    "/start — перезапуск і головне меню\n"
    "/menu — показати меню\n"
    "/new — почати розмову з помічником заново\n"
    "/help — повна довідка"
)


def get_main_menu() -> ReplyKeyboardMarkup:
    """
    Повертає клавіатуру головного меню бота.

    Returns:
        ReplyKeyboardMarkup із кнопками головного меню.
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📚 Мої завдання"),
                KeyboardButton(text="➕ Додати завдання"),
            ],
            [
                KeyboardButton(text="🎤 Голосове завдання"),
                KeyboardButton(text="🧠 Пройти тест"),
            ],
            [
                KeyboardButton(text="📊 Мій прогрес"),
                KeyboardButton(text="❓ Допомога"),
            ],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
        # Підказка в полі вводу
        input_field_placeholder="Напиши питання або обери дію 👇",
    )


@router.message(CommandStart())
async def handle_start(message: Message, state: FSMContext) -> None:
    """
    Обробник команди /start.
    Реєструє користувача в базі даних та показує головне меню.
    """
    # Скидаємо будь-який попередній стан
    await state.clear()

    user = message.from_user

    try:
        # Реєструємо або оновлюємо дані користувача
        await db.register_user(
            telegram_id=user.id,
            username=user.username,
            full_name=user.full_name,
        )
        logger.info(f"Користувач {user.id} ({user.full_name}) запустив бота.")
    except Exception as e:
        logger.error(f"Помилка реєстрації {user.id}: {e}")

    welcome_text = (
        f"👋 Привіт, <b>{escape(user.first_name)}</b>!\n\n"
        "Я — твій розумний помічник з навчання 🎓\n"
        "⏰ Щодня о 18:00 нагадую про дедлайни.\n\n"
        f"{LEGEND_TEXT}\n\n"
        "Обери дію у меню нижче або просто напиши питання 👇"
    )

    await message.answer(
        welcome_text,
        reply_markup=get_main_menu(),
        parse_mode="HTML",
    )


@router.message(Command("menu"))
@router.message(lambda m: m.text == "🏠 Головне меню")
async def handle_menu(message: Message, state: FSMContext) -> None:
    """
    Повертає до головного меню та скидає поточний стан.
    """
    await state.clear()
    await message.answer(
        "🏠 Головне меню:",
        reply_markup=get_main_menu(),
    )


@router.message(Command("help"))
@router.message(lambda m: m.text == "❓ Допомога")
async def handle_help(message: Message) -> None:
    """
    Надсилає довідку з описом усіх функцій бота.
    """
    help_text = (
        "📖 <b>Довідка по боту</b>\n\n"
        "<b>Команди:</b>\n"
        "/start — перезапустити бота\n"
        "/menu — повернутись до меню\n"
        "/new — почати розмову з помічником заново\n"
        "/help — ця довідка\n\n"
        "💬 <b>Чат з помічником</b> — просто напиши будь-яке питання "
        "(наприклад: «поясни теорему Піфагора» або «допоможи спланувати ДЗ на тиждень»). "
        "Я пам'ятаю контекст розмови і бачу твої активні завдання.\n\n"
        "<b>Кнопки меню:</b>\n\n"
        "📚 <b>Мої завдання</b> — переглянути активні ДЗ\n\n"
        "➕ <b>Додати завдання</b> — додати ДЗ текстом покроково\n\n"
        "🎤 <b>Голосове завдання</b> — надиктуй завдання голосом, "
        "і я автоматично розпізнаю предмет та дедлайн\n\n"
        "🧠 <b>Пройти тест</b> — ШІ генерує тест по твоєму ДЗ "
        "і перевіряє знання\n\n"
        "📊 <b>Мій прогрес</b> — статистика тестів\n\n"
        "⏰ <b>Нагадування</b> — щодня о 18:00 я нагадую "
        "про незавершені завдання\n\n"
        "💡 <i>Порада: щоб додати завдання голосом, просто "
        "надішли голосове повідомлення у будь-який момент!</i>"
    )
    await message.answer(help_text, parse_mode="HTML", reply_markup=get_main_menu())
