import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.db.models import Thread
from app.core.logging import get_logger
from app.core.exceptions import ThreadServiceException, ForbiddenException

logger = get_logger(__name__)


async def create_thread(db: AsyncSession, user_id: str, title: str) -> Thread:
    """Create a new thread scoped to user."""
    try:
        thread_id = str(uuid.uuid4())
        thread = Thread(
            id=thread_id,
            user_id=user_id,
            title=title,
            is_titled=False,
        )
        db.add(thread)
        await db.flush()
        await db.refresh(thread)
        logger.info(f"Thread created: {thread_id} — user: {user_id}")
        return thread
    except ThreadServiceException:
        raise
    except Exception as e:
        raise ThreadServiceException(f"Failed to create thread: {str(e)}")


async def list_threads(db: AsyncSession, user_id: str) -> list[Thread]:
    """Return all threads for this user, most recently updated first."""
    try:
        result = await db.execute(
            select(Thread)
            .where(Thread.user_id == user_id)
            .order_by(Thread.updated_at.desc())
        )
        return list(result.scalars().all())
    except ThreadServiceException:
        raise
    except Exception as e:
        raise ThreadServiceException(f"Failed to list threads: {str(e)}")


async def get_thread_by_id(db: AsyncSession, user_id: str, thread_id: str) -> Thread | None:
    """
    Return a thread by ID, scoped to user.
    Returns None if not found. Raises ForbiddenException if thread exists but belongs to another user.
    """
    try:
        result = await db.execute(
            select(Thread).where(Thread.id == thread_id)
        )
        thread = result.scalar_one_or_none()

        if thread is None:
            return None

        # Thread exists but belongs to a different user — 403, not 404
        # Returning 404 here would leak whether the thread_id exists at all
        if thread.user_id != user_id:
            raise ForbiddenException()

        return thread
    except (ThreadServiceException, ForbiddenException):
        raise
    except Exception as e:
        raise ThreadServiceException(f"Failed to fetch thread '{thread_id}': {str(e)}")


async def rename_thread(db: AsyncSession, thread: Thread, title: str) -> Thread:
    """Rename a thread and mark it as titled. Ownership already verified by caller."""
    try:
        thread.title = title
        thread.is_titled = True
        await db.flush()
        await db.refresh(thread)
        logger.info(f"Thread renamed: {thread.id} → {title}")
        return thread
    except ThreadServiceException:
        raise
    except Exception as e:
        raise ThreadServiceException(f"Failed to rename thread '{thread.id}': {str(e)}")


async def delete_thread(db: AsyncSession, thread_id: str) -> None:
    """Delete a thread by ID. Ownership already verified by caller."""
    try:
        await db.execute(delete(Thread).where(Thread.id == thread_id))
        await db.flush()
        logger.info(f"Thread deleted: {thread_id}")
    except ThreadServiceException:
        raise
    except Exception as e:
        raise ThreadServiceException(f"Failed to delete thread '{thread_id}': {str(e)}")