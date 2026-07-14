"""
core/memory.py
Smart memory system for Grace v3.

Strategy:
  1. Recency window  — last MEMORY_WINDOW messages always sent
  2. Semantic recall — embedding cosine-search for relevant older messages
  3. Auto-summary    — compress old messages every SUMMARY_THRESHOLD turns
"""

import math
import threading
from typing import List, Dict, Optional, Tuple
from core.config import cfg
from core import models as db
from utils.logger import log

# ── Embedding model ────────────────────────────────────────────────────────────

_embed_model = None
_embed_lock = threading.Lock()


def _get_embedder():
    global _embed_model
    if not cfg.ENABLE_SEMANTIC_MEMORY:
        return None
    with _embed_lock:
        if _embed_model is None:
            try:
                from sentence_transformers import SentenceTransformer
                log.info(f"Loading embedder from: {cfg.SENTENCE_TRANSFORMER_PATH}")
                _embed_model = SentenceTransformer(cfg.SENTENCE_TRANSFORMER_PATH)
                log.info("✅ Sentence transformer loaded")
            except Exception as e:
                log.warning(f"Embedder unavailable: {e}. Semantic memory disabled.")
    return _embed_model


def embed_text(text: str) -> Optional[List[float]]:
    m = _get_embedder()
    if m is None:
        return None
    try:
        return m.encode(text[:512], convert_to_numpy=True).tolist()
    except Exception as e:
        log.warning(f"Embedding failed: {e}")
        return None


def _cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


# ── Main memory class ──────────────────────────────────────────────────────────

class MemoryManager:

    def save_turn(
        self,
        conv_id: str,
        user_text: str,
        assistant_text: str,
        mode: str = "chat",
    ):
        """Persist both sides of a conversation turn."""
        user_emb = embed_text(user_text)
        asst_emb = embed_text(assistant_text)
        db.save_message(conv_id, "user", user_text, embedding=user_emb)
        db.save_message(
            conv_id,
            "assistant",
            assistant_text,
            embedding=asst_emb,
            meta={"mode": mode},
        )
        log.debug(f"Saved turn for conv {conv_id[:8]}")

    def build_context(
        self, conv_id: str, query: str
    ) -> Tuple[List[Dict[str, str]], str]:
        """
        Returns (recent_history, context_string).
        recent_history: list of {role, content} for the LLM messages array.
        context_string: extra context block injected into system prompt.
        """
        # 1. Recent window
        recent = db.get_recent_messages(conv_id, limit=cfg.MEMORY_WINDOW)
        history = [{"role": m["role"], "content": m["content"]} for m in recent]
        recent_ids = [m["id"] for m in recent]

        # 2. Latest summary
        summary_row = db.get_latest_summary(conv_id)
        summary_text = summary_row["summary"] if summary_row else ""

        # 3. Semantic recall
        semantic_hits = self._semantic_recall(conv_id, query, exclude_ids=recent_ids)

        # Build context string
        parts = []
        if summary_text:
            parts.append(f"Summary of earlier conversation:\n{summary_text}")
        if semantic_hits:
            parts.append(
                "Relevant past exchanges:\n"
                + "\n".join(
                    f"[{h['role']}]: {h['content'][:200]}" for h in semantic_hits
                )
            )

        return history, "\n\n".join(parts)

    def _semantic_recall(
        self,
        conv_id: str,
        query: str,
        exclude_ids: List[int],
        top_k: int = 3,
        threshold: float = 0.55,
    ) -> List[Dict]:
        q_emb = embed_text(query)
        if q_emb is None:
            return []
        candidates = db.get_messages_with_embeddings(conv_id, exclude_ids)
        scored = []
        for m in candidates:
            try:
                score = _cosine(q_emb, m["embedding"])
                if score >= threshold:
                    scored.append((score, m))
            except Exception:
                continue
        scored.sort(key=lambda x: x[0], reverse=True)
        return [{"role": m["role"], "content": m["content"]} for _, m in scored[:top_k]]

    def maybe_summarize(self, conv_id: str, complete_fn) -> bool:
        """
        If message count exceeds SUMMARY_THRESHOLD since last summary,
        generate a new rolling summary. Returns True if summarised.
        complete_fn: callable(prompt: str) -> str
        """
        total = db.count_messages(conv_id)
        last = db.get_latest_summary(conv_id)
        summarised_at = last["message_count_at"] if last else 0

        if (total - summarised_at) < cfg.SUMMARY_THRESHOLD:
            return False

        # Grab older messages (exclude recent window)
        older = db.get_all_messages(conv_id)
        to_summarise = older[: max(0, total - cfg.MEMORY_WINDOW)]
        if not to_summarise:
            return False

        transcript = "\n".join(
            f"{m['role'].upper()}: {m['content'][:300]}" for m in to_summarise
        )
        prompt = (
            "Summarise this conversation in 3-5 concise sentences. "
            "Capture key topics, decisions, and important details.\n\n"
            f"CONVERSATION:\n{transcript}\n\nSUMMARY:"
        )

        def _run():
            try:
                summary = complete_fn(prompt)
                if summary:
                    db.save_summary(conv_id, summary, total)
                    log.info(f"📝 Summarised conv {conv_id[:8]} at {total} messages")
            except Exception as e:
                log.warning(f"Summarisation failed: {e}")

        threading.Thread(target=_run, daemon=True).start()
        return True

    def auto_title(self, conv_id: str, first_message: str, complete_fn):
        """Generate and save a conversation title from the first user message."""
        def _run():
            try:
                prompt = (
                    f'Generate a concise 4-6 word title for a conversation '
                    f'starting with: "{first_message[:150]}". '
                    f'Reply with ONLY the title, no quotes or punctuation.'
                )
                title = complete_fn(prompt)
                if title:
                    db.update_conversation_title(conv_id, title.strip()[:80])
                    log.info(f"Title set: '{title.strip()}'")
            except Exception as e:
                log.warning(f"Auto-title failed: {e}")
        threading.Thread(target=_run, daemon=True).start()


# Singleton
memory = MemoryManager()
