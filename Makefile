.PHONY: check
# `make check` is the single "is this done?" command. Claude's Stop hook and CI both run it.
# Later build steps add: ruff, mypy, pytest (Step 1+), eslint, tsc, vitest, playwright (Step 4+).
check:
	@bash scripts/check-file-length.sh
