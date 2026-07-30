"""Reviewer isolation and complete-review orchestration tests.

Covers lens resolution, rejection of an incomplete or mismatched raw
review-code-change result, default fresh-reviewer selection with no automatic
fallback, the explicit in-agent override, reviewer-identity freshness,
before/after mutation detection that fails a cycle closed, and deterministic
finding normalization/selection.
"""

from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[2]

_ORCH_SPEC = importlib.util.spec_from_file_location(
    "review_fix_loop_reviewer_orchestration",
    SKILL_ROOT / "scripts" / "reviewer_orchestration.py",
)
assert _ORCH_SPEC and _ORCH_SPEC.loader
ORCH = importlib.util.module_from_spec(_ORCH_SPEC)
_ORCH_SPEC.loader.exec_module(ORCH)

_VALIDATE_SPEC = importlib.util.spec_from_file_location(
    "review_fix_loop_validate", SKILL_ROOT / "scripts" / "validate.py"
)
assert _VALIDATE_SPEC and _VALIDATE_SPEC.loader
VALIDATE = importlib.util.module_from_spec(_VALIDATE_SPEC)
_VALIDATE_SPEC.loader.exec_module(VALIDATE)

HEAD = "1212121212121212121212121212121212121212"
BASE = "abababababababababababababababababababab"
OTHER_HEAD = "3434343434343434343434343434343434343434"

CLEAN_AGGREGATE = {
    "schema_version": "1.4",
    "lens": "aggregate",
    "candidate": {"head_sha": HEAD, "comparison_base_sha": BASE},
    "verdict": "clean",
    "findings": [],
    "blocking_reasons": [],
    "lens_executions": [
        {
            "lens": lens,
            "head_sha": HEAD,
            "comparison_base_sha": BASE,
            "verdict": "clean",
            "freshly_executed": True,
        }
        for lens in ("solution_simplicity", "correctness", "code_simplicity")
    ],
    "validation_limitations": [],
    "next_action": "No changes are required.",
}


def _finding(finding_id: str, lens: str, severity: str) -> dict:
    return {
        "id": finding_id,
        "lens": lens,
        "severity": severity,
        "confidence": "high",
        "rule": "example rule",
        "evidence": [{"location": "example.py:1", "detail": "example detail"}],
        "concern": "example concern",
        "impact": "example impact",
        "proposed_change": "example proposed change",
        "expected_effect": "example expected effect",
    }


VALID_PACKET = {
    "schema_version": "1.0",
    "repository": {"identity": "shaug/agent-scripts", "base_branch": "main"},
    "candidate": {
        "head_sha": HEAD,
        "comparison_base_sha": BASE,
        "diff": {
            "format": "unified_diff",
            "complete": True,
            "content": "diff --git a/example.py b/example.py\n",
        },
    },
    "change_contract": {
        "goal": "Fix the example.",
        "acceptance_criteria": ["example.py behaves correctly"],
        "non_goals": [],
        "preserved_behaviors": [],
    },
    "sources": {
        "repository_instructions": [],
        "named_documents": [],
        "nearby_patterns": [],
    },
    "validation": [
        {
            "name": "focused unit test",
            "command": "python3 -m unittest tests.test_example",
            "scope": "focused",
            "status": "passed",
            "result": "OK",
        },
        {
            "name": "full repository gate",
            "command": "just test",
            "scope": "full",
            "status": "passed",
            "result": "OK",
        },
    ],
}


CHANGES_REQUIRED_AGGREGATE = {
    "schema_version": "1.4",
    "lens": "aggregate",
    "candidate": {"head_sha": HEAD, "comparison_base_sha": BASE},
    "verdict": "changes_required",
    "findings": [_finding("correctness-001", "correctness", "blocking")],
    "blocking_reasons": [],
    # The sequence stops at the first gating finding, so only one lens ran.
    "lens_executions": [
        {
            "lens": "solution_simplicity",
            "head_sha": HEAD,
            "comparison_base_sha": BASE,
            "verdict": "clean",
            "freshly_executed": True,
        }
    ],
    "validation_limitations": [],
    "next_action": "Fix correctness-001.",
}


