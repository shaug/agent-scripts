set shell := ["bash", "-eu", "-o", "pipefail", "-c"]
set dotenv-load := false

skills_dir := "skills"
py_targets := "."
md_targets := "."

list-skills:
  @find {{skills_dir}} -mindepth 1 -maxdepth 1 -type d -print

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
  fi

test-prepare-changesets:
  python3 -m unittest discover -s {{skills_dir}}/prepare-changesets/scripts/tests -p 'test_*.py'

eval-prepare-changesets:
  {{skills_dir}}/prepare-changesets/scripts/evals/runner.py --skip-codex

eval-prepare-changesets-codex:
  {{skills_dir}}/prepare-changesets/scripts/evals/runner.py

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
    echo "Installing skills-ref into .venv from local cache..."; \
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
