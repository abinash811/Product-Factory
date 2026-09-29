---
name: debug-root-cause
description: Systematic bug fixing. Use for any bug, failing test, failing CI, or unexpected behavior, before changing code.
---
# Debug to the root cause

1. **Reproduce.** Get the exact error or a failing test. If you cannot reproduce it, say so; do not guess-fix.
2. **Gather evidence.** Read the full error, recent changes (`git log`, `git diff`), logs and request IDs. Form 1-3 hypotheses and say how each would be confirmed.
3. **Confirm the cause.** Test the most likely hypothesis with a minimal experiment. Do not stack fixes on an unconfirmed theory.
4. **Fix the cause, not the symptom.** Never suppress the error, loosen an assertion, skip a test or add a broad try/except to get green.
5. **Prove it.** Add a test that fails before the fix and passes after. Run `make check` and show the output.
6. If two attempts fail, stop, summarize what was learned, and re-plan instead of piling on changes.
