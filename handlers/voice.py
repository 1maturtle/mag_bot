# ======================================
# handlers/voice.py — Обробка голосових повідомлень
# ======================================
# Алгоритм:
#   1. Отримати голосове повідомлення від Telegram
#   2. Завантажити аудіофайл (.ogg) через Bot API
#   3. Передати байти в Gemini → транскрипція + витягування даних
#   4. Показати розпізнані дані для підтвердження
#   5. Після підтвердження — зберегти в базу даних
# ======================================

import logging
from datetime import datetime, timedelta
from html import escape

from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

import database as db
import ai_service as ai
from deadlines import parse_deadline_text, validate_deadline
from states import VoiceTaskStates
from handlers.start import get_main_menu

logger = logging.getLogger(__name__)

# Роутер для голосових повідомлень
router = Router(name="voice")


def get_confirm_keyboard() -> InlineKeyboardMarkup:
    """
    Inline-клавіатура підтвердження розпізнаного завдання.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Зберегти", callback_data="voice_confirm:yes"),
                InlineKeyboardButton(text="❌ Скасувати", callback_data="voice_confirm:no"),
            ]
        ]
    )


# ──────────────────────────────────────────────────────────────
# КНОПКА "ГОЛОСОВЕ ЗАВДАННЯ"
# ──────────────────────────────────────────────────────────────

@router.message(F.text == "🎤 Голосове завдання")
async def handle_voice_menu(message: Message, state: FSMContext) -> None:
    """
    Запускає режим очікування голосового повідомлення.
    Переводить бота у стан VoiceTaskStates.waiting_for_voice.
    """
    await state.set_state(VoiceTaskStates.waiting_for_voice)
    await message.answer(
        "🎤 <b>Голосове додавання завдання</b>\n\n"
        "Надішли голосове повідомлення з описом домашнього завдання.\n\n"
        "Приклад: <i>«Математика, параграф 12, задачі 3 і 5, здати завтра»</i>\n\n"
        "💡 Чим детальніше ти скажеш — тим точніше я розпізнаю!\n\n"
        "Натисни <b>❌ Скасувати</b> щоб повернутися до меню.",
        parse_mode="HTML",
    )


# ──────────────────────────────────────────────────────────────
# ОБРОБКА ГОЛОСОВОГО ПОВІДОМЛЕННЯ (ПРЯМЕ НАДСИЛАННЯ)
# ──────────────────────────────────────────────────────────────

@router.message(F.voice)
async def handle_voice_message(message: Message, state: FSMContext, bot: Bot) -> None:
    """
    Основний обробник голосових повідомлень.
    Приймає .ogg файл, відправляє в Gemini для транскрипції,
    показує розпізнані дані для підтвердження.

    Спрацьовує як при натисканні кнопки "Голосове завдання",
    так і при прямому надсиланні голосового повідомлення.
    """
    await message.answer(
        "⏳ Розпізнаю голосове повідомлення...\n"
        "<i>Це може зайняти кілька секунд.</i>",
        parse_mode="HTML",
    )

    # Завантажуємо файл через Telegram Bot API
    try:
        voice = message.voice
        file_info = await bot.get_file(voice.file_id)
        file_bytes = await bot.download_file(file_info.file_path)
        audio_data = file_bytes.read()
        logger.info(
            f"Голосове повідомлення отримано від {message.from_user.id}, "
            f"розмір: {len(audio_data)} байт"
        )
    except Exception as e:
        logger.error(f"Помилка завантаження голосового файлу: {e}")
        await message.answer(
            "❌ Не вдалось завантажити аудіофайл. Спробуй ще раз.",
            reply_markup=get_main_menu(),
        )
        await state.clear()
        return

    # Передаємо аудіо в Gemini для транскрипції та витягування даних
    try:
        parsed = await ai.transcribe_and_extract_task(
            audio_bytes=audio_data,
            mime_type="audio/ogg",
        )
    except Exception as e:
        logger.error(f"Помилка транскрипції голосового повідомлення: {e}")
        parsed = None

    if not parsed or not parsed.get("description"):
        await message.answer(
            "😔 Не вдалось розпізнати завдання з голосу.\n\n"
            "Переконайся, що:\n"
            "• Мікрофон чіткий\n"
            "• Ти чітко назвав предмет та опис завдання\n\n"
            "Спробуй ще раз або додай завдання <b>текстом</b>.",
            parse_mode="HTML",
            reply_markup=get_main_menu(),
        )
        await state.clear()
        return

    # Розпізнаємо дедлайн: спершу стандартні формати, потім Gemini
    deadline_text = (parsed.get("deadline_text") or "не вказано").strip()
    deadline_dt = None
    auto_note = "автоматично"

    if deadline_text.lower() != "не вказано":
        deadline_dt = parse_deadline_text(deadline_text)
        if deadline_dt is None:
            iso_str = await ai.parse_deadline_to_datetime(deadline_text)
            if iso_str:
                try:
                    deadline_dt = datetime.fromisoformat(iso_str)
                except Exception:
                    deadline_dt = None
        # Неактуальну дату (минулу або більш ніж на рік наперед) не приймаємо
        if deadline_dt is not None and validate_deadline(deadline_dt):
            auto_note = f"«{deadline_text}» — неактуальна дата, встановлено автоматично"
            deadline_dt = None

    if deadline_dt is not None:
        deadline_display = deadline_dt.strftime("%d.%m.%Y о %H:%M")
    else:
        # Якщо дедлайн не розпізнано або він неактуальний — ставимо за 3 дні о 23:59
        deadline_dt = (datetime.now() + timedelta(days=3)).replace(
            hour=23, minute=59, second=0, microsecond=0
        )
        deadline_display = deadline_dt.strftime("%d.%m.%Y о %H:%M") + f" ({auto_note})"

    # Зберігаємо дані для підтвердження у стані FSM
    await state.update_data(
        subject=parsed.get("subject", "Загальне"),
        description=parsed["description"],
        deadline_dt=deadline_dt.isoformat(),
        deadline_display=deadline_display,
        raw_transcript=parsed.get("raw_transcript", ""),
    )
    await state.set_state(VoiceTaskStates.confirming_parsed_task)

    # Показуємо розпізнані дані для підтвердження
    confirm_text = (
        "🎤 <b>Я розпізнав таке завдання:</b>\n\n"
        f"📖 <b>Предмет:</b> {escape(parsed.get('subject', 'Загальне'))}\n"
        f"📝 <b>Опис:</b> {escape(parsed['description'])}\n"
        f"⏰ <b>Дедлайн:</b> {escape(deadline_display)}\n\n"
        f"🔤 <i>Транскрипт: «{escape(parsed.get('raw_transcript', ''))}»</i>\n\n"
        "Все правильно? Зберегти це завдання?"
    )

    await message.answer(
        confirm_text,
        parse_mode="HTML",
        reply_markup=get_confirm_keyboard(),
    )


# ──────────────────────────────────────────────────────────────
# ПІДТВЕРДЖЕННЯ АБО СКАСУВАННЯ
# ──────────────────────────────────────────────────────────────

@router.callback_query(VoiceTaskStates.confirming_parsed_task, F.data.startswith("voice_confirm:"))
async def handle_voice_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Обробляє підтвердження або скасування розпізнаного завдання.

    При підтвердженні зберігає завдання в базу даних.
    При скасуванні повертається до головного меню.
    """
    action = callback.data.split(":")[1]

    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)

    if action == "no":
        await state.clear()
        await callback.message.answer(
            "❌ Завдання скасовано. Повертаюсь до меню.",
            reply_markup=get_main_menu(),
        )
        return

    # Підтверджено — зберігаємо в БД
    data = await state.get_data()

    try:
        deadline_dt = datetime.fromisoformat(data["deadline_dt"])
        task = await db.create_task(
            telegram_id=callback.from_user.id,
            subject=data["subject"],
            description=data["description"],
            deadline=deadline_dt,
        )
        await state.clear()

        await callback.message.answer(
            "✅ <b>Голосове завдання збережено!</b>\n\n"
            f"📖 Предмет: <b>{escape(data['subject'])}</b>\n"
            f"📝 Опис: {escape(data['description'])}\n"
            f"⏰ Дедлайн: <b>{escape(data['deadline_display'])}</b>",
            parse_mode="HTML",
            reply_markup=get_main_menu(),
        )
        logger.info(
            f"Голосове завдання збережено для {callback.from_user.id}: "
            f"{data['subject']}"
        )

    except Exception as e:
        logger.error(f"Помилка збереження голосового завдання: {e}")
        await state.clear()
        await callback.message.answer(
            "❌ Помилка збереження завдання. Спробуй ще раз.",
            reply_markup=get_main_menu(),
        )
