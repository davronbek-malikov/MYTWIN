from openai import AsyncOpenAI
import config
from utils.logger import logger


async def text_to_speech(text: str, voice: str = "nova", fmt: str = "opus") -> bytes | None:
    if not text or not text.strip():
        return None
    # Strip markdown symbols that sound bad when spoken
    clean = (
        text.replace("*", "").replace("_", "").replace("`", "")
            .replace("#", "").replace(">", "")
    )
    # Trim to ~800 chars so TTS stays concise
    if len(clean) > 800:
        clean = clean[:800] + "..."
    try:
        client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
        response = await client.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=clean,
            response_format=fmt,
        )
        return response.content
    except Exception as e:
        logger.error(f"TTS error: {e}")
        return None
