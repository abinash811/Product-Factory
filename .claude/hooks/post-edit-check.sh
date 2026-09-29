#!/usr/bin/env bash
# PostToolUse(Edit|Write): format + lint the edited file, and enforce the 300-line rule.
# Mechanical only. Tools that are not installed yet are skipped (they arrive in later build steps).
set -uo pipefail
path=$(jq -r '.tool_input.file_path // ""' 2>/dev/null)
[ -n "$path" ] && [ -f "$path" ] || exit 0
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0

fail=0
case "$path" in
  *.py)
    if command -v ruff >/dev/null 2>&1; then
      ruff format -q "$path" >/dev/null 2>&1
      ruff check "$path" || fail=1
    fi ;;
  *.ts|*.tsx|*.js|*.jsx|*.json|*.css|*.md)
    if [ -x node_modules/.bin/prettier ]; then node_modules/.bin/prettier --write "$path" >/dev/null 2>&1; fi
    case "$path" in
      *.ts|*.tsx|*.js|*.jsx)
        if [ -x node_modules/.bin/eslint ]; then node_modules/.bin/eslint --quiet "$path" || fail=1; fi ;;
    esac ;;
esac

bash scripts/check-file-length.sh "$path" || fail=1
[ "$fail" -eq 0 ] || { echo "Fix the problems above before continuing." >&2; exit 2; }
exit 0
