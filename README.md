# AgentLens 🔍

> See inside your AI agent. Every decision. Every token. Every trace.

![FastAPI](https://img.shields.io/badge/FastAPI-0.136-009688?style=flat&logo=fastapi&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-1.2-1C3C3C?style=flat&logo=langchain&logoColor=white)
![Gemini](https://img.shields.io/badge/Gemini-Flash-4285F4?style=flat&logo=google&logoColor=white)
![Pinecone](https://img.shields.io/badge/Pinecone-Vector_Store-000000?style=flat&logo=pinecone&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?style=flat&logo=react&logoColor=black)
![OpenTelemetry](https://img.shields.io/badge/OpenTelemetry-1.44-425CC7?style=flat&logo=opentelemetry&logoColor=white)
![SigNoz](https://img.shields.io/badge/SigNoz-Cloud_us2-F46800?style=flat)
![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat&logo=python&logoColor=white)
![Render](https://img.shields.io/badge/Render-Deployed-46E3B7?style=flat&logo=render&logoColor=black)
![Vercel](https://img.shields.io/badge/Vercel-Deployed-000000?style=flat&logo=vercel&logoColor=white)

**Live Demo:** [agent-lens-rosy.vercel.app](https://agent-lens-rosy.vercel.app) · **Backend:** [agentlens-9ari.onrender.com](https://agentlens-9ari.onrender.com) · **Track:** AI & Agent Observability


---

Built for the [Agents of SigNoz Hackathon](https://wemakedevs.org/hackathons/signoz) — WeMakeDevs × SigNoz, July 20–26, 2026.

---

## The Problem

AI agents are notoriously hard to debug. You send a message, something happens inside a LangGraph state machine, and you get a response — but everything in between is a black box. How many tokens did that cost? Which tool fired? Did it hit the vector store? Was the LLM slow or was it the retrieval?

Most teams bolt on logging after the fact. I wanted to instrument the agent *from the inside* — every reasoning step, every tool invocation, every memory read, every vector query — and surface that data both in SigNoz and directly in the chat UI in real time.

That's AgentLens.

---

## What It Does

AgentLens is a full agentic RAG system with deep OpenTelemetry instrumentation built in from day one. It's not a demo app with traces added at the end — observability is part of the architecture.

The agent can:
- Answer questions using its own knowledge or live tools (web search, weather, finance, datetime, calculator)
- Upload and query your documents via RAG (Pinecone vector store)
- Remember things about you across sessions via long-term memory (LTM)
- Maintain conversation history across messages via short-term memory (LangGraph checkpointing — SQLite locally, Postgres on prod)
- Tell you exactly what it did and how long it took — live, in the sidebar, while it's still responding

While you chat, the right sidebar shows you token consumption, LLM latency, tool calls with individual timings, RAG retrieval results, and LTM read/write counts — all pulled from a live `/metrics/session` endpoint that aggregates from the same OTel instrumentation flowing to SigNoz.

### Agentic Document Context Injection

Before each request, `build_doc_context()` in `chat_service.py` queries the database for the user's uploaded documents and injects the result directly into the system prompt as `doc_context`.

- **No documents uploaded** → agent receives `[System: User has no documents uploaded. Do not call document_search.]` — the tool call is eliminated before reasoning begins
- **Documents exist** → agent receives filenames and an instruction to only call `document_search` when the query is document-relevant

This means the agent's decision to query the vector store is grounded in live database state, not prompt guessing. It eliminates unnecessary Pinecone round trips and prevents the agent from hallucinating document content when none exists.



---

## Architecture

```
User → React (Vercel)
         ↓ SSE stream
      FastAPI (Render)
         ↓
      LangGraph Agent
      ├── Reasoner Node      → Gemini LLM
      ├── Tool Executor      → 6 tools (search, weather, finance, datetime, calculator, document_search)
      ├── LTM Store          → Supabase Postgres (persistent memory across sessions)
      └── RAG Store          → Pinecone (document embeddings, cosine similarity)
         ↓
      OpenTelemetry SDK
         ↓
      SigNoz Cloud (us2)
      ├── Traces             → full agent waterfall per request
      ├── Metrics            → 6 custom counters + histograms
      ├── Logs               → structured logs correlated with traces
      ├── Dashboard          → 4-panel "AgentLens Observability" view
      └── Alerts             → 2 configured, both confirmed firing
```

**Stack:** FastAPI · LangGraph · Gemini · Pinecone · Supabase Postgres · React/Vite · OpenTelemetry 1.44.0 · SigNoz Cloud

---

## SigNoz Integration

This is where I went deep.

### Instrumentation Strategy

I ran into a real constraint early: `openinference-instrumentation-langchain` — the standard auto-instrumentation library for LangChain/LangGraph — is incompatible with Python 3.14, which is what Render uses. Rather than downgrade Python or fight the dependency, I removed it entirely and wrote manual spans for every node in the agent graph.

This turned out to be a better decision. Auto-instrumentation gives you generic spans. Manual spans give you exactly the attributes you care about.

**Auto-instrumented (via `opentelemetry-instrument` CLI):**
- FastAPI routes — HTTP spans, status codes, route templates
- Python logging — all `logger.*` calls correlated with active trace context

**Manually instrumented:**

`agentlens.reasoner` — fires on every LLM call inside the reasoning node. Captures `llm.input_tokens`, `llm.output_tokens`, `llm.total_tokens`, `llm.latency_ms`, `llm.tool_calls_requested`. Also increments the token counter and records to the latency histogram.

`agentlens.tool.<name>` — one child span per tool invocation. Captures `tool.name`, `tool.input`, `tool.output_preview`, `tool.latency_ms`, `tool.success`. Lets you see exactly which tool fired, what it was given, and whether it succeeded.

`agentlens.ltm.read` / `agentlens.ltm.write` — wraps every long-term memory operation. Captures `ltm.operation`, `ltm.key`, `ltm.record_count`. Lets you see when the agent reads your profile and when it decides to save something new.

`agentlens.rag.query` — wraps every vector store query for both Chroma (local) and Pinecone (prod). Captures `rag.backend`, `rag.results_returned`, `rag.latency_ms`, `rag.threshold`. Records to the retrieval latency histogram.

`agentlens.chat.stream` — root span for the entire SSE stream turn. Carries `session.id` and `user.id` as attributes, making every trace in SigNoz searchable by session. This span is deliberately opened in the wrapper function (not the async generator) to ensure reliable export before streaming begins.

### Custom Metrics (6 total)

| Metric | Type | What it tracks |
|--------|------|----------------|
| `agentlens.tokens.total` | Counter | Total tokens consumed, labelled by model and token type |
| `agentlens.tool.calls.total` | Counter | Tool invocations, labelled by tool name and success/failure |
| `agentlens.ltm.operations.total` | Counter | LTM read/write operations |
| `agentlens.retrieval.latency` | Histogram | Vector store query latency in ms, labelled by backend |
| `agentlens.llm.latency` | Histogram | LLM response latency in ms |
| `agentlens.sessions.active` | UpDownCounter | Currently active chat sessions |

All 6 metrics are confirmed flowing to SigNoz Cloud from production.

### Alerts

Two alerts configured and confirmed firing:

- **High RAG Retrieval Latency** — fires when `agentlens.retrieval.latency` p99 exceeds 2000ms over a 5-minute window
- **Token Cost Spike** — fires when `agentlens.tokens.total` sum exceeds 500 tokens in a 5-minute window

Both received email notifications during development.

### Dashboard

Custom "AgentLens Observability" dashboard in SigNoz with 4 panels:
- Token Usage Over Time
- LLM Response Latency P99
- Tool Invocations
- Memory Operations (LTM)

### The Self-Awareness Feature

One thing I built that goes beyond standard observability: the agent's own metrics are accessible at `/metrics/session/{session_id}` — an auth-protected endpoint that aggregates everything from the OTel instrumentation in real time. The React frontend polls this every 2 seconds during a stream and renders it in the Observability sidebar.

The thread ID the frontend holds when it opens a chat stream is the same `session.id` attribute on the root span in SigNoz. So you can take the session ID visible in the sidebar, paste it into SigNoz's trace search, and find the exact trace for that conversation. The agent is observable from both sides — the user-facing UI and the SigNoz backend — using the same identifier.

---

## On SigNoz Cloud vs Self-Hosted

I deployed to SigNoz Cloud (us2 region) rather than running self-hosted Foundry. The reason is straightforward: the agent itself runs on Render's free tier with a cloud Postgres and Pinecone backend. Running a self-hosted SigNoz instance alongside it would have required additional infrastructure that doesn't reflect how this would actually be deployed in production.

SigNoz Cloud is SigNoz's own managed product — the same ingestion pipeline, the same query engine, the same dashboards. The observability setup is identical.

**Migrating to self-hosted Foundry takes one change:**

```bash
# In your .env or Render environment
OTLP_ENDPOINT=http://your-signoz-host:4317   # was: https://ingest.us2.signoz.cloud:443
# Remove SIGNOZ_INGESTION_KEY — not needed for self-hosted
```

The `casting.yaml` and `casting.yaml.lock` document the full deployment configuration for reproducibility.

---

## Running Locally

See [`backend/README.md`](./backend/README.md) for backend setup and OTel instrumentation instructions.
See [`frontend/README.md`](./frontend/README.md) for frontend setup.

---

## Known Limitations

- Observability sidebar session metrics are in-memory with a 1-hour TTL — won't persist across backend restarts
- Render free tier cold-starts after 15 minutes of inactivity — first request may take 30–50 seconds to respond

---


## Health Check

```bash
curl https://agentlens-9ari.onrender.com/health
```

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

## What Was Built for This Hackathon

The underlying agent infrastructure — LangGraph ReAct graph, dual-layer memory (STM + LTM), RAG pipeline, and tool integrations — was built prior to the hackathon as a personal project (NeuroGraphAI).

Everything below was designed and built during the hackathon week (July 20–25, 2026):

**Observability layer (net new):**
- `telemetry.py` — OTel bootstrap, 6 custom metric instruments, thread-safe in-memory session store with 1-hour TTL
- Manual spans on all 4 agent nodes — reasoner, tool_executor, ltm_store, rag/store
- `agentlens.chat.stream` root span with session.id propagation
- ContextVar-based session ID threading across the entire call stack
- LoggingInstrumentor integration — all logs correlated with active trace context

**Self-awareness API (net new):**
- `metrics_service.py` — session metrics aggregation layer
- `GET /metrics/session/{session_id}` — auth-protected live metrics endpoint
- 204 vs 404 semantics for pre-stream polling

**Frontend observability (net new):**
- `ObservabilityPanel.jsx` — live metrics sidebar polling every 2s during stream
- Metrics polling lifecycle in `ChatContext` — start on stream open, stop on done

**SigNoz integration (net new):**
- 2 alerts — High RAG Retrieval Latency + Token Cost Spike (both confirmed firing)
- Custom 4-panel "AgentLens Observability" dashboard
- `casting.yaml` + `casting.yaml.lock` — deployment spec and lock file

**Infrastructure changes:**
- LangSmith removed entirely, replaced with SigNoz
- `openinference-instrumentation-langchain` removed — Python 3.14 incompatibility on Render, all LangGraph spans rewritten as manual instrumentation
- SSE parent span refactored from async generator to wrapper function for reliable OTLP export
- `/health` endpoint extended with OTel status check
- Supabase Postgres + Pinecone wired for prod persistence

---

## AI Tool Usage Disclosure

This project was built with assistance from Claude (Anthropic) for architectural decisions, debugging, and code review. All instrumentation design, implementation, and deployment were done by me. 

---

*Built solo for the Agents of SigNoz Hackathon. July 20–26, 2026.*
