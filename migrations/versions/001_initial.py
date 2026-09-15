"""Initial multi-tenant application schema."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def uuid_type():
    return postgresql.UUID(as_uuid=True)


def json_type():
    return postgresql.JSONB()


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", uuid_type(), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("full_name", sa.String(160), nullable=False),
        sa.Column("password_hash", sa.String(512), nullable=False),
        sa.Column("is_system_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table(
        "organizations",
        sa.Column("id", uuid_type(), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("created_by", uuid_type(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=True)
    op.create_table(
        "memberships",
        sa.Column("id", uuid_type(), primary_key=True),
        sa.Column(
            "user_id", uuid_type(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "organization_id",
            uuid_type(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("groups", json_type(), nullable=False),
        sa.Column("classification_max", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "organization_id", name="uq_membership_user_org"),
    )
    op.create_index("ix_memberships_user_id", "memberships", ["user_id"])
    op.create_index("ix_memberships_organization_id", "memberships", ["organization_id"])
    op.create_table(
        "refresh_sessions",
        sa.Column("id", uuid_type(), primary_key=True),
        sa.Column(
            "user_id", uuid_type(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("token_hash", sa.String(128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_refresh_sessions_token_hash", "refresh_sessions", ["token_hash"], unique=True
    )
    op.create_index("ix_refresh_sessions_user_id", "refresh_sessions", ["user_id"])
    op.create_index("ix_refresh_sessions_expires_at", "refresh_sessions", ["expires_at"])
    op.create_table(
        "invitations",
        sa.Column("id", uuid_type(), primary_key=True),
        sa.Column(
            "organization_id",
            uuid_type(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("full_name", sa.String(160), nullable=False),
        sa.Column("token_hash", sa.String(128), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("groups", json_type(), nullable=False),
        sa.Column("classification_max", sa.String(20), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_invitations_token_hash", "invitations", ["token_hash"], unique=True)
    op.create_index("ix_invitations_organization_id", "invitations", ["organization_id"])
    op.create_index("ix_invitations_expires_at", "invitations", ["expires_at"])
    op.create_index("ix_invitations_org_email", "invitations", ["organization_id", "email"])
    op.create_table(
        "documents",
        sa.Column("id", uuid_type(), primary_key=True),
        sa.Column(
            "organization_id",
            uuid_type(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("owner_user_id", uuid_type(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("classification", sa.String(20), nullable=False),
        sa.Column("allowed_groups", json_type(), nullable=False),
        sa.Column("source_uri", sa.String(2048)),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("chunks_indexed", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_documents_organization_id", "documents", ["organization_id"])
    op.create_index("ix_documents_org_status", "documents", ["organization_id", "status"])
    op.create_table(
        "conversations",
        sa.Column("id", uuid_type(), primary_key=True),
        sa.Column(
            "organization_id",
            uuid_type(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id", uuid_type(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_conversations_organization_id", "conversations", ["organization_id"])
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])
    op.create_index("ix_conversations_org_user", "conversations", ["organization_id", "user_id"])
    op.create_table(
        "chat_messages",
        sa.Column("id", uuid_type(), primary_key=True),
        sa.Column(
            "conversation_id",
            uuid_type(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("citations", json_type(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_chat_messages_conversation_id", "chat_messages", ["conversation_id"])
    op.create_table(
        "audit_events",
        sa.Column("id", uuid_type(), primary_key=True),
        sa.Column(
            "organization_id", uuid_type(), sa.ForeignKey("organizations.id", ondelete="SET NULL")
        ),
        sa.Column("user_id", uuid_type(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("metadata", json_type(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_events_organization_id", "audit_events", ["organization_id"])
    op.create_index("ix_audit_events_event_type", "audit_events", ["event_type"])
    op.create_index("ix_audit_org_created", "audit_events", ["organization_id", "created_at"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("chat_messages")
    op.drop_table("conversations")
    op.drop_table("documents")
    op.drop_table("invitations")
    op.drop_table("refresh_sessions")
    op.drop_table("memberships")
    op.drop_table("organizations")
    op.drop_table("users")
