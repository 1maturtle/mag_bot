# ======================================
# database.py — Взаємодія із Supabase (PostgreSQL)
# ======================================
# Таблиці:
#   users        — реєстрація учнів
#   tasks        — домашні завдання
#   quiz_results — результати тестів
# ======================================

import asyncio
import logging
from datetime import datetime, date, timedelta
from typing import Optional

from supabase import create_client, Client

from config import SUPABASE_URL, SUPABASE_KEY

logger = logging.getLogger(__name__)

# Ініціалізація клієнта Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


async def _run(query):
    """
    Виконує синхронний запит Supabase в окремому потоці,
    щоб мережевий запит не блокував event loop бота.
    """
    return await asyncio.to_thread(query.execute)


# ──────────────────────────────────────────────────────────────
# ТАБЛИЦЯ USERS
# ──────────────────────────────────────────────────────────────

async def register_user(
    telegram_id: int,
    username: Optional[str],
    full_name: Optional[str],
) -> dict:
    """
    Реєструє нового користувача або повертає вже існуючого.
    Використовує upsert, щоб уникнути дублікатів.

    Args:
        telegram_id: Унікальний Telegram ID користувача.
        username: Нікнейм у Telegram (може бути None).
        full_name: Повне ім'я користувача.

    Returns:
        Словник із даними користувача.
    """
    try:
        response = await _run(
            supabase.table("users")
            .upsert(
                {
                    "telegram_id": telegram_id,
                    "username": username,
                    "full_name": full_name,
                },
                on_conflict="telegram_id",
            )
        )
        logger.info(f"Користувач {telegram_id} зареєстрований/оновлений.")
        return response.data[0] if response.data else {}
    except Exception as e:
        logger.error(f"Помилка реєстрації користувача {telegram_id}: {e}")
        raise


async def get_user(telegram_id: int) -> Optional[dict]:
    """
    Отримує дані користувача за telegram_id.

    Args:
        telegram_id: Telegram ID.

    Returns:
        Словник із даними або None, якщо не знайдено.
    """
    try:
        response = await _run(
            supabase.table("users")
            .select("*")
            .eq("telegram_id", telegram_id)
            .limit(1)
        )
        return response.data[0] if response.data else None
    except Exception as e:
        logger.error(f"Помилка отримання користувача {telegram_id}: {e}")
        return None


# ──────────────────────────────────────────────────────────────
# ТАБЛИЦЯ TASKS
# ──────────────────────────────────────────────────────────────

async def create_task(
    telegram_id: int,
    subject: str,
    description: str,
    deadline: datetime,
) -> dict:
    """
    Створює нове домашнє завдання в базі даних.

    Args:
        telegram_id: Telegram ID власника завдання.
        subject: Назва предмета (наприклад, "Математика").
        description: Опис або розпізнаний текст завдання.
        deadline: Дата та час дедлайну.

    Returns:
        Словник із даними створеного завдання.
    """
    try:
        response = await _run(
            supabase.table("tasks")
            .insert(
                {
                    "telegram_id": telegram_id,
                    "subject": subject,
                    "description": description,
                    "deadline": deadline.isoformat(),
                    "status": "active",
                }
            )
        )
        logger.info(f"Завдання створено для {telegram_id}: {subject}")
        return response.data[0] if response.data else {}
    except Exception as e:
        logger.error(f"Помилка створення завдання для {telegram_id}: {e}")
        raise


async def get_active_tasks(telegram_id: int) -> list[dict]:
    """
    Отримує всі активні завдання користувача, впорядковані за дедлайном.

    Args:
        telegram_id: Telegram ID.

    Returns:
        Список словників із активними завданнями.
    """
    try:
        response = await _run(
            supabase.table("tasks")
            .select("*")
            .eq("telegram_id", telegram_id)
            .eq("status", "active")
            .order("deadline", desc=False)
        )
        return response.data or []
    except Exception as e:
        logger.error(f"Помилка отримання завдань для {telegram_id}: {e}")
        return []


