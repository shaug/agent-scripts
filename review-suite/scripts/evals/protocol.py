#!/usr/bin/env python3
"""Versioned stdin/stdout replay protocol for the review suite.

One evaluation attempt is one fresh executor process. The runner writes a
single result-blind JSON request to stdin and reads a single JSON response
from stdout. Nothing about the expected outcome may appear in the request:
that blindness is a contract, and `audit_request` enforces it structurally
and textually rather than by convention.

The response `outcome` field separates a valid review from a runtime problem
so that a spawn failure, timeout, crash, oversized reply, malformed reply, or
protocol mismatch can never be scored as a clean review.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

# Imported for its normalisation only. The contamination audit has to judge a
# leak by the same rule the grader uses to match one, so the two must share that
# rule rather than each keep its own. `grader` deliberately imports nothing from
# here, so this direction stays acyclic.
from . import grader

PROTOCOL_VERSION = "1.0"

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
REVIEW_SUITE = SCRIPTS_DIR.parent
REPOSITORY_ROOT = REVIEW_SUITE.parent
EVAL_CONTRACTS = REVIEW_SUITE / "evals" / "contracts"

#: Every terminal classification of one attempt. The first six are evaluation
#: failures: they describe the harness or the runtime, never review quality.
ATTEMPT_STATUSES = (
    "spawn_failure",
    "timeout",
    "runtime_failure",
    "output_too_large",
    "malformed_output",
    "protocol_mismatch",
    "blocked",
    "review_result",
)

#: Statuses that report an evaluation failure rather than a review outcome.
EVALUATION_FAILURE_STATUSES = ATTEMPT_STATUSES[:6]

#: Statuses in which the executor returned a valid, candidate-bound review.
VALID_OUTCOME_STATUSES = ("blocked", "review_result")

#: Only a merge verdict is graded against expectations; a `blocked` review
#: refuses to give one, so there is nothing to score it against.
GRADABLE_STATUSES = ("review_result",)

#: Request keys the protocol permits, at the top level and inside `run`.
#: `audit_request` rejects anything else so a private expectation object
#: cannot ride along inside an unnoticed extra key.
REQUEST_KEYS = frozenset(
    {
        "protocol_version",
        "target_skill",
        "target_skill_digest",
        "skill_prompt",
        "contract_documents",
        "instructions",
        "packet",
        "run",
    }
)
RUN_KEYS = frozenset(
    {
        "case_ref",
        "run_number",
        "suite_commit",
        "corpus_version",
        "candidate",
        "started_at",
    }
)
CANDIDATE_KEYS = frozenset({"head_sha", "comparison_base_sha"})


def _load_validator():
    """Load the canonical review-suite validator without third-party deps."""
    spec = importlib.util.spec_from_file_location(
        "review_suite_validate", SCRIPTS_DIR / "validate.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {SCRIPTS_DIR / 'validate.py'}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VALIDATOR = _load_validator()


def load_eval_schema(name: str) -> dict[str, Any]:
    return json.loads((EVAL_CONTRACTS / name).read_text())


def validate_against(name: str, document: Any) -> list[str]:
    """Validate a document with the review suite's schema-subset validator."""
    return VALIDATOR.validate_schema(document, load_eval_schema(name))


def case_ref(case_id: str) -> str:
    """Return the opaque per-case reference used inside a request.

    The real case identifier never reaches the executor. Even a badly named
    case therefore cannot leak its name through the payload; `audit_corpus`
    separately rejects outcome-revealing identifiers at the source.
    """
    digest = hashlib.sha256(case_id.encode("utf-8")).hexdigest()
    return f"c-{digest[:8]}"


def prompt_digest(skill_prompt: str) -> str:
    """Pin the exact target-skill text evaluated by one attempt."""
    return hashlib.sha256(skill_prompt.encode("utf-8")).hexdigest()[:16]


def build_request(
    *,
    case_id: str,
    target_skill: str,
    skill_prompt: str,
    contract_documents: dict[str, str],
    instructions: str,
    packet: dict[str, Any],
    run_number: int,
    suite_commit: str,
    corpus_version: str,
    started_at: str,
) -> dict[str, Any]:
    """Build one result-blind request for one fresh executor process."""
    candidate = packet.get("candidate")
    if not isinstance(candidate, dict):
        raise ValueError(f"{case_id}: packet has no candidate object")
    identity = {
        field: candidate[field]
        for field in sorted(CANDIDATE_KEYS)
        if field in candidate
    }
    if set(identity) != CANDIDATE_KEYS:
        raise ValueError(f"{case_id}: packet candidate lacks complete identity")
    return {
        "protocol_version": PROTOCOL_VERSION,
        "target_skill": target_skill,
        "target_skill_digest": prompt_digest(skill_prompt),
        "skill_prompt": skill_prompt,
        "contract_documents": dict(contract_documents),
        "instructions": instructions,
        "packet": packet,
        "run": {
            "case_ref": case_ref(case_id),
            "run_number": run_number,
            "suite_commit": suite_commit,
            "corpus_version": corpus_version,
            "candidate": identity,
            "started_at": started_at,
        },
    }


