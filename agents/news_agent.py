"""
News Agent — fetches and summarizes recent news across 5 topic areas.
All topics are fetched in parallel via asyncio.gather.
Results are cached in-memory for 30 minutes to avoid re-fetching.
"""
from __future__ import annotations

import asyncio
from datetime import datetime

from openai import AsyncOpenAI

import config
from utils.logger import logger

TOPICS = [
    {"key": "ai_llm",    "name": "AI & LLMs",           "emoji": "🤖", "color": "#6c63ff",
     "query": "artificial intelligence GPT-4 Claude Gemini LLM 2025 latest"},
    {"key": "ai_agents", "name": "AI Agents",            "emoji": "⚡", "color": "#00d4ff",
     "query": "AI agents autonomous systems agentic AI 2025"},
    {"key": "tech",      "name": "Modern Tech",          "emoji": "💡", "color": "#00e676",
     "query": "technology innovation breakthrough startups 2025"},
    {"key": "education", "name": "Education",            "emoji": "📚", "color": "#ff9800",
     "query": "education edtech online learning AI education 2025"},
    {"key": "faang",     "name": "Big Tech (FAANG+)",    "emoji": "🏢", "color": "#ff5252",
     "query": "Google Apple Meta Amazon Microsoft OpenAI Anthropic news 2025"},
    {"key": "asia_tech",    "name": "Asia Tech",              "emoji": "🌏", "color": "#e91e63",
     "query": "China Japan Korea technology AI startup innovation 2025"},
    {"key": "startups",     "name": "Startups",               "emoji": "🚀", "color": "#ff6d00",
     "query": "startup funding venture capital product launch 2025"},
    {"key": "new_software", "name": "New Software & Tools",   "emoji": "🛠️", "color": "#00bcd4",
     "query": "new app software launch product tool notion productivity 2025"},
    {"key": "new_llms",     "name": "New LLMs & Models",      "emoji": "🧠", "color": "#ab47bc",
     "query": "new LLM model release GPT Claude Gemini Llama mistral 2025"},
]

_cache: dict = {}
_CACHE_TTL = 1800  # 30 minutes


async def _raw_news(query: str, max_results: int = 6) -> list:
    from duckduckgo_search import DDGS

    def _sync():
        try:
            with DDGS() as ddgs:
                return list(ddgs.news(query, max_results=max_results))
        except Exception as e:
            logger.error(f"DDG news error: {e}")
            return []

    return await asyncio.to_thread(_sync)


async def _summarize(client: AsyncOpenAI, title: str, body: str) -> str:
    try:
        r = await client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You summarize news articles in exactly 2 clear sentences. "
                        "Be factual, concise, and highlight the most important insight."
                    ),
                },
                {"role": "user", "content": f"Title: {title}\n\n{body[:700]}"},
            ],
            max_tokens=110,
        )
        return r.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Summary error: {e}")
        return (body[:200] + "…") if len(body) > 200 else body


async def _fetch_topic(topic: dict) -> dict:
    raw = await _raw_news(topic["query"])
    if not raw:
        return {**topic, "articles": [], "fetched_str": datetime.now().strftime("%H:%M, %d %b"), "_ts": datetime.now().timestamp()}

    client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)

    summaries = await asyncio.gather(
        *[_summarize(client, a.get("title", ""), a.get("body", "")) for a in raw]
    )

    articles = []
    for a, summary in zip(raw, summaries):
        articles.append({
            "title":   a.get("title", ""),
            "summary": summary,
            "url":     a.get("url", "#"),
            "source":  a.get("source", "Unknown"),
            "date":    (a.get("date") or "")[:10],
        })

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
