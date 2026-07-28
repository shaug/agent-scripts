# Result-blind review replay evaluation

This directory is the canonical evaluator for the repository-owned review suite.
It measures what the review skills actually do when a real agent runtime
executes them repeatedly, instead of asserting quality through expected JSON
that the same change also authored.

Review skills may reference this evaluator. They must not fork it.

The evaluator changes no review behaviour. It does not read, modify, or extend
`../CONTRACT.md`, the packet and result schemas, the lens prompts, or the
existing `../fixtures/` corpus.

## Layout

```text
review-suite/evals/
├── contracts/                          versioned evaluator schemas
│   ├── executor-request.schema.json    the complete result-blind payload
│   ├── executor-response.schema.json   the single reply an executor returns
│   ├── corpus.schema.json              versions, target closure, stratum, cases
│   ├── expectation.schema.json         private material root causes
│   ├── provenance.schema.json          origin and retention authority
│   └── calibration.schema.json         probe reviews and required classifications
├── corpus/                             the protocol-proof corpus
│   ├── corpus.json                     versions, target closure, case ids
│   ├── reviewer/PROMPT.md              shared reviewer instructions
│   ├── reviewer/<case>/packet.json     reviewer-visible artifacts
│   ├── private/expectations/<case>.json
│   └── private/provenance/<case>.json
├── strata/                             one directory per baseline stratum
│   ├── README.md                       what a stratum is, and the measured envelope
│   └── <stratum>/                      a complete corpus with its own target
├── calibration/<case_id>.json          private grader calibration probes
├── baseline/v1/                        the frozen v1 baseline record
│   ├── frozen-configuration.json       the immutable configuration
│   ├── COST-CEILING-PROPOSAL.md        per-stratum ceiling, from pilot numbers
│   ├── CALIBRATION.md                  what was calibrated, and from what
│   ├── ADJUDICATION-PLAN.md            how two independent adjudications can hold
│   ├── SOURCING.md                     ground truth, sanitization, batches
│   ├── LIMITATIONS.md                  explicit inputs to interpretation
│   └── pilot/<stratum>.report.json     the unscored pilot's compact reports
├── v2/                                 the v2 planning/definition record (#59)
│   ├── FAILURE-TAXONOMY.md             every v1 material outcome, classified
│   ├── DECISION-RECORD.md              per-mechanism evidence and disposition
│   ├── gate-manifest.json              preregistered v2 gates, before scoring
│   └── audits/                         the three graph audits (later step, empty for now)
└── artifacts/                          opt-in captured output, not in git

review-suite/scripts/evals/
├── protocol.py           versioned request/response contract, failure taxonomy
├── corpus.py             corpus loading, separation, naming, and discovery
├── grader.py             root-cause grading interface and reference grader
├── calibration.py        calibration sets and the case index they grade against
├── report.py             per-attempt records and the aggregate report
├── runner.py             fresh-process replay driver
├── audit_corpus.py       `just audit-review-corpus`
├── fixture_executor.py   deterministic simulation, never a baseline
└── claude_executor.py    documented real-runtime adapter
```

## Strata

A stratum is the unit of valid comparison: same target skill, same declared
dependency closure, same runtime and model, same kind of ground truth. Each
directory under `strata/` is a complete corpus declaring its own `target_skill`
and a `stratum` block naming its id, its ground truth, whether it is scored, and
what it is for. `just audit-review-corpus` discovers every one of them, so a
stratum added later is gated without changing the recipe.

Read [`strata/README.md`](strata/README.md) for the measured per-stratum cost
and latency envelope, and
[`baseline/v1/LIMITATIONS.md`](baseline/v1/LIMITATIONS.md) before quoting any
figure. In particular: **the connector stratum is deferred, not satisfied.**
Connector-escape recall has never been measured here, and no human-review figure
may be reported as a connector figure.

## v2 planning

[`v2/README.md`](v2/README.md) records the planning/definition gate that reads
this frozen v1 baseline and turns it into an implementation-ready decision for
the review suite's next mechanisms, before any scored v2 output exists. It
changes no review prompt, schema, rubric, orchestration, or caller runtime
behavior by itself.

## Calibration

An uncalibrated grader does not report a conservative score; it reports a
meaningless one, because matching is containment on normalised text.
Formulations are therefore calibrated against prose a real reviewer actually
returned — from the unscored pilot only, never from scored output — and
`review-suite/scripts/tests/test_eval_calibration.py` replays committed probe
reviews through the real grader to assert the classification each must receive.
Calibration probes every boundary: paraphrase, overlapping symptom, duplicate
report, partial claim, plausible false positive, and accepted non-finding.

