# NeuroGraph AI — Backend

A production-focused conversational AI agent built with LangGraph, FastAPI, and Gemini 3.1 Flash Lite. The system features a manually constructed ReAct graph, dual-layer memory architecture (STM + LTM), and Dynamic Agentic RAG — runtime document ingestion with agent-driven retrieval decisions, not pipeline-forced retrieval.

---


## Architecture

```
FastAPI Backend
│
├── /chat          ├── /threads       ├── /memory        ├── /documents
│                  │                  │                  │
└──────────────────┴──────────────────┴──────────────────┘
                              │
                    ┌─────────▼──────────┐
                    │  LangGraph ReAct   │
                    │      Agent         │
                    │                    │
                    │  reasoner          │
                    │     │              │
                    │     ▼              │
                    │  tool_executor     │
                    │     │              │
                    │     └──► reasoner  │
                    │           │        │
                    │           ▼        │
                    │          END       │
                    └─────────┬──────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
    ┌─────────▼──────┐ ┌──────▼──────┐ ┌─────▼──────────┐
    │   STM          │ │    LTM      │ │   RAG Store    │
    │                │ │             │ │                │
    │ SqliteSaver    │ │ user_profile│ │ ChromaDB       │
    │ (local)        │ │ table       │ │ (local)        │
    │                │ │             │ │                │
    │ AsyncPostgres  │ │ SQLite /    │ │ Pinecone       │
    │ (prod)         │ │ Postgres    │ │ (prod)         │
    └────────────────┘ └─────────────┘ └────────────────┘

Tools registered in agent:
  calculator │ tavily_search │ weather │ finance │ get_datetime │ document_search
```

---


## Tech Stack

| Layer | Technology |
|---|---|
| Framework | FastAPI |
| Agent | LangGraph (manual ReAct graph) |
| LLM | Gemini 3.1 Flash Lite via `langchain-google-genai` |
| Embeddings | Gemini `gemini-embedding-001` via `google-genai` SDK |
| STM | LangGraph `AsyncSqliteSaver` / `AsyncPostgresSaver` |
| LTM | SQLAlchemy + SQLite (dev) / Postgres (prod) |
| Vector Store | ChromaDB (dev) / Pinecone (prod) |
| PDF Extraction | PyMuPDF (`fitz`) |
| Observability | LangSmith |
| Config | Pydantic Settings |
| Streaming | FastAPI `StreamingResponse` + SSE |

---


## Project Structure

```
backend/
├── app/
│   ├── api/
│   │   ├── deps.py                  # Dependency injection — get_db, get_current_user
│   │   └── routes/
│   │       ├── auth.py              # POST /auth/register, POST /auth/login
│   │       ├── chat.py              # POST /chat/stream, GET /chat/history/{id}
│   │       ├── threads.py           # CRUD /threads
│   │       ├── memory.py            # CRUD /memory/profile
│   │       ├── documents.py         # POST /documents/upload, GET /documents/, DELETE /documents/{sha256}
│   │       └── health.py            # GET /health — DB liveness check
│   ├── agent/
│   │   ├── graph.py                 # LangGraph graph definition
│   │   ├── state.py                 # AgentState TypedDict
│   │   ├── nodes/
│   │   │   ├── reasoner.py          # LLM reasoning node + system prompt
│   │   │   ├── tool_executor.py     # Tool execution node
│   │   │   └── memory_writer.py     # LTM write node — returns saved keys
│   │   └── tools/
│   │       ├── calculator.py
│   │       ├── search.py            # Tavily web search
│   │       ├── weather.py
│   │       ├── finance.py           # yFinance
│   │       ├── datetime_tool.py
│   │       └── document_search.py   # RAG tool — per-request factory, user_id baked into closure
│   ├── core/
│   │   ├── config.py                # Pydantic Settings
│   │   ├── exceptions.py            # Custom exception hierarchy
│   │   ├── security.py              # bcrypt password hashing, JWT sign/verify
│   │   └── logging.py               # Structured logging
│   ├── db/
│   │   ├── base.py                  # SQLAlchemy engine + session factory
│   │   └── models.py                # User, Thread, UserProfile, Document ORM models
│   ├── memory/
│   │   ├── checkpointer.py          # STM checkpointer config
│   │   └── ltm_store.py             # LTM CRUD operations (repository layer)
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── store.py                 # Vector store singleton — ChromaDB/Pinecone switching
│   │   └── ingestor.py              # File validation, text extraction, chunking, embedding
│   ├── schemas/
│   │   ├── auth.py                  # RegisterRequest, LoginRequest, TokenResponse, UserRead
│   │   ├── chat.py
│   │   ├── thread.py
│   │   ├── memory.py
│   │   └── document.py              # DocumentRead, DocumentUploadResponse
│   ├── services/
│   │   ├── auth_service.py          # Register, login — bcrypt + JWT
│   │   ├── chat_service.py          # Chat business logic — streaming, SSE, LangGraph orchestration
│   │   ├── thread_service.py        # Thread CRUD service layer
│   │   └── document_service.py      # Document ingest, list, delete service layer
│   └── main.py                      # App factory + lifespan
├── alembic/                         # Schema migration files
│   ├── env.py
│   └── versions/
│       └── 0001_initial_auth.py     # Initial schema — users, threads, documents, user_profile
├── data/                            # SQLite + ChromaDB files (local dev, gitignored)
├── alembic.ini
├── .env                             # Local secrets (gitignored)
├── .env.example                     # Environment variable reference
└── requirements.txt
```

