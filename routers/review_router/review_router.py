import logging
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile

from database.db import ReviewDB
from config.create_bot import bot, ADMIN, ADMINISTRATOR, ADMINISTRATOR2
from routers.states import ReviewStates
from routers.review_router.review_keyboards import get_source_kb

import os
import asyncio

review_router = Router()
review_db = ReviewDB()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ADMINS = [int(ADMIN), int(ADMINISTRATOR), int(ADMINISTRATOR2)]


@review_router.message(Command("start"))
async def start_survey(message: types.Message, state: FSMContext, bot: bot):
    """
    Начинает опрос, отправляет приветственное фото и спрашивает источник информации.
    """
    logger.info(f"Пользователь {message.from_user.id} начал опрос")
    await state.clear()

    caption_text = (
        "Спасибо, что посетили выставку современного искусства «Зачем родился?» в Сити-парке «Град»! "
        "Будем признательны, если вы поделитесь впечатлениями о событии и ответите на несколько вопросов. "
        "Это займёт пару минут."
    )

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    photo_path = os.path.join(base_dir, 'database', 'photo.jpg')

    if not os.path.exists(photo_path):
        logger.error(f"Фото не найдено по пути {photo_path}")
        await message.answer("Извините, изображение временно недоступно.")
        return

    photo = FSInputFile(path=photo_path)

    try:
        await bot.send_photo(chat_id=message.chat.id, photo=photo, caption=caption_text)
        await asyncio.sleep(1.5)
        await message.answer("Откуда вы узнали о выставке?", reply_markup=get_source_kb())
        await state.set_state(ReviewStates.waiting_for_source_choice)
        logger.info(f"Отправлено приветственное сообщение пользователю {message.from_user.id}")
    except Exception as e:
        logger.error(f"Ошибка отправки приветственного сообщения: {e}")
        await message.answer("Произошла ошибка при отправке сообщения.")


@review_router.callback_query(lambda c: c.data and c.data.startswith("source_"))
async def process_source_choice(callback: CallbackQuery, state: FSMContext):
    """
    Обрабатывает выбор источника информации о выставке.
    """
    user_id = callback.from_user.id
    source_option = callback.data.split("_")[1]
    logger.info(f"Пользователь {user_id} выбрал источник {source_option}")

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
        await callback.message.answer(
            "В свободной форме расскажите, как вам выставка? Какие произведения понравились больше всего?"
        )
        await state.set_state(ReviewStates.waiting_for_free_review)
    await callback.answer()


@review_router.message(ReviewStates.waiting_for_custom_source)
async def process_custom_source(message: types.Message, state: FSMContext):
    """
    Обрабатывает ввод собственного источника информации.
    """
    user_id = message.from_user.id
    logger.info(f"Пользователь {user_id} ввёл собственный источник: {message.text}")
    await state.update_data(source=message.text)
    await message.answer(
        "В свободной форме расскажите, как вам выставка? Какие произведения понравились больше всего?"
    )
    await state.set_state(ReviewStates.waiting_for_free_review)


@review_router.message(ReviewStates.waiting_for_free_review)
async def process_free_review(message: types.Message, state: FSMContext):
    """
    Обрабатывает свободный отзыв пользователя и завершает опрос.
    """
    user_id = message.from_user.id
    logger.info(f"Пользователь {user_id} оставил отзыв")
    await state.update_data(free_review=message.text)

    await finish_survey(message, state, user_id, message.from_user.username)


async def finish_survey(message: types.Message, state: FSMContext, user_id: int, username: str | None):
    """
    Сохраняет отзыв в базу, благодарит пользователя и уведомляет администраторов.
    """
    logger.info(f"Завершение опроса пользователя {user_id}")
    data = await state.get_data()
    free_review = data.get("free_review", "")
    source = data.get("source", "")

    full_review = f"Отзыв: {free_review}\n\nОткуда узнал(а): {source}"
    review_id = review_db.add_review(user_id, username, full_review)

    await message.answer(
        "Спасибо за обратную связь! Мы очень ценим мнение каждого посетителя ❤️\n"
        "Ваш отзыв поможет нам стать лучше."
    )
    logger.info(f"Сохранён отзыв #{review_id} пользователя {user_id}")

    from ..start_router.start_r import send_admin_new_review_notification

    for admin_id in ADMINS:
        try:
            await send_admin_new_review_notification(review_id, user_id, username, free_review, source, int(admin_id))
        except Exception as e:
            logger.error(f"Ошибка уведомления админа {admin_id}: {e}")

    await state.clear()
    logger.info(f"Состояние пользователя {user_id} очищено после завершения опроса")
