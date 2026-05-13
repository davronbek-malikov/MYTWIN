from agents.news_agent import fetch_topic, fetch_all, TOPICS


async def get_news_briefing(topic: str = "all", max_articles: int = 3) -> str:
    """Fetch and return a formatted news briefing for Telegram."""
    max_articles = min(max(1, max_articles), 5)

    if topic == "all":
        results = await fetch_all()
    else:
        result = await fetch_topic(topic)
        results = [result]

    lines = []
    for t in results:
        if not t.get("articles"):
            continue
        lines.append(f"{t.get('emoji','📰')} *{t['name']}*")
        for a in t["articles"][:max_articles]:
            title = a["title"].replace("*", "").replace("[", "").replace("]", "")
            lines.append(f"• [{title}]({a['url']})")
            lines.append(f"  _{a['summary']}_")
            if a.get("source") or a.get("date"):
                lines.append(f"  `{a.get('source','')} · {a.get('date','')}`")
        lines.append("")

    if not lines:
        return "No news articles found right now. Try again in a moment."

    available = ", ".join(t["key"] for t in TOPICS)
    lines.append(f"_Topics: {available}_")
    return "\n".join(lines)
