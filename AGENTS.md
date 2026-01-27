# Agent Guidelines

This repo is a monorepo of agent skills under `skills/`.

## Working Model

- Treat each skill folder as the unit of change.
- Keep changes local to the relevant skill unless the task is clearly
  cross-cutting.
- Prefer direct, runnable scripts under each skill’s `scripts/` directory.

## Required Checks

Before every commit and push, run:

```bash
just format
just lint
just test
```

`just lint` includes `skills-ref validate` and will auto-install it into `.venv`
if missing (network required).

## Skill Conventions

- Skill root contains `SKILL.md` and optional `scripts/`, `references/`, and
  `assets/`.
- Tests live under `scripts/tests/` and should use `unittest`.
- Record intermediate record-keeping data under a skill-local dot directory (for
  example, `.skill-state/` or `.<skill-name>/`) and keep it out of git history
  via a skill-local `.gitignore`.

## Safety

- Do not use destructive git commands (e.g., `git reset --hard`) unless
  explicitly requested.
- Avoid rewriting or mutating user-specified reference branches as part of skill
  workflows.

## Git Workflow

- Use Conventional Commits for commit messages (e.g., `feat: ...`, `fix: ...`,
  `chore: ...`).

- **Changelog**

  - Maintain `CHANGELOG.md` in a daily format.
  - Create or update a section for today near the top:
    `## YYYY-MM-DD — <day summary>`.
  - Summarize the day in that heading.
  - Add one bullet per commit under the day section.
  - Format each entry as `<commit title> (<full SHA>)`.
  - Order entries with newest days first and newest commits first within a day.

- Avoid shell interpolation in commit and PR messages. Always write the full
  message to a temporary file and use file-based flags instead of inline `-m`
  strings.

  ```bash
  cat >/tmp/commit-msg.md <<'EOF'
  chore: initialize agent-scripts monorepo

  ## Summary
  - Add monorepo structure and CI

  ## Why
  - Establish consistent quality gates
  EOF
  git commit -F /tmp/commit-msg.md
  ```

  ```bash
  gh pr create --title "$TITLE" --body-file /tmp/pr-body.md
  ```

- If a ticket subject or title includes backticks, escape them as \`\`\` before
  placing the text into shell commands or temp files.

- Write commit bodies in Markdown. Summarize what changed and why it was added.
  Example of a good commit body:

  ```md
  ## Summary
  - Split eval path resolution to use `__file__`-relative paths
  - Fold `skills-ref validate` into `just lint`

  ## Why
  - Make scripts location-independent in the monorepo
  - Ensure skill validation always runs as part of lint
  ```

  Example of a bad commit body:

  ```md
  fixed stuff
  cleanups
  ```

- Push directly to `main` for small, self-contained changes.

- Use branches only for larger tasks that require multiple steps.

- When submitting a PR, rebase onto `main` first.
