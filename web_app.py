"""
My Twin — Web UI
Run with: python web_app.py
Then open: http://localhost:8000
"""
import io
import os
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

import config
from core.brain import brain
from database.db import (
    init_db, get_or_create_user, get_user_mode, set_user_mode
)
from tools.entry_tools import get_summary, query_entries
from utils.logger import logger

_WEB_TELEGRAM_ID = 0
_web_user_id: int | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _web_user_id
    try:
        await init_db()
        if not os.getenv("VERCEL"):
            db_user = await get_or_create_user(
                _WEB_TELEGRAM_ID, "web", config.OWNER_NAME
            )
            _web_user_id = db_user["id"]
    except Exception as e:
        logger.error(f"Startup DB error (non-fatal): {e}")
    yield


app = FastAPI(lifespan=lifespan)
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    mode = await get_user_mode(_WEB_TELEGRAM_ID)
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "owner": config.OWNER_NAME,
            "mode": mode,
            "sheet_url": config.google_sheet_url(),
        },
    )


class ChatMsg(BaseModel):
    message: str
    mode: str = "assistant"


@app.post("/api/chat")
async def chat(msg: ChatMsg):
    response = await brain.think(_web_user_id, msg.message, msg.mode)
    await set_user_mode(_WEB_TELEGRAM_ID, msg.mode)
    return {"response": response}


@app.get("/api/stats")
async def stats():
    summary = await get_summary(_web_user_id, period="all")
    mode = await get_user_mode(_WEB_TELEGRAM_ID)
    return {
        "mode": mode,
        "history_length": brain.history_length(_web_user_id),
        "entries": summary,
    }


@app.get("/api/entries")
async def entries(limit: int = 8):
    data = await query_entries(_web_user_id, limit=limit)
    return data


@app.post("/api/mode/{mode}")
async def change_mode(mode: str):
    await set_user_mode(_WEB_TELEGRAM_ID, mode)
    brain.clear_history(_web_user_id)
    return {"mode": mode}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/clear")
async def clear_chat():
    brain.clear_history(_web_user_id)
    return {"status": "cleared"}


class TTSRequest(BaseModel):
    text: str

@app.post("/api/tts")
async def tts(req: TTSRequest):
    from tools.tts_tools import text_to_speech
    audio = await text_to_speech(req.text, fmt="mp3")
    if audio:
        return Response(content=audio, media_type="audio/mpeg")
    return JSONResponse({"error": "TTS failed"}, status_code=500)


@app.post("/api/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
    audio_bytes = await audio.read()
    buf = io.BytesIO(audio_bytes)
    buf.name = audio.filename or "audio.webm"
    try:
        result = await client.audio.transcriptions.create(
            model="whisper-1", file=buf
        )
        return {"transcript": result.text.strip()}
    except Exception as e:
        return {"transcript": "", "error": str(e)}


# ── Telegram webhook (used in production on Vercel) ───────────────────────
_tg_app = None

async def _get_tg_app():
    global _tg_app
    if _tg_app:
        return _tg_app
    from telegram import Update
    from telegram.ext import Application, MessageHandler, CommandHandler, CallbackQueryHandler, filters
    from bot.handlers.text_handler import text_handler
    from bot.handlers.voice_handler import voice_handler
    from bot.handlers.image_handler import image_handler
    from bot.handlers.file_handler import file_handler
    from bot.handlers.command_handler import (
        start_command, mode_command, clear_command,
        stats_command, voice_command, sheet_command, callback_handler,
    )
    tg = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    tg.add_handler(CommandHandler("start",  start_command))
    tg.add_handler(CommandHandler("mode",   mode_command))
    tg.add_handler(CommandHandler("clear",  clear_command))
    tg.add_handler(CommandHandler("stats",  stats_command))
    tg.add_handler(CommandHandler("voice",  voice_command))
    tg.add_handler(CommandHandler("sheet",  sheet_command))
    tg.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    tg.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, voice_handler))
    tg.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, image_handler))
    tg.add_handler(MessageHandler(filters.Document.ALL & ~filters.Document.IMAGE, file_handler))
    tg.add_handler(CallbackQueryHandler(callback_handler))
    await tg.initialize()
    _tg_app = tg
    return tg


@app.post("/telegram")
async def telegram_webhook(request: Request):
    from telegram import Update
    data = await request.json()
    tg   = await _get_tg_app()
    update = Update.de_json(data, tg.bot)
    await tg.process_update(update)
    return {"ok": True}


@app.get("/set-webhook")
async def set_webhook(request: Request):
    """Call once after deployment: /set-webhook?url=https://your-app.vercel.app"""
    url = request.query_params.get("url")
    if not url:
        return {"error": "Pass ?url=https://your-vercel-url"}
    import httpx
    webhook_url = f"{url}/telegram"
    r = httpx.get(
        f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/setWebhook",
        params={"url": webhook_url},
    )
    return r.json()


if __name__ == "__main__":
    import os
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("web_app:app", host="0.0.0.0", port=port, reload=False)
