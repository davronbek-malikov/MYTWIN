# Daily Changes Log

> Format: Date → Time → Mode → Feature name → Tasks

---

## 2026-04-29

---

### 11:30 | Phase 1 | Both Modes | Project Scaffold

**Files created:**
- `requirements.txt` — all Phase 1 Python dependencies
- `.env.example` — environment variable template
- `.gitignore` — excludes .env, database, logs, caches
- `main.py` — single entry point to start the bot
- `config.py` — loads all settings from .env

---

### 11:31 | Phase 1 | Both Modes | Directory & Package Structure

**Files created:**
- `utils/__init__.py`
- `database/__init__.py`
- `core/__init__.py`
- `tools/__init__.py`
- `bot/__init__.py`
- `bot/handlers/__init__.py`
- `modes/__init__.py`
- `modes/assistant/__init__.py`
- `modes/twin/__init__.py`

---

### 11:32 | Phase 1 | Both Modes | Logger

**File:** `utils/logger.py`

**Tasks:**
- Configured Python standard `logging` with stdout + file (`twin.log`) output
- Format: `timestamp | level | name | message`

---

### 11:33 | Phase 1 | Both Modes | Database Layer

**File:** `database/db.py`

**Tasks:**
- Designed 3-table SQLite schema: `users`, `memories`, `entries`
- `entries.data` stored as JSON string — fully flexible, any category
- Async operations via `aiosqlite`
- Functions: `init_db`, `get_or_create_user`, `get_user_mode`, `set_user_mode`

---

### 11:34 | Phase 1 | Assistant Mode | Memory Tools

**File:** `tools/memory_tools.py`

**Tasks:**
- `save_memory(user_id, key, value, category)` — upsert long-term facts
- `recall_memories(user_id, category, search)` — filtered retrieval

---

### 11:35 | Phase 1 | Assistant Mode | Entry Tools

**File:** `tools/entry_tools.py`

**Tasks:**
- `save_entry(user_id, category, data, description)` — save any typed data (finance, task, note, idea, etc.)
- `query_entries(user_id, category, limit, search)` — full-text search across entries
- `get_summary(user_id, category, period)` — counts by category and time window (today/week/month/all)

---

### 11:36 | Phase 1 | Both Modes | Tool Registry

**File:** `tools/registry.py`

**Tasks:**
- Defined 5 tool schemas for Claude API (save_memory, recall_memories, save_entry, query_entries, get_summary)
- `execute_tool(name, input, user_id)` — dispatcher that injects user_id (Claude never sees it)
- Error handling and logging per tool call

---

### 11:37 | Phase 1 | Both Modes | AI Brain

**File:** `core/brain.py`

**Tasks:**
- `Brain` class with async Claude client
- Per-user conversation history (in-memory, configurable max length via `MAX_HISTORY`)
- `think(user_id, text, mode, image_data, image_mime)` — unified entry point for all input types
- `_agent_loop()` — full agentic tool-use loop: Claude → tool call → result → Claude (up to 10 rounds)
- Image support: base64-encodes bytes → Claude Vision
- Mode-specific system prompts: Assistant (reactive) vs Twin (autonomous)
- `clear_history()` and `history_length()` utilities

---

### 11:38 | Phase 1 | Both Modes | Telegram Bot — Keyboards

**File:** `bot/keyboards.py`

**Tasks:**
- `mode_keyboard()` — inline buttons: Assistant Mode / Twin Mode
- `main_menu_keyboard()` — inline buttons: Switch Mode / My Stats / Clear Chat

---

### 11:39 | Phase 1 | Assistant Mode | Telegram Bot — Text Handler

**File:** `bot/handlers/text_handler.py`

**Tasks:**
- Receives any text message
- Shows "..." while Claude processes (edited to final response)
- Passes message to `brain.think()` in current mode

---

### 11:40 | Phase 1 | Assistant Mode | Telegram Bot — Voice Handler

**File:** `bot/handlers/voice_handler.py`

**Tasks:**
- Downloads OGG voice file from Telegram
- Transcribes with OpenAI Whisper API (`whisper-1`)
- Shows transcription to user, then passes text to `brain.think()`
- Graceful error if `OPENAI_API_KEY` not set

---

### 11:41 | Phase 1 | Assistant Mode | Telegram Bot — Image Handler

**File:** `bot/handlers/image_handler.py`

**Tasks:**
- Handles Telegram `PHOTO` and `Document.IMAGE` messages
- Validates supported MIME types (JPEG, PNG, GIF, WebP)
- Downloads image and passes bytes to `brain.think()` with `image_data`
- Caption text forwarded as the user's instruction alongside the image