class ResolveReviewLensesTests(unittest.TestCase):
    def test_returns_the_fixed_three_lens_set(self):
        self.assertEqual(
            ("solution_simplicity", "correctness", "code_simplicity"),
            ORCH.resolve_review_lenses(),
        )

    def test_matches_the_bundled_contracts_own_required_set(self):
        # Sourced from the same constant the bundled validator enforces, so
        # this cannot silently drift from what actually gates `clean`.
        self.assertEqual(
            ORCH.REVIEW_SUITE.REQUIRED_AGGREGATE_LENSES, ORCH.resolve_review_lenses()
        )


class EvaluateReviewResultTests(unittest.TestCase):
    def test_current_clean_aggregate_is_accepted(self):
        self.assertEqual([], ORCH.evaluate_review_result(CLEAN_AGGREGATE, HEAD, BASE))

    def test_current_changes_required_with_partial_lens_executions_is_accepted(self):
        # changes_required legitimately stops early; only clean requires full
        # lens completeness.
        self.assertEqual(
            [], ORCH.evaluate_review_result(CHANGES_REQUIRED_AGGREGATE, HEAD, BASE)
        )

    def test_stale_head_is_rejected(self):
        errors = ORCH.evaluate_review_result(CLEAN_AGGREGATE, OTHER_HEAD, BASE)
        self.assertTrue(any("not bound to the current candidate" in e for e in errors))

    def test_stale_base_is_rejected(self):
        errors = ORCH.evaluate_review_result(CLEAN_AGGREGATE, HEAD, OTHER_HEAD)
        self.assertTrue(any("not bound to the current candidate" in e for e in errors))

    def test_malformed_result_is_rejected(self):
        malformed = copy.deepcopy(CLEAN_AGGREGATE)
        del malformed["findings"]
        errors = ORCH.evaluate_review_result(malformed, HEAD, BASE)
        self.assertTrue(errors)
        self.assertTrue(any(e.startswith("schema:") for e in errors))

    def test_clean_missing_one_lens_is_rejected(self):
        incomplete = copy.deepcopy(CLEAN_AGGREGATE)
        incomplete["lens_executions"] = [
            execution
            for execution in incomplete["lens_executions"]
            if execution["lens"] != "code_simplicity"
        ]
        errors = ORCH.evaluate_review_result(incomplete, HEAD, BASE)
        self.assertTrue(errors)
        self.assertTrue(any("code_simplicity" in e for e in errors))

    def test_clean_with_stale_lens_execution_head_is_rejected(self):
        stale = copy.deepcopy(CLEAN_AGGREGATE)
        stale["lens_executions"][0]["head_sha"] = OTHER_HEAD
        errors = ORCH.evaluate_review_result(stale, HEAD, BASE)
        self.assertTrue(errors)

    def test_non_aggregate_lens_result_is_rejected(self):
        solo = copy.deepcopy(CLEAN_AGGREGATE)
        solo["lens"] = "correctness"
        solo["lens_executions"] = []
        errors = ORCH.evaluate_review_result(solo, HEAD, BASE)
        self.assertTrue(any("expected an aggregate result" in e for e in errors))

    def test_blocked_result_bound_to_candidate_is_accepted(self):
        blocked = {
            "schema_version": "1.4",
            "lens": "aggregate",
            "candidate": {},
            "verdict": "blocked",
            "findings": [],
            "blocking_reasons": ["missing repository identity"],
        }
        # `blocked` legitimately omits candidate identity when it could not
        # be established; this must not be rejected as an unbound candidate.
        self.assertEqual([], ORCH.evaluate_review_result(blocked, HEAD, BASE))


