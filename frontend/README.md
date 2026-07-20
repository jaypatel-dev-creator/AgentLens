# NeuroGraph AI — Frontend

A React frontend for the NeuroGraph AI conversational agent. Built with Vite, Tailwind CSS v4, and a native `fetch`-based SSE client. All state is managed through React context — no Redux, no external state library.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | React 19 |
| Build Tool | Vite 8 |
| Styling | Tailwind CSS v4 (`@tailwindcss/vite` plugin) |
| Markdown Rendering | `react-markdown` + `@tailwindcss/typography` |
| HTTP Client | Axios (thread/memory/document API calls) + native `fetch` (SSE stream) |
| State Management | React Context + `useState` / `useCallback` / `useRef` |

---

## Project Structure

```
frontend/
├── public/
│   ├── favicon.svg
│   └── icons.svg
├── src/
│   ├── api/
│   │   └── client.js                # Axios instance — baseURL, Bearer token interceptor, 401 handler
│   ├── components/
│   │   ├── Chat/
│   │   │   ├── ChatWindow.jsx       # Message list, streaming, memory + upload status notifications
│   │   │   ├── MessageBubble.jsx    # Human + AI message rendering
│   │   │   ├── StreamingMessage.jsx # Live streaming render with tool badges
│   │   │   └── ChatInput.jsx        # Auto-resize textarea, paperclip upload, Enter to send
│   │   ├── Sidebar/
│   │   │   ├── Sidebar.jsx          # New chat, collapse toggle, documents panel, profile toggle, sign out
│   │   │   ├── ThreadList.jsx       # List of conversation threads
│   │   │   └── ThreadItem.jsx       # Thread row — click, rename, delete
│   │   ├── Documents/
│   │   │   └── DocumentList.jsx     # Uploaded documents list — filename, chunk count, delete
│   │   ├── Memory/
│   │   │   └── ProfileViewer.jsx    # LTM profile panel — view, delete entries
│   │   └── ToolCall/
│   │       └── ToolCallBadge.jsx    # Tool badge — running/done state, expandable output
│   ├── context/
│   │   ├── AuthContext.jsx          # Auth state — token, login, register, logout
│   │   └── ChatContext.jsx          # Global state + all API calls + SSE handler + document actions
│   ├── pages/
│   │   ├── AuthPage.jsx             # Login / register form — shown when unauthenticated
│   │   └── ChatPage.jsx             # Root layout — Sidebar + ChatWindow + ProfileViewer
│   ├── App.jsx                      # AuthProvider + ChatProvider wrapper, route guard
│   ├── main.jsx                     # React DOM entry point
│   └── index.css                    # Tailwind imports + global styles
├── index.html
├── vite.config.js
└── package.json
```

---

## Architecture

### Authentication

Auth state lives in `AuthContext`. `App.jsx` wraps the entire app in `AuthProvider` and conditionally renders `AuthPage` or `ChatPage` based on `isAuthenticated`. `ChatProvider` is keyed to the JWT token — it fully remounts on user change so no state leaks between accounts.

```
AuthContext
├── token                  — JWT from localStorage
├── isAuthenticated        — Boolean derived from token
├── login(email, password) — POST /auth/login → stores token
├── register(email, pass)  — POST /auth/register → stores token
└── logout()               — clears token, remounts ChatProvider
```

The Axios client (`client.js`) injects `Authorization: Bearer <token>` on every request via a request interceptor. On a 401 response, it fires an `auth:logout` custom event that `AuthContext` listens for — forcing logout without a circular import between the two modules.

The SSE stream (`/chat/stream`) uses native `fetch` which bypasses Axios — the token is injected manually from `localStorage` in `sendMessage`.

### State Management

All chat state lives in `ChatContext`. Components read from context via `useChat()` — no prop drilling anywhere.

```
ChatContext (single source of truth)
├── threads[]              — sidebar thread list
├── activeThreadId         — currently selected thread
├── messages[]             — committed message history
├── streamingMessage       — live in-progress AI response
├── isStreaming            — input disabled during stream
├── profile[]              — LTM profile entries
├── showProfile            — profile panel visibility
├── memoryNotification     — { keys[] } — auto-dismissed after 4s
├── documents[]            — uploaded document list from DB
├── showDocuments          — documents panel visibility in sidebar
└── uploadStatuses[]       — per-file upload feedback (uploading/success/duplicate/error)
```

