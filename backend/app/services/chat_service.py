import json
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from opentelemetry import trace, context as otel_context

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

#module level singleton 
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
    """
    Public entry point. Opens the root OTel span here — in a regular async
    function, not a generator — so the span context is captured and exported
    reliably before SSE streaming begins. The captured context is then passed
    into the inner generator so all child spans attach to this root.
    """
    # ── Session metrics init ─────────────────────────────────────────────────
    tel.current_session_id.set(thread_id)
    tel.init_session(thread_id)
    if tel.active_sessions_gauge:
        tel.active_sessions_gauge.add(1, {"session.id": thread_id})

    # ── Root span — opened here, NOT inside the generator ───────────────────
    # Async generators hold spans open across yields, which causes unreliable
    # export on Render (span drops if generator GC'd before OTLP flush).
    # Opening the span in a regular async function guarantees it is exported
    # as soon as this function returns, while child spans still attach via
    # the propagated context token passed to _stream_events().
    span = _tracer.start_span("agentlens.chat.stream")
    span.set_attribute("session.id", thread_id)
    span.set_attribute("user.id", user_id)

    try:
        db_path = get_db_path()
        ltm_context = await build_ltm_context(db, user_id)
        doc_context = await build_doc_context(db, user_id)

        span.set_attribute("chat.has_ltm", bool(ltm_context))
        span.set_attribute("chat.has_docs", bool(doc_context))

        # Capture the OTel context with the span active so the generator
        # can attach child spans to this root without holding the span open.
        ctx = otel_context.get_current()
        with trace.use_span(span, end_on_exit=True):
            ctx = otel_context.get_current()

        # Delegate to the inner generator, passing the captured context
        async for chunk in _stream_events(
            thread_id, message, db, user_id,
            ltm_context, doc_context, db_path, ctx,
        ):
            yield chunk

    except Exception as e:
        span.record_exception(e)
        span.end()
        logger.error(f"Stream setup error for user {user_id}: {str(e)}", exc_info=True)
        yield format_sse({"type": "error", "message": "Something went wrong. Please try again."})

    finally:
        if tel.active_sessions_gauge:
            tel.active_sessions_gauge.add(-1, {"session.id": thread_id})
        tel.current_session_id.set("")


async def _stream_events(
    thread_id: str,
    message: str,
    db: AsyncSession,
    user_id: str,
    ltm_context: str,
    doc_context: str,
    db_path: str,
    ctx: object,
) -> AsyncGenerator[str, None]:
    """
    Inner generator. Runs the LangGraph stream and yields SSE chunks.
    Receives the root span's OTel context so child spans (reasoner, tools,
    ltm, rag) attach correctly in SigNoz without holding the root span open.
    """
    token = otel_context.attach(ctx)
    try:
        config = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": 10,
        }
        input_state = {
            "messages": [HumanMessage(content=message)],
            "ltm_context": ltm_context,
            "doc_context": doc_context,
        }

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
        otel_context.detach(token)


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