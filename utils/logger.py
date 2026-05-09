import logging
import os
import sys

handlers: list = [logging.StreamHandler(sys.stdout)]

# FileHandler only works locally — Vercel filesystem is read-only
if not os.getenv("VERCEL"):
    try:
        handlers.append(logging.FileHandler("twin.log", encoding="utf-8"))
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=handlers,
)

logger = logging.getLogger("MyTwin")
