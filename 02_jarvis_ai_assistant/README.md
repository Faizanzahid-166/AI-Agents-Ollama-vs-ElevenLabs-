# JARVIS — Fully Offline AI Assistant
## Complete Setup & Usage Guide (Windows)

---

## What This Is

A 100% offline, Jarvis-style AI assistant that runs entirely on your Windows machine. No internet. No cloud. No external APIs. Everything — voice recognition, embeddings, file management, memory — runs locally.

---

## System Architecture

```
jarvis_ai_assistant/
├── main.py                     ← Entry point — boots system, runs REPL
├── requirements.txt
├── .env.example
│
├── config/
│   └── settings.py             ← All paths, thresholds, DB config
│
├── database/
│   └── db.py                   ← PostgreSQL pool + full DDL schema
│
├── core/
│   ├── ai_engine.py            ← Intent classification + response generation
│   ├── speech_to_text.py       ← Whisper binary wrapper (offline STT)
│   ├── memory.py               ← Embeddings + semantic search (pgvector)
│   └── task_manager.py         ← Task CRUD + daily suggestions
│
├── agents/
│   └── file_manager.py         ← Full file/folder CRUD agent
│
├── utils/
│   └── logger.py               ← Structured rotating log setup
│
└── logs/                       ← Auto-created at runtime
```

---

## PostgreSQL Schema (jarvisg_02_memory)

| Table | Purpose |
|---|---|
| `chat_history` | Every user ↔ assistant turn, with 384-dim vector embedding |
| `user_commands` | Parsed commands with intent + result status |
| `file_operations` | Full audit trail of every file operation |
| `tasks` | Tasks/reminders with priority, due date, status, embedding |
| `memory_snapshots` | Summarised long-term memory entries |
| `user_preferences` | Key-value settings store |
| `activity_log` | Daily activity diary |

Vector search powered by **pgvector** (`<=>` cosine distance operator).

---

## Prerequisites

### 1. Python 3.10+
```
python --version   # must be 3.10 or higher
```

### 2. PostgreSQL 14+ with pgvector extension
```sql
-- In psql as superuser:
CREATE DATABASE jarvisg_02_memory;
CREATE EXTENSION IF NOT EXISTS vector;
```

### 3. Your local models (already downloaded)
- Whisper binary:  `D:\07_code_2025\25_MODELS\models\whisper\whisper-bin-x64\main.exe`
- Whisper model:   `ggml-base.en-q5_1.bin`  (or `ggml-medium.bin` for higher accuracy)
- Sentence model:  `D:\07_code_2025\25_MODELS\models\sentence_transformer`

---

## Installation

### Step 1 — Clone / extract project
```
cd C:\Projects
# copy jarvis_ai_assistant folder here
cd jarvis_ai_assistant
```

### Step 2 — Create virtual environment
```
python -m venv .venv
py -3.11 -m venv .venv
.venv\Scripts\activate
```

### Step 3 — Install dependencies
```
pip install -r requirements.txt

# For CPU-only PyTorch (smaller, faster install):
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

### Step 4 — Configure environment
Copy `.env.example` to `.env` and fill in your values:
```
JARVIS_DB_HOST=localhost
JARVIS_DB_PORT=5432
JARVIS_DB_NAME=jarvisg_02_memory
JARVIS_DB_USER=postgres
JARVIS_DB_PASS=your_password

WHISPER_BIN_DIR=D:\07_code_2025\25_MODELS\models\02_whisper\whisper-bin-x64
WHISPER_MODEL=D:\07_code_2025\25_MODELS\models\02_whisper\whisper-bin-x64\model\ggml-base.en-q5_1.bin
SENTENCE_TRANSFORMER_PATH=D:\07_code_2025\25_MODELS\models\03_sentence_transformer
```

### Step 5 — Run Jarvis
```
# Text mode (no microphone needed)
python main.py

# Voice mode (uses Whisper STT)
python main.py voice
```

The schema is applied automatically on first run.

---

## Example Commands

### File Operations
```
Create a Word file named ProjectPlan
Create an Excel spreadsheet called Budget2024
Make a folder called ClientWork on my Desktop
Delete the file old_draft.txt
Move all PDFs to Documents
Organize my Downloads folder
Read file C:\Users\You\Documents\notes.txt
```

### Tasks
```
What should I do today?
Add task: finish the quarterly report
Add task: call client tomorrow - urgent
Show my pending tasks
Complete task 3
What is my schedule for this week?
```

### Memory / History
```
What did I work on yesterday?
Summarize my activities from last week
Do you remember what I said about the project?
What were we discussing earlier?
```

### General
```
Hello
What can you do?
Help
What is my schedule today?
```

---

## How the AI Brain Works (Offline)

Since no external LLM is used, Jarvis uses a **3-tier intent pipeline**:

```
User Input
    │
    ▼
[Tier 1] Keyword scan        → Fast O(n) string match
    │ (confidence < 0.6)
    ▼
[Tier 2] Regex patterns      → Structural command parsing
    │ (confidence < 0.5)
    ▼
[Tier 3] Embedding cosine    → Semantic similarity against example phrases
    │                           (sentence-transformer, local model)
    ▼
Intent + Params

    │
    ▼
Route to handler:
  file_operation  → FileManager agent
  task_query      → TaskManager
  memory_query    → MemorySystem (pgvector semantic search)
  schedule_query  → TaskManager.get_schedule_summary()
  system_organize → FileManager.auto_organize()
  general         → AIEngine response templates + memory context
```

---

## Memory System

Every conversation turn is:
1. Stored in `chat_history` with its **384-dimensional sentence embedding**
2. Indexed with `ivfflat` in pgvector for sub-millisecond cosine search

When you ask "what did I work on last week?", Jarvis:
1. Embeds your query
2. Runs `ORDER BY embedding <=> query_vec` in PostgreSQL
3. Returns the top-K most semantically similar past messages
4. Formats them as a human-readable summary

---

## Upgrading to a Local LLM (Optional, Future)

To add a local LLM for richer responses (keeping everything offline):

1. Install [Ollama](https://ollama.com/) — completely local
2. Pull a model: `ollama pull mistral` or `ollama pull llama3`
3. In `ai_engine.py`, add an Ollama call in `respond()`:
```python
import ollama
response = ollama.chat(model='mistral', messages=[
    {'role': 'system', 'content': 'You are Jarvis, an offline assistant.'},
    {'role': 'user', 'content': text}
])
return response['message']['content']
```

No API keys. Still 100% offline.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `psycopg2.OperationalError` | Check PostgreSQL is running; verify `.env` credentials |
| `pgvector not found` | Run `CREATE EXTENSION vector;` in the database as superuser |
| `sentence_transformers` import error | `pip install sentence-transformers` |
| `sounddevice` no devices | Check mic drivers; use text mode with `python main.py` |
| Whisper binary not found | Update `WHISPER_BIN_DIR` in `.env` to exact path |
| `torch` install slow | Use CPU wheel: `pip install torch --index-url .../cpu` |

---

## License

MIT — use freely, modify as needed.
