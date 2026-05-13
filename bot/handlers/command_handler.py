import config
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from agents.news_agent import fetch_topic as news_fetch_topic, fetch_all as news_fetch_all, TOPICS as NEWS_TOPICS
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


async def sheet_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    url = config.google_sheet_url()
    if url:
        await update.message.reply_text(
            f"📊 *Your Financial Sheet*\n\n[Open Google Sheet]({url})",
            parse_mode="Markdown",
            disable_web_page_preview=False,
        )
    else:
        await update.message.reply_text(
            "⚠️ Sheet ID not set. Add `GOOGLE_SHEET_ID=your_id` to your `.env` file.\n\n"
            "Find it in your sheet URL:\n`docs.google.com/spreadsheets/d/`*>>>ID<<<*`/edit`",
            parse_mode="Markdown",
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


def _news_keyboard() -> InlineKeyboardMarkup:
    """Build the topic-picker keyboard for /news."""
    topic_keys = [t["key"] for t in NEWS_TOPICS]
    rows = []
    # Pair up topics into rows of 2, then add "All Topics" as a final full-width row
    for i in range(0, len(topic_keys), 2):
        pair = topic_keys[i: i + 2]
        row = []
        for key in pair:
            topic = next(t for t in NEWS_TOPICS if t["key"] == key)
            row.append(InlineKeyboardButton(
                f"{topic['emoji']} {topic['name']}",
                callback_data=f"news__{key}",
            ))
        rows.append(row)
    rows.append([InlineKeyboardButton("🌐 All Topics", callback_data="news__all")])
    return InlineKeyboardMarkup(rows)


def _format_topic_result(result: dict) -> str:
    """Format a single topic result as Telegram Markdown."""
    emoji = result.get("emoji", "")
    name = result.get("name", result.get("key", ""))
    fetched = result.get("fetched_str", "")
    articles = result.get("articles", [])

    lines = [f"*{emoji} {name}*  _({fetched})_"]
    if not articles:
        lines.append("_No articles found._")
        return "\n".join(lines)

    for art in articles[:4]:
        title = art.get("title", "No title")
        url = art.get("url", "#")
        source = art.get("source", "Unknown")
        date = art.get("date", "")
        summary = art.get("summary", "")

        source_date = f"{source}"
        if date:
            source_date += f" · {date}"

        lines.append(
            f"\n[{title}]({url})\n"
            f"_{source_date}_\n"
            f"{summary}"
        )

    return "\n".join(lines)


async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "📰 *News Digest* — choose a topic:",
        parse_mode="Markdown",
        reply_markup=_news_keyboard(),
    )


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

    elif data.startswith("news__"):
        topic_key = data[len("news__"):]
        await query.edit_message_text("⏳ Fetching news, please wait…", parse_mode="Markdown")

        if topic_key == "all":
            results = await news_fetch_all()
            first = True
            for result in results:
                text = _format_topic_result(result)
                if first:
                    await query.edit_message_text(text, parse_mode="Markdown", disable_web_page_preview=True)
                    first = False
                else:
                    await query.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)
        else:
            result = await news_fetch_topic(topic_key)
            text = _format_topic_result(result)
            await query.edit_message_text(text, parse_mode="Markdown", disable_web_page_preview=True)
