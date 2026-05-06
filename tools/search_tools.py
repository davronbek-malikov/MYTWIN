import asyncio
import httpx
from utils.logger import logger


async def web_search(query: str, max_results: int = 5) -> str:
    try:
        from duckduckgo_search import DDGS

        def _search():
            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=max_results):
                    results.append(f"• {r['title']}\n  {r['body'][:180]}\n  {r['href']}")
            return results

        results = await asyncio.to_thread(_search)
        if not results:
            return "No results found."
        return f"Search: '{query}'\n\n" + "\n\n".join(results)
    except Exception as e:
        logger.error(f"Web search error: {e}")
        return f"Search failed: {e}"


async def get_weather(city: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"https://wttr.in/{city}?format=3&lang=en")
            if r.status_code == 200:
                return r.text.strip()
            return f"Could not get weather for {city}."
    except Exception as e:
        logger.error(f"Weather error: {e}")
        return f"Weather check failed: {e}"


async def get_news(topic: str = "latest news", max_results: int = 5) -> str:
    try:
        from duckduckgo_search import DDGS

        def _news():
            results = []
            with DDGS() as ddgs:
                for r in ddgs.news(topic, max_results=max_results):
                    body = r.get("body", "")[:150]
                    results.append(f"• {r['title']}\n  {body}\n  Source: {r['source']}")
            return results

        results = await asyncio.to_thread(_news)
        if not results:
            return "No news found."
        return f"News: '{topic}'\n\n" + "\n\n".join(results)
    except Exception as e:
        logger.error(f"News error: {e}")
        return f"News fetch failed: {e}"


async def convert_currency(amount: float, from_currency: str, to_currency: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://api.frankfurter.app/latest",
                params={
                    "from": from_currency.upper(),
                    "to": to_currency.upper(),
                    "amount": amount,
                },
            )
            if r.status_code == 200:
                data = r.json()
                result = data["rates"][to_currency.upper()]
                return f"{amount:,.2f} {from_currency.upper()} = {result:,.2f} {to_currency.upper()}"
            return "Currency conversion failed."
    except Exception as e:
        logger.error(f"Currency error: {e}")
        return f"Conversion failed: {e}"
