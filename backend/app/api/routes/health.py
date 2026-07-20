from fastapi import APIRouter
from sqlalchemy import text

from app.db.base import AsyncSessionLocal
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.get("/health", tags=["Health"])
async def health():
    """
    Liveness check — verifies DB connectivity.
    Returns 200 only if the database is reachable.
    Returns 503 if DB is down so load balancers and uptime monitors
    can correctly detect an unhealthy instance.
    """
    db_status = "ok"
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception as e:
        logger.error(f"Health check DB ping failed: {str(e)}")
        db_status = "unreachable"

    healthy = db_status == "ok"
    return {
        "status": "ok" if healthy else "degraded",
        "service": "neurograph-ai",
        "checks": {
            "database": db_status,
        },
    }, 200 if healthy else 503