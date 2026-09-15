"""Persist the selected organization in refresh sessions."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "002_refresh_session_organization"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "refresh_sessions",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.execute(
        sa.text(
            """
            UPDATE refresh_sessions AS sessions
            SET organization_id = memberships.organization_id
            FROM memberships
            WHERE memberships.user_id = sessions.user_id
              AND memberships.status = 'active'
              AND memberships.id = (
                  SELECT candidate.id
                  FROM memberships AS candidate
                  WHERE candidate.user_id = sessions.user_id
                    AND candidate.status = 'active'
                  ORDER BY candidate.created_at
                  LIMIT 1
              )
            """
        )
    )
    # A session without a valid tenant cannot be safely refreshed. Revoking it
    # is safer than inventing an organization context during migration.
    op.execute(sa.text("DELETE FROM refresh_sessions WHERE organization_id IS NULL"))
    op.alter_column("refresh_sessions", "organization_id", nullable=False)
    op.create_foreign_key(
        "fk_refresh_sessions_organization_id",
        "refresh_sessions",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_refresh_sessions_organization_id", "refresh_sessions", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_refresh_sessions_organization_id", table_name="refresh_sessions")
    op.drop_constraint(
        "fk_refresh_sessions_organization_id", "refresh_sessions", type_="foreignkey"
    )
    op.drop_column("refresh_sessions", "organization_id")
