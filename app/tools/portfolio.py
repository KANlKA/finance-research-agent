"""
Portfolio Tool - manages a user's holdings in SQLite and values them using
live quotes from the market data tool.
"""
from app.db import get_conn
from app.tools.market_data import get_quote

TOOL_SPEC = {
    "name": "portfolio",
    "description": "View or value the current user's stock holdings.",
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["list", "value", "add"]},
            "symbol": {"type": "string"},
            "shares": {"type": "number"},
            "cost_basis": {"type": "number"},
        },
        "required": ["action"],
    },
}


def add_holding(user_id: int, symbol: str, shares: float, cost_basis: float):
    conn = get_conn()
    conn.execute(
        "INSERT INTO holdings (user_id, symbol, shares, cost_basis) VALUES (?, ?, ?, ?)",
        (user_id, symbol.upper(), shares, cost_basis),
    )
    conn.commit()


def list_holdings(user_id: int) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT symbol, shares, cost_basis, acquired_at FROM holdings WHERE user_id = ?",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def value_portfolio(user_id: int) -> dict:
    holdings = list_holdings(user_id)
    lines = []
    total_value = 0.0
    total_cost = 0.0
    for h in holdings:
        quote = get_quote(h["symbol"])
        price = quote.get("price") or 0
        market_value = price * h["shares"]
        cost = h["cost_basis"] * h["shares"]
        total_value += market_value
        total_cost += cost
        lines.append(
            {
                "symbol": h["symbol"],
                "shares": h["shares"],
                "price": price,
                "market_value": round(market_value, 2),
                "cost_basis_total": round(cost, 2),
                "gain_loss": round(market_value - cost, 2),
            }
        )
    return {
        "holdings": lines,
        "total_value": round(total_value, 2),
        "total_cost": round(total_cost, 2),
        "total_gain_loss": round(total_value - total_cost, 2),
    }


def run(action: str, user_id: int, symbol: str = "", shares: float = 0, cost_basis: float = 0):
    if action == "list":
        return {"holdings": list_holdings(user_id)}
    elif action == "value":
        return value_portfolio(user_id)
    elif action == "add":
        add_holding(user_id, symbol, shares, cost_basis)
        return {"status": "added", "symbol": symbol.upper(), "shares": shares}
    raise ValueError(f"Unknown portfolio action: {action}")
