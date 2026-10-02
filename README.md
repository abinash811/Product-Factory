# Product Factory

A reusable, production-grade foundation for building many products (pharmacy, HR, support, sales, AI and more). The core stays fixed; each new product is a copy of this repo with its own branding, roles and business logic.

- Rules for Claude: [`CLAUDE.md`](CLAUDE.md)
- Locked stack: [`docs/TECHNOLOGY_DECISIONS.md`](docs/TECHNOLOGY_DECISIONS.md)
- Layout: [`docs/architecture.md`](docs/architecture.md) · Decisions: [`docs/adr/`](docs/adr/)
- Build plan and research: [`docs/FACTORY_PROPOSAL.md`](docs/FACTORY_PROPOSAL.md)

Status: **Steps 0-3 done** (rulebook and guardrails, backend skeleton, database, login/organizations/custom roles/invitations with row-level security). Next: Step 4, frontend and design system.

## Run it
```
make db-up        # local Postgres (Docker, or native when Docker is unavailable)
make api-dev      # applies migrations, then serves the API on http://localhost:8000 (docs at /docs)
make check        # lint, types, tests, 300-line rule: must pass before anything is "done"
```
Copy `apps/api/.env.example` to `apps/api/.env` for local settings.
