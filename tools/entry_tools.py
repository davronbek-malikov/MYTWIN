import json
from datetime import datetime
from database.db import get_pool
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
    for key in ("amount", "currency", "type", "date", "item", "note", "price"):
        if key in extra:
            data[key] = extra[key]
    if "date" not in data:
        data["date"] = datetime.now().strftime("%Y-%m-%d")

    data_json = json.dumps(data, ensure_ascii=False)
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Duplicate check
        rows = await conn.fetch(
            "SELECT id, data FROM entries WHERE user_id = $1 AND category = $2 "
            "AND created_at >= NOW() - INTERVAL '5 minutes'",
            user_id, category,
        )
        for r in rows:
            d = json.loads(r["data"])
            if (str(d.get("amount","")) == str(data.get("amount",""))
                    and d.get("date","") == data.get("date","")):
                return (f"⚠️ Duplicate — {category} {data.get('amount','')} "
                        f"on {data.get('date','')} already saved. Ignored.")
        await conn.execute(
            "INSERT INTO entries (user_id, category, data, description) VALUES ($1,$2,$3,$4)",
            user_id, category, data_json, description,
        )

    await sync_to_sheet(category, data, description)

    amount   = data.get("amount", "")
    currency = data.get("currency", "")
    etype    = data.get("type", "")
    emoji    = "💸" if etype == "expense" else "💰" if etype == "income" else "✅"
    amt_str  = f"{amount:,} {currency}".strip() if amount else ""
    return (f"{emoji} Saved | {category} | {description or ''} "
            f"{'| ' + amt_str if amt_str else ''} | {data['date']}")


async def delete_entry(
    user_id: int,
    entry_id: int | None = None,
    delete_last: bool = False,
    search: str | None = None,
    date: str | None = None,
) -> str:
    from integrations.google_sheets import delete_from_sheet
    pool = await get_pool()
    async with pool.acquire() as conn:
        if delete_last:
            row = await conn.fetchrow(
                "SELECT * FROM entries WHERE user_id = $1 ORDER BY created_at DESC LIMIT 1", user_id)
        elif entry_id:
            row = await conn.fetchrow(
                "SELECT * FROM entries WHERE id = $1 AND user_id = $2", entry_id, user_id)
        elif search:
            q = f"%{search}%"
            row = await conn.fetchrow(
                "SELECT * FROM entries WHERE user_id = $1 AND (description ILIKE $2 OR data ILIKE $2) "
                "ORDER BY created_at DESC LIMIT 1", user_id, q)
        else:
            return "Specify what to delete."

        if not row:
            return "❌ Entry not found."

        entry = dict(row)
        data  = json.loads(entry["data"])
        await conn.execute("DELETE FROM entries WHERE id = $1", entry["id"])

    await delete_from_sheet(entry["category"], data, entry["description"])
    return (f"🗑 Deleted: {entry['category']} | {entry['description'] or ''} | "
            f"{data.get('amount','')} {data.get('currency','')} | {data.get('date','')}\nAlso removed from Google Sheet.")


async def query_entries(
    user_id: int,
    category: str | None = None,
    limit: int = 20,
    search: str | None = None,
) -> list[dict]:
    limit = min(limit or 20, 100)
    pool  = await get_pool()
    async with pool.acquire() as conn:
        q = "SELECT * FROM entries WHERE user_id = $1"
        params: list = [user_id]
        i = 2
        if category:
            q += f" AND category = ${i}"; params.append(category); i += 1
        if search:
            q += f" AND (description ILIKE ${i} OR data ILIKE ${i})"; params.append(f"%{search}%"); i += 1
        q += f" ORDER BY created_at DESC LIMIT ${i}"; params.append(limit)
        rows = await conn.fetch(q, *params)
    result = []
    for r in rows:
        e = dict(r)
        e["data"] = json.loads(e["data"])
        e["created_at"] = str(e["created_at"])
        result.append(e)
    return result


async def get_daily_summary(user_id: int, date: str) -> str:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT category, data, description, created_at FROM entries "
            "WHERE user_id = $1 ORDER BY created_at ASC",
            user_id,
        )

    # Filter in Python for date (works with both json date field and created_at)
    matches = []
    for r in rows:
        d = json.loads(r["data"])
        if d.get("date") == date or str(r["created_at"])[:10] == date:
            matches.append((dict(r["_asdict"]() if hasattr(r, "_asdict") else r), d))

    # Re-fetch properly
    pool2 = await get_pool()
    async with pool2.acquire() as conn:
        all_rows = await conn.fetch(
            "SELECT category, data, description, created_at::text FROM entries "
            "WHERE user_id = $1 ORDER BY created_at ASC", user_id)

    filtered = []
    for r in all_rows:
        d = json.loads(r["data"])
        if d.get("date") == date or r["created_at"][:10] == date:
            filtered.append((dict(r), d))

    if not filtered:
        return f"No entries found for {date}."

    income_total = expense_total = 0.0
    currency = ""
    lines = [f"📅 Summary for {date}\n"]

    for row, d in filtered:
        cat  = row["category"]
        desc = row["description"] or d.get("description", cat)
        amt  = float(d.get("amount") or 0)
        cur  = d.get("currency", "")
        if cur: currency = cur
        etype = d.get("type", "")
        if etype == "income" or cat.lower() in ("kirim", "kurs puli"):
            income_total += amt
            lines.append(f"  💰 {cat} | {desc} | +{amt:,.0f} {cur}")
        else:
            expense_total += amt
            lines.append(f"  💸 {cat} | {desc} | -{amt:,.0f} {cur}")

    net = income_total - expense_total
    lines.append(f"\n💰 Income:   {income_total:,.0f} {currency}")
    lines.append(f"💸 Expenses: {expense_total:,.0f} {currency}")
    lines.append(f"{'📈' if net >= 0 else '📉'} Net: {'+' if net >= 0 else ''}{net:,.0f} {currency}")
    return "\n".join(lines)


async def get_summary(user_id: int, category: str | None = None, period: str = "all") -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        period_filter = ""
        if period == "today":
            period_filter = "AND DATE(created_at) = CURRENT_DATE"
        elif period == "week":
            period_filter = "AND created_at >= NOW() - INTERVAL '7 days'"
        elif period == "month":
            period_filter = "AND created_at >= NOW() - INTERVAL '30 days'"

        if category:
            sql = (f"SELECT '{category}' as category, COUNT(*) as count "
                   f"FROM entries WHERE user_id = $1 AND category = $2 {period_filter}")
            rows = await conn.fetch(sql, user_id, category)
        else:
            sql = (f"SELECT category, COUNT(*) as count FROM entries "
                   f"WHERE user_id = $1 {period_filter} GROUP BY category ORDER BY count DESC")
            rows = await conn.fetch(sql, user_id)
    return [dict(r) for r in rows]
