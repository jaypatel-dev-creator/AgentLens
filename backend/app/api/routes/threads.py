from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.db.models import User
from app.schemas.thread import ThreadCreate, ThreadRead, ThreadUpdate
from app.core.exceptions import ThreadNotFoundException
from app.services.thread_service import (
    create_thread,
    list_threads,
    get_thread_by_id,
    rename_thread,
    delete_thread,
)

router = APIRouter()


@router.post("", response_model=ThreadRead, status_code=201)
async def create_thread_route(
    payload: ThreadCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    thread = await create_thread(db, current_user.id, payload.title)
    return ThreadRead.model_validate(thread)


@router.get("", response_model=list[ThreadRead])
async def list_threads_route(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    threads = await list_threads(db, current_user.id)
    return [ThreadRead.model_validate(t) for t in threads]


@router.get("/{thread_id}", response_model=ThreadRead)
async def get_thread_route(
    thread_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    thread = await get_thread_by_id(db, current_user.id, thread_id)
    if not thread:
        raise ThreadNotFoundException(thread_id)
    return ThreadRead.model_validate(thread)


@router.patch("/{thread_id}", response_model=ThreadRead)
async def rename_thread_route(
    thread_id: str,
    payload: ThreadUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    thread = await get_thread_by_id(db, current_user.id, thread_id)
    if not thread:
        raise ThreadNotFoundException(thread_id)
    thread = await rename_thread(db, thread, payload.title)
    return ThreadRead.model_validate(thread)


@router.delete("/{thread_id}", status_code=204)
async def delete_thread_route(
    thread_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    thread = await get_thread_by_id(db, current_user.id, thread_id)
    if not thread:
        raise ThreadNotFoundException(thread_id)
    await delete_thread(db, thread_id)