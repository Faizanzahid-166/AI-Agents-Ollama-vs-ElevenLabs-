"""utils/audio_utils.py – Audio helpers for Grace Desktop backend"""
import os
import uuid
from pathlib import Path
from typing import Optional
import logging

from config import settings

logger = logging.getLogger("grace")
Path(settings.AUDIO_TEMP_DIR).mkdir(parents=True, exist_ok=True)


def get_temp_path(suffix: str = ".wav") -> str:
    return str(Path(settings.AUDIO_TEMP_DIR) / f"grace_{uuid.uuid4().hex}{suffix}")


def cleanup_file(path: Optional[str]):
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass


def convert_to_wav(input_path: str, output_path: Optional[str] = None) -> str:
    if output_path is None:
        output_path = get_temp_path(".wav")
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_file(input_path)
        audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)
        audio.export(output_path, format="wav")
        return output_path
    except ImportError:
        pass
    import subprocess
    r = subprocess.run(
        ["ffmpeg", "-y", "-i", input_path, "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", output_path],
        capture_output=True
    )
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {r.stderr.decode()[:200]}")
    return output_path


def save_upload(data: bytes, filename: str = "upload.wav") -> str:
    ext = Path(filename).suffix or ".wav"
    path = get_temp_path(ext)
    with open(path, "wb") as f:
        f.write(data)
    return path


def to_base64(path: str) -> str:
    import base64
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()
