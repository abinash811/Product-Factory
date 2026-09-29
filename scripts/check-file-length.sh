#!/usr/bin/env bash
# Fails if any source file is longer than MAX_LINES (default 300).
# Usage: scripts/check-file-length.sh [file ...]   (no args = every tracked/untracked source file)
# Exclusions (generated code, lockfiles, migrations) live in .file-length-ignore, one glob per line.
set -uo pipefail

MAX_LINES="${MAX_LINES:-300}"
cd "$(git rev-parse --show-toplevel 2>/dev/null || echo .)" || exit 0

is_ignored() {
  local f="$1" pattern
  [ -f .file-length-ignore ] || return 1
  while IFS= read -r pattern; do
    case "$pattern" in ''|'#'*) continue ;; esac
    # shellcheck disable=SC2254
    case "$f" in $pattern) return 0 ;; esac
  done < .file-length-ignore
  return 1
}

if [ "$#" -gt 0 ]; then
  files=("$@")
else
  mapfile -t files < <(git ls-files -co --exclude-standard -- '*.py' '*.ts' '*.tsx' '*.js' '*.jsx' '*.sh')
fi

fail=0
for f in "${files[@]}"; do
  [ -f "$f" ] || continue
  case "$f" in *.py|*.ts|*.tsx|*.js|*.jsx|*.sh) ;; *) continue ;; esac
  rel="${f#"$PWD"/}"
  is_ignored "$rel" && continue
  lines=$(wc -l < "$f")
  if [ "$lines" -gt "$MAX_LINES" ]; then
    echo "FILE TOO LONG: $rel has $lines lines (max $MAX_LINES). Split it into smaller modules." >&2
    fail=1
  fi
done
exit $fail
