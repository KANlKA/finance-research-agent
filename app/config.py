"""
Central configuration. Everything is env-var driven so the same code runs
locally, in CI, or in a container without edits.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# Load variables from a .env file in the project root (if present) into the
# real process environment. Without this, values in .env are never seen by
# os.environ.get() below -- this was previously missing and silently caused
# LLM_PROVIDER/GROQ_API_KEY etc. from .env to be ignored.
load_dotenv(BASE_DIR / ".env")

# --- Auth ---
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-me-in-prod")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

# --- Storage ---
SQLITE_PATH = str(DATA_DIR / "finagent.db")
CACHE_DIR = str(DATA_DIR / "cache")

# --- LLM ---
# Provider is pluggable: "mock" (no key, deterministic rule-based planner,
# runs fully offline/free) or "groq" (free-tier real tool-calling LLM).
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "mock")

# Groq free tier (as of mid-2026): ~30 requests/min, ~1,000-14,400 requests/day
# depending on model. https://console.groq.com/docs/rate-limits -- always
# check the live page for current numbers.
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")

# --- Cache TTLs (seconds) ---
QUOTE_CACHE_TTL = 30
NEWS_CACHE_TTL = 300
HISTORY_CACHE_TTL = 3600

# --- RAG ---
VECTOR_TOP_K = 4
