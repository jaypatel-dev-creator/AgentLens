from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime, Boolean, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# User model — auth anchor, every other table FKs to this
class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)           # uuid, generated in auth_service
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


# Thread model — scoped to user
class Thread(Base):
    __tablename__ = "threads"

    id: Mapped[str] = mapped_column(String, primary_key=True)           # uuid generated in thread_service
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String, default="New Chat")
    is_titled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


# UserProfile model — LTM entries, scoped to user
# PK changed from (key) → composite (user_id, key)
# so the same key e.g. "name" can exist for multiple users independently
class UserProfile(Base):
    __tablename__ = "user_profile"

    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, primary_key=True
    )
    key: Mapped[str] = mapped_column(String, primary_key=True)          # composite PK: (user_id, key)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


# Document model — tracks uploaded files for RAG, scoped to user
# PK changed from (sha256) → composite (user_id, sha256)
# so two users uploading the same file are deduped independently per user
class Document(Base):
    __tablename__ = "documents"

    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, primary_key=True
    )
    sha256: Mapped[str] = mapped_column(String, primary_key=True)       # composite PK: (user_id, sha256)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )