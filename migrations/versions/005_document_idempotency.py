"""Prevent duplicate document creation on client retries."""

import sqlalchemy as sa
from alembic import op

revision = "005_document_idempotency"
down_revision = "004_data_integrity_constraints"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("idempotency_key", sa.String(length=128), nullable=True))
    op.create_unique_constraint(
        "uq_documents_org_idempotency_key", "documents", ["organization_id", "idempotency_key"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_documents_org_idempotency_key", "documents", type_="unique")
    op.drop_column("documents", "idempotency_key")
