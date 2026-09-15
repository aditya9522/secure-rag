# Backend architecture

The FastAPI application is composed from small, domain-focused modules:

```text
app/
├── main.py                    # app factory, middleware, router registration
├── api/
│   ├── dependencies.py        # authentication and authorization dependencies
│   ├── auth.py                # login, invitation acceptance, refresh, logout
│   ├── profile.py             # current-user profile and notifications
│   ├── organizations.py       # organization switching and membership controls
│   ├── documents.py           # knowledge-source lifecycle endpoints
│   ├── conversations.py       # conversation history endpoints
│   ├── query.py               # RAG query and SSE streaming endpoints
│   ├── admin.py               # platform-admin monitoring and provisioning
│   └── health.py              # liveness, readiness, and local dev token
├── core/
│   └── runtime.py             # shared limiter, provider instances, bounded thread offload
├── services/
│   ├── auth_service.py        # authentication and organization domain operations
│   ├── chat_service.py        # conversation persistence
│   └── document_service.py    # document lifecycle persistence helpers
├── providers/                 # OpenAI and Pinecone adapters
├── security/                  # JWT, password, policy, and ACL enforcement
└── db_models.py               # SQLAlchemy persistence models
```

## Module boundaries

- `main.py` only composes the application. New endpoints belong in a domain router under `api/`.
- Router functions translate HTTP input/output and choose dependencies. Reusable business or
  persistence behavior belongs in `services/`.
- Authentication and authorization dependencies are centralized in `api/dependencies.py` so every
  route uses the same tenant and role checks.
- Provider clients and blocking-operation limits are centralized in `core/runtime.py`; routes do
  not create provider clients or manage their own concurrency controls.
- Provider calls have a bounded deadline and retain their concurrency slot until a timed-out
  worker actually finishes. Streaming uses bounded queues and cancels its orchestration task on
  client disconnect.
- PostgreSQL row-level policies protect tenant-owned data independently of application predicates.
  Auth dependencies set transaction-local context after token parsing and membership checks.
- Provider adapters remain behind `providers/`, while RAG policy stays in `rag.py` and
  `security/policy.py`.

When adding a new domain, add its router, include it once from `main.py`, and keep the route's
response contract in `models.py`.
