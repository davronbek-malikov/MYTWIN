import config
from telegram import Update
from telegram.ext import ContextTypes

from bot.keyboards import main_menu_keyboard, mode_keyboard
from core.brain import brain
from database.db import get_or_create_user, get_user_mode, set_user_mode, get_voice_enabled, set_voice_enabled
from tools.entry_tools import get_summary


async def _stats_text(telegram_id: int) -> str:
    db_user = await get_or_create_user(telegram_id)
    mode = await get_user_mode(telegram_id)
    history_len = brain.history_length(db_user["id"])
    summary = await get_summary(db_user["id"], period="all")

    if summary:
        lines = "\n".join(f"  - {s['category']}: {s['count']}" for s in summary)
    else:
        lines = "  No entries yet"

    return (
        f"*Twin Stats*\n\n"
        f"Mode: {mode.upper()}\n"
        f"Messages in memory: {history_len}\n\n"
        f"*Stored Entries:*\n{lines}"
    )


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await get_or_create_user(user.id, user.username, user.first_name)
    mode = await get_user_mode(user.id)
    voice_on = await get_voice_enabled(user.id)

    await update.message.reply_text(
        f"Hi! I'm *{config.OWNER_NAME}'s AI Twin*.\n\n"
        f"Current mode: *{mode.upper()}*\n\n"
        f"*Assistant Mode* — I respond to your requests, track anything you share, answer questions.\n"
        f"*Twin Mode* — I act autonomously on your behalf.\n\n"
        f"Send me text, a voice message, or an image — I'll handle the rest.",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(voice_on),
    )


async def voice_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    current = await get_voice_enabled(user.id)
    new_state = not current
    await set_voice_enabled(user.id, new_state)
    status = "ON 🔊" if new_state else "OFF 🔇"
    await update.message.reply_text(
        f"Voice replies: *{status}*\n\n"
        f"{'I will now speak my responses back to you.' if new_state else 'Text-only mode.'}",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(new_state),
    )


async def mode_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Choose your mode:", reply_markup=mode_keyboard())


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db_user = await get_or_create_user(update.effective_user.id)
    brain.clear_history(db_user["id"])
    await update.message.reply_text("Conversation cleared. Fresh start.")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = await _stats_text(update.effective_user.id)
    await update.message.reply_text(text, parse_mode="Markdown")


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    data = query.data

    if data == "mode_assistant":
        await set_user_mode(user.id, "assistant")
        db_user = await get_or_create_user(user.id)
        brain.clear_history(db_user["id"])
        await query.edit_message_text(
            "Switched to *Assistant Mode*. How can I help?", parse_mode="Markdown"
        )

    elif data == "mode_twin":
        await set_user_mode(user.id, "twin")
        db_user = await get_or_create_user(user.id)
        brain.clear_history(db_user["id"])
        await query.edit_message_text(
            "*Twin Mode Activated.*\n\nI am operating autonomously on your behalf. "
            "Give me a task or situation to handle.",
            parse_mode="Markdown",
        )

    elif data == "show_modes":
        await query.edit_message_text("Choose your mode:", reply_markup=mode_keyboard())

    elif data == "stats":
        text = await _stats_text(user.id)
        await query.edit_message_text(text, parse_mode="Markdown")

    elif data == "clear_chat":
        db_user = await get_or_create_user(user.id)
        brain.clear_history(db_user["id"])
        await query.edit_message_text("Conversation cleared. Fresh start.")

    elif data == "toggle_voice":
        current = await get_voice_enabled(user.id)
        new_state = not current
        await set_voice_enabled(user.id, new_state)
        status = "ON 🔊" if new_state else "OFF 🔇"
        await query.edit_message_text(
            f"Voice replies: *{status}*\n\n"
            f"{'I will now speak my responses back to you.' if new_state else 'Text-only mode.'}",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(new_state),
        )