See [`baseline/v1/CALIBRATION.md`](baseline/v1/CALIBRATION.md) for what was
calibrated, what it measured before and after, and what remains un-adjudicated,
and [`baseline/v1/ADJUDICATION-PLAN.md`](baseline/v1/ADJUDICATION-PLAN.md) for
how the two-independent-adjudication gate can honestly be satisfied — including
why a blind agent context sharing a model family with the evaluated reviewer is
not a legitimate second adjudicator for whether a defect is materially real.

## Commands

```bash
just test-review-suite                      # deterministic tests, no runtime
just audit-review-corpus                    # corpus integrity, no runtime
just eval-review-suite '<executor command>' # the only command that may cost money
```

`just test` includes the deterministic evaluator tests and never launches a paid
runtime. `just eval-review-suite` is deliberately absent from `test`, `lint`,
and `check`.

The bundled real-runtime adapter needs the `claude` CLI on `PATH`:

```bash
just eval-review-suite "python3 review-suite/scripts/evals/claude_executor.py"
```

The runner accepts `--runs N` for repeated attempts, `--timeout`,
`--max-output-bytes`, `--artifact-dir`, `--attempts-out`, `--report-out`, and
`--baseline-report`. Run it directly when you need those options:

```bash
python3 review-suite/scripts/evals/runner.py \
  --executor "python3 review-suite/scripts/evals/claude_executor.py" \
  --runs 5 --report-out out/report.json
```

## Executor protocol

One attempt is one fresh process. The runner writes a single JSON request to
stdin and reads a single JSON response from stdout. `protocol_version` is `1.0`.

The request carries the target skill name, a digest pinning the exact skill
text, the reviewer-visible instructions, the raw review packet, the bundled
review contracts, and public run metadata: an opaque case reference, the run
number, the suite commit, the corpus version, the exact candidate and
comparison-base identity, and a start timestamp.

### The evaluated skill is a closure, not a file

`corpus.json` declares `target_skill` plus `target_skill_dependencies`, and the
payload ships that whole closure: each skill's `SKILL.md` and every Markdown
file under its `references/`, excluding the bundled `review-suite/` mirror that
`contract_documents` already supplies canonically. Every section is labelled,
and the target's own `SKILL.md` is labelled `## Target skill:` so a reviewer can
tell which skill it is being asked to execute.

This is load-bearing rather than tidy. `review-code-change` instructs its
reviewer to verify that `review-solution-simplicity`, `review-correctness`, and
`review-code-simplicity` are available and readable, and to return an aggregate
`blocked` result naming any that are missing. An executor is told to reason only
from what it is given. Ship the target alone and a fully compliant reviewer must
refuse every case, so recall and false-clean rates move the *wrong* way as the
reviewer becomes *more* compliant — the measurement inverts. Earlier revisions
had exactly that defect. Supplying the closure removes the inversion; it does
not by itself make any single case answer correctly, and the recorded runs below
show that case still varying between runs.

`target_skill_digest` hashes the rendered closure, so it changes when any part
of any included skill changes. Loading fails closed when a declared skill is
absent, duplicated, or names the target itself.

Which target a *scored* corpus should measure, which strata it contains, and the
cost envelope that follows from the closure's size are corpus-composition
decisions and are deliberately not settled here.

The request never carries expected findings, private labels, prior conclusions,
suspected issues, implementation transcripts, or the case name.

The response reports `outcome` as `review_result`, `blocked`, or
`runtime_failure`, plus `simulation`, executor identity, and optional usage. The
runner classifies each attempt into exactly one status:

| status              | meaning                                           |
| ------------------- | ------------------------------------------------- |
| `spawn_failure`     | the executor command could not start              |
| `timeout`           | the executor outlived `--timeout`                 |
| `runtime_failure`   | non-zero exit, or a self-reported runtime failure |
| `output_too_large`  | stdout exceeded `--max-output-bytes`              |
| `malformed_output`  | unparseable, schema-invalid, or wrongly bound     |
| `protocol_mismatch` | the reply declared another protocol version       |
| `blocked`           | a valid review that refuses a merge verdict       |
| `review_result`     | a valid, candidate-bound review                   |

The first six are evaluation failures. They are reported separately, are never
graded, and can never appear as a clean review. A malformed review result is an
evaluation failure, not a missed finding.

Classification judges the reply, never the packet. `corpus.py` has already
established each packet's validity before anything launches, so a packet defect
is a deliberate property of the case rather than news about the executor, and it
is never charged to the executor. That matters for a `packet_valid: false` case:
a reviewer that wrongly issues a merge verdict on incomplete evidence is
classified `review_result` and graded as the wrong answer it is, instead of
disappearing into `malformed_output`.

Only `review_result` attempts are graded, because a `blocked` review declines to
give a merge verdict and so has nothing to score against. A `blocked` attempt is
still a valid review and still counts toward stability. The runner's exit status
reports evaluation integrity, never review quality: `0` when every attempt
produced a valid outcome, `1` when any attempt failed the protocol, `2` when the
configuration or corpus was rejected before any launch.

