from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

import config
from bot.handlers.command_handler import (
    callback_handler,
    clear_command,
    mode_command,
    start_command,
    stats_command,
)
from bot.handlers.image_handler import image_handler
from bot.handlers.text_handler import text_handler
from bot.handlers.voice_handler import voice_handler
from database.db import init_db
from utils.logger import logger


async def _post_init(application: Application) -> None:
    await init_db()
    logger.info("Database ready. Bot is live.")


def create_and_run_bot() -> None:
    if not config.TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN is missing from .env")
    if not config.OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is missing from .env")

    app = (
        Application.builder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .post_init(_post_init)
        .build()
    )

    # Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("mode", mode_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(CommandHandler("stats", stats_command))

    # Messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, voice_handler))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, image_handler))

    # Inline button callbacks
    app.add_handler(CallbackQueryHandler(callback_handler))

    logger.info("Bot polling started.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)
