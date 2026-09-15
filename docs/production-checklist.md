# Production release checklist

The application enforces the important data-boundary controls in code, but a production release also needs deployment-level controls. Complete this checklist for every environment.

## Identity and access

- Use a unique, randomly generated `JWT_SECRET` from a secret manager.
- Keep `ALLOW_LOCAL_DEV_TOKENS=false`; the development token route is loopback-only and must never be exposed.
- Put the API behind TLS and an authenticated reverse proxy/WAF.
- Configure OIDC/JWKS or an approved MFA-capable identity provider if password authentication is not the chosen enterprise control.
- Bootstrap the first system administrator only from a trusted shell.
- Test direct API access for suspended users, revoked memberships, cross-organization IDs, and non-admin users.

## Data and providers

- Use a dedicated least-privilege PostgreSQL role and database per environment.
- Store `DATABASE_URL`, OpenAI, Pinecone, and Redis credentials in a secret manager.
- Run `alembic upgrade head` as an explicit deployment step and record the migration revision.
- Deploy migrations 003–006 before enabling the API; they enforce row-level tenant isolation,
  data-integrity checks, tenant-scoped document idempotency, and durable ingestion-job recovery.
- Configure a shared Redis-compatible `RATE_LIMIT_STORAGE_URI` for more than one API worker/instance.
- Create the Pinecone index with deletion protection enabled and verify namespace/metadata filters.
- Verify PostgreSQL backups, restore drills, Pinecone recovery, and retention/deletion procedures.

## Runtime and network

- Set `ENVIRONMENT=production`, explicit `CORS_ALLOWED_ORIGINS`, and a production-only host allowlist at the ingress layer.
- Expose only the TLS reverse proxy; keep PostgreSQL, Redis, and provider management endpoints private.
- Set CPU/memory limits for API workers and isolate document parsing/provider work from the request process when throughput requires it.
- Deploy the database-backed ingestion worker (`python scripts/ingestion_worker.py`)
  as a separately scaled process. It uses leases, idempotency keys, bounded retry
  budgets, terminal failure state, and readiness reconciliation.
- Configure centralized logs and alerts for authentication failures, refresh-token reuse, denied access, ingestion failures, provider outages, and readiness failures.
- Propagate `X-Request-ID` into ingress and log aggregation for safe incident correlation.

## Release validation

- Run backend tests, Ruff, frontend type/build/lint, migration upgrade/downgrade validation, dependency scanning, and secret scanning in CI.
- Run tenant-boundary and authorization acceptance tests against a disposable PostgreSQL/Pinecone environment.
- Confirm `/healthz` and `/readyz` behavior from the load balancer’s network location.
- Verify the frontend uses only the public API base URL and contains no provider or database secret.
- Perform a focused OWASP review and an authorized penetration test before handling regulated or high-impact data.
