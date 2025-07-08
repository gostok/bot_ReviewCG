import re
import logging
from aiogram import Router, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from database.db import ReviewDB
from config.create_bot import bot, ADMIN, ADMINISTRATOR, ADMINISTRATOR2

from routers.review_router.review_keyboards import get_start_review_kb
from routers.states import ReviewStates, AdminAnswer

start_router = Router()
review_db = ReviewDB()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def is_admin(user_id: int) -> bool:
    """
    Проверяет, является ли пользователь администратором.
    """
    return user_id in {int(ADMINISTRATOR), int(ADMIN), int(ADMINISTRATOR2)}


def reorder_review_text(review_text: str) -> str:
    """
    Разделяет review_text на отзыв и источник, меняет их местами для вывода.

    Ожидается формат:
    <текст отзыва>

    Откуда узнал(а): <текст источника>
    """
    parts = review_text.split("\n\nОткуда узнал(а): ")
    if len(parts) == 2:
        free_review, source = parts
        return f"Откуда узнали:\n{source}\n\nОтзыв:\n{free_review}"
    else:
        # Если формат не совпадает, возвращаем как есть
        return review_text


@start_router.message(Command('reviews'))
async def cmd_reviews(message: types.Message):
    """
    Обрабатывает команду /reviews — выводит список необработанных отзывов администратору.
    """
    user_id = message.from_user.id
    logger.info(f"Пользователь {user_id} вызвал /reviews")
    if not is_admin(user_id):
        await message.answer("Команда доступна только администратору.")
        logger.warning(f"Доступ запрещён пользователю {user_id} к /reviews")
        return

    reviews = review_db.get_unanswered_reviews()
    if not reviews:
        await message.answer("Нет новых отзывов.")
        logger.info("Нет новых отзывов для отображения")
        return

    for review_id, user_id_r, username, review_text in reviews:
        formatted_text = reorder_review_text(review_text)
        text = f"Отзыв #{review_id} от @{username or 'неизвестно'} (id: {user_id_r}):\n\n{formatted_text}"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Ответить", callback_data=f"answer_{review_id}_{user_id_r}")]
        ])
        await message.answer(text, reply_markup=kb)
    logger.info(f"Отправлены отзывы пользователю {user_id}")


@start_router.callback_query(lambda c: c.data and c.data.startswith("answer_"))
async def callback_answer_review(callback: CallbackQuery, state: FSMContext):
    """
    Обрабатывает нажатие кнопки "Ответить" на отзыве — переводит в состояние ожидания ответа.
    """
    user = callback.from_user.id
    logger.info(f"Пользователь {user} нажал кнопку ответить на отзыве")
    if not is_admin(user):
        await callback.answer("Доступ запрещён.", show_alert=True)
        logger.warning(f"Доступ запрещён пользователю {user} к ответу на отзыв")
        return

    try:
        _, review_id_str, user_id_str = callback.data.split("_", 2)
        review_id = int(review_id_str)
        user_id_r = int(user_id_str)
    except Exception as e:
        logger.error(f"Ошибка парсинга callback data: {callback.data} - {e}")
        await callback.answer("Ошибка данных.", show_alert=True)
        return

    await state.update_data(review_id=review_id, user_id=user_id_r)
    await callback.message.answer(f"Введите ответ на отзыв #{review_id}:")
    await state.set_state(AdminAnswer.waiting_for_answer)
    await callback.answer()
    logger.info(f"Переведён в состояние ожидания ответа на отзыв #{review_id} пользователем {user}")


@start_router.message(AdminAnswer.waiting_for_answer)
async def process_admin_answer(message: types.Message, state: FSMContext):
    """
    Обрабатывает ответ администратора на отзыв — отправляет пользователю и помечает отзыв отвеченным.
    """
    data = await state.get_data()
    review_id = data.get("review_id")
    user_id = data.get("user_id")
    answer_text = message.text

    logger.info(f"Администратор {message.from_user.id} отвечает на отзыв #{review_id} пользователю {user_id}")

    try:
        await bot.send_message(user_id, f"Администратор ответил на ваш отзыв:\n\n{answer_text}")
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения пользователю {user_id}: {e}")
        await message.answer(f"Не удалось отправить сообщение пользователю: {e}")
        await state.clear()
        return

    review_db.mark_review_answered(review_id, answer_text)
    await message.answer("Ответ отправлен и отзыв помечен как отвеченный.")
    await state.clear()
    logger.info(f"Отзыв #{review_id} помечен как отвеченный")


