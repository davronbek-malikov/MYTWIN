"""
My Twin — Desktop Voice Assistant
Run with:      python desktop_app.py
List mics:     python desktop_app.py --list-mics
Say the wake word (default: "Twin") → Twin listens → speak your command → Twin replies aloud
"""
import asyncio
import io
import queue
import sys
import tempfile
import wave

import numpy as np
import sounddevice as sd
import soundfile as sf
from openai import AsyncOpenAI

import config
from core.brain import brain
from database.db import init_db, get_or_create_user
from tools.tts_tools import text_to_speech
from utils.logger import logger


def list_microphones() -> None:
    print("\nAvailable microphones:\n")
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0:
            print(f"  [{i}] {d['name']}")
    print(f"\nSet MICROPHONE_INDEX=<number> in your .env file.\n")

_DESKTOP_TELEGRAM_ID = 0   # dedicated DB user for desktop
_desktop_user_id: int | None = None

SAMPLE_RATE   = 16000
CHANNELS      = 1
DTYPE         = "int16"
SILENCE_LIMIT = 1.5    # seconds of silence before stopping recording
ENERGY_THRESH = 500    # RMS threshold to detect speech

# ── Terminal colours ─────────────────────────────────────────────────────────
CYAN  = "\033[96m"
GREEN = "\033[92m"
YEL   = "\033[93m"
RESET = "\033[0m"
BOLD  = "\033[1m"


def status(emoji: str, msg: str) -> None:
    print(f"\r{emoji}  {msg:<60}", end="", flush=True)


# ── Audio recording ──────────────────────────────────────────────────────────

def _record_until_silence(max_seconds: int = 15) -> np.ndarray | None:
    """Record from mic until silence is detected or max_seconds reached."""
    q: queue.Queue = queue.Queue()

    def callback(indata, frames, time, status_flag):
        q.put(indata.copy())

    chunks = []
    silent_chunks = 0
    chunks_per_second = 10
    silence_chunks = int(SILENCE_LIMIT * chunks_per_second)
    blocksize = SAMPLE_RATE // chunks_per_second
    started = False

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS,
                        dtype=DTYPE, blocksize=blocksize, callback=callback,
                        device=config.MICROPHONE_INDEX):
        for _ in range(max_seconds * chunks_per_second):
            try:
                chunk = q.get(timeout=1)
            except queue.Empty:
                break
            rms = int(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))
            if rms > ENERGY_THRESH:
                started = True
                silent_chunks = 0
                chunks.append(chunk)
            elif started:
                chunks.append(chunk)
                silent_chunks += 1
                if silent_chunks >= silence_chunks:
                    break

    if not chunks:
        return None
    return np.concatenate(chunks, axis=0)


def _audio_to_wav_bytes(audio: np.ndarray) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)   # int16 = 2 bytes
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio.tobytes())
    return buf.getvalue()


# ── Audio playback ───────────────────────────────────────────────────────────

def _play_mp3_sync(mp3_bytes: bytes) -> None:
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        f.write(mp3_bytes)
        tmp_path = f.name
    data, sr = sf.read(tmp_path, dtype="float32")
    sd.play(data, sr)
    sd.wait()
    import os; os.unlink(tmp_path)


async def speak(text: str) -> None:
    audio = await text_to_speech(text, voice=config.VOICE_NAME, fmt="mp3")
    if audio:
        await asyncio.to_thread(_play_mp3_sync, audio)


# ── Speech-to-text ───────────────────────────────────────────────────────────

async def transcribe(wav_bytes: bytes) -> str:
    client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
    buf = io.BytesIO(wav_bytes)
    buf.name = "audio.wav"
    try:
        result = await client.audio.transcriptions.create(
            model="whisper-1", file=buf
        )
        return result.text.strip()
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        return ""


# ── Main loop ────────────────────────────────────────────────────────────────

async def main() -> None:
    global _desktop_user_id

    print(f"\n{BOLD}{'='*55}")
    print("  🤖  MY TWIN — Desktop Voice Assistant")
    print(f"{'='*55}{RESET}\n")

    await init_db()
    db_user = await get_or_create_user(
        _DESKTOP_TELEGRAM_ID, "desktop", config.OWNER_NAME
    )
    _desktop_user_id = db_user["id"]

    wake_word = config.WAKE_WORD.lower()

    greeting = (
        f"Hello {config.OWNER_NAME}! I'm awake. "
        f"Say '{config.WAKE_WORD}' to talk to me."
    )
    print(f"  {CYAN}{greeting}{RESET}\n")
    await speak(greeting)

    status("💤", f"Sleeping — say '{config.WAKE_WORD}' to wake me")

    while True:
        try:
            # ── Phase 1: listen for wake word ────────────────────────
            audio = await asyncio.to_thread(_record_until_silence, 4)

            if audio is None:
                continue

            wav = _audio_to_wav_bytes(audio)
            status("🔍", "Checking...")
            heard = await transcribe(wav)

            if not heard or wake_word not in heard.lower():
                status("💤", f"Sleeping — say '{config.WAKE_WORD}'")
                continue

            # ── Phase 2: wake up ──────────────────────────────────────
            print(f"\n\n{GREEN}⚡  Wake word detected!{RESET}")
            await speak("Yes?")

            # ── Phase 3: record command ───────────────────────────────
            status("👂", "Listening for your command...")
            cmd_audio = await asyncio.to_thread(_record_until_silence, 20)

            if cmd_audio is None:
                status("💤", "No command heard — sleeping")
                continue

            status("🔍", "Transcribing...")
            command = await transcribe(_audio_to_wav_bytes(cmd_audio))

            if not command:
                status("💤", "Couldn't hear you — sleeping")
                continue

            print(f"\n{YEL}🗣  You:{RESET} {command}")

            # ── Phase 4: think ────────────────────────────────────────
            status("🧠", "Thinking...")
            response = await brain.think(_desktop_user_id, command, "assistant")
            print(f"{GREEN}🤖  Twin:{RESET} {response}\n")

            # ── Phase 5: speak ────────────────────────────────────────
            status("🔊", "Speaking...")
            await speak(response)

            status("💤", f"Sleeping — say '{config.WAKE_WORD}'")

        except KeyboardInterrupt:
            print(f"\n\n👋  Goodbye, {config.OWNER_NAME}!\n")
            break
        except Exception as e:
            logger.error(f"Desktop error: {e}")
            status("⚠️ ", f"Error: {e}")
            await asyncio.sleep(1)


if __name__ == "__main__":
    if "--list-mics" in sys.argv:
        list_microphones()
    else:
        asyncio.run(main())
