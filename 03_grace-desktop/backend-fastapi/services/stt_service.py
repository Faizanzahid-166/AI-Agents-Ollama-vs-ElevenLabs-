"""services/stt_service.py – Async Whisper STT"""
import asyncio
import os
import re
import subprocess
import platform
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import Optional
import logging
from unittest import result

from config import settings
from utils.audio_utils import get_temp_path, convert_to_wav

logger = logging.getLogger("grace")
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="whisper")


def _find_whisper_bin() -> str:
    bin_dir = Path(settings.WHISPER_BIN_DIR)

    names = (
        ["whisper-cli.exe", "main.exe", "whisper.exe"]
        if platform.system() == "Windows"
        else ["whisper-cli", "main", "whisper"]
    )

    for name in names:
        p = bin_dir / name

        print("CHECKING:", p)

        if p.exists():
            print("USING:", p)
            return str(p.resolve())

    import shutil

    for name in ["whisper-cli", "whisper"]:
        found = shutil.which(name)
        if found:
            return found

    raise FileNotFoundError(
        f"Whisper binary not found in {bin_dir}"
    )


def _transcribe_sync(audio_path: str, language: str = "en") -> str:
    whisper_bin = _find_whisper_bin()
    model_path = settings.WHISPER_MODEL_PATH

    if not Path(model_path).exists():
        raise FileNotFoundError(f"Whisper model not found: {model_path}")

    wav_path = audio_path
    converted = False

    if not audio_path.lower().endswith(".wav"):
        wav_path = get_temp_path(".wav")
        convert_to_wav(audio_path, wav_path)
        converted = True

    wav_path = str(Path(wav_path).resolve())

    cmd = [
        whisper_bin,
        "-m", model_path,
        "-f", wav_path,
        "-l", language,
        "-otxt",
        "-np",
        "-t", "4",
    ]

    print("COMMAND:", cmd)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(Path(settings.WHISPER_BIN_DIR))
    )

    print("RETURN CODE:", result.returncode)
    print("STDOUT:", result.stdout)
    print("STDERR:", result.stderr)

    # if result.returncode != 0:
    #     raise RuntimeError(f"Whisper failed:\n{result.stderr}")
    
    if result.returncode != 0:
        raise RuntimeError(
            f"\nWhisper failed\n"
            f"Return code: {result.returncode}\n\n"
            f"STDOUT:\n{result.stdout}\n\n"
            f"STDERR:\n{result.stderr}"
        )

    txt_path = wav_path + ".txt"

    transcript = ""

    if os.path.exists(txt_path):
        with open(txt_path, "r", encoding="utf-8") as f:
            transcript = f.read()

        os.remove(txt_path)
    else:
        transcript = result.stdout

    if converted and os.path.exists(wav_path):
        os.remove(wav_path)

    return _clean(transcript)


def _clean(raw: str) -> str:
    cleaned = re.sub(r"\[\d{2}:\d{2}:\d{2}\.\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}\.\d{3}\]", "", raw)
    cleaned = re.sub(r"\[.*?\]", "", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


class STTService:
    async def transcribe(self, audio_path: str, language: str = "en") -> str:
        loop = asyncio.get_event_loop()
        logger.info(f"STT: transcribing {audio_path}")
        text = await loop.run_in_executor(_executor, lambda: _transcribe_sync(audio_path, language))
        logger.info(f"STT result: '{text[:80]}'")
        return text


stt_service = STTService()
