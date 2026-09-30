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
