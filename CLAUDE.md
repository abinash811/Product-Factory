# Product Factory — rules for Claude

This repo is a reusable factory. Each product is created from it (GitHub template + `factory` upstream remote), then given its own business logic. The owner is a non-technical product builder: make technical decisions, implement them, explain important ones in short, simple language.

Full stack and rationale: @docs/TECHNOLOGY_DECISIONS.md. Target layout: @docs/architecture.md. Definition of done: @docs/DEFINITION_OF_DONE.md.

## Locked decisions (IMPORTANT)
- The stack in `docs/TECHNOLOGY_DECISIONS.md` is final. Never suggest or introduce alternatives during normal work (no Prisma, MongoDB, Redux, MUI, etc.).
- If you believe a foundational decision must change: STOP, explain why in simple words, wait for approval, then record a new ADR in `docs/adr/`.
- No new dependency without a clear reason and the owner's OK. Install it first, confirm it works, then import it. Never hand-edit lockfiles.
- The AI layer (`ai/`) is reserved. Do not build it unless asked.

## Where things live
- `core/` and `design-system/` folders are the FIXED factory. While building a product feature, never edit them. If core must change, say so and treat it as a separate, reviewed factory change.
- Product identity lives in `product/` (config, roles, workflows). Business logic in `apps/api/app/domain/`, product screens in `apps/web/src/features/`, connectors in `apps/api/app/integrations/`.
- Reuse before building: search the repo for an existing component, helper or pattern first. Do not rebuild what exists.

## How to work
1. New product or significant feature: run the `feature-kickoff` skill first (interview → research → written spec → owner approval). Do not code before the spec is agreed.
2. Inspect existing code, check architecture and design system, write a short plan (plan mode for multi-file work).
3. Implement in small steps. Write tests WITH the code (unit + E2E where user-facing), not after.
4. Run `make check` and paste real output as evidence. "Looks done" is never done.
5. Self-review the diff, then use the `reviewer` agent (and `security-reviewer` for auth, data access, secrets, dependencies, uploads, webhooks).
6. Small, understandable commits: Conventional Commits, explain why. Never push to `main`, never `--no-verify`, never force-push.
7. Finish by explaining what changed in a few plain sentences.
When a bug appears, use the `debug-root-cause` skill: reproduce, find the cause, fix the cause, add a test that would have caught it.

## Code standards
- Max 300 lines per file (enforced by `scripts/check-file-length.sh`). Split by responsibility, not arbitrarily.
- Backend: routes are thin → services hold business logic → repositories talk to the database. Python typed everywhere (mypy strict), Ruff clean, Pydantic at every boundary.
- Frontend: TypeScript strict, no `any`. Server data via TanStack Query, never Zustand. Forms via React Hook Form + Zod. API client is generated from OpenAPI, never hand-written.
- Every tenant-owned table has `organization_id`, row-level security (`enable_tenant_isolation`), and every query goes through a `TenantRepository`. No exceptions; each new tenant table must be covered by `tests/test_tenant_isolation.py`. Follow `database-conventions`.
- Every new route declares its permission explicitly. Default is protected.
- Never a raw stack trace or internal message to the client; use the standard error shape.
- No secrets in code, logs or commits. Variable NAMES go in `.env.example`; values live in host secret stores.

## UI standards
- shadcn/ui is the only component library. Use design tokens and the shared patterns; no hardcoded colors or spacing, no raw `<button>`, no one-off UI.
- Every screen ships loading, empty, error (with retry), no-permission and success states using the shared state components. Copy follows the writing guide in `docs/`.
- Keyboard accessible, visible focus, WCAG 2.2 AA.

## Commands
- `make check` — everything that must pass before work is done (grows with each build step).
- `make api-dev` — run the API locally (starts the database and applies migrations first). `make api-test` — backend tests only.
- `make db-up` starts local Postgres (Docker, or native where Docker is unavailable). `make db-migrate` applies migrations. `make db-revision m="..."` creates one. Read `database-conventions` before touching models or migrations.
- Python deps: `cd apps/api && uv add <pkg>` (dev: `uv add --dev <pkg>`). Never edit `pyproject.toml` or `uv.lock` by hand to add a package.

## Automatic guardrails (hooks in `.claude/hooks/`)
Edits to `.env` files and existing migrations are blocked; destructive commands, pushes to main and `--no-verify` are blocked; files are formatted/linted after each edit; the turn cannot end while `make check` fails. Hooks are a safety net, not a boundary: CI runs the same checks and is the real gate.
