"""Oracle: the untouched sibling call site keeps deciding permissively.

Requirement, from the packet's acceptance criteria: every path that decides
whether a record is integrated applies the same strictness rule for a closed
record. The check asks both decision paths about the one record shape the change
exists to catch - closed, carrying a merge marker, with no target-branch proof -
and requires them to agree.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import CaseOracle


@dataclass
class Record:
    status: str = "open"
    merge_marker: bool = False
    target_ref: str | None = None
    reopened: bool = False


def _integration_proven(record: Record, *, require_target_proof: bool = False) -> bool:
    if require_target_proof:
        return bool(record.target_ref)
    return bool(record.merge_marker or record.target_ref)


class _Candidate:
    """`reconcile_closed` hardened; `dependency_finalized` left as it was."""

    @staticmethod
    def reconcile_decides_integrated(record: Record) -> bool:
        return _integration_proven(
            record, require_target_proof=record.status == "closed"
        )

    @staticmethod
    def dependency_decides_integrated(record: Record) -> bool:
        return _integration_proven(record)


class _Corrected:
    """Both call sites adopt the strict mode for a closed record."""

    @staticmethod
    def reconcile_decides_integrated(record: Record) -> bool:
        return _integration_proven(
            record, require_target_proof=record.status == "closed"
        )

    @staticmethod
    def dependency_decides_integrated(record: Record) -> bool:
        return _integration_proven(
            record, require_target_proof=record.status == "closed"
        )


def _reconcile_closed(subject, records):
    """The candidate's loop, transcribed: reopen what is not proven integrated."""
    for record in records:
        if not subject.reconcile_decides_integrated(record):
            record.reopened = True
    return records


def _check(subject) -> bool:
    abandoned = Record(status="closed", merge_marker=True, target_ref=None)
    landed = Record(status="closed", merge_marker=True, target_ref="refs/heads/main")
    open_record = Record(status="open", merge_marker=True, target_ref=None)
    # Exercise the corrective action the packet's own added test asserts, not
    # only the predicates. Modelling the predicates alone let a diff whose
    # action guard was inverted - so that its stated test could never pass -
    # satisfy this oracle.
    _reconcile_closed(subject, [abandoned, landed, open_record])
    return (
        # The two decision paths must agree on the closed record.
        subject.reconcile_decides_integrated(abandoned)
        == subject.dependency_decides_integrated(abandoned)
        # ...and must agree on the answer being "not integrated".
        and subject.dependency_decides_integrated(abandoned) is False
        # A genuinely landed closed record stays integrated on both paths.
        and subject.dependency_decides_integrated(landed) is True
        # An open record keeps the permissive behaviour the contract preserves.
        and subject.dependency_decides_integrated(open_record) is True
        # The abandoned record is the one the reconcile pass must reopen.
        and abandoned.reopened is True
        and landed.reopened is False
    )


ORACLE = CaseOracle(
    case_id="dependency-strictness-propagation",
    requirement=(
        "Every path that decides whether a record is integrated applies the same "
        "strictness rule for a closed record."
    ),
    candidate=_Candidate,
    corrected=_Corrected,
    check=_check,
)