---

## Memory Architecture

### Short-Term Memory (STM)

Implemented via LangGraph's checkpointing system. Each conversation thread maintains its own checkpoint — the full agent state (messages, tool calls, reasoning) is persisted per turn and restored on subsequent requests within the same thread.

- **Local dev:** `AsyncSqliteSaver` → `data/checkpoints.db`
- **Production:** `AsyncPostgresSaver` → Supabase Postgres

### Long-Term Memory (LTM)

Implemented as a key-value profile store backed by SQLAlchemy. The agent extracts persistent user facts — name, location, profession, preferences, interests, and any other personal detail shared in conversation — and writes them via a `memory_writer` node that runs post-graph with a fresh database session. On each new request, the stored profile is injected into the system prompt so the agent retains context across sessions and threads.

- **Local dev:** SQLite → `data/neurograph.db`
- **Production:** Supabase Postgres

The `memory_writer` node returns a list of keys saved on each turn. The chat service captures this and emits a `memory_update` SSE event to the frontend, which displays a passive `🧠 Memory updated` notification.

The current implementation injects the full profile on every request. In production systems with large profiles, semantic retrieval — embedding the user query and retrieving only the top-k relevant profile entries — is the recommended approach to avoid unnecessary context window usage.

---

## Dynamic Agentic RAG

Users upload PDF or TXT documents at runtime. The backend ingests them on the fly — extracts text, chunks, embeds, and stores in a vector database. The agent then has a `document_search` tool in its existing ReAct loop and decides when to use it based on the user's question. This is not a separate mode or pipeline — retrieval is a decision made by the agent, not a forced step on every request.

### Why Agentic, Not Pipeline

Pipeline RAG retrieves on every message regardless of relevance — injecting document context even when the user asks a general knowledge question. Agentic RAG treats retrieval as one tool among many. The agent calls `document_search` only when it determines the user's question relates to uploaded document content. General knowledge questions are answered directly without touching the vector store.

### Document Grounding

At every request, `chat_service.py` queries the `documents` table and injects the current upload state into the system prompt as `doc_context`:
```
# When documents exist:
[System: User has 2 document(s) uploaded: report.pdf, contract.txt. Only call document_search when the user is asking about content from these documents.]

# When no documents exist:
[System: User has no documents uploaded. Do not call document_search.]
```
---

### Ingest Pipeline
```
Upload → Validate (size, type) → SHA256 dedup check
→ Extract text (PyMuPDF for PDF, decode for TXT)
→ Recursive character split → Validate chunk count
→ Batch embed (Gemini gemini-embedding-001)
→ Write to ChromaDB / Pinecone
→ Persist metadata to documents table
```
**Deduplication:** SHA256 hash of file content. Uploading the same file twice — even with a different filename — skips re-embedding entirely and returns `already indexed — ready to query`.

**Chunking:** via LangChain's RecursiveCharacterTextSplitter.


**Embedding:** Gemini `gemini-embedding-001` with `output_dimensionality=768`. Batch embedding — all chunks in a single API call. Separate task types: `RETRIEVAL_DOCUMENT` at ingest, `RETRIEVAL_QUERY` at search time.

**Retrieval:** Top-k=3 cosine similarity search. Chunks below a similarity threshold of 0.5 are discarded — prevents irrelevant content from reaching the agent when no relevant document exists for the query.

### Vector Store — Env-Based Switching

Same pattern as SQLite/Postgres switching for the main database:

| Environment | Store | Config |
|---|---|---|
| Local (default) | ChromaDB | `PINECONE_API_KEY` absent |
| Production | Pinecone | `PINECONE_API_KEY` set |

The `init_store()` function runs once at startup in the FastAPI lifespan. Both backends implement the same interface (`add`, `query`, `delete_by_sha256`, `has_sha256`) — the rest of the codebase never knows which is active.

### Current Constraints

