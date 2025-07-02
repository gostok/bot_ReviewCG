from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def get_start_review_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Оставить отзыв", callback_data="start_review")]
    ])
    return kb


def get_source_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Увидел(а)/услышал(а) информацию в Граде", callback_data="source_1")],
        [InlineKeyboardButton(text="В соцсетях Града (Telegram, ВК и др.)", callback_data="source_2")],
        [InlineKeyboardButton(text="В сторонних каналах и СМИ", callback_data="source_3")],
        [InlineKeyboardButton(text="Через афишный сервис", callback_data="source_4")],
        [InlineKeyboardButton(text="Свой вариант", callback_data="source_5")]
    ])
    return kb
