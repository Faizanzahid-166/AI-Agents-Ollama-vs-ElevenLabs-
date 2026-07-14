"""
services/llm_service.py – Streaming Ollama LLM service
Supports: token streaming, model switching (chat/code), warm-loading
"""
import json
import asyncio
from typing import List, Dict, AsyncGenerator, Optional
import httpx
from config import settings
import logging

logger = logging.getLogger("grace")

ChatMessage = Dict[str, str]

GRACE_OPTIONS = {
    "temperature": 0.82,
    "top_p": 0.9,
    "top_k": 40,
    "repeat_penalty": 1.08,
    "num_ctx": 4096,
    "num_predict": 1024,
}


class LLMService:
    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL.rstrip("/")
        self.chat_model = settings.OLLAMA_CHAT_MODEL
        self.code_model = settings.OLLAMA_CODE_MODEL
        self._client: Optional[httpx.AsyncClient] = None
        self._preloaded = set()

    async def _client_(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(connect=5, read=180, write=15, pool=5)
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def _pick_model(self, mode: str) -> str:
        return self.code_model if mode == "code" else self.chat_model

    # ── Warm-load a model into Ollama's memory ────────────────────────────────
    async def preload_model(self, model: str):
        if model in self._preloaded:
            return
        try:
            client = await self._client_()
            # Send a minimal request to load the model
            await client.post(
                f"{self.base_url}/api/generate",
                json={"model": model, "prompt": "", "stream": False, "keep_alive": "10m"},
                timeout=30,
            )
            self._preloaded.add(model)
            logger.info(f"✅ Model warm-loaded: {model}")
        except Exception as e:
            logger.warning(f"Preload failed for {model}: {e}")

    async def preload_all(self):
        await asyncio.gather(
            self.preload_model(self.chat_model),
            self.preload_model(self.code_model),
        )

    # ── Streaming token generator ─────────────────────────────────────────────
    async def stream(
        self,
        user_message: str,
        history: List[ChatMessage],
        system_context: str = "",
        mode: str = "chat",
    ) -> AsyncGenerator[str, None]:
        """
        Yields text tokens as they arrive from Ollama.
        Caller is responsible for accumulating the full response.
        """
        model = self._pick_model(mode)
        messages = self._build_messages(user_message, history, system_context)

        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": GRACE_OPTIONS,
            "keep_alive": "10m",
        }

        client = await self._client_()
        logger.info(f"Streaming from {model} | history={len(history)} | mode={mode}")

        try:
            async with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                        if chunk.get("done"):
                            return
                        token = chunk.get("message", {}).get("content", "")
                        if token:
                            yield token
                    except json.JSONDecodeError:
                        continue
        except httpx.ConnectError:
            raise RuntimeError(f"Cannot reach Ollama at {self.base_url}. Is it running?")
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Ollama error {e.response.status_code}: {e.response.text[:200]}")

    # ── Single-shot for summaries ──────────────────────────────────────────────
    async def complete(self, prompt: str, model: Optional[str] = None) -> str:
        m = model or self.chat_model
        client = await self._client_()
        payload = {
            "model": m,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {**GRACE_OPTIONS, "temperature": 0.3},
        }
        resp = await client.post(f"{self.base_url}/api/chat", json=payload)
        resp.raise_for_status()
        return resp.json()["message"]["content"].strip()

    def _build_messages(
        self, user_message: str, history: List[ChatMessage], system_context: str
    ) -> List[ChatMessage]:
        system = settings.GRACE_SYSTEM_PROMPT
        if system_context:
            system += f"\n\n[Relevant context from past conversations]\n{system_context}"
        return [
            {"role": "system", "content": system},
            *history,
            {"role": "user", "content": user_message},
        ]

    async def is_available(self) -> bool:
        try:
            client = await self._client_()
            r = await client.get(f"{self.base_url}/api/tags", timeout=3)
            return r.status_code == 200
        except Exception:
            return False


llm_service = LLMService()
