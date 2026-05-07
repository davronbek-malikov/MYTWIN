import config
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def mode_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Assistant Mode", callback_data="mode_assistant"),
            InlineKeyboardButton("Twin Mode", callback_data="mode_twin"),
        ]
    ])


def main_menu_keyboard(voice_on: bool = False) -> InlineKeyboardMarkup:
    voice_label = "🔊 Voice: ON" if voice_on else "🔇 Voice: OFF"
    rows = [
        [InlineKeyboardButton("Switch Mode", callback_data="show_modes")],
        [
            InlineKeyboardButton("My Stats", callback_data="stats"),
            InlineKeyboardButton("Clear Chat", callback_data="clear_chat"),
        ],
        [InlineKeyboardButton(voice_label, callback_data="toggle_voice")],
    ]
    sheet_url = config.google_sheet_url()
    if sheet_url:
        rows.append([InlineKeyboardButton("📊 Open Google Sheet", url=sheet_url)])
    return InlineKeyboardMarkup(rows)