#: Provenance fields whose free text could carry restricted material.
PRIVATE_PROVENANCE_FIELDS = ("retention_authority", "sanitization", "notes")


def blind_strings(expectation: dict[str, Any], provenance: dict[str, Any]) -> list[str]:
    """Return every private string that must never reach an executor.

    Three deliberate exclusions keep the check meaningful rather than vacuous:

    - `requirement` normally restates the reviewer-visible acceptance criterion
      and `surface` is a reviewer-visible code location, so banning them would
      ban the packet itself;
    - `expected_verdict`, `severity`, and `origin` are closed public
      vocabularies that the bundled review contracts spell out in full, so
      banning those words would ban the contracts; those fields stay private
      structurally instead, because the expectation file is never part of a
      request and the permitted request keys are exact.

    Everything that identifies *which* outcome this case expects is banned.
    """
    strings: list[str] = []
    for root_cause in expectation.get("material_root_causes", []):
        strings.append(str(root_cause.get("id", "")))
        strings.append(str(root_cause.get("consequence", "")))
        strings.append(str(root_cause.get("trigger", "")))
        strings.extend(
            str(item) for item in root_cause.get("equivalent_formulations", [])
        )
    for non_finding in expectation.get("accepted_non_findings", []):
        strings.append(str(non_finding.get("id", "")))
        strings.append(str(non_finding.get("description", "")))
        strings.extend(
            str(item) for item in non_finding.get("equivalent_formulations", [])
        )
    strings.extend(
        str(provenance.get(field, "")) for field in PRIVATE_PROVENANCE_FIELDS
    )
    return [item for item in strings if item]


