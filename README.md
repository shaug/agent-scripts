# shaug/agent-scripts

A personal monorepo for agent skills and supporting scripts.

## Installation

Install the plugin when you need any composed workflow. It packages all eight
skills together so stable-name dependencies such as `implement-ticket`,
`review-code-change`, and `babysit-pr` are available in the same fresh session.

### Claude Code

Add the repository marketplace, install the plugin, and start a fresh session:

```text
/plugin marketplace add shaug/agent-scripts
/plugin install agent-scripts@agent-scripts
```

The equivalent non-interactive commands are:

```bash
claude plugin marketplace add shaug/agent-scripts
claude plugin install agent-scripts@agent-scripts
```

### Codex

Codex CLI 0.117 or newer can add the repository marketplace and install the same
plugin:

```bash
codex plugin marketplace add shaug/agent-scripts
codex plugin add agent-scripts@agent-scripts
```

The repository marketplace also appears in the Codex plugin browser. Start a
fresh Codex task after installation so the complete skill set is loaded.

### Individual skills

Standalone-capable skills can still be installed independently:

```bash
npx skills add shaug/agent-scripts
```

Codex users can also invoke `$skill-installer` with this repository. Prefer the
plugin for `implement-epic`, `implement-ticket`, `babysit-pr`,
`review-code-change`, or `carve-changesets`: installing one of those entrypoints
alone intentionally leaves required stable-name dependencies unavailable and
causes the workflow to fail closed.

## Repository Layout

- `skills/` — skill folders, each containing a `SKILL.md` and bundled resources
- `review-suite/` — canonical code-review contracts, validators, raw evaluation
  fixtures, and the result-blind replay evaluator shared by repository-owned
  review skills
- `justfile` — common tasks for testing, validation, and formatting

Current reusable agent skills:

- `skills/babysit-pr` — monitor one existing GitHub pull request through
  current-head CI, feedback, repository-owned re-review, mergeability, and an
  explicitly authorized completion policy
- `skills/implement-ticket` — implement exactly one standalone ticket or named
  epic child through isolated execution and initial repository-owned review,
  publish one ordinary PR through `babysit-pr` or an explicitly authorized
  carved stack through `carve-changesets`, then verify tracker, mainline, and
  cleanup outcomes; this is the canonical owner of generic single-ticket
  execution rules consumed by `implement-epic`
- `skills/implement-epic` — traverse live GitHub or Linear epic graphs and
  delegate each selected child to `implement-ticket`, then refresh graph state
  and verify separately authorized epic closeout
- `skills/carve-changesets` — recompose a review-ready source branch into a
  stateless chain, review each changeset through `review-code-change`, and
  delegate each published PR lifecycle to `babysit-pr`
- `skills/review-code-change` — orchestrate the repository-owned review lenses
  into one evidence-bound, deduplicated verdict
- `skills/review-correctness` — find material behavioral, security,
  compatibility, data-integrity, and validation failures in a code change
- `skills/review-solution-simplicity` — challenge whole-solution machinery that
  is not justified by real requirements or repository constraints
- `skills/review-code-simplicity` — reduce local cognitive load through
  behavior-preserving reuse, DRY, control-flow, and test simplification

The composed implementation dependency chain is:

```text
implement-epic
└── implement-ticket
    ├── review-code-change          # initial candidate review
    ├── babysit-pr                  # ordinary single-PR lifecycle
    │   └── review-code-change      # after a head-changing fix
    └── carve-changesets            # authority-gated oversized path
        ├── review-code-change      # each exact changeset
        └── babysit-pr              # each changeset PR lifecycle
            └── review-code-change  # after a head-changing fix

carve-changesets
├── review-code-change              # direct per-changeset review
└── babysit-pr                      # each published PR lifecycle
    └── review-code-change          # after a head-changing fix
```

Compatible runtimes may provide named subagents or equivalent isolated
implementation and review contexts. Files under each skill's `agents/` directory
(`openai.yaml` for OpenAI runtimes, `claude-code.md` for Claude Code) are
optional discovery and adapter metadata, not part of the skills' portable
contracts.

Each review skill bundles a verbatim copy of the canonical `review-suite`
contract and schemas under its own `references/review-suite/` directory so the
skill remains self-contained when installed elsewhere. Edit only the canonical
files and refresh the copies with:

```bash
just sync-contracts
```

## Quick Start

Run the core checks:

```bash
just check
```

Run skill-specific tests:

```bash
just test-carve-changesets
just test-review-suite
just test-babysit-pr
just test-implement-ticket
just test-implement-epic
just eval-implement-ticket
just eval-implement-epic
```

Validate a review packet and result together:

```bash
python3 review-suite/scripts/validate.py pair packet.json result.json
```

