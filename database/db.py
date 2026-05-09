import json
import asyncpg
import config
from utils.logger import logger

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(config.DATABASE_URL, min_size=1, max_size=5)
    return _pool


_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id          SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username    TEXT,
    first_name  TEXT,
    mode        TEXT DEFAULT 'assistant',
    voice_enabled INTEGER DEFAULT 0,
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS memories (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    key        TEXT NOT NULL,
    value      TEXT NOT NULL,
    category   TEXT DEFAULT 'general',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS entries (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    category    TEXT NOT NULL,
    data        TEXT NOT NULL,
    description TEXT,
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS conversations (
    user_id  INTEGER PRIMARY KEY REFERENCES users(id),
    messages TEXT NOT NULL DEFAULT '[]',
    updated_at TIMESTAMP DEFAULT NOW()
);
"""


async def init_db() -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        for stmt in _CREATE_SQL.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                await conn.execute(stmt)
    logger.info("Database ready")


async def get_or_create_user(
    telegram_id: int,
    username: str | None = None,
    first_name: str | None = None,
) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM users WHERE telegram_id = $1", telegram_id
        )
        if row:
            return dict(row)
        await conn.execute(
            "INSERT INTO users (telegram_id, username, first_name) VALUES ($1,$2,$3) ON CONFLICT DO NOTHING",
            telegram_id, username, first_name,
        )
        row = await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1", telegram_id)
        return dict(row)


async def get_user_mode(telegram_id: int) -> str:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT mode FROM users WHERE telegram_id = $1", telegram_id)
        return row["mode"] if row else "assistant"


async def set_user_mode(telegram_id: int, mode: str) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET mode = $1 WHERE telegram_id = $2", mode, telegram_id)


async def get_voice_enabled(telegram_id: int) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT voice_enabled FROM users WHERE telegram_id = $1", telegram_id)
        return bool(row["voice_enabled"]) if row else False


async def set_voice_enabled(telegram_id: int, enabled: bool) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET voice_enabled = $1 WHERE telegram_id = $2",
            int(enabled), telegram_id,
        )


async def load_history(user_id: int) -> list:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT messages FROM conversations WHERE user_id = $1", user_id)
        if row:
            return json.loads(row["messages"])
        return []


async def save_history(user_id: int, history: list) -> None:
    trimmed = json.dumps(history[-config.MAX_HISTORY:], ensure_ascii=False)
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO conversations (user_id, messages) VALUES ($1, $2)
               ON CONFLICT (user_id) DO UPDATE SET messages = $2, updated_at = NOW()""",
            user_id, trimmed,
        )
