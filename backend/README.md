# AgentLens — Backend

FastAPI backend for AgentLens. Handles the LangGraph agent, OTel instrumentation, RAG pipeline, dual-layer memory, SSE streaming, and the live metrics API that powers the frontend observability panel.

**Runtime:** Python 3.11.9 · **Framework:** FastAPI · **Agent:** LangGraph (manual ReAct graph) · **LLM:** Gemini via `langchain-google-genai`

---

## Project Structure

```
backend/
├── app/
│   ├── agent/
│   │   ├── graph.py              # LangGraph StateGraph — compile_graph() + get_graph_with_checkpointer()
│   │   ├── state.py              # AgentState TypedDict
│   │   ├── nodes/
│   │   │   ├── reasoner.py       # LLM node — manual agentlens.reasoner span + token/latency recording
│   │   │   ├── tool_executor.py  # Tool node — per-tool child spans + tool metrics
│   │   │   └── memory_writer.py  # Post-graph LTM write node — parses MEMORY_UPDATE lines
│   │   └── tools/
│   │       ├── calculator.py     # Safe math eval via simpleeval
│   │       ├── search.py         # Tavily web search
│   │       ├── weather.py        # wttr.in async weather
│   │       ├── finance.py        # yFinance stock data
│   │       ├── datetime_tool.py  # UTC datetime
│   │       └── document_search.py # RAG tool factory — user_id baked into closure per-request
│   ├── api/
│   │   ├── deps.py               # get_db, get_current_user dependency injection
│   │   └── routes/
│   │       ├── auth.py           # POST /auth/register, POST /auth/login
│   │       ├── chat.py           # POST /chat/stream, GET /chat/history/{thread_id}
│   │       ├── threads.py        # CRUD /threads
│   │       ├── memory.py         # CRUD /memory/profile
│   │       ├── documents.py      # POST /documents/upload, GET /documents/, DELETE /documents/{sha256}
│   │       ├── metrics.py        # GET /metrics/session/{session_id}
│   │       └── health.py         # GET /health — DB + OTel liveness
│   ├── core/
│   │   ├── config.py             # Pydantic Settings — all env vars
│   │   ├── exceptions.py         # Typed exception hierarchy + FastAPI handlers
│   │   ├── security.py           # bcrypt hashing, JWT sign/verify
│   │   └── logging.py            # Structured logging + LoggingInstrumentor
│   ├── db/
│   │   ├── base.py               # SQLAlchemy async engine + session factory
│   │   └── models.py             # User, Thread, UserProfile, Document ORM models
│   ├── memory/
│   │   ├── checkpointer.py       # STM checkpointer config — SQLite (local) / Postgres (prod)
│   │   └── ltm_store.py          # LTM CRUD — manual agentlens.ltm spans + LTM metrics
│   ├── rag/
│   │   ├── store.py              # Vector store singleton — ChromaDB/Pinecone + agentlens.rag spans
│   │   └── ingestor.py           # File validation, extraction, chunking, batch embedding
│   ├── schemas/                  # Pydantic request/response models
│   ├── services/
│   │   ├── auth_service.py       # Register, login — bcrypt + JWT
│   │   ├── chat_service.py       # SSE orchestration + agentlens.chat.stream root span
│   │   ├── thread_service.py     # Thread CRUD service layer
│   │   ├── document_service.py   # Document ingest, list, delete
│   │   └── metrics_service.py    # Session metrics aggregation for /metrics/session
│   ├── telemetry.py              # OTel bootstrap + 6 custom metrics + session store
│   └── main.py                   # App factory + lifespan
├── .env.example
├── requirements.txt
└── runtime.txt                   # python-3.11.9 — pins Render Python version
```

---

## Local Development

### Prerequisites

- Python 3.11+
- A SigNoz Cloud account (free tier works) — or remove OTel flags to run without telemetry

### Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Fill in your keys in .env
```

### Running with OTel (recommended)

```bash
opentelemetry-instrument \
  --traces_exporter otlp \
  --metrics_exporter otlp \
  --logs_exporter otlp \
  --exporter_otlp_endpoint $OTLP_ENDPOINT \
  --exporter_otlp_headers "signoz-ingestion-key=$SIGNOZ_INGESTION_KEY" \
  --service_name agentlens \
  uvicorn app.main:app --reload --port 8000
