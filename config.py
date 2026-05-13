import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")
OWNER_NAME: str = os.getenv("OWNER_NAME", "User")
DATABASE_PATH: str = os.getenv("DATABASE_PATH", "twin.db")
# Supabase / Neon / any PostgreSQL — use the pooler URL for Vercel
DATABASE_URL: str  = os.getenv("DATABASE_URL", "")
MAX_HISTORY: int = int(os.getenv("MAX_HISTORY", "40"))

# Gemini API (used for News Agent summarization)
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

# Google Sheets integration (optional — leave blank to disable)
GOOGLE_WEBHOOK_URL: str = os.getenv("GOOGLE_WEBHOOK_URL", "")
GOOGLE_SHEET_ID: str    = os.getenv("GOOGLE_SHEET_ID", "")
# Auth
SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-production-use-random-32-chars")
ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "davronbekmalikov96@gmail.com")
GMAIL_APP_PASSWORD: str = os.getenv("GMAIL_APP_PASSWORD", "")

def google_sheet_url() -> str:
    if GOOGLE_SHEET_ID:
        return f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}/edit"
    return ""

# Desktop voice assistant
WAKE_WORD: str = os.getenv("WAKE_WORD", "Twin")
VOICE_NAME: str = os.getenv("VOICE_NAME", "nova")
MICROPHONE_INDEX: int | None = int(os.getenv("MICROPHONE_INDEX")) if os.getenv("MICROPHONE_INDEX") else None
