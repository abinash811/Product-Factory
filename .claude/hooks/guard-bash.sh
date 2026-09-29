#!/usr/bin/env bash
# PreToolUse(Bash): block a few destructive or rule-breaking commands. Exit 2 = blocked.
# Not a security boundary (a determined prompt injection can route around it); CI is the real backstop.
set -uo pipefail
cmd=$(jq -r '.tool_input.command // ""' 2>/dev/null)

block() { echo "BLOCKED by Product Factory guardrail: $1" >&2; exit 2; }

echo "$cmd" | grep -Eq '(^|[;&|[:space:]])rm[[:space:]]+(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r)[[:space:]]+(/|~|\.|\*)([[:space:]]|$)' \
  && block "recursive force-delete of a root/home/current directory."
echo "$cmd" | grep -Eq 'git[[:space:]]+push.*(--force|-f)([[:space:]]|$)' \
  && block "force-push needs the product owner's explicit approval."
echo "$cmd" | grep -Eq 'git[[:space:]]+push[[:space:]]+[^ ]+[[:space:]]+(HEAD:)?(main|master)([[:space:]]|$)' \
  && block "never push directly to main. Use a branch and a pull request."
echo "$cmd" | grep -Eq -- '--no-verify' \
  && block "skipping git hooks is not allowed. Fix the failing check instead."
exit 0
