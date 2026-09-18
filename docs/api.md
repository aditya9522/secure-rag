# API surface

- `GET /healthz` — liveness.
- `GET /readyz` — readiness; returns 503 until providers and required authentication configuration are available.
- `POST /auth/dev-token` — local-development token issuer, disabled by default and never intended for production.
- `POST /v1/admin/organizations` — create an organization and owner account; requires an authenticated system administrator.
- `POST /auth/login` — authenticate with a password and issue a short-lived access token plus HttpOnly refresh cookie.
- `POST /auth/refresh` / `POST /auth/logout` — rotate or revoke refresh sessions; the selected organization is persisted in the refresh session.
- `POST /auth/accept-invite` — accept a one-time organization invitation.
- `GET /v1/me` / `PATCH /v1/me` — read or update the current user profile; password changes revoke refresh sessions.
- `GET /v1/notifications` — tenant-scoped safe activity summaries for the workspace notification center.
- `POST /v1/organizations/switch` — select the current organization context from the user's active memberships.
- `POST /v1/documents` — authenticated document ingestion.
  Clients may send a tenant-scoped `Idempotency-Key` (up to 128 characters) to safely
  retry an upload; active requests replay the original result and in-progress requests
  return `409`.
- `GET /v1/documents` / `DELETE /v1/documents/{document_id}` — list or revoke organization documents.
  Document listing accepts bounded `limit` (1–100) and `offset` parameters.
- `GET /v1/organizations/members` / `PATCH /v1/organizations/members/{member_id}` — admin membership controls.
- `GET /v1/conversations` / `GET /v1/conversations/{conversation_id}/messages` — tenant-scoped chat history;
  both endpoints accept bounded `limit` (1–100) and `offset` parameters.
- `GET /v1/admin/metrics` / `GET /v1/admin/audit` — system-admin monitoring endpoints.
- `POST /v1/feedback` / `GET /v1/feedback/mine` — submit feedback and view only the current user's
  feedback in the active organization. Feedback is rate-limited, tenant-scoped, and stores a
  reporter snapshot so the platform team can triage it safely.
- `GET /v1/admin/feedback` / `PATCH /v1/admin/feedback/{feedback_id}` — platform-admin-only
  feedback queue and review updates across organizations. The endpoint supports bounded
  pagination and status/category filters; organization members cannot read this queue.
- `POST /v1/query` — authenticated, tenant-isolated, ACL-filtered RAG query. When no
  `conversation_id` is supplied, the request creates its conversation and returns the
  resulting `conversation_id` so clients do not need a separate create call.
- `POST /v1/query/stream` — the same authenticated query contract over server-sent events;
  it emits response deltas followed by the validated final response and conversation ID.

When the frontend is served from a separate origin, configure `CORS_ALLOWED_ORIGINS` with an explicit comma-separated HTTP(S) allowlist. Wildcard origins are rejected.

Run `alembic upgrade head` before starting the API. The API does not create tables implicitly at startup; PostgreSQL migrations are the deployment gate.

## Query modes

The query endpoint has three explicit response modes:

- `grounded` — the answer used authorized evidence and includes validated citations.
- `conversational` — the request was small talk or a general capability question. It is generated without retrieval, citations, or organization facts.
- `refused` — the service could not safely answer, including when authorized evidence is insufficient.

Document lifecycle state is authoritative in PostgreSQL. Uploads are persisted as
database-backed ingestion jobs before provider work begins; the API may process the
job immediately, and the worker can reclaim an expired lease after a crash. Pinecone
vectors are staged
inactive during ingestion, and query results are discarded unless their document is
currently `active` in PostgreSQL. Revocation records the deny state before attempting
vector cleanup, so provider failures fail closed. Request-bound ingestion has a hard
provider deadline; readiness reconciliation marks abandoned `indexing` records as
failed and attempts provider cleanup. High-volume deployments should move ingestion
to a durable external worker queue before increasing upload concurrency.

PostgreSQL row-level security is enabled for documents, conversations, chat messages,
audit events, and feedback. Authenticated request dependencies set transaction-local tenant
context, while system-admin operations use an explicitly verified bypass context.

This keeps natural chat useful without weakening the rule that organization facts must come from authorized sources.

OpenAPI docs are available at `/docs` outside production; production disables interactive API documentation.
