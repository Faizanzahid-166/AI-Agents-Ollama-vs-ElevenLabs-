"""
utils/audio.py  (REALTIME UPGRADE)
─────────────────────────────────
Replaces the old write-full-WAV MicRecorder with a streaming capture
pipeline that feeds 20 ms PCM frames through webrtcvad, accumulates
voiced segments, and pushes them into a queue for the STT worker.

Key classes
───────────
StreamingMicCapture   – sounddevice InputStream, pushes raw 20 ms frames
VADFilter             – webrtcvad wrapper; classifies frames as speech/silence
VoiceSegmentBuffer    – state machine that groups voiced frames into segments
AudioChunkQueue       – typed alias for the inter-thread queue

Helper functions (unchanged from v3 for backward compat)
─────────────────────────────────────────────────────────
get_temp_path()
cleanup()
convert_to_wav()
"""

import os
import queue
import threading
import uuid
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import sounddevice as sd

from core.config import cfg
from utils.logger import log

# ── Constants ──────────────────────────────────────────────────────────────────
SAMPLE_RATE   = 16_000          # Hz — required by Whisper and webrtcvad
FRAME_MS      = 20              # ms per VAD frame  (webrtcvad supports 10/20/30)
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000   # 320 samples
FRAME_BYTES   = FRAME_SAMPLES * 2                # int16 = 2 bytes/sample

# Silence padding around speech segments (in frames)
SILENCE_PADDING_FRAMES   = 15   # 300 ms of trailing silence before cut
MIN_SPEECH_FRAMES        = 5    # discard clips shorter than 100 ms
MAX_SEGMENT_FRAMES       = 400  # hard cap at 8 s to prevent runaway buffers


# ── Queue type alias ───────────────────────────────────────────────────────────
# Each item is a bytes object containing a 16kHz int16 PCM segment
AudioChunkQueue = queue.Queue   # queue.Queue[bytes]


# ── VAD wrapper ────────────────────────────────────────────────────────────────

class VADFilter:
    """
    Wraps webrtcvad.  Classifies each 20 ms PCM frame as speech or silence.

    aggressiveness: 0 (permissive) → 3 (strict)
    For conversational mic use, 2 is a good balance.
    """

    def __init__(self, aggressiveness: int = 2):
        try:
            import webrtcvad
            self._vad = webrtcvad.Vad(aggressiveness)
            self._available = True
        except ImportError:
            log.warning("webrtcvad not installed — VAD disabled (all audio passed through)")
            self._available = False

    def is_speech(self, frame_bytes: bytes) -> bool:
        """Return True if the 20 ms PCM frame contains speech."""
        if not self._available:
            return True   # pass-through if VAD unavailable
        if len(frame_bytes) != FRAME_BYTES:
            return False
        try:
            return self._vad.is_speech(frame_bytes, SAMPLE_RATE)
        except Exception:
            return True


# ── Voice segment buffer ───────────────────────────────────────────────────────

class VoiceSegmentBuffer:
    """
    State machine that groups VAD-positive frames into speech segments.

    States:
        SILENCE  → waiting for speech to start
        SPEECH   → accumulating voiced frames
        TRAILING → accumulating post-speech padding

    When the state returns to SILENCE (after enough padding) or hits
    MAX_SEGMENT_FRAMES, it emits the accumulated bytes to out_queue.
    """

    _STATE_SILENCE  = "silence"
    _STATE_SPEECH   = "speech"
    _STATE_TRAILING = "trailing"

    def __init__(self, out_queue: AudioChunkQueue):
        self._q      = out_queue
        self._state  = self._STATE_SILENCE
        self._buf: list[bytes] = []
        self._trailing = 0

    def feed(self, frame: bytes, is_speech: bool):
        """Feed a single 20 ms frame with its VAD classification."""
        if self._state == self._STATE_SILENCE:
            if is_speech:
                self._state  = self._STATE_SPEECH
                self._buf    = [frame]
                self._trailing = 0

        elif self._state == self._STATE_SPEECH:
            self._buf.append(frame)
            if not is_speech:
                self._state    = self._STATE_TRAILING
                self._trailing = 1
            elif len(self._buf) >= MAX_SEGMENT_FRAMES:
                self._emit()

        elif self._state == self._STATE_TRAILING:
            self._buf.append(frame)
            if is_speech:
                self._state    = self._STATE_SPEECH
                self._trailing = 0
            else:
                self._trailing += 1
                if self._trailing >= SILENCE_PADDING_FRAMES:
                    self._emit()

    def flush(self):
        """Force-emit whatever is buffered (e.g. on mic stop)."""
        if len(self._buf) >= MIN_SPEECH_FRAMES:
            self._emit()
        else:
            self._buf  = []
            self._state = self._STATE_SILENCE

    def _emit(self):
        if len(self._buf) >= MIN_SPEECH_FRAMES:
            segment = b"".join(self._buf)
            self._q.put_nowait(segment)
            log.debug(f"VAD: emitted segment {len(segment)//FRAME_BYTES*FRAME_MS}ms")
        self._buf    = []
        self._state  = self._STATE_SILENCE
        self._trailing = 0


