# Architecture (target layout)

Folders marked FIXED are the factory core. A product never edits them.

```
product-factory/
├─ CLAUDE.md, Makefile, .claude/ (skills, agents, hooks), .github/workflows/
├─ docs/            decisions, specs, ADRs, writing guide
├─ product/         PRODUCT: product.config.json (brand, terms, flags, pricing), roles.config.json, workflows/
├─ apps/
│  ├─ web/src/
│  │  ├─ core/            FIXED  auth, app shell, org switcher, generated API client
│  │  ├─ design-system/   FIXED  tokens, shadcn components, shared state components, patterns
│  │  └─ features/        PRODUCT screens
│  └─ api/
│     ├─ app/core/        FIXED  config, auth, tenancy, RBAC, errors, logging, rate limit, audit, files, email, jobs, webhooks
│     ├─ app/modules/     OPTIONAL factory modules (billing, ...)
│     ├─ app/domain/      PRODUCT business logic
│     ├─ app/integrations/ PRODUCT connectors
│     ├─ migrations/      Alembic (append-only)
│     └─ tests/
├─ infra/           docker-compose, render.yaml, env templates
├─ scripts/         checks and tooling
└─ ai/              RESERVED (not built)
```

Flow: Browser → Next.js (Vercel) → FastAPI (Render) → Postgres/Storage (Supabase), Redis → Celery workers. Auth by Supabase; FastAPI verifies its tokens. Isolation model: Organization → Membership (user + role) → Permissions (`resource:action`, configured per product) → Resources.

Only the docs, `.claude/`, scripts and CI exist so far. App folders are created as build steps land (see `docs/FACTORY_PROPOSAL.md`, section 7).