## Corpus and expectation contract

Three separately validated locations keep the reviewer away from the answer:

- `reviewer/` holds only the shared prompt and each case's `packet.json`;
- `private/expectations/` holds the material root causes and accepted
  non-findings; and
- `private/provenance/` holds origin, retention authority, and sanitization.

A case identifier and every reviewer-visible filename must describe the subject
matter, never the outcome. `corpus.py` rejects names containing verdict,
severity, failure-class, or disposition words. The payload additionally carries
only an opaque `c-<hash>` case reference, so even a badly named case cannot leak
through a request.

`just audit-review-corpus` builds the complete request each case would produce
and rejects it both structurally, by permitting an exact key set, and textually,
by searching for private expectation and provenance text. Three fields are
deliberately exempt from the text search because banning them would ban the
packet or the contracts themselves: a root cause's `requirement` normally
restates a reviewer-visible acceptance criterion, its `surface` is a
reviewer-visible code location, and `expected_verdict`, `severity`, and `origin`
are closed public vocabularies that the bundled contracts spell out in full.
Those three stay private structurally instead, because the expectation file is
never part of a request.

Loading fails closed. A missing expectation, a missing provenance record, a
schema violation, an orphaned file, a packet whose validity disagrees with its
expectation, or a grader-version mismatch is an error before any process starts.

## Grading interface

A reviewer is graded on material root causes, not prose. Each root cause states
its requirement, triggering condition, affected surface, material consequence,
severity, and the formulations a competent reviewer may use. An observed finding
matches when it points at the affected surface *and* describes the root cause in
an accepted way. One signal alone is a partial match, and a finding that fully
matches two root causes is ambiguous; both are referred for adjudication rather
than silently scored either way. `accepted_non_findings` describe observations
that are tolerated without counting as false positives.

The reference grader is protocol proof. It is not calibrated, and its output is
not a v1 score.

## Simulation and baselines

`fixture_executor.py` hand-codes the review a compliant reviewer would return
for each synthetic packet, so the protocol, failure taxonomy, grading interface,
and reporting are deterministically testable for free. It is a simulation, not a
model evaluation, and it cannot detect a model misreading the review contract.

Two independent controls keep a simulation out of any baseline: every fixture
response sets `"simulation": true`, and the runner forces the flag whenever the
bundled fixture executor is the command, regardless of what the reply claims. An
aggregate report whose `simulation` is true reports `baseline_eligible: false`,
and `--baseline-report` refuses to write a file for it.

## Reporting

`--attempts-out` writes one JSON record per attempt. `--report-out` writes the
aggregate report, which represents material-finding recall, false-clean rate,
false-positive rate, false-alarm rate, unique finding contribution, verdict and
finding stability, every failure-status rate, latency, and whatever usage and
cost the executor reported. Every rate and every stability figure is published
with its denominator so a small run count is not mistaken for a precise
capability measurement.

Stability spans every attempt that produced a valid review, `blocked` ones
included, and is computed per case before being averaged. Pooling verdicts
across unlike cases would report disagreement between cases as instability
within one, and dropping `blocked` attempts would report a reviewer that refuses
a verdict on one run and issues one on the next as perfectly stable.

The report's `configuration` block states what was run: executor command, target
skill, its declared dependencies, the exact closure document list, the closure
digest, suite commit, corpus and grader versions, run count, and the timeout and
output limits. Each attempt repeats the target, its dependencies, and the
digest, so a per-attempt record is self-describing without its report.

The report encodes no success threshold and returns no pass/fail judgement.

`--artifact-dir` retains raw executor output. It is opt-in, and
`review-suite/evals/artifacts/` is excluded from git.

### Usage accounting

An adapter reports `input_tokens`, `output_tokens`, and `cost_usd`. Two details
of the Claude adapter generalize to any cached runtime and matter to anyone
freezing a cost envelope:

- Input tokens total every input-side field the runtime reports, including cache
  creation and cache read. Under prompt caching the uncached `input_tokens`
  residue is tiny — a measured 16,456-token prompt reported `input_tokens: 2` —
  so counting only that field understates real input by orders of magnitude.
- Model identity is required, not optional. Headless output carries no top-level
  `model` string; it reports `modelUsage` as a mapping keyed by model id. The
  adapter resolves the model from that mapping, falls back to `--model`, and
  returns `runtime_failure` rather than recording an attempt that cannot name
  the model that answered, because a stratum without a model is not comparable.

## Scope and known limitations

This directory proves the protocol, the grading interface, the contamination
controls, and the failure taxonomy. It now also carries the stratum layout, the
per-stratum unscored pilot envelope, the grader calibration machinery, and the
frozen v1 configuration record.

