"""smoking_events

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-13

"""
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "smoking_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("trigger", sa.String(length=200), nullable=False),
        sa.Column("craving_intensity", sa.Integer(), nullable=False),
        sa.Column("stress_level", sa.Integer(), nullable=True),
        sa.Column("context", sa.String(length=500), nullable=True),
        sa.Column("outcome", sa.String(length=20), nullable=False),
        sa.Column("alternative_action", sa.String(length=300), nullable=True),
        sa.Column("reflection_note", sa.Text(), nullable=True),
        sa.Column("notes", sa.String(length=1000), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_smoking_events_user_id", "smoking_events", ["user_id"])
    op.create_index("ix_smoking_events_occurred_at", "smoking_events", ["occurred_at"])


def downgrade() -> None:
    op.drop_table("smoking_events")
