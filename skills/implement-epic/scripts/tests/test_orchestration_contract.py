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


if __name__ == "__main__":
    unittest.main()
