# Product Factory — Foundation Proposal

Status: **DRAFT, waiting for product-owner approval. No code has been written.**
Date: 2026-09-29

---

## 1. What I inspected

| Source | What it is | Verdict |
|---|---|---|
| `abinash811/Product-Factory` | This repo | **Empty.** Nothing to reuse. |
| `abinash811/claude-product-template` | Your repo | **Empty.** Nothing to reuse. |
| `abinash811/engineering-os` | Your repo. 129 Markdown files: rules, roles, workflow, ADR template, Claude hook/skill/agent adapters | **No code.** It is a *process handbook*. Useful for standards and the Claude workflow. Its FastAPI profile matches our backend choice. |
| Other private repos (Pharmacare-*, Chatter, Slacker, etc.) | Your earlier products | **Not inspected** (not in scope of this session). Worth mining later for the pharmacy domain module. |
| Public open source (below) | Read via GitHub pages | Verified license and stack. Activity dates were not always visible; re-check before copying anything. |

## 2. Strongest open-source foundations

None of these is adopted whole. Each is a **reference we extract from**.

| Repo | License | Stars | What we take | What we leave |
|---|---|---|---|---|
| [fastapi/full-stack-fastapi-template](https://github.com/fastapi/full-stack-fastapi-template) | MIT | 45.8k | Backend layout, Docker Compose, GitHub Actions, Playwright + pytest setup, OpenAPI-generated frontend client, React Email idea | SQLModel (we use SQLAlchemy), its own JWT login (we use Supabase Auth), Vite frontend, Traefik |
| [Kiranism/next-shadcn-dashboard-starter](https://github.com/Kiranism/next-shadcn-dashboard-starter) | MIT | 7.1k | App shell, sidebar, data-table + filters + URL state, chart layout patterns (Next.js 16, Tailwind v4, shadcn, TanStack, Zustand) | Clerk auth/billing (tightly coupled), TanStack Form (we use React Hook Form) |
| [point-source/supabase-tenant-rbac](https://github.com/point-source/supabase-tenant-rbac) | BSD-2 (keep attribution) | 476 | **Design** for orgs → members → per-org roles → permissions, with Postgres helper functions for row security | The extension itself. We write our own Alembic migrations in the same shape. |
| [vintasoftware/nextjs-fastapi-template](https://github.com/vintasoftware/nextjs-fastapi-template) | MIT | 329 | Confirms the Next.js + FastAPI + `openapi-fetch` typed-client pattern | fastapi-users auth (conflicts with Supabase Auth) |
| [satnaing/shadcn-admin](https://github.com/satnaing/shadcn-admin) | MIT | 15.1k | Visual reference for the shell only | Vite-based, Clerk |
| [muzamil-rashdi/fastapi-rbac-boilerplate](https://github.com/muzamil-rashdi/fastapi-rbac-boilerplate) | MIT | 0 (one commit) | Reading reference for "principal → permission check → tenant-filtered repository" | Not production-validated. Do not copy code. |
| `abinash811/engineering-os` | yours | — | Governance standards, ADR template, definition of done, Claude skills/agents/hooks | See decision D3 |

**Why not one big starter?** No single repo covers Supabase Auth + multi-tenant RBAC + Celery + webhooks + audit logs. Merging two of them would give two auth systems and two UI systems. So we build one coherent core and borrow proven parts.

## 3. Conflicts and unnecessary parts

| Issue | Resolution |
|---|---|
| **Supabase vs SQLAlchemy overlap.** Supabase can serve data straight to the browser, bypassing our API. | Use Supabase only as **managed Postgres + Auth + Storage**. All business data goes through FastAPI + SQLAlchemy. One path, one set of rules. (Decision D1) |
| **Two auth systems** in the FastAPI starters (own JWT) vs Supabase Auth. | Supabase Auth only. FastAPI just verifies Supabase's tokens. |
| **Next.js API routes vs FastAPI.** | Next.js is UI only. No business logic in Next. |
| **Sentry vs OpenTelemetry overlap.** | Not a conflict: OpenTelemetry produces traces/request IDs, Sentry catches errors, PostHog tracks product usage. Keep all three, each with one job. |
| **Cloudflare in front of Vercel.** | Use Cloudflare for DNS (and CDN/WAF in front of Render API), not as a proxy on the Vercel site. |
| **Zustand + TanStack Query.** | Not a conflict if disciplined: Query = server data, Zustand = small UI state only. |
| **Redis/Celery cost on Render.** | Works, but see cost notes below. |

## 4. Proposed repository structure

One repo. Core is **fixed**. Everything a product changes lives in clearly marked "product" places.

```
product-factory/
├─ CLAUDE.md                     # Claude's rulebook for this repo (short, strict)
├─ .claude/                      # skills, review agents, hooks (from engineering-os ideas)
├─ .github/workflows/            # CI: lint, tests, security scan, deploy
├─ docs/
│  ├─ adr/                       # Architecture Decision Records
│  ├─ architecture.md
│  └─ new-product-checklist.md
├─ product/                      # ★ THE ONLY PLACE PRODUCT IDENTITY LIVES
│  ├─ product.config.json        #   name, logo, colors, terminology, feature flags, pricing
│  ├─ roles.config.json          #   roles + permissions for this product
│  └─ workflows/                 #   domain-specific workflow definitions
├─ apps/
│  ├─ web/                       # Next.js frontend
│  │  └─ src/
│  │     ├─ core/                #   auth, org switcher, app shell, API client (FIXED)
│  │     ├─ design-system/       #   tokens + shadcn components + patterns (FIXED)
│  │     └─ features/            # ★ product screens
│  └─ api/                       # FastAPI backend
│     ├─ app/
│     │  ├─ core/                #   config, auth, tenancy, RBAC, errors, logging,
│     │  │                       #   rate limit, audit, files, email, jobs, webhooks (FIXED)
│     │  ├─ modules/             #   optional: billing, notifications-center, etc.
│     │  ├─ domain/              # ★ business logic (pharmacy, HR, sales…)
│     │  └─ integrations/        # ★ third-party connectors
│     ├─ migrations/             #   Alembic
│     └─ tests/
├─ infra/                        # docker-compose, render.yaml, env templates
└─ ai/                           # RESERVED. README only. Not built yet.
```

Rule for Claude: **never edit `core/` or `design-system/` while building a product feature.** If core must change, it is a separate, reviewed change that goes back into the Factory.

## 5. Dependency map

How pieces talk to each other:

```
Browser ─► Next.js (Vercel) ──REST + Supabase JWT──► FastAPI (Render)
   │             │                                      │
   │             └─ Supabase Auth (login) ◄─ verify ────┤
   │                                                    ├─► PostgreSQL (Supabase) via SQLAlchemy
   └─ PostHog (usage)                                   ├─► Supabase Storage (files)
                                                        ├─► Redis ─► Celery workers ─► Resend (email), webhooks out
                                                        └─► Sentry + OpenTelemetry
```

| Layer | Tool | Purpose | Cost |
|---|---|---|---|
| Frontend | Next.js, React, TypeScript, Tailwind, shadcn/ui | UI + design system | free |
| Frontend | React Hook Form + Zod | forms + validation | free |
| Frontend | TanStack Query / Table, Zustand, Recharts | data, tables, UI state, charts | free |
| Backend | FastAPI, Pydantic, SQLAlchemy, Alembic | API, validation, DB, migrations | free |
| Jobs | Redis + Celery (+ Celery Beat) | async, scheduled, retry | Redis on Render has a free tier; workers are paid |
| Platform | Supabase (Postgres, Auth, Storage) | data, login, files | free tier |
| Delivery | Vercel, Render, Cloudflare, Resend | hosting, DNS/CDN, email | free tiers with limits |
| Quality | Ruff, ESLint, Prettier, pytest, Vitest, Playwright | lint + tests | free |
| Observability | Sentry, OpenTelemetry, PostHog | errors, traces, analytics | free tiers |
| Security in CI | GitHub Dependabot, CodeQL, gitleaks, pip-audit / `pnpm audit` | dependency + secret scanning | free for public repos |

**Small additions I need your OK for** (tooling only, not architecture): `pnpm` (JS packages), `uv` (Python packages), `openapi-typescript` + `openapi-fetch` (auto-generate a typed API client from OpenAPI so frontend and backend cannot drift), `pydantic-settings` (env config), `structlog` (structured logs), `slowapi` (rate limiting on Redis). Nothing else without asking.

**Cost reality check (verify before launch, plans change):** Vercel's free Hobby plan is for non-commercial use, so a revenue product needs Pro (~$20/mo). Render free web services sleep when idle and Celery workers are not free (~$7/mo each). Supabase free projects pause after inactivity. Fine for building; budget roughly $30–60/mo for the first paying product. The architecture does not change when you upgrade.

## 6. How multi-tenancy and permissions will work

- Data model: **Organization → Membership (user + role) → Role → Permissions → Resources.**
- Every tenant table has `organization_id`. Isolation is enforced **twice**:
  1. In the API: every query goes through a tenant-scoped repository that automatically filters by the caller's organization. Developers cannot forget it.
  2. In the database: Postgres row-level security as a safety net on tenant tables.
- Roles and permissions come from `product/roles.config.json` (pharmacy: *pharmacist, cashier*; HR: *recruiter, manager*). Permissions look like `invoice:create`. Core checks them; products only define them.
- A mandatory automated test proves a user in org A can never read or write org B's data. Every new tenant table must be covered by it.

## 7. Implementation plan

Each phase ends with something you can see working, tested, and committed in small pieces.

| # | Phase | You will see |
|---|---|---|
| 0 | **Foundations**: monorepo, CLAUDE.md, ADRs for these decisions, lint/format, CI skeleton, Docker Compose (Postgres, Redis), secret handling | Repo runs locally with one command; CI green |
| 1 | **API core**: config, versioned `/api/v1`, standard errors, pagination/filter/sort helpers, structured logging, request IDs, health checks, CORS, secure headers, rate limiting, OpenAPI | Live API docs page |
| 2 | **Auth + tenancy**: Supabase Auth, token verification, orgs, memberships, invitations, config-driven RBAC, tenant-scoped repository, RLS, isolation tests | Sign up, create org, invite a teammate, roles enforced |
| 3 | **Design system + app shell**: tokens, theming from `product.config.json`, sidebar/topbar, forms, tables, charts, empty/loading/error states, accessibility checks | Branded, responsive shell; re-theme by editing one file |
| 4 | **Frontend ↔ backend**: generated API client, auth flow, org switcher, permission-aware UI, Playwright E2E for login → org → protected page | End-to-end login test passing in CI |
| 5 | **Audit logs + files + notifications**: audit trail, safe uploads (type/size checks, private buckets, signed URLs), email via Resend | Actions logged; upload/download works safely |
| 6 | **Jobs**: Celery + Beat, retries, failure handling, idempotency keys, email as first real job | Background job visibly retried and recovered |
| 7 | **Webhooks**: incoming (signature check, dedupe, event log) and outgoing (signing, retries, delivery log) | Test webhook in and out |
| 8 | **Observability + analytics**: Sentry, OpenTelemetry, PostHog wired in, basic metrics | Errors and traces appear in dashboards |
| 9 | **Billing foundation + optional modules**: plans, feature flags, entitlements (no payment provider lock-in yet) | Feature gated by plan |
| 10 | **Deploy + product-creation kit**: Vercel/Render/Cloudflare setup, `new-product-checklist.md`, a `/new-product` Claude skill, security review | Create a throwaway "demo product" from the Factory in under a day |

AI layer stays untouched (`ai/` placeholder only) until you ask.

## 8. Decisions I need from you

**D1 — Supabase role (clarification, not a change).** Supabase = managed Postgres + Auth + Storage only. The browser never reads business data straight from Supabase; everything goes through FastAPI. *Recommended: yes.*

**D2 — How a new product is created.**
- **A (recommended):** The Factory is a GitHub *template repo*. Each product gets its **own repo** (own deploys, own data, own risk). Core improvements are pulled into products by merging from the Factory. The strict `core/` vs `product/` split keeps merges painless.
- **B:** One giant repo holding all products. Shared core, but one mistake affects every product and deploys get tangled.

**D3 — `engineering-os`.** It is a technology-agnostic handbook, while the Factory fixes one stack. Recommended: **keep it separate as your "company rulebook"** and copy only what the Factory needs (ADR template, definition of done, security/git standards, Claude skills and hooks) into `docs/` and `.claude/`. The Factory is then self-contained.

## 9. Stack changes I recommend

**None required.** Every technology you listed works together. Only flags, none needing action now:
1. Costs above (Vercel commercial plan, paid Render workers).
2. Don't adopt SQLModel even though the biggest FastAPI starter uses it: it would be a second way to define models beside SQLAlchemy + Pydantic.
3. Zustand is easy to overuse. Rule: server data goes in TanStack Query, never Zustand.

## 10. Not verified

- I could not see exact last-commit dates for the open-source repos (only that they show recent activity), and could not reach supabase.com docs from this environment. Supabase token verification (public-key vs shared-secret signing) will be confirmed in Phase 2 before it is built.
- Free-tier limits are from memory and must be rechecked before launch.
