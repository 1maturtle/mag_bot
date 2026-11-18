# ======================================
# handlers/chat.py — Вільний чат з ШІ-помічником
# ======================================
# Будь-який текст, який не є кнопкою меню чи командою, потрапляє сюди:
#   1. Поки Gemini генерує відповідь, у чаті видно статус «друкує…»
#   2. Готова відповідь надходить одним повідомленням
#   3. Помічник пам'ятає останні репліки розмови (/new — почати заново)
#   4. Невідомі /команди отримують легенду з переліком можливостей
# ======================================

import logging
from collections import defaultdict
from datetime import datetime

from aiogram import Router, F, Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.utils.chat_action import ChatActionSender

import ai_service as ai
import database as db
from handlers.start import get_main_menu, LEGEND_TEXT
from states import QuizStates, VoiceTaskStates

logger = logging.getLogger(__name__)

router = Router(name="chat")

# Історія розмов у пам'яті: {telegram_id: [{"role": "user"|"model", "text": ...}]}
# (після перезапуску бота розмова починається з чистого аркуша)
_histories: dict[int, list[dict]] = defaultdict(list)
_MAX_HISTORY = 20            # скільки останніх реплік пам'ятати
_TG_LIMIT = 4000             # ліміт Telegram — 4096 символів, лишаємо запас


def _remember(user_id: int, role: str, text: str) -> None:
    history = _histories[user_id]
    history.append({"role": role, "text": text})
    del history[:-_MAX_HISTORY]


async def _tasks_context(user_id: int) -> str:
    """Короткий перелік активних ДЗ учня для контексту помічника."""
    tasks = await db.get_active_tasks(user_id)
    lines = []
    for t in tasks[:10]:
        deadline = t.get("deadline") or ""
        try:
            deadline = datetime.fromisoformat(deadline).strftime("%d.%m.%Y %H:%M")
        except ValueError:
            pass
        lines.append(f"- {t.get('subject')}: {t.get('description')} (до {deadline})")
    return "\n".join(lines)


def _split(text: str, size: int = _TG_LIMIT) -> list[str]:
    """Ділить довгий текст на частини, намагаючись різати по абзацах."""
    parts = []
    while len(text) > size:
        cut = text.rfind("\n", 0, size)
        if cut < size // 2:
            cut = size
        parts.append(text[:cut])
        text = text[cut:].lstrip("\n")
    parts.append(text)
    return parts


# ──────────────────────────────────────────────────────────────
# КОМАНДИ
# ──────────────────────────────────────────────────────────────

@router.message(Command("new"))
async def handle_new_chat(message: Message, state: FSMContext) -> None:
    """Очищає історію розмови з помічником."""
    await state.clear()
    _histories.pop(message.from_user.id, None)
    await message.answer(
        "🧹 Розмову почато з чистого аркуша. Про що поговоримо?",
        reply_markup=get_main_menu(),
    )


@router.message(F.text.startswith("/"))
async def handle_unknown_command(message: Message) -> None:
    """Невідома команда — показуємо легенду."""
    await message.answer(
        "🤔 Не знаю такої команди.\n\n" + LEGEND_TEXT,
        parse_mode="HTML",
        reply_markup=get_main_menu(),
    )


# ──────────────────────────────────────────────────────────────
# ВІЛЬНИЙ ЧАТ
# ──────────────────────────────────────────────────────────────

@router.message(
    StateFilter(None, VoiceTaskStates.waiting_for_voice, QuizStates.answering_question),
    F.text,
)
async def handle_chat(message: Message, state: FSMContext, bot: Bot) -> None:
    """
    Відповідає на довільний текст як ШІ-помічник.
    Поки Gemini генерує відповідь, у чаті видно статус «друкує…» (як у людини),
    після чого відповідь надходить одним повідомленням.
    """
    user_id = message.from_user.id
    user_text = message.text.strip()

    # Якщо учень натиснув «Голосове завдання», а потім написав текст — виходимо з режиму
    if await state.get_state() == VoiceTaskStates.waiting_for_voice.state:
        await state.clear()

    full_text = ""
    try:
        # ChatActionSender повторює статус «друкує…» кожні кілька секунд,
        # доки триває генерація (сам статус у Telegram гасне через ~5 с)
        async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id):
            context = await _tasks_context(user_id)
            async for piece in ai.chat_stream(_histories[user_id], user_text, context):
                full_text += piece
    except Exception as e:
        logger.error(f"Помилка чату з помічником для {user_id}: {e}")
        if not full_text:
            await message.answer(
                "😔 Зараз не вдалося отримати відповідь від ШІ. Спробуй ще раз трохи згодом."
            )
            return

    full_text = full_text.strip()
    if not full_text:
        await message.answer("🤔 Не знайшов, що відповісти. Спробуй переформулювати.")
        return

    # Надсилаємо відповідь (довгу ділимо на кілька повідомлень)
    for part in _split(full_text):
        try:
            await message.answer(ai.to_telegram_html(part), parse_mode="HTML")
        except TelegramBadRequest:
            await message.answer(part, parse_mode=None)

    _remember(user_id, "user", user_text)
    _remember(user_id, "model", full_text)
    logger.info(f"Чат: відповідь для {user_id} ({len(full_text)} символів)")
