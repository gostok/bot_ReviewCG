from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from database.db import ReviewDB
from config.create_bot import bot, ADMIN
from routers.states import ReviewStates
from routers.review_router.review_keyboards import get_source_kb

review_router = Router()
review_db = ReviewDB()

@review_router.message(Command("start"))
async def start_survey(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Спасибо, что посетили выставку современного искусства «Зачем родился?» в Сити-парке «Град»! "
        "Будем признательны, если вы поделитесь впечатлениями о событии и ответите на несколько вопросов. "
        "Это займёт пару минут."
    )
    await message.answer("В свободной форме расскажите, как вам выставка? Какие произведения понравились больше всего?")
    await state.set_state(ReviewStates.waiting_for_free_review)

@review_router.message(ReviewStates.waiting_for_free_review)
async def process_free_review(message: types.Message, state: FSMContext):
    await state.update_data(free_review=message.text)
    await message.answer("Откуда вы узнали о выставке?", reply_markup=get_source_kb())
    await state.set_state(ReviewStates.waiting_for_source_choice)

@review_router.callback_query(lambda c: c.data and c.data.startswith("source_"))
async def process_source_choice(callback: CallbackQuery, state: FSMContext):
    source_option = callback.data.split("_")[1]
    user_id = callback.from_user.id
    username = callback.from_user.username

    if source_option == "5":
        await callback.message.answer("Пожалуйста, напишите, откуда вы узнали о выставке:")
        await state.set_state(ReviewStates.waiting_for_custom_source)
    else:
        sources = {
            "1": "Увидел(а)/услышал(а) информацию в Граде",
            "2": "В соцсетях Града (Telegram, ВК и др.)",
            "3": "В сторонних каналах и СМИ",
            "4": "Через афишный сервис"
        }
        source_text = sources.get(source_option, "Неизвестно")
        await state.update_data(source=source_text)
        await finish_survey(callback.message, state, user_id, username)
    await callback.answer()

@review_router.message(ReviewStates.waiting_for_custom_source)
async def process_custom_source(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username

    await state.update_data(source=message.text)
    await finish_survey(message, state, user_id, username)


async def finish_survey(message: types.Message, state: FSMContext, user_id: int, username: str | None):
    data = await state.get_data()
    free_review = data.get("free_review", "")
    source = data.get("source", "")

    full_review = f"Отзыв: {free_review}\n\nОткуда узнал(а): {source}"
    review_id = review_db.add_review(user_id, username, full_review)

    await message.answer(
        "Спасибо за обратную связь! Мы очень ценим мнение каждого посетителя ❤️\n"
        "Ваш отзыв поможет нам стать лучше."
    )

    from ..start_router.start_r import send_admin_new_review_notification
    await send_admin_new_review_notification(review_id, user_id, username, free_review, source)

    await state.clear()
