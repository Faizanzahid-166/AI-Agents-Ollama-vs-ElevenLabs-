"""
core/models.py
Database schema creation and all CRUD queries for Grace v3.

Tables:
  users                 — user identity
  conversations         — chat sessions
  messages              — individual turns
  conversation_summaries— rolling summaries for long chats
"""

import uuid
import json
from datetime import datetime, timezone
from typing import Optional, List, Dict
from core.database import get_conn
from utils.logger import log


# ── Schema ─────────────────────────────────────────────────────────────────────

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL DEFAULT 'Friend',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS conversations (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title       TEXT NOT NULL DEFAULT 'New conversation',
    mode        TEXT NOT NULL DEFAULT 'chat',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_archived BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS ix_conv_user ON conversations(user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS messages (
    id              SERIAL PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL,
    content         TEXT NOT NULL,
    embedding       TEXT,          -- JSON-encoded float list
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    meta            TEXT           -- JSON metadata
);
CREATE INDEX IF NOT EXISTS ix_msg_conv ON messages(conversation_id, timestamp);

CREATE TABLE IF NOT EXISTS conversation_summaries (
    id                  SERIAL PRIMARY KEY,
    conversation_id     TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    summary             TEXT NOT NULL,
    message_count_at    INT NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


def init_schema():
    """Create all tables if they don't exist. Safe to call on every startup."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(CREATE_TABLES_SQL)
    log.info("✅ DB schema ready")


# ── Users ──────────────────────────────────────────────────────────────────────

def get_or_create_user(user_id: str, name: str = "Friend") -> Dict:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name FROM users WHERE id = %s", (user_id,))
            row = cur.fetchone()
            if row:
                return {"id": row[0], "name": row[1]}
            cur.execute(
                "INSERT INTO users(id, name) VALUES(%s, %s) RETURNING id, name",
                (user_id, name),
            )
            row = cur.fetchone()
            return {"id": row[0], "name": row[1]}


# ── Conversations ──────────────────────────────────────────────────────────────

def create_conversation(user_id: str, title: str = "New conversation", mode: str = "chat") -> str:
    get_or_create_user(user_id)
    conv_id = str(uuid.uuid4())
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO conversations(id, user_id, title, mode) VALUES(%s,%s,%s,%s)",
                (conv_id, user_id, title, mode),
            )
    return conv_id


def list_conversations(user_id: str) -> List[Dict]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, title, mode, updated_at
                   FROM conversations
                   WHERE user_id = %s AND is_archived = FALSE
                   ORDER BY updated_at DESC LIMIT 50""",
                (user_id,),
            )
            rows = cur.fetchall()
    return [{"id": r[0], "title": r[1], "mode": r[2], "updated_at": r[3]} for r in rows]


def update_conversation_title(conv_id: str, title: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE conversations SET title = %s WHERE id = %s",
                (title[:100], conv_id),
            )


def touch_conversation(conv_id: str):
    """Update the updated_at timestamp."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE conversations SET updated_at = NOW() WHERE id = %s",
                (conv_id,),
            )


def delete_conversation(conv_id: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM conversations WHERE id = %s", (conv_id,))


# ── Messages ───────────────────────────────────────────────────────────────────

def save_message(
    conv_id: str,
    role: str,
    content: str,
    embedding: Optional[List[float]] = None,
    meta: Optional[dict] = None,
) -> int:
    emb_json = json.dumps(embedding) if embedding else None
    meta_json = json.dumps(meta) if meta else None
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO messages(conversation_id, role, content, embedding, meta)
                   VALUES(%s,%s,%s,%s,%s) RETURNING id""",
                (conv_id, role, content, emb_json, meta_json),
            )
            msg_id = cur.fetchone()[0]
    touch_conversation(conv_id)
    return msg_id


def get_recent_messages(conv_id: str, limit: int = 6) -> List[Dict]:
    """Return last `limit` messages in chronological order."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, role, content, timestamp
                   FROM messages
                   WHERE conversation_id = %s
                   ORDER BY timestamp DESC LIMIT %s""",
                (conv_id, limit),
            )
            rows = cur.fetchall()
    return [
        {"id": r[0], "role": r[1], "content": r[2], "timestamp": r[3]}
        for r in reversed(rows)
    ]


def get_all_messages(conv_id: str) -> List[Dict]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, role, content, timestamp
                   FROM messages
                   WHERE conversation_id = %s
                   ORDER BY timestamp ASC""",
                (conv_id,),
            )
            rows = cur.fetchall()
    return [{"id": r[0], "role": r[1], "content": r[2], "timestamp": r[3]} for r in rows]


def get_messages_with_embeddings(conv_id: str, exclude_ids: List[int]) -> List[Dict]:
    """Fetch older messages that have embeddings, excluding recently used IDs."""
    placeholders = ",".join(["%s"] * len(exclude_ids)) if exclude_ids else "NULL"
    query = f"""
        SELECT id, role, content, embedding
        FROM messages
        WHERE conversation_id = %s
          AND embedding IS NOT NULL
          {"AND id NOT IN (" + placeholders + ")" if exclude_ids else ""}
        ORDER BY timestamp ASC
    """
    params = [conv_id] + exclude_ids if exclude_ids else [conv_id]
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
    result = []
    for r in rows:
        try:
            emb = json.loads(r[3]) if r[3] else None
        except Exception:
            emb = None
        if emb:
            result.append({"id": r[0], "role": r[1], "content": r[2], "embedding": emb})
    return result


def count_messages(conv_id: str) -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM messages WHERE conversation_id = %s", (conv_id,))
            return cur.fetchone()[0]


# ── Summaries ──────────────────────────────────────────────────────────────────

def save_summary(conv_id: str, summary: str, message_count: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO conversation_summaries(conversation_id, summary, message_count_at)
                   VALUES(%s,%s,%s)""",
                (conv_id, summary, message_count),
            )


def get_latest_summary(conv_id: str) -> Optional[Dict]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT summary, message_count_at
                   FROM conversation_summaries
                   WHERE conversation_id = %s
                   ORDER BY created_at DESC LIMIT 1""",
                (conv_id,),
            )
            row = cur.fetchone()
    if row:
        return {"summary": row[0], "message_count_at": row[1]}
    return None
