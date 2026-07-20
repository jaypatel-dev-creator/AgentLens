from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse
from app.services.auth_service import register_user, login_user

router = APIRouter()


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new user. Returns a JWT on success.
    Immediately authenticates — no separate login step needed after registration.
    409 if email already exists.
    """
    return await register_user(db, payload)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticate an existing user. Returns a JWT on success.
    401 on wrong email or wrong password (same error — no enumeration).
    """
    return await login_user(db, payload)