from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.db.models import User
from app.core.exceptions import ProfileEntryNotFoundException
from app.memory.ltm_store import (
    get_profile,
    upsert_profile_entry,
    delete_profile,
    delete_profile_entry,
    update_profile_entry,
)
from app.schemas.memory import ProfileRead, ProfileEntry, ProfileUpsert, ProfileEntryUpdate

router = APIRouter()


@router.get("/profile", response_model=ProfileRead)
async def read_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    entries = await get_profile(db, current_user.id)
    return ProfileRead(
        entries=[ProfileEntry.model_validate(e) for e in entries]
    )


@router.put("/profile", response_model=ProfileEntry)
async def upsert_profile(
    payload: ProfileUpsert,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    entry = await upsert_profile_entry(db, current_user.id, payload.key, payload.value)
    return ProfileEntry.model_validate(entry)


@router.patch("/profile/{key}", response_model=ProfileEntry)
async def update_profile_entry_route(
    key: str,
    payload: ProfileEntryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    entry = await update_profile_entry(db, current_user.id, key, payload.value)
    if not entry:
        raise ProfileEntryNotFoundException(key)
    return ProfileEntry.model_validate(entry)


@router.delete("/profile/{key}", status_code=204)
async def delete_single_profile_entry(
    key: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deleted = await delete_profile_entry(db, current_user.id, key)
    if not deleted:
        raise ProfileEntryNotFoundException(key)


@router.delete("/profile", status_code=204)
async def clear_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await delete_profile(db, current_user.id)