class EvaluateReviewPairTests(unittest.TestCase):
    def test_valid_packet_and_clean_result_are_accepted(self):
        self.assertEqual(
            [], ORCH.evaluate_review_pair(VALID_PACKET, CLEAN_AGGREGATE, HEAD, BASE)
        )

    def test_clean_result_paired_with_failed_packet_validation_is_rejected(self):
        packet = copy.deepcopy(VALID_PACKET)
        packet["validation"][0]["status"] = "failed"
        packet["validation"][0]["result"] = "AssertionError: boom"
        errors = ORCH.evaluate_review_pair(packet, CLEAN_AGGREGATE, HEAD, BASE)
        self.assertTrue(errors)

    def test_clean_result_paired_with_unavailable_packet_validation_is_rejected(self):
        packet = copy.deepcopy(VALID_PACKET)
        packet["validation"][1]["status"] = "unavailable"
        del packet["validation"][1]["result"]
        packet["validation"][1]["reason"] = "sandbox has no network access"
        errors = ORCH.evaluate_review_pair(packet, CLEAN_AGGREGATE, HEAD, BASE)
        self.assertTrue(errors)

    def test_packet_candidate_mismatch_with_result_is_rejected(self):
        packet = copy.deepcopy(VALID_PACKET)
        packet["candidate"]["head_sha"] = OTHER_HEAD
        errors = ORCH.evaluate_review_pair(packet, CLEAN_AGGREGATE, HEAD, BASE)
        self.assertTrue(errors)

    def test_still_enforces_expected_candidate_binding(self):
        # Packet and result agree with each other but not with what this
        # cycle actually expects.
        errors = ORCH.evaluate_review_pair(
            VALID_PACKET, CLEAN_AGGREGATE, OTHER_HEAD, BASE
        )
        self.assertTrue(any("not bound to the current candidate" in e for e in errors))

    def test_changes_required_with_partial_lens_executions_is_still_accepted(self):
        self.assertEqual(
            [],
            ORCH.evaluate_review_pair(
                VALID_PACKET, CHANGES_REQUIRED_AGGREGATE, HEAD, BASE
            ),
        )


class ResolveReviewExecutionModeTests(unittest.TestCase):
    def test_default_capable_host_gets_fresh_subagent(self):
        resolution = ORCH.resolve_review_execution_mode(
            "fresh_subagent", host_supports_fresh_subagent=True
        )
        self.assertEqual("fresh_subagent", resolution["independence"])
        self.assertIsNone(resolution["blocked_reason"])
        self.assertIsNone(resolution["authorized_by"])

    def test_incapable_host_with_no_override_is_blocked_missing_capability(self):
        resolution = ORCH.resolve_review_execution_mode(
            "fresh_subagent", host_supports_fresh_subagent=False
        )
        self.assertIsNone(resolution["independence"])
        self.assertEqual("missing_capability", resolution["blocked_reason"])

    def test_explicit_override_is_honored_and_recorded(self):
        resolution = ORCH.resolve_review_execution_mode(
            "in_agent_override",
            override_authorization="operator approved in-agent review for #42",
            host_supports_fresh_subagent=True,
        )
        self.assertEqual("in_agent_override", resolution["independence"])
        self.assertEqual(
            "operator approved in-agent review for #42", resolution["authorized_by"]
        )
        self.assertIsNone(resolution["blocked_reason"])

    def test_override_is_honored_even_when_fresh_subagent_would_be_available(self):
        # An explicit override does not require the fresh path to be
        # unavailable first.
        resolution = ORCH.resolve_review_execution_mode(
            "in_agent_override",
            override_authorization="explicit operator override",
            host_supports_fresh_subagent=True,
        )
        self.assertEqual("in_agent_override", resolution["independence"])

    def test_unknown_mode_raises(self):
        with self.assertRaises(ValueError):
            ORCH.resolve_review_execution_mode("read_only")


class GenerateReviewerIdentityTests(unittest.TestCase):
    def test_default_identity_matches_example_convention(self):
        self.assertEqual(
            "fresh-subagent-review-1",
            ORCH.generate_reviewer_identity("fresh_subagent", 1),
        )
        self.assertEqual(
            "fresh-subagent-review-2",
            ORCH.generate_reviewer_identity("fresh_subagent", 2),
        )

    def test_different_sequence_yields_a_different_identity(self):
        first = ORCH.generate_reviewer_identity("fresh_subagent", 1)
        second = ORCH.generate_reviewer_identity("fresh_subagent", 2)
        self.assertNotEqual(first, second)

    def test_in_agent_override_identity_shape(self):
        self.assertEqual(
            "in-agent-override-review-1",
            ORCH.generate_reviewer_identity("in_agent_override", 1),
        )

    def test_explicit_identity_wins(self):
        self.assertEqual(
            "session-abc123",
            ORCH.generate_reviewer_identity(
                "fresh_subagent", 1, explicit="session-abc123"
            ),
        )

    def test_rejects_non_positive_sequence(self):
        with self.assertRaises(ValueError):
            ORCH.generate_reviewer_identity("fresh_subagent", 0)


