# ======================================
# handlers/tasks.py — Управління домашніми завданнями
# ======================================
# Включає:
#   - Перегляд активних завдань
#   - Покрокове додавання завдання текстом (FSM)
#   - Позначення завдання виконаним
#   - Запуск тесту по завданню
#   - Перегляд прогресу
# ======================================

import logging
from datetime import datetime
from html import escape
from typing import Optional

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)

import database as db
import ai_service as ai
from states import AddTaskStates, QuizStates
from handlers.start import get_main_menu

logger = logging.getLogger(__name__)

# Роутер для завдань та тестів
router = Router(name="tasks")


# ──────────────────────────────────────────────────────────────
# КЛАВІАТУРИ
# ──────────────────────────────────────────────────────────────

def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Клавіатура з кнопкою скасування поточної дії."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Скасувати")]],
        resize_keyboard=True,
    )


def get_task_actions_keyboard(task_id: str) -> InlineKeyboardMarkup:
    """
    Inline-клавіатура з діями для конкретного завдання.

    Args:
        task_id: ID завдання.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Виконано",
                    callback_data=f"complete:{task_id}",
                ),
                InlineKeyboardButton(
                    text="🧠 Тест",
                    callback_data=f"quiz:{task_id}",
                ),
            ]
        ]
    )


def get_quiz_options_keyboard(options: list[str], question_idx: int) -> InlineKeyboardMarkup:
    """
    Inline-клавіатура з варіантами відповідей для тесту.

    Args:
        options: Список варіантів відповідей.
        question_idx: Індекс поточного питання.
    """
    buttons = []
    letters = ["А", "Б", "В", "Г"]
    for i, option in enumerate(options):
        letter = letters[i] if i < len(letters) else str(i + 1)
        buttons.append([
            InlineKeyboardButton(
                text=option,
                callback_data=f"answer:{question_idx}:{letter}",
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ──────────────────────────────────────────────────────────────
# ПЕРЕГЛЯД ЗАВДАНЬ
# ──────────────────────────────────────────────────────────────

@router.message(F.text == "📚 Мої завдання")
async def handle_my_tasks(message: Message) -> None:
    """
    Показує список активних домашніх завдань користувача.
    Для кожного завдання відображає предмет, опис, дедлайн та кнопки дій.
    """
    tasks = await db.get_active_tasks(message.from_user.id)

    if not tasks:
        await message.answer(
            "📭 У тебе поки немає активних завдань!\n\n"
            "Натисни <b>➕ Додати завдання</b> або надішли голосове повідомлення 🎤",
            parse_mode="HTML",
            reply_markup=get_main_menu(),
        )
        return

    await message.answer(
        f"📚 <b>Твої активні завдання ({len(tasks)}):</b>",
        parse_mode="HTML",
    )

    for task in tasks:
        # Форматуємо дату дедлайну
        deadline_str = _format_deadline(task.get("deadline"))

        task_text = (
            f"📖 <b>{escape(task['subject'])}</b>\n"
            f"📝 {escape(task['description'])}\n"
            f"⏰ Дедлайн: <b>{deadline_str}</b>"
        )

        await message.answer(
            task_text,
            parse_mode="HTML",
            reply_markup=get_task_actions_keyboard(str(task["id"])),
        )


def _format_deadline(deadline_raw: Optional[str]) -> str:
    """
    Форматує дедлайн із ISO рядка в читабельний вигляд.

    Args:
        deadline_raw: Рядок дати у форматі ISO 8601.

    Returns:
        Відформатована дата та час.
    """
    if not deadline_raw:
        return "не вказано"
    try:
        dt = datetime.fromisoformat(deadline_raw.replace("Z", "+00:00"))
        return dt.strftime("%d.%m.%Y о %H:%M")
    except Exception:
        return deadline_raw


# ──────────────────────────────────────────────────────────────
# ДОДАВАННЯ ЗАВДАННЯ (FSM)
# ──────────────────────────────────────────────────────────────

@router.message(F.text == "➕ Додати завдання")
async def handle_add_task_start(message: Message, state: FSMContext) -> None:
    """
    Починає процес покрокового додавання завдання текстом.
    Переводить бота у стан очікування назви предмета.
    """
    await state.set_state(AddTaskStates.waiting_for_subject)
    await message.answer(
        "➕ <b>Додавання нового завдання</b>\n\n"
        "Крок 1/3 — Введи назву <b>предмета</b>:\n"
        "<i>(наприклад: Математика, Фізика, Українська мова)</i>",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard(),
    )


@router.message(AddTaskStates.waiting_for_subject, F.text)
async def handle_task_subject(message: Message, state: FSMContext) -> None:
    """
    Отримує назву предмета та переходить до кроку опису.
    """
    if message.text == "❌ Скасувати":
        await _cancel_action(message, state)
        return

    subject = message.text.strip()
    if len(subject) < 2:
        await message.answer("⚠️ Назва предмета занадто коротка. Спробуй ще раз:")
        return

    # Зберігаємо предмет у стані FSM
    await state.update_data(subject=subject)
    await state.set_state(AddTaskStates.waiting_for_description)

    await message.answer(
        f"✅ Предмет: <b>{escape(subject)}</b>\n\n"
        "Крок 2/3 — Введи <b>опис завдання</b>:\n"
        "<i>(що потрібно зробити?)</i>",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard(),
    )


@router.message(AddTaskStates.waiting_for_description, F.text)
async def handle_task_description(message: Message, state: FSMContext) -> None:
    """
    Отримує опис завдання та переходить до кроку дедлайну.
    """
    if message.text == "❌ Скасувати":
        await _cancel_action(message, state)
        return

    description = message.text.strip()
    if len(description) < 5:
        await message.answer("⚠️ Опис завдання занадто короткий. Спробуй ще раз:")
        return

    await state.update_data(description=description)
    await state.set_state(AddTaskStates.waiting_for_deadline)

    await message.answer(
        "Крок 3/3 — Введи <b>дедлайн</b>:\n"
        "<i>Формати: 25.10.2024, 25.10.2024 15:00, або просто 'завтра', 'в п'ятницю'</i>",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard(),
    )


@router.message(AddTaskStates.waiting_for_deadline, F.text)
async def handle_task_deadline(message: Message, state: FSMContext) -> None:
    """
    Отримує дедлайн, парсить його та зберігає завдання в базу даних.
    """
    if message.text == "❌ Скасувати":
        await _cancel_action(message, state)
        return

    deadline_text = message.text.strip()
    data = await state.get_data()

    # Намагаємось розпарсити дедлайн
    deadline_dt = _try_parse_deadline(deadline_text)

    if deadline_dt is None:
        # Якщо не вдалось парсити стандартно — просимо Gemini
        await message.answer("⏳ Розпізнаю дату...")
        iso_str = await ai.parse_deadline_to_datetime(deadline_text)
        if iso_str:
            try:
                deadline_dt = datetime.fromisoformat(iso_str)
            except Exception:
                deadline_dt = None

    if deadline_dt is None:
        await message.answer(
            "⚠️ Не вдалось розпізнати дату. Спробуй формат <b>ДД.ММ.РРРР</b> "
            "або <b>ДД.ММ.РРРР ГГ:ХХ</b>",
            parse_mode="HTML",
        )
        return

    # Зберігаємо завдання
    try:
        task = await db.create_task(
            telegram_id=message.from_user.id,
            subject=data["subject"],
            description=data["description"],
            deadline=deadline_dt,
        )
        await state.clear()

        confirmation = (
            "✅ <b>Завдання додано!</b>\n\n"
            f"📖 Предмет: <b>{escape(data['subject'])}</b>\n"
            f"📝 Опис: {escape(data['description'])}\n"
            f"⏰ Дедлайн: <b>{deadline_dt.strftime('%d.%m.%Y о %H:%M')}</b>"
        )
        await message.answer(
            confirmation,
            parse_mode="HTML",
            reply_markup=get_main_menu(),
        )
        logger.info(f"Завдання додано для {message.from_user.id}: {data['subject']}")

    except Exception as e:
        logger.error(f"Помилка збереження завдання: {e}")
        await state.clear()
        await message.answer(
            "❌ Виникла помилка при збереженні завдання. Спробуй ще раз.",
            reply_markup=get_main_menu(),
        )


def _try_parse_deadline(text: str) -> Optional[datetime]:
    """
    Намагається розпарсити текст дедлайну стандартними форматами.

    Args:
        text: Текстовий рядок з датою.

    Returns:
        Об'єкт datetime або None.
    """
    formats = [
        "%d.%m.%Y %H:%M",
        "%d.%m.%Y",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(text, fmt)
            # Якщо час не вказано — встановлюємо 23:59
            if fmt in ("%d.%m.%Y", "%Y-%m-%d"):
                dt = dt.replace(hour=23, minute=59)
            return dt
        except ValueError:
            continue
    return None


# ──────────────────────────────────────────────────────────────
# CALLBACK — ПОЗНАЧЕННЯ ВИКОНАНИМ
# ──────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("complete:"))
async def handle_complete_task(callback: CallbackQuery) -> None:
    """
    Обробляє натискання кнопки "Виконано" для завдання.
    Змінює статус завдання на 'completed' у базі даних.
    """
    task_id = callback.data.split(":", 1)[1]

    success = await db.update_task_status(task_id, "completed")

    if success:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(
            "🎉 Чудово! Завдання позначено як виконане!\n"
            "Так тримати — ти молодець! 💪",
        )
    else:
        await callback.answer("❌ Помилка оновлення статусу.", show_alert=True)

    await callback.answer()


# ──────────────────────────────────────────────────────────────
# ТЕСТ (QUIZ) — ЗАПУСК ТА ПРОХОДЖЕННЯ
# ──────────────────────────────────────────────────────────────

@router.message(F.text == "🧠 Пройти тест")
async def handle_quiz_start_menu(message: Message, state: FSMContext) -> None:
    """
    Запускає вибір завдання для тесту з головного меню.
    Показує список активних завдань як варіанти для тесту.
    """
    tasks = await db.get_active_tasks(message.from_user.id)

    if not tasks:
        await message.answer(
            "📭 Немає активних завдань для тесту!\n"
            "Спочатку додай домашнє завдання.",
            reply_markup=get_main_menu(),
        )
        return

    # Формуємо inline кнопки для вибору завдання
    buttons = []
    for task in tasks[:8]:  # Обмежуємо 8 завданнями
        label = f"📖 {task['subject']} — {task['description'][:30]}..."
        buttons.append([
            InlineKeyboardButton(
                text=label,
                callback_data=f"quiz:{task['id']}",
            )
        ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await message.answer(
        "🧠 <b>Вибери завдання для тесту:</b>",
        parse_mode="HTML",
        reply_markup=keyboard,
    )


@router.callback_query(F.data.startswith("quiz:"))
async def handle_quiz_launch(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Запускає генерацію тесту для обраного завдання.
    Gemini генерує 5 питань на основі теми та опису ДЗ.
    """
    task_id = callback.data.split(":", 1)[1]
    task = await db.get_task_by_id(task_id)

    if not task:
        await callback.answer("❌ Завдання не знайдено.", show_alert=True)
        return

    await callback.answer()
    await callback.message.answer(
        f"⏳ Генерую тест по предмету <b>{escape(task['subject'])}</b>...\n"
        "<i>Це може зайняти кілька секунд.</i>",
        parse_mode="HTML",
    )

    # Генеруємо тест через Gemini
    quiz_data = await ai.generate_quiz(
        subject=task["subject"],
        description=task["description"],
    )

    if not quiz_data or not quiz_data.get("questions"):
        await callback.message.answer(
            "❌ Не вдалось згенерувати тест. Спробуй ще раз.",
            reply_markup=get_main_menu(),
        )
        return

    # Зберігаємо тест та стан у FSM
    await state.set_state(QuizStates.answering_question)
    await state.update_data(
        quiz=quiz_data["questions"],
        current_q=0,
        score=0,
        task_id=task_id,
        subject=task["subject"],
        # callback.message надіслав бот, тож ID учня беремо з callback.from_user
        telegram_id=callback.from_user.id,
    )

    total = len(quiz_data["questions"])
    await callback.message.answer(
        f"🧠 <b>Тест по предмету: {escape(task['subject'])}</b>\n"
        f"Всього питань: {total}\n\n"
        "Готовий? Починаємо! 🚀",
        parse_mode="HTML",
    )

    # Показуємо перше питання
    await _send_question(callback.message, state)


