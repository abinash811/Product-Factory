# ADR 0005: Organizations, custom roles and two locks on tenant data

- **Date:** 2026-10-02
- **Status:** accepted (product owner chose runtime-creatable custom roles)

## Context
Products need Organization → Users → Roles → Permissions → Resources, with roles that differ per product and customizable per customer, and tenant data that can never leak.

## Decision
- **Tables:** `users` (our own id; provider id stored beside it), `organizations`, `roles`, `memberships` (one role per member). `invitations` (email + role + expiry; only a hash of the secret token is stored; accepting needs the token AND a login with the matching email; atomic, single use). Row-level security lets the holder of a token see exactly that one invitation. Email delivery arrives with build steps 5-6; until then the API returns the token once to the inviter.
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

## Review findings and what was done (2026-10-02)
Two independent reviews (code and security, fresh context) were run on step 3. Fixed, each with a test that fails if the fix is removed:
- **Commit after response:** the database commit used to run after the client was told "success". The session now finishes before the response (`SessionDep`, `scope="function"`); a test makes the commit fail and expects an error.
- **Races:** owner changes (remove or demote) lock the organization row, so two owners cannot both leave (reproduced before the fix: the organization ended with no owner). Role delete/assign and invitation create take row locks. At most one open invitation per email is enforced by a partial unique index. Accepting an invitation is atomic.
- **Rate limits could be bypassed** with a forged `X-Forwarded-For` header. The client address now comes only from the entry our own proxy added (`TRUSTED_PROXY_HOPS`).
- **Invitation email check** now uses the email in the current verified token (not the one stored from earlier logins); anonymous sessions are rejected by default; an email the provider explicitly marks unverified is not trusted.
- **Default-protected API:** every `/api/v1` route requires a login at the router level; tests call every route anonymously (must be 401) and as a member with no permissions (must be 403, except a short reviewed allow-list). Custom roles cannot hold `*`.
- Revoking an invitation needs the same standing as creating one; the organization context is given to the database only after membership is proven; returning users cause no database write; the API role cannot modify migration history; the row-level-security readiness gate also applies whenever login is configured.

Known and deferred (decided, not forgotten):
- **No audit log yet.** Role, member and invitation changes are not recorded. This is build step 5 (audit logs) and must retrofit these services.
- **Email-verification claim names are unconfirmed.** The code only distrusts an email the token explicitly marks unverified; it cannot fail closed without a real Supabase token. Products must turn on "Confirm email" and run the first-product smoke test (`docs/NEW_PRODUCT_SETUP.md`).
- **Row-level security trusts the organization the app sets** (after membership is proven). A stricter policy that checks membership inside the database was considered and not built.
- **Per-user limits:** rate limits are per client address. A per-user quota on creating organizations is a product decision.
- **Taken slugs reveal that an organization with that slug exists** (slugs are treated as public identifiers).
- **Roles are live:** editing a role changes it for everyone holding it, including invitations not yet accepted.
