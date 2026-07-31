# Review-fix-loop evaluations

Issue #101's cross-cutting, result-blind evaluation corpus for the standalone
`review-fix-loop` skill. It does not replace
`scripts/tests/test_local_commit.py` or `scripts/tests/test_update_pr.py` —
those remain the capability-owned unit suites for issues #99/#100. This corpus
instead proves the skill's whole behavioral contract across both publication
policies, from externally observable Git evidence rather than the returned
terminal-result document's own claims.

## Where the corpus lives

Every other evaluated skill in this repository (`carve-changesets`,
`implement-ticket`, `babysit-pr`) keeps its scenario data in this directory as
`cases.json`/`expectations.json`, because each of their scenarios is a short
natural-language situation description handed to an agent-shaped executor for
judgment. `review-fix-loop` has no equivalent judgment surface to evaluate that
way: its actual behavior is the deterministic Python engine in
`../scripts/local_commit.py` and `../scripts/update_pr.py`, and the three
genuinely host-boundary actions (`reviewer`, `decide`, `apply_fix`) are already
exercised with scripted fixtures by the capability-owned unit suites. A JSON
case format here would either duplicate that fixture plumbing or describe
scenarios too shallowly to build the real Git repositories, disposable bare
remotes, and interleaved-clone races several scenarios require.

The corpus is therefore a registry of plain Python scenario functions in
`../scripts/evals/corpus.py` (`CORPUS.SCENARIOS`/`CORPUS.SCENARIOS_BY_ID`), each
of which drives the real engine against a real temporary repository and reports
a `checks` mapping of independently-derived Git evidence for
`../scripts/evals/grader.py` to diff. This directory still exists, per the
repository's convention that every evaluated skill keeps its evaluation
documentation and data under `evals/`, and is the place to look for what this
corpus asserts and why.

## Running it

```bash
just eval-review-fix-loop            # run the whole corpus once
python3 scripts/evals/runner.py --list                 # list scenario ids
python3 scripts/evals/runner.py --scenario lc_converged_after_one_fix
python3 scripts/evals/runner.py --output-dir /tmp/out   # per-scenario JSON reports
```

No subprocess boundary and no model call is involved: every scenario is an
in-process, deterministic replay, so the whole corpus is free and safe to run in
repository CI. `scripts/tests/test_evals.py` already runs it under `just test`;
`eval-review-fix-loop` is the standalone entry point for ad hoc runs and
per-scenario reports.

## Scope

The corpus mirrors this ticket's own "Scope" bullet list: convergence, repeated
findings, invalid reviews, declined findings, budget exhaustion, interruption,
recovery, validation failure, reviewer mutation, and publication races — across
both `local_commit` and `update_pr` — plus fresh-subagent defaults and the
explicit in-agent override. It deliberately does not add dedicated
`oscillation`/`repeated_failed_attempt` scenarios: those `changes_remaining`
reasons are already covered by `scripts/tests/test_local_commit.py`.

## Result-blindness

`grader.grade_case` never trusts a scenario's returned terminal-result document
by itself. Each scenario's `checks` mapping compares the terminal contract's own
declared fields (`terminal_state`, `reason`) *and* a set of facts computed
independently by asking Git directly — a real commit count, a real file's
content at a real commit, a real remote ref, a real object's reachability, a
real dirty-worktree listing — so a result that lies about what happened
disagrees with the evidence rather than being trusted.
`scripts/tests/test_evals.py`'s `SeededFaultDemonstrationTests` demonstrates
this directly: a fabricated "converged" claim with no matching Git evidence, and
a deliberately unfixable fixture declared to converge, are both rejected.
