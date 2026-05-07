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


async def delete_from_sheet(category: str, data: dict, description: str | None = None) -> None:
    if not config.GOOGLE_WEBHOOK_URL:
        return
    transaction_date = data.get("date") or datetime.now().strftime("%Y-%m-%d")
    amount   = data.get("amount", "")
    currency = data.get("currency", "")
    desc     = description or data.get("description", category)
    # Build the cell value string exactly as it was written
    cell_value = f"{desc}:{amount}"
    if currency and currency != "UZS":
        cell_value += f" {currency}"

    payload = {
        "action": "delete",
        "transaction_date": transaction_date,
        "cell_value": cell_value,
        "description": desc,
    }
    try:
        await asyncio.to_thread(_post_to_sheet, payload)
        logger.info(f"Delete request sent to Google Sheet for '{cell_value}'")
    except Exception as e:
        logger.error(f"Google Sheets delete failed: {e}")


async def sync_to_sheet(category: str, data: dict, description: str | None = None) -> None:
    if not _is_financial(category):
        return
    if not config.GOOGLE_WEBHOOK_URL:
        return

    # Use the actual transaction date (set by AI from user's words like "kecha")
    # Fall back to today only if not set
    transaction_date = data.get("date") or datetime.now().strftime("%Y-%m-%d")

    payload = {
        "transaction_date": transaction_date,          # YYYY-MM-DD — Apps Script uses this for column
        "category": category,
        "type": data.get("type", ""),
        "amount": data.get("amount", ""),
        "currency": data.get("currency", ""),
        "description": description or data.get("description", ""),
    }
    try:
        await asyncio.to_thread(_post_to_sheet, payload)
        logger.info(f"Synced '{category}' entry to Google Sheet (date={transaction_date})")
    except Exception as e:
        logger.error(f"Google Sheets sync failed: {e}")
