"""
My Twin — Web UI
Run with: python web_app.py
Then open: http://localhost:8000
"""
import io
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

_WEB_TELEGRAM_ID = 0
_web_user_id: int | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _web_user_id
    await init_db()
    db_user = await get_or_create_user(
        _WEB_TELEGRAM_ID, "web", config.OWNER_NAME
    )
    _web_user_id = db_user["id"]
    yield


app = FastAPI(lifespan=lifespan)
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    mode = await get_user_mode(_WEB_TELEGRAM_ID)
    return templates.TemplateResponse("index.html", {
        "request": request,
        "owner": config.OWNER_NAME,
        "mode": mode,
    })


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


if __name__ == "__main__":
    uvicorn.run("web_app:app", host="0.0.0.0", port=8000, reload=True)
