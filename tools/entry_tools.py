import json
from datetime import datetime
import aiosqlite
import config
from integrations.google_sheets import sync_to_sheet


async def save_entry(
    user_id: int,
    category: str,
    data: dict | None = None,
    description: str | None = None,
    **extra,
) -> str:
    if data is None:
        data = {}
    # Merge any top-level financial fields AI passes outside data dict
    for key in ("amount", "currency", "type", "date", "item", "note", "price"):
        if key in extra:
            data[key] = extra[key]
    # Always stamp the date so queries work correctly
    if "date" not in data:
        data["date"] = datetime.now().strftime("%Y-%m-%d")

    data_json = json.dumps(data, ensure_ascii=False)
    async with aiosqlite.connect(config.DATABASE_PATH) as db:
        # Duplicate check: same category + amount + date saved within last 5 minutes
        dup = await db.execute(
            "SELECT id FROM entries WHERE user_id = ? AND category = ? "
            "AND json_extract(data,'$.amount') = ? "
            "AND json_extract(data,'$.date') = ? "
            "AND created_at >= datetime('now','-5 minutes')",
            (user_id, category, str(data.get("amount", "")), data.get("date", "")),
        )
        if await dup.fetchone():
            return (
                f"⚠️ Duplicate — this entry ({category} {data.get('amount','')} "
                f"on {data.get('date','')}) was already saved a moment ago. Ignored."
            )
        await db.execute(
            "INSERT INTO entries (user_id, category, data, description) VALUES (?, ?, ?, ?)",
            (user_id, category, data_json, description),
        )
        await db.commit()
    await sync_to_sheet(category, data, description)

    # Return a rich confirmation string for the AI to forward to the user
    amount   = data.get("amount", "")
    currency = data.get("currency", "")
    etype    = data.get("type", "")
    emoji    = "💸" if etype == "expense" else "💰" if etype == "income" else "✅"
    amt_str  = f"{amount:,} {currency}".strip() if amount else ""
    return (
        f"{emoji} Saved | {category} | {description or ''} "
        f"{'| ' + amt_str if amt_str else ''} | {data['date']}"
    )


async def query_entries(
    user_id: int,
    category: str | None = None,
    limit: int = 20,
    search: str | None = None,
) -> list[dict]:
    limit = min(limit or 20, 100)
    async with aiosqlite.connect(config.DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        base = "SELECT * FROM entries WHERE user_id = ?"
        params: list = [user_id]

        if category:
            base += " AND category = ?"
            params.append(category)
        if search:
            base += " AND (description LIKE ? OR data LIKE ? OR json_extract(data,'$.date') LIKE ?)"
            params += [f"%{search}%", f"%{search}%", f"%{search}%"]

        base += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cur = await db.execute(base, params)
        rows = await cur.fetchall()
        result = []
        for r in rows:
            entry = dict(r)
            entry["data"] = json.loads(entry["data"])
            result.append(entry)
        return result


async def get_daily_summary(user_id: int, date: str) -> str:
    """Return all transactions for a specific date as a formatted string.
    date format: YYYY-MM-DD  e.g. '2026-05-06'
    Queries the JSON date field (transaction date) not created_at (insert date).
    """
    async with aiosqlite.connect(config.DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            # Primary: use the date stored inside the JSON data field
            # Fallback: use created_at for older entries that have no JSON date
            "SELECT category, data, description, created_at FROM entries "
            "WHERE user_id = ? AND ("
            "  json_extract(data, '$.date') = ? "
            "  OR (json_extract(data, '$.date') IS NULL AND date(created_at) = ?)"
            ") ORDER BY created_at ASC",
            (user_id, date, date),
        )
        rows = await cur.fetchall()

    if not rows:
        return f"No entries found for {date}."

    income_total = expense_total = 0.0
    lines = [f"📅 Summary for {date}\n"]
    currency = ""

    for row in rows:
        data = json.loads(row["data"])
        cat  = row["category"]
        desc = row["description"] or data.get("description", cat)
        amt  = data.get("amount", 0) or 0
        cur_sym = data.get("currency", "")
        if cur_sym:
            currency = cur_sym
        etype = data.get("type", "")
        try:
            amt = float(amt)
        except (ValueError, TypeError):
            amt = 0.0

        if etype == "income" or cat.lower() in ("kirim", "kurs puli"):
            income_total += amt
            lines.append(f"  💰 {cat} | {desc} | +{amt:,.0f} {cur_sym}")
        else:
            expense_total += amt
            lines.append(f"  💸 {cat} | {desc} | -{amt:,.0f} {cur_sym}")

    lines.append(f"\n💰 Income:   {income_total:,.0f} {currency}")
    lines.append(f"💸 Expenses: {expense_total:,.0f} {currency}")
    net = income_total - expense_total
    lines.append(f"{'📈' if net >= 0 else '📉'} Net:      {'+' if net >= 0 else ''}{net:,.0f} {currency}")
    return "\n".join(lines)


async def get_summary(
    user_id: int,
    category: str | None = None,
    period: str = "all",
) -> list[dict]:
    period_filter = ""
    if period == "today":
        period_filter = "AND date(created_at) = date('now')"
    elif period == "week":
        period_filter = "AND created_at >= datetime('now', '-7 days')"
    elif period == "month":
        period_filter = "AND created_at >= datetime('now', '-30 days')"

    async with aiosqlite.connect(config.DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        if category:
            sql = (
                f"SELECT '{category}' as category, COUNT(*) as count, "
                f"MIN(created_at) as first_entry, MAX(created_at) as last_entry "
                f"FROM entries WHERE user_id = ? AND category = ? {period_filter}"
            )
            cur = await db.execute(sql, (user_id, category))
        else:
            sql = (
                f"SELECT category, COUNT(*) as count "
                f"FROM entries WHERE user_id = ? {period_filter} "
                f"GROUP BY category ORDER BY count DESC"
            )
            cur = await db.execute(sql, (user_id,))

        rows = await cur.fetchall()
        return [dict(r) for r in rows]
