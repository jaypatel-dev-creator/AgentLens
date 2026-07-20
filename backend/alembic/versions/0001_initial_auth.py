"""initial auth — create all tables from scratch with user_id scoping

Revision ID: 0001
Revises:
Create Date: 2025-07-15
"""
from alembic import op
import sqlalchemy as sa

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. users — auth anchor, must be created first (other tables FK to it)
    op.create_table(
        'users',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
    )

    # 2. threads — scoped to user
    op.create_table(
        'threads',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=True),
        sa.Column('title', sa.String(), nullable=True),
        sa.Column('is_titled', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_threads_user_id', 'threads', ['user_id'])

    # 3. user_profile — composite PK (user_id, key)
    op.create_table(
        'user_profile',
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('key', sa.String(), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id', 'key'),
    )

    # 4. documents — composite PK (user_id, sha256)
    op.create_table(
        'documents',
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('sha256', sa.String(), nullable=False),
        sa.Column('filename', sa.String(), nullable=False),
        sa.Column('chunk_count', sa.Integer(), nullable=False),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id', 'sha256'),
    )


def downgrade() -> None:
    op.drop_table('documents')
    op.drop_table('user_profile')
    op.drop_index('ix_threads_user_id', 'threads')
    op.drop_table('threads')
    op.drop_table('users')