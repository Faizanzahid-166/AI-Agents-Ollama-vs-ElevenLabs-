# 🎓 SpeakWise — AI English Speaking Practice

Desktop app: **Electron + React + Vite + Tailwind**.
Speech-to-text via **local Whisper CLI** (offline, no API key).
AI tutor via **Ollama phi3:mini** (offline, local).
Text-to-speech via **browser SpeechSynthesis** (built-in, offline).

---

## 📁 Project Structure

```
speakwise/
├── electron/
│   ├── main.js          ← CJS: Electron main + Whisper spawn + Ollama fetch
│   ├── preload.js       ← CJS: contextBridge (secure IPC bridge)
│   └── package.json     ← forces "type":"commonjs" for electron folder
├── 
│   ├── App.jsx          ← root component, state orchestration
│   ├── main.jsx         ← React entry point
│   ├── index.css        ← Tailwind + global styles
│   ├── components/
│   │   ├── ChatMessage.jsx    user & AI chat bubbles
│   │   ├── FeedbackCard.jsx   grammar diff + score card
│   │   ├── InputBar.jsx       text input + mic button
│   │   ├── ScoreRing.jsx      animated SVG score ring
│   │   ├── Sidebar.jsx        session stats + system status
│   │   ├── StatusBar.jsx      Ollama + Whisper status bar
│   │   ├── Waveform.jsx       recording animation
│   │   ├── WelcomeScreen.jsx  empty state + conversation starters
│   │   └── ErrorBanner.jsx    dismissible error messages
│   └── hooks/
│       ├── useSpeech.js  MediaRecorder → PCM → IPC → Whisper + SpeechSynthesis TTS
│       └── useOllama.js  IPC → Ollama REST → structured JSON feedback
├── whisper/                   ← YOU CREATE THIS (see Step 2)
│   ├── whisper-cli.exe
│   └── models/
│       └── ggml-base.en-q5_1.bin
├── index.html
├── vite.config.js
├── tailwind.config.js
├── postcss.config.js
└── package.json               ← "type":"module" for Vite/React side
```

---

## 🚀 Setup — Step by Step

### Step 1 — Install Node.js and Ollama

- **Node.js** v18+: https://nodejs.org
- **Ollama**: https://ollama.ai

```bash
# Start Ollama server
ollama serve

# Pull the AI model (one time, ~2.3 GB)
ollama pull phi3:mini
```

### Step 2 — Set up local Whisper CLI

SpeakWise uses **whisper.cpp** — a fast C++ Whisper port that runs fully offline.

**2a. Download whisper-cli.exe**

Pre-built Windows binary (no install needed):
👉 https://github.com/ggerganov/whisper.cpp/releases

Download the latest `whisper-cli.exe` from the Assets section.

**2b. Download the model**

👉 https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en-q5_1.bin

Direct download (~57 MB, English-only, quantized for speed).

**2c. Place files like this:**

```
speakwise/
└── whisper/
    ├── whisper-cli.exe               ← paste here
    └── models/
        └── ggml-base.en-q5_1.bin    ← paste here
```

**Test it works:**
```bash
cd speakwise/whisper
whisper-cli.exe -m models/ggml-base.en-q5_1.bin -f your_audio.wav -l en -nt -np
```

### Step 3 — Install npm dependencies

```bash
cd speakwise
npm install
```

### Step 4 — Run in development

```bash
npm run dev
```

This starts Vite on port 5173 and Electron simultaneously.

### Step 5 — Build for production

```bash
npm run build
# Output → dist-electron/
```

---

## 🔊 How Voice Works

```
[User clicks 🎤]
      │
      ▼
MediaRecorder (browser) — captures mic audio as webm/opus
      │
[User clicks ⏹]
      │
      ▼
AudioContext.decodeAudioData() — decode to Float32 PCM
      │
      ▼
window.electronAPI.transcribe(pcmBuffer, sampleRate)
      │  (IPC via contextBridge)
      ▼
main.js — resample to 16 kHz → encode WAV → write temp file
      │
      ▼
spawn("whisper-cli.exe", ["-m", model, "-f", wav, "-nt", "-np"])
      │
      ▼
parse stdout → return transcript string
      │
      ▼
React state → send to Ollama → display feedback
      │
      ▼
SpeechSynthesis.speak(aiResponse)  ← TTS plays AI reply
```

---

## 🔒 Security

| Feature | Detail |
|---|---|
| `nodeIntegration: false` | Renderer cannot use Node APIs |
| `contextIsolation: true` | Renderer and preload are isolated JS contexts |
| `contextBridge` | Only 4 named functions exposed to renderer |
| Local-only | No cloud, no API keys, no telemetry |

---

## 🤖 AI Response Format

Ollama returns structured JSON for every message:

```json
{
  "corrected":    "The corrected version of your sentence.",
  "mistakes":     ["Missing article 'the'", "Wrong verb tense"],
  "improved":     "A more natural and fluent phrasing.",
  "response":     "Great effort! That's a common mistake with articles.",
  "score":        78,
  "scoreFeedback":"Good overall, minor grammar issues.",
  "followUp":     "Can you tell me more about what you did on the weekend?"
}
```

---

## 🛠 Troubleshooting

| Problem | Fix |
|---|---|
| **Ollama offline** | Run `ollama serve` in terminal |
| **phi3:mini not found** | Run `ollama pull phi3:mini` |
| **Whisper CLI missing** | Download `whisper-cli.exe` → place in `whisper/` |
| **Model not found** | Download `ggml-base.en-q5_1.bin` → place in `whisper/models/` |
| **Mic access denied** | Windows: Settings → Privacy → Microphone → allow Desktop apps |
| **No speech detected** | Speak louder / closer to mic; min ~1 second of audio |
| **Whisper output garbled** | Audio too short or silent; try speaking a full sentence |
| **Blank screen on launch** | Make sure Vite is running on port 5173 first |

---

## 📦 Tech Stack

| Layer | Technology |
|---|---|
| Desktop shell | Electron 28 |
| UI framework | React 18 + Vite 5 |
| Styling | Tailwind CSS 3 |
| STT | whisper.cpp CLI (local, offline) |
| TTS | Web SpeechSynthesis API (built-in) |
| AI model | Ollama phi3:mini (local, offline) |
| Audio capture | MediaRecorder + AudioContext (browser) |
| IPC | Electron contextBridge |
