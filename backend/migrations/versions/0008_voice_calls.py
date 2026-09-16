"""voice_calls

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-13

"""
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "voice_calls",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("language", sa.String(length=10), nullable=False, server_default="en"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="in_progress"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("recording_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("recording_local_reference", sa.String(length=500), nullable=True),
        sa.Column("recording_duration_seconds", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_voice_calls_user_id", "voice_calls", ["user_id"])
    op.create_index("ix_voice_calls_conversation_id", "voice_calls", ["conversation_id"])
    op.create_index("ix_voice_calls_started_at", "voice_calls", ["started_at"])


def downgrade() -> None:
    op.drop_table("voice_calls")
