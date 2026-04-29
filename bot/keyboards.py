from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def mode_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Assistant Mode", callback_data="mode_assistant"),
            InlineKeyboardButton("Twin Mode", callback_data="mode_twin"),
        ]
    ])


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Switch Mode", callback_data="show_modes")],
        [
            InlineKeyboardButton("My Stats", callback_data="stats"),
            InlineKeyboardButton("Clear Chat", callback_data="clear_chat"),
        ],
    ])
