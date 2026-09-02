"""
SEC Filings Tool - recent regulatory filings (10-K, 10-Q, 8-K, etc.) from
SEC EDGAR. Completely free, public, unauthenticated -- SEC only requires a
descriptive User-Agent header identifying the requester (their fair-access
policy, not a paid API).

Two-step lookup: ticker -> CIK (via SEC's company_tickers.json, cached for
a day since it rarely changes) -> that CIK's filing history.
"""
import httpx

from app.cache import cached

SEC_HEADERS = {
    # SEC's fair-access policy requires a descriptive User-Agent with a
    # real contact -- replace with your own app name/email in production.
    "User-Agent": "AI-Financial-Research-Agent contact@example.com"
}

TOOL_SPEC = {
    "name": "sec_filings",
    "description": (
        "Get a company's recent SEC filings (10-K annual report, 10-Q "
        "quarterly report, 8-K material event, etc.) with filing dates and "
        "links to the source documents on SEC EDGAR."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Ticker symbol, e.g. AAPL"},
            "form_type": {
                "type": "string",
                "description": "Optional filter, e.g. '10-K', '10-Q', '8-K'. Omit for all recent filings.",
            },
            "limit": {"type": "integer", "description": "Max filings to return", "default": 5},
        },
        "required": ["symbol"],
    },
}


@cached(ttl_seconds=86400, prefix="sec_ticker_map")
def _load_ticker_to_cik() -> dict:
    """SEC's canonical ticker -> CIK mapping. Refreshed daily via cache TTL."""
    resp = httpx.get("https://www.sec.gov/files/company_tickers.json", headers=SEC_HEADERS, timeout=20)
    resp.raise_for_status()
    raw = resp.json()
    return {row["ticker"].upper(): str(row["cik_str"]).zfill(10) for row in raw.values()}


@cached(ttl_seconds=3600, prefix="sec_filings")
def get_recent_filings(symbol: str, form_type: str = "", limit: int = 5) -> dict:
    symbol = symbol.upper().strip()
    ticker_map = _load_ticker_to_cik()
    cik = ticker_map.get(symbol)
    if not cik:
        return {"symbol": symbol, "error": f"No SEC CIK found for ticker {symbol}", "filings": []}

    resp = httpx.get(f"https://data.sec.gov/submissions/CIK{cik}.json", headers=SEC_HEADERS, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    recent = data.get("filings", {}).get("recent", {})

    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accessions = recent.get("accessionNumber", [])
    primary_docs = recent.get("primaryDocument", [])

    filings = []
    for form, date, accession, doc in zip(forms, dates, accessions, primary_docs):
        if form_type and form.upper() != form_type.upper():
            continue
        accession_nodash = accession.replace("-", "")
        filings.append(
            {
                "form": form,
                "filing_date": date,
                "url": f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_nodash}/{doc}",
            }
        )
        if len(filings) >= limit:
            break

    return {"symbol": symbol, "company_name": data.get("name"), "filings": filings}


def run(symbol: str, form_type: str = "", limit: int = 5) -> dict:
    return get_recent_filings(symbol, form_type, limit)