"""config.py – Grace Desktop Backend Configuration"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

class Settings:
    # Database
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT", "5432"))
    DB_NAME = os.getenv("DB_NAME", "03_grace_memory")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")

    @property
    def DATABASE_URL(self):
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def ASYNC_DATABASE_URL(self):
        return self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

    # Ollama
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "llama3:latest")
    OLLAMA_CODE_MODEL = os.getenv("OLLAMA_CODE_MODEL", "qwen3.5:latest")

    # Whisper
    WHISPER_BIN_DIR = os.getenv("WHISPER_BIN_DIR", r"C:\whisper-bin-x64")
    WHISPER_MODEL_PATH = os.getenv("WHISPER_MODEL_PATH", r"C:\whisper-bin-x64\model\ggml-base.en-q5_1.bin")

    # Piper TTS
    PIPER_BIN_PATH = os.getenv("PIPER_BIN_PATH", r"C:\piper\piper.exe")
    PIPER_MODEL_PATH = os.getenv("PIPER_MODEL_PATH", r"C:\piper\en_US-amy-medium.onnx")

    # Sentence Transformer
    SENTENCE_TRANSFORMER_PATH = os.getenv("SENTENCE_TRANSFORMER_PATH", r"C:\models\sentence_transformer")

    # Audio
    AUDIO_TEMP_DIR = os.getenv("AUDIO_TEMP_DIR", "./temp_audio")

    # App
    APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT = int(os.getenv("APP_PORT", "8000"))
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    # Memory
    MEMORY_WINDOW = int(os.getenv("MEMORY_WINDOW", "6"))
    SUMMARY_THRESHOLD = int(os.getenv("SUMMARY_THRESHOLD", "20"))

    GRACE_SYSTEM_PROMPT = """You are Grace — a brilliant, witty, warm AI assistant who feels like that one friend who's somehow great at everything.

Personality:
- Sharp and knowledgeable across coding, science, writing, math, and life.
- Genuinely funny — light sarcasm, clever wit, natural humor.
- Emotionally intelligent — you listen, empathize, give real advice without being preachy.
- Direct and honest, always kind.
- Conversational — talk like a person, not a textbook.

Rules:
- Never give dry robotic answers. Always add warmth or personality.
- Keep it safe, respectful, and positive.
- If someone shares code, review it properly and be specific.
- Remember context from this conversation and reference it naturally.
- For coding questions: provide working code with brief explanation.
- For life questions: be a real friend, not a helpline script.

Your name is Grace. Own it."""

settings = Settings()
