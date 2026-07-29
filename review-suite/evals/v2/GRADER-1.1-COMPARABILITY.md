# Grader `1.1`: a real defect fix, and what it breaks comparability with

This record exists because a scored measurement run under this directory (the
`s1-correctness-orchestrator` v2 re-score for #54's evidence gate) found a
genuine defect in `review-suite/scripts/evals/grader.py` mid-run, not because
any child of #51-#57 planned a grader change. It documents the fix and, per the
repository owner's explicit instruction, extends the existing
runtime/model-change comparability principle to grader-version changes: **a
`GRADER_VERSION` change creates a new, non-comparable stratum, exactly as a
runtime or model change does.**

This file does not modify `gate-manifest.json`, `DECISION-RECORD.md`,
`FAILURE-TAXONOMY.md`, or any file under `audits/` - all remain exactly as #59
delivered them.

## What changed, in one sentence

`finding_surfaces()` (surface-hit detection) read only structured `location`
fields; grader `1.1` adds `surface_named_in_prose()`, which also credits a
finding whose prose names the expected surface as a whole phrase, even when
every `location` field is a bare file path with no symbol in it.

## How this was found

While re-scoring `s1-correctness-orchestrator` post-#53 (commit `2c671fd`),
reading raw attempts directly (prompted by an independent check against this
report) showed all 5 attempts on `dependency-strictness-propagation` and all 5
on `stale-claim-release-guard` correctly, concretely, and consistently
identifying the exact expected root cause - naming the right symbol, the right
file, the right causal mechanism, and (for the traversal case) correctly
populating `consumer_impact_evidence` for both call sites. Yet every one of
these 10 attempts was graded `unexpected` (a false positive), never even
reaching `referred`.

The mechanism: `dependency_finalized`, the expectation's `surface` field, never
appeared in any attempt's `location` fields - every attempt put file paths there
(`pipeline/dependencies.py`) and named the symbol only in prose
(`` `dependency_finalized` still uses the permissive integration check ``).
`"dependencies"` (plural, from the path) is a different token than
`"dependency"` (singular, from the surface field) under the grader's
exact-token, no-stemming location matching, and `"finalized"` never appeared in
any location string at all. The equivalent-formulations list for both cases is
deliberately uncalibrated against real prose by corpus design (see
`CALIBRATION.md`), so `signal_hit` was false too - both signals false yields
`match_strength: none`, which is `unexpected`, not `partial`.

This is not new to `#53` or to this measurement: it is present in `grader.py`
since its original commit, predates every `#51`-`#57` child, and was silently
present in the frozen v1 baseline's own scoring of these same two cases (see
`s1-rescore-pre-post-comparison.md` in this directory for what that means for
v1's "confident miss" reading).

## Why the first attempted fix was wrong, and what shipped instead

The first fix folded prose tokens directly into `finding_surfaces()` as a
token-set union. It correctly fixed both real cases, but it also broke this
repository's own `probe.partial-claim-wrong-surface` calibration case
(`review-suite/evals/calibration/rollback-guidance-render.json`): that probe
deliberately places a finding at the *wrong* surface (`storectl/cli.py`, not
`render_rollback_guidance`) whose prose incidentally contains the single common
word "guidance" ("the guidance cannot run"). A token-set union credited that
coincidence as a surface hit and silently turned a calibrated `partial`
(correctly referred, not matched) into a `full` match - `just test` failed
immediately (`test_eval_calibration.py`), which is exactly what the calibration
suite exists to catch.

The shipped fix instead requires the expectation's whole `surface` string,
normalized to a phrase, to appear as a contiguous substring of the finding's
prose (`surface_named_in_prose`) - the same substring-of-normalized-text test
`_signal_match` already uses for formulations, applied to the surface field.
`"dependency finalized"` and `"release"` (the single meaningful token of
`_release`) each appear as whole phrases in the real attempts; a lone
`"guidance"` does not satisfy `"render rollback guidance"`. Both the real fix
and this precision boundary are covered by dedicated tests in
`review-suite/scripts/tests/test_eval_grader.py`
(`test_a_symbol_named_only_in_prose_is_a_surface_hit`,
`test_a_lone_common_word_shared_with_the_surface_is_not_a_surface_hit`), and the
pre-existing calibration suite continues to pass unchanged.

## Version and comparability

- `GRADER_VERSION`: `1.0` -> `1.1` (commit `50a02d1`), additive-behavior change
  (a new way to reach `surface_hit: true`; nothing that previously hit stops
  hitting).
- Every corpus's declared `grader_version` was bumped to `1.1` in the same
  commit so `runner.py`/`audit_corpus.py`'s existing version-match gate keeps
  working; no corpus content (cases, packets, expectations) changed.
- **Comparability rule, extended per the repository owner's explicit
  instruction:** exactly as "a change of runtime, runtime version, or model
  creates a new stratum" (`frozen-configuration.json`, `gate-manifest.json`), a
  change of `GRADER_VERSION` also creates a new, non-comparable stratum. A score
  computed under `1.0` - including every figure in
  `review-suite/evals/baseline/v1/` - must never be compared directly against a
  score computed under `1.1`. Any future comparison spanning this boundary must
  say so explicitly, exactly as the existing runtime/model rule already
  requires.
- `review-suite/scripts/evals/regrade.py` exists precisely to make a
  grader-version change auditable without new spend: it re-grades an
  already-captured raw attempt set (`--attempts-in` + `--artifact-dir`) with
  whatever grader is currently shipped, and its output report always records
  `configuration.regraded: true` and `configuration.regraded_grader_version`, so
  a regraded report can never be mistaken for a fresh execution under the newer
  grader.

## What this does not do

- Does not re-derive or restate v1's own frozen numbers - `baseline/v1/` is
  untouched.
- Does not decide whether v1 should be re-scored wholesale under `1.1`, or
  whether any other stratum's cases need re-examination for the same
  location-only-surface blind spot. That is a separate, larger judgment call for
  the repository owner; this record only fixes the specific defect this
  measurement's raw evidence demonstrated and states the comparability
  consequence.
