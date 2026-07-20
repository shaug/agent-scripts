# shaug/agent-scripts

A personal monorepo for agent skills and supporting scripts.

## Repository Layout

- `skills/` — skill folders, each containing a `SKILL.md` and bundled resources
- `review-suite/` — canonical code-review contracts, validators, and raw
  evaluation fixtures shared by repository-owned review skills
- `justfile` — common tasks for testing, validation, and formatting

Current skills:

- `skills/implement-epic-sequence` — execute GitHub or Linear epics through
  dependency-aware implementation, review, merge, cleanup, and closeout
- `skills/prepare-changesets` — decompose a large, review-ready branch into a
  deterministic chain of smaller, reviewable changesets and GitHub PRs

## Quick Start

Run the core checks:

```bash
just check
```

Run skill-specific tests:

```bash
just test-prepare-changesets
just test-review-suite
```

Validate a review packet and result together:

```bash
python3 review-suite/scripts/validate.py pair packet.json result.json
```

Run deterministic local evals (no Codex required):

```bash
just eval-prepare-changesets
```

## Prerequisites

- Python 3.11+
- Git
- GitHub CLI (`gh`) for PR workflows
- `skills-ref` on `PATH` for skill validation (optional but recommended)

## Notes

Each skill should be runnable and testable in isolation. Prefer adding tests
under the skill’s own `scripts/tests/` directory and wire them into the
`justfile`.
