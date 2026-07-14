"""
database/db.py
==============
PostgreSQL connection pool + schema initialisation.
Uses psycopg2. All DDL lives here — single source of truth.
"""

import logging
from contextlib import contextmanager
from typing import Optional, List, Dict, Any

import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor, execute_values

logger = logging.getLogger("jarvis.database")

# ─────────────────────────────────────────────────────────────────────────────
# Full PostgreSQL DDL — run once on startup
# ─────────────────────────────────────────────────────────────────────────────
SCHEMA_SQL = """
-- Enable pgvector extension for semantic similarity search
CREATE EXTENSION IF NOT EXISTS vector;

-- ── Chat history ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS chat_history (
    id          BIGSERIAL PRIMARY KEY,
    session_id  UUID NOT NULL DEFAULT gen_random_uuid(),
    role        VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content     TEXT NOT NULL,
    intent_type VARCHAR(50),
    embedding   vector(384),              -- sentence-transformer embedding
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_chat_history_session  ON chat_history (session_id);
CREATE INDEX IF NOT EXISTS idx_chat_history_created  ON chat_history (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_chat_history_emb      ON chat_history
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- ── User commands log ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_commands (
    id            BIGSERIAL PRIMARY KEY,
    raw_text      TEXT NOT NULL,
    intent_type   VARCHAR(50),
    intent_params JSONB,
    result_status VARCHAR(20) DEFAULT 'success',
    result_detail TEXT,
    executed_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_commands_intent    ON user_commands (intent_type);
CREATE INDEX IF NOT EXISTS idx_commands_executed  ON user_commands (executed_at DESC);

-- ── File operations audit log ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS file_operations (
    id           BIGSERIAL PRIMARY KEY,
    operation    VARCHAR(20) NOT NULL,   -- create|read|update|delete|move|organize
    source_path  TEXT,
    dest_path    TEXT,
    file_type    VARCHAR(20),
    file_size    BIGINT,
    success      BOOLEAN DEFAULT TRUE,
    error_msg    TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_file_ops_op       ON file_operations (operation);
CREATE INDEX IF NOT EXISTS idx_file_ops_created  ON file_operations (created_at DESC);

-- ── Tasks & reminders ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tasks (
    id           BIGSERIAL PRIMARY KEY,
    title        TEXT NOT NULL,
    description  TEXT,
    priority     SMALLINT DEFAULT 3 CHECK (priority BETWEEN 1 AND 5),
    status       VARCHAR(20) DEFAULT 'pending'
                     CHECK (status IN ('pending','in_progress','completed','cancelled')),
    due_date     DATE,
    due_time     TIME,
    tags         TEXT[],
    embedding    vector(384),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_tasks_status   ON tasks (status);
CREATE INDEX IF NOT EXISTS idx_tasks_due_date ON tasks (due_date);
CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks (priority DESC);

-- ── Memory snapshots (summarised context) ────────────────────────────────
CREATE TABLE IF NOT EXISTS memory_snapshots (
    id          BIGSERIAL PRIMARY KEY,
    summary     TEXT NOT NULL,
    source_type VARCHAR(30),             -- 'chat'|'task'|'file_activity'
    source_ids  BIGINT[],
    embedding   vector(384),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_memory_emb ON memory_snapshots
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);

-- ── User preferences ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_preferences (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed sensible defaults (idempotent)
INSERT INTO user_preferences (key, value) VALUES
    ('voice_enabled',       'false'),
    ('tts_enabled',         'false'),
    ('default_save_dir',    '~/Documents'),
    ('task_reminder_hours', '8'),
    ('theme',               'dark')
ON CONFLICT (key) DO NOTHING;

-- ── Daily activity summary (for "what did I do today") ───────────────────
CREATE TABLE IF NOT EXISTS activity_log (
    id           BIGSERIAL PRIMARY KEY,
    date         DATE NOT NULL DEFAULT CURRENT_DATE,
    activity     TEXT NOT NULL,
    category     VARCHAR(30),
    metadata     JSONB,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_activity_date ON activity_log (date DESC);
"""

# SCHEMA_SQL = """
# -- Enable UUID support
# CREATE EXTENSION IF NOT EXISTS pgcrypto;

# -- ── Chat history ──────────────────────────────────────────────────────────
# CREATE TABLE IF NOT EXISTS chat_history (
#     id          BIGSERIAL PRIMARY KEY,
#     session_id  UUID NOT NULL DEFAULT gen_random_uuid(),
#     role        VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
#     content     TEXT NOT NULL,
#     intent_type VARCHAR(50),

#     -- temporary replacement for pgvector
#     embedding   JSONB,

#     created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
# );

# CREATE INDEX IF NOT EXISTS idx_chat_history_session
# ON chat_history (session_id);

# CREATE INDEX IF NOT EXISTS idx_chat_history_created
# ON chat_history (created_at DESC);

# -- ── User commands log ──────────────────────────────────────────────────────
# CREATE TABLE IF NOT EXISTS user_commands (
#     id            BIGSERIAL PRIMARY KEY,
#     raw_text      TEXT NOT NULL,
#     intent_type   VARCHAR(50),
#     intent_params JSONB,
#     result_status VARCHAR(20) DEFAULT 'success',
#     result_detail TEXT,
#     executed_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
# );

# CREATE INDEX IF NOT EXISTS idx_commands_intent
# ON user_commands (intent_type);

