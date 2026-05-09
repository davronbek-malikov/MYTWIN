from database.db import get_pool


async def save_memory(user_id: int, key: str, value: str, category: str = "general") -> str:
    pool = await get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT id FROM memories WHERE user_id = $1 AND key = $2", user_id, key)
        if existing:
            await conn.execute(
                "UPDATE memories SET value=$1, category=$2, updated_at=NOW() WHERE user_id=$3 AND key=$4",
                value, category, user_id, key)
        else:
            await conn.execute(
                "INSERT INTO memories (user_id, key, value, category) VALUES ($1,$2,$3,$4)",
                user_id, key, value, category)
    return f"Saved: {key} = {value}"


async def recall_memories(user_id: int, category: str | None = None, search: str | None = None) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        q = "SELECT key, value, category FROM memories WHERE user_id = $1"
        params: list = [user_id]
        i = 2
        if category:
            q += f" AND category = ${i}"; params.append(category); i += 1
        if search:
            q += f" AND (key ILIKE ${i} OR value ILIKE ${i})"; params.append(f"%{search}%"); i += 1
        q += " ORDER BY updated_at DESC LIMIT 50"
        rows = await conn.fetch(q, *params)
    return [dict(r) for r in rows]
