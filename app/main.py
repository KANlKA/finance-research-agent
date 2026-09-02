"""
Backend API entrypoint.

Run with:  uvicorn app.main:app --reload
Docs at:   http://localhost:8000/docs
"""
import json

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from app.agent.orchestrator import run_agent
from app.auth import authenticate_user, create_access_token, create_user, get_current_user
from app.conversation import (
    conversation_belongs_to_user,
    create_conversation,
    get_recent_messages,
    list_conversations,
)
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
    conversation_id: str | None = None  # omit to start a fresh, stateless query;
    # pass a previous response's conversation_id to continue that thread


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


# ---------- Conversations ----------
@app.post("/conversations")
def new_conversation(user=Depends(get_current_user)):
    """Start a new conversation thread. Pass the returned id as
    conversation_id on subsequent /agent/query calls to keep memory."""
    conv_id = create_conversation(user["id"])
    return {"conversation_id": conv_id}


@app.get("/conversations")
def get_conversations(user=Depends(get_current_user)):
    return {"conversations": list_conversations(user["id"])}


@app.get("/conversations/{conversation_id}/messages")
def get_conversation_messages(conversation_id: str, user=Depends(get_current_user)):
    if not conversation_belongs_to_user(conversation_id, user["id"]):
        raise HTTPException(404, "Conversation not found")
    return {"messages": get_recent_messages(conversation_id, limit=100)}


# ---------- Agent (streaming) ----------
@app.post("/agent/query")
def agent_query_stream(req: QueryRequest, user=Depends(get_current_user)):
    """
    Server-Sent Events stream. Each event is a JSON-encoded step from the
    multi-step reasoning loop: rag_context, tool_call, tool_result,
    final_answer, done. If conversation_id is provided, prior turns in that
    thread are used as context and this turn is appended to it.
    """
    if req.conversation_id and not conversation_belongs_to_user(req.conversation_id, user["id"]):
        raise HTTPException(404, "Conversation not found")

    def event_generator():
        for step in run_agent(req.question, user["id"], req.conversation_id):
            yield {"event": step["type"], "data": json.dumps(step, default=str)}

    return EventSourceResponse(event_generator())


@app.post("/agent/query_sync")
def agent_query_sync(req: QueryRequest, user=Depends(get_current_user)):
    """Non-streaming variant (simpler for curl / testing / eval)."""
    from app.agent.orchestrator import run_agent_sync

    if req.conversation_id and not conversation_belongs_to_user(req.conversation_id, user["id"]):
        raise HTTPException(404, "Conversation not found")

    return run_agent_sync(req.question, user["id"], req.conversation_id)


@app.get("/health")
def health():
    return {"status": "ok"}


# ---------- Browser chat UI ----------
# Mounted last, and only under /app, so it never shadows the API routes
# above (an exact-path API route always matches before a path-prefix mount).
app.mount("/app", StaticFiles(directory="static", html=True), name="static")