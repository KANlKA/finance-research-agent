"""
Market Data Tool - wraps yfinance (free, unauthenticated Yahoo Finance data).
No API key required. Cached to avoid hammering Yahoo and to keep the agent
fast on repeated questions about the same ticker.
"""
import yfinance as yf

from app.cache import cached
from app.config import HISTORY_CACHE_TTL, QUOTE_CACHE_TTL


@cached(ttl_seconds=QUOTE_CACHE_TTL, prefix="quote")
def get_quote(symbol: str) -> dict:
    symbol = symbol.upper().strip()
    t = yf.Ticker(symbol)
    fast = t.fast_info
    return {
        "symbol": symbol,
        "price": getattr(fast, "last_price", None),
        "previous_close": getattr(fast, "previous_close", None),
        "day_high": getattr(fast, "day_high", None),
        "day_low": getattr(fast, "day_low", None),
        "market_cap": getattr(fast, "market_cap", None),
        "currency": getattr(fast, "currency", None),
    }


@cached(ttl_seconds=HISTORY_CACHE_TTL, prefix="history")
def get_history(symbol: str, period: str = "1mo") -> dict:
    symbol = symbol.upper().strip()
    t = yf.Ticker(symbol)
    hist = t.history(period=period)
    if hist.empty:
        return {"symbol": symbol, "period": period, "closes": []}
    closes = [round(float(c), 2) for c in hist["Close"].tolist()]
    return {
        "symbol": symbol,
        "period": period,
        "closes": closes,
        "start": closes[0] if closes else None,
        "end": closes[-1] if closes else None,
        "pct_change": round((closes[-1] / closes[0] - 1) * 100, 2) if closes else None,
    }


TOOL_SPEC = {
    "name": "market_data",
    "description": "Get a live quote or recent price history for a stock ticker symbol.",
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["quote", "history"]},
            "symbol": {"type": "string", "description": "Ticker symbol, e.g. AAPL"},
            "period": {"type": "string", "description": "For history only, e.g. 1mo, 6mo, 1y"},
        },
        "required": ["action", "symbol"],
    },
}


def run(action: str, symbol: str, period: str = "1mo") -> dict:
    if action == "quote":
        return get_quote(symbol)
    elif action == "history":
        return get_history(symbol, period)
    raise ValueError(f"Unknown market_data action: {action}")
