---
name: database-conventions
description: How to add or change database tables, models and migrations. Use whenever a model, table, column or migration is involved.
---
# Database conventions

Decisions and reasons: `docs/adr/0003-database-conventions.md`. Code: `apps/api/app/core/db/`.

- New model: inherit `Base` plus `UUIDPrimaryKeyMixin` and `TimestampMixin`. Import the model module in `apps/api/migrations/env.py` so autogenerate sees it.
- Tenant-owned tables also need `organization_id` and go through the tenant-scoped repository (added in build step 3).
- Change the schema ONLY through a migration: `make db-revision m="short description"`, then read the generated file. Autogenerate misses renames, data changes and some defaults, so fix those by hand.
- Never edit a migration that already exists (a hook blocks it). Write a new one to correct it.
- Migrations must work forward and backward (`downgrade`) and on a non-empty database. Backfill data explicitly; add NOT NULL columns in steps (nullable → backfill → NOT NULL).
- Use the request session: `session: Annotated[AsyncSession, Depends(get_session)]`. Do not commit inside routes or services; the dependency commits or rolls back.
- Timestamps are timezone-aware UTC. IDs are UUIDs. Give constraints no manual names; the naming convention does it.
- Tests use the real database: the `db_session` fixture rolls back after each test. Never mock the database.
- `make check` includes a test that fails when models and migrations disagree; run `make db-migrate` to apply migrations locally.
