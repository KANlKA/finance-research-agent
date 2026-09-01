"""
Backend API entrypoint.

Run with:  uvicorn app.main:app --reload
Docs at:   http://localhost:8000/docs
"""
import json

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sse_starlette.sse import EventSourceResponse

from app.agent.orchestrator import run_agent
from app.auth import authenticate_user, create_access_token, create_user, get_current_user
from app.db import init_db
from app.tools import portfolio as portfolio_tool
from pydantic import BaseModel

app = FastAPI(title="AI Financial Research Agent", version="1.0")


@app.on_event("startup")
def startup():
    init_db()


# ---------- Schemas ----------
class RegisterRequest(BaseModel):
    username: str
    password: str


class HoldingRequest(BaseModel):
    symbol: str
    shares: float
    cost_basis: float


class QueryRequest(BaseModel):
    question: str


# ---------- Auth ----------
@app.post("/auth/register")
def register(req: RegisterRequest):
    try:
        user_id = create_user(req.username, req.password)
    except Exception:
        raise HTTPException(400, "Username already taken")
    token = create_access_token(req.username)
    return {"user_id": user_id, "access_token": token, "token_type": "bearer"}


@app.post("/auth/login")
def login(form: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form.username, form.password)
    if not user:
        raise HTTPException(401, "Invalid credentials")
    token = create_access_token(user["username"])
    return {"access_token": token, "token_type": "bearer"}


# ---------- Portfolio ----------
@app.get("/portfolio")
def get_portfolio(user=Depends(get_current_user)):
    return portfolio_tool.value_portfolio(user["id"])


@app.post("/portfolio/holdings")
def add_holding(req: HoldingRequest, user=Depends(get_current_user)):
    portfolio_tool.add_holding(user["id"], req.symbol, req.shares, req.cost_basis)
    return {"status": "ok"}


# ---------- Agent (streaming) ----------
@app.post("/agent/query")
def agent_query_stream(req: QueryRequest, user=Depends(get_current_user)):
    """
    Server-Sent Events stream. Each event is a JSON-encoded step from the
    multi-step reasoning loop: rag_context, tool_call, tool_result,
    final_answer, done.
    """

    def event_generator():
        for step in run_agent(req.question, user["id"]):
            yield {"event": step["type"], "data": json.dumps(step, default=str)}

    return EventSourceResponse(event_generator())


@app.post("/agent/query_sync")
def agent_query_sync(req: QueryRequest, user=Depends(get_current_user)):
    """Non-streaming variant (simpler for curl / testing / eval)."""
    from app.agent.orchestrator import run_agent_sync

    return run_agent_sync(req.question, user["id"])


@app.get("/health")
def health():
    return {"status": "ok"}
