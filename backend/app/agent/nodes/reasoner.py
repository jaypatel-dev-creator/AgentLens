import time

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage
from langchain_core.tools import BaseTool
from opentelemetry import trace

from app.agent.state import AgentState
from app.core.config import get_settings
from app.core.logging import get_logger
import app.telemetry as tel

logger = get_logger(__name__)
_tracer = trace.get_tracer("agentlens.reasoner")


# used in graph.py in compile_graph() function to bind llm with tools
def build_llm_with_tools(tools: list[BaseTool]) -> ChatGoogleGenerativeAI:
    settings = get_settings()
    llm = ChatGoogleGenerativeAI(
        model="gemini-3.1-flash-lite",
        google_api_key=settings.google_api_key,
        temperature=0.7,
    )
    return llm.bind_tools(tools)


# Called every turn inside reasoner_node — builds fresh system prompt with updated LTM and doc context
def build_system_prompt(tools: list[BaseTool], ltm_context: str, doc_context: str) -> str:
    tool_descriptions = "\n".join(
        f"- {t.name}: {t.description}" for t in tools
    )

    base = f"""You are AgentLens — an intelligent, conversational AI agent with persistent memory, real-time tool access, and full observability. Every decision you make, every tool you call, and every token you consume is traced, measured, and visible in SigNoz. You remember past conversations, learn from interactions, and are transparent about what you're doing and why.
CORE RULE: Always give a warm, helpful conversational response to the user FIRST.
Never respond with only a MEMORY_UPDATE line. Always say something meaningful to the user.

You have access to the following tools:
{tool_descriptions}

Tool usage rules:
- Use tools ONLY when the user asks for real-time, current, or factual data
  you cannot confidently answer from your own knowledge — such as current
  prices, weather, today's date, or recent events.
- For general knowledge questions — definitions, explanations, concepts,
  how things work, historical facts, science, math theory, etc. — answer
  DIRECTLY from your own knowledge. Do NOT search the web or use any tool
  for things you already know well. Tools are for real-time data you
  genuinely cannot know on your own, not a substitute for reasoning.
- ALWAYS call get_datetime FIRST whenever the question involves today's date,
  current time, "today", "now", "latest", "current", or anything time-sensitive —
  before searching the web or using any other tool. Never assume or guess the
  current date from search result content.
- Call document_search only when the user has uploaded documents AND is asking
  about their content. If no documents are uploaded, never call document_search.
  If documents are uploaded but the question is general knowledge, answer directly
  without calling document_search.
  If document_search returns no relevant content, tell the user plainly that nothing
  was found — do not guess or fabricate document content.
- If no tool is needed, respond directly and conversationally
- After using a tool, explain the result clearly to the user

Memory rules:
- If you learn anything meaningful about the user, save it using a MEMORY_UPDATE line
  at the VERY END of your response, after your conversational reply
- Always save: name, location/city, profession, preferences, interests, skills,
  experience, goals, or any personal detail the user shares
- Treat "currently in X" or "I am in X" as location — always save it as location=X
- Format: MEMORY_UPDATE: key=<key> value=<value>
- Only add MEMORY_UPDATE when the user shares new information not already known
- Never add MEMORY_UPDATE without also giving a proper conversational response first
- You can include multiple MEMORY_UPDATE lines if needed

Example of correct behavior:
User: "Hi, my name is Jay and I am an AI engineer"
You: "Nice to meet you, Jay! That's exciting — AI engineering is such a dynamic field
right now. What are you currently working on?
MEMORY_UPDATE: key=name value=Jay
MEMORY_UPDATE: key=profession value=AI engineer"

User: "currently i am in mumbai india"
You: "That's great, Mumbai is a vibrant city! How are you finding it?
MEMORY_UPDATE: key=location value=Mumbai, India"

Example of WRONG behavior:
User: "Hi, my name is Jay"
You: "MEMORY_UPDATE: key=name value=Jay" ← NEVER do this
"""

    if ltm_context:
        base += f"\n\nWhat you already know about the user:\n{ltm_context}"
        base += "\n\nUse this context naturally in conversation without explicitly saying 'I remember that...'"

    if doc_context:
        base += f"\n\n{doc_context}"

    return base


async def reasoner_node(
    state: AgentState,
    llm_with_tools: ChatGoogleGenerativeAI,
    tools: list[BaseTool],
) -> dict:
    logger.debug("Reasoner node executing")

    system_prompt = build_system_prompt(
        tools,
        state.get("ltm_context", ""),
        state.get("doc_context", ""),
    )
    messages = [SystemMessage(content=system_prompt)] + state["messages"]

    with _tracer.start_as_current_span("agentlens.reasoner") as span:
        span.set_attribute("llm.model", "gemini-3.1-flash-lite")
        span.set_attribute("llm.message_count", len(messages))
        span.set_attribute("llm.has_ltm_context", bool(state.get("ltm_context")))
        span.set_attribute("llm.has_doc_context", bool(state.get("doc_context")))
        span.set_attribute("llm.tool_count", len(tools))

        t0 = time.perf_counter()
        response = await llm_with_tools.ainvoke(messages)
        latency_ms = (time.perf_counter() - t0) * 1000

        input_tokens = 0
        output_tokens = 0
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            input_tokens = response.usage_metadata.get("input_tokens", 0)
            output_tokens = response.usage_metadata.get("output_tokens", 0)

        total_tokens = input_tokens + output_tokens

        span.set_attribute("llm.input_tokens", input_tokens)
        span.set_attribute("llm.output_tokens", output_tokens)
        span.set_attribute("llm.total_tokens", total_tokens)
        span.set_attribute("llm.latency_ms", round(latency_ms, 2))
        span.set_attribute("llm.tool_calls_requested", len(getattr(response, "tool_calls", []) or []))

        if tel.token_cost_counter and total_tokens:
            tel.token_cost_counter.add(
                total_tokens,
                {"llm.model": "gemini-3.1-flash-lite", "token.type": "total"},
            )
        if tel.llm_latency_histogram:
            tel.llm_latency_histogram.record(
                latency_ms,
                {"llm.model": "gemini-3.1-flash-lite"},
            )

        # ── Per-session token recording ──────────────────────────────────────
        # Reads session_id from the ContextVar set in stream_agent_response.
        # No-op if session_id is "" (e.g. called outside a stream context).
        session_id = tel.current_session_id.get()
        tel.record_session_tokens(session_id, input_tokens, output_tokens, latency_ms)

        logger.info(
            "Reasoner complete — tokens: %d in / %d out | latency: %.1fms | tool_calls: %d",
            input_tokens,
            output_tokens,
            latency_ms,
            len(getattr(response, "tool_calls", []) or []),
        )

    return {"messages": [response]}