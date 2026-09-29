# Definition of Done

Something is done only when every item is mechanically true, shown with real output, not asserted.

## Every feature
- [ ] Requirement traced to the approved spec
- [ ] No deviation from `docs/TECHNOLOGY_DECISIONS.md` (or an approved ADR exists)
- [ ] Tests written with the code and actually run; command and output shown (unit, plus E2E for user-facing flows)
- [ ] `make check` passes with zero errors and no skipped or loosened tests
- [ ] Files under 300 lines; existing components reused
- [ ] UI: all five states (loading, empty, error, no permission, success), tokens only, accessible
- [ ] API: explicit permission, validation, pagination where listing, tenant-isolation test for tenant data
- [ ] Reviewed by the `reviewer` agent (and `security-reviewer` when sensitive areas are touched); findings resolved
- [ ] No secrets in the diff; dependencies installed properly and scanned
- [ ] Docs updated (README/ADR/OpenAPI as relevant)
- [ ] Small commits with clear messages

## Every release
- [ ] All of the above, CI green, no merge conflict
- [ ] Monitoring and alerts verified with a real test alert
- [ ] Backup and restore exercised once
- [ ] Cost within the owner's budget

## Automatic "not done"
"Looks correct" with no test run · a skipped or weakened test · docs promised for later · a silent bypass of a check.
