from aiogram.fsm.state import State, StatesGroup

class ReviewStates(StatesGroup):
    waiting_for_free_review = State()
    waiting_for_source_choice = State()
    waiting_for_custom_source = State()

class AdminAnswer(StatesGroup):
    waiting_for_answer = State()