# CREATE INDEX IF NOT EXISTS idx_commands_executed
# ON user_commands (executed_at DESC);

# -- ── File operations audit log ─────────────────────────────────────────────
# CREATE TABLE IF NOT EXISTS file_operations (
#     id           BIGSERIAL PRIMARY KEY,
#     operation    VARCHAR(20) NOT NULL,
#     source_path  TEXT,
#     dest_path    TEXT,
#     file_type    VARCHAR(20),
#     file_size    BIGINT,
#     success      BOOLEAN DEFAULT TRUE,
#     error_msg    TEXT,
#     created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
# );

# CREATE INDEX IF NOT EXISTS idx_file_ops_op
# ON file_operations (operation);

# CREATE INDEX IF NOT EXISTS idx_file_ops_created
# ON file_operations (created_at DESC);

# -- ── Tasks & reminders ─────────────────────────────────────────────────────
# CREATE TABLE IF NOT EXISTS tasks (
#     id           BIGSERIAL PRIMARY KEY,
#     title        TEXT NOT NULL,
#     description  TEXT,
#     priority     SMALLINT DEFAULT 3 CHECK (priority BETWEEN 1 AND 5),

#     status       VARCHAR(20) DEFAULT 'pending'
#         CHECK (status IN ('pending','in_progress','completed','cancelled')),

#     due_date     DATE,
#     due_time     TIME,
#     tags         TEXT[],

#     -- temporary replacement for pgvector
#     embedding    JSONB,

#     created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
#     updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
#     completed_at TIMESTAMPTZ
# );

# CREATE INDEX IF NOT EXISTS idx_tasks_status
# ON tasks (status);

# CREATE INDEX IF NOT EXISTS idx_tasks_due_date
# ON tasks (due_date);

# CREATE INDEX IF NOT EXISTS idx_tasks_priority
# ON tasks (priority DESC);

# -- ── Memory snapshots ──────────────────────────────────────────────────────
# CREATE TABLE IF NOT EXISTS memory_snapshots (
#     id          BIGSERIAL PRIMARY KEY,
#     summary     TEXT NOT NULL,
#     source_type VARCHAR(30),
#     source_ids  BIGINT[],

#     -- temporary replacement for pgvector
#     embedding   JSONB,

#     created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
# );

# -- ── User preferences ──────────────────────────────────────────────────────
# CREATE TABLE IF NOT EXISTS user_preferences (
#     key         TEXT PRIMARY KEY,
#     value       TEXT NOT NULL,
#     updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
# );

# INSERT INTO user_preferences (key, value)
# VALUES
#     ('voice_enabled', 'false'),
#     ('tts_enabled', 'false'),
#     ('default_save_dir', '~/Documents'),
#     ('task_reminder_hours', '8'),
#     ('theme', 'dark')
# ON CONFLICT (key) DO NOTHING;

# -- ── Daily activity summary ────────────────────────────────────────────────
# CREATE TABLE IF NOT EXISTS activity_log (
#     id           BIGSERIAL PRIMARY KEY,
#     date         DATE NOT NULL DEFAULT CURRENT_DATE,
#     activity     TEXT NOT NULL,
#     category     VARCHAR(30),
#     metadata     JSONB,
#     created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
# );

# CREATE INDEX IF NOT EXISTS idx_activity_date
# ON activity_log (date DESC);
# """

class Database:
    """Thread-safe connection pool wrapper."""

    def __init__(self, dsn: str, min_conn: int = 2, max_conn: int = 10):
        self.dsn = dsn
        self._pool: Optional[pool.ThreadedConnectionPool] = None
        self._min = min_conn
        self._max = max_conn

    def connect(self):
        if self._pool is None:
            try:
                self._pool = pool.ThreadedConnectionPool(
                    self._min,
                    self._max,
                    dsn=self.dsn,
                    cursor_factory=RealDictCursor,
                )
                logger.info("✅ PostgreSQL connection pool established.")
            except psycopg2.OperationalError as e:
                logger.error(f"❌ Cannot connect to PostgreSQL: {e}")
                raise

    def initialize_schema(self):
        """Create all tables/indexes if they don't exist yet."""
        self.connect()
        with self.cursor() as cur:
            cur.execute(SCHEMA_SQL)
        logger.info("✅ Database schema verified/applied.")

    @contextmanager
    def cursor(self, autocommit: bool = False):
        """Yield a cursor; auto-commit or rollback."""
        self.connect()
        conn = self._pool.getconn()
        try:
            conn.autocommit = autocommit
            with conn.cursor() as cur:
                yield cur
            if not autocommit:
                conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._pool.putconn(conn)

    # ── Convenience helpers ──────────────────────────────────────────────

    def execute(self, sql: str, params=None) -> None:
        with self.cursor() as cur:
            cur.execute(sql, params)

    def fetchone(self, sql: str, params=None) -> Optional[Dict]:
        with self.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()

    def fetchall(self, sql: str, params=None) -> List[Dict]:
        with self.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()

    def insert_returning(self, sql: str, params=None) -> Optional[Dict]:
        with self.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()

    def bulk_insert(self, sql: str, rows: List[tuple]) -> None:
        with self.cursor() as cur:
            execute_values(cur, sql, rows)

    def close(self):
        if self._pool:
            self._pool.closeall()
            logger.info("Database pool closed.")
