"""
config/settings.py
==================
All configuration constants in one place.
Edit this file to match your local paths and preferences.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # ------------------------------------------------------------------ #
    # Project root
    # ------------------------------------------------------------------ #
    BASE_DIR: Path = Path(__file__).resolve().parent.parent

    # ------------------------------------------------------------------ #
    # Database
    # ------------------------------------------------------------------ #
    DB_HOST: str = os.getenv("JARVIS_DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("JARVIS_DB_PORT", "5432"))
    DB_NAME: str = os.getenv("JARVIS_DB_NAME", "02_jarvish_memory")
    DB_USER: str = os.getenv("JARVIS_DB_USER", "postgres")
    DB_PASS: str = os.getenv("JARVIS_DB_PASS", "")

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql://{self.DB_USER}:{self.DB_PASS}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    # ------------------------------------------------------------------ #
    # Local model paths — update to match your machine
    # ------------------------------------------------------------------ #
    WHISPER_BIN_DIR: str = os.getenv(
        "WHISPER_BIN_DIR",
        r"D:\07_code_2025\25_MODELS\models\02_whisper\whisper-bin-x64",
    )
    WHISPER_MODEL: str = os.getenv(
        "WHISPER_MODEL",
        r"D:\07_code_2025\25_MODELS\models\02_whisper\whisper-bin-x64\model\ggml-base.en-q5_1.bin",
    )
    # Set WHISPER_MODEL to ggml-medium.bin for higher accuracy (slower)
    WHISPER_EXE: str = os.path.join(WHISPER_BIN_DIR, "whisper-cli.exe")
    SENTENCE_TRANSFORMER_PATH: str = os.getenv(
        "SENTENCE_TRANSFORMER_PATH",
        r"D:\07_code_2025\25_MODELS\models\03_sentence_transformer",
    )

    # ------------------------------------------------------------------ #
    # Audio
    # ------------------------------------------------------------------ #
    AUDIO_TEMP_FILE: str = str(BASE_DIR / "logs" / "_temp_audio.wav")
    AUDIO_SAMPLE_RATE: int = 16_000
    AUDIO_RECORD_SECONDS: int = 10        # max recording length
    AUDIO_SILENCE_THRESHOLD: float = 500  # amplitude for VAD

    # ------------------------------------------------------------------ #
    # Memory / embeddings
    # ------------------------------------------------------------------ #
    EMBEDDING_DIM: int = 384              # all-MiniLM-L6-v2 default
    MEMORY_TOP_K: int = 5                 # results returned by semantic search
    MEMORY_SIMILARITY_THRESHOLD: float = 0.3

    # ------------------------------------------------------------------ #
    # File system agent
    # ------------------------------------------------------------------ #
    WATCH_DIRS: list = [
        os.path.expanduser("~/Downloads"),
        os.path.expanduser("~/Desktop"),
    ]
    ORGANIZE_TARGET_ROOT: str = os.path.expanduser("~/Documents/Jarvis_Organized")

    FILE_TYPE_MAP: dict = {
        # Documents
        ".pdf": "Documents/PDFs",
        ".docx": "Documents/Word",
        ".doc": "Documents/Word",
        ".xlsx": "Documents/Excel",
        ".xls": "Documents/Excel",
        ".pptx": "Documents/PowerPoint",
        ".ppt": "Documents/PowerPoint",
        ".txt": "Documents/Text",
        ".md": "Documents/Text",
        # Images
        ".jpg": "Media/Images",
        ".jpeg": "Media/Images",
        ".png": "Media/Images",
        ".gif": "Media/Images",
        ".bmp": "Media/Images",
        ".svg": "Media/Images",
        # Audio / Video
        ".mp3": "Media/Audio",
        ".wav": "Media/Audio",
        ".mp4": "Media/Video",
        ".avi": "Media/Video",
        ".mkv": "Media/Video",
        # Code
        ".py": "Code/Python",
        ".js": "Code/JavaScript",
        ".ts": "Code/TypeScript",
        ".java": "Code/Java",
        ".cpp": "Code/CPP",
        ".cs": "Code/CSharp",
        # Archives
        ".zip": "Archives",
        ".rar": "Archives",
        ".7z": "Archives",
        ".tar": "Archives",
        ".gz": "Archives",
    }

    # ------------------------------------------------------------------ #
    # AI engine / reasoning
    # ------------------------------------------------------------------ #
    RESPONSE_MAX_CONTEXT: int = 5   # how many past turns to include
    INTENT_CONFIDENCE_THRESHOLD: float = 0.4

    # ------------------------------------------------------------------ #
    # Logging
    # ------------------------------------------------------------------ #
    LOG_LEVEL: str = os.getenv("JARVIS_LOG_LEVEL", "INFO")
    LOG_FILE: str = str(BASE_DIR / "logs" / "jarvis.log")