---

### 11:42 | Phase 1 | Both Modes | Telegram Bot — Command Handler

**File:** `bot/handlers/command_handler.py`

**Tasks:**
- `/start` — welcome message with current mode and main menu
- `/mode` — show mode switch keyboard
- `/clear` — reset conversation history for this user
- `/stats` — show current mode, message count, entry summary by category
- `callback_handler()` — handles all inline button presses (mode switch, stats, clear)
- `_stats_text()` — shared helper used by both command and callback

---

### 11:43 | Phase 1 | Both Modes | Telegram Bot — Application Setup

**File:** `bot/telegram_bot.py`

**Tasks:**
- Builds `Application` with `post_init` hook for async DB initialization
- Registers all handlers: commands, text, voice, image, callbacks
- `create_and_run_bot()` — validates required env vars before starting

---

### 11:44 | Phase 1 | Assistant Mode | Mode Documentation

**Files:** `modes/assistant/handler.py`, `modes/twin/handler.py`

**Tasks:**
- Documented available tools per mode
- Listed Phase 3 additions for Assistant (email, reports)
- Listed Phase 4 additions for Twin (task queue, browser automation, inbox handling)

---

## 2026-05-03

---

### 10:00 | Setup | Both Modes | Project Configuration & GitHub 

**Files changed:** `.env`, `.env.example`, `config.py`, `bot/telegram_bot.py`, `CLAUDE.md`

**Tasks:**
- Created `.env` with real `TELEGRAM_BOT_TOKEN` and `OPENAI_API_KEY`
- Fixed `bot/telegram_bot.py` — was validating `ANTHROPIC_API_KEY` (wrong) → changed to `OPENAI_API_KEY`
- Removed unused `ANTHROPIC_API_KEY` from config entirely
- Created `CLAUDE.md` — codebase documentation for Claude Code
- Initialised git repo inside project folder and pushed to GitHub: `davronbek-malikov/MYTWIN`

---

### 14:00 | Phase 2 | Both Modes | Google Sheets Integration

**Files created:** `integrations/__init__.py`, `integrations/google_sheets.py`

**Files changed:** `config.py`, `.env.example`, `requirements.txt`, `tools/entry_tools.py`