```

### Running without OTel

```bash
uvicorn app.main:app --reload --port 8000
```

Spans and metrics will be no-ops. Everything else works normally.

Swagger UI: `http://localhost:8000/docs`

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GOOGLE_API_KEY` | Yes | Gemini API key — used for LLM calls and embeddings |
| `SIGNOZ_INGESTION_KEY` | Yes (with OTel) | SigNoz Cloud ingestion key |
| `OTLP_ENDPOINT` | Yes (with OTel) | `https://ingest.us2.signoz.cloud:443` for SigNoz Cloud us2 |
| `OTEL_SERVICE_NAME` | Yes (with OTel) | `agentlens` |
| `JWT_SECRET_KEY` | Yes | Random secret — generate with `openssl rand -hex 32` |
| `TAVILY_API_KEY` | Yes | Tavily web search API key |
| `DATABASE_URL` | No | Leave empty for SQLite (local). Set Supabase Postgres URL for prod |
| `SQLITE_DB_PATH` | No | Default: `./data/agentlens.db` |
| `CHECKPOINT_DB_PATH` | No | Default: `./data/checkpoints.db` |
| `PINECONE_API_KEY` | No | Leave empty for ChromaDB (local). Set for Pinecone (prod) |
| `PINECONE_INDEX_NAME` | No | Default: `agentlens-rag` |
| `CHROMA_PATH` | No | Default: `./data/chroma` |
| `FRONTEND_URL` | Yes | CORS origin — `http://localhost:5173` (local) or Vercel URL (prod) |
| `APP_ENV` | No | `development` or `production` |

---

## API Reference

### Auth

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register` | Register — returns JWT on success, 409 if email exists |
| POST | `/auth/login` | Login — returns JWT on success, 401 on invalid credentials |

### Chat

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/chat/stream` | ✓ | Send a message, receive SSE stream |
| GET | `/chat/history/{thread_id}` | ✓ | Full message history for a thread |

#### SSE Event Types

```json
{"type": "text", "content": "..."}
{"type": "tool_start", "tool_name": "...", "tool_input": {}}
{"type": "tool_end", "tool_name": "...", "tool_output": "...", "sources": []}
{"type": "memory_update", "keys": ["name", "location"]}
{"type": "done"}
{"type": "error", "message": "..."}
```

### Threads

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/threads` | ✓ | Create a new thread |
| GET | `/threads` | ✓ | List all threads (ordered by recent activity) |
| GET | `/threads/{id}` | ✓ | Get a single thread |
| PATCH | `/threads/{id}` | ✓ | Rename a thread |
| DELETE | `/threads/{id}` | ✓ | Delete a thread |

### Memory (LTM)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/memory/profile` | ✓ | Read all stored profile facts |
| PUT | `/memory/profile` | ✓ | Upsert a profile entry |
| PATCH | `/memory/profile/{key}` | ✓ | Update a single entry by key |
| DELETE | `/memory/profile/{key}` | ✓ | Delete a single entry |
| DELETE | `/memory/profile` | ✓ | Clear entire profile |

### Documents

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/documents/upload` | ✓ | Upload PDF/TXT — validates, chunks, embeds, stores |
| GET | `/documents/` | ✓ | List all uploaded documents with metadata |
| DELETE | `/documents/{sha256}` | ✓ | Hard delete from vector store + documents table |

### Metrics

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/metrics/session/{session_id}` | ✓ | Live OTel metrics for a session — 204 if no data yet |

#### Metrics Response Shape

```json
{
  "session_id": "uuid",
  "tokens": { "input": 0, "output": 0, "total": 0 },
  "llm": { "calls": 0, "last_latency_ms": 0.0 },
  "tools": {
    "total_calls": 0, "successful": 0, "failed": 0,
    "calls": [{ "name": "...", "success": true, "latency_ms": 0.0 }]
  },
  "retrieval": {
    "total_queries": 0, "avg_latency_ms": null,
    "max_latency_ms": null, "latencies_ms": []
  },
  "ltm": { "reads": 0, "writes": 0, "total": 0 },
  "session": { "started_at": 0.0, "last_updated": 0.0, "duration_seconds": 0.0 }
}
```

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Returns DB status + OTel telemetry status. 200 when healthy, 503 when DB unreachable |

```json
{
  "status": "ok",
  "service": "AgentLens",
  "checks": {
    "database": "ok",
    "telemetry": "active"
  }
}
```

