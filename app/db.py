"""
SQLite persistence layer. This doubles as the "SQL Database Tool" backing
store the agent queries for portfolio / holdings questions.
"""
import sqlite3
import threading
from contextlib import contextmanager

from app.config import SQLITE_PATH

_local = threading.local()

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS holdings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    shares REAL NOT NULL,
    cost_basis REAL NOT NULL,
    acquired_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS query_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    question TEXT,
    answer TEXT,
    tool_trace TEXT,
    latency_ms REAL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def get_conn() -> sqlite3.Connection:
    """One connection per thread (SQLite connections aren't thread-safe)."""
    if not hasattr(_local, "conn"):
        conn = sqlite3.connect(SQLITE_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        _local.conn = conn
    return _local.conn


def init_db():
    conn = get_conn()
    conn.executescript(SCHEMA)
    conn.commit()


@contextmanager
def tx():
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def run_readonly_sql(sql: str, params: tuple = ()) -> list[dict]:
    """
    Executes a read-only query for the agent's SQL tool. Rejects anything
    that isn't a SELECT to prevent the agent (or a prompt-injected doc) from
    mutating data.
    """
    normalized = sql.strip().lower()
    if not normalized.startswith("select"):
        raise ValueError("Only SELECT statements are permitted via the SQL tool.")
    forbidden = ["insert", "update", "delete", "drop", "alter", "attach", "pragma"]
    if any(f in normalized for f in forbidden):
        raise ValueError("Query contains a forbidden keyword.")
    conn = get_conn()
    cur = conn.execute(sql, params)
    rows = [dict(r) for r in cur.fetchall()]
    return rows
