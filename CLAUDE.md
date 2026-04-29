# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A Telegram-based AI personal assistant bot ("My Twin") with two operating modes — **Assistant** (reactive) and **Twin** (autonomous). It uses an agentic loop backed by an OpenAI-compatible API (Claude or GPT), SQLite for persistence, and python-telegram-bot for the Telegram interface.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in required values
python main.py
```

Required `.env` variables: `TELEGRAM_BOT_TOKEN`, `OPENAI_API_KEY`.

## Running

```bash
python main.py
```

No test suite, no build step, no CI. Logs go to stdout and `twin.log`.

## Architecture

### Request Flow

```
Telegram update → Handler (text/voice/image/command)
                → core/brain.py:think()
                → Agentic loop (Claude ↔ tools, max 10 rounds)
                → Telegram reply
```

### Key Modules

| Module | Role |
|--------|------|
| `core/brain.py` | Central AI loop. Maintains per-user in-memory conversation history, calls the LLM, dispatches tool calls, handles base64 image encoding for vision. |
| `database/db.py` | Three-table SQLite schema: `users` (profiles + mode), `memories` (long-term facts), `entries` (flexible JSON-keyed records for any trackable data). All operations are async via aiosqlite. |
| `tools/registry.py` | Defines OpenAI-format tool schemas + `execute_tool()` dispatcher. Claude never receives raw user IDs — they're injected at execution time in the dispatcher. |
| `bot/telegram_bot.py` | Wires up all handlers, initialises the DB on startup, runs long-polling. |
| `modes/` | `assistant/handler.py` and `twin/handler.py` supply different system prompts to the brain. Mode is persisted in `users.mode` and toggled via inline buttons. |

### Tools Available to the AI

- `save_memory` / `recall_memories` — long-term facts by category
- `save_entry` / `query_entries` — arbitrary JSON-structured records (transactions, tasks, notes, etc.)
- `get_summary` — aggregated counts by category/time period

### Data Flexibility Pattern

`entries.data` is a JSON column with no enforced schema. Claude chooses the structure at save time, which means the same table stores expenses, tasks, notes, and anything else without migrations.

## Config

All tunables live in `config.py` loaded from `.env`:

| Variable | Default | Purpose |
|----------|---------|---------|
| `OPENAI_MODEL` | `gpt-4o` | Model for brain + tool calls |
| `MAX_HISTORY` | `40` | Per-user in-memory message window |
| `DATABASE_PATH` | *(from env)* | SQLite file path |

