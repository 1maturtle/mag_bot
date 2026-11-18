# ======================================
# deadlines.py — Розбір і перевірка дедлайнів
# ======================================
# Правила:
#   - дедлайн не може бути в минулому (сьогоднішня дата без часу → 23:59 сьогодні)
#   - дедлайн не далі, ніж MAX_DAYS_AHEAD днів наперед
#   - без року ("25.12") → найближча така дата в майбутньому
#   - "сьогодні", "завтра", "післязавтра" розпізнаються без звернення до ШІ
# ======================================

from datetime import datetime, timedelta
from typing import Optional

# Максимальний горизонт дедлайну (днів)
MAX_DAYS_AHEAD = 365

_RELATIVE_DAYS = {
    "сьогодні": 0,
    "завтра": 1,
    "післязавтра": 2,
}


def _end_of_day(dt: datetime) -> datetime:
    return dt.replace(hour=23, minute=59, second=0, microsecond=0)


def parse_deadline_text(text: str, now: Optional[datetime] = None) -> Optional[datetime]:
    """
    Розбирає дедлайн у стандартних форматах без звернення до ШІ.

    Підтримує: ДД.ММ.РРРР [ГГ:ХХ], ДД.ММ.РР [ГГ:ХХ], ДД.ММ [ГГ:ХХ],
    РРРР-ММ-ДД [ГГ:ХХ], "сьогодні"/"завтра"/"післязавтра".
    Повертає None, якщо формат не розпізнано.
    """
    now = now or datetime.now()
    text = text.strip().lower().replace(",", " ").replace("/", ".")
    text = " ".join(text.split())

    if text in _RELATIVE_DAYS:
        return _end_of_day(now + timedelta(days=_RELATIVE_DAYS[text]))

    # Формати з роком
    for fmt in ("%d.%m.%Y %H:%M", "%d.%m.%Y", "%d.%m.%y %H:%M", "%d.%m.%y",
                "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(text, fmt)
            return dt if "%H" in fmt else _end_of_day(dt)
        except ValueError:
            continue

    # Формати без року → найближча майбутня дата
    for fmt in ("%d.%m %H:%M", "%d.%m"):
        try:
            parsed = datetime.strptime(text, fmt)
        except ValueError:
            continue
        try:
            dt = parsed.replace(year=now.year)
        except ValueError:  # 29.02 у невисокосний рік
            dt = parsed.replace(year=now.year + 1)
        if "%H" not in fmt:
            dt = _end_of_day(dt)
        if dt < now:
            try:
                dt = dt.replace(year=now.year + 1)
            except ValueError:
                return None
        return dt

    return None


def validate_deadline(dt: datetime, now: Optional[datetime] = None) -> Optional[str]:
    """
    Перевіряє, що дедлайн актуальний.

    Returns:
        None, якщо дедлайн коректний, інакше — текст пояснення для користувача.
    """
    now = now or datetime.now()
    if dt < now:
        return (
            f"⚠️ Дата <b>{dt.strftime('%d.%m.%Y %H:%M')}</b> вже минула.\n"
            "Дедлайн має бути в майбутньому — введи актуальну дату:"
        )
    if dt > now + timedelta(days=MAX_DAYS_AHEAD):
        return (
            f"⚠️ Дата <b>{dt.strftime('%d.%m.%Y')}</b> занадто далеко — "
            f"дедлайн можна поставити не більше ніж на рік наперед.\n"
            "Введи іншу дату:"
        )
    return None


def deadline_hint(now: Optional[datetime] = None) -> str:
    """Підказка з прикладами форматів на поточний рік."""
    now = now or datetime.now()
    example = now + timedelta(days=7)
    return (
        f"<i>Наприклад: {example.strftime('%d.%m.%Y')}, "
        f"{example.strftime('%d.%m.%Y')} 15:00, {example.strftime('%d.%m')}, "
        "'завтра' або 'в п'ятницю'</i>"
    )
