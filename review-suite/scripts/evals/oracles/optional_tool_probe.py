"""Oracle: the probe cannot detect an absent executable.

Requirement, from the packet's acceptance criteria: the suite skips these tests,
rather than failing, when the runner is absent. The check runs the probe against
an executable name that does not exist - which is what the packet says CI is -
and requires a skip rather than an error.

This is the one case in the corpus whose real counterpart was already adjudicated
by a machine: the defect survived an aggregate `clean` review verdict and CI
caught it. The oracle reproduces that judgement locally.
"""

from __future__ import annotations

import subprocess
import unittest

from . import CaseOracle

ABSENT = "taskr-executable-that-does-not-exist"


def _candidate():
    """Probe as the candidate wrote it: inspect the return code only."""

    def probe():
        if (
            subprocess.run([ABSENT, "--version"], capture_output=True, check=False)
        ).returncode != 0:
            raise unittest.SkipTest("taskr is not installed")

    return probe


def _corrected():
    """Probe that distinguishes absent from present-and-failing."""

    def probe():
        try:
            completed = subprocess.run(
                [ABSENT, "--version"], capture_output=True, check=False
            )
        except OSError as error:
            raise unittest.SkipTest(f"taskr is unavailable: {error}") from error
        if completed.returncode != 0:
            raise unittest.SkipTest("taskr is present but not runnable")

    return probe


def _check(probe) -> bool:
    """The requirement: an absent executable produces a skip, not an error."""
    try:
        probe()
    except unittest.SkipTest:
        return True
    except OSError:
        return False
    return False


ORACLE = CaseOracle(
    case_id="optional-tool-probe",
    requirement=(
        "The suite skips these tests, rather than failing, when the runner is absent."
    ),
    candidate=_candidate,
    corrected=_corrected,
    check=_check,
)
