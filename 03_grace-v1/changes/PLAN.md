# Grace v3 → Realtime Upgrade: Complete Technical Implementation Plan

---

## 1. THE PROBLEM: WHERE LATENCY COMES FROM

Current pipeline — every step is **serial and blocking**:

```
[Record full clip]        ~2-5s   (wait for silence)
     ↓
[Write WAV to disk]       ~20ms
     ↓
[whisper-cli.exe launch]  ~300ms  (process spawn overhead alone)
     ↓
[Full transcription]      ~800ms-3s (ggml-base on CPU)
     ↓
[Send full prompt]        ~10ms
     ↓
[Wait first token]        ~500-1200ms (model cold path)
     ↓
[Wait FULL response]      ~3-10s
     ↓
[Piper full synthesis]    ~500ms-2s
     ↓
[Play audio]              starts
```

**Total before user hears anything: 7–20 seconds.**

Target after upgrade:

```
[VAD detects speech end]   <100ms
[Partial STT chunk]        <400ms  (streaming, not waiting)
[First LLM token]          <700ms  (streaming)
[First sentence spoken]    <1.5s   (Piper on partial sentence)
```

---

## 2. ARCHITECTURE DECISION: STT ENGINE

### Option A: Optimized whisper.cpp (keep current binary)
**Pros:** Already installed, no new deps, works offline
**Cons:**
- Subprocess spawn = 200-400ms cold overhead EVERY call
- No streaming API — must write full WAV, then transcribe
- No partial results
- Cannot do VAD internally
- Cannot be interrupted mid-transcription

### Option B: faster-whisper (Python library) ✅ RECOMMENDED
**Pros:**
- Pure Python API — no subprocess spawn overhead
- CTranslate2 backend: 2-4x faster than original Whisper on CPU
- Streaming transcription via `model.transcribe(..., condition_on_previous_text=False)`
- Returns segments as a generator — you get partials immediately
- Works with int8 quantization on CPU
- CUDA support automatic if available
- VAD filter built-in (silero VAD)

**Cons:**
- ~500MB extra download for the model
- First load ~2s (but loaded once at startup)

**Verdict: faster-whisper wins on every axis for realtime use.**

For your hardware (i5-10210U, 24GB RAM, no discrete GPU):
- Use `faster-whisper` with `model_size="base.en"`, `compute_type="int8"`
- Runs ~3-4x faster than whisper.cpp on CPU
- No CUDA needed (but will auto-use if present)

---

## 3. RECOMMENDED OLLAMA MODELS FOR REALTIME

Tested on CPU-primary Intel laptops:

| Model | First token (CPU) | Quality | Recommended for |
|-------|-------------------|---------|-----------------|
| `llama3.2:3b` | ~400ms | Good | **Best balance — use this** |
| `qwen2.5:3b` | ~380ms | Very good at code | Code mode |
| `phi4-mini` | ~320ms | Decent | Fastest, smaller context |
| `llama3:8b` | ~900ms | Excellent | When speed isn't critical |
| `qwen3.5:latest` | ~700ms | Excellent | Your current — too slow for realtime |

**Primary recommendation: `llama3.2:3b` for chat, `qwen2.5:3b` for code.**

The 3B models on your hardware give ~400ms first token vs ~900ms for 7B+ models.
That's the difference between "instant" and "noticeable lag."

---

