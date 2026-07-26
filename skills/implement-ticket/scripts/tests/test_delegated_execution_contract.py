"""Tests for the optional delegated implement-ticket protocol."""

from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path
from types import ModuleType

SKILL_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_ROOT = SKILL_ROOT / "references" / "delegated-execution"
SHA_A = "a" * 40
SHA_B = "b" * 40
SHA_C = "c" * 40


def load_validator() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "delegated_execution_validator",
        CONTRACT_ROOT / "validate.py",
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load delegated execution validator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def invocation() -> dict[str, object]:
    return {
        "schema": "agent-scripts.implement-ticket/delegated-invocation/v1",
        "capability": "agent-scripts.implement-ticket/delegated-execution/v1",
        "invocation_id": "run-123",
        "ticket": {
            "provider": "github",
            "id": "123",
            "url": "https://github.com/example/project/issues/123",
            "observation": "sha256:ticket",
        },
        "repository": {
            "identity": "github:example/project",
            "remote_url": "git@github.com:example/project.git",
            "base_ref": "refs/heads/main",
            "base_sha": SHA_A,
        },
        "work": {
            "id": "external-work-123",
            "revision": 1,
            "approval_evidence": "coordinator-record:approved-123",
            "intent": "Add the approved behavior",
            "scope": ["one reviewable change"],
            "non_goals": ["merge"],
            "constraints": ["preserve compatibility"],
            "done_definition": ["one ready PR"],
        },
        "validation": ["just test", "just lint"],
        "review": {
            "independent": True,
            "unresolved_feedback_required": True,
        },
        "authority": {
            "allow": [
                "repository.candidate.create",
                "repository.candidate.push",
                "pull_request.create",
                "pull_request.update",
                "review.reply",
                "review.resolve",
            ]
        },
        "desired_outcome": "ready_pr",
        "accepted_terminal_states": [
            "ready_pr",
            "blocked",
            "requires_epic",
        ],
        "checkpoint": {
            "command": ["example-coordinator", "checkpoint"],
            "last_sequence": 0,
            "continuation_token": "token-0",
        },
    }


def candidate(kind: str = "ordinary") -> dict[str, object]:
    return {
        "repository": "github:example/project",
        "remote_url": "git@github.com:example/project.git",
        "remote_ref": "refs/heads/example-work",
        "base_sha": SHA_A,
        "head_sha": SHA_B,
        "publication": {
            "kind": kind,
            "pull_requests": [
                {
                    "id": "456",
                    "url": "https://github.com/example/project/pull/456",
                    "base_ref": "refs/heads/main",
                    "base_sha": SHA_A,
                    "head_ref": "refs/heads/example-work",
                    "head_sha": SHA_B,
                    "state": "open",
                }
            ],
        },
    }


def result() -> dict[str, object]:
    source = invocation()
    return {
        "schema": "agent-scripts.implement-ticket/delegated-result/v1",
        "capability": "agent-scripts.implement-ticket/delegated-execution/v1",
        "invocation_id": "run-123",
        "terminal_state": "ready_pr",
        "ticket": source["ticket"],
        "repository": {
            "identity": "github:example/project",
            "base_ref": "refs/heads/main",
            "base_sha": SHA_A,
        },
        "implementation_state": "published",
        "candidate": candidate(),
        "handoff": {"transferable": True, "reason": None},
        "checkpoint": {
            "last_sequence": 4,
            "continuation_token": "token-4",
        },
        "validation": [
            {
                "name": "just test",
                "outcome": "passed",
                "candidate_sha": SHA_B,
                "observed_at": "2026-07-25T12:00:00Z",
            }
        ],
        "reviews": [
            {
                "name": "review-code-change",
                "outcome": "passed",
                "candidate_sha": SHA_B,
                "observed_at": "2026-07-25T12:10:00Z",
            }
        ],
        "feedback": {
            "unresolved_material_count": 0,
            "candidate_sha": SHA_B,
            "observed_at": "2026-07-25T12:11:00Z",
        },
        "authority_used": [
            "repository.candidate.create",
            "repository.candidate.push",
            "pull_request.create",
        ],
        "unresolved_obligations": [],
        "blocking_reason": None,
        "next_action": "Caller may accept the ready PR",
    }


