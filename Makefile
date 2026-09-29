.PHONY: check file-length api-check api-dev api-test
# `make check` is the single "is this done?" command. Claude's Stop hook and CI both run it.
# Later build steps add: eslint, tsc, vitest, playwright (frontend), dependency scans.
check: file-length api-check

file-length:
	@bash scripts/check-file-length.sh

api-check:
	cd apps/api && uv run --frozen ruff format --check . && uv run --frozen ruff check . \
		&& uv run --frozen mypy app tests && uv run --frozen pytest -q

api-dev:
	cd apps/api && uv run uvicorn app.main:app --reload --port 8000

api-test:
	cd apps/api && uv run --frozen pytest -q
