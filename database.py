# ======================================
# database.py — Взаємодія із Supabase (PostgreSQL)
# ======================================
# Таблиці (структура вже існуючої бази):
#   users        — id (= Telegram ID), username, created_at
#   tasks        — id, user_id → users.id, subject, description,
#                  deadline (ТЕКСТ "ДД.ММ.РРРР ГГ:ХХ"), status ('active'/'completed'),
#                  result_description, created_at
#   quiz_results — id, user_id → users.id, topic, score (к-сть правильних),
#                  total_questions, created_at
#
# Назовні модуль віддає задачі з дедлайном у форматі ISO 8601,
# щоб обробники та планувальник працювали з датою однаково.
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

# Формат, у якому дедлайн зберігається в колонці tasks.deadline (тип text)
DEADLINE_DB_FORMAT = "%d.%m.%Y %H:%M"


async def _run(query):
    """
    Виконує синхронний запит Supabase в окремому потоці,
    щоб мережевий запит не блокував event loop бота.
    """
    return await asyncio.to_thread(query.execute)


# ──────────────────────────────────────────────────────────────
# ДОПОМІЖНІ ФУНКЦІЇ ДЛЯ ДЕДЛАЙНУ
# ──────────────────────────────────────────────────────────────

def _parse_deadline(raw: Optional[str]) -> Optional[datetime]:
    """Розбирає дедлайн з БД: "ДД.ММ.РРРР ГГ:ХХ", "ДД.ММ.РРРР" або ISO 8601."""
    if not raw:
        return None
    raw = raw.strip()
    for fmt in (DEADLINE_DB_FORMAT, "%d.%m.%Y"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            pass
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.replace(tzinfo=None)
    except ValueError:
        return None


def _normalize_task(task: dict) -> dict:
    """
    Приводить запис задачі до формату, з яким працюють обробники:
    deadline → ISO 8601 (або сирий текст, якщо дату не вдалося розібрати),
    telegram_id → копія user_id.
    """
    task = dict(task)
    dt = _parse_deadline(task.get("deadline"))
    if dt is not None:
        task["deadline"] = dt.isoformat()
    task["telegram_id"] = task.get("user_id")
    return task


def _sort_by_deadline(tasks: list[dict]) -> list[dict]:
    """Сортує задачі за дедлайном (без дати — в кінці)."""
    return sorted(tasks, key=lambda t: _parse_deadline(t.get("deadline")) or datetime.max)


# ──────────────────────────────────────────────────────────────
# ТАБЛИЦЯ USERS
# ──────────────────────────────────────────────────────────────

async def register_user(
    telegram_id: int,
    username: Optional[str],
    full_name: Optional[str] = None,
) -> dict:
    """
    Реєструє нового користувача або оновлює існуючого (upsert за id).

    Args:
        telegram_id: Telegram ID — він же первинний ключ users.id.
        username: Нікнейм у Telegram. Якщо його немає — зберігаємо ID текстом.
        full_name: Не зберігається (у таблиці немає такої колонки),
                   параметр лишено для сумісності з обробниками.

    Returns:
        Словник із даними користувача.
    """
    try:
        response = await _run(
            supabase.table("users")
            .upsert(
                {
                    "id": telegram_id,
                    "username": username or str(telegram_id),
                },
                on_conflict="id",
            )
        )
        logger.info(f"Користувач {telegram_id} зареєстрований/оновлений.")
        return response.data[0] if response.data else {}
    except Exception as e:
        logger.error(f"Помилка реєстрації користувача {telegram_id}: {e}")
        raise


async def get_user(telegram_id: int) -> Optional[dict]:
    """Отримує дані користувача за Telegram ID або None."""
    try:
        response = await _run(
            supabase.table("users").select("*").eq("id", telegram_id).limit(1)
        )
        return response.data[0] if response.data else None
    except Exception as e:
        logger.error(f"Помилка отримання користувача {telegram_id}: {e}")
        return None


async def get_all_users() -> list[dict]:
    """
    Повертає список всіх зареєстрованих користувачів
    у вигляді [{"telegram_id": ..., "username": ...}].
    """
    try:
        response = await _run(supabase.table("users").select("id, username"))
        return [
            {"telegram_id": u["id"], "username": u.get("username")}
            for u in (response.data or [])
        ]
    except Exception as e:
        logger.error(f"Помилка отримання списку користувачів: {e}")
        return []


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
    Створює нове домашнє завдання.

    Args:
        telegram_id: Telegram ID власника (users.id).
        subject: Назва предмета.
        description: Опис завдання.
        deadline: Дата та час дедлайну.

    Returns:
        Словник із даними створеного завдання.
    """
    try:
        response = await _run(
            supabase.table("tasks").insert(
                {
                    "user_id": telegram_id,
                    "subject": subject,
                    "description": description,
                    "deadline": deadline.strftime(DEADLINE_DB_FORMAT),
                    "status": "active",
                }
            )
        )
        logger.info(f"Завдання створено для {telegram_id}: {subject}")
        return _normalize_task(response.data[0]) if response.data else {}
    except Exception as e:
        logger.error(f"Помилка створення завдання для {telegram_id}: {e}")
        raise


async def get_active_tasks(telegram_id: int) -> list[dict]:
    """
    Отримує всі активні завдання користувача, впорядковані за дедлайном.
    Дедлайн у БД — текст "ДД.ММ.РРРР", тож сортуємо в Python, а не в SQL.
    """
    try:
        response = await _run(
            supabase.table("tasks")
            .select("*")
            .eq("user_id", telegram_id)
            .eq("status", "active")
        )
        tasks = [_normalize_task(t) for t in (response.data or [])]
        return _sort_by_deadline(tasks)
    except Exception as e:
        logger.error(f"Помилка отримання завдань для {telegram_id}: {e}")
        return []


async def get_tasks_due_today(telegram_id: int) -> list[dict]:
    """Активні завдання користувача з дедлайном сьогодні."""
    today = date.today()
    tasks = await get_active_tasks(telegram_id)
    return [
        t for t in tasks
        if (dt := _parse_deadline(t.get("deadline"))) and dt.date() == today
    ]


async def get_all_active_tasks_for_reminder() -> list[dict]:
    """
    Активні завдання всіх користувачів, дедлайн яких — сьогодні або раніше.
    """
    try:
        response = await _run(
            supabase.table("tasks").select("*").eq("status", "active")
        )
        today = date.today()
        tasks = [_normalize_task(t) for t in (response.data or [])]
        return [
            t for t in tasks
            if (dt := _parse_deadline(t.get("deadline"))) and dt.date() <= today
        ]
    except Exception as e:
        logger.error(f"Помилка отримання завдань для нагадувань: {e}")
        return []


async def get_task_by_id(task_id: str) -> Optional[dict]:
    """Отримує завдання за його ID або None."""
    try:
        response = await _run(
            supabase.table("tasks").select("*").eq("id", task_id).limit(1)
        )
        return _normalize_task(response.data[0]) if response.data else None
    except Exception as e:
        logger.error(f"Помилка отримання завдання {task_id}: {e}")
        return None


async def update_task_status(task_id: str, status: str) -> bool:
    """Змінює статус завдання ('active' або 'completed')."""
    try:
        await _run(supabase.table("tasks").update({"status": status}).eq("id", task_id))
        logger.info(f"Статус завдання {task_id} змінено на '{status}'.")
        return True
    except Exception as e:
        logger.error(f"Помилка зміни статусу завдання {task_id}: {e}")
        return False


# ──────────────────────────────────────────────────────────────
# ТАБЛИЦЯ QUIZ_RESULTS
# ──────────────────────────────────────────────────────────────

async def save_quiz_result(
    telegram_id: int,
    topic: str,
    score: int,
    total_questions: int,
) -> dict:
    """
    Зберігає результат пройденого тесту.

    Args:
        telegram_id: Telegram ID учня (users.id).
        topic: Тема/предмет тесту.
        score: Кількість правильних відповідей.
        total_questions: Загальна кількість питань.
    """
    try:
        response = await _run(
            supabase.table("quiz_results").insert(
                {
                    "user_id": telegram_id,
                    "topic": topic,
                    "score": score,
                    "total_questions": total_questions,
                }
            )
        )
        logger.info(
            f"Результат тесту збережено для {telegram_id}: {score}/{total_questions}."
        )
        return response.data[0] if response.data else {}
    except Exception as e:
        logger.error(f"Помилка збереження результату тесту для {telegram_id}: {e}")
        raise


async def get_quiz_history(telegram_id: int, limit: int = 5) -> list[dict]:
    """
    Останні результати тестів користувача.
    До кожного запису додається поле "percent" (0–100).
    """
    try:
        response = await _run(
            supabase.table("quiz_results")
            .select("*")
            .eq("user_id", telegram_id)
            .order("created_at", desc=True)
            .limit(limit)
        )
        results = []
        for r in response.data or []:
            total = r.get("total_questions") or 0
            score = r.get("score") or 0
            r["percent"] = round(score / total * 100) if total else 0
            results.append(r)
        return results
    except Exception as e:
        logger.error(f"Помилка отримання історії тестів для {telegram_id}: {e}")
        return []
