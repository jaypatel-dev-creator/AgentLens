import time
from datetime import datetime, timezone
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from opentelemetry import trace

from app.db.models import UserProfile
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.exceptions import LTMException
import app.telemetry as tel

logger = get_logger(__name__)
_tracer = trace.get_tracer("agentlens.ltm")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def get_profile(db: AsyncSession, user_id: str) -> list[UserProfile]:
    with _tracer.start_as_current_span("agentlens.ltm.read") as span:
        span.set_attribute("ltm.operation", "read")
        span.set_attribute("ltm.user_id", user_id)

        t0 = time.perf_counter()
        try:
            result = await db.execute(
                select(UserProfile)
                .where(UserProfile.user_id == user_id)
                .order_by(UserProfile.key)
            )
            entries = list(result.scalars().all())
            latency_ms = (time.perf_counter() - t0) * 1000

            span.set_attribute("ltm.record_count", len(entries))
            span.set_attribute("ltm.latency_ms", round(latency_ms, 2))

            if tel.ltm_operation_counter:
                tel.ltm_operation_counter.add(
                    1,
                    {"ltm.operation": "read"},
                )

            logger.info(
                "LTM read — user: %s | records: %d | latency: %.1fms",
                user_id,
                len(entries),
                latency_ms,
            )
            return entries

        except Exception as e:
            span.record_exception(e)
            raise LTMException(f"Failed to fetch LTM profile: {str(e)}")


async def upsert_profile_entry(
    db: AsyncSession,
    user_id: str,
    key: str,
    value: str,
) -> UserProfile:
    settings = get_settings()
    now = utcnow()

    with _tracer.start_as_current_span("agentlens.ltm.write") as span:
        span.set_attribute("ltm.operation", "write")
        span.set_attribute("ltm.user_id", user_id)
        span.set_attribute("ltm.key", key)

        t0 = time.perf_counter()
        try:
            if settings.database_url:
                from sqlalchemy.dialects.postgresql import insert as pg_insert
                stmt = (
                    pg_insert(UserProfile)
                    .values(user_id=user_id, key=key, value=value, updated_at=now)
                    .on_conflict_do_update(
                        index_elements=["user_id", "key"],
                        set_={"value": value, "updated_at": now},
                    )
                )
            else:
                from sqlalchemy.dialects.sqlite import insert as sqlite_insert
                stmt = (
                    sqlite_insert(UserProfile)
                    .values(user_id=user_id, key=key, value=value, updated_at=now)
                    .on_conflict_do_update(
                        index_elements=["user_id", "key"],
                        set_={"value": value, "updated_at": now},
                    )
                )

            await db.execute(stmt)
            await db.flush()

            result = await db.execute(
                select(UserProfile).where(
                    UserProfile.user_id == user_id,
                    UserProfile.key == key,
                )
            )
            entry = result.scalar_one()
            latency_ms = (time.perf_counter() - t0) * 1000

            span.set_attribute("ltm.latency_ms", round(latency_ms, 2))

            if tel.ltm_operation_counter:
                tel.ltm_operation_counter.add(
                    1,
                    {"ltm.operation": "write"},
                )

            logger.info(
                "LTM write — user: %s | key: %s | latency: %.1fms",
                user_id,
                key,
                latency_ms,
            )
            return entry

        except LTMException:
            raise
        except Exception as e:
            span.record_exception(e)
            raise LTMException(f"Failed to upsert LTM entry '{key}': {str(e)}")


async def delete_profile(db: AsyncSession, user_id: str) -> None:
    try:
        await db.execute(delete(UserProfile).where(UserProfile.user_id == user_id))
        await db.flush()
        logger.info(f"LTM profile cleared — user: {user_id}")
    except Exception as e:
        raise LTMException(f"Failed to clear LTM profile: {str(e)}")


async def delete_profile_entry(db: AsyncSession, user_id: str, key: str) -> bool:
    try:
        result = await db.execute(
            select(UserProfile).where(
                UserProfile.user_id == user_id,
                UserProfile.key == key,
            )
        )
        entry = result.scalar_one_or_none()

        if not entry:
            return False

        await db.execute(
            delete(UserProfile).where(
                UserProfile.user_id == user_id,
                UserProfile.key == key,
            )
        )
        await db.flush()
        logger.info(f"LTM entry deleted — user: {user_id} key: {key}")
        return True
    except LTMException:
        raise
    except Exception as e:
        raise LTMException(f"Failed to delete LTM entry '{key}': {str(e)}")


async def update_profile_entry(
    db: AsyncSession,
    user_id: str,
    key: str,
    value: str,
) -> UserProfile | None:
    try:
        result = await db.execute(
            select(UserProfile).where(
                UserProfile.user_id == user_id,
                UserProfile.key == key,
            )
        )
        entry = result.scalar_one_or_none()

        if not entry:
            return None

        entry.value = value
        entry.updated_at = utcnow()
        await db.flush()
        return entry
    except LTMException:
        raise
    except Exception as e:
        raise LTMException(f"Failed to update LTM entry '{key}': {str(e)}")