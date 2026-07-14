"""
core/tts.py  (REALTIME UPGRADE)
────────────────────────────────
Sentence-level streaming TTS pipeline:

  sentence_queue
       │
       ▼
  TTSWorkerThread   (Piper subprocess per sentence → raw PCM bytes)
       │
       ▼
  audio_queue       (PCM bytes, immediately ready to play)
       │
       ▼
  AudioPlayerThread (sounddevice play, interruptible via stop_event)

Key improvements over v3:
  ─ Grace starts speaking the FIRST sentence while LLM is still generating
  ─ Audio player runs in its own thread — never blocks anything
  ─ stop() drains both queues instantly (interrupt in <50ms)
  ─ Piper launched once per sentence (lightweight process, ~100ms each)
  ─ PCM output mode avoids WAV header overhead
"""

import io
import queue
import subprocess
import threading
from pathlib import Path
from typing import Optional, Callable

import numpy as np
import sounddevice as sd

from core.config import cfg
from utils.logger import log

# ── Audio constants ────────────────────────────────────────────────────────────
PIPER_SAMPLE_RATE = 22_050     # Piper default output sample rate
PIPER_CHANNELS    = 1
PIPER_DTYPE       = "int16"    # raw PCM 16-bit

# Playback chunk size in samples (controls how quickly stop() takes effect)
PLAYBACK_CHUNK_SAMPLES = 2048  # ~93ms at 22kHz — good interrupt granularity


# ── Piper subprocess helper ────────────────────────────────────────────────────

def _piper_available() -> bool:
    return (
        Path(cfg.PIPER_BIN_PATH).exists()
        and Path(cfg.PIPER_MODEL_PATH).exists()
    )


def _synthesize_to_pcm(text: str) -> Optional[bytes]:
    """
    Run Piper on `text` and return raw int16 PCM bytes.
    Uses --output-raw so no WAV header — minimal overhead.
    Returns None on failure.
    """
    if not text.strip():
        return None
    try:
        result = subprocess.run(
            [
                cfg.PIPER_BIN_PATH,
                "--model",          cfg.PIPER_MODEL_PATH,
                "--output-raw",     # raw PCM to stdout (no WAV header)
                "--sentence-silence", "0.05",
            ],
            input=text.encode("utf-8"),
            capture_output=True,
            timeout=15,
        )
        if result.returncode == 0 and result.stdout:
            return result.stdout
        log.warning(f"Piper exit {result.returncode}: {result.stderr[:120]}")
        return None
    except Exception as e:
        log.error(f"Piper error: {e}")
        return None


def _synthesize_pyttsx3(text: str) -> Optional[bytes]:
    """pyttsx3 fallback — writes to temp WAV, reads back as PCM."""
    try:
        import soundfile as sf
        from utils.audio import get_temp_path, cleanup
        path = get_temp_path(".wav")
        import pyttsx3
        engine = pyttsx3.init()
        engine.setProperty("rate", 175)
        engine.save_to_file(text, path)
        engine.runAndWait()
        if Path(path).exists():
            data, sr = sf.read(path, dtype="int16")
            cleanup(path)
            return data.tobytes()
    except Exception as e:
        log.error(f"pyttsx3 fallback failed: {e}")
    return None


# ── TTS worker thread ──────────────────────────────────────────────────────────

class TTSWorker:
    """
    Consumes sentences from sentence_queue.
    Synthesises each via Piper (or pyttsx3 fallback).
    Puts raw PCM bytes into audio_queue.

    Sentinel: sentence_queue.put(None) to stop the worker.
    """

    def __init__(
        self,
        sentence_queue: queue.Queue,
        audio_queue: queue.Queue,
        stop_event: threading.Event,
    ):
        self._sentences = sentence_queue
        self._audio     = audio_queue
        self._stop      = stop_event
        self._use_piper = _piper_available()
        self._thread    = threading.Thread(
            target=self._run, daemon=True, name="TTSWorker"
        )
        if not self._use_piper:
            log.warning("Piper not found — using pyttsx3 fallback (higher latency)")

    def start(self):
        self._thread.start()

    def _run(self):
        log.info("TTSWorker started")
        while not self._stop.is_set():
            try:
                sentence = self._sentences.get(timeout=0.3)
            except queue.Empty:
                continue

            if sentence is None:
                log.info("TTSWorker: received sentinel -> stopping and forwarding to AudioPlayer")
                # Propagate sentinel to audio player
                self._audio.put_nowait(None)
                break

            log.info(f"TTSWorker: received sentence ({len(sentence)} chars): '{sentence[:120]}'")

            if self._stop.is_set():
                break

            # Synthesise
            pcm = (
                _synthesize_to_pcm(sentence)
                if self._use_piper
                else _synthesize_pyttsx3(sentence)
            )
            if pcm and not self._stop.is_set():
                self._audio.put_nowait(pcm)
                log.info(f"TTS synthesised {len(pcm)//2/PIPER_SAMPLE_RATE*1000:.0f}ms audio")
            else:
                log.warning(
                    f"TTS synthesis failed (use_piper={self._use_piper}) for sentence: '{sentence[:200]}'"
                )

        log.info("TTSWorker stopped")


# ── Audio player thread ────────────────────────────────────────────────────────