class DetectWorktreeMutationTests(unittest.TestCase):
    CLEAN_STATE = {
        "head_sha": HEAD,
        "tracked": ["a.py"],
        "staged": [],
        "unstaged": [],
        "untracked": [],
        "ignored": [],
    }

    def test_identical_snapshots_report_no_mutation(self):
        before = copy.deepcopy(self.CLEAN_STATE)
        after = copy.deepcopy(self.CLEAN_STATE)
        self.assertEqual([], ORCH.detect_worktree_mutation(before, after))

    def test_head_advance_is_detected(self):
        before = copy.deepcopy(self.CLEAN_STATE)
        after = copy.deepcopy(self.CLEAN_STATE)
        after["head_sha"] = OTHER_HEAD
        mutations = ORCH.detect_worktree_mutation(before, after)
        self.assertTrue(any("head_sha advanced" in m for m in mutations))

    def test_staged_addition_is_detected(self):
        before = copy.deepcopy(self.CLEAN_STATE)
        after = copy.deepcopy(self.CLEAN_STATE)
        after["staged"] = ["evil.py"]
        mutations = ORCH.detect_worktree_mutation(before, after)
        self.assertTrue(any(m.startswith("staged:") for m in mutations))

    def test_untracked_addition_is_detected(self):
        before = copy.deepcopy(self.CLEAN_STATE)
        after = copy.deepcopy(self.CLEAN_STATE)
        after["untracked"] = ["stray.py"]
        mutations = ORCH.detect_worktree_mutation(before, after)
        self.assertTrue(any(m.startswith("untracked:") for m in mutations))

    def test_tracked_removal_is_detected(self):
        before = copy.deepcopy(self.CLEAN_STATE)
        after = copy.deepcopy(self.CLEAN_STATE)
        after["tracked"] = []
        mutations = ORCH.detect_worktree_mutation(before, after)
        self.assertTrue(
            any("removed" in m and m.startswith("tracked:") for m in mutations)
        )

    def test_ignored_changes_are_still_detected(self):
        # `ignored` is not part of invocation "clean" (build output etc.),
        # but a reviewer touching it is still an attempted write this check
        # must surface.
        before = copy.deepcopy(self.CLEAN_STATE)
        after = copy.deepcopy(self.CLEAN_STATE)
        after["ignored"] = ["build/output.bin"]
        mutations = ORCH.detect_worktree_mutation(before, after)
        self.assertTrue(any(m.startswith("ignored:") for m in mutations))

    def test_new_local_ref_is_detected(self):
        # A reviewer that runs `git stash` or creates a branch without
        # touching HEAD or any tracked path is still a write-isolation
        # violation.
        before = copy.deepcopy(self.CLEAN_STATE)
        before["refs"] = {"refs/heads/main": HEAD}
        after = copy.deepcopy(before)
        after["refs"] = {"refs/heads/main": HEAD, "refs/stash": OTHER_HEAD}
        mutations = ORCH.detect_worktree_mutation(before, after)
        self.assertTrue(any(m.startswith("refs:") and "added" in m for m in mutations))

    def test_force_moved_local_ref_is_detected(self):
        before = copy.deepcopy(self.CLEAN_STATE)
        before["refs"] = {"refs/heads/evil": HEAD}
        after = copy.deepcopy(self.CLEAN_STATE)
        after["refs"] = {"refs/heads/evil": OTHER_HEAD}
        mutations = ORCH.detect_worktree_mutation(before, after)
        self.assertTrue(
            any(m.startswith("refs:") and "changed" in m for m in mutations)
        )

    def test_removed_local_ref_is_detected(self):
        before = copy.deepcopy(self.CLEAN_STATE)
        before["refs"] = {"refs/heads/evil": HEAD}
        after = copy.deepcopy(self.CLEAN_STATE)
        after["refs"] = {}
        mutations = ORCH.detect_worktree_mutation(before, after)
        self.assertTrue(
            any(m.startswith("refs:") and "removed" in m for m in mutations)
        )

    def test_remote_tracking_ref_change_alone_is_not_flagged(self):
        # Excluded from comparison: an unattributed remote-tracking-ref
        # advance is the ordinary remote_advanced publication-race contract,
        # not reviewer misconduct.
        before = copy.deepcopy(self.CLEAN_STATE)
        before["refs"] = {"refs/remotes/origin/main": HEAD}
        after = copy.deepcopy(self.CLEAN_STATE)
        after["refs"] = {"refs/remotes/origin/main": OTHER_HEAD}
        self.assertEqual([], ORCH.detect_worktree_mutation(before, after))

    def test_identical_refs_report_no_mutation(self):
        before = copy.deepcopy(self.CLEAN_STATE)
        before["refs"] = {"refs/heads/main": HEAD}
        after = copy.deepcopy(before)
        self.assertEqual([], ORCH.detect_worktree_mutation(before, after))

    def test_missing_refs_key_is_treated_as_no_refs(self):
        # `refs` is optional; a snapshot without it must not be treated as
        # differing from one with an explicit empty mapping.
        before = copy.deepcopy(self.CLEAN_STATE)
        after = copy.deepcopy(self.CLEAN_STATE)
        after["refs"] = {}
        self.assertEqual([], ORCH.detect_worktree_mutation(before, after))


