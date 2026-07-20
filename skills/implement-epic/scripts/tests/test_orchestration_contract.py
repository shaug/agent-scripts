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


class ImplementEpicContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = read(SKILL_ROOT / "SKILL.md")
        cls.github = read(SKILL_ROOT / "references" / "github.md")
        cls.linear = read(SKILL_ROOT / "references" / "linear.md")
        cls.closeout = read(SKILL_ROOT / "references" / "closeout.md")
        cls.contract = compact(cls.skill + cls.github + cls.linear + cls.closeout)
        cls.eval_contract = compact(
            read(SKILL_ROOT / "evals" / "cases.json")
            + read(SKILL_ROOT / "evals" / "results.json")
        )
        cls.cases = {
            item["id"]: item
            for item in json.loads(read(SKILL_ROOT / "evals" / "cases.json"))
        }
        cls.results = {
            item["case_id"]: item
            for item in json.loads(read(SKILL_ROOT / "evals" / "results.json"))
        }

    def test_canonical_name_and_metadata(self):
        self.assertTrue(self.skill.startswith("---\nname: implement-epic\n"))
        self.assertNotIn("implement-epic-sequence", self.contract)
        self.assertFalse((REPOSITORY_ROOT / "skills/implement-epic-sequence").exists())
        metadata = read(SKILL_ROOT / "agents" / "openai.yaml")
        self.assertIn('display_name: "Implement Epic"', metadata)
        self.assertIn("$implement-epic", metadata)
        self.assertNotIn("$implement-epic-sequence", metadata)

    def test_product_neutral_runtime_contract(self):
        self.assertNotIn("Codex", self.contract)
        self.assertNotIn("OpenAI", self.contract)
        self.assertNotIn("Codex", self.eval_contract)
        self.assertNotIn("OpenAI", self.eval_contract)
        self.assertIn("compatible agentic runtime", self.contract)
        self.assertIn(
            "`implement-epic` and repository-owned `implement-ticket` by stable skill name",
            self.contract,
        )
        self.assertIn(
            "`implement-epic` → `implement-ticket` → `review-code-change`",
            self.contract,
        )
        self.assertIn("retain task state", self.contract)
        self.assertIn("poll or wait for asynchronous", self.contract)
        self.assertIn(
            "worker and subagent describe possible isolated execution roles",
            self.contract,
        )
        self.assertIn("does not constrain the operating contract", self.contract)

    def test_implement_ticket_is_required_and_owns_one_ticket(self):
        self.assertIn("verify that `implement-ticket` is available", self.contract)
        self.assertIn(
            "supports `ready_pr`, `merged`, `blocked`, and `requires_epic`",
            self.contract,
        )
        self.assertIn("Return `blocked` before mutation", self.contract)
        self.assertIn("Invoke `implement-ticket` once", self.skill)
        self.assertIn("never reproduce its one-ticket workflow", self.skill)

    def test_epic_does_not_own_review_or_ticket_mechanics(self):
        self.assertIn("Do not invoke individual review lenses", self.contract)
        self.assertIn(
            "Do not invoke individual review lenses or `review-code-change` directly",
            self.contract,
        )
        self.assertNotIn("review-solution-simplicity", self.contract)
        self.assertNotIn("review-correctness", self.contract)
        self.assertNotIn("review-code-simplicity", self.contract)
        self.assertNotIn("fix/re-review cycles", self.contract)
        self.assertNotIn("per-PR cleanup", self.closeout)

    def test_graph_selection_and_refresh_use_live_native_state(self):
        self.assertIn(
            "native parent, sub-issue, `blockedBy`, and `blocking`", self.contract
        )
        self.assertIn("After every verified merge", self.contract)
        self.assertIn("reread the native graph", self.contract)
        self.assertIn("Do not reuse an earlier ready set", self.contract)
        self.assertIn(
            "A `ready_pr` result does not satisfy a dependency", self.contract
        )

    def test_result_handling_is_fail_closed(self):
        for state in ("ready_pr", "merged", "blocked", "requires_epic"):
            self.assertIn(f"`{state}`", self.contract)
        self.assertIn("Do not count the child complete", self.contract)
        self.assertIn("Never count it as complete", self.contract)
        self.assertIn("never recursively invoke this skill", self.contract)

    def test_scope_and_authority_do_not_expand(self):
        self.assertIn(
            "Pass authority into `implement-ticket` without expansion", self.contract
        )
        self.assertIn(
            "Child merge authority does not imply parent closeout", self.contract
        )
        self.assertIn("For one named child, stop", self.contract)
        self.assertIn("Do not implement unnamed siblings", self.contract)
        self.assertIn("Parent-close authority is separate", self.contract)

    def test_delegated_mutation_is_exclusive(self):
        self.assertIn(
            "exclusive ownership of one verified ticket worktree", self.contract
        )
        self.assertIn(
            "Never run two mutating contexts against the same candidate", self.contract
        )
        self.assertIn(
            "reject parallel mutation",
            self.results["parallel-nonoverlap-required"]["required_actions"],
        )
        self.assertEqual(
            "serial_execution_required",
            self.results["parallel-nonoverlap-required"]["workflow_state"],
        )

    def test_tracker_and_pr_host_ownership_are_separate(self):
        self.assertIn("Resolve issue-tracker ownership independently", self.contract)
        self.assertIn("`implement-ticket` owns GitHub PR-host", self.contract)
        self.assertIn("same-numbered GitHub issues", self.contract)
        self.assertIn("same-numbered GitHub issue", self.contract)

    def test_closeout_is_epic_wide_and_conservative(self):
        self.assertIn("Verify parent acceptance criteria", self.contract)
        self.assertIn("Sweep late feedback", self.contract)
        self.assertIn("keep the epic open", self.contract)
        self.assertIn("invoke `implement-ticket`", self.contract)
        self.assertIn("Close each epic separately", self.contract)

    def test_forward_cases_cover_composed_contract(self):
        required = {
            "two-child-refresh-chain",
            "named-child-boundary",
            "ready-pr-does-not-unblock",
            "blocked-missing-sibling-outcome",
            "blocked-then-independent-ready",
            "missing-implement-ticket",
            "exclusive-delegated-worktree",
            "ticket-evidence-pass-through",
            "late-feedback-blocks-closeout",
            "authorized-full-epic-closeout",
            "umbrella-closeout-separately",
            "unexpected-requires-epic-child-result",
            "parallel-nonoverlap-required",
            "equivalent-isolated-context-profile",
            "missing-review-dependency-through-ticket",
            "missing-isolation-capability",
            "missing-asynchronous-wait",
        }
        self.assertEqual(required, set(self.cases))
        self.assertEqual(required, set(self.results))

    def test_forward_results_preserve_critical_boundaries(self):
        self.assertEqual(
            "waiting_for_child_merge",
            self.results["ready-pr-does-not-unblock"]["workflow_state"],
        )
        self.assertEqual(
            "blocked", self.results["missing-implement-ticket"]["workflow_state"]
        )
        self.assertEqual(
            "closeout_blocked",
            self.results["late-feedback-blocks-closeout"]["workflow_state"],
        )
        self.assertEqual(
            "blocked",
            self.results["unexpected-requires-epic-child-result"]["workflow_state"],
        )
        self.assertEqual(
            "epic_children_merged",
            self.results["equivalent-isolated-context-profile"]["workflow_state"],
        )
        for case_id in (
            "missing-review-dependency-through-ticket",
            "missing-isolation-capability",
            "missing-asynchronous-wait",
        ):
            self.assertEqual("blocked", self.results[case_id]["workflow_state"])


if __name__ == "__main__":
    unittest.main()
