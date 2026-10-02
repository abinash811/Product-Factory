# ADR 0005: Organizations, custom roles and two locks on tenant data

- **Date:** 2026-10-02
- **Status:** accepted (product owner chose runtime-creatable custom roles)

## Context
Products need Organization → Users → Roles → Permissions → Resources, with roles that differ per product and customizable per customer, and tenant data that can never leak.

## Decision
- **Tables:** `users` (our own id; provider id stored beside it), `organizations`, `roles`, `memberships` (one role per member). Invitations follow in build step 3d.
- **Roles live in the database, per organization.** New organizations get starter roles copied from `product/roles.config.json`; organizations can create, edit and delete custom roles at runtime. The product config also defines the catalog of valid permissions (factory core plus product-specific), so a custom role can only use real permissions.
- **Permissions** are `resource:action` with wildcards (`*`, `resource:*`). Every route declares its permission; permissions named in routes are checked against the catalog at startup.
- **No privilege escalation:** you can only grant, assign, edit or remove roles whose permissions you hold yourself. The `owner` role (`*`) is immutable and an organization always keeps at least one owner.
- **The organization comes from the URL** (`/organizations/{org_id}/...`). Non-members get 404, identical to a missing organization.
- **Two independent locks on tenant data:** (1) `TenantRepository` filters every query by organization; (2) Postgres row-level security, forced on every tenant table, driven by per-request values (`app.current_org`, `app.current_user_id`) set transaction-locally. A composite foreign key stops a membership from pointing at another organization's role.
- **The API connects as a limited database role** (not superuser, no BYPASSRLS). In production the readiness check fails otherwise; in development a warning is logged. Tests run the API as that limited role.
- Tests that prove isolation: cross-tenant attacks through every route, direct SQL as the limited role, and a test that fails if any table with `organization_id` lacks forced row-level security.

## Alternatives considered
Roles only in config (simpler, rejected: owner wants custom roles); several roles per member (more flexible, more complexity: can be added later with a migration); `X-Organization` header instead of URL (hidden state, harder to test and cache); relying on the application filter alone (one forgotten filter leaks data).

## Consequences
Strong isolation by default; products add tenant tables with a documented checklist. Users table is global (not tenant-owned) and is accessed only through explicit queries. Per-request context values reset at commit, so routes must never commit mid-request (the session dependency commits).
