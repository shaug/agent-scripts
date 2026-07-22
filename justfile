set shell := ["bash", "-eu", "-o", "pipefail", "-c"]
set dotenv-load := false

skills_dir := "skills"
py_targets := "."
md_targets := "."

list-skills:
  @find {{skills_dir}} -mindepth 1 -maxdepth 1 -type d -print

# Refresh the review-suite contract copies bundled into each review skill so
# the skills stay self-contained when installed outside this repository.
sync-contracts:
  @for skill in review-code-change review-correctness review-code-simplicity review-solution-simplicity; do \
    dest="{{skills_dir}}/$skill/references/review-suite"; \
    mkdir -p "$dest"; \
    cp review-suite/CONTRACT.md "$dest/CONTRACT.md"; \
    cp review-suite/contracts/review-packet.schema.json "$dest/review-packet.schema.json"; \
    cp review-suite/contracts/review-result.schema.json "$dest/review-result.schema.json"; \
    cp review-suite/scripts/validate.py "$dest/validate.py"; \
    echo "Synced $dest"; \
  done

test:
  @found=0; \
  for tests in {{skills_dir}}/*/scripts/tests; do \
    if [ -d "$tests" ]; then \
      found=1; \
      echo "Running tests in $tests"; \
      python3 -m unittest discover -s "$tests" -p 'test_*.py'; \
    fi; \
  done; \
  if [ "$found" -eq 0 ]; then \
    echo "No skill tests found under {{skills_dir}}/*/scripts/tests"; \
  fi; \
  if [ -d review-suite/scripts/tests ]; then \
    echo "Running tests in review-suite/scripts/tests"; \
    python3 -m unittest discover -s review-suite/scripts/tests -p 'test_*.py'; \
  fi

test-review-suite:
  python3 -m unittest discover -s review-suite/scripts/tests -p 'test_*.py'

test-babysit-pr:
  python3 -m unittest discover -s {{skills_dir}}/babysit-pr/scripts/tests -p 'test_*.py'

test-implement-ticket:
  python3 -m unittest discover -s {{skills_dir}}/implement-ticket/scripts/tests -p 'test_*.py'

eval-implement-ticket:
  python3 {{skills_dir}}/implement-ticket/scripts/evals/run_forward.py

# Real-runtime forward evaluation; requires the `claude` CLI on PATH.
eval-implement-ticket-claude:
  python3 {{skills_dir}}/implement-ticket/scripts/evals/run_forward.py \
    --executor "python3 {{skills_dir}}/implement-ticket/scripts/evals/claude_executor.py"

test-implement-epic:
  python3 -m unittest discover -s {{skills_dir}}/implement-epic/scripts/tests -p 'test_*.py'

test-carve-changesets:
  python3 -m unittest discover -s {{skills_dir}}/carve-changesets/scripts/tests -p 'test_*.py'

eval-carve-changesets:
  python3 {{skills_dir}}/carve-changesets/scripts/evals/runner.py --integration-self-test
  python3 {{skills_dir}}/carve-changesets/scripts/evals/runner.py

# Forward-evaluate through any fresh-process stdin/stdout JSON adapter.
eval-carve-changesets-executor executor:
  python3 {{skills_dir}}/carve-changesets/scripts/evals/runner.py --executor "{{executor}}"

validate-skills: lint-skills

fmt-py:
  @if command -v ruff >/dev/null 2>&1; then \
    ruff check --select I,RUF022 --fix {{py_targets}}; \
    ruff format {{py_targets}}; \
  else \
    echo "ruff not found on PATH; skipping Python formatting"; \
  fi

fmt-md:
  @if command -v mdformat >/dev/null 2>&1; then \
    md_files="$(find {{md_targets}} -type f -name '*.md' \
      -not -path '*/.venv/*' \
      -not -path '*/.git/*' \
      -not -path '*/.tools/*')"; \
    if [ -n "$md_files" ]; then \
      mdformat --wrap 80 $md_files; \
    fi; \
  else \
    echo "mdformat not found on PATH; skipping Markdown formatting"; \
  fi

lint-py:
  @if command -v ruff >/dev/null 2>&1; then \
    ruff check {{py_targets}}; \
  else \
    echo "ruff not found on PATH; skipping Python lint"; \
  fi

lint-md:
  @if command -v mdformat >/dev/null 2>&1; then \
    md_files="$(find {{md_targets}} -type f -name '*.md' \
      -not -path '*/.venv/*' \
      -not -path '*/.git/*' \
      -not -path '*/.tools/*')"; \
    if [ -n "$md_files" ]; then \
      mdformat --check --wrap 80 $md_files; \
    fi; \
  else \
    echo "mdformat not found on PATH; skipping Markdown lint"; \
  fi

lint-skills:
  @set -euo pipefail; \
  AGENTSKILLS_DIR=".tools/agentskills"; \
  SKILLS_REF_BIN=""; \
  install_skills_ref() { \
    echo "Installing skills-ref: recreating .venv and cloning agentskills from GitHub (network required)..."; \
    rm -rf .venv; \
    python -m venv .venv; \
    mkdir -p .tools; \
    rm -rf "$AGENTSKILLS_DIR"; \
    git clone https://github.com/agentskills/agentskills.git "$AGENTSKILLS_DIR"; \
    .venv/bin/pip install --upgrade pip; \
    .venv/bin/pip install -e "$AGENTSKILLS_DIR/skills-ref"; \
    SKILLS_REF_BIN=".venv/bin/skills-ref"; \
  }; \
  if command -v skills-ref >/dev/null 2>&1; then \
    SKILLS_REF_BIN="$(command -v skills-ref)"; \
    if ! "$SKILLS_REF_BIN" --help >/dev/null 2>&1; then \
      SKILLS_REF_BIN=""; \
    fi; \
  fi; \
  if [ -z "$SKILLS_REF_BIN" ] && [ -x .venv/bin/skills-ref ]; then \
    SKILLS_REF_BIN=".venv/bin/skills-ref"; \
    if ! "$SKILLS_REF_BIN" --help >/dev/null 2>&1; then \
      SKILLS_REF_BIN=""; \
    fi; \
  fi; \
  if [ -z "$SKILLS_REF_BIN" ]; then \
    install_skills_ref; \
  fi; \
  "$SKILLS_REF_BIN" --help >/dev/null; \
  for skill in {{skills_dir}}/*; do \
    if [ -d "$skill" ]; then \
      echo "Validating $skill"; \
      "$SKILLS_REF_BIN" validate "$skill"; \
    fi; \
  done

lint: lint-py lint-md lint-skills

format: fmt-py fmt-md

check: test lint
