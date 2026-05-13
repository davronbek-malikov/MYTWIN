import json
import os
import re
import ssl
import tempfile
from pathlib import Path

import aiosqlite
import asyncpg
import config
from utils.logger import logger

_pool = None


def _is_postgres_dsn(value: str) -> bool:
    return value.startswith(("postgresql://", "postgres://"))


def _sqlite_path() -> str:
    if os.getenv("VERCEL"):
        return str(Path(tempfile.gettempdir()) / Path(config.DATABASE_PATH or "twin.db").name)
    return config.DATABASE_PATH or "twin.db"


def _sqlite_row_factory(cursor, row):
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


def _sqlite_sql(sql: str) -> str:
    replacements = {
        "NOW() - INTERVAL '5 minutes'": "datetime('now', '-5 minutes')",
        "NOW() - INTERVAL '7 days'": "datetime('now', '-7 days')",
        "NOW() - INTERVAL '30 days'": "datetime('now', '-30 days')",
        "NOW()": "CURRENT_TIMESTAMP",
        "created_at::text": "created_at",
        "ILIKE": "LIKE",
    }
    for old, new in replacements.items():
        sql = sql.replace(old, new)
    return re.sub(r"\$(\d+)", r"?\1", sql)


class SQLiteConnection:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def execute(self, sql: str, *params):
        return await self._conn.execute(_sqlite_sql(sql), params)

    async def fetchrow(self, sql: str, *params):
        cursor = await self._conn.execute(_sqlite_sql(sql), params)
        try:
            return await cursor.fetchone()
        finally:
            await cursor.close()

    async def fetch(self, sql: str, *params):
        cursor = await self._conn.execute(_sqlite_sql(sql), params)
        try:
            return await cursor.fetchall()
        finally:
            await cursor.close()


class SQLiteAcquire:
    def __init__(self, path: str) -> None:
        self._path = path
        self._conn: aiosqlite.Connection | None = None

    async def __aenter__(self) -> SQLiteConnection:
        self._conn = await aiosqlite.connect(self._path)
        self._conn.row_factory = _sqlite_row_factory
        await self._conn.execute("PRAGMA foreign_keys = ON")
        return SQLiteConnection(self._conn)

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._conn:
            if exc_type:
                await self._conn.rollback()
            else:
                await self._conn.commit()
            await self._conn.close()


class SQLitePool:
    def __init__(self, path: str) -> None:
        self.path = path

    def acquire(self) -> SQLiteAcquire:
        return SQLiteAcquire(self.path)


async def get_pool():
    global _pool
    if _pool is None:
        if not _is_postgres_dsn(config.DATABASE_URL):
            if config.DATABASE_URL:
                logger.warning(
                    "DATABASE_URL is not a Postgres DSN; using SQLite fallback. "
                    "Set DATABASE_URL to a postgresql:// Supabase pooler URL for durable storage."
                )
            path = _sqlite_path()
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            _pool = SQLitePool(path)
            return _pool

        # Supabase (and Neon) require SSL; build a permissive SSL context.
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode   = ssl.CERT_NONE
        _pool = await asyncpg.create_pool(
            config.DATABASE_URL,
            min_size=1,
            max_size=5,
            ssl=ssl_ctx,
        )
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

_SQLITE_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id   INTEGER UNIQUE NOT NULL,
    username      TEXT,
    first_name    TEXT,
    mode          TEXT DEFAULT 'assistant',
    voice_enabled INTEGER DEFAULT 0,
    created_at    TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS memories (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    key        TEXT NOT NULL,
    value      TEXT NOT NULL,
    category   TEXT DEFAULT 'general',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS entries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    category    TEXT NOT NULL,
    data        TEXT NOT NULL,
    description TEXT,
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conversations (
    user_id    INTEGER PRIMARY KEY REFERENCES users(id),
    messages   TEXT NOT NULL DEFAULT '[]',
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


async def init_db() -> None:
    pool = await get_pool()
    create_sql = _CREATE_SQL if _is_postgres_dsn(config.DATABASE_URL) else _SQLITE_CREATE_SQL
    async with pool.acquire() as conn:
        for stmt in create_sql.strip().split(";"):
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
