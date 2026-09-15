# Secure RAG — OpenAI + Pinecone

A production-oriented reference implementation of a secure multi-tenant RAG service. It demonstrates defense-in-depth safeguards rather than relying on a single prompt.

This repository contains the complete application in one tree: a FastAPI backend in
`app/` and a React + TypeScript frontend in `frontend/`. The frontend keeps access
tokens in memory and talks to the backend through the configured API base URL.

## Included safeguards

- JWT authentication and tenant-aware authorization.
- PostgreSQL source of truth for accounts, organizations, memberships, refresh sessions, documents, conversations, and audit events.
- Pinecone namespace isolation per tenant.
- Pinecone metadata ACL filters (groups/users/classification/document status).
- Retrieval score threshold, bounded top-k, simple lexical reranking, and duplicate removal.
- Retrieved content is explicitly treated as untrusted data; document instructions are never considered executable instructions.
- Prompt-injection heuristics on user input and retrieved chunks.
- OpenAI moderation on user input and generated output.
- PII + secret detection/redaction before model context and on output.
- Grounding check: answer only from retrieved evidence; refuse when evidence is insufficient.
- Explicit conversational intent path: greetings and small talk are generated without retrieval or organization facts.
- Citation enforcement with document IDs/titles and chunk IDs.
- Audit events that exclude raw secret-bearing headers and redact common sensitive values.
- Rate limiting.
- Bounded streaming uploads and a shared rate-limit-store option for horizontally scaled workers.
- Request/body size limits and upload type checks.
- Document ingestion provenance, version, owner, groups, classification, and active status.
- Access grants are limited to the principal's own groups unless the trusted `can_manage_access` claim is present.
- Tool/action security boundary is modeled in `app/security/action_policy.py` for future agent tools.
- Security-focused unit tests.
- Dockerfile + docker-compose for local development.

## Architecture

The backend is organized into domain routers under `app/api/`, reusable domain services under
`app/services/`, shared runtime infrastructure under `app/core/`, and isolated provider/security
adapters. [`docs/backend-architecture.md`](/home/adi/Projects/rag-guardrails/docs/backend-architecture.md)
describes the module boundaries.

The repository layout is:

```text
app/                 FastAPI API and domain services
frontend/            React + TypeScript web application
migrations/          Alembic database migrations
scripts/             Operational and ingestion-worker commands
docs/                API, security, architecture, and deployment guidance
tests/               Backend unit and security tests
```

```text
Client
  -> OIDC/password AuthN + PostgreSQL membership lookup
  -> Input policy + moderation + injection checks
  -> Tenant/ACL context
  -> Intent boundary (conversation vs. organization knowledge)
  -> OpenAI embeddings (knowledge questions only)
  -> Pinecone namespace + metadata ACL filter
  -> Score threshold + rerank + duplicate removal
  -> Grounded OpenAI response (optionally streamed over SSE)
  -> Output moderation + PII/secret redaction + citation validation
  -> Audit event
```

## Why this design

Authorization is enforced before the LLM sees data. The LLM is never used as the security boundary. Each tenant gets a dedicated Pinecone namespace, and each vector also stores ACL metadata for defense-in-depth filtering.

## Prerequisites

- Python 3.11+
- OpenAI API key
- Pinecone API key

The implementation uses Pinecone serverless indexes with 1536 dimensions and cosine similarity to match OpenAI `text-embedding-3-small`. Pinecone documents namespaces as the tenant isolation mechanism, and metadata filters can be used to constrain query results.

## PostgreSQL setup

Start PostgreSQL locally with `docker compose up -d db`, then apply the schema with `alembic upgrade head`. Create the first administrator account through an approved bootstrap process, then use the authenticated admin console to create organizations. Organization owners receive their credentials through a secure channel; public signup is not available.

## Quick start

Install the backend dependencies and configure local secrets:

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest -q
uvicorn app.main:app --reload
```

Open `http://localhost:8000/docs`.

