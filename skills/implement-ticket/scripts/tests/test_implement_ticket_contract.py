"""Load-bearing contract invariants for the implement-ticket skill.

These tests intentionally check only stable identifiers — skill names,
terminal states, policy tokens, routing markers, dependency names, file
layout, and neutrality — not prose phrasing. Behavior is covered by the
forward evaluations under scripts/evals/.
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


class ImplementTicketContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = read(SKILL_ROOT / "SKILL.md")
        cls.github = read(SKILL_ROOT / "references" / "github.md")
        cls.linear = read(SKILL_ROOT / "references" / "linear.md")
        cls.gates = read(SKILL_ROOT / "references" / "review-and-merge-gates.md")
        cls.handoff = read(SKILL_ROOT / "references" / "babysit-pr-handoff.md")
        cls.result = read(SKILL_ROOT / "references" / "cleanup-and-result.md")
        cls.skill_compact = compact(cls.skill)
        cls.handoff_compact = compact(cls.handoff)
        cls.result_compact = compact(cls.result)
        cls.eval_contract = compact(
            read(SKILL_ROOT / "evals" / "cases.json")
            + read(SKILL_ROOT / "evals" / "expectations.json")
        )
        cls.all_contract = compact(
            cls.skill + cls.github + cls.linear + cls.gates + cls.handoff + cls.result
        )
        cls.cases = {
            item["id"]: item
            for item in json.loads(read(SKILL_ROOT / "evals" / "cases.json"))
        }
        cls.expectations = {
            item["case_id"]: item
            for item in json.loads(read(SKILL_ROOT / "evals" / "expectations.json"))
        }

    def test_frontmatter_and_product_neutral_contract(self):
        self.assertTrue(self.skill.startswith("---\nname: implement-ticket\n"))
        self.assertNotIn("Codex", self.all_contract)
        self.assertNotIn("OpenAI", self.all_contract)
        self.assertNotIn("Codex", self.eval_contract)
        self.assertNotIn("OpenAI", self.eval_contract)

    def test_terminal_states_are_stable(self):
        for state in ("ready_pr", "merged", "blocked", "requires_epic"):
            self.assertIn(state, self.skill)
            self.assertIn(state, self.result_compact)

    def test_completion_policies_and_mapping_are_stable(self):
        for policy in (
            "ready PR only",
            "merge after gates",
            "merge plus manual transition",
        ):
            self.assertIn(policy, self.skill_compact)
        for source, target in (
            ("ready_to_merge", "ready_pr"),
            ("merged", "merged"),
            ("closed", "blocked"),
            ("blocked", "blocked"),
        ):
            self.assertIn(f"`{source}` maps to `{target}`", self.handoff_compact)
        self.assertIn("watch_until_closed", self.handoff_compact)

    def test_epic_routing_marker_and_cycle_guard_are_stable(self):
        self.assertIn(
            "implement-ticket:requires-epic:<tracker>:<ticket-id>",
            self.all_contract,
        )
        self.assertIn("routing cycle detected", self.all_contract)
        self.assertIn("implement-epic", self.skill_compact)

    def test_dependency_names_are_repository_owned_and_acyclic(self):
        self.assertIn("review-code-change", self.skill_compact)
        self.assertIn("babysit-pr", self.skill_compact)
        self.assertIn(
            "`babysit-pr` must never invoke `implement-ticket`", self.skill_compact
        )

    def test_instruction_file_naming_is_host_neutral(self):
        self.assertIn("CLAUDE.md", self.skill_compact)
        self.assertIn("AGENTS.md", self.skill_compact)

    def test_eval_cases_and_expectations_stay_paired(self):
        self.assertTrue(self.cases)
        self.assertEqual(set(self.cases), set(self.expectations))

    def test_eval_expectations_enforce_routing_and_authority(self):
        self.assertEqual(
            "ready_pr", self.expectations["standalone-ready-pr"]["terminal_state"]
        )
        self.assertEqual(
            "blocked",
            self.expectations["canonical-pr-owned-elsewhere"]["terminal_state"],
        )
        self.assertEqual(
            "requires_epic",
            self.expectations["missing-implement-epic"]["terminal_state"],
        )
        self.assertEqual(
            "blocked", self.expectations["repeated-epic-handoff"]["terminal_state"]
        )
        for case_id in (
            "missing-review-code-change",
            "missing-isolation-capability",
            "missing-asynchronous-wait",
        ):
            self.assertEqual("blocked", self.expectations[case_id]["terminal_state"])

    def test_runtime_adapters_exist_for_both_products(self):
        metadata = read(SKILL_ROOT / "agents" / "openai.yaml")
        self.assertIn('display_name: "Implement Ticket"', metadata)
        self.assertIn("Claude Code adapter", read(SKILL_ROOT / "agents" / "claude.md"))


if __name__ == "__main__":
    unittest.main()
