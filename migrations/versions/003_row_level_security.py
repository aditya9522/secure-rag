"""Add database-enforced tenant isolation for sensitive records."""

from alembic import op

revision = "003_row_level_security"
down_revision = "002_refresh_session_organization"
branch_labels = None
depends_on = None


_TENANT_POLICY = """
    organization_id::text = current_setting('app.current_organization_id', true)
    OR current_setting('app.is_system_admin', true) = 'true'
"""


def upgrade() -> None:
    for table in ("documents", "conversations", "audit_events"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table}_tenant_isolation ON {table}
            USING ({_TENANT_POLICY})
            WITH CHECK ({_TENANT_POLICY})
            """
        )

    op.execute("ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE chat_messages FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY chat_messages_tenant_isolation ON chat_messages
        USING (
            current_setting('app.is_system_admin', true) = 'true'
            OR EXISTS (
                SELECT 1 FROM conversations
                WHERE conversations.id = chat_messages.conversation_id
                  AND {_TENANT_POLICY}
            )
        )
        WITH CHECK (
            current_setting('app.is_system_admin', true) = 'true'
            OR EXISTS (
                SELECT 1 FROM conversations
                WHERE conversations.id = chat_messages.conversation_id
                  AND {_TENANT_POLICY}
            )
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS chat_messages_tenant_isolation ON chat_messages")
    op.execute("ALTER TABLE chat_messages NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE chat_messages DISABLE ROW LEVEL SECURITY")
    for table in ("documents", "conversations", "audit_events"):
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
