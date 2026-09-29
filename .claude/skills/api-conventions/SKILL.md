---
name: api-conventions
description: REST API conventions for the FastAPI backend. Use when designing, adding or reviewing any endpoint.
---
# API conventions

- Versioned base path `/api/v1`. Plural nouns, kebab-case, no verbs in paths (`/purchase-orders`, not `/createOrder`).
- Every route declares authentication AND a permission (`resource:action`). Public routes are an explicit, reviewed exception.
- Request and response bodies are Pydantic models. Never return ORM objects directly.
- List endpoints: pagination (`limit`, `cursor` or `page`), filtering and sorting via query params, with a documented allow-list of sortable/filterable fields. Always paginated, with a max page size.
- One standard error shape: `{ "error": { "code": "...", "message": "...", "request_id": "..." } }`. Correct status codes (400 validation, 401, 403, 404, 409, 422, 429). Never leak stack traces or internals.
- Tenant safety: data access only through the tenant-scoped repository. Cross-tenant lookups return 404, not 403.
- Anything that sends messages or moves money accepts an idempotency key.
- Rate limits on auth and public write endpoints. Validate all input at the boundary, including webhooks and uploads.
- New endpoint checklist: schema → service → repository → route → permission → tests (happy path, validation, permission denied, cross-tenant) → OpenAPI description → regenerate the frontend client.
