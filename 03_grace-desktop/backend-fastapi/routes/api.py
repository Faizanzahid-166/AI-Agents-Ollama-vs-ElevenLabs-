"""
routes/api.py – REST endpoints for Grace Desktop

GET    /api/conversations/{user_id}         – list conversations
POST   /api/conversations                   – create conversation
DELETE /api/conversations/{conv_id}         – delete conversation
GET    /api/messages/{conv_id}              – get messages
POST   /api/voice                           – voice upload → STT → return transcript
GET    /api/health                          – health check
POST   /api/clear/{user_id}                 – clear all user data
GET    /api/audio/{filename}                – serve TTS audio file
"""

import os
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db, check_db
from services.llm_service import llm_service
from services.memory_service import memory_service
from services.stt_service import stt_service
from utils.audio_utils import save_upload, cleanup_file
from config import settings

logger = logging.getLogger("grace")
router = APIRouter(prefix="/api")


# ── Schemas ────────────────────────────────────────────────────────────────────

class CreateConvRequest(BaseModel):
    user_id: str
    title: str = "New conversation"
    mode: str = "chat"


# ── Conversations ──────────────────────────────────────────────────────────────

@router.get("/conversations/{user_id}")
async def list_conversations(user_id: str, db: AsyncSession = Depends(get_db)):
    await memory_service.get_or_create_user(db, user_id)
    convs = await memory_service.list_conversations(db, user_id)
    return {"conversations": convs}


@router.post("/conversations")
async def create_conversation(req: CreateConvRequest, db: AsyncSession = Depends(get_db)):
    conv = await memory_service.create_conversation(db, req.user_id, req.title, req.mode)
    return {"id": conv.id, "title": conv.title, "mode": conv.mode}


@router.delete("/conversations/{conv_id}")
async def delete_conversation(conv_id: str, db: AsyncSession = Depends(get_db)):
    await memory_service.delete_conversation(db, conv_id)
    return {"deleted": conv_id}


@router.get("/messages/{conv_id}")
async def get_messages(conv_id: str, db: AsyncSession = Depends(get_db)):
    msgs = await memory_service.get_messages(db, conv_id)
    return {"messages": msgs}


# ── Voice ──────────────────────────────────────────────────────────────────────

@router.post("/voice/transcribe")
async def transcribe_voice(
    audio: UploadFile = File(...),
    language: str = Form(default="en"),
):
    """Upload audio → return transcript. WS endpoint handles the rest."""
    data = await audio.read()
    if not data:
        raise HTTPException(400, "Empty audio file")

    temp_path = save_upload(data, audio.filename or "upload.wav")
    try:
        transcript = await stt_service.transcribe(temp_path, language)
        return {"transcript": transcript}
    except Exception as e:
        logger.error(f"STT error: {e}")
        raise HTTPException(500, f"Transcription failed: {e}")
    finally:
        cleanup_file(temp_path)


@router.get("/audio/{filename}")
async def serve_audio(filename: str):
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(400, "Invalid filename")
    path = Path(settings.AUDIO_TEMP_DIR) / filename
    if not path.exists():
        raise HTTPException(404, "Audio file not found")
    ext = path.suffix.lower()
    media = {".wav": "audio/wav", ".mp3": "audio/mpeg", ".ogg": "audio/ogg"}.get(ext, "audio/wav")
    return FileResponse(str(path), media_type=media, filename=filename)


# ── Health ─────────────────────────────────────────────────────────────────────

@router.get("/health")
async def health():
    db_ok = await check_db()
    llm_ok = await llm_service.is_available()
    return {
        "status": "healthy" if (db_ok and llm_ok) else "degraded",
        "database": "ok" if db_ok else "error",
        "ollama": "ok" if llm_ok else "error",
        "models": {
            "chat": settings.OLLAMA_CHAT_MODEL,
            "code": settings.OLLAMA_CODE_MODEL,
        },
    }


# ── Clear data ────────────────────────────────────────────────────────────────

@router.delete("/clear/{user_id}")
async def clear_user(user_id: str, db: AsyncSession = Depends(get_db)):
    await memory_service.delete_user_data(db, user_id)
    return {"message": f"All data cleared for {user_id}"}
