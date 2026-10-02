.PHONY: check file-length api-check api-dev api-test db-up db-down db-migrate db-revision
# `make check` is the single "is this done?" command. Claude's Stop hook and CI both run it.
# Later build steps add: eslint, tsc, vitest, playwright (frontend), dependency scans.
check: file-length api-check

file-length:
	@bash scripts/check-file-length.sh

# Start (or find) local Postgres. Uses Docker Compose when available, native Postgres otherwise.
db-up:
	@bash scripts/ensure-db.sh

db-down:
	docker compose -f infra/docker-compose.yml down

db-migrate: db-up
	cd apps/api && uv run alembic upgrade head
	@PGPASSWORD=factory psql -q -h localhost -U factory -d factory -c "REVOKE ALL ON alembic_version FROM factory_app" >/dev/null 2>&1 || true

# Usage: make db-revision m="add invoices table"   (review the generated file before committing)
db-revision: db-up
	cd apps/api && uv run alembic revision --autogenerate -m "$(m)"

api-check: db-up
	cd apps/api && uv run --frozen ruff format --check . && uv run --frozen ruff check . \
		&& uv run --frozen mypy app tests && uv run --frozen pytest -q

api-dev: db-migrate
	cd apps/api && uv run uvicorn app.main:app --reload --port 8000

api-test: db-up
	cd apps/api && uv run --frozen pytest -q
