"""Validated argv command specifications and execution."""

from __future__ import annotations

import json
import shlex
import subprocess
from typing import Any

from common import CommandError


def validate_argv(value: Any, *, label: str) -> list[str]:
    """Return a validated copy of one JSON-compatible argv array."""

    if not isinstance(value, list):
        raise CommandError(f"{label} must be a JSON array of strings.")
    if not value:
        raise CommandError(f"{label} must be a non-empty JSON array of strings.")
    if not all(isinstance(argument, str) for argument in value):
        raise CommandError(f"{label} must contain only strings.")
    if not value[0]:
        raise CommandError(f"{label} executable (argv[0]) must not be empty.")
    if any("\x00" in argument for argument in value):
        raise CommandError(f"{label} must not contain NUL bytes.")
    return list(value)


def validate_optional_argv(value: Any, *, label: str) -> list[str]:
    """Validate an argv array while allowing an explicit empty-list placeholder."""

    if isinstance(value, list) and not value:
        return []
    return validate_argv(value, label=label)


def parse_argv_json(raw: str, *, label: str) -> list[str]:
    """Parse and validate one argv array supplied as JSON."""

    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CommandError(f"{label} must be valid JSON: {exc.msg}.") from exc
    return validate_argv(value, label=label)


def display_argv(argv: Any) -> str:
    """Render argv for humans without changing what execution receives."""

    return shlex.join(validate_argv(argv, label="command argv"))


def execute_argv(
    argv: Any, *, text: bool = False, capture_output: bool = False
) -> subprocess.CompletedProcess:
    """Execute an already approved argv array without implicit shell parsing."""

    checked = validate_argv(argv, label="command argv")
    try:
        return subprocess.run(
            checked,
            shell=False,
            text=text,
            capture_output=capture_output,
            check=False,
        )
    except FileNotFoundError as exc:
        raise CommandError(f"Command not found: {checked[0]}") from exc