def parse_review_text(text: str) -> dict:
    """
    Парсит отзыв из формата:

    Отзыв: <текст отзыва>

    Откуда узнал(а): <источник>
    Темы выставок, которые хотел(а) бы видеть: <темы>

    Возвращает dict с ключами 'review', 'source', 'subject'.
    """
    review = ""
    source = ""
    subject = ""

    # Разобьём на строки и найдём ключевые строки
    lines = text.splitlines()
    # Собираем свободный отзыв — все строки до первой строки, начинающейся с "Откуда узнал(а):"
    review_lines = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("Откуда узнал(а):"):
            break
        review_lines.append(line)
        i += 1
    review = "\n".join(review_lines).strip()

    # Теперь ищем источник
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("Откуда узнал(а):"):
            source = line[len("Откуда узнал(а):"):].strip()
            i += 1
            break
        i += 1

    # Теперь ищем темы выставок
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("Темы выставок, которые хотел(а) бы видеть:"):
            subject = line[len("Темы выставок, которые хотел(а) бы видеть:"):].strip()
            break
        i += 1

    return {
        "review": review,
        "source": source,
        "subject": subject,
    }


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
        for review_id, user_id_r, username, review_text in unanswered:
            parts = parse_review_text(review_text)
            text = (
                f"Отзыв #{review_id} от @{username or 'неизвестно'} (id: {user_id_r}):\n\n"
                f"📢 *Откуда узнали:*\n{parts['source'] or '_не указано_'}\n\n"
                f"📝 *Отзыв:*\n{parts['review'] or '_пустой_'}\n\n"
                f"🎨 *Темы выставок, которые хотел(а) бы видеть:*\n{parts['subject'] or '_не указано_'}"
            )
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Ответить", callback_data=f"answer_{review_id}_{user_id_r}")]
            ])
            await message.answer(text, parse_mode="Markdown", reply_markup=kb)
    else:
        await message.answer("Нет необработанных отзывов.")

    if answered:
        await message.answer("✅ *Обработанные отзывы:*", parse_mode="Markdown")
        for review_id, user_id_r, username, review_text, admin_answer in answered:
            parts = parse_review_text(review_text)
            text = (
                f"Отзыв #{review_id} от @{username or 'неизвестно'} (id: {user_id_r}):\n\n"
                f"📢 *Откуда узнали:*\n{parts['source'] or '_не указано_'}\n\n"
                f"📝 *Отзыв:*\n{parts['review'] or '_пустой_'}\n\n"
                f"🎨 *Темы выставок, которые хотел(а) бы видеть:*\n{parts['subject'] or '_не указано_'}\n\n"
                f"💬 *Ответ администратора:*\n{admin_answer}"
            )
            await message.answer(text, parse_mode="Markdown")
    else:
        await message.answer("Нет обработанных отзывов.")



@start_router.message(Command(commands=["answer"]))
async def cmd_answer_review(message: types.Message, state: FSMContext):
    """
    Обрабатывает команду /answer <id> — переводит администратора в состояние ввода ответа на конкретный отзыв.
    """
    user_id = message.from_user.id
    logger.info(f"Пользователь {user_id} вызвал /answer")
    if not is_admin(user_id):
        await message.answer("Команда доступна только администратору.")
        logger.warning(f"Доступ запрещён пользователю {user_id} к /answer")
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
        logger.warning(f"Отзыв с ID {review_id} не найден")
        return
    review_user_id, answered = row
    if answered:
        await message.answer(f"Отзыв #{review_id} уже обработан.")
        logger.info(f"Отзыв #{review_id} уже обработан")
        return

    await state.update_data(review_id=review_id, user_id=review_user_id)
    await message.answer(f"Введите ответ на отзыв #{review_id}:")
    await state.set_state(AdminAnswer.waiting_for_answer)
    logger.info(f"Перевод администратора {user_id} в состояние ожидания ответа на отзыв #{review_id}")


@start_router.message(Command('statistic'))
async def cmd_statistics(message: types.Message):
    """
    Обрабатывает команду /statistic — выводит статистику: сколько пользователей и сколько отзывов.
    """
    user_id = message.from_user.id
    logger.info(f"Пользователь {user_id} вызвал /statistic")
    if not is_admin(user_id):
        await message.answer("Команда доступна только администратору.")
        logger.warning(f"Доступ запрещён пользователю {user_id} к /statistic")
        return

    user_count = review_db.count_users()
    review_count = review_db.count_reviews()

    text = (
        f"📊 *Статистика бота:*\n\n"
        f"👥 Пользователей, воспользовавшихся ботом: {user_count}\n"
        f"📝 Отзывов отправлено: {review_count}"
    )
    await message.answer(text, parse_mode="Markdown")
    logger.info(f"Отправлена статистика пользователю {user_id}")


@start_router.message(Command(commands=["admin"]))
async def cmd_admin(message: types.Message):
    """
    Обрабатывает команду /admin — выводит список админ-команд.
    """
    user_id = message.from_user.id
    logger.info(f"Пользователь {user_id} вызвал /admin")
    if not is_admin(user_id):
        await message.answer("Команда доступна только администратору.")
        logger.warning(f"Доступ запрещён пользователю {user_id} к /admin")
        return

    await message.answer("📋 *Админ команды:*\n\n\
        '/reviews' - просмотр не обработанных отзывов;\n\
        '/all_reviews' - просмотр всех отзывов обработанных (с ответами от админа) и не обработанных;\n\
        '/answer &lt;id&gt;' - ответить на отзыв с определенным id;\n\
        '/statistic' - показать статистику использования бота.", parse_mode="HTML")


async def send_admin_new_review_notification(
        review_id: int,
        user_id_ms: int,
        username: str | None,
        free_review: str,
        source: str,
        subject: str,
        admin_id: int
    ):
    """
    Отправляет уведомление администратору о новом отзыве с кнопкой "Ответить".

    :param review_id: ID отзыва
    :param user_id_ms: ID пользователя, оставившего отзыв
    :param username: Имя пользователя
    :param free_review: Текст отзыва
    :param source: Источник информации
    :param admin_id: ID администратора для отправки сообщения
    """
    text = (
        f"Новый отзыв #{review_id} от @{username or 'неизвестно'}:\n\n"
        f"📢 Вопрос 1: Откуда вы узнали о выставке?\n"
        f"Ответ: {source}\n\n"
        f"📝 Вопрос 2: В свободной форме расскажите, как вам выставка? Какие произведения понравились больше всего?\n"
        f"Ответ: {free_review}\n\n"
        f"🎨 Вопрос 3: Темы выставок, которые хотел(а) бы видеть:\n"
        f"Ответ: {subject}"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Ответить",
                callback_data=f"answer_{review_id}_{user_id_ms}"
            )
        ]
    ])
    try:
        await bot.send_message(admin_id, text, reply_markup=keyboard)
        logger.info(f"Отправлено уведомление админу {admin_id} о отзыве #{review_id}")
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления админу {admin_id}: {e}")

