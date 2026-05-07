import io

from telegram import Update
from telegram.ext import ContextTypes

from core.brain import brain
from database.db import get_or_create_user, get_user_mode
from utils.dedup import is_duplicate
from utils.logger import logger

_SUPPORTED_MIME = {"image/jpeg", "image/png", "image/gif", "image/webp"}


async def image_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    db_user = await get_or_create_user(user.id, user.username, user.first_name)
    mode = await get_user_mode(user.id)

    # Dedup check using Telegram's file_unique_id
    file_id = (
        update.message.photo[-1].file_unique_id if update.message.photo
        else update.message.document.file_unique_id if update.message.document
        else None
    )
    if file_id and is_duplicate(user.id, file_id):
        await update.message.reply_text("⚠️ Already processed this image recently — ignored.")
        return

    thinking = await update.message.reply_text("Analyzing image...")

    try:
        if update.message.photo:
            photo = update.message.photo[-1]
            mime_type = "image/jpeg"
        elif update.message.document:
            doc = update.message.document
            mime_type = doc.mime_type or "image/jpeg"
            if mime_type not in _SUPPORTED_MIME:
                await thinking.edit_text(
                    f"Unsupported file type: {mime_type}. Send a JPEG, PNG, GIF, or WebP."
                )
                return
            photo = doc
        else:
            await thinking.edit_text("No image found in message.")
            return

        tg_file = await context.bot.get_file(photo.file_id)
        buf = io.BytesIO()
        await tg_file.download_to_memory(buf)
        image_data = buf.getvalue()

        caption = update.message.caption or ""
        response = await brain.think(
            db_user["id"], caption, mode,
            image_data=image_data, image_mime=mime_type,
        )
        await thinking.edit_text(response)

    except Exception as e:
        logger.error(f"Image handler error user={user.id}: {e}")
        await thinking.edit_text(f"Could not process image: {e}")
