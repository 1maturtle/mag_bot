# ======================================
# scheduler.py — Планувальник щоденних нагадувань
# ======================================
# Щодня о 18:00 (за часовим поясом Europe/Kiev):
#   1. Отримує список всіх зареєстрованих користувачів
#   2. Для кожного перевіряє активні завдання з дедлайном сьогодні або пізніше
#   3. Надсилає зведене нагадування в Telegram
# ======================================

import logging
from datetime import date, datetime, timedelta
from html import escape

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from aiogram import Bot

import database as db
from config import TIMEZONE, REMINDER_HOUR, REMINDER_MINUTE

logger = logging.getLogger(__name__)


def _format_task_reminder(task: dict) -> str:
    """
    Форматує одне завдання для нагадування.

    Args:
        task: Словник із даними завдання.

    Returns:
        Відформатований рядок з описом завдання.
    """
    subject = task.get("subject", "Невідомий предмет")
    description = task.get("description", "")
    deadline_raw = task.get("deadline", "")

    # Форматуємо дедлайн
    deadline_str = "не вказано"
    if deadline_raw:
        try:
            dt = datetime.fromisoformat(deadline_raw.replace("Z", "+00:00"))
            today = date.today()
            task_date = dt.date()

            if task_date == today:
                deadline_str = f"📛 СЬОГОДНІ о {dt.strftime('%H:%M')}"
            elif task_date == today + timedelta(days=1):
                deadline_str = f"⚠️ завтра о {dt.strftime('%H:%M')}"
            else:
                deadline_str = dt.strftime("%d.%m.%Y о %H:%M")
        except Exception:
            deadline_str = str(deadline_raw)

    # Скорочуємо опис якщо дуже довгий
    short_desc = description[:80] + "..." if len(description) > 80 else description

    return f"📖 <b>{escape(subject)}</b>\n   {escape(short_desc)}\n   ⏰ {deadline_str}"


async def send_daily_reminders(bot: Bot) -> None:
    """
    Головна задача планувальника — надсилає нагадування всім користувачам.

    Для кожного користувача:
    - Отримує активні завдання з бази даних
    - Якщо завдань немає — пропускає
    - Якщо є завдання — формує зведене повідомлення та надсилає

    Args:
        bot: Екземпляр Telegram Bot для надсилання повідомлень.
    """
    logger.info("⏰ Запуск щоденних нагадувань...")

    # Отримуємо всіх зареєстрованих користувачів
    users = await db.get_all_users()

    if not users:
        logger.info("Немає зареєстрованих користувачів для нагадувань.")
        return

    sent_count = 0
    error_count = 0

    for user in users:
        telegram_id = user.get("telegram_id")
        if not telegram_id:
            continue

        try:
            # Отримуємо активні завдання користувача
            tasks = await db.get_active_tasks(telegram_id)

            if not tasks:
                logger.debug(f"Немає завдань для нагадування користувачу {telegram_id}")
                continue

            # Формуємо зведене повідомлення
            tasks_text = "\n\n".join(_format_task_reminder(t) for t in tasks)

            # Визначаємо термінові завдання (сьогодні або прострочені)
            today = date.today()
            urgent_count = 0
            for task in tasks:
                dl = task.get("deadline", "")
                if dl:
                    try:
                        dt = datetime.fromisoformat(dl.replace("Z", "+00:00"))
                        if dt.date() <= today:
                            urgent_count += 1
                    except Exception:
                        pass

            # Заголовок нагадування
            if urgent_count > 0:
                header = (
                    f"🔔 <b>Щоденне нагадування!</b>\n\n"
                    f"⚡ У тебе {urgent_count} завдань{'я' if urgent_count == 1 else ''} "
                    f"на сьогодні!\n"
                    f"Загалом активних завдань: <b>{len(tasks)}</b>\n\n"
                )
            else:
                header = (
                    f"🔔 <b>Щоденне нагадування!</b>\n\n"
                    f"📚 У тебе <b>{len(tasks)}</b> активних завдань:\n\n"
                )

            footer = (
                "\n\n💪 <i>Ти впораєшся! Не відкладай на потім 🚀</i>"
            )

            reminder_message = header + tasks_text + footer

            # Надсилаємо повідомлення
            await bot.send_message(
                chat_id=telegram_id,
                text=reminder_message,
                parse_mode="HTML",
            )
            sent_count += 1
            logger.info(f"✅ Нагадування надіслано користувачу {telegram_id}")

        except Exception as e:
            error_count += 1
            logger.error(f"❌ Помилка надсилання нагадування {telegram_id}: {e}")

    logger.info(
        f"⏰ Нагадування завершено: надіслано {sent_count}, помилок {error_count}"
    )


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    """
    Ініціалізує та налаштовує планувальник APScheduler.

    Додає задачу щоденних нагадувань о вказаний час
    (за замовчуванням 18:00 Europe/Kiev).

    Args:
        bot: Екземпляр Telegram Bot.

    Returns:
        Налаштований, але ще не запущений AsyncIOScheduler.
    """
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)

    # Додаємо задачу щоденних нагадувань
    scheduler.add_job(
        func=send_daily_reminders,
        trigger=CronTrigger(
            hour=REMINDER_HOUR,
            minute=REMINDER_MINUTE,
            timezone=TIMEZONE,
        ),
        args=[bot],
        id="daily_reminders",
        name="Щоденні нагадування про завдання",
        replace_existing=True,  # Замінюємо якщо задача вже існує
        max_instances=1,        # Не запускаємо паралельні екземпляри
    )

    logger.info(
        f"📅 Планувальник налаштовано: нагадування щодня о "
        f"{REMINDER_HOUR:02d}:{REMINDER_MINUTE:02d} ({TIMEZONE})"
    )

    return scheduler