### SSE Streaming

The backend streams responses as Server-Sent Events. The frontend reads the stream using the native `fetch` + `ReadableStream` API — not `EventSource` — because `EventSource` does not support `POST` requests.

```
fetch POST /chat/stream
→ ReadableStream reader
→ TextDecoder + line buffer
→ JSON.parse each "data: {...}" line
→ handleSSEEvent(event)
```

#### SSE Event Handling

| Event Type | Action |
|---|---|
| `text` | Appends to `streamingMessage.content`, strips `MEMORY_UPDATE:` lines live |
| `tool_start` | Sets `streamingMessage.currentTool` with `status: running` |
| `tool_end` | Moves tool to `streamingMessage.toolCalls[]` with `status: done` |
| `memory_update` | Shows `🧠 Memory updated` notification, auto-dismisses after 4s |
| `done` | Commits `streamingMessage` to `messages[]`, clears streaming state, refreshes thread title |
| `error` | Shows error message, clears streaming state |

### MEMORY_UPDATE Filtering

The agent appends `MEMORY_UPDATE: key=x value=y` sentinel lines to its responses for LTM persistence. These are never intended for display. The frontend strips them in two places:

- **During streaming** — `stripMemoryUpdates()` runs on each `text` chunk as it arrives
- **On `done`** — a final strip pass runs before committing to `messages[]`

This ensures sentinel lines never appear in the rendered chat, regardless of streaming timing.

---

## Components

### ChatWindow

Root chat component. Renders the committed message list, the live `StreamingMessage`, the `🧠 Memory updated` notification, and per-file upload status pills. Handles auto-scroll to the latest message on every update.

The memory notification renders as a small purple pill between the message list and the input bar — non-intrusive, passive, auto-dismisses after 4 seconds.

Upload status pills appear in the same area, one per file, color-coded by state:
- 🔵 Blue — uploading in progress
- ✅ Green — indexed successfully (shows chunk count)
- 📋 Yellow — already indexed (duplicate)
- ❌ Red — upload failed

Pills auto-dismiss after 5 seconds.

### MessageBubble

Renders a single committed message.

- **Human messages** — right-aligned gray bubble
- **AI messages** — left-aligned, markdown rendered via `react-markdown` with `@tailwindcss/typography` prose styles. Tool badges render above the response text, sources render below.

Tool badges and sources are visible during live streaming. On history reload, only the AI's final text response is shown — tool metadata is not persisted across page refresh. See [Known Limitations](#known-limitations-and-future-improvements).

### StreamingMessage

Renders the live in-progress AI response. Distinct from `MessageBubble` because streaming state has additional fields (`currentTool`, `toolCalls[]`, cursor blink) that committed messages do not.

States handled:
- **Thinking** — three bouncing dots while waiting for first content
- **Tool running** — `ToolCallBadge` with `Using Document Search...` + pulse indicator
- **Streaming text** — markdown rendered live with blinking cursor
- **Sources** — shown below text once streaming content exists

### ToolCallBadge

Pill badge showing tool execution status. Two visual states:

- `status: running` — blue tint, `Using {Tool}...` label, animated pulse dot
- `status: done` — gray tint, `Used {Tool}` label, expandable chevron

Click to expand and view the raw tool output (truncated to 200 characters). Each tool has a dedicated icon and label:

| Tool | Icon | Label |
|---|---|---|
| `calculator` | 🧮 | Calculator |
| `weather` | 🌤️ | Weather |
| `finance` | 📈 | Finance |
| `get_datetime` | 🕐 | Date & Time |
| `tavily_search` | 🔍 | Web Search |
| `document_search` | 📄 | Document Search |

### AuthPage

Login and registration form — shown when the user is unauthenticated. Minimal, Claude-like design matching the app aesthetic. Toggles between Sign in and Sign up mode. Submits to `POST /auth/login` or `POST /auth/register`, stores the returned JWT, and redirects to the chat UI automatically.

### Sidebar

Left panel containing the thread list and navigation controls.

