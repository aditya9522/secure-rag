"""Persist ingestion payloads and worker leases for crash recovery."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "006_durable_ingestion_jobs"
down_revision = "005_document_idempotency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ingestion_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requested_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.String(length=256), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=True),
        sa.Column("classification", sa.String(length=20), nullable=False),
        sa.Column("allowed_groups", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_uri", sa.String(length=2048), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", name="uq_ingestion_jobs_document"),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name="ck_ingestion_job_status",
        ),
        sa.CheckConstraint("attempts >= 0", name="ck_ingestion_job_attempts_nonnegative"),
    )
    op.create_index("ix_ingestion_jobs_organization_id", "ingestion_jobs", ["organization_id"])
    op.create_index(
        "ix_ingestion_jobs_claim",
        "ingestion_jobs",
        ["status", "available_at", "locked_until"],
    )
    op.execute("ALTER TABLE ingestion_jobs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE ingestion_jobs FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY ingestion_jobs_tenant_isolation ON ingestion_jobs
        USING (
            organization_id::text = current_setting('app.current_organization_id', true)
            OR current_setting('app.is_system_admin', true) = 'true'
        )
        WITH CHECK (
            organization_id::text = current_setting('app.current_organization_id', true)
            OR current_setting('app.is_system_admin', true) = 'true'
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS ingestion_jobs_tenant_isolation ON ingestion_jobs")
    op.execute("ALTER TABLE ingestion_jobs NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE ingestion_jobs DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_ingestion_jobs_claim", table_name="ingestion_jobs")
    op.drop_index("ix_ingestion_jobs_organization_id", table_name="ingestion_jobs")
    op.drop_table("ingestion_jobs")
