"""
News Search Tool - pulls from free, public RSS feeds (Yahoo Finance's
per-ticker RSS endpoint). No API key, no paid news API needed.
"""
import feedparser

from app.cache import cached
from app.config import NEWS_CACHE_TTL

YAHOO_RSS_TEMPLATE = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region=US&lang=en-US"


@cached(ttl_seconds=NEWS_CACHE_TTL, prefix="news")
def search_news(symbol: str, limit: int = 5) -> dict:
    symbol = symbol.upper().strip()
    url = YAHOO_RSS_TEMPLATE.format(symbol=symbol)
    feed = feedparser.parse(url)
    articles = []
    for entry in feed.entries[:limit]:
        articles.append(
            {
                "title": entry.get("title"),
                "link": entry.get("link"),
                "published": entry.get("published", ""),
                "summary": entry.get("summary", "")[:300],
            }
        )
    return {"symbol": symbol, "articles": articles}


TOOL_SPEC = {
    "name": "news_search",
    "description": "Search recent news headlines for a stock ticker.",
    "input_schema": {
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Ticker symbol, e.g. AAPL"},
            "limit": {"type": "integer", "description": "Max articles to return", "default": 5},
        },
        "required": ["symbol"],
    },
}


def run(symbol: str, limit: int = 5) -> dict:
    return search_news(symbol, limit)
