"""
Pluggable LLM client.

- "mock": a deterministic, rule-based planner. Zero cost, zero network,
  fully reproducible -- this is what makes the whole system runnable and
  testable for free without any API key. It implements the SAME interface
  a real tool-calling LLM would, so it's a genuine stand-in, not a fake.
- "groq": real tool-calling via Groq's free-tier, OpenAI-compatible API,
  used when GROQ_API_KEY is set.

Both return a normalized `LLMStep`: either a tool call to make, or a final
answer to stream back.
"""
import json
import re
from dataclasses import dataclass, field

from app.config import GROQ_API_KEY, GROQ_MODEL, LLM_PROVIDER


@dataclass
class LLMStep:
    kind: str  # "tool_call" | "final_answer"
    tool_name: str | None = None
    tool_input: dict = field(default_factory=dict)
    text: str = ""


TICKER_RE = re.compile(r"\b[A-Z]{1,5}\b")
COMMON_WORDS = {"I", "A", "THE", "IS", "OF", "TO", "IN", "MY", "ON", "AT", "IT"}


def _guess_symbol(text: str) -> str | None:
    for tok in TICKER_RE.findall(text.upper()):
        if tok not in COMMON_WORDS and len(tok) <= 5:
            return tok
    return None


class MockPlanner:
    """
    Rule-based ReAct-style planner. Deterministically decides which tool(s)
    to call based on keywords, then synthesizes a final answer from the
    accumulated tool results + retrieved RAG context. This mirrors exactly
    the control flow a real function-calling LLM would drive.
    """

    def next_step(self, question: str, history: list[dict], rag_context: list[dict]) -> LLMStep:
        q = question.lower()
        called = {h["tool"] for h in history if h.get("type") == "tool_result"}

        symbol = _guess_symbol(question)

        if any(k in q for k in ["portfolio", "holdings", "positions", "worth"]) and "portfolio" not in called:
            action = "value" if any(k in q for k in ["worth", "value", "gain", "loss"]) else "list"
            return LLMStep(kind="tool_call", tool_name="portfolio", tool_input={"action": action})

        if symbol and any(k in q for k in ["price", "quote", "trading at", "history", "chart"]) and "market_data" not in called:
            action = "history" if "history" in q or "chart" in q or "trend" in q else "quote"
            return LLMStep(kind="tool_call", tool_name="market_data", tool_input={"action": action, "symbol": symbol})

        if symbol and any(k in q for k in ["news", "headline", "happening", "announcement"]) and "news_search" not in called:
            return LLMStep(kind="tool_call", tool_name="news_search", tool_input={"symbol": symbol})

        if any(k in q for k in ["how many times", "log", "history of my questions", "asked"]) and "sql_query" not in called:
            return LLMStep(
                kind="tool_call",
                tool_name="sql_query",
                tool_input={"sql": "SELECT question, created_at FROM query_log ORDER BY created_at DESC LIMIT 10"},
            )

        calc_match = re.search(r"calculate ([\d\.\+\-\*/\(\)\s]+)", q)
        if calc_match and "calculator" not in called:
            return LLMStep(kind="tool_call", tool_name="calculator", tool_input={"expression": calc_match.group(1).strip()})

        # No more tools needed -> synthesize final answer.
        return LLMStep(kind="final_answer", text=self._synthesize(question, history, rag_context))

    def _synthesize(self, question: str, history: list[dict], rag_context: list[dict]) -> str:
        parts = [f"Here's what I found regarding: \"{question}\"\n"]
        for h in history:
            if h.get("type") != "tool_result":
                continue
            tool, data = h["tool"], h["result"]
            if "error" in data:
                parts.append(f"- {tool} lookup failed: {data['error']}")
                continue
            if tool == "market_data":
                if "closes" in data:
                    parts.append(
                        f"- {data['symbol']} moved from {data.get('start')} to {data.get('end')} "
                        f"over {data.get('period')} ({data.get('pct_change')}% change)."
                    )
                else:
                    parts.append(f"- {data['symbol']} is trading at {data.get('price')} {data.get('currency', '')}.")
            elif tool == "news_search":
                headlines = "; ".join(a["title"] for a in data.get("articles", [])[:3])
                parts.append(f"- Recent headlines for {data['symbol']}: {headlines or 'none found.'}")
            elif tool == "portfolio":
                if "total_value" in data:
                    parts.append(
                        f"- Portfolio total value: ${data['total_value']}, "
                        f"total gain/loss: ${data['total_gain_loss']}."
                    )
                else:
                    syms = ", ".join(h_["symbol"] for h_ in data.get("holdings", [])) or "no holdings on file"
                    parts.append(f"- Holdings: {syms}.")
            elif tool == "sql_query":
                parts.append(f"- Query returned {data['row_count']} row(s).")
            elif tool == "calculator":
                parts.append(f"- {data['expression']} = {data['result']}")

        if rag_context:
            parts.append("\nRelevant background:")
            for r in rag_context:
                parts.append(f"- {r['text']} (source: {r['id']}, relevance {r['score']})")

        parts.append(
            "\nThis is informational analysis, not personalized financial advice."
        )
        return "\n".join(parts)


