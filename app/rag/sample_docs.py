"""
Seed corpus for the RAG index: financial concepts, glossary, and methodology
notes the agent grounds its answers in. In a real deployment you'd ingest
10-Ks, earnings call transcripts, and analyst notes here via ingest.py.
"""

SAMPLE_DOCS = [
    {
        "id": "glossary-pe-ratio",
        "text": (
            "Price-to-earnings (P/E) ratio is a company's share price divided by its "
            "earnings per share. A high P/E can indicate the market expects higher "
            "future growth, or that the stock is overvalued relative to earnings. "
            "It should be compared against sector peers and historical averages, not "
            "used in isolation."
        ),
        "metadata": {"topic": "valuation"},
    },
    {
        "id": "glossary-market-cap",
        "text": (
            "Market capitalization is share price multiplied by shares outstanding. "
            "It is commonly used to bucket companies into large-cap (>$10B), "
            "mid-cap ($2B-$10B), and small-cap (<$2B) categories, which correlates "
            "with volatility and liquidity."
        ),
        "metadata": {"topic": "valuation"},
    },
    {
        "id": "methodology-diversification",
        "text": (
            "Diversification reduces unsystematic (company-specific) risk by holding "
            "assets whose returns are not perfectly correlated. It does not eliminate "
            "systematic (market-wide) risk. A common rule of thumb is to avoid any "
            "single position exceeding 5-10% of a portfolio unless the investor has "
            "a high risk tolerance and conviction."
        ),
        "metadata": {"topic": "risk"},
    },
    {
        "id": "methodology-dollar-cost-averaging",
        "text": (
            "Dollar-cost averaging means investing a fixed amount at regular "
            "intervals regardless of price, which smooths out the average purchase "
            "price over time and reduces the risk of poor market timing, at the cost "
            "of potentially lower returns versus a lump sum in a rising market."
        ),
        "metadata": {"topic": "strategy"},
    },
    {
        "id": "glossary-gain-loss",
        "text": (
            "Unrealized gain/loss is the difference between a holding's current "
            "market value and its cost basis while still held. It becomes a realized "
            "gain/loss, and a taxable event in most jurisdictions, only once the "
            "position is sold."
        ),
        "metadata": {"topic": "tax"},
    },
    {
        "id": "risk-disclaimer",
        "text": (
            "This system provides informational analysis only. It is not a licensed "
            "financial advisor, does not know an individual's full financial "
            "situation, and its output should not be treated as personalized "
            "investment advice. Past performance does not guarantee future results."
        ),
        "metadata": {"topic": "compliance"},
    },
    {
        "id": "methodology-earnings-surprise",
        "text": (
            "An earnings surprise is the difference between a company's reported EPS "
            "and the consensus analyst estimate. Positive surprises often, but not "
            "always, produce short-term upward price moves; the magnitude depends on "
            "forward guidance and how the beat was achieved (revenue growth vs. cost "
            "cutting)."
        ),
        "metadata": {"topic": "earnings"},
    },
]
