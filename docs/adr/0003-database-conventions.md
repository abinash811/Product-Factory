# ADR 0003: Database conventions

- **Date:** 2026-09-30
- **Status:** accepted

## Context
Every product stores data. Conventions decided once keep every table and migration consistent.

## Decision
- **Access:** SQLAlchemy 2.0 async with the psycopg 3 driver. One driver serves the API, Alembic and later Celery jobs.
- **IDs:** random UUIDs (`gen_random_uuid()` on the server, `uuid4` in Python). Unguessable and safe to generate anywhere.
- **Time:** every timestamp is `timestamptz`, stored in UTC. All tables get `created_at` and `updated_at` from `TimestampMixin`.
- **Names:** constraints and indexes follow one naming convention (`app/core/db/base.py`) so migrations are predictable.
- **Transactions:** one session per request. Commit on success, roll back on any error (`get_session`).
- **Connections:** the app may use Supabase's pooled connection (`DB_POOLER=true` disables prepared statements as pgbouncer requires). Migrations use the direct connection (`MIGRATION_DATABASE_URL`).
- **Migrations:** Alembic, append-only (existing migration files are never edited; a hook blocks it). Files are date-prefixed. A test fails when models and migrations disagree.
- **Tests:** run against a real Postgres, never mocks. Each test runs inside a rolled-back transaction. Tests can never reach a real database: the test setup overrides `DATABASE_URL`.
- **Local database:** Docker Compose (`make db-up`). Where Docker is unavailable (cloud sessions) `scripts/ensure-db.sh` starts a native Postgres 16 with UTF-8 encoding.

## Alternatives considered
- Integer auto-increment IDs: guessable, leak record counts, awkward across environments.
- asyncpg as a second driver: faster in benchmarks but a second dependency for no product-visible benefit.
- Fake or in-memory databases in tests: hide real Postgres behavior (constraints, transactions, RLS).

## Consequences
Consistent tables and safe requests by default. Every tenant table added in Step 3 builds on these mixins.
