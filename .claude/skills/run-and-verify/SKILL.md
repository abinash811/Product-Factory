---
name: run-and-verify
description: How to run this repo's checks and prove a change works before calling it done. Use before declaring any task complete.
---
# Run and verify

```
make check                              # everything that must pass (grows each build step)
bash scripts/check-file-length.sh       # 300-line rule
```

Later build steps add here (do not invent commands that do not exist yet): local dev with Docker Compose, backend tests (pytest), frontend tests (Vitest), browser tests (Playwright), lint and type checks.

Rules:
- Run the real command, read the real output, and show it as evidence. Never write "tests should pass".
- Prefer running the single relevant test while iterating, then the full `make check` at the end.
- If a check cannot run in this environment, say so explicitly instead of skipping it silently.
- Never disable, skip or loosen a test to get green.
