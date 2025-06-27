from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.filters.state import StateFilter  # импорт фильтра состояния
from database.db import ReviewDB

from routers.states import ReviewStates  # импорт состояний из общего модуля

review_router = Router()
review_db = ReviewDB()

@review_router.message(Command("review"))
async def cmd_review(message: Message, state: FSMContext):
    await message.answer("Пожалуйста, оставьте ваш отзыв в свободной форме.")
    await state.set_state(ReviewStates.waiting_for_review)

@review_router.message(StateFilter(ReviewStates.waiting_for_review))
async def process_review(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username
    review_text = message.text

    review_id = review_db.add_review(user_id, username, review_text)
    await message.answer("Спасибо за ваш отзыв! Он будет рассмотрен.")
    await state.clear()
