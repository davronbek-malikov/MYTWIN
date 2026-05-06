from io import BytesIO
from telegram import Update
from telegram.ext import ContextTypes

from core.brain import brain
from database.db import get_or_create_user, get_user_mode, get_voice_enabled
from tools.tts_tools import text_to_speech


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    text = update.message.text

    db_user = await get_or_create_user(user.id, user.username, user.first_name)
    mode = await get_user_mode(user.id)

    thinking = await update.message.reply_text("...")
    response = await brain.think(db_user["id"], text, mode)
    await thinking.edit_text(response)

    if await get_voice_enabled(user.id):
        audio = await text_to_speech(response)
        if audio:
            await update.message.reply_voice(voice=BytesIO(audio))
