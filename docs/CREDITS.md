# Credits

Open-source projects this factory reuses or was informed by. When code or a design is adapted from a
repo, it is listed here with its licence, what was taken, and where it lives in this repo.

## Used as dependencies (installed, not copied)
FastAPI, Pydantic, SQLAlchemy, Alembic, psycopg, structlog, slowapi, httpx, uv, Ruff, mypy, pytest.
Exact versions are in `apps/api/uv.lock`.

## Adapted
| Source | Licence | What we took | Where |
|---|---|---|---|
| [Alembic async template](https://alembic.sqlalchemy.org/) (`alembic init -t async`) | MIT | Starting point for the async migration environment | `apps/api/migrations/env.py` |

## Ideas only (no code copied)
| Source | Licence | Idea | Where |
|---|---|---|---|
| [fastapi/full-stack-fastapi-template](https://github.com/fastapi/full-stack-fastapi-template) | MIT | uv-based project, strict mypy and Ruff rule set, single-origin CORS, stable OpenAPI operation ids, cached Docker dependency layer, `compare_type` in migrations, `NullPool` for migrations, `pool_pre_ping` | `apps/api/pyproject.toml`, `Dockerfile`, `migrations/env.py`, `app/core/db/session.py` |

| [point-source/supabase-tenant-rbac](https://github.com/point-source/supabase-tenant-rbac) | BSD-2-Clause | Design only: organizations own members, members hold roles, roles bundle permissions, expiring invitations accepted atomically, no handing out roles above your own. Re-implemented for our stack (own users table, app-level checks plus row-level security); no SQL or code copied | `apps/api/app/core/tenancy/`, `migrations/versions/*0003*`, `*0004*` |
| PyJWT (`pyjwt[crypto]`) | MIT | Dependency: token verification with JWKS keys | `apps/api/app/core/auth/tokens.py` |

## Planned
| Source | Licence | For |
|---|---|---|
| [Kiranism/next-shadcn-dashboard-starter](https://github.com/Kiranism/next-shadcn-dashboard-starter) | MIT | App shell, tables, charts patterns (Step 4) |
