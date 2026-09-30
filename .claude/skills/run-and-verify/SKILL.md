---
name: run-and-verify
description: How to run this repo's checks and prove a change works before calling it done. Use before declaring any task complete.
---
# Run and verify

```
make check          # everything that must pass: 300-line rule, ruff, mypy strict, pytest (coverage >= 90%)
make api-test       # backend tests only (fast loop)
make api-dev        # start the database, apply migrations, run the API on :8000
make db-up          # local Postgres only (Docker, or native where Docker is unavailable)
make db-migrate     # apply migrations
cd apps/api && uv run pytest tests/test_health.py -q --no-cov   # one test file while iterating
```

Later build steps add here (do not invent commands that do not exist yet): frontend tests (Vitest), browser tests (Playwright).

Rules:
- Run the real command, read the real output, and show it as evidence. Never write "tests should pass".
- Prefer running the single relevant test while iterating, then the full `make check` at the end.
- If a check cannot run in this environment, say so explicitly instead of skipping it silently.
- Never disable, skip or loosen a test to get green.
