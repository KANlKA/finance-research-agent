"""
Fundamentals Tool - company-level fundamental data (valuation ratios,
sector/industry, business summary) via yfinance. Free, no API key.
Complements market_data (price/history) with the "why" context an analyst
would want: what does this company do, how is it valued, what sector.
"""
import yfinance as yf

from app.cache import cached
from app.config import HISTORY_CACHE_TTL

TOOL_SPEC = {
    "name": "company_fundamentals",
    "description": (
        "Get fundamental data for a company: sector, industry, business "
        "summary, P/E ratio, EPS, dividend yield, 52-week range, and analyst "
        "target price. Use this for 'what does this company do' or "
        "valuation-style questions, not for live price (use market_data)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {"symbol": {"type": "string", "description": "Ticker symbol, e.g. AAPL"}},
        "required": ["symbol"],
    },
}


@cached(ttl_seconds=HISTORY_CACHE_TTL, prefix="fundamentals")
def get_fundamentals(symbol: str) -> dict:
    symbol = symbol.upper().strip()
    info = yf.Ticker(symbol).info
    return {
        "symbol": symbol,
        "short_name": info.get("shortName"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "summary": (info.get("longBusinessSummary") or "")[:600],
        "pe_ratio_trailing": info.get("trailingPE"),
        "pe_ratio_forward": info.get("forwardPE"),
        "eps_trailing": info.get("trailingEps"),
        "dividend_yield": info.get("dividendYield"),
        "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
        "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
        "analyst_target_price": info.get("targetMeanPrice"),
        "recommendation": info.get("recommendationKey"),
    }


def run(symbol: str) -> dict:
    return get_fundamentals(symbol)