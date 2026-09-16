"""diet_logs, water_logs, sleep_logs, workout_logs, mood_logs

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-04

"""
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "diet_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("meal_type", sa.String(length=20), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("calories", sa.Integer(), nullable=True),
        sa.Column("protein_grams", sa.Float(), nullable=True),
        sa.Column("logged_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_diet_logs_user_id", "diet_logs", ["user_id"])
    op.create_index("ix_diet_logs_logged_at", "diet_logs", ["logged_at"])

    op.create_table(
        "water_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("amount_ml", sa.Integer(), nullable=False),
        sa.Column("logged_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_water_logs_user_id", "water_logs", ["user_id"])
    op.create_index("ix_water_logs_logged_at", "water_logs", ["logged_at"])

    op.create_table(
        "sleep_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("sleep_date", sa.Date(), nullable=False),
        sa.Column("bedtime", sa.DateTime(timezone=True), nullable=True),
        sa.Column("wake_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("quality", sa.Integer(), nullable=True),
        sa.Column("notes", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_sleep_logs_user_id", "sleep_logs", ["user_id"])
    op.create_index("ix_sleep_logs_sleep_date", "sleep_logs", ["sleep_date"])
    # At most one sleep log per user per night — enforced in the DB, not just
    # in health_service's upsert logic, so a race between two requests for
    # the same night can't create two rows.
    op.create_unique_constraint("uq_sleep_logs_user_id_sleep_date", "sleep_logs", ["user_id", "sleep_date"])

    op.create_table(
        "workout_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("activity_type", sa.String(length=80), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("intensity", sa.String(length=10), nullable=False, server_default="medium"),
        sa.Column("logged_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.String(length=1000), nullable=True),
    )
    op.create_index("ix_workout_logs_user_id", "workout_logs", ["user_id"])
    op.create_index("ix_workout_logs_logged_at", "workout_logs", ["logged_at"])

    op.create_table(
        "mood_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("mood", sa.String(length=20), nullable=False),
        sa.Column("stress_level", sa.Integer(), nullable=True),
        sa.Column("journal_entry", sa.Text(), nullable=True),
        sa.Column("logged_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_mood_logs_user_id", "mood_logs", ["user_id"])
    op.create_index("ix_mood_logs_logged_at", "mood_logs", ["logged_at"])


def downgrade() -> None:
    op.drop_table("mood_logs")
    op.drop_table("workout_logs")
    op.drop_table("sleep_logs")
    op.drop_table("water_logs")
    op.drop_table("diet_logs")
