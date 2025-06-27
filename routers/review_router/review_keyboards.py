from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

def get_start_review_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Оставить отзыв", callback_data="start_review")]
    ])
    return kb
