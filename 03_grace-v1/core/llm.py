"""
core/llm.py  (REALTIME UPGRADE)
────────────────────────────────
Adds to the existing OllamaClient:

  1. CancellableStream   — wraps the requests stream; killed instantly via Event
  2. SentenceSplitter    — accumulates tokens, yields complete sentences
  3. stream_realtime()   — drives the full pipeline:
                           tokens → UI queue + sentence queue simultaneously
  4. Model recommendations updated for 3B-class realtime models

The existing stream() generator is preserved for backward compat.
New code adds stream_realtime() which drives both queues in parallel.
"""

import json
import queue
import re
import threading
from typing import Callable, Generator, Iterator, List, Dict, Optional

import requests

from core.config import cfg
from utils.logger import log

# ── Sentence boundary pattern ──────────────────────────────────────────────────
# Splits on sentence-ending punctuation followed by space or end-of-string
_SENTENCE_END = re.compile(r'(?<=[.!?])\s+|(?<=[.!?])$')

# Minimum chars before we consider emitting a "sentence"
_MIN_SENTENCE_CHARS = 20


# ── Sentence splitter ──────────────────────────────────────────────────────────

class SentenceSplitter:
    """
    Accumulates LLM tokens and emits complete sentences.

    Usage:
        splitter = SentenceSplitter(out_queue)
        for token in llm_stream:
            splitter.feed(token)
        splitter.flush()   # emit any remaining text
    """

    def __init__(self, out_queue: queue.Queue):
        self._q   = out_queue
        self._buf = ""

    def feed(self, token: str):
        self._buf += token
        # Check for sentence boundaries
        parts = _SENTENCE_END.split(self._buf)
        if len(parts) > 1:
            # Everything except the last part is a complete sentence
            for sentence in parts[:-1]:
                sentence = sentence.strip()
                if len(sentence) >= _MIN_SENTENCE_CHARS:
                    self._q.put_nowait(sentence)
                    log.info(f"SentenceSplitter → '{sentence[:120]}'")
            # Keep the incomplete tail
            self._buf = parts[-1]

    def flush(self):
        """Emit whatever remains in the buffer."""
        remaining = self._buf.strip()
        if len(remaining) >= 3:   # even short final sentences
            self._q.put_nowait(remaining)
            log.debug(f"SentenceSplitter flush → '{remaining[:60]}'")
        self._buf = ""


# ── Cancellable stream wrapper ─────────────────────────────────────────────────

class CancellableStream:
    """
    Wraps a requests streaming response.
    Calling cancel() causes the generator to stop at the next token boundary.
    """

    def __init__(self, response: requests.Response, cancel_event: threading.Event):
        self._resp   = response
        self._cancel = cancel_event

    def __iter__(self) -> Iterator[str]:
        try:
            for line in self._resp.iter_lines():
                if self._cancel.is_set():
                    log.debug("LLM stream: cancelled")
                    break
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                    if chunk.get("done"):
                        break
                    token = chunk.get("message", {}).get("content", "")
                    if token:
                        yield token
                except json.JSONDecodeError:
                    continue
        finally:
            try:
                self._resp.close()
            except Exception:
                pass


# ── Main LLM client ────────────────────────────────────────────────────────────

