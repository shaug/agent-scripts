"""Load-bearing contract invariants for the implement-epic skill.

These tests intentionally check only stable identifiers — skill names,
terminal states, dependency names, file layout, and neutrality — not prose
phrasing. Scenario coverage lives in the evaluation data under evals/.
"""

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
            + read(SKILL_ROOT / "evals" / "expectations.json")
        )
        cls.cases = {
            item["id"]: item
            for item in json.loads(read(SKILL_ROOT / "evals" / "cases.json"))
        }
        cls.expectations = {
            item["case_id"]: item
            for item in json.loads(read(SKILL_ROOT / "evals" / "expectations.json"))
        }

    def test_canonical_name_and_metadata(self):
        self.assertTrue(self.skill.startswith("---\nname: implement-epic\n"))
        metadata = read(SKILL_ROOT / "agents" / "openai.yaml")
        self.assertIn('display_name: "Implement Epic"', metadata)
        self.assertIn(
            "Claude Code adapter", read(SKILL_ROOT / "agents" / "claude-code.md")
        )

    def test_product_neutral_runtime_contract(self):
        self.assertNotIn("Codex", self.contract)
        self.assertNotIn("OpenAI", self.contract)
        self.assertNotIn("Codex", self.eval_contract)
        self.assertNotIn("OpenAI", self.eval_contract)

    def test_dependency_chain_is_stable_and_acyclic(self):
        self.assertIn(
            "`implement-epic` → `implement-ticket` → "
            "(`review-code-change`, `babysit-pr`, `carve-changesets`)",
            self.contract,
        )
        self.assertIn(
            "Do not make this skill invoke `review-code-change`, `babysit-pr`, or "
            "`carve-changesets` itself",
            self.contract,
        )
        self.assertIn("never recursively invoke this skill", self.contract)

    def test_child_terminal_states_are_stable(self):
        for state in ("ready_pr", "ready_prs", "merged", "blocked", "requires_epic"):
            self.assertIn(f"`{state}`", self.contract)

    def test_epic_only_passes_authority_and_verifies_stack_results(self):
        self.assertIn("off by default", self.contract)
        self.assertIn("ordered predecessor-base topology", self.contract)
        self.assertIn("full-chain representation on the base", self.contract)
        self.assertIn("gains no decomposition mechanics", self.contract)

    def test_epic_does_not_own_lens_mechanics(self):
        self.assertNotIn("review-solution-simplicity", self.contract)
        self.assertNotIn("review-correctness", self.contract)
        self.assertNotIn("review-code-simplicity", self.contract)
        self.assertNotIn("fix/re-review cycles", self.contract)

    def test_eval_cases_and_expectations_stay_paired(self):
        self.assertTrue(self.cases)
        self.assertEqual(set(self.cases), set(self.expectations))

    def test_eval_expectations_preserve_critical_boundaries(self):
        self.assertEqual(
            "waiting_for_child_merge",
            self.expectations["ready-pr-does-not-unblock"]["workflow_state"],
        )
        self.assertEqual(
            "blocked", self.expectations["missing-implement-ticket"]["workflow_state"]
        )
        self.assertEqual(
            "closeout_blocked",
            self.expectations["late-feedback-blocks-closeout"]["workflow_state"],
        )
        self.assertEqual(
            "serial_execution_required",
            self.expectations["parallel-nonoverlap-required"]["workflow_state"],
        )
        for case_id in (
            "missing-review-dependency-through-ticket",
            "missing-isolation-capability",
            "missing-asynchronous-wait",
        ):
            self.assertEqual("blocked", self.expectations[case_id]["workflow_state"])
        self.assertEqual(
            "stack_child_verified",
            self.expectations["verify-stacked-child-result"]["workflow_state"],
        )
        for case_id in (
            "closed-children-missing-manual-browser",
            "reopened-correction-missing-journey-revalidation",
        ):
            self.assertEqual(
                "closeout_blocked", self.expectations[case_id]["workflow_state"]
            )
        self.assertEqual(
            "epic_closed",
            self.expectations["authorized-full-epic-closeout"]["workflow_state"],
        )

    def test_verified_delivery_refreshes_graph_even_when_acceptance_blocks(self):
        self.assertIn(
            "After every verified merge, delivery, or tracker transition",
            self.skill,
        )
        for adapter in (self.github, self.linear):
            self.assertIn("regardless of the returned terminal state", adapter)
            self.assertIn("complete current acceptance ledger", adapter)
        self.assertIn("merged delivery with acceptance pending", self.github)
        self.assertIn("merged delivery with acceptance pending", self.linear)

    def test_closeout_requires_child_and_parent_acceptance_ledgers(self):
        self.assertIn("complete native child and blocker graph", self.contract)
        self.assertIn("criterion-specific acceptance ledger", self.contract)
        self.assertIn("parent's own ledger", self.contract)
        self.assertIn("current-main representation", self.contract)
        self.assertIn("exact deployed SHA", self.contract)
        self.assertIn("functional browser checks alone are insufficient", self.contract)

    def test_delivery_and_acceptance_are_reported_separately(self):
        self.assertIn(
            '"all native children closed" are delivery and administrative milestones, not epic acceptance',
            self.contract,
        )
        self.assertIn("Keep the parent open", self.contract)
        self.assertIn("Parent-close authority is separate", self.contract)

    def test_auto_closed_incomplete_child_routes_through_ticket_recovery(self):
        self.assertIn(
            "auto-closed while required acceptance remains missing", self.contract
        )
        self.assertIn(
            "Route that auto-closed child through `implement-ticket`", self.contract
        )
        self.assertIn("granted or withheld reopen authority", self.contract)
        self.assertIn(
            "Do not select an accepted, superseded, or otherwise terminal closed child",
            self.contract,
        )

    def test_reopened_epic_requires_affected_journey_revalidation(self):
        self.assertIn("focused corrective child", self.contract)
        self.assertIn("regression test at the escaped boundary", self.contract)
        self.assertIn("full affected customer journey", self.contract)
        self.assertIn("do not impose unrelated full-system testing", self.contract)


if __name__ == "__main__":
    unittest.main()