class AudioPlayer:
    """
    Dedicated playback thread that reads raw int16 PCM from audio_queue
    and plays through sounddevice.

    Key properties:
      ─ Plays in PLAYBACK_CHUNK_SAMPLES chunks → can be interrupted mid-sentence
      ─ stop() drains queue AND stops current playback instantly
      ─ on_speaking_change(bool) fires when playback state changes

    Sentinel: audio_queue.put(None) to stop the player.
    """

    def __init__(
        self,
        audio_queue: queue.Queue,
        stop_event: threading.Event,
        on_speaking_change: Optional[Callable[[bool], None]] = None,
    ):
        self._q         = audio_queue
        self._stop      = stop_event
        self._on_change = on_speaking_change
        self._playing   = False
        self._thread    = threading.Thread(
            target=self._run, daemon=True, name="AudioPlayer"
        )

    def start(self):
        self._thread.start()

    def _set_playing(self, state: bool):
        if state != self._playing:
            self._playing = state
            if self._on_change:
                self._on_change(state)

    def _run(self):
        log.info("AudioPlayer started")
        try:
            out_idx = sd.default.device[1]
            dev = sd.query_devices(out_idx)
            log.info(f"AudioPlayer using device {out_idx}: {dev['name']}")
        except Exception as e:
            log.warning(f"Could not query sounddevice output device: {e}")
        while True:
            try:
                pcm = self._q.get(timeout=0.3)
            except queue.Empty:
                if self._stop.is_set():
                    break
                continue

            if pcm is None:
                self._set_playing(False)
                break

            if self._stop.is_set():
                continue   # drain queue without playing

            # Play in chunks so we can interrupt quickly
            audio_i16  = np.frombuffer(pcm, dtype=np.int16)
            audio_f32  = audio_i16.astype(np.float32) / 32768.0
            offset = 0

            self._set_playing(True)

            while offset < len(audio_f32):
                if self._stop.is_set():
                    sd.stop()
                    break
                chunk = audio_f32[offset: offset + PLAYBACK_CHUNK_SAMPLES]
                try:
                    sd.play(chunk, samplerate=PIPER_SAMPLE_RATE, blocking=True)
                except Exception as e:
                    log.warning(f"Audio play error: {e}")
                    break
                offset += PLAYBACK_CHUNK_SAMPLES

        self._set_playing(False)
        log.info("AudioPlayer stopped")


# ── High-level pipeline ────────────────────────────────────────────────────────

class TTSPipeline:
    """
    One-stop class that owns:
      ─ sentence_queue  (LLM feeds sentences here)
      ─ audio_queue     (TTS worker puts PCM here)
      ─ TTSWorker       (sentence → PCM)
      ─ AudioPlayer     (PCM → speakers)

    To start a new response:
        pipeline.start_response()
        # feed sentences via pipeline.sentence_queue

    To interrupt immediately:
        pipeline.interrupt()
    """

    def __init__(
        self,
        on_speaking_change: Optional[Callable[[bool], None]] = None,
    ):
        # External callback provided by caller
        self._on_speaking_external = on_speaking_change
        # Internal playing flag (kept in sync with AudioPlayer)
        self._playing = False
        self._stop_event = threading.Event()
        self.sentence_queue: queue.Queue = queue.Queue()
        self._audio_queue:   queue.Queue = queue.Queue()
        self._tts_worker = None
        self._audio_player = None

    @property
    def on_speaking_change(self) -> Optional[Callable[[bool], None]]:
        """External-facing property to get/set the speaking-change callback."""
        return self._on_speaking_external

    @on_speaking_change.setter
    def on_speaking_change(self, fn: Optional[Callable[[bool], None]]):
        self._on_speaking_external = fn

    def _handle_playing_change(self, state: bool):
        """Internal handler called by AudioPlayer when playback state changes."""
        self._playing = state
        if self._on_speaking_external:
            try:
                self._on_speaking_external(state)
            except Exception:
                pass

    def start(self):
        """Start the worker threads (call once at app startup)."""
        self._spawn_workers()

    def _spawn_workers(self):
        self._stop_event.clear()
        self._tts_worker = TTSWorker(
            self.sentence_queue, self._audio_queue, self._stop_event
        )
        self._audio_player = AudioPlayer(
            self._audio_queue, self._stop_event, self._handle_playing_change
        )
        self._tts_worker.start()
        self._audio_player.start()

    def interrupt(self):
        """
        Stop current speech IMMEDIATELY and drain queues.
        Respawn workers so the pipeline is ready for the next response.
        """
        log.info("TTS: interrupt")
        self._stop_event.set()
        sd.stop()   # stop sounddevice playback instantly

        # Drain both queues
        for q in (self.sentence_queue, self._audio_queue):
            while not q.empty():
                try:
                    q.get_nowait()
                except queue.Empty:
                    break

        # Respawn fresh workers
        self._spawn_workers()

    def feed_sentence(self, sentence: str):
        """Called by LLM SentenceSplitter for each complete sentence."""
        self.sentence_queue.put_nowait(sentence)

    def signal_done(self):
        """Called when LLM stream is complete — lets TTS drain naturally."""
        self.sentence_queue.put_nowait(None)

    def shutdown(self):
        self._stop_event.set()
        sd.stop()


# Singleton — owns the audio pipeline for the entire app lifetime
tts_pipeline = TTSPipeline()
