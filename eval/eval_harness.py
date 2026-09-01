"""
Evaluation harness.

Not a "vibes-based" eval -- it checks three concrete, automatable things
per test case:
  1. Tool-call correctness: did the agent invoke (a superset of) the tools
     we expect for this question?
  2. Groundedness / keyword coverage: does the final answer mention the
     expected entities/keywords (catches hallucination-by-omission)?
  3. Latency: how long did the full multi-step loop take?

Run:  python -m eval.eval_harness
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.auth import authenticate_user, create_user
from app.db import get_conn, init_db
from app.agent.orchestrator import run_agent_sync
from app.tools.portfolio import add_holding

TEST_CASES_PATH = Path(__file__).parent / "test_cases.json"


def _ensure_eval_user() -> int:
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE username = ?", ("eval_user",)).fetchone()
    if row:
        return row["id"]
    uid = create_user("eval_user", "eval_password_123")
    add_holding(uid, "AAPL", 10, 150.0)
    add_holding(uid, "MSFT", 5, 300.0)
    conn = get_conn()
    conn.execute(
        "INSERT INTO query_log (user_id, question, answer, tool_trace, latency_ms) VALUES (?, 'seed question', 'seed answer', '[]', 10)",
        (uid,),
    )
    conn.commit()
    return uid


def run_eval() -> dict:
    init_db()
    user_id = _ensure_eval_user()
    cases = json.loads(TEST_CASES_PATH.read_text())

    results = []
    for i, case in enumerate(cases):
        if i > 0:
            time.sleep(2)  # pace requests to stay under free-tier RPM limits
        t0 = time.time()
        out = run_agent_sync(case["question"], user_id)
        elapsed_ms = round((time.time() - t0) * 1000, 1)

        expected_tools = set(case["expected_tools"])
        actual_tools = set(out["tool_calls"])
        tool_pass = expected_tools.issubset(actual_tools) if expected_tools else True

        answer_lower = out["answer"].lower()
        keyword_hits = [kw for kw in case["expect_keywords"] if kw.lower() in answer_lower]
        keyword_pass = len(keyword_hits) > 0

        results.append(
            {
                "id": case["id"],
                "question": case["question"],
                "expected_tools": sorted(expected_tools),
                "actual_tools": sorted(actual_tools),
                "tool_pass": tool_pass,
                "keyword_pass": keyword_pass,
                "keyword_hits": keyword_hits,
                "latency_ms": elapsed_ms,
                "answer_preview": out["answer"][:160],
                "overall_pass": tool_pass and keyword_pass,
            }
        )

    total = len(results)
    passed = sum(1 for r in results if r["overall_pass"])
    avg_latency = round(sum(r["latency_ms"] for r in results) / total, 1) if total else 0

    report = {
        "total_cases": total,
        "passed": passed,
        "pass_rate": round(passed / total, 3) if total else 0,
        "avg_latency_ms": avg_latency,
        "results": results,
    }
    return report


def print_report(report: dict):
    print(f"\n=== Eval Report: {report['passed']}/{report['total_cases']} passed "
          f"({report['pass_rate']*100:.1f}%), avg latency {report['avg_latency_ms']}ms ===\n")
    for r in report["results"]:
        status = "PASS" if r["overall_pass"] else "FAIL"
        print(f"[{status}] {r['id']:<22} tools={r['actual_tools']} "
              f"(expected {r['expected_tools']})  {r['latency_ms']}ms")
        if not r["overall_pass"]:
            print(f"        answer: {r['answer_preview']!r}")


if __name__ == "__main__":
    report = run_eval()
    print_report(report)
    out_path = Path(__file__).parent / "last_report.json"
    out_path.write_text(json.dumps(report, indent=2))
    print(f"\nFull report written to {out_path}")