Run deterministic local evaluation harnesses without an agent runtime:

```bash
just eval-carve-changesets
just eval-implement-ticket
just eval-implement-epic
```

The carve-changesets command first runs its objective integration self-test,
which checks clean-tree, plan, immutable-source, chain, equivalence, and
validation invariants. It then runs peer-shaped judgment cases through a fresh
process for each result-blind packet. The bundled executor is a deterministic
simulation of a compliant runtime, not a model evaluation. Pass any compatible
stdin/stdout JSON adapter with:

```bash
just eval-carve-changesets-executor "python3 /path/to/adapter.py"
```

The ticket-composition evaluator starts a fresh process for each case, with
fixture identity and grader expectations withheld. Its shared corpus targets
both `implement-ticket` and `implement-epic`; `just eval-implement-epic` filters
the same validated corpus to epic packets. Case artifacts carry raw, live-shaped
workflow state, including criterion-specific acceptance evidence bound to the
candidate or deployed SHA. The harness grades obligation mapping and
terminal-state selection. Its bundled reference executor is a deterministic
simulation of a compliant runtime, not a model. To forward-evaluate a real agent
runtime, pass its stdin/stdout JSON adapter through
`scripts/evals/run_forward.py --executor` and retain captured observations with
`--output-dir`. A Claude Code headless adapter is bundled:

```bash
just eval-implement-ticket-claude
```

### Result-blind review replay evaluation

`review-suite/evals/` is the canonical evaluator that measures what the review
skills actually do when a real agent runtime executes them repeatedly, rather
than asserting quality through expected JSON. It changes no review behaviour.
See [its README](review-suite/evals/README.md) for the protocol, the corpus
contract, and the grading interface.

Three commands cover it:

```bash
just test-review-suite                      # deterministic tests, no runtime
just audit-review-corpus                    # corpus integrity, no runtime
just eval-review-suite '<executor command>' # the only one that may cost money
```

`just test` includes the deterministic evaluator tests and never launches a paid
runtime. `just eval-review-suite` is deliberately absent from `test`, `lint`,
and `check`. The bundled real-runtime adapter needs the `claude` CLI on `PATH`:

```bash
just eval-review-suite "python3 review-suite/scripts/evals/claude_executor.py"
```

Each attempt starts a fresh process and receives one result-blind JSON request:
the target skill text, the raw review packet, the review contracts, and public
run identity. Expected findings, private grader labels, provenance, and even the
case name stay out of the payload, and `just audit-review-corpus` proves it by
inspecting the complete payload every case would produce. Spawn, timeout,
runtime, oversized-output, malformed, and protocol failures are reported
separately from a valid review and are never scored as clean.

The bundled `fixture_executor.py` is a deterministic simulation of a compliant
reviewer, not a model. Its runs are marked `simulation`, so no baseline report
can be produced from them. Run the runner directly for repeated attempts,
per-attempt records, and the aggregate report:

```bash
python3 review-suite/scripts/evals/runner.py \
  --executor "python3 review-suite/scripts/evals/claude_executor.py" \
  --runs 5 --report-out out/report.json
```

Cases are grouped into **strata** under `review-suite/evals/strata/`. A stratum
is the unit of valid comparison — same target skill, same declared dependency
closure, same runtime and model, same kind of ground truth — and each directory
is a complete corpus declaring its own target. `just audit-review-corpus`
discovers every one of them.

The frozen v1 baseline record lives in `review-suite/evals/baseline/v1/`: the
immutable configuration, the unscored pilot's per-stratum cost and latency
envelope, a per-stratum cost-ceiling proposal built from those numbers, the
grader calibration and adjudication record, a plan for satisfying the
two-independent-adjudication gate, the ground-truth sourcing and sanitization
record, and the baseline limitations.

Two things are deliberately still outstanding, and the configuration record says
so rather than implying otherwise: the scored strata are declared but not
populated, and no scored run may launch until the repository owner preregisters
a per-stratum cost ceiling and each private expectation has two independent
adjudications. Read
[the limitations record](review-suite/evals/baseline/v1/LIMITATIONS.md) before
quoting any figure — in particular, **the connector stratum is deferred, not
satisfied**, so connector-escape recall has never been measured and no
human-review figure may be reported as a connector figure.

## Prerequisites

- Python 3.11+
- Git
- GitHub CLI (`gh`) 2.37 or newer for PR workflows (the babysit-pr watcher
  requires `gh pr checks --json`)
- `skills-ref` on `PATH` for skill validation (optional but recommended)

## Notes

Each skill should be runnable and testable in isolation. Prefer adding tests
under the skill’s own `scripts/tests/` directory and wire them into the
`justfile`.
