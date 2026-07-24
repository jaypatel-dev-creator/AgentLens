# AgentLens — Frontend

React frontend for AgentLens. Handles SSE streaming, real-time observability metrics, document uploads, long-term memory display, and thread management. No Redux — all state lives in React context.

**Framework:** React 19 · **Build:** Vite 8 · **Styling:** Tailwind CSS v4

---

## Project Structure

```
frontend/
├── public/
│   ├── favicon.svg
│   └── icons.svg
├── src/
│   ├── api/
│   │   └── client.js                   # Axios instance — baseURL, Bearer token interceptor, 401 handler
│   ├── components/
│   │   ├── Chat/
│   │   │   ├── ChatWindow.jsx          # Message list, streaming, memory + upload status notifications
│   │   │   ├── MessageBubble.jsx       # Human + AI message rendering with markdown
│   │   │   ├── StreamingMessage.jsx    # Live streaming render with tool badges + thinking state
│   │   │   └── ChatInput.jsx           # Auto-resize textarea, paperclip upload, Enter to send
│   │   ├── Observability/
│   │   │   └── ObservabilityPanel.jsx  # Live metrics sidebar — tokens, LLM, tools, RAG, LTM, session
│   │   ├── Sidebar/
│   │   │   ├── Sidebar.jsx             # New chat, collapse toggle, documents panel, profile, sign out
│   │   │   ├── ThreadList.jsx          # Conversation thread list
│   │   │   └── ThreadItem.jsx          # Thread row — click, rename (double-click), delete
│   │   ├── Documents/
│   │   │   └── DocumentList.jsx        # Uploaded documents — filename, chunk count, delete
│   │   ├── Memory/
│   │   │   └── ProfileViewer.jsx       # LTM profile panel — view, delete entries, clear all
│   │   └── ToolCall/
│   │       └── ToolCallBadge.jsx       # Tool badge — running/done state, expandable output
│   ├── context/
│   │   ├── AuthContext.jsx             # Auth state — token, login, register, logout
│   │   └── ChatContext.jsx             # Global state + all API calls + SSE handler + metrics polling
│   ├── pages/
│   │   ├── AuthPage.jsx                # Login / register form
│   │   └── ChatPage.jsx                # Root layout — Sidebar + ChatWindow + ObservabilityPanel
│   ├── App.jsx                         # AuthProvider + ChatProvider wrapper, route guard
│   ├── main.jsx                        # React DOM entry point
│   └── index.css                       # Tailwind imports + global styles
├── index.html
├── vite.config.js
└── package.json
```

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Framework | React 19 |
| Build Tool | Vite 8 |
| Styling | Tailwind CSS v4 (`@tailwindcss/vite` plugin) |
| Markdown Rendering | `react-markdown` + `@tailwindcss/typography` |
| HTTP Client | Axios (REST API calls) + native `fetch` (SSE stream) |
| State Management | React Context + `useState` / `useCallback` / `useRef` |

---

## Architecture

### Authentication

Auth state lives in `AuthContext`. `App.jsx` wraps the entire app in `AuthProvider` and conditionally renders `AuthPage` or `ChatPage` based on `isAuthenticated`. `ChatProvider` is keyed to the JWT token — it fully remounts on user change so no state leaks between accounts.

The Axios client injects `Authorization: Bearer <token>` on every request via a request interceptor. On a 401 response, it fires an `auth:logout` custom event that `AuthContext` listens for — forcing logout without a circular import between the two modules.

The SSE stream uses native `fetch` — not Axios — because `EventSource` doesn't support `POST` requests. The token is injected manually from `localStorage`.

### State (ChatContext)

All chat state in one place. Components read from context via `useChat()` — no prop drilling.

```
ChatContext
├── threads[]              — sidebar thread list
├── activeThreadId         — currently selected thread
├── messages[]             — committed message history
├── streamingMessage       — live in-progress AI response
├── isStreaming            — input disabled during stream
├── sessionMetrics         — live OTel metrics from /metrics/session
├── showObservability      — observability panel visibility toggle
├── profile[]              — LTM profile entries
├── showProfile            — profile panel visibility
├── memoryNotification     — { keys[] } — auto-dismissed after 4s
├── documents[]            — uploaded document list
├── showDocuments          — documents panel visibility
└── uploadStatuses[]       — per-file upload feedback
```

### SSE Streaming

```
fetch POST /chat/stream
→ ReadableStream reader
→ TextDecoder + line buffer
→ JSON.parse each "data: {...}" line
→ handleSSEEvent(event)
```

| Event Type | Action |
|------------|--------|
| `text` | Appends to `streamingMessage.content`, strips `MEMORY_UPDATE:` lines live |
| `tool_start` | Sets `streamingMessage.currentTool` with `status: running` |
| `tool_end` | Moves tool to `streamingMessage.toolCalls[]` with `status: done` |
| `memory_update` | Shows 🧠 notification, auto-dismisses after 4s |
| `done` | Commits `streamingMessage` to `messages[]`, stops metrics polling, final metrics fetch |
| `error` | Shows error message, clears streaming state |

