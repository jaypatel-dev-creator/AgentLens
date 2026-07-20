from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.db.base import AsyncSessionLocal
from app.db.models import User
from app.memory.checkpointer import get_db_path
from app.schemas.chat import ChatRequest, ChatHistoryRead
from app.core.exceptions import ThreadNotFoundException
from app.services.chat_service import (
    stream_agent_response,
    generate_title,
    get_checkpointer_context,
    build_chat_history,
)
from app.agent.graph import get_graph_with_checkpointer
from app.services.thread_service import get_thread_by_id

router = APIRouter()


@router.post("/stream")
async def stream_chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    thread = await get_thread_by_id(db, current_user.id, request.thread_id)
    if not thread:
        raise ThreadNotFoundException(request.thread_id)

    # Generate and commit title in a separate session BEFORE streaming starts.
    # The route's db session stays open for the entire stream duration —
    # committing title inside it would only happen after streaming ends,
    # which is too late for the frontend's refreshThreadTitle call.
    if not thread.is_titled:
        title = await generate_title(request.message)
        async with AsyncSessionLocal() as title_db:
            try:
                title_thread = await get_thread_by_id(title_db, current_user.id, request.thread_id)
                if title_thread:
                    title_thread.title = title
                    title_thread.is_titled = True
                    await title_db.commit()
            except Exception:
                await title_db.rollback()

    return StreamingResponse(
        stream_agent_response(request.thread_id, request.message, db, current_user.id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/history/{thread_id}", response_model=ChatHistoryRead)
async def get_chat_history(
    thread_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    thread = await get_thread_by_id(db, current_user.id, thread_id)
    if not thread:
        raise ThreadNotFoundException(thread_id)

    db_path = get_db_path()
    config = {"configurable": {"thread_id": thread_id}}

    async with get_checkpointer_context(db_path) as checkpointer:
        graph_with_memory = get_graph_with_checkpointer(checkpointer, current_user.id)
        state = await graph_with_memory.aget_state(config)

    messages = build_chat_history(state)
    return ChatHistoryRead(thread_id=thread_id, messages=messages)