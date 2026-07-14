"""
core/memory.py
==============
Persistent memory system backed by PostgreSQL + pgvector.
Uses sentence-transformers (local model) for embeddings.

Capabilities:
  • Store every interaction with a vector embedding
  • Semantic search: "what did I work on last week?"
  • Summarise recent activity for daily briefing
  • Retrieve relevant context for AI responses
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from sentence_transformers import SentenceTransformer, models

logger = logging.getLogger("jarvis.memory")

try:
    from sentence_transformers import SentenceTransformer
    ST_AVAILABLE = True
except ImportError:
    ST_AVAILABLE = False
    logger.warning("sentence-transformers not installed — embeddings disabled.")


class MemorySystem:
    """
    Handles all memory operations:
    - Storing interactions with embeddings
    - Semantic similarity search via pgvector
    - Context retrieval for AI engine
    """

    def __init__(self, db, settings):
        self.db = db
        self.settings = settings
        self._model = None
        self._load_model()
        logger.info("Memory system initialised.")

    # ------------------------------------------------------------------ #
    # Model loading
    # ------------------------------------------------------------------ #

    def _load_model(self):
        if not ST_AVAILABLE:
            logger.warning("Sentence-transformers not available.")
            return

        try:
            model_path = self.settings.SENTENCE_TRANSFORMER_PATH

            word_embedding_model = models.Transformer(model_path)

            pooling_model = models.Pooling(
               #word_embedding_model.get_word_embedding_dimension(),
                word_embedding_model.get_embedding_dimension(),
                pooling_mode="mean"
                #
            )

            self._model = SentenceTransformer(
                modules=[word_embedding_model, pooling_model]
            )

            logger.info("✅ Embedding model loaded (manual pooling)")

        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            self._model = None

    def embed(self, text: str) -> Optional[List[float]]:
        """Return a 384-dim float list, or None if model unavailable."""
        if self._model is None:
            return None
        try:
            vec = self._model.encode(text, normalize_embeddings=True)
            return vec.tolist()
        except Exception as e:
            logger.error(f"Embedding failed: {e}")
            return None

    # ------------------------------------------------------------------ #
    # Storing interactions
    # ------------------------------------------------------------------ #

    def store_interaction(
        self,
        role: str,
        content: str,
        intent_type: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Optional[int]:
        """Persist a chat turn with its embedding."""
        embedding = self.embed(content)
        emb_str = f"[{','.join(str(x) for x in embedding)}]" if embedding else None

        row = self.db.insert_returning(
    """
    INSERT INTO chat_history (role, content, intent_type, embedding, session_id)
    VALUES (%(role)s, %(content)s, %(intent_type)s, %(embedding)s, COALESCE(%(session_id)s::uuid, gen_random_uuid()))
    RETURNING id
    """,
    {
        "role": role,
        "content": content,
        "intent_type": intent_type,
        "embedding": embedding,   # ✅ raw list
        "session_id": session_id,
    },
)
        return row["id"] if row else None

    # ------------------------------------------------------------------ #
    # Retrieval
    # ------------------------------------------------------------------ #

    def get_recent_history(self, n: int = 10) -> List[Dict]:
        """Return last N chat turns, oldest first."""
        rows = self.db.fetchall(
            """
            SELECT id, role, content, created_at
            FROM chat_history
            ORDER BY created_at DESC
            LIMIT %(n)s
            """,
            {"n": n},
        )
        return list(reversed(rows))

    def semantic_search(self, query: str, top_k: int = None) -> List[Dict]:
        """
        Find the most semantically similar stored memories.
        Returns [{content, role, similarity, created_at}, …]
        """
        top_k = top_k or self.settings.MEMORY_TOP_K
        query_emb = self.embed(query)
        if query_emb is None:
            return self._fallback_keyword_search(query, top_k)

        emb_str = f"[{','.join(str(x) for x in query_emb)}]"
        rows = self.db.fetchall(
            """
            SELECT
                id,
                role,
                content,
                created_at,
                1 - (embedding <=> %(emb)s::vector) AS similarity
            FROM chat_history
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> %(emb)s::vector
            LIMIT %(k)s
            """,
            {"emb": emb_str, "k": top_k},
        )
        threshold = self.settings.MEMORY_SIMILARITY_THRESHOLD
        return [r for r in rows if r["similarity"] >= threshold]

    def semantic_search_response(self, query: str) -> str:
        """Human-readable answer to a memory query."""
        results = self.semantic_search(query)
        if not results:
            return "I don't have relevant memories for that. Try rephrasing?"

        lines = [f"Here's what I recall related to that:\n"]
        for r in results[:5]:
            ts = r["created_at"].strftime("%b %d %H:%M") if r.get("created_at") else "?"
            snippet = r["content"][:120].replace("\n", " ")
            lines.append(f"  [{ts}] ({r['role']}) {snippet}")
        return "\n".join(lines)

    def get_context_for_ai(self, current_query: str) -> List[Dict]:
        """
        Return blended context: recent turns + semantically relevant memories.
        Used by AIEngine to build response context.
        """
        recent = self.get_recent_history(self.settings.RESPONSE_MAX_CONTEXT)
        semantic = self.semantic_search(current_query, top_k=3)

        # De-duplicate by id
        seen = {r["id"] for r in recent}
        extra = [r for r in semantic if r["id"] not in seen]
        return recent + extra

    def get_activity_summary(self, days_back: int = 1) -> str:
        """
        Summarise what was discussed/done in the last N days.
        Used for "what did I work on today/yesterday?"
        """
        since = datetime.now() - timedelta(days=days_back)
        rows = self.db.fetchall(
            """
            SELECT role, content, created_at
            FROM chat_history
            WHERE created_at >= %(since)s
            ORDER BY created_at ASC
            """,
            {"since": since},
        )

        if not rows:
            period = "today" if days_back == 1 else f"the last {days_back} days"
            return f"No recorded activity for {period}."

        # Group user commands only
        commands = [r for r in rows if r["role"] == "user"]
        if not commands:
            return "I have assistant replies but no commands from you in that period."

        period = "today" if days_back == 1 else f"over the last {days_back} days"
        lines = [f"Here's a summary of your activity {period}:\n"]
        for c in commands[:15]:  # cap at 15
            ts = c["created_at"].strftime("%H:%M")
            snippet = c["content"][:80].replace("\n", " ")
            lines.append(f"  • [{ts}] {snippet}")

        if len(commands) > 15:
            lines.append(f"  … and {len(commands) - 15} more interactions.")
        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _fallback_keyword_search(self, query: str, top_k: int) -> List[Dict]:
        """Full-text keyword search when embeddings unavailable."""
        rows = self.db.fetchall(
            """
            SELECT id, role, content, created_at, 0.5 AS similarity
            FROM chat_history
            WHERE to_tsvector('english', content) @@ plainto_tsquery('english', %(q)s)
            ORDER BY created_at DESC
            LIMIT %(k)s
            """,
            {"q": query, "k": top_k},
        )
        return rows

    def store_memory_snapshot(self, summary: str, source_type: str, source_ids: List[int]):
        """Persist a summarised snapshot for long-term memory."""
        embedding = self.embed(summary)
        emb_str = f"[{','.join(str(x) for x in embedding)}]" if embedding else None
        self.db.execute(
            """
            INSERT INTO memory_snapshots (summary, source_type, source_ids, embedding)
            VALUES (%(summary)s, %(source_type)s, %(source_ids)s, %(embedding)s::vector)
            """,
            {
                "summary": summary,
                "source_type": source_type,
                "source_ids": source_ids,
                "embedding": emb_str,
            },
        )
