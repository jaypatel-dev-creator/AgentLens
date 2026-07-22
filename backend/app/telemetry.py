"""
AgentLens — Telemetry Bootstrap
Registers custom metrics and auto-instruments LangChain/LangGraph.

Provider setup is handled by the opentelemetry-instrument CLI wrapper,
which sets TracerProvider and MeterProvider before the app starts.
This module only adds custom metric instruments on top.

Call setup_telemetry() once at application startup (lifespan).
"""

import logging
import threading
import time
from contextvars import ContextVar
from opentelemetry import trace, metrics
from openinference.instrumentation.langchain import LangChainInstrumentor

logger = logging.getLogger(__name__)

# ── Custom metric instruments ───────────────────────────────────────────────
# Accessed directly by other modules after setup_telemetry() is called.
token_cost_counter = None
tool_call_counter = None
ltm_operation_counter = None
retrieval_latency_histogram = None
llm_latency_histogram = None
active_sessions_gauge = None

# ── Request-scoped session ID ───────────────────────────────────────────────
# Set once in stream_agent_response before the graph runs.
# Readable from any coroutine in the same async context — reasoner, tool_executor,
# ltm_store, rag/store — with zero signature changes to those functions.
# Default "" means "no active session" — all record_session_* calls are no-ops.
current_session_id: ContextVar[str] = ContextVar("current_session_id", default="")

# ── In-memory session metrics store ────────────────────────────────────────
# Keyed by thread_id (which IS the session ID in AgentLens).
# Structure per session:
#   {
#     "tokens_in": int,
#     "tokens_out": int,
#     "tokens_total": int,
#     "llm_latency_ms": float,          # last LLM call latency
#     "llm_calls": int,
#     "tool_calls": [{"name": str, "success": bool, "latency_ms": float}],
#     "retrieval_latency_ms": [float],   # one entry per RAG query
#     "ltm_reads": int,
#     "ltm_writes": int,
#     "started_at": float,               # time.time()
#     "last_updated": float,
#   }
#
# Written by: chat_service (session open/close), reasoner, tool_executor,
#             ltm_store, rag/store via record_session_* helpers below.
# Read by:    metrics_service → GET /metrics/session/{session_id}
#
# TTL: sessions older than SESSION_TTL_SECONDS are pruned on each write
# to prevent unbounded memory growth on long-running servers.

_session_store: dict[str, dict] = {}
_store_lock = threading.Lock()
SESSION_TTL_SECONDS = 3600  # 1 hour


def _prune_old_sessions() -> None:
    """Remove sessions not updated in the last SESSION_TTL_SECONDS. Call inside lock."""
    cutoff = time.time() - SESSION_TTL_SECONDS
    expired = [sid for sid, s in _session_store.items() if s["last_updated"] < cutoff]
    for sid in expired:
        del _session_store[sid]


def init_session(session_id: str) -> None:
    """Create or reset the metrics bucket for a session. Called at stream start."""
    with _store_lock:
        _prune_old_sessions()
        _session_store[session_id] = {
            "tokens_in": 0,
            "tokens_out": 0,
            "tokens_total": 0,
            "llm_latency_ms": 0.0,
            "llm_calls": 0,
            "tool_calls": [],
            "retrieval_latency_ms": [],
            "ltm_reads": 0,
            "ltm_writes": 0,
            "started_at": time.time(),
            "last_updated": time.time(),
        }


def get_session_metrics(session_id: str) -> dict | None:
    """Return a snapshot of session metrics, or None if session not found."""
    with _store_lock:
        data = _session_store.get(session_id)
        if data is None:
            return None
        return dict(data)  # shallow copy — callers must not mutate nested lists


def record_session_tokens(
    session_id: str,
    tokens_in: int,
    tokens_out: int,
    latency_ms: float,
) -> None:
    """Called by reasoner_node after each LLM call."""
    if not session_id:
        return
    with _store_lock:
        s = _session_store.get(session_id)
        if s is None:
            return
        s["tokens_in"] += tokens_in
        s["tokens_out"] += tokens_out
        s["tokens_total"] += tokens_in + tokens_out
        s["llm_latency_ms"] = round(latency_ms, 2)   # keep last call latency
        s["llm_calls"] += 1
        s["last_updated"] = time.time()


