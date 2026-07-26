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
│   ├── corpus.schema.json              corpus version metadata and case list
│   ├── expectation.schema.json         private material root causes
│   └── provenance.schema.json          origin and retention authority
├── corpus/
│   ├── corpus.json                     versions plus the case identifiers
│   ├── reviewer/PROMPT.md              shared reviewer instructions
│   ├── reviewer/<case>/packet.json     reviewer-visible artifacts
│   ├── private/expectations/<case>.json
│   └── private/provenance/<case>.json
└── artifacts/                          opt-in captured output, not in git

review-suite/scripts/evals/
├── protocol.py           versioned request/response contract, failure taxonomy
├── corpus.py             corpus loading, separation, and naming rules
├── grader.py             root-cause grading interface and reference grader
├── report.py             per-attempt records and the aggregate report
├── runner.py             fresh-process replay driver
├── audit_corpus.py       `just audit-review-corpus`
├── fixture_executor.py   deterministic simulation, never a baseline
└── claude_executor.py    documented real-runtime adapter
```

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

The report encodes no success threshold and returns no pass/fail judgement.

`--artifact-dir` retains raw executor output. It is opt-in, and
`review-suite/evals/artifacts/` is excluded from git.

## Scope and known limitations

This directory proves the protocol, the grading interface, the contamination
controls, and the failure taxonomy. It deliberately does not curate a
representative scored corpus, calibrate the grader, or capture a v1 baseline.

Two limitations are worth stating plainly for whoever curates that corpus:

- Surface matching is file-level, because a private root cause names a function
  while a finding names a line. A finding in the right file that the grader does
  not recognize is therefore reported as a partial match needing adjudication,
  not as a false positive. Calibration must decide how those are scored.
- The shipped formulations were written before any real run and were not tuned
  afterwards. A smoke evaluation through the bundled Claude adapter produced
  correct verdicts on every case while matching no formulation, so every finding
  was referred for adjudication. That is the conservative behaviour this
  interface is meant to have, and it is direct evidence that grader calibration
  is required before any recall number means anything.
