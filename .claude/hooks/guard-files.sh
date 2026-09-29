#!/usr/bin/env bash
# PreToolUse(Edit|Write): protect secrets and applied database migrations. Exit 2 = blocked.
set -uo pipefail
path=$(jq -r '.tool_input.file_path // ""' 2>/dev/null)
[ -n "$path" ] || exit 0
base=$(basename "$path")

block() { echo "BLOCKED by Product Factory guardrail: $1" >&2; exit 2; }

case "$base" in
  .env.example|.env.*.example) ;;                       # templates are fine
  .env|.env.*) block "never write real .env files. Put variable NAMES in .env.example; real values live in host secret stores." ;;
esac

# Existing migration files are history: create a new migration instead of editing an old one.
if echo "$path" | grep -Eq '/migrations/versions/[^/]+\.py$' && [ -f "$path" ]; then
  block "migrations are append-only. Create a new migration instead of editing $base."
fi
exit 0