class BuildReviewRecordTests(unittest.TestCase):
    def test_builds_expected_shape_for_clean_result(self):
        record = ORCH.build_review_record(
            sequence=1,
            result=CLEAN_AGGREGATE,
            expected_head=HEAD,
            expected_base=BASE,
            independence="fresh_subagent",
            reviewer_identity="fresh-subagent-review-1",
        )
        self.assertEqual(
            {
                "sequence": 1,
                "head_sha": HEAD,
                "comparison_base_sha": BASE,
                "review_independence": "fresh_subagent",
                "reviewer_identity": "fresh-subagent-review-1",
                "write_isolation": "enforced",
                "aggregate_verdict": "clean",
                "finding_dispositions": [],
                "mutation_attempts": [],
            },
            record,
        )

    def test_matches_checkpoint_review_records_item_schema(self):
        record = ORCH.build_review_record(
            sequence=1,
            result=CLEAN_AGGREGATE,
            expected_head=HEAD,
            expected_base=BASE,
            independence="fresh_subagent",
            reviewer_identity="fresh-subagent-review-1",
        )
        schema = VALIDATE._load_schema("checkpoint")
        item_schema = schema["properties"]["review_records"]["items"]
        self.assertEqual([], VALIDATE.validate_schema(record, item_schema))

    def test_mutation_forces_write_isolation_violated(self):
        record = ORCH.build_review_record(
            sequence=1,
            result=CLEAN_AGGREGATE,
            expected_head=HEAD,
            expected_base=BASE,
            independence="fresh_subagent",
            reviewer_identity="fresh-subagent-review-1",
            mutation_attempts=["staged: added ['evil.py']"],
        )
        self.assertEqual("violated", record["write_isolation"])
        self.assertEqual(["staged: added ['evil.py']"], record["mutation_attempts"])

    def test_mutation_record_fails_a_converged_terminal_result_closed(self):
        """Integration: a mutation-tainted record cannot certify convergence.

        Acceptance criterion: "Tests detect attempted reviewer mutation and
        fail the cycle closed." This proves it end to end using the skill's
        own checkpoint/terminal-result validator: even though the aggregate
        verdict itself is `clean`, `validate_terminal_result` must reject a
        `converged` result whose `review_records` contains this record.
        """
        record = ORCH.build_review_record(
            sequence=1,
            result=CLEAN_AGGREGATE,
            expected_head=HEAD,
            expected_base=BASE,
            independence="fresh_subagent",
            reviewer_identity="fresh-subagent-review-1",
            mutation_attempts=["untracked: added ['evil.py']"],
        )
        terminal_result = {
            "schema_version": "1.0",
            "invocation_id": "test-invocation",
            "terminal_state": "converged",
            "budget": {
                "original_max_fix_cycles": 3,
                "consumed_cycles": 0,
                "remaining_cycles": 3,
            },
            "resume_status": "not_resumed",
            "repository": {
                "identity": "shaug/agent-scripts",
                "git_common_directory": "/x/.git",
            },
            "branch": "fix/example",
            "worktree": {
                "tracked": [],
                "staged": [],
                "unstaged": [],
                "untracked": [],
                "ignored": [],
            },
            "head": {"initial": HEAD, "final": HEAD},
            "comparison_base": {
                "initial": {"ref": "main", "sha": BASE},
                "final": {"ref": "main", "sha": BASE},
            },
            "head_history": [HEAD],
            "base_revision_history": [{"ref": "main", "sha": BASE}],
            "review_records": [record],
            "validation_summary": [
                {
                    "name": "focused",
                    "command": "python3 -m unittest",
                    "scope": "focused",
                    "status": "passed",
                    "result": "OK",
                },
                {
                    "name": "full",
                    "command": "just test",
                    "scope": "full",
                    "status": "passed",
                    "result": "OK",
                },
            ],
            "finding_dispositions": [],
            "created_commits": [],
            "preserved_failed_attempts": [],
            "source": {"status": "unavailable", "unavailable_reason": "example"},
            "unpushed_commits": [],
            "publication": {
                "policy": "local_commit",
                "status": "not_applicable",
                "non_converged_exposure": False,
            },
            "acceptance_reconciliation_required": False,
            "unresolved_or_deferred_findings": [],
            "operator_action": "none",
        }
        errors = VALIDATE.validate_terminal_result(terminal_result)
        self.assertTrue(
            any("mutation attempt" in e for e in errors),
            f"expected a mutation-attempt rejection, got: {errors}",
        )

    def test_incomplete_result_raises_review_integrity_error(self):
        incomplete = copy.deepcopy(CLEAN_AGGREGATE)
        incomplete["lens_executions"] = incomplete["lens_executions"][:2]
        with self.assertRaises(ORCH.ReviewIntegrityError) as context:
            ORCH.build_review_record(
                sequence=1,
                result=incomplete,
                expected_head=HEAD,
                expected_base=BASE,
                independence="fresh_subagent",
                reviewer_identity="fresh-subagent-review-1",
            )
        self.assertTrue(context.exception.errors)

    def test_stale_candidate_raises_review_integrity_error(self):
        with self.assertRaises(ORCH.ReviewIntegrityError):
            ORCH.build_review_record(
                sequence=1,
                result=CLEAN_AGGREGATE,
                expected_head=OTHER_HEAD,
                expected_base=BASE,
                independence="fresh_subagent",
                reviewer_identity="fresh-subagent-review-1",
            )

    def test_packet_with_failed_validation_raises_even_for_clean_result(self):
        packet = copy.deepcopy(VALID_PACKET)
        packet["validation"][0]["status"] = "failed"
        packet["validation"][0]["result"] = "AssertionError: boom"
        with self.assertRaises(ORCH.ReviewIntegrityError):
            ORCH.build_review_record(
                sequence=1,
                result=CLEAN_AGGREGATE,
                expected_head=HEAD,
                expected_base=BASE,
                independence="fresh_subagent",
                reviewer_identity="fresh-subagent-review-1",
                packet=packet,
            )

    def test_valid_packet_is_accepted_and_produces_the_same_record(self):
        record = ORCH.build_review_record(
            sequence=1,
            result=CLEAN_AGGREGATE,
            expected_head=HEAD,
            expected_base=BASE,
            independence="fresh_subagent",
            reviewer_identity="fresh-subagent-review-1",
            packet=VALID_PACKET,
        )
        self.assertEqual("clean", record["aggregate_verdict"])
        self.assertEqual("enforced", record["write_isolation"])

    def test_changes_required_result_is_accepted_and_recorded(self):
        record = ORCH.build_review_record(
            sequence=1,
            result=CHANGES_REQUIRED_AGGREGATE,
            expected_head=HEAD,
            expected_base=BASE,
            independence="fresh_subagent",
            reviewer_identity="fresh-subagent-review-1",
        )
        self.assertEqual("changes_required", record["aggregate_verdict"])
        self.assertEqual("enforced", record["write_isolation"])

    def test_one_record_per_aggregate_pass_regardless_of_nested_lens_count(self):
        # Nested lenses may share the aggregate-review subagent: this module
        # only ever produces one review_records entry per aggregate call, no
        # matter how many lenses ran inside it.
        record = ORCH.build_review_record(
            sequence=1,
            result=CLEAN_AGGREGATE,
            expected_head=HEAD,
            expected_base=BASE,
            independence="fresh_subagent",
            reviewer_identity="fresh-subagent-review-1",
        )
        self.assertEqual(1, record["sequence"])
        self.assertNotIn("lens_executions", record)


