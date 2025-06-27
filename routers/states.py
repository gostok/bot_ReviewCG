from aiogram.fsm.state import State, StatesGroup

class ReviewStates(StatesGroup):
    waiting_for_review = State()

class AdminAnswer(StatesGroup):
    waiting_for_answer = State()
