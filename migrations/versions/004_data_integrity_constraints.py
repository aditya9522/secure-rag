"""Enforce enumerated lifecycle and authorization values in PostgreSQL."""

from alembic import op

revision = "004_data_integrity_constraints"
down_revision = "003_row_level_security"
branch_labels = None
depends_on = None


CONSTRAINTS = {
    "memberships": (
        ("ck_membership_role", "role IN ('owner', 'admin', 'member')"),
        ("ck_membership_status", "status IN ('active', 'invited', 'suspended')"),
        (
            "ck_membership_classification",
            "classification_max IN ('public', 'internal', 'confidential', 'restricted')",
        ),
    ),
    "invitations": (
        ("ck_invitation_role", "role IN ('admin', 'member')"),
        (
            "ck_invitation_classification",
            "classification_max IN ('public', 'internal', 'confidential', 'restricted')",
        ),
    ),
    "documents": (
        (
            "ck_document_classification",
            "classification IN ('public', 'internal', 'confidential', 'restricted')",
        ),
        ("ck_document_status", "status IN ('indexing', 'active', 'revoked', 'failed')"),
        ("ck_document_version_positive", "version >= 1"),
        ("ck_document_chunks_nonnegative", "chunks_indexed >= 0"),
    ),
    "chat_messages": (
        ("ck_chat_message_role", "role IN ('user', 'assistant')"),
        ("ck_chat_message_mode", "mode IN ('grounded', 'conversational', 'refused')"),
    ),
}


def upgrade() -> None:
    for table, constraints in CONSTRAINTS.items():
        for name, expression in constraints:
            op.create_check_constraint(name, table, expression)


def downgrade() -> None:
    for table, constraints in reversed(tuple(CONSTRAINTS.items())):
        for name, _ in reversed(constraints):
            op.drop_constraint(name, table, type_="check")