class NormalizeFindingsTests(unittest.TestCase):
    def test_sorted_by_severity_then_lens_then_id(self):
        findings = [
            _finding("code-simplicity-002", "code_simplicity", "defer"),
            _finding("correctness-001", "correctness", "blocking"),
            _finding(
                "solution-simplicity-003",
                "solution_simplicity",
                "strong_recommendation",
            ),
        ]
        normalized = ORCH.normalize_findings(findings)
        self.assertEqual(
            ["correctness-001", "solution-simplicity-003", "code-simplicity-002"],
            [finding["id"] for finding in normalized],
        )

    def test_deterministic_across_input_permutations(self):
        findings = [
            _finding("z-defer", "code_simplicity", "defer"),
            _finding("a-blocking", "correctness", "blocking"),
            _finding("m-strong", "solution_simplicity", "strong_recommendation"),
            _finding("b-blocking", "code_simplicity", "blocking"),
        ]
        import itertools

        orders = set()
        for permutation in itertools.permutations(findings):
            normalized = ORCH.normalize_findings(permutation)
            orders.add(tuple(finding["id"] for finding in normalized))
        self.assertEqual(1, len(orders))

    def test_does_not_mutate_input(self):
        findings = [_finding("correctness-001", "correctness", "blocking")]
        original = copy.deepcopy(findings)
        ORCH.normalize_findings(findings)
        self.assertEqual(original, findings)

    def test_copies_are_independent_of_input_dicts(self):
        findings = [_finding("correctness-001", "correctness", "blocking")]
        normalized = ORCH.normalize_findings(findings)
        normalized[0]["severity"] = "defer"
        self.assertEqual("blocking", findings[0]["severity"])


