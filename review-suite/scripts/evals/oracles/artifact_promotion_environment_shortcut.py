"""Oracle: the rollout-environment path still decides promotion permissively.

Requirement, from the packet's acceptance criteria: every path that decides
whether an artifact counts as promoted applies the same mandatory-verification
rule once verification is required. The check drives the exact artifact shape
the change exists to catch - verification required, carrying a promotion
marker, no ledger proof - through both the hardened gate path and the two-hop
rollout path (`resolve_rollout_environment` -> `_pick_rollout_defaults` ->
`artifact_promotable`), and requires them to agree.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import CaseOracle


@dataclass
class Artifact:
    verification_required: bool = False
    promotion_marker: bool = False
    external_ref: str | None = None
    held: bool = False


class _Proof:
    def __init__(self, verified: bool):
        self.verified = verified


class _Ledger:
    """Confirms only the artifact whose external ref names a settled release."""

    def lookup(self, external_ref):
        if external_ref is None:
            return None
        return _Proof(verified=external_ref == "rel-confirmed")


def _artifact_promotable(artifact: Artifact, *, external_proof=None) -> bool:
    if external_proof is not None:
        return bool(external_proof.verified)
    return bool(artifact.promotion_marker or artifact.external_ref)


class _Candidate:
    """`decide_promotion` hardened; the rollout path left exactly as it was."""

    @staticmethod
    def gate_decides_promoted(artifact: Artifact, ledger: _Ledger) -> bool:
        proof = (
            ledger.lookup(artifact.external_ref)
            if artifact.verification_required
            else None
        )
        return _artifact_promotable(artifact, external_proof=proof)

    @staticmethod
    def rollout_decides_promoted(artifact: Artifact) -> bool:
        # `_pick_rollout_defaults`, unmodified: no `external_proof` is ever passed.
        return _artifact_promotable(artifact)


class _Corrected:
    """Both paths adopt the ledger-proof requirement."""

    @staticmethod
    def gate_decides_promoted(artifact: Artifact, ledger: _Ledger) -> bool:
        proof = (
            ledger.lookup(artifact.external_ref)
            if artifact.verification_required
            else None
        )
        return _artifact_promotable(artifact, external_proof=proof)

    @staticmethod
    def rollout_decides_promoted(artifact: Artifact) -> bool:
        ledger = _Ledger()
        proof = (
            ledger.lookup(artifact.external_ref)
            if artifact.verification_required
            else None
        )
        return _artifact_promotable(artifact, external_proof=proof)


def _decide_promotion(subject, artifact: Artifact, ledger: _Ledger) -> None:
    if not subject.gate_decides_promoted(artifact, ledger):
        artifact.held = True


def _check(subject) -> bool:
    ledger = _Ledger()
    unverified = Artifact(
        verification_required=True, promotion_marker=True, external_ref="rel-9"
    )
    verified = Artifact(
        verification_required=True,
        promotion_marker=True,
        external_ref="rel-confirmed",
    )
    not_required = Artifact(
        verification_required=False, promotion_marker=True, external_ref=None
    )

    _decide_promotion(subject, unverified, ledger)
    _decide_promotion(subject, verified, ledger)

    return (
        # The two decision paths must agree on the unverified artifact.
        subject.rollout_decides_promoted(unverified)
        == subject.gate_decides_promoted(unverified, ledger)
        # ...and must agree the answer is "not promoted".
        and subject.gate_decides_promoted(unverified, ledger) is False
        # A genuinely ledger-confirmed artifact stays promoted on both paths.
        and subject.rollout_decides_promoted(verified) is True
        # An artifact that does not require verification keeps the permissive
        # behaviour the contract preserves.
        and subject.rollout_decides_promoted(not_required) is True
        # The unverified artifact is the one the gate must hold.
        and unverified.held is True
        and verified.held is False
    )


ORACLE = CaseOracle(
    case_id="artifact-promotion-environment-shortcut",
    requirement=(
        "Every path that decides whether an artifact counts as promoted "
        "applies the same mandatory-verification rule once verification is "
        "required."
    ),
    candidate=_Candidate,
    corrected=_Corrected,
    check=_check,
)
