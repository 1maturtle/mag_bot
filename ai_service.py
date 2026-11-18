# ======================================
# ai_service.py — Інтеграція з Google Gemini API
# ======================================
# Функції:
#   - Генерація тесту за темою завдання
#   - Перевірка відповіді учня + фідбек
#   - Транскрипція голосового повідомлення
#   - Витягування структурованих даних завдання з аудіо
# ======================================

import html
import json
import logging
import re
from typing import Optional

from google import genai
from google.genai import types

from config import GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger(__name__)

# Клієнт Gemini (новий SDK google-genai). Виклики йдуть через client.aio —
# асинхронно, щоб не блокувати event loop бота під час запиту до ШІ.
_client = genai.Client(api_key=GEMINI_API_KEY)

# Конфігурація для тексту/чату
_TEXT_CONFIG = types.GenerateContentConfig(
    temperature=0.7,
    max_output_tokens=8192,
)

# Конфігурація для мультимодальних запитів (аудіо + текст)
_MULTIMODAL_CONFIG = types.GenerateContentConfig(
    temperature=0.2,  # Нижча температура для точної транскрипції
    max_output_tokens=8192,
)


def to_telegram_html(text: str) -> str:
    """
    Готує текст від Gemini до надсилання з parse_mode=HTML:
    екранує <, >, & і перетворює Markdown-жирний **текст** на <b>текст</b>.
    """
    safe = html.escape(text)
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", safe, flags=re.DOTALL)


async def _generate(contents, config: types.GenerateContentConfig) -> str:
    """Виконує асинхронний запит до Gemini та повертає текст відповіді."""
    response = await _client.aio.models.generate_content(
        model=GEMINI_MODEL,
        contents=contents,
        config=config,
    )
    return (response.text or "").strip()


# ──────────────────────────────────────────────────────────────
# ГЕНЕРАЦІЯ ТЕСТУ
# ──────────────────────────────────────────────────────────────

async def generate_quiz(subject: str, description: str) -> Optional[dict]:
    """
    Генерує тест із 5 питань на основі теми та опису домашнього завдання.

    Повертає структурований JSON із питаннями та варіантами відповідей.

    Args:
        subject: Назва предмета (наприклад, "Математика").
        description: Опис домашнього завдання.

    Returns:
        Словник із полем "questions" — список питань, або None при помилці.

    Приклад повернутого словника:
        {
            "questions": [
                {
                    "question": "...",
                    "options": ["А) ...", "Б) ...", "В) ...", "Г) ..."],
                    "correct": "А",
                    "explanation": "..."
                }
            ]
        }
    """
    prompt = f"""Ти — розумний помічник-учитель для учнів. 
Створи тест рівно з 5 питань за темою домашнього завдання.

Предмет: {subject}
Опис завдання: {description}

Вимоги до тесту:
- Кожне питання має 4 варіанти відповіді (А, Б, В, Г)
- Тільки одна правильна відповідь
- Питання мають перевіряти розуміння матеріалу, а не просто пам'ять
- Поясни правильну відповідь одним реченням

Поверни ТІЛЬКИ валідний JSON у такому форматі (без зайвого тексту):
{{
  "questions": [
    {{
      "question": "Текст питання",
      "options": ["А) варіант", "Б) варіант", "В) варіант", "Г) варіант"],
      "correct": "А",
      "explanation": "Пояснення чому ця відповідь правильна"
    }}
  ]
}}

Мова тесту: українська."""

    try:
        raw_text = await _generate(prompt, _TEXT_CONFIG)

        # Витягуємо JSON навіть якщо є зайвий текст навколо
        json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if not json_match:
            logger.error("Gemini не повернув валідний JSON для тесту.")
            return None

        quiz_data = json.loads(json_match.group())
        logger.info(f"Тест згенеровано для предмета: {subject}")
        return quiz_data

    except json.JSONDecodeError as e:
        logger.error(f"Помилка парсингу JSON відповіді Gemini: {e}")
        return None
    except Exception as e:
        logger.error(f"Помилка генерації тесту: {e}")
        return None


# ──────────────────────────────────────────────────────────────
# ПЕРЕВІРКА ВІДПОВІДІ ТА ФІДБЕК
# ──────────────────────────────────────────────────────────────

async def check_answer_and_feedback(
    question: str,
    correct_answer: str,
    user_answer: str,
    explanation: str,
    score: int,
    total: int,
) -> str:
    """
    Генерує мотивуючий персоналізований фідбек після відповіді на питання.

    Args:
        question: Текст питання.
        correct_answer: Правильний варіант відповіді (наприклад "А").
        user_answer: Відповідь учня.
        explanation: Пояснення правильної відповіді.
        score: Поточна кількість правильних відповідей.
        total: Загальна кількість питань.

    Returns:
        Рядок з фідбеком від Gemini.
    """
    is_correct = user_answer.upper().strip() == correct_answer.upper().strip()

    prompt = f"""Ти — дружній вчитель-помічник для учнів. 
Учень відповів на питання тесту.

Питання: {question}
Правильна відповідь: {correct_answer}
Відповідь учня: {user_answer}
Результат: {"✅ Правильно!" if is_correct else "❌ Неправильно"}
Пояснення: {explanation}
Поточний рахунок: {score} з {total}

Завдання:
{"Підбадьор учня, похвали за правильну відповідь (1-2 речення)." if is_correct else "Підтримай учня, поясни помилку доброзичливо, вкажи на правильну відповідь (2-3 речення)."}

Відповідай лише українською мовою. Будь коротким, теплим та мотивуючим."""

    try:
        return await _generate(prompt, _TEXT_CONFIG)
    except Exception as e:
        logger.error(f"Помилка генерації фідбеку: {e}")
        if is_correct:
            return "✅ Чудово! Правильна відповідь!"
        else:
            return f"❌ На жаль, неправильно. Правильна відповідь: {correct_answer}. {explanation}"


