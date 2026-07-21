"""
AgentLens — Telemetry Bootstrap
Registers custom metrics and auto-instruments LangChain/LangGraph.

Provider setup is handled by the opentelemetry-instrument CLI wrapper,
which sets TracerProvider and MeterProvider before the app starts.
This module only adds custom metric instruments on top.

Call setup_telemetry() once at application startup (lifespan).
"""

import logging
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