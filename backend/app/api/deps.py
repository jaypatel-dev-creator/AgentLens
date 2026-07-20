from collections.abc import AsyncGenerator

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.base import AsyncSessionLocal
from app.db.models import User
from app.core.security import decode_access_token
from app.core.exceptions import UnauthorizedException

# HTTPBearer extracts the token from "Authorization: Bearer <token>" header
# auto_error=False so we raise our own UnauthorizedException instead of FastAPI's default 403
_bearer = HTTPBearer(auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> User:
    """
    Dependency injected into every protected route.
    1. Extracts Bearer token from Authorization header.
    2. Decodes + verifies JWT → gets user_id.
    3. Fetches User from DB — ensures user still exists (e.g. not deleted).
    4. Returns User ORM object — routes access current_user.id directly.
    """
    if credentials is None:
        raise UnauthorizedException("Authorization header missing.")

    user_id = decode_access_token(credentials.credentials)

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise UnauthorizedException("User no longer exists.")

    return user