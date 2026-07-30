"""Validate the review-fix-loop invocation, checkpoint, and terminal-result
contracts: valid examples for both `local_commit` and `update_pr`, invalid and
ambiguous inputs failing closed with actionable diagnostics, rejection of
zero-cycle and review-only invocations, checkpoint-reconstructed cycle
accounting, the per-terminal-state publication/retained-commit/operator-action
contract, and deterministic round-trip serialization.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = SKILL_ROOT / "references" / "examples"

SPEC = importlib.util.spec_from_file_location(
    "review_fix_loop_validator", SKILL_ROOT / "scripts" / "validate.py"
)
assert SPEC and SPEC.loader
VALIDATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATE)


def load(name: str) -> dict:
    return json.loads((EXAMPLES / name).read_text())


class ValidExampleTests(unittest.TestCase):
    """Acceptance: valid examples for both local_commit and update_pr pass
    strict validation, across all three document kinds."""

    def test_local_commit_invocation_valid(self):
        self.assertEqual(
            VALIDATE.validate_invocation(load("local-commit-invocation.json")), []
        )

    def test_local_commit_checkpoint_valid(self):
        self.assertEqual(
            VALIDATE.validate_checkpoint(load("local-commit-checkpoint.json")), []
        )

    def test_local_commit_terminal_converged_valid(self):
        self.assertEqual(
            VALIDATE.validate_terminal_result(
                load("local-commit-terminal-converged.json")
            ),
            [],
        )

    def test_update_pr_invocation_valid(self):
        self.assertEqual(
            VALIDATE.validate_invocation(load("update-pr-invocation.json")), []
        )

    def test_update_pr_checkpoint_valid(self):
        self.assertEqual(
            VALIDATE.validate_checkpoint(load("update-pr-checkpoint.json")), []
        )

    def test_update_pr_terminal_converged_valid(self):
        self.assertEqual(
            VALIDATE.validate_terminal_result(
                load("update-pr-terminal-converged.json")
            ),
            [],
        )

    def test_local_commit_changes_remaining_examples_valid(self):
        self.assertEqual(
            VALIDATE.validate_checkpoint(
                load("local-commit-checkpoint-changes-remaining.json")
            ),
            [],
        )
        self.assertEqual(
            VALIDATE.validate_terminal_result(
                load("local-commit-terminal-changes-remaining.json")
            ),
            [],
        )

    def test_update_pr_blocked_remote_advanced_example_valid(self):
        self.assertEqual(
            VALIDATE.validate_terminal_result(
                load("update-pr-terminal-blocked-remote-advanced.json")
            ),
            [],
        )


class InvocationRejectionTests(unittest.TestCase):
    """Invalid and ambiguous invocations fail closed with actionable diagnostics."""

    def setUp(self):
        self.local_commit = load("local-commit-invocation.json")
        self.update_pr = load("update-pr-invocation.json")

    def test_zero_cycle_budget_rejected(self):
        invocation = copy.deepcopy(self.local_commit)
        invocation["fix_cycle_budget"]["max_fix_cycles"] = 0
        errors = VALIDATE.validate_invocation(invocation)
        self.assertTrue(
            any("must be >= 1" in error for error in errors),
            errors,
        )

    def test_negative_cycle_budget_rejected(self):
        invocation = copy.deepcopy(self.local_commit)
        invocation["fix_cycle_budget"]["max_fix_cycles"] = -1
        errors = VALIDATE.validate_invocation(invocation)
        self.assertTrue(any("must be >= 1" in error for error in errors), errors)

    def test_missing_fix_cycle_budget_rejected(self):
        invocation = copy.deepcopy(self.local_commit)
        del invocation["fix_cycle_budget"]
        errors = VALIDATE.validate_invocation(invocation)
        self.assertTrue(
            any(
                "missing required property 'fix_cycle_budget'" in error
                for error in errors
            ),
            errors,
        )

    def test_over_maximum_cycle_budget_rejected(self):
        invocation = copy.deepcopy(self.local_commit)
        invocation["fix_cycle_budget"]["max_fix_cycles"] = 11
        errors = VALIDATE.validate_invocation(invocation)
        self.assertTrue(any("must be <= 10" in error for error in errors), errors)

    def test_unsupported_review_only_top_level_field_rejected(self):
        invocation = copy.deepcopy(self.local_commit)
        invocation["mode"] = "review_only"
        errors = VALIDATE.validate_invocation(invocation)
        self.assertTrue(any("unknown property" in error for error in errors), errors)

    def test_unsupported_review_execution_mode_rejected(self):
        invocation = copy.deepcopy(self.local_commit)
        invocation["review_execution"]["mode"] = "review_only"
        errors = VALIDATE.validate_invocation(invocation)
        self.assertTrue(any("expected one of" in error for error in errors), errors)

    def test_in_agent_override_requires_authorization(self):
        invocation = copy.deepcopy(self.local_commit)
        invocation["review_execution"]["mode"] = "in_agent_override"
        errors = VALIDATE.validate_invocation(invocation)
        self.assertIn(
            "$.review_execution: in_agent_override requires override_authorization",
            errors,
        )

    def test_fresh_subagent_rejects_override_authorization(self):
        invocation = copy.deepcopy(self.local_commit)
        invocation["review_execution"]["override_authorization"] = "operator note"
        errors = VALIDATE.validate_invocation(invocation)
        self.assertIn(
            "$.review_execution: fresh_subagent must not carry override_authorization",
            errors,
        )

    def test_source_binding_and_unavailable_reason_are_mutually_exclusive(self):
        invocation = copy.deepcopy(self.update_pr)
        invocation["candidate"]["source_unavailable_reason"] = "also unavailable"
        errors = VALIDATE.validate_invocation(invocation)
        self.assertTrue(any("mutually exclusive" in error for error in errors), errors)

    def test_source_binding_and_unavailable_reason_both_absent_rejected(self):
        invocation = copy.deepcopy(self.update_pr)
        del invocation["candidate"]["source_binding"]
        errors = VALIDATE.validate_invocation(invocation)
        self.assertTrue(
            any("requires source_binding or an explicit" in error for error in errors),
            errors,
        )

    def test_update_pr_requires_pull_request_target(self):
        invocation = copy.deepcopy(self.update_pr)
        del invocation["publication"]["pull_request"]
        errors = VALIDATE.validate_invocation(invocation)
        self.assertIn("$.publication: update_pr requires pull_request", errors)

    def test_update_pr_requires_source_binding(self):
        invocation = copy.deepcopy(self.update_pr)
        del invocation["candidate"]["source_binding"]
        invocation["candidate"]["source_unavailable_reason"] = "no source recorded"
        errors = VALIDATE.validate_invocation(invocation)
        self.assertIn(
            "$.publication: update_pr requires candidate.source_binding", errors
        )

    def test_local_commit_rejects_pull_request_target(self):
        invocation = copy.deepcopy(self.local_commit)
        invocation["publication"]["pull_request"] = self.update_pr["publication"][
            "pull_request"
        ]
        errors = VALIDATE.validate_invocation(invocation)
        self.assertIn(
            "$.publication: local_commit must not carry a pull_request target",
            errors,
        )

    def test_local_commit_rejects_remote_iteration_grants(self):
        invocation = copy.deepcopy(self.local_commit)
        invocation["publication"]["remote_iteration_grants"] = [
            {
                "mechanism_id": "external-linter",
                "kind": "hosted_check",
                "repository": "shaug/agent-scripts",
                "ref": "refs/heads/fix/96-example",
                "origin_only_evidence": "the checker only reads the origin ref",
            }
        ]
        errors = VALIDATE.validate_invocation(invocation)
        self.assertTrue(
            any("cannot carry a grant" in error for error in errors), errors
        )

    def test_validation_requires_focused_scope(self):
        invocation = copy.deepcopy(self.local_commit)
        invocation["validation"] = [
            entry for entry in invocation["validation"] if entry["scope"] != "focused"
        ]
        errors = VALIDATE.validate_invocation(invocation)
        self.assertIn("$.validation: missing focused validation", errors)

    def test_validation_requires_full_scope(self):
        invocation = copy.deepcopy(self.local_commit)
        invocation["validation"] = [
            entry for entry in invocation["validation"] if entry["scope"] != "full"
        ]
        errors = VALIDATE.validate_invocation(invocation)
        self.assertIn("$.validation: missing full validation", errors)

    def test_missing_candidate_head_sha_rejected(self):
        invocation = copy.deepcopy(self.local_commit)
        del invocation["candidate"]["head_sha"]
        errors = VALIDATE.validate_invocation(invocation)
        self.assertTrue(
            any("missing required property 'head_sha'" in error for error in errors),
            errors,
        )

    def test_malformed_head_sha_rejected(self):
        invocation = copy.deepcopy(self.local_commit)
        invocation["candidate"]["head_sha"] = "not-a-sha"
        errors = VALIDATE.validate_invocation(invocation)
        self.assertTrue(any("does not match" in error for error in errors), errors)


class CheckpointBudgetReconstructionTests(unittest.TestCase):
    """Cycle consumption and remaining budget reconstruct from checkpoint history."""

    def test_single_committed_cycle(self):
        checkpoint = load("local-commit-checkpoint.json")
        self.assertEqual(
            VALIDATE.reconstruct_cycle_accounting(checkpoint),
            {
                "original_max_fix_cycles": 3,
                "consumed_cycles": 1,
                "remaining_cycles": 2,
            },
        )

    def test_exhausted_budget_with_a_failed_attempt(self):
        checkpoint = load("local-commit-checkpoint-changes-remaining.json")
        self.assertEqual(
            VALIDATE.reconstruct_cycle_accounting(checkpoint),
            {
                "original_max_fix_cycles": 3,
                "consumed_cycles": 3,
                "remaining_cycles": 0,
            },
        )

    def test_no_attempts_yet(self):
        checkpoint = copy.deepcopy(load("local-commit-checkpoint.json"))
        checkpoint["cycle_attempts"] = []
        self.assertEqual(
            VALIDATE.reconstruct_cycle_accounting(checkpoint),
            {
                "original_max_fix_cycles": 3,
                "consumed_cycles": 0,
                "remaining_cycles": 3,
            },
        )


class CheckpointRejectionTests(unittest.TestCase):
    def setUp(self):
        self.checkpoint = load("local-commit-checkpoint.json")

    def test_attempts_cannot_exceed_original_budget(self):
        checkpoint = copy.deepcopy(self.checkpoint)
        for sequence in range(2, 5):
            checkpoint["cycle_attempts"].append(
                {
                    "sequence": sequence,
                    "started_from_head": checkpoint["current_head"],
                    "outcome": "failed",
                }
            )
        errors = VALIDATE.validate_checkpoint(checkpoint)
        self.assertTrue(
            any(
                "consumed more cycles than original_cycle_budget" in error
                for error in errors
            ),
            errors,
        )

    def test_head_history_must_start_at_initial_head(self):
        checkpoint = copy.deepcopy(self.checkpoint)
        checkpoint["head_history"][0] = checkpoint["current_head"]
        errors = VALIDATE.validate_checkpoint(checkpoint)
        self.assertIn("$.head_history[0]: must equal initial_head", errors)

    def test_head_history_must_end_at_current_head(self):
        checkpoint = copy.deepcopy(self.checkpoint)
        checkpoint["head_history"][-1] = checkpoint["initial_head"]
        errors = VALIDATE.validate_checkpoint(checkpoint)
        self.assertIn("$.head_history[-1]: must equal current_head", errors)

    def test_committed_attempt_requires_resulting_head(self):
        checkpoint = copy.deepcopy(self.checkpoint)
        del checkpoint["cycle_attempts"][0]["resulting_head"]
        errors = VALIDATE.validate_checkpoint(checkpoint)
        self.assertTrue(
            any(
                "committed outcome requires resulting_head" in error for error in errors
            ),
            errors,
        )

    def test_committed_count_must_match_head_history_advances(self):
        checkpoint = copy.deepcopy(self.checkpoint)
        checkpoint["cycle_attempts"][0]["outcome"] = "failed"
        del checkpoint["cycle_attempts"][0]["resulting_head"]
        errors = VALIDATE.validate_checkpoint(checkpoint)
        self.assertTrue(
            any("does not match head_history advances" in error for error in errors),
            errors,
        )

    def test_source_unavailable_requires_reason(self):
        checkpoint = copy.deepcopy(self.checkpoint)
        checkpoint["source"] = {"status": "unavailable"}
        errors = VALIDATE.validate_checkpoint(checkpoint)
        self.assertIn(
            "$.source: unavailable status requires unavailable_reason", errors
        )

    def test_source_bound_requires_last_verified_head(self):
        checkpoint = copy.deepcopy(self.checkpoint)
        checkpoint["source"] = {"status": "bound"}
        errors = VALIDATE.validate_checkpoint(checkpoint)
        self.assertIn("$.source: bound status requires last_verified_head", errors)

    def test_base_revision_history_must_match_current_base(self):
        checkpoint = copy.deepcopy(self.checkpoint)
        checkpoint["base_revision_history"][-1]["sha"] = checkpoint["current_head"]
        errors = VALIDATE.validate_checkpoint(checkpoint)
        self.assertIn(
            "$.base_revision_history[-1]: must equal the current comparison_base",
            errors,
        )


class TerminalResultContractTests(unittest.TestCase):
    """Every terminal state has an explicit publication/retained-commit/
    operator-action contract, enforced across converged, changes_remaining,
    and blocked results."""

    def setUp(self):
        self.converged_local = load("local-commit-terminal-converged.json")
        self.converged_pr = load("update-pr-terminal-converged.json")
        self.changes_remaining = load("local-commit-terminal-changes-remaining.json")
        self.blocked = load("update-pr-terminal-blocked-remote-advanced.json")

    def test_converged_must_not_carry_a_reason(self):
        result = copy.deepcopy(self.converged_local)
        result["reason"] = "cycle_budget_exhausted"
        errors = VALIDATE.validate_terminal_result(result)
        self.assertIn("$.reason: converged must not carry a reason", errors)

    def test_changes_remaining_rejects_a_blocked_only_reason(self):
        result = copy.deepcopy(self.changes_remaining)
        result["reason"] = "remote_advanced"
        errors = VALIDATE.validate_terminal_result(result)
        self.assertTrue(
            any("changes_remaining requires one of" in error for error in errors),
            errors,
        )

    def test_changes_remaining_requires_a_reason(self):
        result = copy.deepcopy(self.changes_remaining)
        result.pop("reason", None)
        errors = VALIDATE.validate_terminal_result(result)
        self.assertTrue(
            any("changes_remaining requires one of" in error for error in errors),
            errors,
        )

    def test_blocked_rejects_a_changes_remaining_only_reason(self):
        result = copy.deepcopy(self.blocked)
        result["reason"] = "oscillation"
        errors = VALIDATE.validate_terminal_result(result)
        self.assertTrue(
            any("blocked requires one of" in error for error in errors), errors
        )

    def test_converged_rejects_a_failed_required_validation_entry(self):
        result = copy.deepcopy(self.converged_local)
        result["validation_summary"][1]["status"] = "failed"
        errors = VALIDATE.validate_terminal_result(result)
        self.assertTrue(
            any(
                "converged cannot pair with 'failed' required validation" in error
                for error in errors
            ),
            errors,
        )

    def test_converged_rejects_an_unavailable_required_validation_entry(self):
        result = copy.deepcopy(self.converged_pr)
        result["validation_summary"][0]["status"] = "unavailable"
        errors = VALIDATE.validate_terminal_result(result)
        self.assertTrue(
            any(
                "converged cannot pair with 'unavailable' required validation" in error
                for error in errors
            ),
            errors,
        )

    def test_converged_rejects_a_non_clean_final_head_review_record(self):
        result = copy.deepcopy(self.converged_local)
        result["review_records"][-1]["aggregate_verdict"] = "changes_required"
        errors = VALIDATE.validate_terminal_result(result)
        self.assertTrue(
            any("aggregate_verdict to be 'clean'" in error for error in errors),
            errors,
        )

    def test_converged_rejects_violated_write_isolation_on_final_head_record(self):
        result = copy.deepcopy(self.converged_pr)
        result["review_records"][-1]["write_isolation"] = "violated"
        errors = VALIDATE.validate_terminal_result(result)
        self.assertTrue(
            any("write_isolation to be 'enforced'" in error for error in errors),
            errors,
        )

    def test_converged_rejects_missing_final_head_review_record(self):
        result = copy.deepcopy(self.converged_local)
        result["review_records"] = []
        errors = VALIDATE.validate_terminal_result(result)
        self.assertTrue(
            any(
                "converged requires a review record bound to the exact final "
                "head and comparison base" in error
                for error in errors
            ),
            errors,
        )

    def test_converged_rejects_empty_validation_summary(self):
        result = copy.deepcopy(self.converged_local)
        result["validation_summary"] = []
        errors = VALIDATE.validate_terminal_result(result)
        self.assertTrue(
            any(
                "converged requires a passed focused validation entry" in error
                for error in errors
            )
            and any(
                "converged requires a passed full validation entry" in error
                for error in errors
            ),
            errors,
        )

    def test_converged_rejects_a_missing_validation_scope(self):
        result = copy.deepcopy(self.converged_pr)
        result["validation_summary"] = [
            entry for entry in result["validation_summary"] if entry["scope"] != "full"
        ]
        errors = VALIDATE.validate_terminal_result(result)
        self.assertTrue(
            any(
                "converged requires a passed full validation entry" in error
                for error in errors
            ),
            errors,
        )

    def test_local_commit_publication_status_must_be_not_applicable(self):
        result = copy.deepcopy(self.converged_local)
        result["publication"]["status"] = "published"
        errors = VALIDATE.validate_terminal_result(result)
        self.assertTrue(
            any("local_commit never publishes" in error for error in errors), errors
        )

    def test_converged_update_pr_requires_published_status(self):
        result = copy.deepcopy(self.converged_pr)
        result["publication"]["status"] = "withheld"
        errors = VALIDATE.validate_terminal_result(result)
        self.assertIn(
            "$.publication.status: a converged update_pr result must be published",
            errors,
        )

    def test_changes_remaining_update_pr_requires_withheld_status(self):
        result = copy.deepcopy(self.converged_pr)
        result["terminal_state"] = "changes_remaining"
        result["reason"] = "cycle_budget_exhausted"
        # publication.status is still "published" from the converged fixture.
        errors = VALIDATE.validate_terminal_result(result)
        self.assertIn(
            "$.publication.status: changes_remaining must withhold publication",
            errors,
        )

    def test_blocked_remote_advanced_requires_failed_status(self):
        result = copy.deepcopy(self.blocked)
        result["publication"]["status"] = "withheld"
        errors = VALIDATE.validate_terminal_result(result)
        self.assertIn(
            "$.publication.status: blocked/remote_advanced must be 'failed'",
            errors,
        )

    def test_blocked_non_publication_reason_requires_withheld_status(self):
        result = copy.deepcopy(self.blocked)
        result["reason"] = "missing_capability"
        result["publication"]["status"] = "failed"
        errors = VALIDATE.validate_terminal_result(result)
        self.assertIn(
            "$.publication.status: blocked/missing_capability must be 'withheld'",
            errors,
        )

    def test_unpushed_commits_required_when_head_changed_and_not_published(self):
        result = copy.deepcopy(self.changes_remaining)
        result["unpushed_commits"] = []
        errors = VALIDATE.validate_terminal_result(result)
        self.assertTrue(
            any(
                "no unpushed commits were reported for a non-published result" in error
                for error in errors
            ),
            errors,
        )

    def test_unpushed_commits_must_be_empty_once_published(self):
        result = copy.deepcopy(self.converged_pr)
        result["unpushed_commits"] = [result["head"]["final"]]
        errors = VALIDATE.validate_terminal_result(result)
        self.assertIn(
            "$.unpushed_commits: must be empty once publication.status is published",
            errors,
        )

    def test_acceptance_reconciliation_required_when_head_changed(self):
        result = copy.deepcopy(self.converged_local)
        result["acceptance_reconciliation_required"] = False
        errors = VALIDATE.validate_terminal_result(result)
        self.assertTrue(
            any(
                "must be true when head or comparison_base identity changed" in error
                for error in errors
            ),
            errors,
        )

    def test_budget_arithmetic_must_be_consistent(self):
        result = copy.deepcopy(self.converged_local)
        result["budget"]["remaining_cycles"] = 999
        errors = VALIDATE.validate_terminal_result(result)
        self.assertTrue(
            any(
                "consumed_cycles + remaining_cycles must equal" in error
                for error in errors
            ),
            errors,
        )

    def test_head_history_must_match_head_initial_and_final(self):
        result = copy.deepcopy(self.converged_local)
        result["head_history"][0] = result["head"]["final"]
        errors = VALIDATE.validate_terminal_result(result)
        self.assertIn("$.head_history[0]: must equal head.initial", errors)

    def test_base_revision_history_must_match_comparison_base(self):
        result = copy.deepcopy(self.converged_local)
        result["base_revision_history"][0]["sha"] = result["head"]["final"]
        errors = VALIDATE.validate_terminal_result(result)
        self.assertIn(
            "$.base_revision_history[0]: must equal comparison_base.initial", errors
        )

    def test_source_unavailable_requires_reason(self):
        result = copy.deepcopy(self.converged_local)
        result["source"] = {"status": "unavailable"}
        errors = VALIDATE.validate_terminal_result(result)
        self.assertIn(
            "$.source: unavailable status requires unavailable_reason", errors
        )

    def test_source_bound_requires_initial_and_final_head(self):
        result = copy.deepcopy(self.converged_pr)
        result["source"] = {"status": "bound", "ahead_by": 0, "behind_by": 0}
        errors = VALIDATE.validate_terminal_result(result)
        self.assertIn(
            "$.source: bound status requires initial_head and final_head", errors
        )


class CrossDocumentConsistencyTests(unittest.TestCase):
    """A terminal result must match the checkpoint it derives from."""

    def test_local_commit_terminal_matches_its_checkpoint(self):
        checkpoint = load("local-commit-checkpoint.json")
        terminal = load("local-commit-terminal-converged.json")
        self.assertEqual(
            VALIDATE.validate_terminal_against_checkpoint(checkpoint, terminal), []
        )

    def test_update_pr_terminal_matches_its_checkpoint(self):
        checkpoint = load("update-pr-checkpoint.json")
        terminal = load("update-pr-terminal-converged.json")
        self.assertEqual(
            VALIDATE.validate_terminal_against_checkpoint(checkpoint, terminal), []
        )

    def test_mismatched_budget_is_rejected(self):
        checkpoint = load("local-commit-checkpoint.json")
        terminal = copy.deepcopy(load("local-commit-terminal-converged.json"))
        terminal["budget"]["consumed_cycles"] = 2
        terminal["budget"]["remaining_cycles"] = 1
        errors = VALIDATE.validate_terminal_against_checkpoint(checkpoint, terminal)
        self.assertTrue(
            any(
                "does not match checkpoint-reconstructed value" in error
                for error in errors
            ),
            errors,
        )

    def test_mismatched_invocation_id_is_rejected(self):
        checkpoint = load("local-commit-checkpoint.json")
        terminal = copy.deepcopy(load("local-commit-terminal-converged.json"))
        terminal["invocation_id"] = "some-other-invocation"
        errors = VALIDATE.validate_terminal_against_checkpoint(checkpoint, terminal)
        self.assertIn(
            "$.invocation_id: does not match checkpoint invocation_id", errors
        )

    def test_mismatched_final_head_is_rejected(self):
        checkpoint = load("local-commit-checkpoint.json")
        terminal = copy.deepcopy(load("local-commit-terminal-converged.json"))
        terminal["head"]["final"] = terminal["head"]["initial"]
        errors = VALIDATE.validate_terminal_against_checkpoint(checkpoint, terminal)
        self.assertIn("$.head.final: does not match checkpoint current_head", errors)

    def test_mismatched_final_comparison_base_is_rejected(self):
        checkpoint = load("local-commit-checkpoint.json")
        terminal = copy.deepcopy(load("local-commit-terminal-converged.json"))
        terminal["comparison_base"]["final"]["sha"] = terminal["head"]["final"]
        errors = VALIDATE.validate_terminal_against_checkpoint(checkpoint, terminal)
        self.assertIn(
            "$.comparison_base.final: does not match checkpoint comparison_base",
            errors,
        )

    def test_mismatched_initial_comparison_base_is_rejected(self):
        checkpoint = load("local-commit-checkpoint.json")
        terminal = copy.deepcopy(load("local-commit-terminal-converged.json"))
        terminal["comparison_base"]["initial"]["sha"] = terminal["head"]["final"]
        errors = VALIDATE.validate_terminal_against_checkpoint(checkpoint, terminal)
        self.assertIn(
            "$.comparison_base.initial: does not match checkpoint "
            "base_revision_history[0]",
            errors,
        )


class DeterministicSerializationTests(unittest.TestCase):
    """Contract serialization is deterministic and every example is a complete,
    byte-stable snapshot."""

    def test_every_example_is_already_canonical(self):
        for path in sorted(EXAMPLES.glob("*.json")):
            with self.subTest(example=path.name):
                original_text = path.read_text()
                document = json.loads(original_text)
                self.assertEqual(
                    VALIDATE.canonical_json(document),
                    original_text,
                    f"{path.name} is not in canonical form; re-run the "
                    "canonicalization step",
                )

    def test_canonical_serialization_round_trips(self):
        for path in sorted(EXAMPLES.glob("*.json")):
            with self.subTest(example=path.name):
                document = json.loads(path.read_text())
                serialized = VALIDATE.canonical_json(document)
                reparsed = json.loads(serialized)
                self.assertEqual(document, reparsed)
                # Serializing twice must be byte-identical: no hidden ordering
                # or float-formatting nondeterminism.
                self.assertEqual(serialized, VALIDATE.canonical_json(reparsed))

    def test_key_order_is_independent_of_input_order(self):
        document = load("local-commit-invocation.json")
        reordered = dict(reversed(list(document.items())))
        self.assertEqual(
            VALIDATE.canonical_json(document), VALIDATE.canonical_json(reordered)
        )


if __name__ == "__main__":
    unittest.main()