async def _send_question(message: Message, state: FSMContext) -> None:
    """
    Надсилає поточне питання тесту з варіантами відповідей.

    Args:
        message: Об'єкт повідомлення для відправки.
        state: Контекст FSM зі станом тесту.
    """
    data = await state.get_data()
    quiz = data["quiz"]
    current_q = data["current_q"]

    if current_q >= len(quiz):
        # Тест завершено
        await _finish_quiz(message, state)
        return

    question_data = quiz[current_q]
    q_text = (
        f"❓ <b>Питання {current_q + 1}/{len(quiz)}</b>\n\n"
        f"{escape(question_data['question'])}"
    )

    await message.answer(
        q_text,
        parse_mode="HTML",
        reply_markup=get_quiz_options_keyboard(
            question_data["options"],
            current_q,
        ),
    )


@router.callback_query(QuizStates.answering_question, F.data.startswith("answer:"))
async def handle_quiz_answer(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Обробляє відповідь учня на питання тесту.
    Порівнює відповідь з правильною та надає фідбек від Gemini.
    """
    parts = callback.data.split(":")
    question_idx = int(parts[1])
    user_answer = parts[2]

    data = await state.get_data()
    quiz = data["quiz"]
    current_q = data["current_q"]
    score = data["score"]

    # Перевіряємо, що відповідь на правильне питання
    if question_idx != current_q:
        await callback.answer("Це питання вже пройдено.")
        return

    question_data = quiz[current_q]
    correct = question_data["correct"]
    is_correct = user_answer.upper() == correct.upper()

    if is_correct:
        score += 1

    # Отримуємо фідбек від Gemini
    feedback = await ai.check_answer_and_feedback(
        question=question_data["question"],
        correct_answer=correct,
        user_answer=user_answer,
        explanation=question_data.get("explanation", ""),
        score=score,
        total=len(quiz),
    )

    # Вимикаємо кнопки попереднього питання
    await callback.message.edit_reply_markup(reply_markup=None)

    await callback.message.answer(escape(feedback))
    await callback.answer()

    # Оновлюємо стан
    await state.update_data(current_q=current_q + 1, score=score)

    # Надсилаємо наступне питання
    await _send_question(callback.message, state)


async def _finish_quiz(message: Message, state: FSMContext) -> None:
    """
    Завершує тест, показує підсумковий результат та зберігає в БД.

    Args:
        message: Об'єкт повідомлення.
        state: Контекст FSM.
    """
    data = await state.get_data()
    score = data["score"]
    total = len(data["quiz"])
    task_id = data.get("task_id")
    subject = data.get("subject", "")
    # message тут — повідомлення бота, тому message.from_user — це сам бот
    telegram_id = data.get("telegram_id")

    # Отримуємо фінальний фідбек від Gemini
    final_feedback = await ai.generate_final_feedback(score, total, subject)

    percentage = round((score / total) * 100) if total > 0 else 0

    result_text = (
        f"🏁 <b>Тест завершено!</b>\n\n"
        f"📊 Результат: <b>{score}/{total}</b> ({percentage}%)\n\n"
        f"{escape(final_feedback)}"
    )

    await message.answer(
        result_text,
        parse_mode="HTML",
        reply_markup=get_main_menu(),
    )

    # Зберігаємо результат у базу даних
    if telegram_id:
        try:
            await db.save_quiz_result(
                telegram_id=telegram_id,
                score=percentage,
                feedback=final_feedback,
                task_id=task_id,
            )
        except Exception as e:
            logger.error(f"Помилка збереження результату тесту: {e}")

    await state.clear()


# ──────────────────────────────────────────────────────────────
# ПРОГРЕС КОРИСТУВАЧА
# ──────────────────────────────────────────────────────────────

@router.message(F.text == "📊 Мій прогрес")
async def handle_my_progress(message: Message) -> None:
    """
    Показує статистику навчання: кількість завдань та результати тестів.
    """
    telegram_id = message.from_user.id

    # Отримуємо активні завдання та результати тестів паралельно
    tasks = await db.get_active_tasks(telegram_id)
    quiz_history = await db.get_quiz_history(telegram_id, limit=5)

    tasks_count = len(tasks)

    if quiz_history:
        avg_score = round(sum(q["score"] for q in quiz_history) / len(quiz_history))
        best_score = max(q["score"] for q in quiz_history)
    else:
        avg_score = 0
        best_score = 0

    progress_text = (
        f"📊 <b>Твій прогрес</b>\n\n"
        f"📚 Активних завдань: <b>{tasks_count}</b>\n"
        f"🧠 Пройдено тестів: <b>{len(quiz_history)}</b>\n"
        f"📈 Середній бал: <b>{avg_score}%</b>\n"
        f"🏆 Найкращий результат: <b>{best_score}%</b>\n"
    )

    if quiz_history:
        progress_text += "\n<b>Останні тести:</b>\n"
        for result in quiz_history:
            created = result.get("created_at", "")[:10]
            progress_text += f"  • {result['score']}% — {created}\n"

    if not quiz_history:
        progress_text += "\n<i>Ще немає результатів тестів. Пройди перший тест!</i>"

    await message.answer(
        progress_text,
        parse_mode="HTML",
        reply_markup=get_main_menu(),
    )


# ──────────────────────────────────────────────────────────────
# СКАСУВАННЯ
# ──────────────────────────────────────────────────────────────

@router.message(F.text == "❌ Скасувати")
async def handle_cancel(message: Message, state: FSMContext) -> None:
    """Скасовує поточну дію та повертає до головного меню."""
    await _cancel_action(message, state)


async def _cancel_action(message: Message, state: FSMContext) -> None:
    """Скидає FSM стан та повертає до головного меню."""
    await state.clear()
    await message.answer(
        "❌ Дію скасовано.",
        reply_markup=get_main_menu(),
    )