def record_session_tool_call(
    session_id: str,
    tool_name: str,
    success: bool,
    latency_ms: float,
) -> None:
    """Called by tool_executor_node after each tool invocation."""
    if not session_id:
        return
    with _store_lock:
        s = _session_store.get(session_id)
        if s is None:
            return
        s["tool_calls"].append({
            "name": tool_name,
            "success": success,
            "latency_ms": round(latency_ms, 2),
        })
        s["last_updated"] = time.time()


def record_session_retrieval(session_id: str, latency_ms: float) -> None:
    """Called by rag/store after each vector query."""
    if not session_id:
        return
    with _store_lock:
        s = _session_store.get(session_id)
        if s is None:
            return
        s["retrieval_latency_ms"].append(round(latency_ms, 2))
        s["last_updated"] = time.time()


def record_session_ltm(session_id: str, operation: str) -> None:
    """Called by ltm_store on read/write. operation is 'read' or 'write'."""
    if not session_id:
        return
    with _store_lock:
        s = _session_store.get(session_id)
        if s is None:
            return
        if operation == "read":
            s["ltm_reads"] += 1
        elif operation == "write":
            s["ltm_writes"] += 1
        s["last_updated"] = time.time()


# ── Telemetry setup ─────────────────────────────────────────────────────────

def setup_telemetry(
    service_name: str,
    service_version: str,
    otlp_endpoint: str,
    otlp_headers: dict,
) -> None:
    """
    Register custom AgentLens metric instruments and auto-instrument LangChain.
    TracerProvider and MeterProvider are already set by the CLI wrapper.
    """
    global token_cost_counter, tool_call_counter, ltm_operation_counter
    global retrieval_latency_histogram, llm_latency_histogram, active_sessions_gauge

    meter = metrics.get_meter("agentlens.metrics")

    token_cost_counter = meter.create_counter(
        name="agentlens.tokens.total",
        description="Total tokens consumed across all LLM calls",
        unit="tokens",
    )

    tool_call_counter = meter.create_counter(
        name="agentlens.tool.calls.total",
        description="Number of tool invocations, labelled by tool name",
        unit="calls",
    )

    ltm_operation_counter = meter.create_counter(
        name="agentlens.ltm.operations.total",
        description="Long-term memory read and write operations",
        unit="operations",
    )

    retrieval_latency_histogram = meter.create_histogram(
        name="agentlens.retrieval.latency",
        description="Vector store retrieval latency in milliseconds",
        unit="ms",
    )

    llm_latency_histogram = meter.create_histogram(
        name="agentlens.llm.latency",
        description="LLM response latency in milliseconds",
        unit="ms",
    )

    active_sessions_gauge = meter.create_up_down_counter(
        name="agentlens.sessions.active",
        description="Number of currently active chat sessions",
        unit="sessions",
    )

    # Auto-instrument LangChain/LangGraph — monkey-patches internals.
    # skip_dep_check=True suppresses the double-instrument warning that fires
    # when the CLI wrapper has already partially instrumented the environment
    # before this call runs.
    if not LangChainInstrumentor().is_instrumented_by_opentelemetry:
        LangChainInstrumentor().instrument(skip_dep_check=True)
    else:
        logger.debug("LangChainInstrumentor already active — skipping re-instrument.")

    logger.info(
        "AgentLens telemetry active — service: %s | endpoint: %s",
        service_name,
        otlp_endpoint,
    )


def get_tracer(name: str = "agentlens"):
    """Return a tracer scoped to the given instrumentation name."""
    return trace.get_tracer(name)


def get_meter(name: str = "agentlens"):
    """Return a meter scoped to the given instrumentation name."""
    return metrics.get_meter(name)


def shutdown_telemetry() -> None:
    """No-op — CLI wrapper handles provider shutdown on process exit."""
    logger.info("AgentLens telemetry shut down.")