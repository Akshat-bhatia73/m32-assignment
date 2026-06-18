"""organizations, memberships, invitations + org_id on sessions/action_items

Adds team workspaces. Backfills one org per existing user (owner membership) and scopes their
existing sessions/action items into it.

Revision ID: 0004_organizations
Revises: 0003_message_artifacts
Create Date: 2026-06-18
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_organizations"
down_revision: str | None = "0003_message_artifacts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False, server_default="Workspace"),
        sa.Column(
            "owner_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
    )
    op.create_index("ix_organizations_owner_user_id", "organizations", ["owner_user_id"])

    op.create_table(
        "memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="member"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.UniqueConstraint("org_id", "user_id", name="uq_membership_org_user"),
    )
    op.create_index("ix_memberships_org_id", "memberships", ["org_id"])
    op.create_index("ix_memberships_user_id", "memberships", ["user_id"])

    op.create_table(
        "invitations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=True),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="member"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column(
            "invited_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.UniqueConstraint("token", name="uq_invitation_token"),
    )
    op.create_index("ix_invitations_org_id", "invitations", ["org_id"])
    op.create_index("ix_invitations_email", "invitations", ["email"])

    op.add_column(
        "chat_sessions",
        sa.Column("org_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True),
    )
    op.create_index("ix_chat_sessions_org_id", "chat_sessions", ["org_id"])
    op.add_column(
        "action_items",
        sa.Column("org_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True),
    )
    op.create_index("ix_action_items_org_id", "action_items", ["org_id"])

    # --- Backfill: one org per existing user, then scope their data into it. ---
    op.execute(
        """
        INSERT INTO organizations (id, name, owner_user_id, created_at)
        SELECT gen_random_uuid(),
               COALESCE(NULLIF(u.name, ''), split_part(u.email, '@', 1)) || '''s workspace',
               u.id, now()
        FROM users u
        """
    )
    op.execute(
        """
        INSERT INTO memberships (id, org_id, user_id, role, created_at)
        SELECT gen_random_uuid(), o.id, o.owner_user_id, 'owner', now()
        FROM organizations o
        """
    )
    op.execute(
        """
        UPDATE chat_sessions cs SET org_id = o.id
        FROM organizations o WHERE o.owner_user_id = cs.user_id
        """
    )
    op.execute(
        """
        UPDATE action_items ai SET org_id = o.id
        FROM organizations o WHERE o.owner_user_id = ai.user_id
        """
    )


def downgrade() -> None:
    op.drop_index("ix_action_items_org_id", table_name="action_items")
    op.drop_column("action_items", "org_id")
    op.drop_index("ix_chat_sessions_org_id", table_name="chat_sessions")
    op.drop_column("chat_sessions", "org_id")
    op.drop_table("invitations")
    op.drop_table("memberships")
    op.drop_table("organizations")