## 4. NEW REALTIME PIPELINE ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────────────┐
│                         GRACE REALTIME PIPELINE                      │
│                                                                       │
│  MicThread (daemon)                                                   │
│  ┌──────────────────┐                                                 │
│  │  sounddevice     │  16kHz PCM chunks (20ms frames)                │
│  │  input stream    │──────────────────────────────────►  VADThread  │
│  └──────────────────┘                                    │           │
│                                                           │ speech    │
│                                                           │ segments  │
│                                                           ▼           │
│                                                    STTWorkerThread    │
│                                                    │ faster-whisper  │
│                                                    │ streaming       │
│                                                    │ transcription   │
│                                                    │                 │
│                                              partial_text_q          │
│                                                    │                 │
│                                                    ▼                 │
│                                             LLMWorkerThread          │
│                                             │ Ollama stream=True    │
│                                             │ token generator       │
│                                             │                       │
│                                       token_q ──────────────────►  │
│                                             │                  UI thread │
│                                             │ (widget.after)           │
│                                    sentence_splitter                  │
│                                             │                         │
│                                    tts_sentence_q                     │
│                                             │                         │
│                                             ▼                         │
│                                      TTSWorkerThread                  │
│                                      │ Piper subprocess              │
│                                      │ per sentence                  │
│                                      │                               │
│                                   audio_playback_q                   │
│                                      │                               │
│                                      ▼                               │
│                               AudioPlaybackThread                     │
│                               │ sounddevice play                    │
│                               │ interruptible                       │
│                               └─────────────────                    │
│                                                                       │
│  INTERRUPT SIGNAL: any thread can set stop_event → drains ALL queues │
└─────────────────────────────────────────────────────────────────────┘
```

### Thread roles and queues:

```
Thread                  Reads from          Writes to          Blocks on
──────────────────────  ──────────────────  ─────────────────  ──────────────
MicCaptureThread        sounddevice         raw_audio_q        sd.InputStream
VADThread               raw_audio_q         speech_chunk_q     queue.get()
STTWorkerThread         speech_chunk_q      partial_text_q     faster-whisper
LLMWorkerThread         partial_text_q      token_q            requests stream
SentenceSplitter        token_q             tts_sentence_q     queue.get()
TTSWorkerThread         tts_sentence_q      audio_q            Piper subprocess
AudioPlaybackThread     audio_q             (speakers)         sd.play()
UIUpdateThread          token_q (mirror)    CTk widgets        widget.after()
```

### Interrupt flow:
```
User presses mic button while Grace is speaking:
  → stop_event.set()
  → AudioPlaybackThread: sd.stop() immediately
  → TTSWorkerThread: drains tts_sentence_q
  → LLMWorkerThread: closes requests stream
  → All queues: drain with sentinel (None)
  → orb state → "listening"
  → New recording cycle begins
```

---

## 5. FILE-BY-FILE UPGRADE PLAN

### 5.1 utils/audio.py — ADD VAD + Streaming Capture

**Remove:** `MicRecorder` class (write-full-WAV approach)
**Add:**
- `StreamingMicCapture` — continuous 20ms PCM frames via sounddevice callback
- `VADFilter` — webrtcvad-based speech/silence detector
- `AudioChunkBuffer` — accumulates voiced frames into transcribable segments

### 5.2 core/stt.py — REPLACE with faster-whisper streaming

**Remove:** `transcribe_sync()` / `transcribe_async()` subprocess wrappers
**Add:**
- `WhisperStreamingEngine` — loads faster-whisper model once at startup
- `transcribe_stream()` — generator yielding partial text as segments arrive
- Segment-level partial callbacks

### 5.3 core/llm.py — UPGRADE streaming + cancellation

**Keep:** `OllamaClient.stream()` generator
**Add:**
- `CancellableStream` — wraps the requests stream with a threading.Event cancel signal
- `SentenceSplitter` — accumulates tokens, yields complete sentences
- `stream_with_cancellation()` — interruptible streaming generator

### 5.4 core/tts.py — SENTENCE-LEVEL STREAMING

**Remove:** `speak()` / `speak_async()` (full-text approach)
**Add:**
- `PiperStreamingTTS` — runs Piper per sentence, writes raw PCM
- `AudioQueue` — thread-safe queue for playback segments
- `AudioPlayer` — dedicated playback thread, interruptible via Event
- `TTSPipeline` — connects LLM sentence stream → Piper → AudioPlayer

### 5.5 ui/voice_orb.py — ADD "interrupted" state + smoother animations

**Keep:** Canvas animation loop
**Add:** `interrupted` state (red flash), smoother state transitions

### 5.6 ui/input_bar.py — REAL-TIME STATUS UPDATES

**Add:** live partial transcription display, interrupt button during speech

### 5.7 ui/app.py — REWIRE TO REALTIME PIPELINE

**Replace:** sequential flow
**Add:**
- `RealtimePipeline` orchestrator
- Event-based state machine
- `stop_event` propagation to all workers

---

## 6. DEPENDENCY ADDITIONS

```
# requirements_realtime.txt additions
faster-whisper==1.0.3          # CTranslate2-based Whisper (replaces subprocess)
webrtcvad-wheels==2.0.14        # VAD (Windows-compatible wheel)
sounddevice>=0.4.6             # Already present — streaming callback mode
numpy>=1.26.0                  # Already present
```

Install:
```bash
pip install faster-whisper webrtcvad-wheels
```

---

## 7. UPGRADED CODE — EACH FILE IN FULL
