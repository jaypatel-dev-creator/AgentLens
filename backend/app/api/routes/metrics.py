"""
AgentLens — Metrics Routes
Exposes per-session observability data for the frontend observability panel.
All endpoints are auth-protected — a user can only query sessions they own
(enforced by verifying the thread belongs to the current user).
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.db.models import User
from app.services.thread_service import get_thread_by_id
from app.services.metrics_service import get_session_summary
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.get("/session/{session_id}")
async def get_session_metrics(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return live telemetry metrics for a session (thread_id).

    session_id == thread_id in AgentLens — the UUID the frontend already holds
    when it opens a chat stream. The frontend can call this endpoint mid-stream
    or after the stream ends to display the observability sidebar panel.

    Auth: caller must own the thread. Returns 404 if thread not found or
    belongs to another user. Returns 204 if the session has no metrics yet
    (stream not started or store expired after SESSION_TTL_SECONDS).
    """
    # Ownership check — thread must exist and belong to the current user
    thread = await get_thread_by_id(db, current_user.id, session_id)
    if not thread:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found or access denied.",
        )

    summary = get_session_summary(session_id)
    if summary is None:
        # Session exists in DB but has no in-memory metrics yet.
        # This is normal before the first message is sent, or after TTL expiry.
        raise HTTPException(
            status_code=404,
            detail=f"No metrics available for session '{session_id}'. "
                   "Send a message first to start recording.",
        )

    logger.debug(
        "Metrics fetched — session: %s | tokens: %d | tools: %d",
        session_id,
        summary["tokens"]["total"],
        summary["tools"]["total_calls"],
    )

    return summary