# NeuroGraph AI

![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.136+-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![LangChain](https://img.shields.io/badge/LangChain-1.x-1C3C3C?logo=langchain&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-1.x-1C3C3C?logo=langchain&logoColor=white)
![ChromaDB](https://img.shields.io/badge/ChromaDB-Local-E07B39?logoColor=white)
![Pinecone](https://img.shields.io/badge/Pinecone-Production-00B388?logoColor=white)
![Gemini](https://img.shields.io/badge/Gemini-3.1_Flash_Lite-4285F4?logo=google&logoColor=white)

A full-stack conversational AI agent with dual-layer memory and Dynamic Agentic RAG. Built on a manually constructed LangGraph ReAct graph — not a wrapper around prebuilt agent abstractions.

**Live demo:** [neuro-graph-ai.vercel.app](https://neuro-graph-ai.vercel.app)  
**Backend API:** [neurographai.onrender.com](https://neurographai.onrender.com)

> ⚠️ Hosted on Render free tier — first request may take 30–60 seconds to cold start.

---

## What This Is

Most AI chat demos call an LLM and return a response. NeuroGraph AI is an agent — it reasons, decides which tools to use, executes them, observes the results, and reasons again. Memory persists across turns (STM) and across sessions (LTM). Users can upload documents at runtime and the agent decides when to search them — retrieval is a decision, not a pipeline step.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    React Frontend                       │
│         SSE streaming · context state · no Redux        │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP + SSE
┌──────────────────────▼──────────────────────────────────┐
│                   FastAPI Backend                       │
│                                                         │
│  /auth  /chat/stream  /threads  /memory  /documents     │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │           LangGraph ReAct Agent                  │   │
│  │  Thought → Action → Observation → Thought → ...  │   │
│  │                                                  │   │
│  │  Tools: web search · weather · finance ·         │   │
│  │         calculator · datetime · document_search  │   │
│  └──────────────────────────────────────────────────┘   │
│                                                         │
│   Auth: JWT — bcrypt passwords, per-user data scoping   │
│   STM: LangGraph checkpointer (SQLite / Postgres)       │
│   LTM: user_profile table (SQLite / Postgres)           │
│   RAG: ChromaDB (local) / Pinecone (prod)               │
│   Migrations: Alembic                                   │
└─────────────────────────────────────────────────────────┘
```

---

## Key Features

**JWT Authentication + per-user isolation**  
Register/login with bcrypt-hashed passwords and stateless JWT tokens. Every thread, LTM profile entry, and uploaded document is scoped to the authenticated user — enforced at the service and vector store layer. Users cannot access each other's data.

**Agentic RAG — not pipeline RAG**  
Users upload PDF or TXT files at runtime. The agent calls `document_search` only when the user is asking about document content — not on every message. Retrieval is a tool call, not a forced injection.

**Dual-layer memory**  
Short-term memory (STM) via LangGraph checkpointing persists full conversation state per thread. Long-term memory (LTM) extracts and stores user facts across sessions — injected into the system prompt on every request.

**Manual ReAct graph**  
Built with LangGraph's `StateGraph` directly — not `create_react_agent`. Enables custom post-graph hooks for LTM writing with request-scoped DB sessions.

**Env-based store switching**  
ChromaDB locally, Pinecone in production. SQLite locally, Postgres (Supabase) in production. Switching is entirely config-driven — no code changes between environments.

**Alembic migrations**  
Schema changes are versioned and reproducible across environments. The start command runs `alembic upgrade head` automatically on every deploy.

**SSE streaming**  
Responses stream token-by-token. Tool execution, memory updates, and errors are distinct SSE event types — the frontend renders each differently in real time.

---

## Tech Stack

| Layer | Local | Production |
|---|---|---|
| LLM + Embeddings | Gemini 3.1 Flash Lite + gemini-embedding-001 | same |
| Backend | FastAPI + LangGraph | Render |
| Frontend | React + Vite | Vercel |
| Database | SQLite + aiosqlite | Supabase Postgres |
| Vector Store | ChromaDB | Pinecone |
| Checkpointer | SQLite | Postgres (LangGraph) |
| Auth | JWT + bcrypt | same |
| Migrations | Alembic | same |

---

## Repository Structure

```
neurograph-ai/
├── backend/          # FastAPI + LangGraph agent
│   └── README.md     # Full backend documentation
├── frontend/         # React + Vite
│   └── README.md     # Full frontend documentation
└── README.md         # This file
```

Backend and frontend each have their own README covering architecture, API reference, project structure, environment variables, and deployment.

---

## Quick Start

**Prerequisites:** Python 3.12+, Node.js 18+

```bash
# Clone
git clone https://github.com/jaypatel-dev-creator/NeuroGraphAI.git
cd NeuroGraphAI

# Backend
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # fill in API keys
alembic upgrade head            # run database migrations
uvicorn app.main:app --reload --port 8000

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

Backend: `http://localhost:8000` · Swagger: `http://localhost:8000/docs`  
Frontend: `http://localhost:5173`

---

## Required API Keys

| Key | Purpose | Free Tier |
|---|---|---|
| `GOOGLE_API_KEY` | Gemini LLM + embeddings | Yes |
| `TAVILY_API_KEY` | Web search tool | Yes |
| `LANGCHAIN_API_KEY` | LangSmith tracing | Yes |
| `PINECONE_API_KEY` | Vector store (prod only) | Yes |

Leave `PINECONE_API_KEY` empty locally — ChromaDB is used automatically.  
Generate `JWT_SECRET_KEY` with: `python -c "import secrets; print(secrets.token_hex(32))"`