class OllamaClient:
    """
    Ollama /api/chat client with realtime streaming support.

    Recommended models for realtime on Intel i5 + CPU:
      llama3.2:3b   ← best balance (use for chat)
      qwen2.5:3b    ← slightly faster, great for code
      phi4-mini     ← fastest, shorter context

    Keep qwen3.5:latest / llama3:latest for code mode where
    speed is less critical than answer quality.
    """

    # Per-mode model selection
    REALTIME_CHAT_MODEL = "llama3.2:3b"
    REALTIME_CODE_MODEL = "qwen2.5:3b"

    def __init__(self):
        self.base           = cfg.OLLAMA_BASE_URL.rstrip("/")
        self.chat_model     = cfg.OLLAMA_CHAT_MODEL
        self.code_model     = cfg.OLLAMA_CODE_MODEL
        self._session       = requests.Session()
        self._session.headers["Content-Type"] = "application/json"

    def _pick_model(self, mode: str) -> str:
        return self.code_model if mode == "code" else self.chat_model

    # ── Ollama health + preload ────────────────────────────────────────────────

    def is_available(self) -> bool:
        try:
            r = self._session.get(f"{self.base}/api/tags", timeout=3)
            return r.status_code == 200
        except Exception:
            return False

    def preload(self, mode: str = "chat"):
        """Warm the model into Ollama's memory — call at startup."""
        model = self._pick_model(mode)
        def _load():
            try:
                self._session.post(
                    f"{self.base}/api/generate",
                    json={"model": model, "prompt": "", "stream": False, "keep_alive": "30m"},
                    timeout=30,
                )
                log.info(f"✅ Model warm-loaded: {model}")
            except Exception as e:
                log.warning(f"Preload {model}: {e}")
        threading.Thread(target=_load, daemon=True).start()

    # ── Legacy streaming (preserved for backward compat) ──────────────────────

    def stream(
        self,
        user_message: str,
        history: List[Dict],
        system_context: str = "",
        mode: str = "chat",
    ) -> Iterator[str]:
        """Blocking token generator. Run inside a daemon thread."""
        model    = self._pick_model(mode)
        messages = self._build_messages(user_message, history, system_context)
        payload  = self._build_payload(model, messages)

        log.info(f"LLM stream | model={model} | history={len(history)}")
        try:
            with self._session.post(
                f"{self.base}/api/chat", json=payload, stream=True, timeout=(5, 120)
            ) as resp:
                resp.raise_for_status()
                for token in CancellableStream(resp, threading.Event()):
                    yield token
        except requests.ConnectionError:
            raise RuntimeError(f"Cannot reach Ollama at {self.base}")

    # ── REALTIME streaming — drives token_q + sentence_q simultaneously ────────

    def stream_realtime(
        self,
        user_message: str,
        history: List[Dict],
        token_queue: queue.Queue,       # UI reads tokens from here
        sentence_queue: queue.Queue,    # TTS reads sentences from here
        cancel_event: threading.Event,
        system_context: str = "",
        mode: str = "chat",
        on_done: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ):
        """
        Run the full LLM pipeline in a background daemon thread.

        Tokens → token_queue (UI appends them live)
        Tokens → SentenceSplitter → sentence_queue (TTS consumes)

        Call cancel_event.set() to stop generation mid-stream.
        Sends None sentinel to both queues when done/cancelled.
        """
        def _run():
            model    = self._pick_model(mode)
            messages = self._build_messages(user_message, history, system_context)
            payload  = self._build_payload(model, messages)

            splitter    = SentenceSplitter(sentence_queue)
            full_parts  = []

            log.info(f"LLM realtime | model={model} | mode={mode}")

            try:
                with self._session.post(
                    f"{self.base}/api/chat",
                    json=payload,
                    stream=True,
                    timeout=(5, 120),
                ) as resp:
                    resp.raise_for_status()
                    for token in CancellableStream(resp, cancel_event):
                        full_parts.append(token)
                        token_queue.put_nowait(token)
                        splitter.feed(token)

            except requests.ConnectionError as e:
                err = f"Cannot reach Ollama at {self.base}"
                log.error(err)
                if on_error:
                    on_error(err)
            except Exception as e:
                log.error(f"LLM error: {e}")
                if on_error:
                    on_error(str(e))
            finally:
                splitter.flush()
                # Sentinel signals: "stream ended"
                token_queue.put_nowait(None)
                sentence_queue.put_nowait(None)
                if on_done:
                    on_done("".join(full_parts))

        t = threading.Thread(target=_run, daemon=True, name="LLMWorker")
        t.start()
        return t

    # ── Single-shot (for summaries/titles) ────────────────────────────────────

    def complete(self, prompt: str, mode: str = "chat") -> str:
        model = self._pick_model(mode)
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": 256},
        }
        try:
            r = self._session.post(
                f"{self.base}/api/chat", json=payload, timeout=(5, 60)
            )
            r.raise_for_status()
            return r.json()["message"]["content"].strip()
        except Exception as e:
            log.warning(f"LLM complete failed: {e}")
            return ""

    # ── Builders ──────────────────────────────────────────────────────────────

    def _build_messages(
        self, user_msg: str, history: List[Dict], system_ctx: str
    ) -> List[Dict]:
        system = cfg.GRACE_SYSTEM_PROMPT
        if system_ctx:
            system += f"\n\n[Relevant context]\n{system_ctx}"
        return [
            {"role": "system", "content": system},
            *history,
            {"role": "user", "content": user_msg},
        ]

    def _build_payload(self, model: str, messages: List[Dict]) -> dict:
        return {
            "model": model,
            "messages": messages,
            "stream": True,
            "keep_alive": "30m",
            "options": {
                "temperature": 0.82,
                "top_p": 0.9,
                "top_k": 40,
                "repeat_penalty": 1.08,
                "num_ctx": 2048,       # reduced for lower latency on 3B models
                "num_predict": 512,
            },
        }


# Singleton
llm = OllamaClient()
