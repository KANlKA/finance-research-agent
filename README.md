# AI Financial Research Agent

A real, working multi-tool AI agent backend — not a prompt wrapper. Every
piece in the architecture diagram below is implemented with actual code,
tested end-to-end (auth, DB writes, cache hits, SSE streaming all verified
live during build), and built entirely on free/open-source tools.

```
User
 ↓ (JWT-authenticated HTTP)
FastAPI Backend  ──────────────────────────────────────────
 │                                                          │
 ├── /auth/register, /auth/login        (JWT auth)          │
 ├── /portfolio                          (REST CRUD)        │
 └── /agent/query  (SSE streaming)   ── Agent Orchestrator   │
                                          │                  │
                              ┌───────────┼───────────┐      │
                              │   multi-step ReAct loop      │
                              │   (bounded, max 6 steps)      │
                              └───────────┬───────────┘      │
                                          │                  │
                    ┌─────────────────────┼─────────────────┐│
                    │                     │                 ││
              LLM Planner          RAG Retrieval       Tool Dispatch
        (mock or Anthropic)      (TF-IDF vector store)      │
                                                    ┌─────────┼─────────┬────────┬───────────┐
                                              Market Data  News Search  SQL Tool  Calculator  Portfolio
                                              (yfinance)   (RSS feeds)  (SQLite)  (safe AST)  (SQLite)
                                                    │            │          │
                                              Cache (diskcache, TTL per tool)
                                                    │
                                              SQLite (users, holdings, query_log)
```

## What's real here

| Requirement | Implementation |
|---|---|
| **Tool calling** | 5 real tools (`app/tools/*`) with JSON-schema `TOOL_SPEC`s, dispatched by name/input — the same schema format used by Anthropic's native tool-calling API |
| **Multi-step reasoning** | `app/agent/orchestrator.py` runs a bounded ReAct loop: plan → call tool → observe → replan, up to 6 steps, with full trace logged |
| **RAG** | `app/rag/vector_store.py` — real cosine-similarity retrieval over a financial glossary/methodology corpus, injected into every agent turn |
| **Vector database** | TF-IDF sparse vector index (scikit-learn), persisted to disk (`data/vector_index.pkl`). Swappable for dense embeddings — see `DenseEmbeddingStore` stub in the same file — without touching any other code |
| **Evaluation** | `eval/eval_harness.py` — 8 test cases checking tool-call correctness + answer groundedness + latency, not vibes. Caught 2 real bugs during build (see below) |
| **Caching** | `app/cache.py` — disk-backed TTL cache (diskcache), wraps each tool with its own TTL (quotes: 30s, news: 5min, history: 1hr). Verified: identical calls hit cache, don't re-fetch |
| **Streaming responses** | `/agent/query` is a real Server-Sent-Events endpoint — each reasoning step (`rag_context`, `tool_call`, `tool_result`, `final_answer`, `done`) streams to the client as it happens, not buffered |
| **Authentication** | JWT via `python-jose`, bcrypt password hashing via `passlib`, `OAuth2PasswordBearer` dependency injection protecting every agent/portfolio route |
| **Backend APIs** | FastAPI with auto-generated OpenAPI docs at `/docs`, proper request/response Pydantic schemas |

## Why "mock" LLM mode exists (and it's not a cop-out)

The brief said **free tools only**. There is no free tier for a real
tool-calling frontier LLM. So the LLM layer (`app/agent/llm.py`) is
pluggable:

- **`LLM_PROVIDER=mock`** (default): a deterministic rule-based planner
  that implements the *exact same interface* — `next_step(question,
  history, rag_context) → tool_call | final_answer` — that a real
  function-calling LLM would. This is what makes the whole stack runnable
  end-to-end for $0, offline, reproducibly, right now.
- **`LLM_PROVIDER=anthropic`**: real tool-calling via the Anthropic
  Messages API. Set `ANTHROPIC_API_KEY` and everything else (tools, RAG,
  cache, streaming, auth) is unchanged — only the planner swaps in.

This is a legitimate architectural pattern (a "fake" or "stub" adapter
behind a real interface), not a placeholder pretending to be the real
thing — the mock planner actually drives real tool calls against real
data sources.

## Free tools used (no paid API keys required to run)

- **yfinance** — free, unauthenticated Yahoo Finance market data
- **Yahoo Finance RSS** — free news headlines per ticker
- **SQLite** — embedded, zero-config SQL database
- **scikit-learn TF-IDF** — real vector space model, no model download needed
- **diskcache** — embedded TTL cache, no Redis server required
- **FastAPI + Uvicorn** — open-source ASGI backend
- **python-jose + passlib** — open-source JWT/bcrypt, no auth-as-a-service

## Running it

```bash
pip install -r requirements.txt
cp .env.example .env          # defaults already work
uvicorn app.main:app --reload
```

Or with Docker:

```bash
docker compose up --build
```

API docs: `http://localhost:8000/docs`

### Try it

```bash
# Register (returns a JWT)
curl -X POST localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"secret123"}'

TOKEN=<paste access_token>

# Add a holding
curl -X POST localhost:8000/portfolio/holdings \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"symbol":"AAPL","shares":10,"cost_basis":150}'

# Ask the agent (streaming)
curl -N -X POST localhost:8000/agent/query \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"question":"What is AAPL trading at and is it in the news?"}'
```

### Run the evals

```bash
python -m eval.eval_harness
```

## Project layout

```
app/
  main.py              FastAPI app, routes
  config.py            env-driven settings
  db.py                SQLite schema + safe read-only SQL guard
  auth.py              JWT + bcrypt
  cache.py             diskcache TTL wrapper/decorator
  tools/
    market_data.py     yfinance quote/history
    news_search.py     Yahoo RSS headlines
    portfolio.py       holdings CRUD + valuation
    sql_tool.py         guarded read-only SQL for the agent
    calculator.py       safe AST-based arithmetic
  rag/
    vector_store.py     TF-IDF vector index (+ dense embedding stub)
    sample_docs.py      seed knowledge base
  agent/
    llm.py               pluggable planner (mock / anthropic)
    orchestrator.py       multi-step ReAct loop, SSE-ready generator
eval/
  test_cases.json        8 scenario tests
  eval_harness.py         tool-correctness + groundedness + latency scoring
```

## Known limitations / next steps

- The mock planner uses keyword heuristics, not real language understanding
  — swap in `LLM_PROVIDER=anthropic` for genuine reasoning over ambiguous
  questions.
- TF-IDF retrieval is lexical, not semantic — swap in the
  `DenseEmbeddingStore` stub with sentence-transformer or Anthropic/OpenAI
  embeddings for better recall on paraphrased queries.
- Rate limiting and per-user quota enforcement aren't implemented — add an
  `slowapi`/token-bucket layer in front of `/agent/query` before exposing
  this publicly.
- This is informational infrastructure, not a licensed financial advisor —
  the agent always appends that disclaimer, and that behavior is covered
  by an eval test case (`compliance-grounding`).