In a second terminal, start the frontend:

```bash
cd frontend
cp .env.example .env
npm ci
npm run dev
```

Open the Vite URL shown in the terminal, normally `http://localhost:5173`. Set
`CORS_ALLOWED_ORIGINS=http://localhost:5173` in the backend `.env` when using the
frontend from a separate origin. The frontend build and lint checks can be run from
the repository root with `make frontend-build` and `make frontend-lint`.

For a reproducible container build, the production image installs the committed
`requirements.lock` file. Refresh it deliberately when upgrading dependencies;
do not rely on an unconstrained rebuild.

The Compose file runs PostgreSQL, the API, and the ingestion worker. The frontend
is a separately built static application so it can be deployed to the hosting
platform appropriate for the environment; point it at the API with
`VITE_API_BASE_URL` at build time.

The lock file is generated with platform-specific artifact hashes. Regenerate it
only after reviewing dependency changes:

```bash
uv pip compile pyproject.toml --all-extras --generate-hashes \
  --constraint requirements.lock --python-platform x86_64-unknown-linux-gnu \
  --output-file /tmp/requirements.lock
```

The API can process an upload immediately, while the PostgreSQL-backed
`ingestion-worker` retries crashed or transient jobs. In a production deployment,
run that worker as a separately scaled service and apply migrations through the
release process before starting it.

## Configure Pinecone

Create the index with:

```bash
python scripts/create_index.py
```

This is idempotent: it creates the index when it does not exist and otherwise leaves it alone.

## Local development authentication

For local use only, `ALLOW_LOCAL_DEV_TOKENS=true` enables the `/auth/dev-token` endpoint. Never enable this in production. Use your real IdP/JWT issuer in production and disable this endpoint.

The development issuer is loopback-only and only signs claims; it does not
create users, organizations, or memberships. The UUIDs must already exist in
the local database, and the resulting identity is still checked against active
membership on every protected request. Example:

```bash
curl -X POST http://localhost:8000/auth/dev-token \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"<local-user-uuid>","tenant_id":"<local-organization-uuid>","groups":["engineering"],"classification_max":"confidential"}'
```

Then use the returned bearer token for ingestion/query calls.

## Ingest

```bash
curl -X POST http://localhost:8000/v1/documents \
  -H "Authorization: Bearer $TOKEN" \
  -F 'file=@sample.txt' \
  -F 'classification=internal' \
  -F 'allowed_groups=engineering' \
  -F 'source_uri=https://example.internal/docs/123'
```

The document is chunked, embedded with OpenAI, and upserted into the tenant namespace. Each vector has security metadata including tenant, allowed groups, owner, classification, active status, and provenance.

## Query

```bash
curl -X POST http://localhost:8000/v1/query \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"query":"What is our deployment process?"}'
```

The response contains the answer and citations. When there is not enough authorized evidence, the service returns a grounded refusal rather than inventing an answer.

## Production hardening checklist

This repository intentionally stays deployable without requiring a specific cloud provider. Before production, integrate:

1. An external OIDC/JWKS issuer rather than the local token endpoint.
2. A WAF/API gateway and network policies.
3. A Redis-compatible `RATE_LIMIT_STORAGE_URI` for multi-worker or multi-instance deployments; the in-memory default is development-only.
4. Secret manager / KMS rather than `.env` secrets.
5. Structured centralized audit storage with retention controls.
6. A managed DLP/PII detector if your regulatory requirements demand higher recall.
7. Key rotation and separate OpenAI/Pinecone credentials per environment.
8. Pinecone index/namespace backup and deletion workflows.
9. Human approval before any future high-impact write tool.
10. Red-team evaluation against prompt injection, retrieval poisoning, ACL bypass, data exfiltration, and cross-tenant leakage.

## Threat model

See `docs/threat-model.md` and `docs/security-controls.md`.

The deployable release checklist is in `docs/production-checklist.md`; local PostgreSQL setup is in `docs/postgresql-local.md`.