### Observability Metrics Polling

When a stream starts, `ChatContext` begins polling `GET /metrics/session/{thread_id}` every 2 seconds. The response feeds `sessionMetrics` state, which `ObservabilityPanel` renders live. When the stream ends (`done` event), polling stops and one final fetch captures the complete session metrics.

204 responses (no metrics yet) are handled silently — polling continues without error.

---

## Components

### ObservabilityPanel

The key component added for the hackathon. A right sidebar that shows live OTel metrics during and after a chat stream. Rendered conditionally via the "Show Observability" toggle in the chat header.

Sections:
- **LLM** — tokens in, tokens out, total tokens, LLM calls, last latency
- **Tools** — total calls, success/failure counts, per-tool rows with name + latency + status dot
- **RAG Retrieval** — total queries, avg latency, max latency
- **Memory (LTM)** — reads, writes, total operations
- **Session** — duration, session ID (with "matches SigNoz trace" label)
- **Footer** — "View full traces in SigNoz" link

Shows a `📡 Send a message to start collecting metrics` empty state before the first message. Shows a `● Live` green pulse indicator while streaming is active.

The session ID shown matches the `session.id` span attribute on the root `agentlens.chat.stream` span in SigNoz — you can copy it and search in SigNoz Traces to find the exact trace for that conversation.

### ChatWindow

Root chat component. Renders committed messages, the live `StreamingMessage`, memory notifications, and upload status pills. Auto-scrolls to the latest message on every update.

Memory notification — small purple pill, auto-dismisses after 4 seconds.

Upload status pills — color-coded by state, auto-clear after 5 seconds:
- 🔵 Blue — uploading
- ✅ Green — indexed (shows chunk count)
- 📋 Yellow — duplicate (already indexed)
- ❌ Red — failed

### MessageBubble

- Human messages — right-aligned gray bubble
- AI messages — left-aligned, markdown rendered via `react-markdown` with prose styles. Tool badges above, sources below.

Tool badges and sources are visible during live streaming. Not reconstructed on history reload — see Known Limitations.

### StreamingMessage

Renders the live in-progress response. Distinct from `MessageBubble` because it has additional streaming-only state (`currentTool`, thinking dots, cursor blink).

States:
- **Thinking** — three bouncing dots while waiting for first content
- **Tool running** — `ToolCallBadge` with pulse indicator
- **Streaming text** — markdown rendered live with blinking cursor

### ToolCallBadge

Pill badge with two states:

- `running` — blue tint, `Using {Tool}...`, animated pulse dot
- `done` — gray tint, `Used {Tool}`, expandable chevron showing raw output (truncated to 200 chars)

| Tool | Icon | Label |
|------|------|-------|
| `calculator` | 🧮 | Calculator |
| `weather` | 🌤️ | Weather |
| `finance` | 📈 | Finance |
| `get_datetime` | 🕐 | Date & Time |
| `tavily_search` | 🔍 | Web Search |
| `document_search` | 📄 | Document Search |

### Sidebar

- Collapse toggle — shrinks to icon-only (`w-14`)
- **+ New Chat** — creates thread via `POST /threads`, sets active
- Thread list — sorted by most recent, click to load history
- **📎 Documents** — toggles `DocumentList` inline in sidebar
- **🧠 Memory Profile** — toggles `ProfileViewer`
- Sign out — clears token, returns to `AuthPage`

### ThreadItem

- Single click — selects thread, loads history
- Double click — inline rename input
- Enter — confirms rename via `PATCH /threads/{id}`
- Escape — cancels rename
- Hover — reveals delete button

### ChatInput

Auto-resizing textarea (grows to 128px then scrolls). Enter sends, Shift+Enter inserts newline. Disabled during streaming.

Paperclip button opens native file picker (`multiple`, `.pdf,.txt`). Upload fires immediately on file select — before any message is sent.

---

## Local Development

```bash
cd frontend
npm install
echo "VITE_API_URL=http://localhost:8000" > .env
npm run dev
```

App runs at `http://localhost:5173`. Start the backend first — see `backend/README.md`.

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `VITE_API_URL` | Backend URL. `http://localhost:8000` locally, Render URL in prod |

---

## Production (Vercel)

1. Connect GitHub repo to Vercel
2. Framework preset: **Vite**
3. Build command: `npm run build`
4. Output directory: `dist`
5. Root directory: `frontend`
6. Set `VITE_API_URL` to your Render backend URL in Vercel environment variables

---

## Known Limitations

| Area | Current | Improvement |
|------|---------|-------------|
| Tool history on reload | Tool badges visible during streaming only — not reconstructed on history load | Requires a `chat_messages` table on the backend written at stream time |
| Session metrics TTL | Metrics unavailable after backend restart or 1-hour TTL expiry | Persist session metrics to DB |
| JWT storage | `localStorage` — XSS-vulnerable | `httpOnly` cookie with CSRF protection |
| Empty state | Generic placeholder | Suggested starter prompts |
| Message timestamps | Not displayed | Relative timestamps on hover |