def _string_leaves(value: Any) -> Iterator[str]:
    """Yield every string in a payload, including object keys."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, child in value.items():
            yield str(key)
            yield from _string_leaves(child)
    elif isinstance(value, list):
        for item in value:
            yield from _string_leaves(item)


def _collapse(text: str) -> str:
    """Fold case and whitespace so a re-wrapped leak still matches."""
    return re.sub(r"\s+", " ", text).strip().lower()


def _contains(haystack: list[str], needle: str) -> bool:
    collapsed = _collapse(needle)
    return bool(collapsed) and any(collapsed in leaf for leaf in haystack)


def audit_request(
    request: dict[str, Any],
    *,
    case_id: str,
    expectation: dict[str, Any],
    provenance: dict[str, Any],
) -> list[str]:
    """Prove one complete request payload cannot reveal its expected outcome."""
    errors = [
        f"schema: {error}"
        for error in validate_against("executor-request.schema.json", request)
    ]

    # Structural containment: an unexpected key is the easiest way for grader
    # data to leak, so the permitted key sets are exact rather than minimal.
    extra_top = sorted(set(request) - REQUEST_KEYS)
    if extra_top:
        errors.append("payload carries unpermitted key(s): " + ", ".join(extra_top))
    run = request.get("run")
    if isinstance(run, dict):
        extra_run = sorted(set(run) - RUN_KEYS)
        if extra_run:
            errors.append(
                "payload run carries unpermitted key(s): " + ", ".join(extra_run)
            )
        candidate = run.get("candidate")
        if isinstance(candidate, dict):
            extra_candidate = sorted(set(candidate) - CANDIDATE_KEYS)
            if extra_candidate:
                errors.append(
                    "payload run candidate carries unpermitted key(s): "
                    + ", ".join(extra_candidate)
                )
        if run.get("case_ref") == case_id:
            errors.append("payload run case_ref exposes the case identifier")
        if run.get("case_ref") != case_ref(case_id):
            errors.append("payload run case_ref is not the opaque case reference")

    # Textual containment is checked against the payload's real string values,
    # not its JSON serialization. `json.dumps` escapes every non-ASCII
    # character to `\uXXXX`, newlines to `\n`, and quotes to `\"`, so
    # searching the serialized form silently misses any private string
    # containing an em dash, a curly quote, a line break, or a quotation
    # mark - exactly the characters human-authored expectation prose uses.
    haystack = [_collapse(leaf) for leaf in _string_leaves(request)]
    if _contains(haystack, case_id):
        errors.append(f"payload contains the case identifier {case_id!r}")
    for blind in blind_strings(expectation, provenance):
        if _contains(haystack, blind):
            errors.append(f"payload contains private expectation text {blind!r}")
    errors.extend(_matchable_formulation_errors(request, expectation))
    return errors


def _matchable_formulation_errors(
    request: dict[str, Any], expectation: dict[str, Any]
) -> list[str]:
    """Reject a root-cause formulation the grader could match from the payload.

    The check above folds case and whitespace but keeps punctuation, while the
    grader folds punctuation away entirely. That gap is not academic: a
    formulation reading ``subprocess.run raises FileNotFoundError`` is invisible
    to a collapse-based search of a packet saying
    ``\\`subprocess.run\\` raises \\`FileNotFoundError\\```, and matches perfectly
    once the grader normalises both. A case shipped in exactly that state, so a
    reviewer could have earned full recall by quoting its own input, and the
    escape it was built to measure would have measured nothing.

    Whatever the grader treats as the same text is what decides a score, so the
    audit has to use the grader's own definition rather than a stricter one.

    Scoped to `material_root_causes` deliberately. An accepted non-finding's
    formulation frequently does restate reviewer-visible content, and an echo
    there only makes the grader more tolerant of an observation already judged
    immaterial - it cannot manufacture a correct answer, which is the failure
    this guards against.
    """
    payload = [grader.normalize(leaf) for leaf in _string_leaves(request)]
    errors = []
    for root_cause in expectation.get("material_root_causes", []):
        for formulation in root_cause.get("equivalent_formulations", []):
            needle = grader.normalize(formulation)
            if needle and any(needle in leaf for leaf in payload):
                errors.append(
                    "payload contains text the grader would match as the accepted "
                    f"formulation {formulation!r} for {root_cause.get('id')!r}, so a "
                    "reviewer could earn recall by quoting the packet"
                )
    return errors


def _numeric_usage_errors(response: dict[str, Any]) -> list[str]:
    """Check the numeric usage fields the schema subset cannot type-check."""
    usage = response.get("usage")
    if usage is None:
        return []
    if not isinstance(usage, dict):
        return ["$.usage: expected object"]
    errors = []
    for field, value in usage.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            errors.append(f"$.usage.{field}: expected a number")
    return errors


def classify_response(
    packet: dict[str, Any], stdout: str
) -> tuple[str, dict[str, Any] | None, str]:
    """Classify one executor reply into an attempt status.

    Returns `(status, response, detail)`. `response` is present only when the
    reply parsed as a JSON object, so callers can still record executor
    identity and usage from a reply that failed a later check.
    """
    try:
        response = json.loads(stdout)
    except json.JSONDecodeError as error:
        return "malformed_output", None, f"stdout is not JSON: {error}"
    if not isinstance(response, dict):
        return "malformed_output", None, "stdout is not one JSON object"

    version = response.get("protocol_version")
    if version != PROTOCOL_VERSION:
        return (
            "protocol_mismatch",
            response,
            f"expected protocol {PROTOCOL_VERSION}, got {version!r}",
        )

    errors = validate_against("executor-response.schema.json", response)
    errors.extend(_numeric_usage_errors(response))
    if errors:
        return "malformed_output", response, "; ".join(errors)

    outcome = response["outcome"]
    if outcome == "runtime_failure":
        failure = response.get("failure")
        if not failure:
            return (
                "malformed_output",
                response,
                "runtime_failure requires a failure reason",
            )
        return "runtime_failure", response, failure["reason"]

    result = response.get("result")
    if not isinstance(result, dict):
        return "malformed_output", response, f"{outcome} requires a review result"

    verdict = result.get("verdict")
    allowed = (
        {"clean", "changes_required"} if outcome == "review_result" else {"blocked"}
    )
    if verdict not in allowed:
        return (
            "malformed_output",
            response,
            f"{outcome} cannot carry verdict {verdict!r}",
        )

    # Judge the reply, never the packet. `corpus.load_case` already established
    # and asserted each packet's validity, so a packet defect at this point is
    # a deliberate property of the case, not news about the executor. Billing it
    # to the executor would classify a reviewer that wrongly issues a merge
    # verdict on incomplete evidence as an evaluation failure, which drops the
    # one behaviour a `packet_valid: false` case exists to measure.
    pair_errors = [
        error
        for error in VALIDATOR.validate_pair(packet, result)
        if not error.startswith("packet: ")
    ]
    if pair_errors:
        return "malformed_output", response, "; ".join(pair_errors)

    return ("blocked" if outcome == "blocked" else "review_result"), response, ""


def read_request() -> dict[str, Any]:
    """Read and version-check one request from stdin, for executor scripts."""
    request = json.load(sys.stdin)
    if not isinstance(request, dict):
        raise ValueError("executor request must be one JSON object")
    version = request.get("protocol_version")
    if version != PROTOCOL_VERSION:
        raise ValueError(
            f"executor supports protocol {PROTOCOL_VERSION}, got {version!r}"
        )
    return request


def write_response(response: dict[str, Any]) -> None:
    """Write exactly one JSON response object to stdout."""
    json.dump(response, sys.stdout, sort_keys=True)
    sys.stdout.write("\n")
