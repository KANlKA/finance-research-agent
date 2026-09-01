"""
Agent Orchestrator - the core multi-step reasoning loop.

Flow per query:
  1. Retrieve relevant context from the RAG vector store.
  2. Loop (bounded by MAX_STEPS): ask the planner (LLM) for the next step.
     - If it's a tool call: dispatch to the right tool, append the result
       to history, continue the loop.
     - If it's a final answer: stop.
  3. Log the full trace + latency to SQLite for evaluation/auditing.

Implemented as a generator so the API layer can stream each step to the
client via SSE as it happens, rather than waiting for the whole run.
"""
import json
import time

from app.agent.llm import get_planner
from app.rag.vector_store import get_store
from app.tools import calculator, market_data, news_search, portfolio, sql_tool
from app.db import get_conn

MAX_STEPS = 6

TOOL_REGISTRY = {
    "market_data": market_data,
    "news_search": news_search,
    "portfolio": portfolio,
    "sql_query": sql_tool,
    "calculator": calculator,
}

TOOL_SPECS = [m.TOOL_SPEC for m in TOOL_REGISTRY.values()]


def _dispatch_tool(tool_name: str, tool_input: dict, user_id: int) -> dict:
    if tool_name not in TOOL_REGISTRY:
        raise ValueError(f"Unknown tool: {tool_name}")
    module = TOOL_REGISTRY[tool_name]
    kwargs = dict(tool_input)
    if tool_name == "portfolio":
        kwargs["user_id"] = user_id
    return module.run(**kwargs)


def run_agent(question: str, user_id: int):
    """
    Generator yielding step dicts as the agent works, e.g.:
      {"type": "rag_context", "results": [...]}
      {"type": "tool_call", "tool": "market_data", "input": {...}}
      {"type": "tool_result", "tool": "market_data", "result": {...}, "cache_hit": bool}
      {"type": "final_answer", "text": "..."}
      {"type": "done", "latency_ms": 123.4}
    """
    start = time.time()
    planner = get_planner()
    store = get_store()

    rag_results = store.query(question)
    yield {"type": "rag_context", "results": rag_results}

    history = []
    final_text = ""

    for _ in range(MAX_STEPS):
        try:
            if planner.__class__.__name__ == "GroqPlanner":
                step = planner.next_step(question, history, rag_results, TOOL_SPECS)
            else:
                step = planner.next_step(question, history, rag_results)
        except Exception as e:
            final_text = f"I hit an error while reasoning about this: {e}"
            yield {"type": "final_answer", "text": final_text}
            break

        if step.kind == "tool_call":
            yield {"type": "tool_call", "tool": step.tool_name, "input": step.tool_input}
            try:
                result = _dispatch_tool(step.tool_name, step.tool_input, user_id)
                cache_hit = bool(result.pop("_cache_hit", False)) if isinstance(result, dict) else False
            except Exception as e:
                result = {"error": str(e)}
                cache_hit = False
            history.append({"type": "tool_result", "tool": step.tool_name, "result": result})
            yield {"type": "tool_result", "tool": step.tool_name, "result": result, "cache_hit": cache_hit}
        else:
            final_text = step.text
            yield {"type": "final_answer", "text": final_text}
            break
    else:
        final_text = "I reached the maximum number of reasoning steps without a final answer."
        yield {"type": "final_answer", "text": final_text}

    latency_ms = round((time.time() - start) * 1000, 1)
    conn = get_conn()
    conn.execute(
        "INSERT INTO query_log (user_id, question, answer, tool_trace, latency_ms) VALUES (?, ?, ?, ?, ?)",
        (user_id, question, final_text, json.dumps(history, default=str), latency_ms),
    )
    conn.commit()
    yield {"type": "done", "latency_ms": latency_ms}


def run_agent_sync(question: str, user_id: int) -> dict:
    """Non-streaming convenience wrapper, used by the eval harness."""
    trace = list(run_agent(question, user_id))
    final = next((s for s in trace if s["type"] == "final_answer"), {"text": ""})
    done = next((s for s in trace if s["type"] == "done"), {"latency_ms": None})
    tool_calls = [s["tool"] for s in trace if s["type"] == "tool_call"]
    return {
        "answer": final["text"],
        "tool_calls": tool_calls,
        "latency_ms": done["latency_ms"],
        "trace": trace,
    }
