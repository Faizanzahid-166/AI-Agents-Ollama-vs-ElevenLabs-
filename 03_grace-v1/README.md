# ✦ Grace v3 — Pure Python Desktop AI Assistant

> A fully local, voice-capable, streaming AI desktop assistant.
> Built entirely in Python — no Electron, no React, no web stack.

---

## 📁 Project Structure

```
grace-v1/
│
├── main.py                        # Entry point — run this
│
├── core/                          # All AI + data logic
│   ├── __init__.py
│   ├── config.py                  # Settings from .env
│   ├── database.py                # PostgreSQL pool (psycopg2)
│   ├── models.py                  # DB schema + all queries
│   ├── llm.py                     # Ollama streaming client
│   ├── memory.py                  # Smart memory: window + semantic + summaries
│   ├── stt.py                     # Whisper STT subprocess wrapper
│   └── tts.py                     # Piper TTS + pyttsx3 fallback
│
├── ui/                            # CustomTkinter UI layer
│   ├── __init__.py
│   ├── app.py                     # Root window — wires everything together
│   ├── sidebar.py                 # Conversation list + mode toggle
│   ├── chat_view.py               # Scrollable message area
│   ├── message_bubble.py          # Individual message with markdown rendering
│   ├── input_bar.py               # Input + voice + TTS + send/stop controls
│   ├── voice_orb.py               # Animated Canvas orb (idle/recording/thinking/speaking)
│   └── theme.py                   # All colours, fonts, spacing — edit here
│
├── utils/                         # Shared helpers
│   ├── __init__.py
│   ├── audio.py                   # Temp files, WAV conversion, MicRecorder
│   ├── markdown.py                # Markdown → tk.Text tag segments
│   └── logger.py                  # Structured logging
│
├── assets/                        # App icons (optional)
├── data/                          # Auto-created: temp audio files
│
├── requirements.txt
├── .env.example
└── STRUCTURE.txt
```

---

## 🖥️ UI Components

| Component | What it does |
|-----------|-------------|
| `VoiceOrb` | Animated canvas orb — 4 states: idle, recording, thinking, speaking |
| `MessageBubble` | Rich text widget with bold, italic, code blocks, headers, bullet lists |
| `ChatView` | Scrollable list of bubbles + welcome screen with suggestion chips |
| `InputBar` | Multi-line input, mic toggle, TTS toggle, send/stop button, model indicator |
| `Sidebar` | Conversation list, new chat, mode switch (Chat ↔ Code), delete |

---

## ⚙️ Prerequisites

| Tool | Notes |
|------|-------|
| Python 3.11+ | Required |
| PostgreSQL 14+ | Local install |
| Ollama | https://ollama.ai |
| ffmpeg | For audio conversion (add to PATH) |
| Whisper binary | Already on your disk |

---

## 🗃️ Step 1 — PostgreSQL

```sql
CREATE DATABASE "03_grace_memory";
-- Tables are auto-created on first run
```

---

## 🤖 Step 2 — Ollama

```bash
ollama pull llama3:latest
ollama pull qwen3.5:latest
# Must be running on port 11434
ollama serve
```

---

## 🐍 Step 3 — Python environment

```bash
cd grace-v3

python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux

pip install -r requirements.txt

# CPU-only PyTorch (saves ~2 GB bandwidth):
pip install torch --index-url https://download.pytorch.org/whl/cpu

# Local TTS voice engine:
pip install pyttsx3

# On Linux: sudo apt install espeak espeak-data
```

---

## 🔧 Step 4 — Configure .env

```bash
cp .env.example .env
```

Edit `.env`:
```env
DB_PASSWORD=your_postgres_password

WHISPER_BIN_DIR=D:\07_code_2025\25_MODELS\models\02_whisper\whisper-bin-x64
WHISPER_MODEL_PATH=D:\07_code_2025\25_MODELS\models\02_whisper\whisper-bin-x64\model\ggml-base.en-q5_1.bin

SENTENCE_TRANSFORMER_PATH=D:\07_code_2025\25_MODELS\models\03_sentence_transformer

# Optional — Piper TTS for better voice quality:
PIPER_BIN_PATH=D:\07_code_2025\25_MODELS\models\piper\piper.exe
PIPER_MODEL_PATH=D:\07_code_2025\25_MODELS\models\piper\en_US-amy-medium.onnx
```