async def generate_final_feedback(score: int, total: int, subject: str) -> str:
    """
    Генерує підсумковий мотивуючий фідбек після завершення всього тесту.

    Args:
        score: Кількість правильних відповідей.
        total: Загальна кількість питань.
        subject: Назва предмета.

    Returns:
        Підсумковий фідбек-рядок.
    """
    percentage = round((score / total) * 100) if total > 0 else 0

    prompt = f"""Ти — дружній вчитель-помічник для учнів.
Учень щойно завершив тест з предмета "{subject}".

Результат: {score} з {total} правильних відповідей ({percentage}%).

Напиши короткий (3-5 речень) мотивуючий підсумок:
- Якщо результат > 80%: активно хвали, говори що учень молодець
- Якщо результат 50-80%: підтримай, скажи що є прогрес, порекомендуй повторити матеріал
- Якщо результат < 50%: підбадьор, не критикуй, запропонуй не здаватися і повторити тему

Відповідай лише українською мовою. Додай 1-2 емодзі для підтримки настрою."""

    try:
        return await _generate(prompt, _TEXT_CONFIG)
    except Exception as e:
        logger.error(f"Помилка генерації фінального фідбеку: {e}")
        return f"🏁 Тест завершено! Результат: {score}/{total} ({percentage}%). Продовжуй навчатися!"


# ──────────────────────────────────────────────────────────────
# ОБРОБКА ГОЛОСОВИХ ПОВІДОМЛЕНЬ
# ──────────────────────────────────────────────────────────────

async def transcribe_and_extract_task(audio_bytes: bytes, mime_type: str = "audio/ogg") -> Optional[dict]:
    """
    Транскрибує голосове повідомлення та витягує з нього дані завдання.

    Використовує мультимодальні можливості Gemini для:
    1. Розпізнавання мови з аудіофайлу (.ogg або .mp3)
    2. Витягування структурованих даних: предмет, опис, дедлайн

    Args:
        audio_bytes: Байти аудіофайлу.
        mime_type: MIME-тип аудіо (за замовчуванням "audio/ogg").

    Returns:
        Словник із полями:
            - "subject": str — назва предмета
            - "description": str — опис завдання
            - "deadline_text": str — дедлайн у текстовому форматі (наприклад "завтра" або "22 жовтня")
            - "raw_transcript": str — повний транскрипт аудіо
        або None у разі помилки.
    """
    prompt = """Ти — помічник для розпізнавання домашніх завдань з голосу.

Прослухай аудіо і виконай два завдання:
1. Повністю транскрибуй мовлення
2. Витягни структуровані дані завдання

Поверни ТІЛЬКИ валідний JSON (без зайвого тексту):
{
  "raw_transcript": "Повний текст того, що сказано в аудіо",
  "subject": "Назва предмета (наприклад: Математика, Фізика, Українська мова). Якщо не вказано — 'Загальне'",
  "description": "Детальний опис завдання — що потрібно зробити",
  "deadline_text": "Дедлайн як сказано в аудіо (наприклад: 'завтра', '22 жовтня', 'на п'ятницю'). Якщо не вказано — 'не вказано'"
}

Якщо в аудіо немає чіткого завдання — поверни description як порожній рядок."""

    try:
        # Голосові з Telegram невеликі (< 20 МБ), тож передаємо аудіо
        # напряму в запиті (inline), без Files API та тимчасових файлів.
        audio_part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)
        raw_text = await _generate([audio_part, prompt], _MULTIMODAL_CONFIG)

        # Витягуємо JSON із відповіді
        json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if not json_match:
            logger.error("Gemini не повернув валідний JSON для голосового повідомлення.")
            return None

        result = json.loads(json_match.group())
        logger.info(f"Голосове повідомлення успішно розпізнано. Предмет: {result.get('subject', 'N/A')}")
        return result

    except json.JSONDecodeError as e:
        logger.error(f"Помилка парсингу JSON транскрипції: {e}")
        return None
    except Exception as e:
        logger.error(f"Помилка обробки голосового повідомлення: {e}")
        return None


async def parse_deadline_to_datetime(deadline_text: str) -> Optional[str]:
    """
    Перетворює текстовий опис дедлайну на формат ISO 8601.

    Використовує Gemini для розуміння природного тексту дат.

    Args:
        deadline_text: Текстовий опис (наприклад, "завтра", "в п'ятницю", "22 жовтня").

    Returns:
        Рядок у форматі ISO 8601 (YYYY-MM-DDTHH:MM:SS) або None.
    """
    from datetime import date
    today = date.today().isoformat()

    prompt = f"""Сьогодні: {today}.
Перетвори текст дедлайну на точну дату та час у форматі ISO 8601.

Текст дедлайну: "{deadline_text}"

Правила:
- Якщо вказано "завтра" — наступний день о 23:59
- Якщо вказано день тижня — наступна така дата о 23:59
- Якщо вказано конкретну дату — та дата о 23:59
- Якщо "не вказано" — поверни дату через 3 дні о 23:59

Поверни ТІЛЬКИ рядок у форматі: YYYY-MM-DDTHH:MM:SS
Без пояснень, без JSON, тільки рядок дати."""

    try:
        result = await _generate(prompt, _TEXT_CONFIG)
        # Базова валідація формату (шукаємо дату навіть якщо навколо є зайвий текст)
        match = re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", result)
        if match:
            return match.group()
        logger.warning(f"Gemini повернув некоректний формат дати: {result}")
        return None
    except Exception as e:
        logger.error(f"Помилка парсингу дедлайну '{deadline_text}': {e}")
        return None