It still does **not** carry a populated scored corpus or a captured v1 baseline.
`baseline/v1/frozen-configuration.json` declares three scored strata in state
`declared_unpopulated`, and its `status` is
`incomplete_pending_owner_preregistration`: the per-stratum cost ceiling must be
preregistered by the repository owner before any scored output is examined, and
each private expectation needs two independent adjudications from genuinely
separate parties. Neither can come from an implementing context.
[`baseline/v1/SOURCING.md`](baseline/v1/SOURCING.md) records the population
batches and the ground truth already identified for every required case class.

### Protocol smoke evaluation

> **This run proves the protocol end to end and nothing else.** It is not
> evidence of reviewer capability, review quality, or cost, and must not be
> cited as any of those here or downstream. Its numbers are here to show that
> the fields exist, are populated, and are internally consistent — that an
> attempt is classified, graded, and recorded with identity, usage, and latency.
> One run per case cannot measure a stochastic reviewer, and no cost envelope
> follows from it.

One run per case through the bundled Claude adapter, recorded at suite commit
`62a9ed8fab166c7d380724e426449f0585714b07`, target `review-code-change` with
declared closure `review-solution-simplicity`, `review-correctness`,
`review-code-simplicity` and digest `9b2805f14cdd6158`, model
`claude-opus-4-6[1m]`, corpus version `0.1-protocol-proof`, grader version
`1.0`:

- 6 attempts, 6 valid protocol outcomes, 0 evaluation failures, all 6 graded;
- 5 of 6 verdicts matched. `catalog-import-feed` returned `changes_required`
  where `blocked` was expected — a merge verdict on a packet whose required
  full-scope validation evidence is absent;
- 8 findings reported. 7 were referred for adjudication because none matched a
  shipped formulation, and 1 was recorded as an unexpected gating finding,
  giving `false_positive_rate` 0.1667 over 6;
- `material_finding_recall` 0.0 over the 4 attempts with expected root causes;
  `false_clean_rate` 0.0 over 4;
- usage and latency were populated rather than dropped: 191,422 input tokens,
  8,051 output tokens, 1.03 USD reported, 33.0 s mean and 59.9 s maximum
  latency, and a model identity on every attempt.

The verdicts above are demonstrably not repeatable. The immediately preceding
run of this same configuration returned `blocked` on `catalog-import-feed` — the
correct answer — while this one returned a merge verdict. That case is the one
testing refusal on incomplete evidence, which is the behaviour the surrounding
work most needs to measure, and it flipped between two consecutive runs. Every
stability figure here rests on a denominator of 1. Use `--runs N`, and read the
result as a measurement only once the denominator supports it.

### Limitations for whoever curates the scored corpus

The first two of these have since been measured rather than predicted; see
[`baseline/v1/LIMITATIONS.md`](baseline/v1/LIMITATIONS.md) for what the pilot
found and what it cost to fix.

- Surface matching is file-level, because a private root cause names a function
  while a finding names a line. A finding in the right file that the grader does
  not recognize is therefore reported as a partial match needing adjudication,
  not as a false positive. Calibration must decide how those are scored. The
  pilot showed the sharper form of this: a surface written as a path prefix
  shares a token with almost every location in a packet, and made a deliberately
  wrong gating finding an unfalsifiable partial. Write a surface as the smallest
  identifying symbol.

- The shipped formulations were written before any real run and were not tuned
  afterwards, which is why recall is 0.0 above. That is the conservative
  behaviour this interface is meant to have, and it means grader calibration is
  required before any recall number means anything.

  The scale of it has since been measured, on this ticket's own pilot rather
  than against the void smoke figure above, which cannot anchor a comparison.
  Two cases in one 20-attempt batch, differing only in whether their
  formulations had ever been confronted with real prose: the calibrated case
  scored recall 1.0 over five attempts with zero false positives and zero
  referrals, and the deliberately uncalibrated one scored recall 0.0 over five
  attempts with ten referrals, while the reviewer gated the change every time in
  both. An uncalibrated expectation reports a number about itself.

- Completeness of the evaluated skill closure is load-bearing, not incidental.
  Earlier revisions omitted first the orchestration protocol and then the three
  lens skills that `review-code-change` requires; each omission changed observed
  behaviour on the incomplete-evidence case. Any change to what a payload
  carries is a change to what is being measured, and starts a new stratum. Every
  run records its closure's membership and digest so a stratum can state what it
  evaluated.

- The choice of scored target, the strata to compare, and the cost envelope to
  preregister all follow from that closure and are deliberately left open. Size
  the envelope from a preregistered run of the chosen closure; do not
  extrapolate it from the protocol smoke run above.

- `expectation.schema.json` requires a `severity` on every root cause that no
  metric currently consumes. Either score severity agreement or drop the
  requirement; do not assume it is being measured.
