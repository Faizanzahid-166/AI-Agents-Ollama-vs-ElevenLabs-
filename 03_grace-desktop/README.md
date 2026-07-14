# 🌟 Grace Desktop v2.0 — Real-Time Voice AI Assistant

> ChatGPT-style desktop app. 100% local. Voice-to-voice. Token streaming. Smart memory.

---

## 📁 Full Project Structure

```
grace-desktop/
├── package.json                     # Electron build config
│
├── electron-app/
│   ├── main.js                      # Electron main process
│   └── preload.js                   # Secure IPC bridge
│
├── frontend-react/
│   ├── index.html
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── package.json
│   └── src/
│       ├── main.jsx                 # React entry
│       ├── App.jsx                  # Root layout
│       ├── index.css                # Global styles
│       ├── stores/
│       │   └── graceStore.js        # Zustand global state + WS client
│       ├── hooks/
│       │   └── useVoiceRecorder.js  # MediaRecorder + STT upload
│       └── components/
│           ├── TitleBar.jsx         # Custom titlebar + connection status
│           ├── Sidebar.jsx          # Conversation list
│           ├── ChatWindow.jsx       # Message list + streaming
│           ├── MessageBubble.jsx    # Markdown + syntax highlighting
│           ├── ChatInput.jsx        # Input bar + voice + mode toggle
│           └── VoiceOrb.jsx         # Animated voice visualization
│
└── backend-fastapi/
    ├── main.py                      # FastAPI app + lifespan
    ├── config.py                    # All settings
    ├── database.py                  # Async PostgreSQL engine
    ├── models.py                    # User, Conversation, Message, Summary
    ├── requirements.txt
    ├── .env.example
    ├── routes/
    │   ├── ws_chat.py               # WebSocket /ws/chat (streaming core)
    │   └── api.py                   # REST: conversations, voice, health
    ├── services/
    │   ├── llm_service.py           # Ollama streaming + model switching
    │   ├── memory_service.py        # Smart memory + summaries + semantic recall
    │   ├── stt_service.py           # Whisper STT (async subprocess)
    │   └── tts_service.py           # Piper TTS sentence streaming
    └── utils/
        └── audio_utils.py           # Temp files, WAV conversion
```

---

## ⚡ Architecture: How Streaming Works

```
User types / speaks
       │
       ▼
[React UI]  ──── WebSocket ────►  [FastAPI /ws/chat]
                                         │
                                  ┌──────┴───────┐
                                  │ Memory Query │  ← last 6 msgs + semantic hits
                                  └──────┬───────┘
                                         │
                                  ┌──────▼───────┐
                                  │ Ollama Stream│  stream=True → token generator
                                  └──────┬───────┘
                                         │ tokens
                               ┌─────────┴──────────┐
                               │                    │
                        ► WS token msg        ► Piper TTS
                          (UI renders live)     (sentence chunks)
                               │                    │
                        [React: append]      [PCM audio → WS]
                               │                    │
                        [Streaming cursor]   [AudioContext plays]
                               │
                        [done msg → save to DB]
```

**Result:** First word appears in ~300ms. Grace speaks while still generating.

---

## 🗃️ Step 1 — PostgreSQL Setup

```sql
CREATE DATABASE "03_grace_memory";
\c 03_grace_memory
-- Tables are auto-created on startup
```

---

## 🤖 Step 2 — Ollama

```bash
ollama pull llama3:latest
ollama pull qwen3.5:latest
# Ollama must be running on port 11434
```

---

## 🐍 Step 3 — Backend

```bash
cd grace-desktop/backend-fastapi
python -m venv venv
venv\Scripts\activate        # Windows

pip install -r requirements.txt
pip install pyttsx3           # Local TTS fallback

cp .env.example .env
# Edit .env — set DB password + model paths

python main.py
# → ws://localhost:8000/ws/chat
# → http://localhost:8000/docs
```

---

## 🖥️ Step 4 — Frontend (Dev mode)

```bash
cd grace-desktop/frontend-react
npm install
npm run dev
# → http://localhost:5173
```

