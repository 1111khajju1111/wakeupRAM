"""conversation_language_override

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Lets a single conversation (currently: voice calls — see
    # voice_call_service.start_call) use a language different from the
    # user's standing Profile.preferred_language for that conversation only.
    # NULL for ordinary text chat, which keeps following the profile default
    # exactly as before this migration.
    op.add_column("conversations", sa.Column("language_override", sa.String(length=10), nullable=True))


def downgrade() -> None:
    op.drop_column("conversations", "language_override")
