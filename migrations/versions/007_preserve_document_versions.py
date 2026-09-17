"""Preserve the last active document while a replacement is indexed."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "007_preserve_document_versions"
down_revision = "006_durable_ingestion_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ingestion_jobs",
        sa.Column("previous_document", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ingestion_jobs", "previous_document")
