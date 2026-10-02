# New product setup: what you provide

The Factory has no credentials. When you start a product, create these accounts/projects for THAT product
and give Claude the values only through the secret stores listed. Never paste secrets into files or commits.

| Needed | Where it comes from | Where it goes |
|---|---|---|
| Supabase project (database, login, files) | supabase.com, one project per product | `DATABASE_URL`, `MIGRATION_DATABASE_URL`, Supabase URL and keys: Render + Vercel + GitHub Actions secrets |
| GitHub repo | Created from the Factory template (private) | Add the Factory as the `factory` remote to pull core updates |
| Render (API, workers, Redis) | render.com | Environment variables set in the Render dashboard |
| Vercel (web) | vercel.com | Environment variables set in the Vercel dashboard |
| Resend (email) | resend.com | `RESEND_API_KEY` in Render |
| Sentry, PostHog | sentry.io, posthog.com | DSN / project key in Render and Vercel |
| Domain and Cloudflare | Your registrar and cloudflare.com | DNS records |

Rules: use a separate project and separate keys for staging and production. Rotate a key immediately if it is ever
pasted somewhere it should not be. Build steps that need a service list the exact variable names in `apps/api/.env.example`.

## Database roles (important for security)

Use TWO database roles per product:

| Role | Used for | Rules |
|---|---|---|
| Owner/admin (for example `postgres`) | Running migrations (`MIGRATION_DATABASE_URL`) | Never used by the running API |
| Application role (for example `factory_app`) | The running API (`DATABASE_URL`) | Not a superuser and **no BYPASSRLS** |

Row-level security (the database's own tenant lock) is ignored by superusers and by roles with BYPASSRLS, so the
API must not connect as one. In production the API's readiness check fails if it does, and the deploy will not go live.
Create the application role once with `infra/postgres/app_role.sql` (change the role name and password, and the
role named in `ALTER DEFAULT PRIVILEGES FOR ROLE ...` to your migration/owner role), then put the application
role's connection string in `DATABASE_URL`.

## Supabase settings to check for each product

- **Turn on email confirmation** (Authentication settings). Invitations are matched to the email address in the login
  token, so unconfirmed emails would weaken them.
- **Use the new signing keys** (asymmetric JWT signing). The API accepts only public-key signed tokens (ES256, RS256, EdDSA) and
  rejects shared-secret (HS256) tokens on purpose.
- **First-product smoke test (do this once, with a real token):** sign in, call `GET /api/v1/me`, and confirm it succeeds.
  If it answers 401, compare the token's `iss` and `aud` claims with `AUTH_ISSUER` / `AUTH_AUDIENCE`: the Factory assumes
  issuer `<SUPABASE_URL>/auth/v1` and audience `authenticated`, which could not be verified without a real project.
