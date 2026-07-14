"""
routes/ws_chat.py – WebSocket streaming chat endpoint

Protocol (JSON messages):
  Client → Server:
    { "type": "chat", "conv_id": "...", "user_id": "...", "message": "...", "mode": "chat|code" }
    { "type": "stop" }
    { "type": "ping" }

  Server → Client:
    { "type": "token",       "content": "..." }
    { "type": "tts_chunk",   "sentence": "...", "audio_b64": "...", "audio_format": "pcm_16k" }
    { "type": "done",        "full_response": "...", "conv_id": "..." }
    { "type": "error",       "message": "..." }
    { "type": "pong" }
    { "type": "title_update","conv_id": "...", "title": "..." }
"""

import asyncio
import logging
from typing import Dict, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db, AsyncSessionLocal
from services.llm_service import llm_service
from services.memory_service import memory_service
from services.tts_service import tts_service

logger = logging.getLogger("grace")
router = APIRouter()

# Track active connections so we can cancel streams
_active_streams: Dict[str, asyncio.Task] = {}


@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    client_id = id(websocket)
    logger.info(f"WS connected: {client_id}")

    stop_event = asyncio.Event()

    try:
        while True:
            try:
                data = await websocket.receive_json()
            except Exception:
                break

            msg_type = data.get("type", "chat")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            if msg_type == "stop":
                stop_event.set()
                continue

            if msg_type != "chat":
                continue

            # Reset stop signal for new message
            stop_event.clear()

            user_id = data.get("user_id", "default")
            conv_id = data.get("conv_id")
            user_message = data.get("message", "").strip()
            mode = data.get("mode", "chat")
            enable_tts = data.get("tts", False)

            if not user_message:
                await websocket.send_json({"type": "error", "message": "Empty message"})
                continue

            # Handle in background so we can keep receiving stop signals
            task = asyncio.create_task(
                _handle_chat(
                    websocket, user_id, conv_id, user_message, mode, enable_tts, stop_event
                )
            )
            _active_streams[str(client_id)] = task

            try:
                await task
            except asyncio.CancelledError:
                pass

    except WebSocketDisconnect:
        logger.info(f"WS disconnected: {client_id}")
    finally:
        # Cancel any running stream
        task = _active_streams.pop(str(client_id), None)
        if task and not task.done():
            task.cancel()


async def _handle_chat(
    websocket: WebSocket,
    user_id: str,
    conv_id: Optional[str],
    user_message: str,
    mode: str,
    enable_tts: bool,
    stop_event: asyncio.Event,
):
    """Core streaming pipeline: memory → LLM stream → tokens to WS → TTS chunks."""
    async with AsyncSessionLocal() as db:
        try:
            # ── Ensure conversation exists ────────────────────────────────────
            if not conv_id:
                conv = await memory_service.create_conversation(db, user_id, mode=mode)
                conv_id = conv.id
                await db.commit()
            else:
                conv = await memory_service.get_conversation(db, conv_id)
                if not conv:
                    conv = await memory_service.create_conversation(db, user_id, mode=mode)
                    conv_id = conv.id
                    await db.commit()

            # ── Build context (smart memory) ──────────────────────────────────
            history, semantic_ctx = await memory_service.build_context(db, conv_id, user_message)

            # ── Save user message ─────────────────────────────────────────────
            await memory_service.save_message(db, conv_id, "user", user_message)
            await db.commit()

            # ── Stream LLM response ───────────────────────────────────────────
            full_response = []
            token_gen = llm_service.stream(
                user_message=user_message,
                history=history,
                system_context=semantic_ctx,
                mode=mode,
            )

            if enable_tts:
                # Parallel: stream tokens to UI + synthesize TTS sentence-by-sentence
                async for tts_chunk in tts_service.stream_sentences(
                    _tee_tokens(token_gen, full_response, websocket, stop_event)
                ):
                    if stop_event.is_set():
                        break
                    await websocket.send_json({
                        "type": "tts_chunk",
                        **tts_chunk,
                    })
            else:
                # Token-only streaming
                async for token in token_gen:
                    if stop_event.is_set():
                        break
                    full_response.append(token)
                    await websocket.send_json({"type": "token", "content": token})

            response_text = "".join(full_response).strip()
            if not response_text:
                response_text = "..."

            # ── Save assistant response ───────────────────────────────────────
            await memory_service.save_message(
                db, conv_id, "assistant", response_text,
                meta={"model": llm_service._pick_model(mode), "mode": mode}
            )

            # ── Auto-generate title from first exchange ───────────────────────
            conv = await memory_service.get_conversation(db, conv_id)
            if conv and conv.title == "New conversation":
                title = await _generate_title(user_message)
                await memory_service.update_conversation_title(db, conv_id, title)
                await websocket.send_json({
                    "type": "title_update",
                    "conv_id": conv_id,
                    "title": title,
                })

            # ── Maybe summarize ───────────────────────────────────────────────
            await memory_service.maybe_summarize(db, conv_id, llm_service.complete)
            await db.commit()

            # ── Done ──────────────────────────────────────────────────────────
            await websocket.send_json({
                "type": "done",
                "full_response": response_text,
                "conv_id": conv_id,
            })

        except Exception as e:
            logger.error(f"WS chat error: {e}", exc_info=True)
            try:
                await websocket.send_json({"type": "error", "message": str(e)})
            except Exception:
                pass


async def _tee_tokens(token_gen, accumulator: list, websocket: WebSocket, stop_event: asyncio.Event):
    """Tee: sends each token to the WebSocket AND yields it for TTS processing."""
    async for token in token_gen:
        if stop_event.is_set():
            return
        accumulator.append(token)
        try:
            await websocket.send_json({"type": "token", "content": token})
        except Exception:
            return
        yield token


async def _generate_title(first_message: str) -> str:
    """Generate a short conversation title from the first user message."""
    try:
        prompt = f'Generate a concise 4-6 word title for a conversation starting with: "{first_message[:150]}". Reply with ONLY the title, no quotes.'
        title = await llm_service.complete(prompt)
        return title.strip()[:80]
    except Exception:
        return first_message[:50]