---

## 🚀 Step 5 — Run

```bash
python main.py
```

Grace desktop window opens immediately. First startup initialises the DB tables.

---

## 🎤 Voice Usage

1. Click the **🎙** mic button (or bottom-left of input bar)
2. Speak your message
3. Click **⏹** to stop recording
4. Grace transcribes via Whisper and responds automatically

Enable **🔊 Voice** in the input bar to hear Grace speak responses via Piper / pyttsx3.

---

## ⌨️ Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Enter` | Send message |
| `Shift+Enter` | New line in input |
| `Esc` | (future: close modal) |

---

## 🧠 Memory System

Grace never sends your full history to the LLM. Instead:

1. **Recency window** — last 6 messages always included as context
2. **Semantic recall** — older messages searched by embedding similarity (cosine > 0.55)
3. **Auto-summary** — every 20 messages, older turns are summarised into a compact block
4. **Context injection** — summary + semantic hits prepended to the system prompt

This keeps prompts lean, responses fast, and Grace still "remembers" things from much earlier.

---

## 🎨 Customising the Theme

All visual tokens live in `ui/theme.py`:

```python
# Change the accent colour:
ACCENT_VIOLET = "#7c3aed"    # → try "#059669" for green

# Change fonts:
FONT_FAMILY = "Segoe UI"     # → try "Inter" or "Helvetica"

# Adjust layout:
SIDEBAR_W = 240              # sidebar width in pixels
WINDOW_W  = 1200             # default window width
```

---

## 🔄 Model Switching

Grace automatically picks:
- `llama3:latest` for **Chat mode** (conversation, jokes, life advice)
- `qwen3.5:latest` for **Code mode** (debugging, writing code, explaining algorithms)

Switch via the **Chat / Code** toggle in the sidebar.

To change the models, edit `.env`:
```env
OLLAMA_CHAT_MODEL=llama3:latest
OLLAMA_CODE_MODEL=qwen3.5:latest
```

---

## 📦 Package as Windows EXE (PyInstaller)

```bash
pip install pyinstaller

pyinstaller ^
  --onedir ^
  --windowed ^
  --name "Grace" ^
  --icon "assets/icon.ico" ^
  --add-data "assets;assets" ^
  --hidden-import "customtkinter" ^
  --hidden-import "psycopg2" ^
  --hidden-import "sounddevice" ^
  --hidden-import "soundfile" ^
  main.py

# Output: dist/Grace/Grace.exe
```

> **Note:** The `.env` file must be placed next to `Grace.exe` in the output folder.
> PostgreSQL and Ollama must still be running separately.

---

## 🛠️ Troubleshooting

**Window doesn't open?**
```bash
pip install customtkinter
```

**"Cannot connect to PostgreSQL"?**
→ Start the PostgreSQL service: `net start postgresql-x64-16` (Windows)

**"Ollama offline" status?**
```bash
ollama serve
# Or check: http://localhost:11434
```

**No voice output?**
```bash
pip install pyttsx3
# Linux: sudo apt install espeak espeak-data libespeak-dev
```

**Whisper transcription fails?**
→ Check `WHISPER_BIN_DIR` in `.env` — the folder must contain `whisper.exe` or `main.exe`

**Embeddings not loading?**
→ Verify `SENTENCE_TRANSFORMER_PATH` points to a valid model directory
→ Or set `ENABLE_SEMANTIC_MEMORY=false` to skip embeddings entirely

---

## ⚡ Performance Tips (Intel i5-10210U + 24 GB RAM)

| Setting | Value | Reason |
|---------|-------|--------|
| `OLLAMA_CHAT_MODEL` | `llama3:latest` | Best speed/quality on CPU |
| `MEMORY_WINDOW` | `6` | Less context = faster inference |
| `SUMMARY_THRESHOLD` | `20` | Compress before context bloats |
| Piper voice model | `amy-medium` | Fast synthesis, natural quality |
| PyTorch | CPU build | No GPU needed, saves VRAM |

---

*Grace v3 — Pure Python. Fully local. Always your friend.* ✦
