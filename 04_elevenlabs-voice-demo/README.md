# ElevenLabs AI Voice Assistant — Demo

A minimal full-stack demo: click a button, talk to an ElevenLabs
Conversational AI agent in real time, click again to stop. No auth, no
database, no persistence — exactly as scoped.

## How it works

The backend's only job is to create the ElevenLabs agent server-side (so
your API key never reaches the browser) and hand back its `agentId`. The
frontend then talks to ElevenLabs **directly** using `@elevenlabs/react` —
audio never passes through your backend at all; it's a live WebRTC
connection straight from the browser to ElevenLabs.

```
Browser                Backend                  ElevenLabs
   │  POST /api/agent      │                          │
   │──────────────────────▶│  agents.create()         │
   │                       │─────────────────────────▶│
   │                       │◀─────────────────────────│
   │◀──────────────────────│  { agentId }             │
   │                                                   │
   │  startSession({ agentId })  — direct WebRTC ─────▶│
   │◀──────────────────── live voice audio ───────────▶│
```

## Setup

### 1. Backend

```bash
cd backend
npm install
cp .env.example .env    # paste your ElevenLabs API key into ELEVENLABS_API_KEY
npm run dev             # http://localhost:5000
```

Get an API key at https://elevenlabs.io/app/settings/api-keys. It only
needs to live in the backend's `.env` — it's never sent to the browser.

### 2. Frontend

```bash
cd frontend
npm install
cp .env.example .env     # defaults to http://localhost:5000, adjust if needed
npm run dev              # http://localhost:5173
```

### 3. Try it

Open http://localhost:5173, click **Start Talking**, allow microphone
access, and speak. Click **End Conversation** to stop.

## A few implementation notes

- **Agent creation and caching.** The spec's example code creates a new
  agent on every call — taken literally, that would spawn a fresh
  ElevenLabs agent on every page load, cluttering your workspace since
  there's no database to remember an ID across restarts. I split the
  difference: `backend/src/services/elevenlabsService.js` caches the
  created agent in memory for the life of the Node process. Restarting the
  backend creates a new agent; while it's running, repeated clicks reuse
  the same one.
- **Public agent, no signed URLs.** Since the spec has no auth anywhere,
  the agent is created without ElevenLabs' `enable_auth`/allowlist
  settings, so the frontend can connect with just the `agentId` — no
  signed-URL server round-trip needed. If you later want to lock the agent
  down to your domain, see ElevenLabs' agent authentication docs and add a
  `/signed-url` backend route.
- **The "Thinking" state is a heuristic.** The ElevenLabs React SDK only
  reports `listening` or `speaking` as a conversation mode — there's no
  distinct event for the gap between you finishing a sentence and the
  agent starting its reply. `VoiceAgent.jsx` approximates it by watching
  input volume: once it's been quiet for ~550ms while still in "listening"
  mode, the UI shows "Thinking" until the agent actually starts speaking.
  It's a good-enough approximation for a demo, not an SDK guarantee.
- **Design.** Three conversation phases get three distinct accent colors —
  teal (listening), amber (thinking), violet (speaking) — so the mic
  ring's color always tells you the state even muted. Space Grotesk for
  the heading, Inter for body text, IBM Plex Mono for the status readout.

## Stack

- Backend: Node.js, Express, `@elevenlabs/elevenlabs-js` (official SDK)
- Frontend: React 19, Vite, Tailwind CSS v4, `@elevenlabs/react`, Axios