- **Collapse toggle** — shrinks to icon-only mode (`w-14`) for more reading space
- **+ New Chat** — creates a thread via `POST /threads` and sets it active
- **Thread list** — sorted by most recent, click to load history
- **📎 Documents button** — toggles the `DocumentList` panel inline in the sidebar, loads document list on open
- **🧠 Memory Profile button** — toggles `ProfileViewer`, loads profile on open
- **Sign out button** — calls `logout()` from `AuthContext`, clears token, returns to `AuthPage`

### DocumentList

Inline panel in the sidebar showing all uploaded documents.

- Lists filename and chunk count per document
- Hover over any document to reveal the `✕` delete button
- Delete calls `DELETE /documents/{sha256}` — hard deletes from both vector store and DB
- Shows empty state with upload instructions when no documents exist

### ThreadItem

Individual thread row in the sidebar.

- **Single click** — selects thread, loads history via `GET /chat/history/{id}`
- **Double click** — activates inline rename input
- **Enter** — confirms rename via `PATCH /threads/{id}`
- **Escape** — cancels rename
- **Hover** — reveals delete button (`DELETE /threads/{id}`)

### ProfileViewer

Right panel showing the agent's long-term memory about the user. Opens as a third column alongside the chat window.

- Lists all profile entries (key formatted as Title Case, value as stored)
- `✕` button on each entry — deletes via `DELETE /memory/profile/{key}`
- `Clear all memory` button — clears via `DELETE /memory/profile`
- Auto-refreshes when a `memory_update` SSE event fires while the panel is open

### ChatInput

Auto-resizing textarea. Grows up to `128px` then scrolls. `Enter` sends, `Shift+Enter` inserts a newline. Disabled and dimmed while a response is streaming.

**Paperclip upload button** — sits left of the textarea. Opens a native file picker with `multiple` and `accept=".pdf,.txt"`. On file select, upload fires immediately — before sending any message. The user can upload documents, see the status pills, then ask questions about them.

File upload uses `multipart/form-data` via Axios with `Content-Type: undefined` to let Axios auto-set the correct boundary — bypassing the default `application/json` header set on the shared client instance.

---

## Document Upload Flow

```
User clicks paperclip → file picker opens (PDF/TXT, multi-select)
→ files selected → uploadDocuments() fires immediately
→ FormData built → POST /documents/upload
→ uploadStatuses[] set to "uploading" per file
→ response received → statuses updated per file
→ DocumentList refreshed → pills auto-clear after 5s
```

The agent searches across all uploaded documents simultaneously when `document_search` is called. The agent only calls `document_search` when the user explicitly asks about uploaded document content — not on every message.

---

## Local Development

**Prerequisites:** Node.js 18+

```bash
# 1. Navigate to frontend
cd neurograph-ai/frontend

# 2. Install dependencies
npm install

# 3. Start dev server
npm run dev
```

App runs at `http://localhost:5173`

The backend must be running at `http://localhost:8000` before using the app. Start the backend first — see `backend/README.md`.

---

## Production Deployment (Vercel)

1. Connect your GitHub repo to Vercel
2. Set framework preset to **Vite**
3. Set build command: `npm run build`
4. Set output directory: `dist`
5. Set `VITE_API_URL` environment variable in Vercel dashboard to your deployed backend URL

---

## Known Limitations and Future Improvements

| Area | Current | Future Improvement |
|---|---|---|
| Tool history on reload | Tool badges and sources visible during live streaming only — not shown on history reload | Requires a dedicated `chat_messages` table on the backend written at stream time |
| Backend URL | Hardcoded fallback to `localhost:8000` in `ChatContext.jsx` fetch call | Already uses `import.meta.env.VITE_API_URL` with fallback — set `VITE_API_URL` in Vercel dashboard for prod |
| Error handling | Stream errors show a generic message | Per-event error types with user-facing descriptions |
| Loading states | No skeleton loaders on history load or thread switch | Skeleton UI for message area during `selectThread` |
| Message timestamps | Not displayed | Show relative timestamps on hover |
| Empty state | Generic placeholder text | Suggested starter prompts |
| Document search hint | No UI guidance on how to trigger document search | Hint text near documents panel explaining to mention "my document" in the message |
| JWT storage | `localStorage` — XSS-vulnerable | `httpOnly` cookie with CSRF protection |