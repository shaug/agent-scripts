"""Load-bearing contract invariants for the babysit-pr skill.

These tests intentionally check only stable identifiers — skill names,
terminal states, policy tokens, dependency names, file layout, and
neutrality — not prose phrasing. Behavior is covered by
test_gh_pr_watch.py and the evaluation data under evals/.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = SKILL_ROOT.parents[1]


def read(relative_path):
    return (SKILL_ROOT / relative_path).read_text()


def compact(value):
    return re.sub(r"\s+", " ", value).strip()


class BabysitPrContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = read("SKILL.md")
        cls.github = read("references/github.md")
        cls.decisions = read("references/ci-and-feedback.md")
        cls.upstream = read("references/upstream.md")
        cls.watcher = read("scripts/gh_pr_watch.py")
        cls.contract = compact(cls.skill + cls.github + cls.decisions)
        cls.cases = {item["id"]: item for item in json.loads(read("evals/cases.json"))}
        cls.expectations = {
            item["case_id"]: item
            for item in json.loads(read("evals/expectations.json"))
        }

    def test_frontmatter_and_runtime_neutral_contract(self):
        self.assertTrue(self.skill.startswith("---\nname: babysit-pr\n"))
        self.assertNotIn("Codex", self.contract)
        self.assertNotIn("REVIEW_BOT_LOGIN_KEYWORDS", self.watcher)
        self.assertNotIn("/tmp/codex", self.watcher)

    def test_completion_policies_and_terminal_states_are_stable(self):
        for policy in (
            "ready_to_merge",
            "merge_when_ready",
            "watch_until_closed",
        ):
            self.assertIn(policy, self.contract)
            self.assertIn(policy, self.watcher)
        for state in ("ready_to_merge", "merged", "closed", "blocked"):
            self.assertIn(state, self.skill)

    def test_review_dependency_is_repository_owned(self):
        self.assertIn("review-code-change", self.contract)

    def test_watcher_paths_are_skill_relative(self):
        self.assertNotIn("skills/babysit-pr/scripts", self.skill)
        self.assertNotIn("skills/babysit-pr/scripts", self.github)
        self.assertIn("scripts/gh_pr_watch.py", self.skill)

    def test_upstream_is_pinned_and_licensed(self):
        self.assertIn("a770e5b8470d3320eb53a56a286ea4a0a70a1f59", self.upstream)
        self.assertIn("Apache License 2.0", self.upstream)
        self.assertTrue((SKILL_ROOT / "LICENSE.apache-2.0").is_file())
        self.assertNotIn("raw.githubusercontent.com", self.watcher)

    def test_eval_cases_and_expectations_stay_paired(self):
        self.assertTrue(self.cases)
        self.assertEqual(set(self.cases), set(self.expectations))

    def test_eval_expectations_preserve_authority_boundaries(self):
        self.assertEqual(
            "ready_to_merge",
            self.expectations["ready-without-merge"]["terminal_state"],
        )
        self.assertEqual(
            "merged", self.expectations["authorized-merge"]["terminal_state"]
        )
        self.assertEqual(
            "closed", self.expectations["closed-without-merge"]["terminal_state"]
        )
        self.assertEqual(
            "blocked", self.expectations["missing-capability"]["terminal_state"]
        )

    def test_runtime_adapters_exist_for_both_products(self):
        self.assertIn('display_name: "Babysit PR"', read("agents/openai.yaml"))
        self.assertIn("Claude Code adapter", read("agents/claude.md"))


if __name__ == "__main__":
    unittest.main()
