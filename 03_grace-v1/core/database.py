"""
core/database.py
PostgreSQL connection management using psycopg2.
Provides a simple context-manager-based connection pool.
"""

import psycopg2
import psycopg2.pool
import psycopg2.extras
from contextlib import contextmanager
from utils.logger import log
from core.config import cfg


# Thread-safe connection pool (min 1, max 5 connections)
_pool: psycopg2.pool.ThreadedConnectionPool = None


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=5,
            host=cfg.DB_HOST,
            port=cfg.DB_PORT,
            dbname=cfg.DB_NAME,
            user=cfg.DB_USER,
            password=cfg.DB_PASSWORD,
            connect_timeout=5,
        )
        log.info("✅ PostgreSQL pool created")
    return _pool


@contextmanager
def get_conn():
    """
    Borrow a connection from the pool.
    Automatically commits on exit, rolls back on error.

    Usage:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(...)
    """
    pool = _get_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def check_connection() -> bool:
    """Return True if the database is reachable."""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return True
    except Exception as e:
        log.error(f"DB connection check failed: {e}")
        return False

def init_schema():
    """
    Create database tables if they do not exist.
    """
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

    with get_conn() as conn:
        with conn.cursor() as cur:
            # Detect existing conversations table columns
            cur.execute(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'conversations'
                """
            )
            rows = cur.fetchall()
            existing = {row[0]: row[1] for row in rows}

            needs_recreate = False
            # If updated_at is missing or id is not text, recreate canonical schema
            if "updated_at" not in existing:
                needs_recreate = True
            if "id" in existing and existing.get("id") != "text":
                needs_recreate = True

            if needs_recreate:
                log.warning("DB schema mismatch detected — recreating tables (this will erase local data)")
                cur.execute("DROP TABLE IF EXISTS conversation_summaries, messages, conversations, users CASCADE")
                cur.execute(CREATE_TABLES_SQL)
            else:
                # Safe to apply create-if-not-exists statements (indexes may reference updated_at)
                cur.execute(CREATE_TABLES_SQL)

    log.info("✅ Database schema initialized (canonical)")


def close_pool():
    global _pool
    if _pool:
        _pool.closeall()
        _pool = None
        log.info("PostgreSQL pool closed")