| Constraint | Value | Reason |
|---|---|---|
| Supported formats | PDF, TXT only | PyMuPDF + plain decode |
| Max file size | 10MB | Validated before processing |
| Max PDF pages | 50 | Controls text extraction scope |
| Max chunks per document | 50 | Controls embedding API calls — applies to both PDF and TXT |
| PDF type | Text-based only | PyMuPDF extracts digital text layer — scanned/image PDFs rejected |
| Similarity threshold | 0.5 cosine similarity | Chunks below threshold discarded at retrieval |
| User isolation | Per-user — chunks namespaced by `user_id` in metadata, all queries and deletes filtered at vector store level | Auth + per-user scoping implemented |

---

## Agent Graph

The ReAct graph is built manually using LangGraph's `StateGraph` — not the prebuilt `create_react_agent`. This allows custom node definitions for tool execution and memory writing.

```
START
│
▼
reasoner          ← Gemini 3.1 Flash Lite, decides next action
│
├── tool call? ──► tool_executor ──► reasoner (loop)
│
└── done? ──► END
               │
               └── memory_writer runs post-graph
                   (fresh DB session, outside graph)
```

**Why manual graph construction:** The prebuilt `create_react_agent` does not support custom post-graph hooks like the LTM memory writer, which requires a database session injected at request time rather than graph compile time.

**Recursion limit:** Configured with `recursion_limit=10` — maximum 5 tool call cycles per response. Prevents runaway ReAct loops (agent calling tools indefinitely without reaching a final answer) and unexpected API cost spikes.

---

## Tools

| Tool | Type | Description |
|---|---|---|
| `calculator` | Custom | Safe math expression evaluation via `simpleeval` |
| `tavily_search` | Built-in | Web search via Tavily API — returns sources with title + URL |
| `weather` | Custom | Current weather for any city via wttr.in (async) |
| `finance` | Custom | Stock price and company info via yFinance |
| `get_datetime` | Custom | Current UTC date and time |
| `document_search` | Custom | Semantic search across user-uploaded documents (RAG) |

All tools follow the same error contract — exceptions are caught internally and returned as error strings to the LLM. Tool failures never crash the agent.

Tool execution uses `tool.ainvoke()` throughout. For async tools (`weather`), this runs the coroutine directly. For sync tools, LangChain dispatches to a thread pool executor via `run_in_executor`, keeping the async event loop non-blocking.

---

## Exception Handling

A typed exception hierarchy ensures every error surfaces with the correct HTTP status code and a meaningful message — nothing leaks raw stack traces to the client.
NeuroGraphException (base)
├── AgentException                → 500 — graph not initialized
├── ThreadNotFoundException       → 404 — thread lookup failed
├── ThreadServiceException        → 500 — unexpected thread DB error
├── ProfileEntryNotFoundException → 404 — LTM key not found
├── LTMException                  → 500 — unexpected LTM DB error
├── RAGException                  → 500 / 422 — ingest validation or unexpected RAG error
├── DocumentNotFoundException     → 404 — document sha256 not found
├── UnauthorizedException         → 401 — missing or invalid JWT
├── ForbiddenException            → 403 — authenticated but not authorized (wrong owner)
└── UserAlreadyExistsException    → 409 — email already registered
**Route layer** raises specific 404-type exceptions for expected business logic failures.
**Service layer** wraps unexpected errors in typed 500-type exceptions.
**Global handler** catches all `NeuroGraphException` subclasses — logs warnings for 4xx, errors with stack traces for 5xx.
**Fallback handler** catches anything else as a generic 500 — nothing internal exposed to the client.

---

## Service Layer

Routes are kept thin — request validation, existence checks, and response serialization only. All business logic lives in the service layer.

| Service | Location | Responsibility |
|---|---|---|
| Chat service | `services/chat_service.py` | SSE streaming, LangGraph orchestration, memory writing, doc context injection, title generation |
| Thread service | `services/thread_service.py` | Thread CRUD operations |
| Document service | `services/document_service.py` | Document ingest pipeline, list, delete |
| LTM repository | `memory/ltm_store.py` | UserProfile DB operations — shared across chat and memory routes |
| Auth service | `services/auth_service.py` | User registration, login — bcrypt hashing, JWT issuance |
---

## API Reference

### Chat

| Method | Endpoint | Description |
|---|---|---|
| POST | `/chat/stream` | Send a message, receive SSE stream |
| GET | `/chat/history/{thread_id}` | Full message history for a thread |

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

| Method | Endpoint | Description |
|---|---|---|
| POST | `/threads` | Create a new thread |
| GET | `/threads` | List all threads (ordered by recent activity) |
| GET | `/threads/{id}` | Get a single thread |
| PATCH | `/threads/{id}` | Rename a thread |
| DELETE | `/threads/{id}` | Delete a thread |

### Memory (LTM)

