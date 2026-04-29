import json
import aiosqlite
import config


async def save_entry(
    user_id: int,
    category: str,
    data: dict,
    description: str | None = None,
) -> str:
    data_json = json.dumps(data, ensure_ascii=False)
    async with aiosqlite.connect(config.DATABASE_PATH) as db:
        await db.execute(
            "INSERT INTO entries (user_id, category, data, description) VALUES (?, ?, ?, ?)",
            (user_id, category, data_json, description),
        )
        await db.commit()
    return f"Saved {category}: {description or str(data)[:60]}"


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
            base += " AND (description LIKE ? OR data LIKE ?)"
            params += [f"%{search}%", f"%{search}%"]

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