async def get_tasks_due_today(telegram_id: int) -> list[dict]:
    """
    Отримує активні завдання, дедлайн яких настає сьогодні або вже минув.
    Використовується планувальником для надсилання нагадувань.

    Args:
        telegram_id: Telegram ID.

    Returns:
        Список завдань на сьогодні.
    """
    try:
        today = date.today()
        today_start = datetime.combine(today, datetime.min.time()).isoformat()
        # timedelta замість day + 1 — інакше в останній день місяця ValueError
        tomorrow_start = datetime.combine(
            today + timedelta(days=1),
            datetime.min.time(),
        ).isoformat()

        response = await _run(
            supabase.table("tasks")
            .select("*")
            .eq("telegram_id", telegram_id)
            .eq("status", "active")
            .gte("deadline", today_start)
            .lt("deadline", tomorrow_start)
        )
        return response.data or []
    except Exception as e:
        logger.error(f"Помилка отримання завдань на сьогодні для {telegram_id}: {e}")
        return []


async def get_all_active_tasks_for_reminder() -> list[dict]:
    """
    Отримує всі активні завдання всіх користувачів для планувальника нагадувань.
    Повертає завдання, дедлайн яких — сьогодні або раніше.

    Returns:
        Список завдань згрупованих за telegram_id.
    """
    try:
        today_end = datetime.combine(date.today(), datetime.max.time()).isoformat()

        response = await _run(
            supabase.table("tasks")
            .select("*, users(telegram_id)")
            .eq("status", "active")
            .lte("deadline", today_end)
        )
        return response.data or []
    except Exception as e:
        logger.error(f"Помилка отримання завдань для нагадувань: {e}")
        return []


async def get_task_by_id(task_id: str) -> Optional[dict]:
    """
    Отримує завдання за його унікальним ID.

    Args:
        task_id: UUID або SERIAL ID завдання.

    Returns:
        Словник із даними завдання або None.
    """
    try:
        response = await _run(
            supabase.table("tasks")
            .select("*")
            .eq("id", task_id)
            .limit(1)
        )
        return response.data[0] if response.data else None
    except Exception as e:
        logger.error(f"Помилка отримання завдання {task_id}: {e}")
        return None


async def update_task_status(task_id: str, status: str) -> bool:
    """
    Змінює статус завдання (наприклад, на 'completed' або 'active').

    Args:
        task_id: ID завдання.
        status: Новий статус ('active' або 'completed').

    Returns:
        True якщо успішно, False якщо помилка.
    """
    try:
        await _run(supabase.table("tasks").update({"status": status}).eq("id", task_id))
        logger.info(f"Статус завдання {task_id} змінено на '{status}'.")
        return True
    except Exception as e:
        logger.error(f"Помилка зміни статусу завдання {task_id}: {e}")
        return False


async def get_all_users() -> list[dict]:
    """
    Повертає список всіх зареєстрованих користувачів.
    Використовується для масового надсилання нагадувань.

    Returns:
        Список словників із даними користувачів.
    """
    try:
        response = await _run(supabase.table("users").select("telegram_id, full_name"))
        return response.data or []
    except Exception as e:
        logger.error(f"Помилка отримання списку користувачів: {e}")
        return []


# ──────────────────────────────────────────────────────────────
# ТАБЛИЦЯ QUIZ_RESULTS
# ──────────────────────────────────────────────────────────────

async def save_quiz_result(
    telegram_id: int,
    score: int,
    feedback: str,
    task_id: Optional[str] = None,
) -> dict:
    """
    Зберігає результат пройденого тесту в базу даних.

    Args:
        telegram_id: Telegram ID учня.
        score: Кількість балів (0–100).
        feedback: Текстовий фідбек від Gemini.
        task_id: ID пов'язаного завдання (необов'язково).

    Returns:
        Словник із даними збереженого результату.
    """
    try:
        payload = {
            "telegram_id": telegram_id,
            "score": score,
            "feedback": feedback,
        }
        if task_id:
            payload["task_id"] = task_id

        response = await _run(supabase.table("quiz_results").insert(payload))
        logger.info(f"Результат тесту збережено для {telegram_id}: {score} балів.")
        return response.data[0] if response.data else {}
    except Exception as e:
        logger.error(f"Помилка збереження результату тесту для {telegram_id}: {e}")
        raise


async def get_quiz_history(telegram_id: int, limit: int = 5) -> list[dict]:
    """
    Отримує останні результати тестів користувача.

    Args:
        telegram_id: Telegram ID.
        limit: Максимальна кількість записів.

    Returns:
        Список результатів тестів.
    """
    try:
        response = await _run(
            supabase.table("quiz_results")
            .select("*")
            .eq("telegram_id", telegram_id)
            .order("created_at", desc=True)
            .limit(limit)
        )
        return response.data or []
    except Exception as e:
        logger.error(f"Помилка отримання історії тестів для {telegram_id}: {e}")
        return []