---

## ⚡ Step 5 — Electron Desktop App (Dev)

```bash
cd grace-desktop
npm install

# Run everything together:
npm run dev
# This starts: React (5173) + Electron window
```

---

## 📦 Step 6 — Build Windows EXE

```bash
cd grace-desktop

# 1. Build React
cd frontend-react && npm run build && cd ..

# 2. Package Electron → NSIS installer
npm run build

# Output: dist-electron/Grace Setup 2.0.0.exe
```

> **Note:** The EXE bundles the Electron app + React build. The Python backend runs separately (or bundle it with PyInstaller — see below).

### Bundle Backend with PyInstaller (optional)

```bash
cd backend-fastapi
pip install pyinstaller
pyinstaller --onedir --name grace-backend main.py
# Output: dist/grace-backend/grace-backend.exe
# Copy dist/grace-backend/ into electron-app/resources/backend/
```

Then update `electron-app/main.js` `startBackend()` to use:
```js
const exe = path.join(process.resourcesPath, 'backend', 'grace-backend.exe')
backendProcess = spawn(exe, [], { cwd: ... })
```

---

## 🔌 WebSocket Protocol Reference

```
Client → Server:
  { "type": "chat", "user_id": "u1", "conv_id": null, "message": "Hello", "mode": "chat", "tts": false }
  { "type": "stop" }
  { "type": "ping" }

Server → Client:
  { "type": "token",      "content": "Hey" }
  { "type": "tts_chunk",  "sentence": "Hey there!", "audio_b64": "...", "audio_format": "pcm_16k" }
  { "type": "done",       "full_response": "...", "conv_id": "uuid" }
  { "type": "title_update","conv_id": "uuid", "title": "Fixing the async bug" }
  { "type": "error",      "message": "Ollama not running" }
  { "type": "pong" }
```

---

## 🧠 Smart Memory System

Grace never sends your entire history to the LLM. Instead:

1. **Recency window** — last 6 messages always included
2. **Semantic recall** — embeddings searched for relevant older messages (cosine similarity > 0.55)
3. **Auto-summarization** — every 20 messages, older ones are summarized and compressed
4. **Context injection** — summary + semantic hits prepended as system context

This keeps prompts lean, fast, and relevant.

---

## 🎤 Piper TTS Setup (Windows)

```
1. Download Piper from: https://github.com/rhasspy/piper/releases
2. Extract to: D:\07_code_2025\25_MODELS\models\piper\
3. Download voice model: en_US-amy-medium.onnx
   from: https://huggingface.co/rhasspy/piper-voices
4. Update .env:
   PIPER_BIN_PATH=D:\...\piper\piper.exe
   PIPER_MODEL_PATH=D:\...\piper\en_US-amy-medium.onnx
```

If Piper isn't available, Grace auto-falls back to pyttsx3 (Windows SAPI voices).

---

## 🔧 Performance Tuning (i5-10210U)

| Setting | Recommended Value | Why |
|---------|-------------------|-----|
| `OLLAMA_MODEL` | `llama3:latest` | Fast on CPU, good quality |
| `num_ctx` | `4096` | Fits in 24GB RAM comfortably |
| `MEMORY_WINDOW` | `6` | Minimal context = faster |
| `SUMMARY_THRESHOLD` | `20` | Summarize before context bloats |
| Piper voice | `amy-medium` | Fast synthesis, good quality |

---

## 🛠️ Troubleshooting

**WS stays "connecting"?**
→ Make sure `python main.py` is running and shows "Ready"

**Ollama timeout?**
→ Run `ollama list` — models must be pulled first
→ First response is slow (model loading) — subsequent ones are fast

**No audio from TTS?**
→ Check Piper paths in `.env`
→ Fallback to pyttsx3: `pip install pyttsx3`

**PostgreSQL connection refused?**
→ Start PostgreSQL service: `net start postgresql-x64-16`

---

*Built for speed. Built to feel alive. Grace v2.0* 🌟
