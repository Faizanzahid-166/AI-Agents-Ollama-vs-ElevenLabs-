"""
services/memory_service.py – Smart memory: recency window + summaries + semantic search
Never sends full history to LLM. Smart context injection only.
"""
import json
import math
import logging
from typing import List, Dict, Optional, Tuple
from sqlalchemy import select, delete, desc, func as sqlfunc
from sqlalchemy.ext.asyncio import AsyncSession

from models import User, Conversation, Message, ConversationSummary
from config import settings

logger = logging.getLogger("grace")

_embed_model = None

def _get_embedder():
    global _embed_model
    if _embed_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _embed_model = SentenceTransformer(settings.SENTENCE_TRANSFORMER_PATH)
            logger.info("✅ Sentence transformer loaded")
        except Exception as e:
            logger.warning(f"Embedder unavailable: {e}")
    return _embed_model

def _embed(text: str) -> Optional[List[float]]:
    m = _get_embedder()
    if m is None:
        return None
    try:
        return m.encode(text[:512], convert_to_numpy=True).tolist()
    except Exception:
        return None

def _cosine(a, b) -> float:
    dot = sum(x*y for x,y in zip(a,b))
    na = math.sqrt(sum(x*x for x in a))
    nb = math.sqrt(sum(x*x for x in b))
    return dot / (na * nb) if na and nb else 0.0


