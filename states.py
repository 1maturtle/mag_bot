# ======================================
# states.py — FSM стани для Aiogram
# ======================================

from aiogram.fsm.state import State, StatesGroup


class AddTaskStates(StatesGroup):
    """Стани для покрокового додавання завдання вручну (текстом)."""
    waiting_for_subject = State()      # Очікування назви предмета
    waiting_for_description = State()  # Очікування опису завдання
    waiting_for_deadline = State()     # Очікування дати дедлайну


class VoiceTaskStates(StatesGroup):
    """Стани для обробки голосового повідомлення з завданням."""
    waiting_for_voice = State()         # Очікування голосового повідомлення
    confirming_parsed_task = State()    # Підтвердження розпізнаних даних


class QuizStates(StatesGroup):
    """Стани для проходження тесту з ШІ."""
    selecting_task = State()            # Вибір завдання для тесту
    answering_question = State()        # Відповідь на питання тесту
    viewing_feedback = State()          # Перегляд фідбеку після тесту
