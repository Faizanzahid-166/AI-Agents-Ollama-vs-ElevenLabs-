"""
core/speech_to_text.py
=======================
Offline STT via Whisper local binary (whisper.cpp).
No cloud. No internet. Pure local execution.

Flow:
  1. Record mic audio as 16kHz mono WAV
  2. Pass WAV to whisper.cpp CLI binary
  3. Parse stdout transcript
  4. Return cleaned text string
"""

import os
import logging
import subprocess
import tempfile
import wave
import numpy as np
from pathlib import Path
from typing import Optional

logger = logging.getLogger("jarvis.stt")

try:
    import sounddevice as sd
    SD_AVAILABLE = True
except ImportError:
    SD_AVAILABLE = False
    logger.warning("sounddevice not installed — voice input disabled.")


class SpeechToText:
    """
    Records from microphone and transcribes using the local Whisper binary.
    Falls back to prompt-based input if audio hardware is unavailable.
    """

    def _save_wav(self, audio: np.ndarray):
        """
        Save numpy int16 audio array to WAV file.
        """

        with wave.open(str(self.temp_wav), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # int16 = 2 bytes
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio.tobytes())

    def __init__(self, settings):
        self.settings = settings
        self.whisper_exe = Path(settings.WHISPER_EXE)
        self.whisper_model = Path(settings.WHISPER_MODEL)
        self.sample_rate = settings.AUDIO_SAMPLE_RATE
        self.record_seconds = settings.AUDIO_RECORD_SECONDS
        self.temp_wav = Path(settings.AUDIO_TEMP_FILE)
        self.temp_wav.parent.mkdir(parents=True, exist_ok=True)
        self._verify_setup()

    def _verify_setup(self):
        if not self.whisper_exe.exists():
            logger.warning(f"Whisper binary not found: {self.whisper_exe}")
        if not self.whisper_model.exists():
            logger.warning(f"Whisper model not found: {self.whisper_model}")
        if not SD_AVAILABLE:
            logger.warning("sounddevice unavailable — mic input disabled.")

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def listen_and_transcribe(self) -> Optional[str]:
        """Record from mic, transcribe, return text or None."""
        if not SD_AVAILABLE:
            # Graceful fallback for dev/testing without hardware
            return input("(mic unavailable) Type your command: ").strip() or None

        wav_path = self._record_audio()
        if wav_path is None:
            return None
        return self._transcribe(wav_path)

    def transcribe_file(self, wav_path: str) -> Optional[str]:
        """Transcribe an existing WAV file."""
        return self._transcribe(Path(wav_path))

    # ------------------------------------------------------------------ #
    # Private: recording
    # ------------------------------------------------------------------ #

    def _record_audio(self) -> Optional[Path]:
        logger.info("Listening...")

        try:
            audio_data = sd.rec(
                int(self.record_seconds * self.sample_rate),
                samplerate=self.sample_rate,
                channels=1,
                dtype="int16",
            )

            sd.wait()  # ✔ proper sync instead of loop

            audio_data = self._trim_silence(audio_data.flatten())

            if audio_data is None:
                logger.info("No speech detected")
                return None

            self._save_wav(audio_data)
            return self.temp_wav

        except KeyboardInterrupt:
            sd.stop()
            logger.warning("Stopped by user")
            return None

        except Exception as e:
            logger.error(f"Recording failed: {e}")
            return None
        
    def _trim_silence(
        self,
        audio: np.ndarray,
        silence_thresh: float = None,
        min_speech_frames: int = 4800,
    ) -> Optional[np.ndarray]:
        """
        Remove silence from audio. Returns None if no speech detected.
        """

        threshold = silence_thresh or self.settings.AUDIO_SILENCE_THRESHOLD
        frame_size = 1600  # 100ms chunks at 16kHz
        last_speech_idx = 0

        for i in range(0, len(audio), frame_size):
            frame = audio[i:i + frame_size]

            if len(frame) == 0:
                continue

            if np.abs(frame).mean() > threshold:
                last_speech_idx = i + frame_size

        # No speech detected
        if last_speech_idx < min_speech_frames:
            return None

        end = min(
            last_speech_idx + int(self.sample_rate * 0.5),
            len(audio)
        )

        return audio[:end]

    # ------------------------------------------------------------------ #
    # Private: transcription
    # ------------------------------------------------------------------ #

    def _transcribe(self, wav_path: Path) -> Optional[str]:
        """
        Call the local whisper.cpp binary and capture stdout safely.
        Returns clean transcript only (no warnings, no timestamps).
        """

        if not self.whisper_exe.exists():
            logger.error("Whisper binary missing. Cannot transcribe.")
            return None

        if not self.whisper_model.exists():
            logger.error("Whisper model missing. Cannot transcribe.")
            return None

        cmd = [
            str(self.whisper_exe),
            "-m", str(self.whisper_model),

            # IMPORTANT: whisper.cpp expects file as positional arg
            str(wav_path),

            "-l", "en",
            "-nt"  # no timestamps
        ]

        logger.debug(f"Running Whisper: {' '.join(cmd)}")
        logger.info(f"Whisper EXE: {self.whisper_exe}")
        logger.info(f"Model PATH: {self.whisper_model}")
        logger.info(f"Audio file: {wav_path}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(self.whisper_exe.parent),
            )

            # ❌ NEVER mix stderr into speech pipeline
            if result.returncode != 0:
                logger.error("Whisper failed!")
                logger.error(f"STDOUT:\n{result.stdout}")
                logger.error(f"STDERR:\n{result.stderr}")
                logger.error(f"CMD: {' '.join(cmd)}")
                return None

            raw_output = result.stdout or ""

            # ❌ FILTER OUT DEPRECATION / WARNINGS
            if "WARNING:" in raw_output or "deprecated" in raw_output.lower():
                logger.warning("Whisper returned warning-only output. Ignoring.")
                return None

            # ✅ CLEAN TRANSCRIPT
            transcript = self._parse_whisper_output(raw_output)

            transcript = transcript.strip()

            if not transcript:
                return None

            logger.info(f"Transcript: {transcript}")
            return transcript

        except subprocess.TimeoutExpired:
            logger.error("Whisper timed out after 60s.")
            return None

        except FileNotFoundError:
            logger.error("Whisper binary not found.")
            return None
    
    @staticmethod
    def _parse_whisper_output(raw: str) -> str:
        """Extract plain text from whisper.cpp stdout lines."""
        import re
        lines = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            # Strip timestamp prefix  [HH:MM:SS.mmm --> HH:MM:SS.mmm]
            cleaned = re.sub(r"\[\d{2}:\d{2}:\d{2}\.\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}\.\d{3}\]", "", line)
            cleaned = cleaned.strip()
            if cleaned:
                lines.append(cleaned)
        return " ".join(lines).strip()
    
    
