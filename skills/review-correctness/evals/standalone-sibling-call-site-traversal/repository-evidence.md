# Repository evidence

Repository: `example/pipeline` Base branch: `main` Candidate head:
`6767676767676767676767676767676767676767` Comparison base:
`7676767676767676767676767676767676767676`

`AGENTS.md` requires every caller of `check_dependency` to run under strict
verification; a caller may remain in permissive mode only if AGENTS.md itself
records a dated, reasoned exception for that caller. `lib/policy.py` defines
`check_dependency`. Repository-wide search shows exactly two callers:
`lib/orchestrator.py` and `lib/legacy_importer.py`. `lib/legacy_importer.py`
calls `check_dependency(status, mode="permissive")`, an explicit override that
predates this change, is not touched by this diff, and has no exception recorded
anywhere in `AGENTS.md` — it is simply an old call site nobody has revisited.
Nearby tests in `tests/test_policy.py` assert `check_dependency` raises
`DependencyError` for a non-ready status only when `mode="strict"`.