class SelectNextFindingTests(unittest.TestCase):
    def test_selects_the_only_blocking_finding_first(self):
        findings = [
            _finding("defer-1", "code_simplicity", "defer"),
            _finding("blocking-1", "correctness", "blocking"),
        ]
        selected = ORCH.select_next_finding(findings)
        self.assertEqual("blocking-1", selected["id"])

    def test_falls_back_to_strong_recommendation_when_no_blocking_remains(self):
        findings = [
            _finding("defer-1", "code_simplicity", "defer"),
            _finding("strong-1", "solution_simplicity", "strong_recommendation"),
        ]
        selected = ORCH.select_next_finding(findings)
        self.assertEqual("strong-1", selected["id"])

    def test_returns_none_when_only_deferred_findings_remain(self):
        findings = [_finding("defer-1", "code_simplicity", "defer")]
        self.assertIsNone(ORCH.select_next_finding(findings))

    def test_returns_none_for_empty_findings(self):
        self.assertIsNone(ORCH.select_next_finding([]))

    def test_selection_is_order_independent(self):
        first_order = [
            _finding("blocking-b", "code_simplicity", "blocking"),
            _finding("blocking-a", "correctness", "blocking"),
        ]
        second_order = list(reversed(first_order))
        self.assertEqual(
            ORCH.select_next_finding(first_order)["id"],
            ORCH.select_next_finding(second_order)["id"],
        )


class BuildReviewerBriefingTests(unittest.TestCase):
    def test_includes_every_prohibition(self):
        briefing = ORCH.build_reviewer_briefing(
            independence="fresh_subagent", head_sha=HEAD, comparison_base_sha=BASE
        )
        for prohibition in ORCH.REVIEWER_PROHIBITIONS:
            self.assertIn(prohibition, briefing)

    def test_includes_exact_candidate_identity_and_mode(self):
        briefing = ORCH.build_reviewer_briefing(
            independence="in_agent_override", head_sha=HEAD, comparison_base_sha=BASE
        )
        self.assertIn(HEAD, briefing)
        self.assertIn(BASE, briefing)
        self.assertIn("in_agent_override", briefing)

    def test_prohibits_consulting_the_implementation_transcript(self):
        briefing = ORCH.build_reviewer_briefing(
            independence="fresh_subagent", head_sha=HEAD, comparison_base_sha=BASE
        )
        self.assertIn("implementation transcript", briefing)


if __name__ == "__main__":
    unittest.main()
