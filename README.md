# Local AI Chat

Conversational AI platform with a local-first LLM backend, per-user thread history, knowledge-base RAG, and an agentic ReAct loop.

> **Migration in progress.** The codebase is being restructured to match the architecture and theme of the `agentic-invoice-platform`.  
> New code lives in `backend/` and `frontend/`. The legacy flat-file implementation is preserved at the project root and documented in the [Archive](#archive--previous-architecture) section.

---

## Target Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│ Ingestion          Manual form · File upload (PDF / DOCX / TXT / MD) │
├──────────────────────────────────────────────────────────────────────┤
│ MCP Adapter Layer  KnowledgeBaseAdapter → FAISS + MongoDB metadata    │
├──────────────────────────────────────────────────────────────────────┤
│ Agent Engine       ChatAgent (ReAct loop)                             │
│                    OpenAI-compatible · LM Studio (default) / Ollama  │
│                    Tools: search_knowledge_base · get_document_info   │
├──────────────────────────────────────────────────────────────────────┤
│ Guardrails         Content safety · Rate limiting                     │
├──────────────────────────────────────────────────────────────────────┤
│ Memory             Conversation episodic memory (MongoDB)             │
├──────────────────────────────────────────────────────────────────────┤
│ Data Layer         MongoDB · Redis                                    │
├──────────────────────────────────────────────────────────────────────┤
│ Real-time          WebSocket streaming (agent thoughts + responses)   │
├──────────────────────────────────────────────────────────────────────┤
│ Async Tasks        Celery + Redis (RAG ingestion, scheduled cleanup)  │
├──────────────────────────────────────────────────────────────────────┤
│ Observability      OTEL → Jaeger (traces) + Prometheus/Grafana        │
├──────────────────────────────────────────────────────────────────────┤
│ Admin Portal       React (TS) · Tailwind · Module Federation remote   │
│                    Pages: Dashboard · Chat · Knowledge Base · Login   │
└──────────────────────────────────────────────────────────────────────┘
```

### Project Structure (target)

```
chatbot/
├── backend/
│   ├── app/
│   │   ├── main.py              FastAPI entry + lifespan
│   │   ├── config.py            Pydantic Settings (env-driven)
│   │   ├── agents/
│   │   │   ├── base_agent.py    ReAct loop (THINK → ACT → OBSERVE)
│   │   │   └── chat_agent.py    Chat specialist: KB search tools
│   │   ├── api/
│   │   │   ├── websocket.py     WebSocket — streaming agent events
│   │   │   └── routes/
│   │   │       ├── auth.py      Register / Login / Google OAuth
│   │   │       ├── threads.py   Conversation CRUD + prompt endpoint
│   │   │       ├── context.py   Global context + image context
│   │   │       └── knowledge_base.py  KB CRUD + upload
│   │   ├── db/
│   │   │   ├── mongodb.py       Motor async client + CRUD helpers
│   │   │   └── redis_client.py  Async Redis: pub/sub + cache
│   │   ├── mcp/
│   │   │   ├── base.py          MCPToolBase + adapter registry
│   │   │   └── kb_adapter.py    Knowledge base MCP tools
│   │   ├── memory/
│   │   │   └── memory.py        Episodic memory (MongoDB)
│   │   ├── guardrails/
│   │   │   └── guardrails.py    Content safety + rate limiting
│   │   ├── rag/
│   │   │   └── ingestion.py     Parse → chunk → embed → FAISS
│   │   ├── telemetry/
│   │   │   └── otel.py          OpenTelemetry setup
│   │   └── workers/
│   │       ├── celery_app.py    Celery app definition
│   │       └── tasks.py         ingest_document_task + cleanup
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/                    React 19 · TypeScript · Tailwind CSS
│   └── src/
│       ├── App.tsx              Routes (also the MF exposed component)
│       ├── bootstrap.tsx        Async entry (Module Federation)
│       ├── components/Layout/   Dark sidebar shell
│       ├── pages/               Login · Dashboard · Chat · KnowledgeBase
│       ├── services/api.ts      Typed Axios client
│       ├── hooks/               useWebSocket · useChat
│       └── types/index.ts       Domain types
├── docker-compose.yml           All services incl. observability stack
├── prometheus.yml
├── otel-collector-config.yaml
└── .env.example
```

---

## Quick Start (target — Docker)

### Prerequisites

- Docker Desktop ≥ 4.x with Compose v2
- One of: **LM Studio** (default), OpenAI, Ollama, or any OpenAI-compatible endpoint

### 1. Configure environment

```bash
cp .env.example .env
# Edit .env — set LLM_BASE_URL, LLM_MODEL, JWT_SECRET_KEY
```

```env
# LM Studio (default)
LLM_BASE_URL=http://host.docker.internal:1234/v1
LLM_API_KEY=lm-studio
LLM_MODEL=<model loaded in LM Studio>

# OpenAI
# LLM_BASE_URL=https://api.openai.com/v1
# LLM_API_KEY=sk-...
# LLM_MODEL=gpt-4o

# Ollama
# LLM_BASE_URL=http://host.docker.internal:11434/v1
# LLM_API_KEY=ollama
# LLM_MODEL=llama3.2

JWT_SECRET_KEY=change-me-in-production
```

### 2. Start all services

```bash
docker compose up --build -d
```

### 3. Open the portals

| Service | URL | Notes |
|---------|-----|-------|
| **Chat Portal** | http://localhost:5173 | React frontend (dev) or :3000 (nginx) |
| **API Docs** | http://localhost:8000/api/docs | FastAPI Swagger |
| **Jaeger** | http://localhost:16686 | Distributed traces |
| **Grafana** | http://localhost:3001 | Metrics + logs |
| **Prometheus** | http://localhost:9090 | Raw metrics |

### Micro-frontend integration

The frontend is a **Vite Module Federation remote**. It exposes `./App` at:

```
http://localhost:5173/remoteEntry.js
```

To consume it in a host app (e.g. `agentic-invoice-platform`):

```typescript
// vite.config.ts of the host
federation({
  remotes: {
    chatbot: 'http://localhost:5173/remoteEntry.js',
  },
  shared: ['react', 'react-dom'],
})

// In a route
const ChatApp = React.lazy(() => import('chatbot/App'))
```

---

## Services

| Container | Port | Purpose |
|-----------|------|---------|
| `chatbot-backend` | 8000 | FastAPI — REST API + WebSocket |
| `chatbot-worker` | — | Celery worker — async RAG ingestion |
| `chatbot-beat` | — | Celery beat — scheduled cleanup |
| `chatbot-frontend` | 3000 | React portal (nginx, prod build) |
| `chatbot-mongo` | 27017 | MongoDB — threads, messages, users, KB metadata |
| `chatbot-redis` | 6379 | Redis — task queue + real-time pub/sub |
| `chatbot-otel` | 4317/4318 | OTEL Collector |
| `chatbot-jaeger` | 16686 | Distributed trace viewer |
| `chatbot-prometheus` | 9090 | Metrics store |
| `chatbot-grafana` | 3001 | Dashboards |

---

## Chat Pipeline

```
1. User sends message over WebSocket /ws/chat/{thread_id}?token=...
        ↓
2. ChatAgent — ReAct loop:
   • Decides whether KB search is needed
   • search_knowledge_base(query)   → top-k chunks from FAISS
   • get_document_info(path)        → document metadata
   • Formulates final answer
        ↓
3. Each ReAct step streamed to client:
   {"type": "agent_thinking", "content": "..."}
   {"type": "tool_call",      "tool": "search_knowledge_base", ...}
   {"type": "tool_result",    "chunks": [...]}
   {"type": "agent_response", "content": "Final answer..."}
   {"type": "message_saved",  "message_id": "..."}
        ↓
4. Message + agent thoughts saved to MongoDB
5. Redis pub/sub notifies other connected clients
```

---

## Knowledge Base Pipeline

```
1. POST /api/v1/knowledge-base/files  (multipart upload)
        ↓
2. Celery task: ingest_document_task
   • Parse (PDF / DOCX / TXT / MD) → plain text
   • Recursive character chunking (RAG_CHUNK_SIZE=360)
   • Agentic refinement via LLM (combine / split / keep)
   • Embed each chunk via Ollama nomic-embed-text
   • Store vectors in FAISS (IndexFlatIP, L2-normalised)
   • Store chunk metadata in MongoDB
        ↓
3. Upload returns success only after indexing completes
4. KB available to ChatAgent via MCP search_knowledge_base tool
```

---

## Key API Endpoints

```bash
# Auth
POST /api/v1/auth/register
POST /api/v1/auth/login
GET  /api/v1/auth/google          # OAuth redirect
GET  /api/v1/auth/google/callback

# Threads
GET    /api/v1/threads
POST   /api/v1/threads
GET    /api/v1/threads/{id}
PATCH  /api/v1/threads/{id}
DELETE /api/v1/threads/{id}

# Context
GET    /api/v1/global-context
PUT    /api/v1/global-context
DELETE /api/v1/global-context
GET    /api/v1/threads/{id}/image-contexts
POST   /api/v1/threads/{id}/image-contexts
DELETE /api/v1/threads/{id}/image-contexts/{ctx_id}

# Knowledge Base
GET  /api/v1/knowledge-base
POST /api/v1/knowledge-base/folders
POST /api/v1/knowledge-base/files
GET  /api/v1/knowledge-base/files/chunks?path=...

# Real-time
WS   /ws/chat/{thread_id}?token=...   # Streaming chat
WS   /ws/events                        # Global event feed

# Health
GET  /health
```

---

## Configuration Reference

All settings are read from environment variables (or `.env`):

```env
# App
APP_NAME=Local AI Chat
APP_VERSION=2.0.0

# LLM (OpenAI-compatible)
LLM_BASE_URL=http://localhost:1234/v1
LLM_API_KEY=lm-studio
LLM_MODEL=local-model
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=2048
LLM_TIMEOUT_SECONDS=60

# Vision (image context extraction)
VISION_LLM_MODEL=local-model

# Embeddings (Ollama default — keeps vectors local)
EMBED_BASE_URL=http://localhost:11434
EMBED_MODEL=nomic-embed-text
EMBED_TIMEOUT_SECONDS=120

# Auth
JWT_SECRET_KEY=                  # REQUIRED
JWT_EXPIRE_MINUTES=60

# Google OAuth (optional)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/auth/google/callback
FRONTEND_URL=http://localhost:5173

# Data
MONGODB_URL=mongodb://localhost:27017
MONGODB_DB=chatbot
REDIS_URL=redis://localhost:6379

# RAG
RAG_CHUNK_SIZE=360
RAG_CHUNK_OVERLAP=0
AGENTIC_CHUNK_MODEL=local-model
AGENTIC_CHUNK_WINDOW_SIZE=5
AGENTIC_CHUNK_TARGET_CHARS=360
AGENTIC_CHUNK_MAX_CHARS=1800
AGENTIC_CHUNK_TIMEOUT_SECONDS=300
MAX_DOCUMENT_BYTES=52428800
VECTOR_STORE_NAME=.vector_store
KNOWLEDGE_BASE_DIR=knowledge_base

# Observability
OTEL_ENABLED=false
OTEL_SERVICE_NAME=chatbot-api
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
```

---

## Migration Status

| Component | Status | Notes |
|-----------|--------|-------|
| Backend restructure | ✅ Done | `backend/app/` packages |
| OpenAI-compatible LLM | ✅ Done | Replaces direct Ollama calls |
| MongoDB + Redis | ✅ Done | Replaces SQLite |
| ReAct ChatAgent | ✅ Done | With KB search MCP tools |
| Guardrails | ✅ Done | Content safety + rate limit |
| WebSocket streaming | ✅ Done | Streaming agent thoughts |
| Celery workers | ✅ Done | Async RAG ingestion |
| OTEL telemetry | ✅ Done | Traces + metrics |
| Frontend TS + Tailwind | ✅ Done | Dark theme, indigo accent |
| Module Federation | ✅ Done | Exposes `./App` as MF remote |
| Docker Compose | ✅ Done | Full stack |
| Plug into invoice platform | ⏳ Pending | Add as new tab in host shell |

---

---

# Archive — Previous Architecture

> The following sections document the **original flat-file implementation** still present at the project root (`main.py`, `DATABASE.py`, `auth.py`, `routers/`, etc.).  
> It remains functional and can be run independently. It uses SQLite, direct Ollama calls, and the original React + CSS Modules frontend.

## Original Overview

FastAPI app with persistent threads, global context, per-conversation image context, and an Ollama-compatible local LLM backend.

See [RAG.md](RAG.md) for the original Knowledge Base ingestion pipeline, FAISS vector storage, chunking behaviour, and tuning parameters.

### Original File Layout

```
project root (legacy)
├── main.py                 All routes + LLM helpers
├── DATABASE.py             SQLite helpers (threads, messages, users, context)
├── auth.py                 JWT helpers + get_current_user dependency
├── routers/auth.py         Register / Login / Google OAuth routes
├── knowledge_base_api.py   KB CRUD routes + upload validation
├── rag_ingestion.py        Parse → chunk → embed (Ollama) → FAISS
├── templates.py            Legacy Jinja templates (superseded by React)
├── knowledge_base_templates.py  Legacy KB Jinja (superseded by React)
├── history.db              SQLite database
└── frontend/               Original React + CSS Modules SPA (pre-migration)
```

## Move To A VM

Copy this project folder to the VM. Include `history.db` if you want to keep existing conversations, global context, and per-conversation image context.

Install Python dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Install and start Ollama on the VM, then pull Ministral:

```bash
ollama pull ministral
```

Run the app so it is reachable from outside the VM:

```bash
OLLAMA_MODEL=ministral uvicorn main:app --host 0.0.0.0 --port 8000
```

Open the app from your machine:

```text
http://<VM_IP_ADDRESS>:8000
```

## Original Configuration

```text
OLLAMA_URL=http://localhost:11434/api/generate
OLLAMA_MODEL=ministral
OLLAMA_VISION_MODEL=llava:latest
LLM_TIMEOUT_SECONDS=60
JWT_SECRET_KEY=<required>
JWT_EXPIRE_MINUTES=60
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
FRONTEND_URL=http://localhost:5173
```

## Run Locally On Windows (original)

```powershell
$env:OLLAMA_MODEL="ministral"
$env:JWT_SECRET_KEY="your-secret-key"
uvicorn main:app --host 127.0.0.1 --port 8000
```

Then start the frontend dev server:

```powershell
cd frontend
npm install
npm run dev
```