# ── Streaming mic capture ──────────────────────────────────────────────────────

class StreamingMicCapture:
    """
    Continuously reads from the microphone via sounddevice's non-blocking
    InputStream callback.  Each 20 ms frame is VAD-classified and fed
    into a VoiceSegmentBuffer that emits complete speech segments.

    Usage:
        cap = StreamingMicCapture(out_queue)
        cap.start()
        ...
        cap.stop()   # flushes any buffered audio

    out_queue receives raw bytes (16kHz int16 PCM) for each speech segment.
    """

    def __init__(
        self,
        out_queue: AudioChunkQueue,
        vad_aggressiveness: int = 2,
        on_speech_start: Optional[Callable] = None,
        on_speech_end: Optional[Callable] = None,
    ):
        self._q          = out_queue
        self._vad        = VADFilter(vad_aggressiveness)
        self._seg_buf    = VoiceSegmentBuffer(out_queue)
        self._stream     = None
        self._active     = False
        self._frame_buf  = bytearray()   # partial-frame accumulator
        self._on_start   = on_speech_start
        self._on_end     = on_speech_end
        self._in_speech  = False

    def start(self):
        if self._active:
            return
        self._active = True
        self._stream = sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            blocksize=FRAME_SAMPLES,
            dtype="int16",
            channels=1,
            callback=self._callback,
        )
        self._stream.start()
        log.info("🎙 Streaming mic capture started")

    def stop(self):
        self._active = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        self._seg_buf.flush()
        log.info("🎙 Streaming mic capture stopped")

    def _callback(self, indata: bytes, frames: int, time_info, status):
        """Called by sounddevice on the audio thread — must be fast."""
        if not self._active:
            return
        # indata is memoryview of int16; convert to bytes
        raw = bytes(indata)
        self._frame_buf.extend(raw)

        # Process complete 20 ms frames
        while len(self._frame_buf) >= FRAME_BYTES:
            frame = bytes(self._frame_buf[:FRAME_BYTES])
            self._frame_buf = self._frame_buf[FRAME_BYTES:]

            is_speech = self._vad.is_speech(frame)

            # Fire callbacks on speech state change
            if is_speech and not self._in_speech:
                self._in_speech = True
                if self._on_start:
                    self._on_start()
            elif not is_speech and self._in_speech:
                self._in_speech = False
                if self._on_end:
                    self._on_end()

            self._seg_buf.feed(frame, is_speech)


# ── Backward-compatible helpers ────────────────────────────────────────────────

def get_temp_path(suffix: str = ".wav") -> str:
    cfg.ensure_data_dir()
    return str(cfg.DATA_DIR / f"grace_{uuid.uuid4().hex}{suffix}")


def cleanup(path: Optional[str]):
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass


def convert_to_wav(input_path: str, output_path: Optional[str] = None) -> str:
    """Convert any audio file to 16kHz mono WAV (for compatibility)."""
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
        ["ffmpeg", "-y", "-i", input_path, "-ar", "16000", "-ac", "1",
         "-c:a", "pcm_s16le", output_path],
        capture_output=True,
    )
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {r.stderr.decode()[:200]}")
    return output_path


def pcm_bytes_to_float32(pcm: bytes) -> np.ndarray:
    """Convert raw int16 PCM bytes to float32 in [-1.0, 1.0]."""
    audio_i16 = np.frombuffer(pcm, dtype=np.int16)
    return audio_i16.astype(np.float32) / 32768.0
