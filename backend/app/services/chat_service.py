import json
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from opentelemetry import trace

from app.db.base import AsyncSessionLocal
from app.db.models import Document
from app.memory.ltm_store import get_profile
from app.agent.nodes.memory_writer import memory_writer_node
from app.agent.graph import get_graph_with_checkpointer
from app.memory.checkpointer import get_db_path, use_postgres_checkpointer
from app.schemas.chat import ChatMessage
from app.core.config import get_settings
from app.core.logging import get_logger
import app.telemetry as tel

logger = get_logger(__name__)
_tracer = trace.get_tracer("agentlens.chat")

# Lazily initialized on first generate_title() call — not at import time.
# Module-level init runs before lifespan setup and before .env is validated,
# which causes opaque crashes if google_api_key is missing.
_title_llm: ChatGoogleGenerativeAI | None = None


def _get_title_llm() -> ChatGoogleGenerativeAI:
    global _title_llm
    if _title_llm is None:
        settings = get_settings()
        _title_llm = ChatGoogleGenerativeAI(
            model="gemini-3.1-flash-lite",
            google_api_key=settings.google_api_key,
        )
    return _title_llm


def format_sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


def extract_text_content(content) -> str:
    if isinstance(content, list):
        return " ".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )
    return content or ""


def get_checkpointer_context(db_path: str):
    if use_postgres_checkpointer():
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        settings = get_settings()
        conn_string = settings.database_url.replace("postgresql+psycopg://", "postgresql://", 1)
        return AsyncPostgresSaver.from_conn_string(conn_string)
    else:
        return AsyncSqliteSaver.from_conn_string(db_path)


def parse_tool_output(tool_name: str, raw_output) -> tuple[str, list[dict]]:
    sources = []

    is_tavily = (
        "tavily" in tool_name.lower()
        or (
            isinstance(raw_output, dict)
            and "results" in raw_output
            and "query" in raw_output
        )
    )

    if is_tavily:
        try:
            if isinstance(raw_output, dict) and "results" in raw_output:
                results = raw_output.get("results", [])
                sources = [
                    {"title": r.get("title", ""), "url": r.get("url", "")}
                    for r in results
                    if isinstance(r, dict) and r.get("url")
                ]
                tool_output = " ".join(
                    r.get("content", "") for r in results if isinstance(r, dict)
                )
            elif isinstance(raw_output, list):
                sources = [
                    {"title": r.get("title", ""), "url": r.get("url", "")}
                    for r in raw_output
                    if isinstance(r, dict) and r.get("url")
                ]
                tool_output = " ".join(
                    r.get("content", "") for r in raw_output if isinstance(r, dict)
                )
            else:
                tool_output = str(raw_output)
        except Exception:
            tool_output = str(raw_output)
    else:
        tool_output = str(raw_output)

    return tool_output, sources


async def build_ltm_context(db: AsyncSession, user_id: str) -> str:
    """Load LTM profile entries for this user and return as formatted string."""
    entries = await get_profile(db, user_id)
    if not entries:
        return ""
    lines = [f"{e.key}: {e.value}" for e in entries]
    return "\n".join(lines)


async def build_doc_context(db: AsyncSession, user_id: str) -> str:
    """
    Load uploaded document names for this user.
    Grounds agent's document_search decisions in actual upload state.
    """
    result = await db.execute(
        select(Document.filename).where(Document.user_id == user_id)
    )
    filenames = [row[0] for row in result.fetchall()]

    if not filenames:
        return "[System: User has no documents uploaded. Do not call document_search.]"

    names = ", ".join(filenames)
    return (
        f"[System: User has {len(filenames)} document(s) uploaded: {names}. "
        f"Only call document_search when the user is asking about content from these documents.]"
    )


async def generate_title(message: str) -> str:
    try:
        prompt = (
            f"Generate a short 4-5 word title for a conversation "
            f"that starts with this message: '{message}'. "
            f"Return ONLY the title, nothing else. No quotes, no punctuation at end."
        )
        response = await _get_title_llm().ainvoke(prompt)
        # Gemini 3.x returns content as a list of parts — extract text safely
        raw = response.content
        if isinstance(raw, list):
            title = " ".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in raw
            ).strip()
        else:
            title = str(raw).strip()
        return title or "New Chat"
    except Exception as e:
        logger.warning(f"Title generation failed: {str(e)}")
        return "New Chat"


