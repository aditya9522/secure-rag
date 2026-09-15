# Build status

- Python AST/syntax validation: PASSED.
- Dependency-backed pytest execution: PASSED in the repository virtual environment (see the latest CI run for the count).
- Ruff lint and formatting checks: PASSED.
- Frontend TypeScript/Vite production build and oxlint: PASSED.
- Alembic PostgreSQL upgrade and downgrade SQL generation: PASSED.
- Refresh-session tenant continuity, staged vector visibility, parser signatures, and production configuration guards have regression coverage.
- Partial vector writes are cleaned up, database lifecycle state filters stale provider matches, and query creation is single-request with a returned conversation ID.
- Provider work has bounded deadlines, streaming has bounded backpressure and disconnect cleanup, and abandoned indexing records fail closed during readiness reconciliation.
- Sensitive tenant tables have PostgreSQL row-level-security policies, and API list endpoints enforce bounded pagination.
- The authenticated UI now has functional notifications, help center, chat controls, settings sections, integration readiness, organization-switch errors, and explicit data-load failures.
- No real credentials are committed. Local PostgreSQL provisioning is documented in [`docs/postgresql-local.md`](/home/adi/Projects/rag-guardrails/docs/postgresql-local.md).
