"""
AgentLens — Telemetry Bootstrap
Registers custom metrics for AgentLens observability.

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
from opentelemetry.trace import NonRecordingSpan

logger = logging.getLogger(__name__)

# ── Custom metric instruments ───────────────────────────────────────────────
token_cost_counter = None
tool_call_counter = None
ltm_operation_counter = None
retrieval_latency_histogram = None
llm_latency_histogram = None
active_sessions_gauge = None

# ── Request-scoped session ID ───────────────────────────────────────────────
current_session_id: ContextVar[str] = ContextVar("current_session_id", default="")

# ── In-memory session metrics store ────────────────────────────────────────
_session_store: dict[str, dict] = {}
_store_lock = threading.Lock()
SESSION_TTL_SECONDS = 3600  # 1 hour


def _prune_old_sessions() -> None:
    cutoff = time.time() - SESSION_TTL_SECONDS
    expired = [sid for sid, s in _session_store.items() if s["last_updated"] < cutoff]
    for sid in expired:
        del _session_store[sid]


def init_session(session_id: str) -> None:
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
    with _store_lock:
        data = _session_store.get(session_id)
        if data is None:
            return None
        return dict(data)


def record_session_tokens(
    session_id: str,
    tokens_in: int,
    tokens_out: int,
    latency_ms: float,
) -> None:
    if not session_id:
        return
    with _store_lock:
        s = _session_store.get(session_id)
        if s is None:
            return
        s["tokens_in"] += tokens_in
        s["tokens_out"] += tokens_out
        s["tokens_total"] += tokens_in + tokens_out
        s["llm_latency_ms"] = round(latency_ms, 2)
        s["llm_calls"] += 1
        s["last_updated"] = time.time()


def record_session_tool_call(
    session_id: str,
    tool_name: str,
    success: bool,
    latency_ms: float,
) -> None:
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
    if not session_id:
        return
    with _store_lock:
        s = _session_store.get(session_id)
        if s is None:
            return
        s["retrieval_latency_ms"].append(round(latency_ms, 2))
        s["last_updated"] = time.time()


def record_session_ltm(session_id: str, operation: str) -> None:
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

    logger.info(
        "AgentLens telemetry active — service: %s | endpoint: %s",
        service_name,
        otlp_endpoint,
    )


def is_telemetry_active() -> bool:
    """
    Returns True if a real SDK TracerProvider is registered.
    Returns False if OTel was never initialised (NoOpTracerProvider).

    The opentelemetry-instrument CLI installs a real provider before
    the app starts; if it didn't run, get_tracer() returns a no-op
    tracer whose spans are NonRecordingSpan instances.
    """
    test_span = trace.get_tracer("agentlens.healthcheck").start_span("_healthcheck")
    active = not isinstance(test_span, NonRecordingSpan)
    test_span.end()
    return active


def get_tracer(name: str = "agentlens"):
    return trace.get_tracer(name)


def get_meter(name: str = "agentlens"):
    return metrics.get_meter(name)


def shutdown_telemetry() -> None:
    logger.info("AgentLens telemetry shut down.")