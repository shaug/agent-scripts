"""Oracle: every attempt produces exactly one attributable retained artifact.

Requirements, from the packet's acceptance criteria: every attempt produces
exactly one retained artifact, and the artifacts are attributable to the executor
that produced them. Both hold. What does *not* hold is anything about
operating-system process identity - the packet states the suite cannot observe a
process identifier at all - which is why the observation that the test's name
overstates its assertion was dispositioned as immaterial rather than as a defect.

Clean-expected, so there is no `corrected` leg. Note what this oracle cannot do:
it cannot adjudicate whether the *name* is misleading, because that is a
judgement about prose. It adjudicates only that the stated requirements hold.
"""

from __future__ import annotations

from . import CaseOracle

EXECUTOR_NAME = "bundled-executor"


def _candidate():
    """Two attempts, each writing one retained artifact."""
    artifacts = {}
    records = []
    for run_number in (1, 2):
        records.append({"run_number": run_number})
        artifacts[f"attempt.run-{run_number}.stdout.json"] = {
            "executor": {"name": EXECUTOR_NAME}
        }
    return records, artifacts


def _check(result) -> bool:
    records, artifacts = result
    names = {doc["executor"]["name"] for doc in artifacts.values()}
    return len(records) == len(artifacts) and names == {EXECUTOR_NAME}


ORACLE = CaseOracle(
    case_id="process-isolation-assertion",
    requirement=(
        "Every attempt produces exactly one retained artifact, and the artifacts "
        "are attributable to the executor that produced them."
    ),
    candidate=_candidate,
    check=_check,
)
