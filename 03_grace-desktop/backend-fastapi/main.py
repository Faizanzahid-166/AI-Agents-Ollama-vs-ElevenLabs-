"""main.py – Grace Desktop FastAPI Application"""
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database import init_db, check_db, async_engine
from routes.ws_chat import router as ws_router
from routes.api import router as api_router

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("grace")
Path(settings.AUDIO_TEMP_DIR).mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("━" * 50)
    logger.info("  🌟  GRACE Desktop Backend starting")
    logger.info("━" * 50)

    db_ok = await check_db()
    if db_ok:
        await init_db()
    else:
        logger.error("⚠️  Database unavailable")

    from services.llm_service import llm_service
    ollama_ok = await llm_service.is_available()
    if ollama_ok:
        logger.info("✅ Ollama reachable — preloading models...")
        asyncio.create_task(llm_service.preload_all())
    else:
        logger.warning("⚠️  Ollama not reachable")

    # Preload embedder in background
    asyncio.create_task(_preload_embedder())

    logger.info(f"✅ Ready → ws://localhost:{settings.APP_PORT}/ws/chat")
    logger.info(f"✅ Docs  → http://localhost:{settings.APP_PORT}/docs")

    yield

    logger.info("👋 Grace shutting down...")
    await llm_service.close()
    await async_engine.dispose()


async def _preload_embedder():
    from services.memory_service import _get_embedder
    _get_embedder()


app = FastAPI(
    title="Grace Desktop API",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ws_router)
app.include_router(api_router)


@app.get("/")
async def root():
    return {"name": "Grace Desktop API", "status": "online", "version": "2.0.0"}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=False,
        log_level=settings.LOG_LEVEL.lower(),
        ws_ping_interval=20,
        ws_ping_timeout=30,
    )
