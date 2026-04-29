import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")
OWNER_NAME: str = os.getenv("OWNER_NAME", "User")
DATABASE_PATH: str = os.getenv("DATABASE_PATH", "twin.db")
MAX_HISTORY: int = int(os.getenv("MAX_HISTORY", "40"))
