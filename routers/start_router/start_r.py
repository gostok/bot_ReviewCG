from aiogram import Router, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from database.db import ReviewDB
from config.create_bot import bot, ADMIN

from routers.review_router.review_keyboards import get_start_review_kb
from routers.states import ReviewStates, AdminAnswer  # импорт состояний из общего модуля


start_router = Router()
review_db = ReviewDB()


def is_admin(user_id: int) -> bool:
    return user_id == int(ADMIN)


@start_router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Добро пожаловать! Нажмите кнопку ниже, чтобы оставить отзыв.",
        reply_markup=get_start_review_kb()
    )


@start_router.callback_query(lambda c: c.data == "start_review")
async def callback_start_review(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Пожалуйста, напишите ваш отзыв.")
    await state.set_state(ReviewStates.waiting_for_review)  
    await callback.answer()


@start_router.message(Command('reviews'))
async def cmd_reviews(message: types.Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer("Команда доступна только администратору.")
        return

    reviews = review_db.get_unanswered_reviews()
    if not reviews:
        await message.answer("Нет новых отзывов.")
        return

    for review_id, user_id, username, review_text in reviews:
        text = f"Отзыв #{review_id} от @{username or 'неизвестно'} (id: {user_id}):\n\n{review_text}"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Ответить", callback_data=f"answer_{review_id}_{user_id}")]
        ])
        await message.answer(text, reply_markup=kb)


@start_router.callback_query(lambda c: c.data and c.data.startswith("answer_"))
async def callback_answer_review(callback: CallbackQuery, state: FSMContext):
    user = callback.from_user.id
    if not is_admin(user):
        await callback.answer("Доступ запрещён.", show_alert=True)
        return

    _, review_id_str, user_id_str = callback.data.split("_", 2)
    review_id = int(review_id_str)
    user_id = int(user_id_str)

    await state.update_data(review_id=review_id, user_id=user_id)
    await callback.message.answer(f"Введите ответ на отзыв #{review_id}:")
    await state.set_state(AdminAnswer.waiting_for_answer)
    await callback.answer()


@start_router.message(AdminAnswer.waiting_for_answer)
async def process_admin_answer(message: types.Message, state: FSMContext):
    data = await state.get_data()
    review_id = data.get("review_id")
    user_id = data.get("user_id")
    answer_text = message.text

    try:
        await bot.send_message(user_id, f"Администратор ответил на ваш отзыв:\n\n{answer_text}")
    except Exception as e:
        await message.answer(f"Не удалось отправить сообщение пользователю: {e}")
        await state.clear()
        return

    review_db.mark_review_answered(review_id, answer_text)

    await message.answer("Ответ отправлен и отзыв помечен как отвеченный.")
    await state.clear()


@start_router.message(Command('all_reviews'))
async def cmd_all_reviews(message: types.Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer("Команда доступна только администратору.")
        return

    unanswered = review_db.get_unanswered_reviews()
    answered = review_db.get_answered_reviews()

    if not unanswered and not answered:
        await message.answer("Отзывов пока нет.")
        return

    if unanswered:
        await message.answer("📋 *Необработанные отзывы:*", parse_mode="Markdown")
        for review_id, user_id, username, review_text in unanswered:
            text = f"Отзыв #{review_id} от @{username or 'неизвестно'} (id: {user_id}):\n\n{review_text}"
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Ответить", callback_data=f"answer_{review_id}_{user_id}")]
            ])
            await message.answer(text, reply_markup=kb)
    else:
        await message.answer("Нет необработанных отзывов.")

    if answered:
        await message.answer("✅ *Обработанные отзывы:*", parse_mode="Markdown")
        for review_id, user_id, username, review_text, admin_answer in answered:
            text = (f"Отзыв #{review_id} от @{username or 'неизвестно'} (id: {user_id}):\n\n"
                    f"{review_text}\n\n"
                    f"💬 *Ответ администратора:*\n{admin_answer}")
            await message.answer(text, parse_mode="Markdown")
    else:
        await message.answer("Нет обработанных отзывов.")


@start_router.message(Command(commands=["answer"]))
async def cmd_answer_review(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer("Команда доступна только администратору.")
        return

    text = message.text or ""
    parts = text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("Пожалуйста, укажите ID отзыва. Пример: /answer 123")
        return

    review_id = int(parts[1])

    cursor = review_db.conn.execute(
        "SELECT user_id, answered FROM reviews WHERE id = ?", (review_id,)
    )
    row = cursor.fetchone()
    if not row:
        await message.answer(f"Отзыв с ID {review_id} не найден.")
        return
    review_user_id, answered = row
    if answered:
        await message.answer(f"Отзыв #{review_id} уже обработан.")
        return

    await state.update_data(review_id=review_id, user_id=review_user_id)
    await message.answer(f"Введите ответ на отзыв #{review_id}:")
    await state.set_state(AdminAnswer.waiting_for_answer)


@start_router.message(Command(commands=["admin"]))
async def cmd_admin(message: types.Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer("Команда доступна только администратору.")
        return
    
    await message.answer("📋 *Админ команды:*\n\n\
        '/reviews' - просмотр не обработанных отзывов;\n\
        '/all_reviews' - просмотр всех отзывов обработанных (с ответами от админа) и не обработанных;\n\
        '/answer &lt;id&gt;' - ответить на отзыв с определенным id.", parse_mode="HTML")
    