class MemoryService:

    # ── Users ─────────────────────────────────────────────────────────────────
    async def get_or_create_user(self, db: AsyncSession, user_id: str, name: str = "Friend") -> User:
        r = await db.execute(select(User).where(User.id == user_id))
        user = r.scalar_one_or_none()
        if not user:
            user = User(id=user_id, name=name)
            db.add(user)
            await db.flush()
        return user

    # ── Conversations ─────────────────────────────────────────────────────────
    async def create_conversation(self, db: AsyncSession, user_id: str, title: str = "New conversation", mode: str = "chat") -> Conversation:
        await self.get_or_create_user(db, user_id)
        conv = Conversation(user_id=user_id, title=title, mode=mode)
        db.add(conv)
        await db.flush()
        return conv

    async def get_conversation(self, db: AsyncSession, conv_id: str) -> Optional[Conversation]:
        r = await db.execute(select(Conversation).where(Conversation.id == conv_id))
        return r.scalar_one_or_none()

    async def list_conversations(self, db: AsyncSession, user_id: str) -> List[Dict]:
        r = await db.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id, Conversation.is_archived == False)
            .order_by(desc(Conversation.updated_at))
            .limit(50)
        )
        convs = r.scalars().all()
        return [{"id": c.id, "title": c.title, "mode": c.mode, "updated_at": c.updated_at.isoformat()} for c in convs]

    async def update_conversation_title(self, db: AsyncSession, conv_id: str, title: str):
        r = await db.execute(select(Conversation).where(Conversation.id == conv_id))
        conv = r.scalar_one_or_none()
        if conv:
            conv.title = title[:80]
            await db.flush()

    # ── Messages ──────────────────────────────────────────────────────────────
    async def save_message(self, db: AsyncSession, conv_id: str, role: str, content: str, meta: dict = None) -> Message:
        emb = _embed(content)
        msg = Message(conversation_id=conv_id, role=role, content=content, embedding=emb, meta=meta)
        db.add(msg)
        await db.flush()
        # Update conversation timestamp
        r = await db.execute(select(Conversation).where(Conversation.id == conv_id))
        conv = r.scalar_one_or_none()
        if conv:
            from datetime import datetime, timezone
            conv.updated_at = datetime.now(timezone.utc)
        return msg

    # ── Smart context builder ─────────────────────────────────────────────────
    async def build_context(
        self, db: AsyncSession, conv_id: str, query: str
    ) -> Tuple[List[Dict], str]:
        """
        Returns (recent_history, semantic_context_string).
        recent_history: last MEMORY_WINDOW messages as role/content dicts.
        semantic_context: relevant past snippets as a string block.
        """
        window = settings.MEMORY_WINDOW

        # Recent messages
        r = await db.execute(
            select(Message)
            .where(Message.conversation_id == conv_id)
            .order_by(desc(Message.timestamp))
            .limit(window)
        )
        recent = list(reversed(r.scalars().all()))
        history = [{"role": m.role, "content": m.content} for m in recent]

        # Latest summary (if exists)
        r2 = await db.execute(
            select(ConversationSummary)
            .where(ConversationSummary.conversation_id == conv_id)
            .order_by(desc(ConversationSummary.created_at))
            .limit(1)
        )
        summary = r2.scalar_one_or_none()

        # Semantic recall from older messages
        semantic_hits = await self._semantic_recall(db, conv_id, query, exclude_recent_ids=[m.id for m in recent])

        # Build context string
        ctx_parts = []
        if summary:
            ctx_parts.append(f"Summary of earlier conversation:\n{summary.summary}")
        if semantic_hits:
            ctx_parts.append("Relevant past exchanges:\n" + "\n".join(
                f"[{h['role']}]: {h['content'][:200]}" for h in semantic_hits
            ))

        return history, "\n\n".join(ctx_parts)

    async def _semantic_recall(self, db: AsyncSession, conv_id: str, query: str, exclude_recent_ids: List[int], top_k: int = 3) -> List[Dict]:
        q_emb = _embed(query)
        if q_emb is None:
            return []
        r = await db.execute(
            select(Message).where(
                Message.conversation_id == conv_id,
                Message.embedding.isnot(None),
                ~Message.id.in_(exclude_recent_ids) if exclude_recent_ids else True
            )
        )
        msgs = r.scalars().all()
        scored = []
        for m in msgs:
            if m.embedding:
                try:
                    emb = m.embedding if isinstance(m.embedding, list) else json.loads(m.embedding)
                    score = _cosine(q_emb, emb)
                    if score > 0.55:
                        scored.append((score, m))
                except Exception:
                    continue
        scored.sort(key=lambda x: x[0], reverse=True)
        return [{"role": m.role, "content": m.content} for _, m in scored[:top_k]]

    # ── Auto-summarization ────────────────────────────────────────────────────
    async def maybe_summarize(self, db: AsyncSession, conv_id: str, llm_complete_fn) -> bool:
        """Summarize if message count exceeds threshold. Returns True if summarized."""
        # Count messages
        r2 = await db.execute(
            select(sqlfunc.count()).select_from(Message).where(Message.conversation_id == conv_id)
        )
        count = r2.scalar()

        # Check last summary
        r3 = await db.execute(
            select(ConversationSummary)
            .where(ConversationSummary.conversation_id == conv_id)
            .order_by(desc(ConversationSummary.created_at))
            .limit(1)
        )
        last_summary = r3.scalar_one_or_none()
        summarized_up_to = last_summary.message_count_at if last_summary else 0

        new_msgs = count - summarized_up_to
        if new_msgs < settings.SUMMARY_THRESHOLD:
            return False

        # Fetch messages to summarize (all except last MEMORY_WINDOW)
        r4 = await db.execute(
            select(Message)
            .where(Message.conversation_id == conv_id)
            .order_by(Message.timestamp)
            .limit(count - settings.MEMORY_WINDOW)
        )
        msgs_to_summarize = r4.scalars().all()
        if not msgs_to_summarize:
            return False

        transcript = "\n".join(f"{m.role.upper()}: {m.content[:300]}" for m in msgs_to_summarize)
        prompt = f"""Summarize this conversation concisely in 3-5 sentences. Capture key topics, decisions, and important details.

CONVERSATION:
{transcript}

SUMMARY:"""
        try:
            summary_text = await llm_complete_fn(prompt)
            s = ConversationSummary(
                conversation_id=conv_id,
                summary=summary_text,
                message_count_at=count,
            )
            db.add(s)
            await db.flush()
            logger.info(f"📝 Summarized conversation {conv_id} at {count} messages")
            return True
        except Exception as e:
            logger.warning(f"Summarization failed: {e}")
            return False

    # ── Full history for display ───────────────────────────────────────────────
    async def get_messages(self, db: AsyncSession, conv_id: str) -> List[Dict]:
        r = await db.execute(
            select(Message).where(Message.conversation_id == conv_id).order_by(Message.timestamp)
        )
        return [{"id": m.id, "role": m.role, "content": m.content, "timestamp": m.timestamp.isoformat()} for m in r.scalars().all()]

    # ── Delete ────────────────────────────────────────────────────────────────
    async def delete_conversation(self, db: AsyncSession, conv_id: str):
        await db.execute(delete(Conversation).where(Conversation.id == conv_id))

    async def delete_user_data(self, db: AsyncSession, user_id: str):
        await db.execute(delete(User).where(User.id == user_id))


memory_service = MemoryService()
