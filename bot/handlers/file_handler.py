"""
Handles any document/file sent to the bot:
- Images sent as files (screenshots) → routed to vision
- Text files (.txt, .csv) → content extracted and sent to brain
- PDFs → first page text extracted
- Excel/CSV → rows read and sent to brain
- Everything else → ask AI to process with the filename as context
"""
import io

from telegram import Update
from telegram.ext import ContextTypes

from core.brain import brain
from database.db import get_or_create_user, get_user_mode
from utils.dedup import is_duplicate
from utils.logger import logger

_IMAGE_MIME = {"image/jpeg", "image/png", "image/gif", "image/webp", "image/bmp"}


async def file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    doc = update.message.document

    # Dedup: same file sent twice
    if doc and is_duplicate(user.id, doc.file_unique_id):
        await update.message.reply_text("⚠️ Already processed this file — ignored.")
        return

    db_user = await get_or_create_user(user.id, user.username, user.first_name)
    mode = await get_user_mode(user.id)
    caption = update.message.caption or ""

    thinking = await update.message.reply_text("📎 Processing file...")

    try:
        mime = (doc.mime_type or "").lower()
        fname = doc.file_name or "file"

        tg_file = await context.bot.get_file(doc.file_id)
        buf = io.BytesIO()
        await tg_file.download_to_memory(buf)
        raw = buf.getvalue()

        # ── Image file → vision ───────────────────────────────────────
        if mime in _IMAGE_MIME:
            prompt = (
                f"{caption}\n\n"
                "IMPORTANT: Look carefully at this receipt/screenshot. "
                "Find the transaction DATE printed on it (e.g. 2026-05-06, 06/05, May 6). "
                "Use THAT date in data['date'] when saving — NOT today's date. "
                "If no date is visible, use today. "
                "Extract every item and amount and save each as a separate entry."
            ).strip()
            response = await brain.think(db_user["id"], prompt, mode, image_data=raw, image_mime=mime)
            await thinking.edit_text(response)
            return

        # ── Plain text / CSV ──────────────────────────────────────────
        if mime in ("text/plain", "text/csv") or fname.endswith((".txt", ".csv")):
            text_content = raw.decode("utf-8", errors="ignore")[:4000]
            prompt = (
                f"{caption}\n\nFile content ({fname}):\n{text_content}"
                if caption else
                f"The user sent a file ({fname}). Parse any financial transactions from it and save them:\n\n{text_content}"
            )
            response = await brain.think(db_user["id"], prompt, mode)
            await thinking.edit_text(response)
            return

        # ── PDF ───────────────────────────────────────────────────────
        if mime == "application/pdf" or fname.endswith(".pdf"):
            try:
                import pypdf
                reader = pypdf.PdfReader(io.BytesIO(raw))
                text_content = "\n".join(
                    page.extract_text() for page in reader.pages[:3] if page.extract_text()
                )[:4000]
                prompt = (
                    f"{caption}\n\nPDF content ({fname}):\n{text_content}"
                    if caption else
                    f"The user sent a PDF ({fname}). Extract any financial data and save it:\n\n{text_content}"
                )
            except ImportError:
                prompt = f"User sent a PDF file named '{fname}'. {caption}"
            response = await brain.think(db_user["id"], prompt, mode)
            await thinking.edit_text(response)
            return

        # ── Excel ─────────────────────────────────────────────────────
        if mime in ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    "application/vnd.ms-excel") or fname.endswith((".xlsx", ".xls")):
            try:
                import openpyxl
                wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
                ws = wb.active
                rows = []
                for i, row in enumerate(ws.iter_rows(values_only=True)):
                    if i > 50:
                        break
                    rows.append(" | ".join(str(c) for c in row if c is not None))
                text_content = "\n".join(rows)[:4000]
                prompt = (
                    f"{caption}\n\nExcel file ({fname}):\n{text_content}"
                    if caption else
                    f"The user sent an Excel file ({fname}). Extract and save any financial data:\n\n{text_content}"
                )
            except ImportError:
                prompt = f"User sent an Excel file named '{fname}'. {caption}"
            response = await brain.think(db_user["id"], prompt, mode)
            await thinking.edit_text(response)
            return

        # ── Unknown file type ─────────────────────────────────────────
        prompt = (
            f"{caption}\n\nUser sent a file: {fname} ({mime})"
            if caption else
            f"User sent a file: {fname} ({mime}). Acknowledge it and ask what they'd like to do with it."
        )
        response = await brain.think(db_user["id"], prompt, mode)
        await thinking.edit_text(response)

    except Exception as e:
        logger.error(f"File handler error user={user.id}: {e}")
        await thinking.edit_text(f"Could not process file: {e}")