async def stream_agent_response(
    thread_id: str,
    message: str,
    db: AsyncSession,
    user_id: str,
) -> AsyncGenerator[str, None]:

    # ── Session metrics init ─────────────────────────────────────────────────
    # thread_id IS the session_id in AgentLens — the frontend holds it already.
    # Set the ContextVar so reasoner, tool_executor, ltm_store, and rag/store
    # can all read the current session_id without any signature changes.
    tel.current_session_id.set(thread_id)
    tel.init_session(thread_id)
    if tel.active_sessions_gauge:
        tel.active_sessions_gauge.add(1, {"session.id": thread_id})

    try:
        db_path = get_db_path()
        ltm_context = await build_ltm_context(db, user_id)
        doc_context = await build_doc_context(db, user_id)

        config = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": 10,
        }
        input_state = {
            "messages": [HumanMessage(content=message)],
            "ltm_context": ltm_context,
            "doc_context": doc_context,
        }

        # ── Root span for the entire stream turn ────────────────────────────
        # Wraps the full astream_events loop so SigNoz shows the complete
        # request waterfall under one parent span with session.id attached.
        with _tracer.start_as_current_span("agentlens.chat.stream") as span:
            span.set_attribute("session.id", thread_id)
            span.set_attribute("user.id", user_id)
            span.set_attribute("chat.has_ltm", bool(ltm_context))
            span.set_attribute("chat.has_docs", bool(doc_context))

            async with get_checkpointer_context(db_path) as checkpointer:
                graph_with_memory = get_graph_with_checkpointer(checkpointer, user_id)
                async for event in graph_with_memory.astream_events(
                    input_state,
                    config=config,
                    version="v2",
                ):
                    event_name = event.get("event")
                    event_data = event.get("data", {})

                    if event_name == "on_chat_model_stream":
                        chunk = event_data.get("chunk")
                        if chunk and hasattr(chunk, "content") and chunk.content:
                            text = extract_text_content(chunk.content)
                            if text.strip():
                                yield format_sse({"type": "text", "content": text})

                    elif event_name == "on_tool_start":
                        tool_name = event.get("name", "")
                        tool_input = event_data.get("input", {})
                        yield format_sse({
                            "type": "tool_start",
                            "tool_name": tool_name,
                            "tool_input": tool_input,
                        })

                    elif event_name == "on_tool_end":
                        tool_name = event.get("name", "")
                        raw_output = event_data.get("output", "")
                        tool_output, sources = parse_tool_output(tool_name, raw_output)
                        yield format_sse({
                            "type": "tool_end",
                            "tool_name": tool_name,
                            "tool_output": tool_output,
                            "sources": sources,
                        })

                state = await graph_with_memory.aget_state(config)
                if state and state.values.get("messages"):
                    async with AsyncSessionLocal() as fresh_db:
                        try:
                            saved_keys = await memory_writer_node(state.values, fresh_db, user_id)
                            await fresh_db.commit()
                            if saved_keys:
                                yield format_sse({"type": "memory_update", "keys": saved_keys})
                        except Exception as e:
                            await fresh_db.rollback()
                            logger.error(f"Memory writer failed for user {user_id}: {str(e)}")

        yield format_sse({"type": "done"})

    except Exception as e:
        logger.error(f"Stream error for user {user_id}: {str(e)}", exc_info=True)
        yield format_sse({"type": "error", "message": "Something went wrong. Please try again."})

    finally:
        # Always decrement active sessions — even on error or early exit
        if tel.active_sessions_gauge:
            tel.active_sessions_gauge.add(-1, {"session.id": thread_id})
        # Reset ContextVar so it doesn't bleed into other requests
        tel.current_session_id.set("")


def build_chat_history(state) -> list[ChatMessage]:
    messages = []
    if not state or not state.values.get("messages"):
        return messages

    for msg in state.values["messages"]:
        if isinstance(msg, HumanMessage):
            messages.append(ChatMessage(role="human", content=msg.content))
        elif isinstance(msg, AIMessage):
            content = extract_text_content(msg.content)
            clean_lines = [
                line for line in content.split("\n")
                if not line.strip().startswith("MEMORY_UPDATE:")
            ]
            clean_content = "\n".join(clean_lines).strip()
            if clean_content:
                messages.append(ChatMessage(role="ai", content=clean_content))

    return messages