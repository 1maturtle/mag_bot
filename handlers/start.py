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
        "Я — твій розумний помічник з навчання 🎓\n\n"
        "Ось що я вмію:\n"
        "📚 <b>Зберігати</b> домашні завдання\n"
        "🎤 <b>Розпізнавати</b> завдання з голосу\n"
        "⏰ <b>Нагадувати</b> про дедлайни щодня о 18:00\n"
        "🧠 <b>Генерувати</b> тести для перевірки знань\n"
        "💪 <b>Мотивувати</b> тебе на навчання!\n\n"
        "Обери дію у меню нижче 👇"
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
        "/help — ця довідка\n\n"
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
    await message.answer(help_text, parse_mode="HTML")
