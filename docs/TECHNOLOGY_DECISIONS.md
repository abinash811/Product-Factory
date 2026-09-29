# Technology Decisions (LOCKED)

Single source of truth for the stack. Changing anything here needs the product owner's approval and a new ADR in `docs/adr/`. Versions: latest stable at build time, pinned by lockfiles.

## Frontend
Next.js (App Router) · React · TypeScript (strict) · Tailwind CSS · shadcn/ui (only component library) · design tokens
React Hook Form + Zod · TanStack Query (server data) · Zustand (small UI state only) · TanStack Table · Recharts
lucide-react (icons) · Geist/Inter via `next/font` · Sonner (toasts) · next-themes · date-fns · nuqs (URL state)
Typed API client generated from OpenAPI: openapi-typescript + openapi-fetch

## Backend
Python 3.13 · FastAPI · Pydantic v2 · OpenAPI · pydantic-settings · structlog · slowapi (rate limiting, Redis) · httpx · Jinja2 (email templates) · mypy (strict)

## Data, auth, files
PostgreSQL on Supabase · SQLAlchemy 2.0 (async) + Alembic · psycopg 3 (one driver for API, migrations and jobs) · Supabase Auth · Supabase Storage · Redis
Search: Postgres full-text (for now). Multi-tenancy: `organization_id` on every tenant table, enforced in the API repository layer and by Postgres row-level security.

## Jobs and integrations
Celery + Celery Beat (Redis broker) · Flower (optional, internal) · in-house webhook module (signing, retries, idempotency, event log) · Resend (email)
Payments: deferred. Billing is a provider-neutral layer until a product needs one.

## Infrastructure and delivery
Docker + Docker Compose (local) · GitHub + GitHub Actions · Vercel (web) · Render (API, workers, Redis) · Cloudflare (DNS/CDN)
pnpm (JS) · uv (Python) · Makefile (task runner) · no monorepo tool

## Testing
Playwright (E2E, with axe accessibility) · Vitest + React Testing Library + MSW · pytest + pytest-asyncio + factory-boy + coverage (real Postgres in tests)

## Code quality and security
Ruff · ESLint · Prettier · Lefthook (git hooks) · Conventional Commits · 300-line file limit
Dependabot · pip-audit · pnpm audit · CodeQL · gitleaks · Trivy · OWASP ASVS/Top 10

## Observability and docs
Sentry · OpenTelemetry · PostHog · health checks and audit logs in core · Markdown · OpenAPI · ADRs

## Claude setup
`CLAUDE.md` + `.claude/` skills, agents and hooks (this repo). MCPs: GitHub, Playwright (locked to localhost, added with the frontend).

## Reserved
`ai/` (LLM gateway, RAG, agents, etc.): not built until requested.

## Product creation model
GitHub template repo. Each product is its own repo with a `factory` upstream remote to pull core updates. See ADR 0002.
