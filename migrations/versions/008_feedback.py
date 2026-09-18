"""Add tenant-safe user feedback and platform-admin review queue."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "008_feedback"
down_revision = "007_preserve_document_versions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reporter_name", sa.String(length=160), nullable=False),
        sa.Column("reporter_email", sa.String(length=320), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("subject", sa.String(length=120), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("source_page", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "category IN ('bug', 'feature_request', 'answer_quality', 'access', 'general')",
            name="ck_feedback_category",
        ),
        sa.CheckConstraint("rating IS NULL OR rating BETWEEN 1 AND 5", name="ck_feedback_rating"),
        sa.CheckConstraint(
            "status IN ('new', 'in_review', 'resolved', 'dismissed')",
            name="ck_feedback_status",
        ),
        sa.CheckConstraint(
            "priority IN ('low', 'normal', 'high')",
            name="ck_feedback_priority",
        ),
    )
    op.create_index("ix_feedback_organization_id", "feedback", ["organization_id"])
    op.create_index("ix_feedback_user_id", "feedback", ["user_id"])
    op.create_index("ix_feedback_org_created", "feedback", ["organization_id", "created_at"])
    op.create_index("ix_feedback_status_created", "feedback", ["status", "created_at"])
    op.execute("ALTER TABLE feedback ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE feedback FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY feedback_tenant_isolation ON feedback
        USING (
            current_setting('app.is_system_admin', true) = 'true'
            OR (
                organization_id::text = current_setting('app.current_organization_id', true)
                AND user_id::text = current_setting('app.current_user_id', true)
            )
        )
        WITH CHECK (
            current_setting('app.is_system_admin', true) = 'true'
            OR (
                organization_id::text = current_setting('app.current_organization_id', true)
                AND user_id::text = current_setting('app.current_user_id', true)
            )
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS feedback_tenant_isolation ON feedback")
    op.execute("ALTER TABLE feedback NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE feedback DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_feedback_status_created", table_name="feedback")
    op.drop_index("ix_feedback_org_created", table_name="feedback")
    op.drop_index("ix_feedback_user_id", table_name="feedback")
    op.drop_index("ix_feedback_organization_id", table_name="feedback")
    op.drop_table("feedback")