**Tasks:**
- Built Google Sheets auto-sync via Google Apps Script webhook (no credentials file needed)
- Added `GOOGLE_WEBHOOK_URL` to config — set blank to disable, paste Apps Script URL to enable
- `sync_to_sheet(category, data, description)` — async, best-effort, never crashes the bot
- Financial category detection covers both English and Uzbek terms (Ovqatlanish, Praduxta, Yo'lkira, etc.)
- `save_entry` now calls `sync_to_sheet` after every DB write automatically
- Apps Script writes in user's existing format: column = day (`03.05(Sunday)`), row = `Item:Amount`
- Foreign currency shown in cell value (e.g. `Kofe:4500 KRW`)

---

### 15:00 | Phase 2 | Assistant Mode | Financial Report Tool

**Files created:** `tools/report_tools.py`

**Files changed:** `tools/registry.py`

**Tasks:**
- Added `generate_report(user_id, period)` — queries SQLite and returns formatted income/expense summary
- Report periods: today / week / month / all
- Classifies entries as income or expense using both entry type field and Uzbek category names
- Registered as AI-callable tool — triggered by natural language ("give me monthly report")
- Added `generate_report` to `execute_tool` dispatcher

---

### 16:00 | Phase 2 | Assistant Mode | System Prompt — Uzbek Categories & Currency

**File changed:** `core/brain.py`

**Tasks:**
- Added Uzbek expense category list to system prompt — bot now uses consistent names:
  Ovqatlanish, Praduxta, Yo'lkira, Uyga xarajat, Yangi uyga xarajat, Boshqa, Qarz, Kurs puli, Kirim
- Added currency detection rules: "won/wonga" → KRW, "dollar/$" → USD, "so'm/sum" → UZS (default), etc.
- Bot now saves specific item name as description (e.g. "Kofe") not category name

---

### 17:00 | Bugfix | Both Modes | save_entry Argument Fix

**File changed:** `tools/entry_tools.py`

**Tasks:**
- Fixed critical bug: AI was sending `amount`, `currency`, `type` as top-level kwargs instead of inside `data` dict
- `save_entry` now accepts `**extra` and auto-merges top-level financial fields into `data`
- Root cause: OpenAI function calling sometimes flattens nested objects
- Effect: transactions were being rejected silently and never reaching Google Sheets

---

## 2026-05-06

---

### Phase 3 | Voice-First Agent | TTS + Web Tools

**Files created:** `tools/tts_tools.py`, `tools/search_tools.py`

**Files modified:** `database/db.py`, `tools/registry.py`, `bot/handlers/text_handler.py`, `bot/handlers/voice_handler.py`, `bot/handlers/command_handler.py`, `bot/telegram_bot.py`, `bot/keyboards.py`, `core/brain.py`, `requirements.txt`

---

#### tools/tts_tools.py — Voice Replies (TTS)
- `text_to_speech(text, voice)` — converts bot response to audio using OpenAI TTS API (`tts-1`, voice: `nova`)
- Strips markdown symbols before speaking, trims to 800 chars
- Returns `bytes` in Opus format, ready for Telegram voice message

#### tools/search_tools.py — Information Tools
- `web_search(query, max_results)` — searches internet via DuckDuckGo (no API key needed)
- `get_weather(city)` — real-time weather via wttr.in (free, no API key)
- `get_news(topic, max_results)` — latest news headlines via DuckDuckGo News
- `convert_currency(amount, from, to)` — live exchange rates via frankfurter.app (free, no API key)

#### database/db.py — Voice Preference
- Added `voice_enabled` column to `users` table via safe ALTER TABLE migration
- `get_voice_enabled(telegram_id)` / `set_voice_enabled(telegram_id, enabled)` functions

#### Handlers — Voice Reply Integration
- `text_handler.py` — after text response, sends voice reply if `voice_enabled = True`
- `voice_handler.py` — always sends voice reply when user sends a voice message

#### Bot — /voice Command & Keyboard
- New `/voice` command — toggles voice replies ON/OFF, shows updated keyboard
- `bot/keyboards.py` — main menu now shows `🔊 Voice: ON` / `🔇 Voice: OFF` toggle button
- `callback_handler` — handles `toggle_voice` button press
- `bot/telegram_bot.py` — registered `/voice` CommandHandler

#### System Prompt — New Tools Awareness
- Brain now knows about `web_search`, `get_weather`, `get_news`, `convert_currency`
- Rules added: always use tools for weather/news/search requests, never say "I can't"

#### requirements.txt
- Added `duckduckgo-search>=6.0.0`

---

## Upcoming Changes

### Phase 2 — Persistent Conversation History (planned)
- Store conversation messages in DB (survive bot restarts)
- Recall context from previous sessions

### Phase 3 — Action System (planned)
- `send_email` tool via SendGrid/SMTP
- PDF and Excel report generation
- "Send me a weekly summary" scheduled report

### Phase 4 — Twin Autonomous Mode (planned)
- Background task queue (Celery + Redis)
- Browser automation via Playwright
- Email inbox monitoring and drafting
- Cron-based autonomous routines (Twin works while you sleep)
- Decision log: Twin records every action taken on your behalf

---

## 2026-05-06 (Session 2)

---

### Phase 3 | Desktop Voice Assistant | Wake Word App

**Files created:** `desktop_app.py`

**Files modified:** `config.py`, `.env.example`, `tools/tts_tools.py`, `requirements.txt`

#### desktop_app.py — Always-Listening Voice App
- Runs independently from Telegram bot (`python desktop_app.py`)
- Wake word loop: listens → detects wake word → records command → replies aloud
- Uses `sounddevice` for microphone recording with energy-based VAD (voice activity detection)
- Sends audio to OpenAI Whisper for transcription
- Processes command through `brain.think()` — same AI, same memory, same tools as Telegram bot
- TTS reply via OpenAI (`nova` voice, mp3) played back through speakers via `soundfile`
- Coloured terminal UI: 💤 sleeping → ⚡ woke → 👂 listening → 🧠 thinking → 🔊 speaking
- `--list-mics` flag: `python desktop_app.py --list-mics` to show all microphone devices
- `MICROPHONE_INDEX` config to specify which mic to use (needed when no default mic is set)

#### config.py / .env.example
- Added `WAKE_WORD` (default: "Twin")
- Added `VOICE_NAME` (default: "nova")
- Added `MICROPHONE_INDEX` (set to mic device number from --list-mics output)

#### tools/tts_tools.py
- Added `fmt` parameter — "opus" for Telegram, "mp3" for desktop playback

#### requirements.txt
- Added `sounddevice`, `soundfile`, `SpeechRecognition`, `numpy`

---

## 2026-05-06 (Session 3)

---

### Phase 3 | Web UI | Voice Control + Jarvis Features

**Files modified:** `web_app.py`, `templates/index.html`

#### web_app.py
- Added `POST /api/tts` endpoint — converts text to MP3 via OpenAI TTS, returns audio bytes
- Browser fetches this to auto-play Twin's responses aloud

#### templates/index.html — Full Voice-First Web UI
- **🎤 Mic button** — click to start listening via Web Speech API (Chrome/Edge native, free)
- **Waveform overlay** — full-screen animated waveform shown while listening, shows live transcript
- **Auto TTS** — after every response, browser fetches `/api/tts` and plays it aloud
- **"Speaking..." badge** — header indicator while Twin is speaking
- **6 quick-action chips** on welcome screen (weather, report, news, currency, entries, capabilities)
- **Animated typing indicator** — 3-dot bounce while AI is thinking
- **Dark theme** — deep space UI matching the AI assistant aesthetic
- Voice input flow: click mic → waveform appears → speak → transcript shown → auto-sends → Twin replies in text + audio

---

### Phase 3 | Web UI | Always-On Voice (No Click Required)

**Files modified:** `templates/index.html`

- Auto-starts microphone on page load — no button click needed
- Live interim transcript shown in input box as user speaks (greyed out)
- Auto-sends when user stops talking (browser VAD detects silence)
- After TTS response plays, mic restarts automatically
- Mic never runs while Twin is speaking (prevents feedback loop)
- Status bar replaces waveform overlay: shows 🎤 Listening / 🧠 Thinking / 🔊 Speaking state
- Mini waveform animation in status bar while listening
- "Voice ON/OFF" toggle button — one click to disable/re-enable
- Graceful fallback if mic permission denied

---

### Phase 3 | Web UI | Cross-Browser Voice (Brave compatible)

**Files modified:** `web_app.py`, `templates/index.html`

- **Root cause:** Web Speech API blocked in Brave by default (routes audio to Google — Brave's privacy shield blocks it)
- **Fix:** Replaced Web Speech API with `MediaRecorder` + `AudioContext` VAD — works in ALL browsers
- **How it works:**
  - `AudioContext.createAnalyser()` reads microphone volume 12x per second
  - When volume exceeds threshold → `MediaRecorder` starts capturing audio
  - When silence detected for 1.4s → recording stops → audio blob sent to `/api/transcribe`
  - `/api/transcribe` sends audio to OpenAI Whisper → returns transcript → auto-sends to AI
- **Added** `POST /api/transcribe` endpoint in `web_app.py` — accepts audio blob, returns Whisper transcript
- **Browser support:** Brave ✅  Chrome ✅  Edge ✅  Firefox ✅  Safari ✅
- **Bonus:** More accurate than Google STT, supports Uzbek/Russian/English automatically
- Volume bar in status strip shows live mic level so user knows it's picking them up

---

## 2026-05-07

---

### Phase 2 | Financial Agent | Complete Financial Tracking

**Files modified:** `tools/entry_tools.py`, `tools/registry.py`, `core/brain.py`, `bot/telegram_bot.py`
**Files created:** `bot/handlers/file_handler.py`

#### tools/entry_tools.py
- `save_entry` now always stamps `data["date"]` with today's date — queries by date now work correctly
- `save_entry` returns a rich confirmation string: emoji + category + item + amount + date
- Added `get_daily_summary(user_id, date)` — returns all transactions for a specific date with income/expense/net totals

#### tools/registry.py
- Registered `get_daily_summary` as AI-callable tool
- Trigger: "how much did I spend on 5th May", "show me today's transactions", "what did I buy yesterday"

#### core/brain.py — System Prompt
- Rule: save immediately when user mentions any financial data
- Rule: always reply with formatted ✅ confirmation after saving (category, item, amount, date)
- Rule: use `get_daily_summary` for specific date questions, `generate_report` for period questions
- Rule: read ALL items from receipt photos and save each transaction

#### bot/handlers/file_handler.py (new)
- Handles any document/file sent to Telegram bot
- Image files → vision (receipt reading)
- .txt / .csv → text extracted, parsed for transactions
- .pdf → text extracted from up to 3 pages (requires pypdf)
- .xlsx / .xls → rows read from first sheet (requires openpyxl)
- Unknown files → AI acknowledges and asks what to do

#### bot/telegram_bot.py
- Registered `file_handler` for `Document.ALL` (non-image documents)