def _build_react_prompt(question: str, history: list[dict], rag_context: list[dict]) -> str:
    ctx = "\n".join(f"[{r['id']}] {r['text']}" for r in rag_context)
    hist = json.dumps(history, default=str)
    return (
        f"You are a financial research assistant. Background knowledge:\n{ctx}\n\n"
        f"Tool call history so far: {hist}\n\nUser question: {question}\n"
        "Decide the next tool call, or give the final answer if you have enough info. "
        "Always note this is not personalized financial advice."
    )


def _anthropic_specs_to_openai(tool_specs: list[dict]) -> list[dict]:
    """Our internal tool spec {name, description, input_schema} -> OpenAI
    function-calling spec {type: function, function: {name, description, parameters}}.
    (Groq's API is OpenAI-compatible.)"""
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        }
        for t in tool_specs
    ]


class GroqPlanner:
    """
    Real tool-calling via Groq's OpenAI-compatible Chat Completions API.
    Free tier (mid-2026): ~30 requests/min, up to ~1,000-14,400 requests/day
    depending on model. Each agent turn (tool_call OR final_answer) is one
    request, so a typical question costs 2-4 requests (1-3 tool calls + 1
    final synthesis) -- comfortably within free-tier RPM/RPD for normal use,
    but bursts (e.g. the eval harness firing 8 questions back-to-back) can
    hit the per-minute cap. We retry 429s with backoff rather than failing
    the whole turn.
    """

    def __init__(self):
        import httpx

        self.client = httpx.Client(
            base_url="https://api.groq.com/openai/v1",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "content-type": "application/json"},
            timeout=60,
        )

    def next_step(self, question: str, history: list[dict], rag_context: list[dict], tool_specs: list[dict]) -> LLMStep:
        import time

        prompt = _build_react_prompt(question, history, rag_context)
        payload = {
            "model": GROQ_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "tools": _anthropic_specs_to_openai(tool_specs),
            "tool_choice": "auto",
            "max_tokens": 1024,
        }

        max_retries = 4
        backoff = 1.0
        resp = None
        for attempt in range(max_retries):
            resp = self.client.post("/chat/completions", json=payload)
            if resp.status_code != 429:
                break
            # Respect Retry-After if Groq sends one, otherwise exponential backoff.
            wait = float(resp.headers.get("retry-after", backoff))
            time.sleep(wait)
            backoff *= 2
        resp.raise_for_status()

        data = resp.json()
        message = data["choices"][0]["message"]
        tool_calls = message.get("tool_calls") or []
        if tool_calls:
            call = tool_calls[0]
            args = json.loads(call["function"]["arguments"] or "{}")
            return LLMStep(kind="tool_call", tool_name=call["function"]["name"], tool_input=args)
        return LLMStep(kind="final_answer", text=message.get("content") or "")


def get_planner():
    if LLM_PROVIDER == "groq" and GROQ_API_KEY:
        return GroqPlanner()
    return MockPlanner()