---

## Agent Architecture

### Graph Design

The ReAct graph is built manually via LangGraph's `StateGraph` — not the prebuilt `create_react_agent`. This was necessary to support the post-graph `memory_writer` node, which requires a database session injected at request time.

```
START → reasoner → [tool call?] → tool_executor → reasoner (loop)
                 → [done?]      → END
                                  ↓
                              memory_writer (post-graph, fresh DB session)
```

**Key design decision:** The graph is compiled fresh per-request via `get_graph_with_checkpointer()`. This is intentional — `document_search` is a factory tool that captures `user_id` in a closure, making each tool list user-scoped and non-shareable. StateGraph construction is cheap; the LLM call is the bottleneck.

`compile_graph()` runs at startup (FastAPI lifespan) to validate the full construction path — tools, LLM binding, graph topology — before the first request arrives. It does not store a compiled graph.

**Recursion limit:** `recursion_limit=10` — max 5 tool-call cycles per response. Prevents runaway ReAct loops and unexpected cost spikes.

### Memory Architecture

**Short-Term Memory (STM):** LangGraph checkpointing. Full agent state (messages, tool calls) persisted per turn per thread. SQLite locally, AsyncPostgresSaver on prod.

**Long-Term Memory (LTM):** Key-value profile store backed by SQLAlchemy. The agent extracts persistent user facts via `MEMORY_UPDATE: key=X value=Y` lines in its responses. `memory_writer` parses these post-graph and persists them. On each new request, the full profile is injected into the system prompt via `ltm_context`.

### RAG Pipeline

```
Upload → validate (size, type, page count) → SHA256 dedup check
→ extract text (PyMuPDF for PDF, decode for TXT)
→ RecursiveCharacterTextSplitter (chunk_size=1000, overlap=200)
→ validate chunk count (max 50)
→ batch embed — Gemini gemini-embedding-001, RETRIEVAL_DOCUMENT task type
→ write to ChromaDB (local) or Pinecone (prod)
→ persist metadata to documents table
```

**Deduplication:** SHA256 hash. Same file uploaded twice → skips re-embedding entirely.

**Retrieval:** top-k=3 cosine similarity, threshold=0.5. Chunks below threshold discarded.

**Vector store switching:** env-based. `PINECONE_API_KEY` absent → ChromaDB. Present → Pinecone. Both implement the same interface (`add`, `query`, `delete_by_sha256`, `has_sha256`).


### Agentic Document Context Injection

Before each request, `build_doc_context()` in `chat_service.py` queries the database for the user's uploaded documents and injects the result directly into the system prompt as `doc_context`.

- **No documents uploaded** → agent receives `[System: User has no documents uploaded. Do not call document_search.]` — the tool call is eliminated before reasoning begins
- **Documents exist** → agent receives filenames and an instruction to only call `document_search` when the query is document-relevant

This means the agent's decision to query the vector store is grounded in live database state, not prompt guessing. It eliminates unnecessary Pinecone round trips and prevents the agent from hallucinating document content when none exists.
---
## Exception Hierarchy

```
NeuroGraphException (base)
├── AgentException                → 500
├── ThreadNotFoundException       → 404
├── ThreadServiceException        → 500
├── ProfileEntryNotFoundException → 404
├── LTMException                  → 500
├── RAGException                  → 500 / 422
├── DocumentNotFoundException     → 404
├── UnauthorizedException         → 401
├── ForbiddenException            → 403
└── UserAlreadyExistsException    → 409
```

Global handler catches all `NeuroGraphException` subclasses — logs warnings for 4xx, errors with stack traces for 5xx. Fallback handler catches everything else as a generic 500. Nothing internal leaks to the client.

---

## OTel Instrumentation Details

The `opentelemetry-instrument` CLI bootstraps the TracerProvider and MeterProvider before the app starts. `telemetry.py` runs at lifespan startup and registers the 6 custom metric instruments on top.

`is_telemetry_active()` in `telemetry.py` checks whether a real SDK TracerProvider is registered by starting a test span and checking if it's a `NonRecordingSpan`. This is what powers the `"telemetry": "active"` check in `/health`.

Session metrics (in `telemetry.py`) are stored in a thread-safe in-memory dict (`_session_store`) with a 1-hour TTL. Each instrumented node reads the current `session_id` from a `ContextVar` set at stream start — no signature changes needed across the call stack.