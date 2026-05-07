import io
from io import BytesIO

from telegram import Update
from telegram.ext import ContextTypes

import config
from core.brain import brain
from database.db import get_or_create_user, get_user_mode, get_voice_enabled
from tools.tts_tools import text_to_speech
from utils.dedup import is_duplicate
from utils.logger import logger


async def voice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user

    if not config.OPENAI_API_KEY:
        await update.message.reply_text("OPENAI_API_KEY is missing from your .env file.")
        return

    # Dedup: prevent same voice file being processed twice
    voice = update.message.voice or update.message.audio
    if voice and is_duplicate(user.id, voice.file_unique_id):
        await update.message.reply_text("⚠️ Already processed this voice message — ignored.")
        return

    db_user = await get_or_create_user(user.id, user.username, user.first_name)
    mode = await get_user_mode(user.id)

    thinking = await update.message.reply_text("Listening...")

    try:
        voice = update.message.voice or update.message.audio
        tg_file = await context.bot.get_file(voice.file_id)

        buf = io.BytesIO()
        await tg_file.download_to_memory(buf)
        buf.seek(0)
        buf.name = "voice.ogg"

        from openai import AsyncOpenAI
        oai = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
        transcript = await oai.audio.transcriptions.create(model="whisper-1", file=buf)
        transcribed = transcript.text
        logger.info(f"Voice transcribed user={user.id}: {transcribed[:60]}")

        await thinking.edit_text(f'You said: "{transcribed}"\n\nThinking...')
        response = await brain.think(db_user["id"], transcribed, mode)
        await thinking.edit_text(response)

        # Always reply with voice when user sends a voice message
        audio = await text_to_speech(response)
        if audio:
            await update.message.reply_voice(voice=BytesIO(audio))

    except Exception as e:
        logger.error(f"Voice handler error user={user.id}: {e}")
        await thinking.edit_text(f"Could not process voice message: {e}")
