# ADR 0001: Fixed technology stack

- **Date:** 2026-09-29
- **Status:** accepted (product owner specified the core stack; gap-filling choices accepted 2026-09-29)

## Context
The owner builds many products in different domains and does not want to rebuild the technical foundation each time. Claude builds the products, so the stack must be stable and unambiguous.

## Decision
Use the stack in `docs/TECHNOLOGY_DECISIONS.md`. It does not change during normal development. Supabase is used as managed Postgres, Auth and Storage only; all business data goes through FastAPI + SQLAlchemy (one data path, one set of rules).

## Alternatives considered
- SQLModel instead of SQLAlchemy + Pydantic: rejected, a second way to define models.
- Own JWT login as in common FastAPI starters: rejected, Supabase Auth is the single auth system.
- Next.js API routes for business logic: rejected, FastAPI is the single backend.
- Turborepo/monorepo tooling: rejected as unnecessary complexity.
- Storybook: rejected, an in-app design-system page is less to maintain.

## Consequences
Faster, consistent builds and fewer decisions per product. Changing a foundational tool later needs an explicit ADR and owner approval.
