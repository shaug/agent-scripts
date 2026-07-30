# Frozen configuration for the #89 discriminating-case validation

This freezes the configuration for #89's own validation run, before any of its
scored output is examined, matching every prior measurement task in this epic.
It does not modify `S1-ABLATION-MATRIX.md`, `FROZEN-V2-CONFIGURATION.md`,
`CLOSEOUT-REPORT.md`, `gate-manifest.json`, `DECISION-RECORD.md`,
`FAILURE-TAXONOMY.md`, `audits/`, or `baseline/v1/` - all remain exactly as
prior tickets delivered them. It does not touch `skills/review-correctness/`,
the traversal pass, or the verification-sufficiency pass.

## What this validates

#57's ablation matrix (`S1-ABLATION-MATRIX.md`) found that
`dependency-strictness-propagation` and `stale-claim-release-guard` - the sole
cases justifying #52's schema and #53's two passes - resolve at
`mean_combined_recall: 1.0` in every tested configuration, including the one
where the pass meant to fix each case is disabled. Neither case demonstrates
unique causal contribution. #89 sources one new, harder, disguised case per pass
and validates whether either shows a real, reproducible discriminating gap
before treating it as corpus evidence.

Two new cases, committed under
`review-suite/evals/strata/s1-correctness-orchestrator/` in the same commit as
this record:

- `artifact-promotion-environment-shortcut` - a harder sibling to
  `dependency-strictness-propagation`. The untouched sibling decision path is
  two calls deep (`resolve_rollout_environment` -> `_pick_rollout_defaults` ->
  `artifact_promotable`) rather than one direct call, and lives in a module
  named for staging/rollout defaults, not dependency or promotion checking.
- `audit-log-flush-keyword-probe` - a harder sibling to
  `stale-claim-release-guard`. The test insufficiency is carried by a mocked
  session that grants success on a keyword match in the request text, rather
  than by the test's initial state (the original case's shape), so it is less
  visually obvious on a first read.

Each case ships an executable oracle
(`review-suite/scripts/evals/oracles/artifact_promotion_environment_shortcut.py`,
`review-suite/scripts/evals/oracles/audit_log_flush_keyword_probe.py`) that
independently confirms the stated root cause: the requirement fails against the
candidate reproduction and holds once corrected. Both pass under
`python3 -m unittest review-suite.scripts.tests.test_eval_oracles`.

## Validation design: one variable changed per comparison

Per #89's own instruction, each case is scored once with its owning pass enabled
and once disabled, 5 runs each, and only kept as corpus evidence if a real,
reproducible gap appears. Reusing #57's own three configurations keeps exactly
one pass different between the two runs compared for each case, rather than
comparing configurations that differ in two passes at once:

| Case                                      | Owning pass                 | "Enabled" configuration                               | "Disabled" configuration                                | What differs                       |
| ----------------------------------------- | --------------------------- | ----------------------------------------------------- | ------------------------------------------------------- | ---------------------------------- |
| `artifact-promotion-environment-shortcut` | traversal (consumer/impact) | both passes together (real, unablated `skills/` tree) | verification-sufficiency-pass-only (traversal disabled) | traversal pass only                |
| `audit-log-flush-keyword-probe`           | verification-sufficiency    | both passes together (real, unablated `skills/` tree) | traversal-pass-only (verification-sufficiency disabled) | verification-sufficiency pass only |

Both "disabled" configurations reuse the exact overlay mechanism
`FROZEN-V2-CONFIGURATION.md` established: a fresh local mirror of this
worktree's real `skills/` tree, with `review-correctness/SKILL.md` overwritten
by the byte-identical committed content of
`review-suite/evals/v2/ablation-skill-roots/{traversal-only,verification-only}/review-correctness/SKILL.md`.
Verified byte-identical by direct `diff` immediately before each run. The "both
passes together" configuration is the real, unablated `skills/` tree with no
overlay.

## Runtime/model stratum (verified immediately before scoring)

- `runtime`: `claude` (Claude Code CLI)
- `runtime_cli_version`: `2.1.92`, verified via `claude --version` immediately
  before scoring - matches `FROZEN-V2-CONFIGURATION.md`'s own pin exactly, so
  this run's figures are runtime-comparable to every prior measurement in this
  epic.
- `model`: no `--model` flag is passed to `claude_executor.py`, the same
  invocation shape every prior ablation run in this epic used; the resolved
  model is recorded verbatim in each report's own
  `configuration.executor_models` field.

## Suite commit, corpus, and grader versions

- `suite_commit`: the commit that adds this record and the two new cases to this
  worktree's branch (recorded verbatim in each report's own
  `configuration.suite_commit` field; this file is written and committed before
  the first scored attempt, so it cannot be edited after seeing a result).
- `corpus_version`: `0.2-s1-populated` (the two new cases added to the existing
  `0.1-s1-populated` stratum; the corpus index's own `stratum.purpose` field
  records the addition).
- `grader_version`: `1.1` (unchanged; the same fixed grader every scored run in
  this epic since `GRADER-1.1-COMPARABILITY.md` uses).
- `protocol_version`: `1.0` (unchanged).

## Executor and run configuration

- `executor_command`: `python3 review-suite/scripts/evals/claude_executor.py`
- `runs_per_case`: `5`, matching every prior `s1` measurement in this epic for
  comparability.
- `timeout_seconds`: `300`, matching `FROZEN-V2-CONFIGURATION.md`'s pin for its
  own two new ablation runs.
- `max_output_bytes`: default (`4,000,000`), unchanged.
- Each run scores its own case in isolation via a scoped ephemeral corpus
  (mirroring the confirming-rerun's own method): a fresh local directory
  carrying only the one case's `reviewer/`, `private/expectations/`, and
  `private/provenance/` files, with `corpus.json`'s other fields carried
  verbatim, unedited, from the real stratum corpus committed alongside this
  record. This is a targeted validation of one new case per run, not a re-score
  of the full (now nine-case) stratum.
- `retry_policy`: none; a failed attempt is an evaluation failure and is never
  retried, unchanged from every prior measurement in this epic.

## Cost ceiling (preregistered before any scored output is examined)

- **This ticket's own hard ceiling: $5.00.**
- Sizing, per #89's own issue body: two candidate cases x two configurations x 5
  runs is 20 attempts; this stratum's real historical per-attempt cost is
  roughly $0.05-0.10 (`S1-ABLATION-MATRIX.md`'s two 35-attempt runs cost $3.560
  and $3.867, or about $0.10-0.11/attempt; the confirming rerun's 5-attempt
  single-case run cost $0.569, about $0.114/attempt). Twenty attempts at that
  rate is roughly $1.00-$2.30, so $5.00 has generous headroom without being
  sized to force a particular outcome.
- No threshold, gate value, or ceiling in this record was adjusted after seeing
  any scored output; this record is committed before the first scored attempt
  runs.

## Invalid runs, missing data, and threshold-change discipline

Unchanged from every prior measurement task in this epic: an attempt classified
`spawn_failure`/`timeout`/`runtime_failure`/`output_too_large`/
`malformed_output`/`protocol_mismatch` is never graded and never silently
retried. The discriminating-gap determination (a real, reproducible
false-positive or false-negative rate difference between the "enabled" and
"disabled" configuration for the same case) is fixed here, before this ticket
examines a single scored attempt.