def checkpoint_request(phase: str = "pre_external_mutation") -> dict[str, object]:
    published_candidate = candidate()
    published_candidate.pop("publication")
    return {
        "schema": "agent-scripts.implement-ticket/checkpoint-request/v1",
        "capability": "agent-scripts.implement-ticket/delegated-execution/v1",
        "invocation_id": "run-123",
        "continuation_token": "token-1",
        "sequence": 2,
        "phase": phase,
        "action": "repository.candidate.push",
        "ticket_observation": "sha256:ticket",
        "candidate": published_candidate,
        "proposed_effect": "Publish the exact candidate",
    }


def checkpoint_response() -> dict[str, object]:
    return {
        "schema": "agent-scripts.implement-ticket/checkpoint-response/v1",
        "invocation_id": "run-123",
        "request_sequence": 2,
        "prior_continuation_token": "token-1",
        "continuation_token": "token-2",
        "decision": "allow",
        "reason": None,
        "acknowledged_candidate_sha": None,
    }


class DelegatedExecutionContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.validator = load_validator()

    def test_all_contract_files_are_valid_json_or_documented_markdown(self) -> None:
        for path in CONTRACT_ROOT.glob("*.schema.json"):
            self.assertIsInstance(json.loads(path.read_text()), dict)
        manifest = json.loads((CONTRACT_ROOT / "capability.json").read_text())
        self.assertEqual([], self.validator.validate("capability", manifest))
        self.assertIn(
            "agent-scripts.implement-ticket/delegated-execution/v1",
            (CONTRACT_ROOT / "CONTRACT.md").read_text(),
        )

    def test_valid_invocation_and_result_match(self) -> None:
        source = invocation()
        value = result()
        value["validation"].append(
            {
                "name": "just lint",
                "outcome": "passed",
                "candidate_sha": SHA_B,
                "observed_at": "2026-07-25T12:01:00Z",
            }
        )
        self.assertEqual([], self.validator.validate("invocation", source))
        self.assertEqual(
            [],
            self.validator.validate_result_for_invocation(source, value),
        )

    def test_unknown_invocation_field_fails_closed(self) -> None:
        value = invocation()
        value["coordinator"] = "atelier"
        self.assertIn(
            "$.coordinator: unknown property",
            self.validator.validate("invocation", value),
        )

    def test_desired_outcome_must_be_accepted(self) -> None:
        value = invocation()
        value["accepted_terminal_states"] = ["blocked", "requires_epic"]
        self.assertIn(
            "$.desired_outcome: must appear in accepted_terminal_states",
            self.validator.validate("invocation", value),
        )

    def test_invocation_carries_checkpoint_resume_position(self) -> None:
        value = invocation()
        value["checkpoint"].pop("last_sequence")
        self.assertIn(
            "$.checkpoint: missing required property 'last_sequence'",
            self.validator.validate("invocation", value),
        )

    def test_candidate_publication_requires_exact_acknowledgement(self) -> None:
        request = checkpoint_request("candidate_published")
        response = checkpoint_response()
        response["acknowledged_candidate_sha"] = SHA_B
        self.assertEqual(
            [],
            self.validator.validate_checkpoint_exchange(request, response),
        )
        response["acknowledged_candidate_sha"] = SHA_A
        self.assertIn(
            "$.acknowledged_candidate_sha: does not match published candidate",
            self.validator.validate_checkpoint_exchange(request, response),
        )

    def test_checkpoint_identity_and_token_must_match(self) -> None:
        request = checkpoint_request()
        response = checkpoint_response()
        response["prior_continuation_token"] = "wrong"
        self.assertIn(
            "$.prior_continuation_token: does not match request continuation_token",
            self.validator.validate_checkpoint_exchange(request, response),
        )

    def test_checkpoint_progress_rejects_replay(self) -> None:
        request = checkpoint_request()
        response = checkpoint_response()
        self.assertEqual(
            [],
            self.validator.validate_checkpoint_progress(
                1,
                "token-1",
                request,
                response,
            ),
        )
        self.assertTrue(
            self.validator.validate_checkpoint_progress(
                2,
                "token-2",
                request,
                response,
            )
        )

    def test_allow_rotates_token_and_deny_explains_reason(self) -> None:
        response = checkpoint_response()
        response["continuation_token"] = "token-1"
        self.assertIn(
            "$.continuation_token: allow must rotate the token",
            self.validator.validate("checkpoint-response", response),
        )
        response["decision"] = "deny"
        response["continuation_token"] = "token-2"
        errors = self.validator.validate("checkpoint-response", response)
        self.assertIn("$.reason: deny requires a reason", errors)
        self.assertIn(
            "$.continuation_token: deny must preserve the prior token",
            errors,
        )
        response["reason"] = "Current authority changed"
        response["continuation_token"] = response["prior_continuation_token"]
        self.assertEqual([], self.validator.validate("checkpoint-response", response))

    def test_local_blocked_state_is_explicitly_not_transferable(self) -> None:
        value = result()
        value.update(
            {
                "terminal_state": "blocked",
                "implementation_state": "local",
                "candidate": None,
                "handoff": {
                    "transferable": False,
                    "reason": "Candidate push was not authorized",
                },
                "blocking_reason": "Candidate push was not authorized",
            }
        )
        value["authority_used"] = ["repository.candidate.create"]
        self.assertEqual([], self.validator.validate("result", value))

    def test_published_blocked_state_preserves_transferable_candidate(self) -> None:
        value = result()
        value["terminal_state"] = "blocked"
        value["blocking_reason"] = "Coordinator unavailable after publication"
        value["candidate"]["publication"]["pull_requests"] = []
        self.assertEqual([], self.validator.validate("result", value))

    def test_ready_pr_rejects_stack_or_local_only_candidate(self) -> None:
        value = result()
        value["candidate"] = candidate("stack")
        self.assertIn(
            "$.candidate.publication: ready_pr requires one ordinary PR",
            self.validator.validate("result", value),
        )
        value = result()
        value["implementation_state"] = "local"
        self.assertTrue(self.validator.validate("result", value))

    def test_result_cannot_exceed_invocation_authority(self) -> None:
        value = result()
        value["authority_used"].append("pull_request.merge")
        self.assertIn(
            "$.authority_used: exceeds invocation: pull_request.merge",
            self.validator.validate_result_for_invocation(invocation(), value),
        )

    def test_result_identity_must_match_invocation(self) -> None:
        value = copy.deepcopy(result())
        value["ticket"]["observation"] = "sha256:changed"
        self.assertIn(
            "$.ticket: does not match invocation",
            self.validator.validate_result_for_invocation(invocation(), value),
        )

    def test_terminal_checkpoint_must_match_caller_ledger_tail(self) -> None:
        source = invocation()
        source["validation"] = ["just test"]
        value = result()
        self.assertEqual(
            [],
            self.validator.validate_result_checkpoint_state(
                source,
                value,
                4,
                "token-4",
            ),
        )
        value["checkpoint"] = {
            "last_sequence": 0,
            "continuation_token": "token-0",
        }
        errors = self.validator.validate_result_checkpoint_state(
            source,
            value,
            4,
            "token-4",
        )
        self.assertIn(
            "$.checkpoint.last_sequence: does not match caller ledger",
            errors,
        )
        self.assertIn(
            "$.checkpoint.continuation_token: does not match caller ledger",
            errors,
        )

    def test_candidate_must_match_invocation_repository(self) -> None:
        value = result()
        value["candidate"]["repository"] = "github:other/project"
        errors = self.validator.validate_result_for_invocation(invocation(), value)
        self.assertIn(
            "$.candidate.repository: does not match invocation",
            errors,
        )

    def test_ready_pr_base_ref_must_match_invocation(self) -> None:
        source = invocation()
        source["validation"] = ["just test"]
        value = result()
        value["candidate"]["publication"]["pull_requests"][0]["base_ref"] = (
            "refs/heads/unrelated"
        )
        self.assertIn(
            "$.candidate.publication: first PR base_ref does not match invocation",
            self.validator.validate_result_for_invocation(source, value),
        )

    def test_ready_pr_head_ref_must_match_candidate(self) -> None:
        value = result()
        value["candidate"]["publication"]["pull_requests"][0]["head_ref"] = (
            "refs/heads/unrelated"
        )
        self.assertIn(
            "$.candidate.publication: ready_pr head ref must match candidate",
            self.validator.validate("result", value),
        )

    def test_delivery_requires_all_requested_current_gates(self) -> None:
        errors = self.validator.validate_result_for_invocation(
            invocation(),
            result(),
        )
        self.assertIn("$.validation: missing required command just lint", errors)
        value = result()
        value["validation"].append(
            {
                "name": "just lint",
                "outcome": "failed",
                "candidate_sha": SHA_B,
                "observed_at": "2026-07-25T12:01:00Z",
            }
        )
        self.assertIn(
            "$.validation: just lint did not pass at exact candidate",
            self.validator.validate_result_for_invocation(invocation(), value),
        )

    def test_published_result_requires_publication_authority(self) -> None:
        value = result()
        value["authority_used"] = []
        errors = self.validator.validate("result", value)
        self.assertIn(
            "$.authority_used: published implementation requires "
            "repository.candidate.push",
            errors,
        )
        self.assertIn(
            "$.authority_used: pull request publication requires create or update",
            errors,
        )

    def test_duplicate_observation_names_fail_closed(self) -> None:
        value = result()
        contradictory = copy.deepcopy(value["validation"][0])
        contradictory["outcome"] = "failed"
        value["validation"].append(contradictory)
        self.assertIn(
            "$.validation: duplicate observation names just test",
            self.validator.validate("result", value),
        )

    def test_ready_prs_require_unique_ordered_topology(self) -> None:
        value = result()
        value["terminal_state"] = "ready_prs"
        value["candidate"]["publication"]["kind"] = "stack"
        duplicate = copy.deepcopy(value["candidate"]["publication"]["pull_requests"][0])
        value["candidate"]["publication"]["pull_requests"].append(duplicate)
        errors = self.validator.validate("result", value)
        self.assertIn(
            "$.candidate.publication: ready_prs requires unique pull request id values",
            errors,
        )
        self.assertIn(
            "$.candidate.publication: ready_prs requires unique pull request head_sha "
            "values",
            errors,
        )
        value["candidate"]["publication"]["pull_requests"][0]["head_sha"] = SHA_C
        value["candidate"]["publication"]["pull_requests"][1].update(
            {
                "id": "789",
                "url": "https://github.com/example/project/pull/789",
                "base_ref": "refs/heads/stack-one",
                "base_sha": SHA_A,
                "head_ref": "refs/heads/stack-two",
                "head_sha": SHA_B,
            }
        )
        self.assertIn(
            "$.candidate.publication: ready_prs base chain is invalid",
            self.validator.validate("result", value),
        )
        value["candidate"]["publication"]["pull_requests"][1]["base_sha"] = SHA_C
        value["candidate"]["publication"]["pull_requests"][0]["head_ref"] = (
            "refs/heads/stack-one"
        )
        self.assertNotIn(
            "$.candidate.publication: ready_prs base chain is invalid",
            self.validator.validate("result", value),
        )
        value["candidate"]["publication"]["pull_requests"][1]["base_ref"] = (
            "refs/heads/unrelated"
        )
        self.assertIn(
            "$.candidate.publication: ready_prs ref chain is invalid",
            self.validator.validate("result", value),
        )
        value["candidate"]["publication"]["pull_requests"][1]["base_ref"] = (
            "refs/heads/stack-one"
        )
        value["candidate"]["publication"]["pull_requests"][1]["head_ref"] = (
            "refs/heads/unrelated"
        )
        self.assertIn(
            "$.candidate.publication: final PR head ref must match candidate",
            self.validator.validate("result", value),
        )

    def test_delivery_requires_review_and_zero_feedback(self) -> None:
        source = invocation()
        source["validation"] = ["just test"]
        value = result()
        value["reviews"] = []
        value["feedback"]["unresolved_material_count"] = 1
        errors = self.validator.validate_result_for_invocation(source, value)
        self.assertIn(
            "$.reviews: independent review did not pass at exact candidate",
            errors,
        )
        self.assertTrue(any(error.startswith("$.feedback:") for error in errors))

    def test_requires_epic_forbids_used_authority(self) -> None:
        value = result()
        value.update(
            {
                "terminal_state": "requires_epic",
                "implementation_state": "none",
                "candidate": None,
                "handoff": {
                    "transferable": False,
                    "reason": "Whole epic requires implement-epic",
                },
                "feedback": None,
                "authority_used": [],
            }
        )
        self.assertEqual([], self.validator.validate("result", value))
        value["authority_used"] = ["repository.candidate.create"]
        self.assertIn(
            "$.authority_used: no implementation requires no actions",
            self.validator.validate("result", value),
        )

    def test_push_checkpoint_requires_exact_candidate(self) -> None:
        value = checkpoint_request()
        value["candidate"] = None
        self.assertIn(
            "$.candidate: action requires exact candidate",
            self.validator.validate("checkpoint-request", value),
        )

    def test_skill_loads_and_enforces_delegated_contract(self) -> None:
        skill = (SKILL_ROOT / "SKILL.md").read_text()
        result_reference = (SKILL_ROOT / "references/cleanup-and-result.md").read_text()
        self.assertIn("delegated execution contract", skill)
        self.assertIn("before every action", skill)
        self.assertIn("invocation's `last_sequence`", skill)
        self.assertIn("candidate_published", skill)
        self.assertIn("versioned delegated-execution contract", result_reference)


if __name__ == "__main__":
    unittest.main()
