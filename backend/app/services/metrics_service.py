"""
AgentLens — Metrics Service
Aggregates per-session telemetry data from the in-memory store in telemetry.py
into a clean, API-ready dict for GET /metrics/session/{session_id}.
"""

from app.core.logging import get_logger
import app.telemetry as tel

logger = get_logger(__name__)


def get_session_summary(session_id: str) -> dict | None:
    """
    Return a structured summary of metrics for a session (thread_id).
    Returns None if the session has no recorded data (not started or expired).

    Shape:
    {
        "session_id": str,
        "tokens": {
            "input": int,
            "output": int,
            "total": int,
        },
        "llm": {
            "calls": int,
            "last_latency_ms": float,
        },
        "tools": {
            "total_calls": int,
            "successful": int,
            "failed": int,
            "calls": [{"name": str, "success": bool, "latency_ms": float}],
        },
        "retrieval": {
            "total_queries": int,
            "avg_latency_ms": float | None,
            "max_latency_ms": float | None,
            "latencies_ms": [float],
        },
        "ltm": {
            "reads": int,
            "writes": int,
            "total": int,
        },
        "session": {
            "started_at": float,    # Unix timestamp
            "last_updated": float,  # Unix timestamp
            "duration_seconds": float,
        },
    }
    """
    raw = tel.get_session_metrics(session_id)
    if raw is None:
        logger.debug("No session metrics found for session_id=%s", session_id)
        return None

    retrieval_latencies: list[float] = raw["retrieval_latency_ms"]
    avg_retrieval = (
        round(sum(retrieval_latencies) / len(retrieval_latencies), 2)
        if retrieval_latencies
        else None
    )
    max_retrieval = max(retrieval_latencies) if retrieval_latencies else None

    tool_calls: list[dict] = raw["tool_calls"]
    successful_tools = sum(1 for t in tool_calls if t["success"])
    failed_tools = len(tool_calls) - successful_tools

    duration = round(raw["last_updated"] - raw["started_at"], 2)

    return {
        "session_id": session_id,
        "tokens": {
            "input": raw["tokens_in"],
            "output": raw["tokens_out"],
            "total": raw["tokens_total"],
        },
        "llm": {
            "calls": raw["llm_calls"],
            "last_latency_ms": raw["llm_latency_ms"],
        },
        "tools": {
            "total_calls": len(tool_calls),
            "successful": successful_tools,
            "failed": failed_tools,
            "calls": tool_calls,
        },
        "retrieval": {
            "total_queries": len(retrieval_latencies),
            "avg_latency_ms": avg_retrieval,
            "max_latency_ms": max_retrieval,
            "latencies_ms": retrieval_latencies,
        },
        "ltm": {
            "reads": raw["ltm_reads"],
            "writes": raw["ltm_writes"],
            "total": raw["ltm_reads"] + raw["ltm_writes"],
        },
        "session": {
            "started_at": raw["started_at"],
            "last_updated": raw["last_updated"],
            "duration_seconds": duration,
        },
    }