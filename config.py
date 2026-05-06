import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")
OWNER_NAME: str = os.getenv("OWNER_NAME", "User")
DATABASE_PATH: str = os.getenv("DATABASE_PATH", "twin.db")
MAX_HISTORY: int = int(os.getenv("MAX_HISTORY", "40"))

# Google Sheets integration (optional — leave blank to disable)
GOOGLE_WEBHOOK_URL: str = os.getenv("GOOGLE_WEBHOOK_URL", "")

# Desktop voice assistant
WAKE_WORD: str = os.getenv("WAKE_WORD", "Twin")
VOICE_NAME: str = os.getenv("VOICE_NAME", "nova")
MICROPHONE_INDEX: int | None = int(os.getenv("MICROPHONE_INDEX")) if os.getenv("MICROPHONE_INDEX") else None
