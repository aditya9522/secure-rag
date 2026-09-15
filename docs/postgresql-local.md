# Local PostgreSQL

The API uses PostgreSQL through SQLAlchemy’s async `asyncpg` driver. Keep the application database separate from unrelated local databases such as `helpdesk_tms`; tenant data, refresh sessions, conversations, and audit records should have their own owner and migration history.

## Create a dedicated database

Run these commands on the host where PostgreSQL is installed. Choose a unique password and keep it in the local `.env` file or a secret manager; do not commit it.

```bash
sudo -u postgres psql
```

```sql
CREATE USER secure_rag WITH LOGIN PASSWORD 'replace-with-a-local-secret';
CREATE DATABASE secure_rag OWNER secure_rag;
\q
```

If the role or database already exists, use `ALTER ROLE ... PASSWORD ...` as the PostgreSQL administrator instead of creating a duplicate. The existing `helpdesk_tms` database may be used only when its owner grants this application a dedicated schema/database role and its data boundary is approved.

## Configure and migrate

```bash
cp .env.example .env
# Set POSTGRES_PASSWORD/DATABASE_URL to real local values and set a random JWT_SECRET.
source .venv/bin/activate
alembic upgrade head
```

For the Docker Compose API image, run the migration explicitly after the database
is healthy and before the first API start:

```bash
docker compose run --rm api alembic upgrade head
docker compose up -d api
```

For an existing database, the migration is intentionally the only schema owner. Do not use `Base.metadata.create_all()` in the application process.

## Bootstrap the first system administrator

Create the first account through your approved bootstrap process, then promote it from a trusted administrator shell:

```bash
python scripts/bootstrap_admin.py admin@example.com
```

The script reads `DATABASE_URL` from the environment and commits only the `is_system_admin` change. System administrator access is not exposed through a public API.

## Verify the connection

```bash
psql "$DATABASE_URL" -c 'select current_database(), current_user'
curl http://localhost:8000/healthz
curl http://localhost:8000/readyz
```

`/healthz` verifies process liveness. `/readyz` verifies PostgreSQL and the configured retrieval providers.