| Method | Endpoint | Description |
|---|---|---|
| GET | `/memory/profile` | Read all stored profile facts |
| PUT | `/memory/profile` | Upsert a profile entry |
| PATCH | `/memory/profile/{key}` | Update a single entry by key |
| DELETE | `/memory/profile/{key}` | Delete a single entry |
| DELETE | `/memory/profile` | Clear entire profile |

### Documents

| Method | Endpoint | Description |
|---|---|---|
| POST | `/documents/upload` | Upload one or more PDF/TXT files — ingests, embeds, stores |
| GET | `/documents/` | List all uploaded documents with metadata |
| DELETE | `/documents/{sha256}` | Hard delete — removes from vector store and documents table |


### Health

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Liveness check — returns 200 with DB status when healthy, 503 when DB is unreachable |

### Auth

| Method | Endpoint | Description |
|---|---|---|
| POST | `/auth/register` | Register a new user — returns JWT on success, 409 if email already exists |
| POST | `/auth/login` | Authenticate an existing user — returns JWT on success, 401 on invalid credentials |
---
## Environment Variables

Copy `.env.example` to `.env` and fill in your values.

```env
# Gemini
GOOGLE_API_KEY=

# LangSmith
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_API_KEY=
LANGCHAIN_PROJECT=neurograph-ai

# Tavily
TAVILY_API_KEY=

# App
APP_ENV=development
FRONTEND_URL=http://localhost:5173

# Database
# Leave DATABASE_URL empty for SQLite (local dev)
# Set to Supabase Postgres connection string for production
DATABASE_URL=
SQLITE_DB_PATH=./data/neurograph.db
CHECKPOINT_DB_PATH=./data/checkpoints.db

# RAG — Vector Store
# Leave PINECONE_API_KEY empty for local (ChromaDB auto-used)
# Set on Render dashboard for production (Pinecone auto-used)
CHROMA_PATH=./data/chroma
PINECONE_API_KEY=
PINECONE_INDEX_NAME=neurograph-rag

# Auth
JWT_SECRET_KEY=        # generate with: openssl rand -hex 32
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=10080
```

---
## Local Development

**Prerequisites:** Python 3.11+, pip

```bash
# 1. Clone and navigate to backend
cd neurograph-ai/backend

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment
cp .env.example .env
# Fill in your API keys in .env

# 5. Run database migrations
alembic upgrade head

# 6. Run the server
uvicorn app.main:app --reload --port 8000
```

Swagger UI available at `http://localhost:8000/docs`
---
## Production Deployment (Render)

1. Create a new Web Service on Render, connect your GitHub repo
2. Set build command: `pip install -r requirements.txt`
3. Set start command: `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Add all environment variables from `.env.example` in the Render dashboard
5. Set `DATABASE_URL` to your Supabase Postgres connection string
6. Set `PINECONE_API_KEY` and `PINECONE_INDEX_NAME` for production RAG
7. Set `APP_ENV=production`
8. Set `FRONTEND_URL` to your Vercel deployment URL
9. Set `JWT_SECRET_KEY` — generate with `openssl rand -hex 32`

---

## Observability

All LLM calls, tool executions, and agent graph runs are traced automatically via LangSmith. Set `LANGCHAIN_API_KEY` and `LANGCHAIN_PROJECT` in your environment — no additional instrumentation required.

Traces are visible at `https://smith.langchain.com` under your configured project.

---
## Known Limitations and Planned Improvements

| Area | Current State | Planned Improvement |
|---|---|---|
| Tool history on reload | Tool badges visible during live streaming only — not reconstructed from checkpoints | Dedicated `chat_messages` table written at stream time |
| PDF support | Text-based PDFs only — scanned/image PDFs rejected | OCR via `pytesseract` or cloud Vision API |
| Chunking | Character-based recursive splitter (LangChain) | Semantic chunking or token-aware splitting |
| RAG retrieval | Top-k=3, no reranking | Cross-encoder reranker (e.g. Cohere Rerank) for precision |
| Similarity threshold | Fixed at 0.5 — not validated against real queries | Evaluate against a query set and tune, or make configurable via env var |
| LTM retrieval | Full profile injected on every request | Semantic retrieval — top-k relevant profile entries per query |
| LTM write mechanism | Regex-parsed from model output (`MEMORY_UPDATE: key=X value=Y`) — silent drop if Gemini reformats | Structured tool call or dedicated memory-write tool |
| Rate limiting | None | `slowapi` middleware or API gateway |
| Tests | None | `pytest` + `httpx.AsyncClient` |
| Thread deletion | Thread record deleted, checkpoint records remain in STM DB | Cascade delete STM checkpoint data on thread deletion |
| Context management | Full message history sent to LLM on every turn | Trimming or summarization for very long conversations |
| Password security | Minimum 8 characters only — no complexity requirement | Enforce uppercase, digit, special character rules |
| JWT storage | `localStorage` — XSS-vulnerable | `httpOnly` cookie with CSRF protection |