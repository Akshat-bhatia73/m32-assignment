"""add messages.data_parts

Persists structured stream parts (email draft / calendar proposal cards) so a reloaded turn
re-renders them as cards instead of only the plain-text twin.

Revision ID: 0005_message_data_parts
Revises: 0004_organizations
Create Date: 2026-06-18
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005_message_data_parts"
down_revision: str | None = "0004_organizations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column("data_parts", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("messages", "data_parts")
