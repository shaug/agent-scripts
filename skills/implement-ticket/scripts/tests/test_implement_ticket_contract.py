from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = SKILL_ROOT.parents[1]


def read(path: Path) -> str:
    return path.read_text()


def compact(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


class ImplementTicketContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = read(SKILL_ROOT / "SKILL.md")
        cls.github = read(SKILL_ROOT / "references" / "github.md")
        cls.linear = read(SKILL_ROOT / "references" / "linear.md")
        cls.gates = read(SKILL_ROOT / "references" / "review-and-merge-gates.md")
        cls.result = read(SKILL_ROOT / "references" / "cleanup-and-result.md")
        cls.skill_compact = compact(cls.skill)
        cls.github_compact = compact(cls.github)
        cls.linear_compact = compact(cls.linear)
        cls.gates_compact = compact(cls.gates)
        cls.result_compact = compact(cls.result)
        cls.all_contract = compact(
            cls.skill + cls.github + cls.linear + cls.gates + cls.result
        )
        cls.cases = {
            item["id"]: item
            for item in json.loads(read(SKILL_ROOT / "evals" / "cases.json"))
        }
        cls.results = {
            item["case_id"]: item
            for item in json.loads(read(SKILL_ROOT / "evals" / "results.json"))
        }

    def test_frontmatter_and_product_neutral_contract(self):
        self.assertTrue(self.skill.startswith("---\nname: implement-ticket\n"))
        self.assertNotIn("Codex", self.all_contract)
        self.assertNotIn("code-review-pro", self.all_contract)
        self.assertIn("compatible agentic runtime", self.skill)

    def test_scope_is_exactly_one_ticket(self):
        self.assertIn("one ticket per branch, worktree, and PR", self.skill_compact)
        self.assertIn("do not select or implement it", self.skill_compact)
        self.assertIn("Never claim whole-epic acceptance", self.skill_compact)
        self.assertIn("parent and sibling context as evidence", self.skill_compact)
        self.assertIn(
            "canonical owner of generic single-ticket readiness",
            self.skill_compact,
        )
        self.assertIn(
            "`implement-epic` consumes this contract",
            self.skill_compact,
        )
        self.assertNotIn("implement-epic-sequence", self.skill_compact)

    def test_epic_routing_is_pre_mutation_and_acyclic(self):
        self.assertIn("Guard whole-epic scope before mutation", self.skill_compact)
        self.assertIn("Treat a named child of an epic", self.skill_compact)
        self.assertIn("Do not invoke or require `implement-epic`", self.skill_compact)
        self.assertIn(
            "implement-ticket:requires-epic:<tracker>:<ticket-id>",
            self.all_contract,
        )
        self.assertIn("routing cycle detected", self.all_contract)

    def test_readiness_fails_closed_without_widening_scope(self):
        self.assertIn("no unresolved native blocker", self.skill_compact)
        self.assertIn(
            "closed, canceled, or not-planned prerequisite", self.skill_compact
        )
        self.assertIn("never absorb that sibling", self.skill_compact)
        self.assertIn("require explicit ownership transfer", self.skill_compact)
        self.assertIn(
            "never claim its candidate as this run's `ready_pr`", self.github_compact
        )

    def test_authority_does_not_expand(self):
        self.assertIn("ready PR only", self.skill_compact)
        self.assertIn("merge after gates", self.skill_compact)
        self.assertIn("merge plus manual transition", self.skill_compact)
        self.assertIn(
            "parent closure always require separate explicit authority",
            self.all_contract,
        )
        self.assertIn(
            "When merge authority is unclear, stop at a ready PR", self.skill_compact
        )
        self.assertIn(
            "automatic ticket transition caused by the selected closing syntax",
            self.skill_compact,
        )
        self.assertIn(
            "disclose the consequence in the resolved completion policy",
            self.github_compact,
        )

    def test_review_dependency_and_integrity_are_preserved(self):
        self.assertIn("only local adversarial-review dependency", self.all_contract)
        self.assertIn("Do not substitute another skill", self.gates_compact)
        self.assertIn(
            "fresh or minimally inherited read-only context", self.gates_compact
        )
        self.assertIn("Exclude the implementation transcript", self.gates_compact)
        self.assertIn("at most three full fix/re-review cycles", self.gates_compact)
        self.assertIn("Treat any mutation as an integrity failure", self.gates_compact)

    def test_current_candidate_and_remote_gates_are_preserved(self):
        self.assertIn(
            "effective diff and resulting tree are unchanged", self.gates_compact
        )
        self.assertIn("no conflict or relevant overlap exists", self.gates_compact)
        self.assertIn("human and connector review is current", self.gates_compact)
        self.assertIn("zero undispositioned actionable items", self.github_compact)
        self.assertIn("Do not infer current approval", self.github_compact)

    def test_tracker_and_pr_host_ownership_are_separate(self):
        self.assertIn("same-numbered GitHub issue", self.github_compact)
        self.assertIn("Linear owns the ticket", self.github_compact)
        self.assertIn("Resolve repository, PR host", self.linear_compact)
        self.assertIn("Do not close or verify the parent epic", self.linear_compact)

    def test_cleanup_and_result_contract_are_complete(self):
        for state in ("ready_pr", "merged", "blocked", "requires_epic"):
            self.assertIn(state, self.result_compact)
        self.assertIn(
            "tracked, staged, unstaged, untracked, and ignored", self.result_compact
        )
        self.assertIn("Never force removal", self.result_compact)
        self.assertIn("Do not close a parent epic", self.result_compact)
        self.assertIn(
            "affected native dependency relationships were reread after the transition",
            self.result_compact,
        )
        self.assertIn("report newly unblocked work", self.github_compact)
        self.assertIn("report newly unblocked work", self.linear_compact)

    def test_forward_cases_cover_required_boundaries(self):
        required = {
            "standalone-ready-pr",
            "authorized-merge-cleanup",
            "named-epic-child-only",
            "open-native-blocker",
            "closed-prerequisite-outcome-missing",
            "sibling-outcome-missing",
            "canonical-pr-owned-elsewhere",
            "correctness-fix-and-rereview",
            "clean-local-review-remote-pending",
            "unrelated-base-drift-retained",
            "linear-ticket-github-pr",
            "epic-with-children",
            "undecomposed-epic",
            "explicit-child-not-redirected",
            "missing-implement-epic",
            "repeated-epic-handoff",
        }
        self.assertEqual(required, set(self.cases))
        self.assertEqual(required, set(self.results))

    def test_forward_results_enforce_routing_and_authority(self):
        self.assertEqual(
            "ready_pr", self.results["standalone-ready-pr"]["terminal_state"]
        )
        self.assertEqual(
            "blocked",
            self.results["canonical-pr-owned-elsewhere"]["terminal_state"],
        )
        self.assertEqual(
            "blocked", self.results["sibling-outcome-missing"]["terminal_state"]
        )
        self.assertEqual(
            "requires_epic",
            self.results["missing-implement-epic"]["terminal_state"],
        )
        self.assertEqual(
            "blocked", self.results["repeated-epic-handoff"]["terminal_state"]
        )
        self.assertIn(
            "do not merge",
            self.results["clean-local-review-remote-pending"]["required_actions"],
        )

    def test_ui_metadata_matches_skill(self):
        metadata = read(SKILL_ROOT / "agents" / "openai.yaml")
        self.assertIn('display_name: "Implement Ticket"', metadata)
        self.assertIn("$implement-ticket", metadata)


if __name__ == "__main__":
    unittest.main()
