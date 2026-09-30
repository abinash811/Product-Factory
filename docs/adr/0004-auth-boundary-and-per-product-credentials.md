# ADR 0004: Supabase Auth behind a replaceable boundary; credentials belong to products, not the factory

- **Date:** 2026-09-30
- **Status:** accepted (product owner confirmed: keep Supabase, supply credentials per product)

## Context
The Factory is a template. It must build, test and run with no external accounts. Each product created from it will have its own Supabase project and its own secrets. We also want to be able to change login provider later without a rewrite.

## Decision
1. **Supabase stays** as database host, login and file storage (ADR 0001). Alternatives were reviewed and not adopted.
2. **No real credentials exist in the Factory.** Only variable NAMES appear in `.env.example`. Tests never contact Supabase: they generate their own signing keys and verify tokens against them.
3. **The API depends on one small thing from the login system: a verified user identity** (token subject and email). It is checked in one replaceable module (`app/core/auth/`, built in Step 3).
4. **Our own database owns everything else:** an internal `users.id` (the provider's ID is stored beside it, never used as the primary key), organizations, memberships, roles and permissions.
5. **No Supabase-only database features.** Row-level security will use our own session setting (for example `app.current_org`), not Supabase's built-in `auth.uid()`, so it works on any Postgres.
6. **Per-product secrets** live in the hosts' secret stores (Render, Vercel, GitHub Actions). See `docs/NEW_PRODUCT_SETUP.md`.

## Alternatives considered
Clerk, Auth0, WorkOS, Keycloak, Better Auth, and a home-built login (see the discussion of 2026-09-30): proprietary and costly, heavy to operate, or security-critical code we should not own. Neon or Render Postgres remain easy swaps for database hosting because we use plain Postgres only.

## Consequences
Changing login provider later is a small code change plus a one-time account migration (or password reset) for existing users. Supabase specifics (token signing keys, exact settings) are to be confirmed against Supabase's documentation in Step 3, since they could not be verified when this was written.
