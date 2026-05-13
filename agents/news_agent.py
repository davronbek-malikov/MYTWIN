"""
News Agent — fetches real news via Google News RSS and summarizes with Gemini.
All 9 topics are fetched in parallel via asyncio.gather.
Results are cached 30 minutes.
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

import httpx

import config
from utils.logger import logger

TOPICS = [
    {"key": "ai_llm",       "name": "AI & LLMs",           "emoji": "🤖", "color": "#6c63ff",
     "query": "artificial intelligence GPT Claude Gemini LLM news"},
    {"key": "ai_agents",    "name": "AI Agents",            "emoji": "⚡", "color": "#00d4ff",
     "query": "AI agents autonomous agentic latest news"},
    {"key": "tech",         "name": "Modern Tech",          "emoji": "💡", "color": "#00e676",
     "query": "technology innovation latest news today"},
    {"key": "education",    "name": "Education",            "emoji": "📚", "color": "#ff9800",
     "query": "education edtech online learning news"},
    {"key": "faang",        "name": "Big Tech (FAANG+)",    "emoji": "🏢", "color": "#ff5252",
     "query": "Google Apple Meta Amazon Microsoft OpenAI Anthropic news"},
    {"key": "asia_tech",    "name": "Asia Tech",            "emoji": "🌏", "color": "#e91e63",
     "query": "China Japan Korea technology AI startup news"},
    {"key": "startups",     "name": "Startups",             "emoji": "🚀", "color": "#ff6d00",
     "query": "startup funding venture capital product launch news"},
    {"key": "new_software", "name": "New Software & Tools", "emoji": "🛠️", "color": "#00bcd4",
     "query": "new software app tool product launch notion news"},
    {"key": "new_llms",     "name": "New LLMs & Models",    "emoji": "🧠", "color": "#ab47bc",
     "query": "new LLM AI model release announcement news"},
]

_cache: dict = {}
_CACHE_TTL = 1800  # 30 minutes

_RSS = "https://news.google.com/rss/search?q={q}+when:2d&hl=en-US&gl=US&ceid=US:en"
_HEADERS = {"User-Agent": "MyTwinNewsBot/1.0 (compatible; httpx)"}
_MAX_AGE_DAYS = 2  # secondary filter — skip anything still older than 2 days


# ── Fetch from Google News RSS ────────────────────────────────────────────

async def _fetch_rss(query: str, max_results: int = 8) -> list:
    """Fetch from Google News RSS and keep only articles ≤ 2 days old."""
    url = _RSS.format(q=query.replace(" ", "+"))
    try:
        async with httpx.AsyncClient(timeout=12, follow_redirects=True, headers=_HEADERS) as client:
            r = await client.get(url)
            r.raise_for_status()
        root = ElementTree.fromstring(r.content)
    except Exception as e:
        logger.error(f"RSS fetch/parse error for '{query}': {e}")
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=_MAX_AGE_DAYS)
    articles = []

    for item in root.findall(".//item")[:max_results]:
        title  = (item.findtext("title") or "").strip()
        link   = item.findtext("link") or ""
        pub    = item.findtext("pubDate") or ""
        src    = item.find("source")
        source = src.text.strip() if src is not None else "News"

        # Parse publish date and filter by age
        pub_dt = None
        date_str = ""
        try:
            pub_dt   = parsedate_to_datetime(pub)
            date_str = pub_dt.strftime("%Y-%m-%d")
        except Exception:
            date_str = pub[:10]

        # Skip if older than cutoff
        if pub_dt and pub_dt < cutoff:
            continue

        if title and link:
            articles.append({"title": title, "url": link, "source": source, "date": date_str})

    return articles


# ── Summarize with Gemini ─────────────────────────────────────────────────

async def _summarize_batch(articles: list, topic_name: str) -> list:
    """Summarize all articles in one OpenAI call (cheap, fast)."""
    if not articles:
        return []
    if not config.OPENAI_API_KEY:
        return [{**a, "summary": a["title"]} for a in articles]

    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)

    numbered = "\n".join(f"{i+1}. {a['title']}" for i, a in enumerate(articles))
    prompt = (
        f"These are recent news headlines about {topic_name}:\n\n{numbered}\n\n"
        "Write a 2-sentence factual summary for EACH headline. "
        "Sentence 1: what happened. Sentence 2: why it matters.\n"
        "Reply with ONLY numbered summaries:\n"
        "1. [summary]\n2. [summary]\netc."
    )
    try:
        r = await client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=600,
        )
        text = r.choices[0].message.content.strip()
        summaries: dict[int, str] = {}
        for line in text.splitlines():
            m = re.match(r"^(\d+)\.\s+(.+)$", line.strip())
            if m:
                summaries[int(m.group(1)) - 1] = m.group(2).strip()
        return [{**a, "summary": summaries.get(i, a["title"])} for i, a in enumerate(articles)]
    except Exception as e:
        logger.error(f"Summarize error: {e}")
        return [{**a, "summary": a["title"]} for a in articles]


# ── Public API ────────────────────────────────────────────────────────────

async def _fetch_topic(topic: dict) -> dict:
    articles_raw = await _fetch_rss(topic["query"])

    if not articles_raw:
        # Fallback: try DuckDuckGo
        try:
            from duckduckgo_search import DDGS
            def _ddg():
                with DDGS() as ddgs:
                    return list(ddgs.news(topic["query"], max_results=6))
            raw = await asyncio.to_thread(_ddg)
            articles_raw = [
                {"title": a.get("title", ""), "url": a.get("url", "#"),
                 "source": a.get("source", ""), "date": (a.get("date") or "")[:10]}
                for a in raw if a.get("title")
            ]
        except Exception as e:
            logger.error(f"DuckDuckGo fallback error: {e}")

    articles = await _summarize_batch(articles_raw, topic["name"])

    return {
        **topic,
        "articles":    articles,
        "fetched_str": datetime.now().strftime("%H:%M, %d %b"),
        "_ts":         datetime.now().timestamp(),
    }


async def fetch_topic(key: str) -> dict:
    topic = next((t for t in TOPICS if t["key"] == key), None)
    if not topic:
        return {"error": "Unknown topic", "articles": []}

    cached = _cache.get(key)
    if cached and (datetime.now().timestamp() - cached.get("_ts", 0)) < _CACHE_TTL:
        logger.info(f"News cache hit: {key}")
        return cached

    logger.info(f"Fetching news: {key}")
    result = await _fetch_topic(topic)
    _cache[key] = result
    return result


async def fetch_all() -> list:
    """Fetch all 9 topics in parallel."""
    return list(await asyncio.gather(*[fetch_topic(t["key"]) for t in TOPICS]))


def invalidate_cache(key: str | None = None) -> None:
    if key:
        _cache.pop(key, None)
    else:
        _cache.clear()
