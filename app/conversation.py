"""
Conversation memory - lets the agent remember prior turns within a
conversation, so follow-up questions like "what about last quarter?" or
"is that expensive?" resolve against what was just discussed, instead of
every query starting from zero context.

Each conversation is scoped to the user who owns it; ownership is checked
on every access so one user can never read or extend another's thread.
"""
import uuid

from app.db import get_conn

MAX_TURNS_IN_CONTEXT = 6  # most recent user/assistant turns fed back to the planner


def create_conversation(user_id: int) -> str:
    conv_id = str(uuid.uuid4())
    conn = get_conn()
    conn.execute("INSERT INTO conversations (id, user_id) VALUES (?, ?)", (conv_id, user_id))
    conn.commit()
    return conv_id


def conversation_belongs_to_user(conversation_id: str, user_id: int) -> bool:
    conn = get_conn()
    row = conn.execute(
        "SELECT 1 FROM conversations WHERE id = ? AND user_id = ?", (conversation_id, user_id)
    ).fetchone()
    return row is not None


def append_message(conversation_id: str, role: str, content: str):
    conn = get_conn()
    conn.execute(
        "INSERT INTO conversation_messages (conversation_id, role, content) VALUES (?, ?, ?)",
        (conversation_id, role, content),
    )
    conn.commit()


def get_recent_messages(conversation_id: str, limit: int = MAX_TURNS_IN_CONTEXT * 2) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT role, content FROM conversation_messages WHERE conversation_id = ? "
        "ORDER BY id DESC LIMIT ?",
        (conversation_id, limit),
    ).fetchall()
    return [dict(r) for r in reversed(rows)]  # chronological order


def format_history_for_prompt(conversation_id: str) -> str:
    """Short, readable transcript to prepend to the planner's prompt."""
    messages = get_recent_messages(conversation_id)
    if not messages:
        return ""
    lines = [f"{m['role'].capitalize()}: {m['content']}" for m in messages]
    return "Prior conversation:\n" + "\n".join(lines) + "\n"


def list_conversations(user_id: int) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, title, created_at FROM conversations WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]