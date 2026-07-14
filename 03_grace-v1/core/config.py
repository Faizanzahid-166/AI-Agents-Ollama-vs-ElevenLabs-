"""
core/config.py
All application settings — reads from .env in project root.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Always load .env from the project root (grace-v3/)
_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")


class Config:
    # ── Project root ──────────────────────────────────────────
    ROOT_DIR: Path = _ROOT
    DATA_DIR: Path = _ROOT / "data"

    # ── PostgreSQL ────────────────────────────────────────────
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
    DB_NAME: str = os.getenv("DB_NAME", "03_grace_memory")
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")

    # ── Ollama ────────────────────────────────────────────────
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_CHAT_MODEL: str = os.getenv("OLLAMA_CHAT_MODEL", "llama3:latest")
    OLLAMA_CODE_MODEL: str = os.getenv("OLLAMA_CODE_MODEL", "qwen3.5:latest")

    # ── Whisper ───────────────────────────────────────────────
    WHISPER_BIN_DIR: str = os.getenv("WHISPER_BIN_DIR", r"C:\whisper-bin-x64")
    WHISPER_MODEL_PATH: str = os.getenv(
        "WHISPER_MODEL_PATH",
        r"C:\whisper-bin-x64\model\ggml-base.en-q5_1.bin",
    )

    # ── Piper TTS ─────────────────────────────────────────────
    PIPER_BIN_PATH: str = os.getenv("PIPER_BIN_PATH", r"C:\piper\piper.exe")
    PIPER_MODEL_PATH: str = os.getenv("PIPER_MODEL_PATH", r"C:\piper\en_US-amy-medium.onnx")

    # ── Sentence Transformer ──────────────────────────────────
    SENTENCE_TRANSFORMER_PATH: str = os.getenv(
        "SENTENCE_TRANSFORMER_PATH", r"C:\models\sentence_transformer"
    )

    # ── App behaviour ─────────────────────────────────────────
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    MEMORY_WINDOW: int = int(os.getenv("MEMORY_WINDOW", "6"))
    SUMMARY_THRESHOLD: int = int(os.getenv("SUMMARY_THRESHOLD", "20"))
    ENABLE_SEMANTIC_MEMORY: bool = os.getenv("ENABLE_SEMANTIC_MEMORY", "true").lower() == "true"

    # ── Grace personality system prompt ───────────────────────
    GRACE_SYSTEM_PROMPT: str = (
        "You are Grace — a brilliant, witty, and genuinely warm AI assistant "
        "who feels like that one friend who's somehow great at everything.\n\n"
        "Personality:\n"
        "- Sharp and knowledgeable: coding, science, writing, math, life.\n"
        "- Genuinely funny: light sarcasm, clever wit, natural humour.\n"
        "- Emotionally intelligent: you listen and give real advice.\n"
        "- Direct and honest, always kind.\n"
        "- Conversational: talk like a person, not a textbook.\n\n"
        "Rules:\n"
        "- Never give dry robotic answers. Always add warmth or personality.\n"
        "- Keep it safe, respectful, and positive.\n"
        "- For code: provide working code with a brief explanation.\n"
        "- For life questions: be a real friend.\n"
        "- Your name is Grace. Own it."
    )

    def ensure_data_dir(self):
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)


# Module-level singleton
cfg = Config()
cfg.ensure_data_dir()
