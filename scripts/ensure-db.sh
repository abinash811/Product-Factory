#!/usr/bin/env bash
# Makes sure a local Postgres is reachable on localhost for development and tests.
#   1. already running (Docker Compose, CI service, your own)  -> just make sure the databases exist
#   2. Docker available                                         -> docker compose up
#   3. otherwise, native Postgres binaries (e.g. cloud sessions) -> start a throwaway local cluster
set -euo pipefail

PORT="${PGPORT:-5432}"
export PGPASSWORD="${PGPASSWORD:-factory}"
DATABASES=(factory factory_test factory_migrations_test)
ready() { pg_isready -q -h localhost -p "$PORT" -U factory; }

if ! ready; then
  if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    docker compose -f infra/docker-compose.yml up -d --wait postgres
  else
    BIN="$(ls -d /usr/lib/postgresql/*/bin 2>/dev/null | sort -V | tail -1 || true)"
    [ -n "$BIN" ] || { echo "No Postgres available. Install Docker and run 'make db-up'." >&2; exit 1; }
    DATA="${FACTORY_PGDATA:-/tmp/factory-pgdata}"
    RUN=()
    if [ "$(id -u)" = "0" ]; then RUN=(runuser -u postgres --); fi   # Postgres refuses to run as root
    if [ "$(id -u)" = "0" ]; then mkdir -p "$DATA" && chown postgres "$DATA"; else mkdir -p "$DATA"; fi
    [ -f "$DATA/PG_VERSION" ] || "${RUN[@]}" "$BIN/initdb" -D "$DATA" -A trust -U postgres -E UTF8 --locale=C.UTF-8 >/dev/null
    "${RUN[@]}" "$BIN/pg_ctl" -D "$DATA" -o "-p $PORT -k /tmp -c listen_addresses=localhost" \
      -l "$DATA/server.log" -w start >/dev/null
    PGPASSWORD="" psql -q -h localhost -p "$PORT" -U postgres -d postgres \
      -c "CREATE ROLE factory LOGIN SUPERUSER PASSWORD 'factory'" >/dev/null 2>&1 || true
  fi
fi

for db in "${DATABASES[@]}"; do
  if ! psql -q -h localhost -p "$PORT" -U factory -d postgres -tAc \
      "SELECT 1 FROM pg_database WHERE datname='$db'" | grep -q 1; then
    createdb -h localhost -p "$PORT" -U factory "$db"
  fi
done
# The limited role the API runs as (so row-level security is really enforced, even locally).
for db in factory factory_test; do
  psql -q -h localhost -p "$PORT" -U factory -d "$db" -v ON_ERROR_STOP=1 \
    -f infra/postgres/app_role.sql >/dev/null
done
echo "Postgres ready on localhost:$PORT"
