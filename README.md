# shaug/agent-scripts

A personal monorepo for agent skills and supporting scripts.

## Repository Layout

- `skills/` — skill folders, each containing a `SKILL.md` and bundled resources
- `review-suite/` — canonical code-review contracts, validators, and raw
  evaluation fixtures shared by repository-owned review skills
- `justfile` — common tasks for testing, validation, and formatting

Current reusable agent skills:

- `skills/babysit-pr` — monitor one existing GitHub pull request through
  current-head CI, feedback, repository-owned re-review, mergeability, and an
  explicitly authorized completion policy
- `skills/implement-ticket` — implement exactly one standalone ticket or named
  epic child through isolated execution and initial repository-owned review,
  delegate the published PR lifecycle to `babysit-pr`, then verify tracker,
  mainline, and cleanup outcomes; this is the canonical owner of generic
  single-ticket execution rules consumed by `implement-epic`
- `skills/implement-epic` — traverse live GitHub or Linear epic graphs and
  delegate each selected child to `implement-ticket`, then refresh graph state
  and verify separately authorized epic closeout
- `skills/carve-changesets` — recompose a review-ready source branch into a
  stateless chain, review each changeset through `review-code-change`, and
  delegate each published PR lifecycle to `babysit-pr`
- `skills/review-code-change` — orchestrate the repository-owned review lenses
  into one evidence-bound, deduplicated verdict
- `skills/prepare-changesets` — decompose a large, review-ready branch into a
  deterministic chain of smaller, reviewable changesets and GitHub PRs
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
    └── babysit-pr                  # published PR lifecycle
        └── review-code-change      # after a head-changing fix

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
just test-prepare-changesets
just test-review-suite
just test-babysit-pr
just test-implement-ticket
just test-implement-epic
just eval-implement-ticket
```

Validate a review packet and result together:

```bash
python3 review-suite/scripts/validate.py pair packet.json result.json
```

Run deterministic local evals without an agent runtime:

```bash
just eval-prepare-changesets
just eval-implement-ticket
```

The ticket-composition evaluator starts a fresh process for each case, with
fixture identity and grader expectations withheld. Case artifacts carry
pre-classified scenario flags (for example, a CI failure already labeled
branch-caused or infrastructure), so the harness grades obligation mapping and
terminal-state selection — not evidence classification itself. Its bundled
reference executor is a deterministic simulation of a compliant runtime, not a
model. To forward-evaluate a real agent runtime, pass its stdin/stdout JSON
adapter through `scripts/evals/run_forward.py --executor` and retain captured
observations with `--output-dir`. A Claude Code headless adapter is bundled:

```bash
just eval-implement-ticket-claude
```

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
