import aiosqlite
import config


async def save_memory(
    user_id: int, key: str, value: str, category: str = "general"
) -> str:
    async with aiosqlite.connect(config.DATABASE_PATH) as db:
        cur = await db.execute(
            "SELECT id FROM memories WHERE user_id = ? AND key = ?", (user_id, key)
        )
        existing = await cur.fetchone()
        if existing:
            await db.execute(
                "UPDATE memories SET value = ?, category = ?, updated_at = datetime('now') "
                "WHERE user_id = ? AND key = ?",
                (value, category, user_id, key),
            )
        else:
            await db.execute(
                "INSERT INTO memories (user_id, key, value, category) VALUES (?, ?, ?, ?)",
                (user_id, key, value, category),
            )
        await db.commit()
    return f"Saved: {key} = {value}"


async def recall_memories(
    user_id: int, category: str | None = None, search: str | None = None
) -> list[dict]:
    async with aiosqlite.connect(config.DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        base = "SELECT * FROM memories WHERE user_id = ?"
        params: list = [user_id]

        if category:
            base += " AND category = ?"
            params.append(category)
        if search:
            base += " AND (key LIKE ? OR value LIKE ?)"
            params += [f"%{search}%", f"%{search}%"]

        base += " ORDER BY updated_at DESC LIMIT 50"
        cur = await db.execute(base, params)
        rows = await cur.fetchall()
        return [dict(r) for r in rows]
