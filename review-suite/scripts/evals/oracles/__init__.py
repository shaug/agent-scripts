"""Executable oracles: a second, machine adjudication of a case's materiality.

Loading is explicit rather than implicit. `oracle_module` resolves a case
identifier to its module so a missing oracle is a clear absence rather than an
import error, because most cases legitimately have none.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

ORACLE_ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class CaseOracle:
    """One case's runnable reproduction and the requirement it must satisfy.

    `corrected` is `None` for a clean-expected case: there is no root cause to
    correct, and inventing one would make the oracle assert something the
    corpus does not claim.
    """

    case_id: str
    requirement: str
    candidate: Callable[[], Any]
    check: Callable[[Any], bool]
    corrected: Callable[[], Any] | None = None


def case_ids() -> list[str]:
    """Every case identifier that ships an oracle."""
    return sorted(
        path.stem.replace("_", "-")
        for path in ORACLE_ROOT.glob("*.py")
        if path.stem != "__init__"
    )


def load(case_id: str) -> CaseOracle:
    """Return one case's oracle, failing loudly on a malformed module."""
    module = importlib.import_module(f"{__name__}.{case_id.replace('-', '_')}")
    oracle = getattr(module, "ORACLE", None)
    if not isinstance(oracle, CaseOracle):
        raise TypeError(f"{module.__name__} does not export a CaseOracle as ORACLE")
    if oracle.case_id != case_id:
        raise ValueError(f"{module.__name__} declares case_id {oracle.case_id!r}")
    return oracle
