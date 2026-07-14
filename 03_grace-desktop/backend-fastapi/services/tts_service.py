"""
services/tts_service.py – Piper TTS with sentence-chunked streaming
Speaks in chunks as LLM tokens arrive — no waiting for full response.
"""
import asyncio
import re
import subprocess
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import AsyncGenerator, Optional,List
import logging

from config import settings
from utils.audio_utils import get_temp_path

logger = logging.getLogger("grace")
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="piper")

# Sentence boundary splitter
_SENTENCE_END = re.compile(r'(?<=[.!?])\s+|(?<=[.!?])$')


def _piper_available() -> bool:
    return Path(settings.PIPER_BIN_PATH).exists() and Path(settings.PIPER_MODEL_PATH).exists()


def _synthesize_chunk_sync(text: str) -> Optional[bytes]:
    """Run Piper synchronously, return raw WAV bytes."""
    if not text.strip():
        return None
    try:
        result = subprocess.run(
            [
                settings.PIPER_BIN_PATH,
                "--model", settings.PIPER_MODEL_PATH,
                "--output-raw",       # raw PCM to stdout
                "--sentence-silence", "0.1",
            ],
            input=text.encode("utf-8"),
            capture_output=True,
            timeout=15,
        )
        if result.returncode == 0 and result.stdout:
            return result.stdout
        logger.warning(f"Piper non-zero exit: {result.stderr[:200]}")
        return None
    except Exception as e:
        logger.error(f"Piper synthesis error: {e}")
        return None


def _synthesize_to_file_sync(text: str, out_path: str) -> bool:
    """Run Piper and write WAV file. Returns True on success."""
    if not text.strip():
        return False
    try:
        result = subprocess.run(
            [
                settings.PIPER_BIN_PATH,
                "--model", settings.PIPER_MODEL_PATH,
                "--output_file", out_path,
            ],
            input=text.encode("utf-8"),
            capture_output=True,
            timeout=20,
        )
        return result.returncode == 0 and os.path.exists(out_path)
    except Exception as e:
        logger.error(f"Piper file synthesis error: {e}")
        return False


class TTSService:
    """
    Streams TTS audio chunks sentence-by-sentence as text tokens arrive.
    Use `feed_tokens()` as an async generator that yields (sentence, audio_bytes) tuples.
    """

    def __init__(self):
        self._piper = _piper_available()
        if not self._piper:
            logger.warning("⚠️  Piper TTS not found — falling back to pyttsx3")

    async def synthesize_file(self, text: str) -> Optional[str]:
        """Synthesize full text to a WAV file. Returns path."""
        if not text.strip():
            return None
        loop = asyncio.get_event_loop()
        out_path = get_temp_path(".wav")

        if self._piper:
            ok = await loop.run_in_executor(_executor, lambda: _synthesize_to_file_sync(text, out_path))
            if ok:
                return out_path

        # Fallback: pyttsx3
        return await self._pyttsx3_fallback(text, out_path)

    async def synthesize_raw(self, text: str) -> Optional[bytes]:
        """Return raw PCM bytes for a text chunk."""
        if not self._piper or not text.strip():
            return None
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, lambda: _synthesize_chunk_sync(text))

    async def stream_sentences(
        self, token_generator: AsyncGenerator[str, None]
    ) -> AsyncGenerator[dict, None]:
        """
        Consumes streaming LLM tokens, detects sentence boundaries,
        and yields {sentence, audio_b64} dicts as each sentence completes.

        Usage:
            async for chunk in tts.stream_sentences(llm.stream(...)):
                ws.send_json({"type": "tts_chunk", **chunk})
        """
        import base64
        buffer = ""

        async for token in token_generator:
            buffer += token
            # Look for sentence boundaries
            sentences = _split_sentences(buffer)
            if len(sentences) > 1:
                # Yield all complete sentences, keep the last (incomplete) in buffer
                for sentence in sentences[:-1]:
                    sentence = sentence.strip()
                    if len(sentence) < 4:
                        continue
                    audio = await self.synthesize_raw(sentence)
                    chunk = {"sentence": sentence, "audio_b64": None, "audio_format": "pcm_16k"}
                    if audio:
                        chunk["audio_b64"] = base64.b64encode(audio).decode()
                    yield chunk
                buffer = sentences[-1]

        # Flush remaining
        if buffer.strip():
            audio = await self.synthesize_raw(buffer.strip())
            import base64
            yield {
                "sentence": buffer.strip(),
                "audio_b64": base64.b64encode(audio).decode() if audio else None,
                "audio_format": "pcm_16k",
            }

    async def _pyttsx3_fallback(self, text: str, out_path: str) -> Optional[str]:
        loop = asyncio.get_event_loop()
        def _run():
            try:
                import pyttsx3
                engine = pyttsx3.init()
                engine.setProperty("rate", 175)
                engine.save_to_file(text, out_path)
                engine.runAndWait()
                return os.path.exists(out_path)
            except Exception as e:
                logger.error(f"pyttsx3 fallback failed: {e}")
                return False
        ok = await loop.run_in_executor(_executor, _run)
        return out_path if ok else None


def _split_sentences(text: str) -> List[str]:
    """Split text on sentence boundaries, preserving incomplete last chunk."""
    parts = re.split(r'(?<=[.!?])\s+', text)
    return parts if parts else [text]


# Lazy import fix
from typing import List
tts_service = TTSService()
