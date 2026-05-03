import asyncio
import json
from datetime import datetime

import httpx

import config
from utils.logger import logger

_FINANCIAL_CATEGORIES = {
    # English
    "transaction", "expense", "expenses", "income", "incomings",
    "purchase", "purchases", "spending", "salary", "payment",
    # Uzbek (user's own categories)
    "ovqatlanish", "praduxta", "yo'lkira", "yolkira",
    "uyga xarajat", "yangi uyga xarajat", "xarajatlar",
    "boshqa", "qarz", "kurs puli", "kirim", "cashback", "visa",
}


def _is_financial(category: str) -> bool:
    c = category.lower()
    return c in _FINANCIAL_CATEGORIES or any(
        k in c for k in ("income", "expense", "purchase", "spend", "salary", "xarajat", "kirim", "puli")
    )


def _post_to_sheet(payload: dict) -> None:
    with httpx.Client(timeout=10) as client:
        client.post(config.GOOGLE_WEBHOOK_URL, json=payload)


async def sync_to_sheet(category: str, data: dict, description: str | None = None) -> None:
    if not _is_financial(category):
        return
    if not config.GOOGLE_WEBHOOK_URL:
        return
    payload = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "category": category,
        "type": data.get("type", ""),
        "amount": data.get("amount", ""),
        "currency": data.get("currency", ""),
        "description": description or data.get("description", ""),
        "extra": json.dumps(
            {k: v for k, v in data.items() if k not in ("type", "amount", "currency", "description")},
            ensure_ascii=False,
        ),
    }
    try:
        await asyncio.to_thread(_post_to_sheet, payload)
        logger.info(f"Synced '{category}' entry to Google Sheet")
    except Exception as e:
        logger.error(f"Google Sheets sync failed: {e}")
