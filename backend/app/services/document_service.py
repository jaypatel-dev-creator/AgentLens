from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.db.models import Document
from app.rag.ingestor import ingest_file, IngestResult
from app.rag.store import get_store
from app.core.logging import get_logger
from app.core.exceptions import RAGException, ForbiddenException

logger = get_logger(__name__)


async def ingest_and_persist(
    db: AsyncSession,
    user_id: str,
    content: bytes,
    filename: str,
    content_type: str,
) -> IngestResult:
    try:
        result = await ingest_file(
            content=content,
            filename=filename,
            content_type=content_type,
            user_id=user_id,  # injected into chunk metadata for per-user vector filtering
        )

        if not result.already_existed:
            doc = Document(
                user_id=user_id,
                sha256=result.sha256,
                filename=result.filename,
                chunk_count=result.chunk_count,
            )
            db.add(doc)
            await db.flush()
            logger.info(f"Document persisted — user: {user_id} file: {filename} ({result.sha256[:8]}...)")

        return result

    except RAGException:
        raise
    except Exception as e:
        raise RAGException(f"Failed to ingest '{filename}': {str(e)}")


async def list_documents(db: AsyncSession, user_id: str) -> list[Document]:
    try:
        result = await db.execute(
            select(Document)
            .where(Document.user_id == user_id)
            .order_by(Document.uploaded_at.desc())
        )
        return list(result.scalars().all())
    except Exception as e:
        raise RAGException(f"Failed to list documents: {str(e)}")


async def get_document_by_sha256(db: AsyncSession, user_id: str, sha256: str) -> Document | None:
    try:
        result = await db.execute(
            select(Document).where(
                Document.user_id == user_id,
                Document.sha256 == sha256,
            )
        )
        return result.scalar_one_or_none()
    except Exception as e:
        raise RAGException(f"Failed to fetch document '{sha256[:8]}...': {str(e)}")


async def delete_document(db: AsyncSession, user_id: str, sha256: str) -> None:
    try:
        # Verify ownership before deletion
        doc = await get_document_by_sha256(db, user_id, sha256)
        if doc is None:
            # Could be not found OR wrong owner — fetch without user filter to distinguish
            result = await db.execute(select(Document).where(Document.sha256 == sha256))
            exists = result.scalar_one_or_none()
            if exists is not None:
                raise ForbiddenException()
            # Genuinely not found — let caller handle None / 404
            return

        store = get_store()
        store.delete_by_sha256(sha256, user_id=user_id)  # scoped deletion in vector store
        await db.execute(
            delete(Document).where(
                Document.user_id == user_id,
                Document.sha256 == sha256,
            )
        )
        await db.flush()
        logger.info(f"Document deleted — user: {user_id} sha256: {sha256[:8]}...")
    except (RAGException, ForbiddenException):
        raise
    except Exception as e:
        raise RAGException(f"Failed to delete document '{sha256[:8]}...': {str(e)}")