from telegram import Update
from telegram.ext import ContextTypes

from core.brain import brain
from database.db import get_or_create_user, get_user_mode


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    text = update.message.text

    db_user = await get_or_create_user(user.id, user.username, user.first_name)
    mode = await get_user_mode(user.id)

    thinking = await update.message.reply_text("...")
    response = await brain.think(db_user["id"], text, mode)
    await thinking.edit_text(response)
