"""
SQL Database Tool - lets the agent issue read-only SELECT queries against
the app's SQLite database (e.g. query_log, holdings) for analytical
questions like "how many times have I asked about NVDA this month".
Guarded in app.db.run_readonly_sql against writes/DDL.
"""
from app.db import run_readonly_sql

TOOL_SPEC = {
    "name": "sql_query",
    "description": (
        "Run a read-only SELECT query against the app database. Tables: "
        "holdings(id, user_id, symbol, shares, cost_basis, acquired_at), "
        "query_log(id, user_id, question, answer, tool_trace, latency_ms, created_at)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {"sql": {"type": "string", "description": "A SELECT statement"}},
        "required": ["sql"],
    },
}


def run(sql: str) -> dict:
    rows = run_readonly_sql(sql)
    return {"rows": rows, "row_count": len(rows)}
