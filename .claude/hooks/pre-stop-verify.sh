#!/usr/bin/env bash
# Stop: Claude cannot finish a turn while `make check` fails. "Looks done" is not done.
set -uo pipefail
input=$(cat)
# Avoid an endless loop: if we already blocked once this turn, let it stop.
[ "$(echo "$input" | jq -r '.stop_hook_active // false' 2>/dev/null)" = "true" ] && exit 0
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0
[ -f Makefile ] && grep -q '^check:' Makefile || exit 0

if ! out=$(make -s check 2>&1); then
  echo "make check failed. The task is not done until it passes:" >&2
  echo "$out" | tail -40 >&2
  exit 2
fi
exit 0
