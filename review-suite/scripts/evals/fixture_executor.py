#!/usr/bin/env python3
"""Deterministic fresh-process stand-in for a compliant review runtime.

This is a SIMULATION, not a model evaluation. It hand-codes the review a
compliant reviewer would return for each synthetic packet so the protocol,
failure taxonomy, grading interface, and reporting stay deterministically
testable without a paid runtime. It cannot detect a model misreading the
review contract.

Every response is marked `"simulation": true`, and `runner.py` additionally
forces the simulation flag whenever this file is the executor, so no baseline
report can be produced from it. Use a real-runtime adapter such as
`claude_executor.py` for behavioural evidence.

Injectable failures for protocol tests are selected with `--mode`.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from evals import protocol
else:
    from . import protocol

EXECUTOR = {"name": "review-suite-fixture-executor", "version": "1.0"}

MODES = (
    "review",
    "runtime_failure",
    "malformed_json",
    "malformed_result",
    "protocol_mismatch",
    "crash",
    "hang",
)


def _finding(
    identifier: str,
    *,
    severity: str,
    location: str,
    rule: str,
    detail: str,
    concern: str,
    impact: str,
    proposed_change: str,
    expected_effect: str,
) -> dict[str, Any]:
    return {
        "id": identifier,
        "lens": "correctness",
        "severity": severity,
        "confidence": "high",
        "rule": rule,
        "evidence": [{"location": location, "detail": detail}],
        "concern": concern,
        "impact": impact,
        "proposed_change": proposed_change,
        "expected_effect": expected_effect,
        "location": location,
    }


def _review(candidate: dict[str, Any], verdict: str, findings: list[dict[str, Any]]):
    return {
        "schema_version": "1.0",
        "lens": "aggregate",
        "candidate": dict(candidate),
        "verdict": verdict,
        "findings": findings,
        "blocking_reasons": [],
    }


def _ledger_review(candidate: dict[str, Any]) -> dict[str, Any]:
    """Report the boundary defect in wording that paraphrases the expectation."""
    return _review(
        candidate,
        "changes_required",
        [
            _finding(
                "correctness.ledger-boundary",
                severity="blocking",
                location="ledger.py:14",
                rule="A charge equal to the available balance must succeed.",
                detail="The comparison became strict, so the equal case falls through.",
                concern="The change introduces an off-by-one at the boundary.",
                impact="A charge for the exact available balance is refused.",
                proposed_change="Compare with less-than-or-equal and cover equality.",
                expected_effect="The boundary charge succeeds again.",
            )
        ],
    )


def _session_review(candidate: dict[str, Any]) -> dict[str, Any]:
    """Report one root cause twice and touch a second surface only vaguely."""
    return _review(
        candidate,
        "changes_required",
        [
            _finding(
                "correctness.session-clock",
                severity="blocking",
                location="session.py:31",
                rule="A refreshed session must extend the deadline.",
                detail="The refresh reuses the original issue time.",
                concern="The refresh path keeps a stale expiry clock.",
                impact="Active operators are signed out mid-task.",
                proposed_change="Recompute the deadline from the refresh instant.",
                expected_effect="A refreshed session survives its original window.",
            ),
            _finding(
                "correctness.session-clock-symptom",
                severity="strong_recommendation",
                location="session.py:31",
                rule="A refreshed session must extend the deadline.",
                detail="Sessions still lapse after refresh; a stale expiry clock.",
                concern="Operators report early sign-out after refreshing.",
                impact="The same lapse is visible from the sign-out path.",
                proposed_change="Fix the shared deadline computation once.",
                expected_effect="Both report paths stop observing early lapse.",
            ),
            _finding(
                "correctness.session-audit-surface",
                severity="strong_recommendation",
                location="audit.py:8",
                rule="Session changes must be auditable.",
                detail="The audit writer is touched by this change.",
                concern="The audit record may not describe the refresh.",
                impact="Operators cannot reconstruct a refresh from the log.",
                proposed_change="Record the refresh instant in the audit entry.",
                expected_effect="The log explains each refresh.",
            ),
        ],
    )


def _invoice_review(candidate: dict[str, Any]) -> dict[str, Any]:
    """Return no gating finding, with one tolerated observation recorded."""
    return _review(
        candidate,
        "clean",
        [
            _finding(
                "correctness.invoice-naming",
                severity="defer",
                location="invoice.py:52",
                rule="The active change does not own the export helper naming.",
                detail="The batch helper name predates this change.",
                concern="The helper name is terse but untouched by this change.",
                impact="Readability only; no behaviour is affected.",
                proposed_change="Rename the helper in separate work.",
                expected_effect="Clearer naming without widening this change.",
            )
        ],
    )


def _webhook_review(candidate: dict[str, Any]) -> dict[str, Any]:
    """Find the real root cause and also raise one unsupported gating claim."""
    return _review(
        candidate,
        "changes_required",
        [
            _finding(
                "correctness.webhook-replay",
                severity="blocking",
                location="webhook.py:22",
                rule="A redelivered webhook must apply once.",
                detail="The handler retries without a de-duplication key.",
                concern="A redelivered event is applied more than once.",
                impact="Duplicate side effects reach the downstream ledger.",
                proposed_change="Key the retry on the delivery identifier.",
                expected_effect="Redelivery becomes idempotent.",
            ),
            _finding(
                "correctness.webhook-imagined-locale",
                severity="blocking",
                location="presentation.py:12",
                rule="Timestamps should be localized for every reader.",
                detail="The queue stores an absolute instant.",
                concern="Readers in other zones may prefer local rendering.",
                impact="Presentation preference only.",
                proposed_change="Render queue timestamps in the reader locale.",
                expected_effect="Locale-aware presentation.",
            ),
        ],
    )


def _pricing_review(candidate: dict[str, Any]) -> dict[str, Any]:
    """Describe one shared surface in wording that fits two root causes."""
    return _review(
        candidate,
        "changes_required",
        [
            _finding(
                "correctness.pricing-lookup",
                severity="blocking",
                location="pricing.py:19",
                rule="Tier selection must stay consistent for every caller.",
                detail=(
                    "The lookup both picks the wrong tier edge and caches the "
                    "stale tier table."
                ),
                concern="The tier lookup is wrong at the edge and serves a stale table.",
                impact="Callers are quoted a price from the wrong tier.",
                proposed_change="Fix the edge selection and invalidate the table.",
                expected_effect="Consistent tier pricing for every caller.",
            )
        ],
    )


def _catalog_review(candidate: dict[str, Any]) -> dict[str, Any]:
    """Refuse a merge verdict because the packet omits required evidence."""
    result = _review(candidate, "blocked", [])
    result["blocking_reasons"] = [
        "The packet supplies no full-scope validation evidence, so no "
        "trustworthy merge verdict is possible."
    ]
    return result


REVIEWS = {
    "example/ledger": _ledger_review,
    "example/session": _session_review,
    "example/invoice": _invoice_review,
    "example/webhook": _webhook_review,
    "example/pricing": _pricing_review,
    "example/catalog": _catalog_review,
}


def simulate(request: dict[str, Any]) -> dict[str, Any]:
    """Return the hand-coded review for the packet's subject repository."""
    packet = request["packet"]
    identity = (packet.get("repository") or {}).get("identity")
    build = REVIEWS.get(identity)
    if build is None:
        return {
            "protocol_version": protocol.PROTOCOL_VERSION,
            "outcome": "runtime_failure",
            "simulation": True,
            "executor": EXECUTOR,
            "failure": {"reason": f"no simulated review for {identity!r}"},
        }
    result = build(request["run"]["candidate"])
    return {
        "protocol_version": protocol.PROTOCOL_VERSION,
        "outcome": "blocked" if result["verdict"] == "blocked" else "review_result",
        "simulation": True,
        "executor": EXECUTOR,
        "result": result,
        "usage": {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=MODES, default="review")
    args = parser.parse_args(argv)

    if args.mode == "hang":
        # Deliberately outstay any sane test timeout.
        time.sleep(3600)
        return 0
    if args.mode == "crash":
        print("simulated executor crash", file=sys.stderr)
        return 3
    if args.mode == "malformed_json":
        sys.stdout.write("this is not JSON\n")
        return 0

    request = protocol.read_request()

    if args.mode == "protocol_mismatch":
        response = simulate(request)
        response["protocol_version"] = "0.9"
        protocol.write_response(response)
        return 0
    if args.mode == "runtime_failure":
        protocol.write_response(
            {
                "protocol_version": protocol.PROTOCOL_VERSION,
                "outcome": "runtime_failure",
                "simulation": True,
                "executor": EXECUTOR,
                "failure": {"reason": "simulated runtime failure"},
            }
        )
        return 0
    if args.mode == "malformed_result":
        protocol.write_response(
            {
                "protocol_version": protocol.PROTOCOL_VERSION,
                "outcome": "review_result",
                "simulation": True,
                "executor": EXECUTOR,
                "result": {"verdict": "clean"},
            }
        )
        return 0

    protocol.write_response(simulate(request))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
