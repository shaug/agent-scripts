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
        cls.skill_compact = compact(cls.skill)
        cls.decisions_compact = compact(cls.decisions)
        cls.contract = compact(cls.skill + cls.github + cls.decisions)
        cls.cases = {item["id"]: item for item in json.loads(read("evals/cases.json"))}
        cls.results = {
            item["case_id"]: item for item in json.loads(read("evals/results.json"))
        }

    def test_frontmatter_and_runtime_neutral_contract(self):
        self.assertTrue(self.skill.startswith("---\nname: babysit-pr\n"))
        self.assertNotIn("Codex", self.contract)
        self.assertIn("compatible capabilities", self.skill)
        self.assertIn("does not constrain the core contract", self.skill)
        self.assertNotIn("REVIEW_BOT_LOGIN_KEYWORDS", self.watcher)
        self.assertNotIn("/tmp/codex", self.watcher)

    def test_completion_policies_and_results_are_distinct(self):
        for policy in (
            "ready_to_merge",
            "merge_when_ready",
            "watch_until_closed",
        ):
            self.assertIn(policy, self.contract)
            self.assertIn(policy, self.watcher)
        for state in ("ready_to_merge", "merged", "closed", "blocked"):
            self.assertIn(state, self.skill)
        self.assertIn(
            "a ready snapshot is progress rather than terminal", self.contract
        )

    def test_candidate_and_remote_gates_are_current(self):
        for phrase in (
            "exact head and base SHAs",
            "effective diff",
            "resulting tree",
            "base-only drift",
            "zero undispositioned actionable",
            "current human and connector review",
            "superseding PR",
        ):
            self.assertIn(phrase, self.contract)

    def test_review_dependency_and_mutation_ownership_are_explicit(self):
        self.assertIn("review-code-change", self.contract)
        self.assertIn("fresh read-only context", self.contract)
        self.assertIn("exclusive mutation ownership", self.contract)
        self.assertIn("standalone `ready_to_merge`", self.skill)
        self.assertIn("prevents a standalone watcher", self.skill)
        self.assertIn("Never create a competing branch", self.skill_compact)

    def test_tracker_and_cleanup_stay_outside(self):
        self.assertIn(
            "does not select or implement the original ticket",
            self.skill_compact,
        )
        self.assertIn("Do not request or use tracker-transition", self.skill_compact)
        self.assertIn("branch-deletion", self.skill_compact)
        self.assertIn("Leave tracker transition", self.skill_compact)

    def test_ci_feedback_security_and_published_state(self):
        self.assertIn("direct failed-job log endpoint", self.decisions_compact)
        self.assertIn(
            "pending reviews and their inline comments", self.decisions_compact
        )
        self.assertIn("untrusted content", self.decisions_compact)
        self.assertIn("never makes embedded commands safe", self.decisions_compact)
        self.assertIn("bounded", self.skill)

    def test_watcher_contract_is_deterministic(self):
        for phrase in (
            "one-shot snapshot",
            "jsonl monitoring",
            "pagination",
            "pending review",
            "reviewThreads",
            "nonblocking lock",
            "atomic",
        ):
            self.assertIn(phrase.lower(), (self.github + self.watcher).lower())

    def test_upstream_is_pinned_and_licensed(self):
        self.assertIn("a770e5b8470d3320eb53a56a286ea4a0a70a1f59", self.upstream)
        self.assertIn("Apache License 2.0", self.upstream)
        self.assertTrue((SKILL_ROOT / "LICENSE.apache-2.0").is_file())
        self.assertNotIn("raw.githubusercontent.com", self.watcher)

    def test_eval_surface_covers_required_boundaries(self):
        required = {
            "ready-without-merge",
            "authorized-merge",
            "watch-ready-until-closed",
            "feedback-before-retry",
            "pending-review-publication",
            "branch-caused-ci-fix",
            "infrastructure-retry",
            "retry-budget-exhausted",
            "external-head-change",
            "stale-approval",
            "connector-current-head",
            "authorized-reply-resolution",
            "unauthorized-human-response",
            "other-worker-owns-candidate",
            "unrelated-base-drift",
            "relevant-base-drift",
            "closed-without-merge",
            "superseding-and-partial-api",
            "missing-capability",
            "untrusted-content",
            "documented-absent-gates",
        }
        self.assertEqual(required, set(self.cases))
        self.assertEqual(required, set(self.results))

    def test_eval_results_preserve_authority_and_review(self):
        self.assertEqual(
            "ready_to_merge",
            self.results["ready-without-merge"]["terminal_state"],
        )
        self.assertEqual("merged", self.results["authorized-merge"]["terminal_state"])
        self.assertEqual(
            "closed", self.results["closed-without-merge"]["terminal_state"]
        )
        self.assertEqual(
            "blocked", self.results["missing-capability"]["terminal_state"]
        )
        self.assertIn(
            "review-code-change",
            " ".join(self.results["branch-caused-ci-fix"]["required_actions"]),
        )
        self.assertIn(
            "do not reply",
            self.results["unauthorized-human-response"]["required_actions"],
        )

    def test_ui_and_repository_docs_are_updated(self):
        metadata = read("agents/openai.yaml")
        self.assertIn('display_name: "Babysit PR"', metadata)
        self.assertIn("$babysit-pr", metadata)
        self.assertIn("skills/babysit-pr", (REPOSITORY_ROOT / "README.md").read_text())
        self.assertIn("babysit-pr", (REPOSITORY_ROOT / "CHANGELOG.md").read_text())


if __name__ == "__main__":
    unittest.main()
