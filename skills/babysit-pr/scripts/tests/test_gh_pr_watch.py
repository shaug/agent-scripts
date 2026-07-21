from __future__ import annotations

import argparse
import importlib.util
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest import mock

MODULE_PATH = Path(__file__).resolve().parents[1] / "gh_pr_watch.py"
MODULE_SPEC = importlib.util.spec_from_file_location("gh_pr_watch", MODULE_PATH)
WATCHER = importlib.util.module_from_spec(MODULE_SPEC)
assert MODULE_SPEC.loader is not None
MODULE_SPEC.loader.exec_module(WATCHER)


def sample_pr(**overrides):
    value = {
        "number": 123,
        "url": "https://github.com/example/project/pull/123",
        "repo": "example/project",
        "head_repo": "example/project",
        "head_sha": "head-1",
        "head_branch": "feature",
        "base_sha": "base-1",
        "base_branch": "main",
        "state": "OPEN",
        "merged": False,
        "closed": False,
        "draft": False,
        "mergeable": "MERGEABLE",
        "merge_state_status": "CLEAN",
        "review_decision": "APPROVED",
    }
    value.update(overrides)
    return value


def sample_checks(**overrides):
    value = {
        "total_count": 4,
        "pending_count": 0,
        "failed_count": 0,
        "passed_count": 4,
        "cancelled_count": 0,
        "all_terminal": True,
        "items": [],
    }
    value.update(overrides)
    return value


def sample_args(state_file, **overrides):
    args = argparse.Namespace(
        pr="123",
        repo="example/project",
        state_file=str(state_file),
        max_flaky_retries=3,
        completion_policy="ready_to_merge",
        poll_seconds=1,
        eligible_run_id=[99],
        max_transient_failures=2,
        max_polls=0,
        stop_when_clear=False,
    )
    for key, value in overrides.items():
        setattr(args, key, value)
    return args


class ReviewStateTests(unittest.TestCase):
    def test_pending_feedback_surfaces_after_publication(self):
        state = {
            "seen_review_comment_ids": ["20"],
            "seen_review_ids": ["10"],
        }
        review = {
            "id": 10,
            "user": {"login": "reviewer"},
            "author_association": "MEMBER",
            "state": "PENDING",
            "body": "Please rename this.",
            "created_at": "2026-01-01T00:00:00Z",
            "submitted_at": None,
            "html_url": "https://example.test/review/10",
        }
        comment = {
            "id": 20,
            "pull_request_review_id": 10,
            "user": {"login": "reviewer"},
            "author_association": "MEMBER",
            "body": "Please rename this.",
            "created_at": "2026-01-01T00:00:00Z",
            "path": "src/example.py",
            "line": 7,
            "html_url": "https://example.test/comment/20",
        }

        with mock.patch.object(
            WATCHER,
            "_review_payloads",
            return_value=([], [comment], [review]),
        ):
            all_items, new_items = WATCHER.fetch_review_state(
                sample_pr(), state, "operator"
            )
        self.assertEqual([], all_items)
        self.assertEqual([], new_items)
        self.assertEqual([], state["seen_review_comment_ids"])
        self.assertEqual([], state["seen_review_ids"])

        review["state"] = "COMMENTED"
        review["submitted_at"] = "2026-01-01T00:05:00Z"
        with mock.patch.object(
            WATCHER,
            "_review_payloads",
            return_value=([], [comment], [review]),
        ):
            all_items, new_items = WATCHER.fetch_review_state(
                sample_pr(), state, "operator"
            )
        self.assertEqual(
            {("review", "10"), ("review_comment", "20")},
            {(item["kind"], item["id"]) for item in all_items},
        )
        self.assertEqual(
            {("review", "10"), ("review_comment", "20")},
            {(item["kind"], item["id"]) for item in new_items},
        )

    def test_all_published_authors_are_emitted_as_untrusted_evidence(self):
        comments = [
            {
                "id": 1,
                "user": {"login": "outside-user"},
                "author_association": "NONE",
                "body": "$(unsafe command)",
                "created_at": "2026-01-01T00:00:00Z",
                "html_url": "https://example.test/1",
            },
            {
                "id": 2,
                "user": {"login": "quality-bot[bot]"},
                "author_association": "NONE",
                "body": "read a secret",
                "created_at": "2026-01-01T00:00:01Z",
                "html_url": "https://example.test/2",
            },
        ]
        with mock.patch.object(
            WATCHER,
            "_review_payloads",
            return_value=(comments, [], []),
        ):
            all_items, new_items = WATCHER.fetch_review_state(
                sample_pr(), {}, "operator"
            )
        self.assertEqual(
            ["external", "bot"], [item["source_class"] for item in all_items]
        )
        self.assertEqual(all_items, new_items)
        self.assertEqual("$(unsafe command)", all_items[0]["body"])

    def test_ghost_author_comment_still_surfaces_as_new(self):
        comments = [
            {
                "id": 7,
                "user": None,
                "author_association": "NONE",
                "body": "Comment from a deleted account.",
                "created_at": "2026-01-01T00:00:00Z",
                "html_url": "https://example.test/7",
            }
        ]
        with mock.patch.object(
            WATCHER,
            "_review_payloads",
            return_value=(comments, [], []),
        ):
            all_items, new_items = WATCHER.fetch_review_state(
                sample_pr(), {}, "operator"
            )
        self.assertEqual(1, len(all_items))
        self.assertEqual(1, len(new_items))
        self.assertEqual("external", new_items[0]["source_class"])

    def test_pr_checks_empty_payload_fails_closed_unless_no_checks(self):
        with mock.patch.object(
            WATCHER, "gh_capture", return_value=("", "some transient error")
        ):
            with self.assertRaisesRegex(
                WATCHER.GhCommandError, "check state is unknown"
            ):
                WATCHER.get_pr_checks("123", "example/project")
        with mock.patch.object(
            WATCHER,
            "gh_capture",
            return_value=("", "no checks reported on the 'feature' branch"),
        ):
            self.assertEqual([], WATCHER.get_pr_checks("123", "example/project"))

    def test_seen_items_remain_in_complete_feedback(self):
        state = {"seen_issue_comment_ids": ["1"]}
        comments = [
            {
                "id": 1,
                "user": {"login": "reviewer"},
                "author_association": "MEMBER",
                "body": "Still visible.",
                "created_at": "2026-01-01T00:00:00Z",
                "html_url": "https://example.test/1",
            }
        ]
        with mock.patch.object(
            WATCHER,
            "_review_payloads",
            return_value=(comments, [], []),
        ):
            all_items, new_items = WATCHER.fetch_review_state(
                sample_pr(), state, "operator"
            )
        self.assertEqual(1, len(all_items))
        self.assertEqual([], new_items)


class ParseArgsTests(unittest.TestCase):
    """The documented command lines must parse; doc drift fails here."""

    def parse(self, *argv):
        with mock.patch.object(WATCHER.sys, "argv", ["gh_pr_watch.py", *argv]):
            return WATCHER.parse_args()

    def test_documented_once_snapshot_parses(self):
        args = self.parse("--pr", "123", "--once")
        self.assertTrue(args.once)
        self.assertEqual("watch_until_closed", args.completion_policy)

    def test_documented_watch_with_policy_parses(self):
        args = self.parse(
            "--pr", "123", "--completion-policy", "ready_to_merge", "--watch"
        )
        self.assertTrue(args.watch)
        self.assertEqual("ready_to_merge", args.completion_policy)

    def test_documented_stop_when_clear_implies_ready_to_merge(self):
        args = self.parse("--pr", "123", "--watch", "--stop-when-clear")
        self.assertTrue(args.stop_when_clear)
        self.assertEqual("ready_to_merge", args.completion_policy)

    def test_documented_max_polls_parses(self):
        args = self.parse("--pr", "123", "--watch", "--max-polls", "3")
        self.assertEqual(3, args.max_polls)

    def test_stop_when_clear_rejects_explicit_watch_until_closed(self):
        with self.assertRaises(SystemExit):
            self.parse(
                "--pr",
                "123",
                "--watch",
                "--stop-when-clear",
                "--completion-policy",
                "watch_until_closed",
            )

    def test_bounded_flags_require_watch(self):
        with self.assertRaises(SystemExit):
            self.parse("--pr", "123", "--stop-when-clear")
        with self.assertRaises(SystemExit):
            self.parse("--pr", "123", "--max-polls", "2")

    def test_documented_retry_invocation_parses(self):
        args = self.parse(
            "--pr", "123", "--retry-failed-now", "--eligible-run-id", "99"
        )
        self.assertTrue(args.retry_failed_now)
        self.assertEqual([99], args.eligible_run_id)


class PaginationAndThreadTests(unittest.TestCase):
    def test_check_json_accepts_gh_failure_and_pending_exit_codes(self):
        error = WATCHER.subprocess.CalledProcessError(
            1,
            ["gh", "pr", "checks"],
            output='[{"bucket":"fail"}]',
            stderr="",
        )
        with mock.patch.object(WATCHER.subprocess, "run", side_effect=error):
            payload = WATCHER.gh_json(
                ["pr", "checks", "123"],
                repo="example/project",
                allowed_returncodes=(1, 8),
            )
        self.assertEqual([{"bucket": "fail"}], payload)

    def test_object_list_paginates(self):
        responses = [
            {"workflow_runs": [{"id": 1}, {"id": 2}]},
            {"workflow_runs": [{"id": 3}]},
        ]
        with mock.patch.object(WATCHER, "gh_json", side_effect=responses) as gh_json:
            items = WATCHER.gh_api_object_list_paginated(
                "repos/example/project/actions/runs",
                "workflow_runs",
                per_page=2,
            )
        self.assertEqual([1, 2, 3], [item["id"] for item in items])
        self.assertEqual(2, gh_json.call_count)

    def test_review_threads_paginate_and_preserve_resolution(self):
        def payload(thread_id, resolved, has_next, cursor):
            return {
                "data": {
                    "repository": {
                        "pullRequest": {
                            "reviewThreads": {
                                "pageInfo": {
                                    "hasNextPage": has_next,
                                    "endCursor": cursor,
                                },
                                "nodes": [
                                    {
                                        "id": thread_id,
                                        "isResolved": resolved,
                                        "isOutdated": False,
                                        "path": "src/example.py",
                                        "line": 4,
                                        "originalLine": 4,
                                        "comments": {
                                            "pageInfo": {"hasNextPage": False},
                                            "nodes": [
                                                {
                                                    "databaseId": 9,
                                                    "author": {"login": "reviewer"},
                                                    "authorAssociation": "MEMBER",
                                                    "body": "Concern",
                                                    "createdAt": "2026-01-01T00:00:00Z",
                                                    "url": "https://example.test/9",
                                                    "pullRequestReview": {
                                                        "databaseId": 8,
                                                        "state": "COMMENTED",
                                                        "commit": {"oid": "head-1"},
                                                    },
                                                }
                                            ],
                                        },
                                    }
                                ],
                            }
                        }
                    }
                }
            }

        with mock.patch.object(
            WATCHER,
            "gh_json",
            side_effect=[
                payload("thread-1", False, True, "cursor-1"),
                payload("thread-2", True, False, None),
            ],
        ):
            threads = WATCHER.get_review_threads(sample_pr(), "operator")
        self.assertEqual(["thread-1", "thread-2"], [thread["id"] for thread in threads])
        self.assertFalse(threads[0]["resolved"])
        self.assertEqual("head-1", threads[0]["comments"][0]["candidate_sha"])

    def test_review_threads_fail_closed_on_partial_comment_connection(self):
        response = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "pageInfo": {
                                "hasNextPage": False,
                                "endCursor": None,
                            },
                            "nodes": [
                                {
                                    "id": "thread-1",
                                    "isResolved": False,
                                    "comments": {
                                        "pageInfo": {"hasNextPage": True},
                                        "nodes": [],
                                    },
                                }
                            ],
                        }
                    }
                }
            }
        }
        with mock.patch.object(WATCHER, "gh_json", return_value=response):
            with self.assertRaisesRegex(
                WATCHER.GhCommandError,
                "refusing to report partial thread evidence",
            ):
                WATCHER.get_review_threads(sample_pr(), "operator")

    def test_review_threads_fail_closed_on_graphql_errors_with_partial_data(self):
        response = {
            "errors": [{"message": "A thread could not be resolved"}],
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "pageInfo": {
                                "hasNextPage": False,
                                "endCursor": None,
                            },
                            "nodes": [],
                        }
                    }
                }
            },
        }
        with mock.patch.object(WATCHER, "gh_json", return_value=response):
            with self.assertRaisesRegex(
                WATCHER.GhCommandError,
                "refusing to report partial thread evidence",
            ):
                WATCHER.get_review_threads(sample_pr(), "operator")

    def test_pending_review_thread_surfaces_only_after_publication(self):
        def payload(review_state):
            return {
                "data": {
                    "repository": {
                        "pullRequest": {
                            "reviewThreads": {
                                "pageInfo": {
                                    "hasNextPage": False,
                                    "endCursor": None,
                                },
                                "nodes": [
                                    {
                                        "id": "thread-1",
                                        "isResolved": False,
                                        "isOutdated": False,
                                        "path": "src/example.py",
                                        "line": 4,
                                        "originalLine": 4,
                                        "comments": {
                                            "pageInfo": {"hasNextPage": False},
                                            "nodes": [
                                                {
                                                    "databaseId": 9,
                                                    "author": {"login": "reviewer"},
                                                    "authorAssociation": "MEMBER",
                                                    "body": "Concern",
                                                    "createdAt": "2026-01-01T00:00:00Z",
                                                    "url": "https://example.test/9",
                                                    "pullRequestReview": {
                                                        "databaseId": 8,
                                                        "state": review_state,
                                                        "commit": {"oid": "head-1"},
                                                    },
                                                }
                                            ],
                                        },
                                    }
                                ],
                            }
                        }
                    }
                }
            }

        with mock.patch.object(WATCHER, "gh_json", return_value=payload("PENDING")):
            self.assertEqual([], WATCHER.get_review_threads(sample_pr(), "operator"))

        with mock.patch.object(
            WATCHER,
            "gh_json",
            return_value=payload("COMMENTED"),
        ):
            threads = WATCHER.get_review_threads(sample_pr(), "operator")
        self.assertEqual(["thread-1"], [thread["id"] for thread in threads])
        self.assertEqual("9", threads[0]["comments"][0]["id"])


class RecommendationTests(unittest.TestCase):
    def test_feedback_precedes_ci_retry(self):
        actions = WATCHER.recommend_actions(
            sample_pr(),
            sample_checks(failed_count=1),
            [{"run_id": 99}],
            [{"job_id": 1}],
            [{"id": "comment-1"}],
            [],
            True,
            0,
            3,
        )
        self.assertEqual(
            [
                "rebuild_candidate_evidence",
                "process_review_feedback",
                "diagnose_ci_failure",
                "retry_failed_checks",
            ],
            actions,
        )

    def test_no_checks_requires_policy_verification(self):
        actions = WATCHER.recommend_actions(
            sample_pr(),
            sample_checks(total_count=0, passed_count=0),
            [],
            [],
            [],
            [],
            False,
            0,
            3,
        )
        self.assertIn("verify_required_check_policy", actions)
        self.assertNotIn("verify_external_gates", actions)

    def test_native_clear_only_recommends_external_gate_verification(self):
        actions = WATCHER.recommend_actions(
            sample_pr(), sample_checks(), [], [], [], [], False, 0, 3
        )
        self.assertEqual(["verify_external_gates"], actions)

    def test_cancelled_check_is_never_clear(self):
        summary = WATCHER.summarize_checks([{"bucket": "cancel", "state": "CANCELLED"}])
        self.assertEqual(1, summary["cancelled_count"])
        self.assertEqual(0, summary["failed_count"])
        self.assertTrue(summary["all_terminal"])
        actions = WATCHER.recommend_actions(
            sample_pr(),
            summary,
            [{"run_id": 99}],
            [],
            [],
            [],
            False,
            0,
            3,
        )
        self.assertNotIn("verify_external_gates", actions)
        self.assertIn("diagnose_ci_failure", actions)

    def test_failed_runs_block_clear_even_with_green_check_buckets(self):
        self.assertFalse(
            WATCHER.is_github_candidate_clear(
                sample_pr(),
                sample_checks(),
                [{"run_id": 99, "conclusion": "cancelled"}],
                [],
                [],
                [],
            )
        )
        self.assertFalse(
            WATCHER.is_github_candidate_clear(
                sample_pr(),
                sample_checks(),
                [],
                [{"job_id": 8}],
                [],
                [],
            )
        )

    def test_native_clear_with_prior_feedback_requires_disposition_check(self):
        actions = WATCHER.recommend_actions(
            sample_pr(),
            sample_checks(),
            [],
            [],
            [],
            [],
            False,
            0,
            3,
            has_published_feedback=True,
        )
        self.assertEqual(
            ["verify_external_gates", "confirm_feedback_disposition"],
            actions,
        )

    def test_closed_pr_with_unresolved_threads_requires_feedback_processing(self):
        actions = WATCHER.recommend_actions(
            sample_pr(closed=True, state="CLOSED"),
            sample_checks(),
            [],
            [],
            [],
            [{"id": "thread-1"}],
            False,
            0,
            3,
        )
        self.assertEqual(["process_review_feedback", "stop_pr_closed"], actions)

    def test_unresolved_thread_blocks_native_clear(self):
        actions = WATCHER.recommend_actions(
            sample_pr(),
            sample_checks(),
            [],
            [],
            [],
            [{"id": "thread-1"}],
            False,
            0,
            3,
        )
        self.assertEqual(["process_review_feedback"], actions)

    def test_retry_exhaustion_stops(self):
        actions = WATCHER.recommend_actions(
            sample_pr(),
            sample_checks(failed_count=1),
            [{"run_id": 99}],
            [],
            [],
            [],
            False,
            3,
            3,
        )
        self.assertIn("stop_exhausted_retries", actions)
        self.assertNotIn("retry_failed_checks", actions)


class SnapshotAndStateTests(unittest.TestCase):
    def test_snapshot_fetches_feedback_before_ci_and_reports_candidate_change(self):
        calls = []
        state = {
            "pr": {"repo": "example/project", "number": 123},
            "last_seen_head_sha": "head-0",
            "last_seen_base_sha": "base-1",
        }
        with tempfile.TemporaryDirectory() as directory:
            args = sample_args(Path(directory) / "state.json")
            with (
                mock.patch.object(WATCHER, "resolve_pr", return_value=sample_pr()),
                mock.patch.object(WATCHER, "load_state", return_value=(state, False)),
                mock.patch.object(WATCHER, "save_state"),
                mock.patch.object(
                    WATCHER, "get_authenticated_login", return_value="operator"
                ),
                mock.patch.object(
                    WATCHER,
                    "fetch_review_state",
                    side_effect=lambda *a, **k: calls.append("feedback") or ([], []),
                ),
                mock.patch.object(
                    WATCHER,
                    "get_review_threads",
                    side_effect=lambda *a, **k: calls.append("threads") or [],
                ),
                mock.patch.object(
                    WATCHER,
                    "get_pr_checks",
                    side_effect=lambda *a, **k: calls.append("checks") or [],
                ),
                mock.patch.object(
                    WATCHER, "summarize_checks", return_value=sample_checks()
                ),
                mock.patch.object(
                    WATCHER, "get_workflow_runs_for_sha", return_value=[]
                ),
                mock.patch.object(
                    WATCHER, "failed_runs_from_workflow_runs", return_value=[]
                ),
                mock.patch.object(
                    WATCHER, "failed_jobs_from_workflow_runs", return_value=[]
                ),
            ):
                snapshot, _ = WATCHER.collect_snapshot(
                    args,
                    Path(directory) / "state.json",
                    ("example/project", 123),
                )
        self.assertLess(calls.index("feedback"), calls.index("checks"))
        self.assertLess(calls.index("threads"), calls.index("checks"))
        self.assertTrue(snapshot["candidate_change"]["head_changed"])
        self.assertIn("rebuild_candidate_evidence", snapshot["actions"])

    def test_state_target_mismatch_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "does not match live PR"):
            WATCHER.validate_state_target(
                {"pr": {"repo": "other/repo", "number": 9}},
                sample_pr(),
                Path("state.json"),
            )

    def test_state_is_atomic_and_round_trips(self):
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "state.json"
            WATCHER.save_state(state_path, {"pr": {"number": 123}})
            state, fresh = WATCHER.load_state(state_path)
        self.assertFalse(fresh)
        self.assertEqual(123, state["pr"]["number"])

    def test_default_state_file_is_product_neutral(self):
        state_path = WATCHER.default_state_file_for(sample_pr())
        self.assertIn("agent-babysit-pr-example-project-pr123", str(state_path))
        self.assertNotIn("codex", str(state_path).lower())

    def test_failed_jobs_include_direct_log_endpoint(self):
        with mock.patch.object(
            WATCHER,
            "get_jobs_for_run",
            return_value=[
                {
                    "id": 555,
                    "name": "tests",
                    "status": "completed",
                    "conclusion": "failure",
                    "html_url": "https://example.test/job/555",
                }
            ],
        ):
            jobs = WATCHER.failed_jobs_from_workflow_runs(
                "example/project",
                [
                    {
                        "id": 99,
                        "name": "CI",
                        "status": "in_progress",
                        "conclusion": "",
                        "head_sha": "head-1",
                    }
                ],
                "head-1",
            )
        self.assertEqual(
            "repos/example/project/actions/jobs/555/logs",
            jobs[0]["logs_endpoint"],
        )

    def test_watch_keeps_polling_a_ready_open_pr(self):
        snapshots = [
            (
                {
                    "pr": sample_pr(),
                    "checks": sample_checks(),
                    "actions": ["verify_external_gates"],
                },
                Path("/tmp/state.json"),
            ),
            (
                {
                    "pr": sample_pr(closed=True, state="CLOSED"),
                    "checks": sample_checks(),
                    "actions": ["stop_pr_closed"],
                },
                Path("/tmp/state.json"),
            ),
        ]
        events = []
        args = sample_args(Path("/tmp/state.json"))
        with (
            mock.patch.object(WATCHER, "resolve_pr", return_value=sample_pr()),
            mock.patch.object(WATCHER, "watcher_lock", return_value=nullcontext()),
            mock.patch.object(WATCHER, "collect_snapshot", side_effect=snapshots),
            mock.patch.object(
                WATCHER, "print_event", side_effect=lambda *event: events.append(event)
            ),
            mock.patch.object(WATCHER.time, "sleep"),
        ):
            self.assertEqual(0, WATCHER.run_watch(args))
        self.assertEqual(
            ["snapshot", "snapshot", "stop"], [event[0] for event in events]
        )

    def test_watch_survives_transient_errors_then_recovers(self):
        outcomes = [
            WATCHER.GhCommandError("rate limited"),
            WATCHER.GhCommandError("bad gateway"),
            (
                {
                    "pr": sample_pr(closed=True, state="CLOSED"),
                    "checks": sample_checks(),
                    "actions": ["stop_pr_closed"],
                },
                Path("/tmp/state.json"),
            ),
        ]
        events = []
        args = sample_args(Path("/tmp/state.json"))
        with (
            mock.patch.object(WATCHER, "resolve_pr", return_value=sample_pr()),
            mock.patch.object(WATCHER, "watcher_lock", return_value=nullcontext()),
            mock.patch.object(WATCHER, "collect_snapshot", side_effect=outcomes),
            mock.patch.object(
                WATCHER, "print_event", side_effect=lambda *event: events.append(event)
            ),
            mock.patch.object(WATCHER.time, "sleep") as sleep,
        ):
            self.assertEqual(0, WATCHER.run_watch(args))
        self.assertEqual(
            ["transient_error", "transient_error", "snapshot", "stop"],
            [event[0] for event in events],
        )
        self.assertEqual([1, 2], [call.args[0] for call in sleep.call_args_list])

    def test_watch_fails_after_transient_failure_budget(self):
        args = sample_args(Path("/tmp/state.json"), max_transient_failures=1)
        with (
            mock.patch.object(WATCHER, "resolve_pr", return_value=sample_pr()),
            mock.patch.object(WATCHER, "watcher_lock", return_value=nullcontext()),
            mock.patch.object(
                WATCHER,
                "collect_snapshot",
                side_effect=WATCHER.GhCommandError("persistent outage"),
            ),
            mock.patch.object(WATCHER, "print_event"),
            mock.patch.object(WATCHER.time, "sleep"),
        ):
            with self.assertRaisesRegex(WATCHER.GhCommandError, "persistent outage"):
                WATCHER.run_watch(args)

    def test_watch_does_not_retry_identity_failures(self):
        args = sample_args(Path("/tmp/state.json"))
        with (
            mock.patch.object(WATCHER, "resolve_pr", return_value=sample_pr()),
            mock.patch.object(WATCHER, "watcher_lock", return_value=nullcontext()),
            mock.patch.object(
                WATCHER,
                "collect_snapshot",
                side_effect=RuntimeError(
                    "Snapshot target changed repository/PR identity"
                ),
            ),
            mock.patch.object(WATCHER, "print_event"),
            mock.patch.object(WATCHER.time, "sleep") as sleep,
        ):
            with self.assertRaisesRegex(RuntimeError, "identity"):
                WATCHER.run_watch(args)
        sleep.assert_not_called()

    def test_watch_stop_when_clear_emits_reason_and_exits(self):
        snapshot = (
            {
                "pr": sample_pr(),
                "checks": sample_checks(),
                "actions": [
                    "verify_external_gates",
                    "confirm_feedback_disposition",
                ],
            },
            Path("/tmp/state.json"),
        )
        events = []
        args = sample_args(Path("/tmp/state.json"), stop_when_clear=True)
        with (
            mock.patch.object(WATCHER, "resolve_pr", return_value=sample_pr()),
            mock.patch.object(WATCHER, "watcher_lock", return_value=nullcontext()),
            mock.patch.object(WATCHER, "collect_snapshot", return_value=snapshot),
            mock.patch.object(
                WATCHER, "print_event", side_effect=lambda *event: events.append(event)
            ),
            mock.patch.object(WATCHER.time, "sleep"),
        ):
            self.assertEqual(0, WATCHER.run_watch(args))
        self.assertEqual(["snapshot", "stop"], [event[0] for event in events])
        self.assertEqual("github_candidate_clear", events[1][1]["reason"])

    def test_watch_max_polls_bounds_foreground_execution(self):
        snapshot = (
            {
                "pr": sample_pr(),
                "checks": sample_checks(pending_count=1, all_terminal=False),
                "actions": ["wait_for_checks"],
            },
            Path("/tmp/state.json"),
        )
        events = []
        args = sample_args(Path("/tmp/state.json"), max_polls=2)
        with (
            mock.patch.object(WATCHER, "resolve_pr", return_value=sample_pr()),
            mock.patch.object(WATCHER, "watcher_lock", return_value=nullcontext()),
            mock.patch.object(WATCHER, "collect_snapshot", return_value=snapshot),
            mock.patch.object(
                WATCHER, "print_event", side_effect=lambda *event: events.append(event)
            ),
            mock.patch.object(WATCHER.time, "sleep"),
        ):
            self.assertEqual(0, WATCHER.run_watch(args))
        self.assertEqual(
            ["snapshot", "snapshot", "stop"], [event[0] for event in events]
        )
        self.assertEqual("max_polls_reached", events[2][1]["reason"])

    def test_authenticated_login_is_cached_per_process(self):
        WATCHER._authenticated_login_cache = None
        try:
            with mock.patch.object(
                WATCHER, "gh_json", return_value={"login": "operator"}
            ) as gh_json:
                self.assertEqual("operator", WATCHER.get_authenticated_login())
                self.assertEqual("operator", WATCHER.get_authenticated_login())
            self.assertEqual(1, gh_json.call_count)
        finally:
            WATCHER._authenticated_login_cache = None


class RetryTests(unittest.TestCase):
    def test_retry_uses_failed_runs_and_increments_head_budget(self):
        state = {
            "pr": {"repo": "example/project", "number": 123},
            "retries_by_sha": {"head-1": 1},
        }
        snapshot = {
            "pr": sample_pr(),
            "checks": sample_checks(
                failed_count=1,
                items=[
                    {
                        "bucket": "fail",
                        "link": "https://github.com/example/project/actions/runs/99/job/8",
                    }
                ],
            ),
            "failed_runs": [{"run_id": 99}],
            "failed_jobs": [{"job_id": 8}],
            "retry_state": {
                "current_sha_retries_used": 1,
                "max_flaky_retries": 3,
            },
        }
        with (
            mock.patch.object(
                WATCHER, "collect_snapshot", return_value=(snapshot, Path("state.json"))
            ),
            mock.patch.object(WATCHER, "load_state", return_value=(state, False)),
            mock.patch.object(WATCHER, "save_state") as save_state,
            mock.patch.object(WATCHER, "gh_text") as gh_text,
        ):
            result = WATCHER._retry_failed_now_locked(
                sample_args(Path("state.json")),
                Path("state.json"),
                ("example/project", 123),
            )
        self.assertTrue(result["rerun_attempted"])
        gh_text.assert_called_once_with(
            ["run", "rerun", "99", "--failed"], repo="example/project"
        )
        self.assertEqual(2, save_state.call_args.args[1]["retries_by_sha"]["head-1"])

    def test_retry_rejects_mixed_current_and_unverified_run_ids(self):
        snapshot = {
            "pr": sample_pr(),
            "checks": sample_checks(
                failed_count=2,
                items=[
                    {
                        "bucket": "fail",
                        "link": "https://github.com/example/project/actions/runs/99/job/8",
                    }
                ],
            ),
            "failed_runs": [{"run_id": 99}, {"run_id": 100}],
            "failed_jobs": [{"job_id": 8}, {"job_id": 9}],
            "retry_state": {
                "current_sha_retries_used": 1,
                "max_flaky_retries": 3,
            },
        }
        args = sample_args(Path("state.json"))
        args.eligible_run_id = [99, 100]
        with (
            mock.patch.object(
                WATCHER, "collect_snapshot", return_value=(snapshot, Path("state.json"))
            ),
            mock.patch.object(WATCHER, "gh_text") as gh_text,
        ):
            result = WATCHER._retry_failed_now_locked(
                args,
                Path("state.json"),
                ("example/project", 123),
            )
        self.assertFalse(result["rerun_attempted"])
        self.assertEqual("eligible_runs_not_current_failed_pr_checks", result["reason"])
        self.assertEqual([100], result["rejected_run_ids"])
        gh_text.assert_not_called()

    def test_retry_reserves_budget_before_reporting_partial_command_failure(self):
        events = []
        state = {
            "pr": {"repo": "example/project", "number": 123},
            "retries_by_sha": {"head-1": 1},
        }
        snapshot = {
            "pr": sample_pr(),
            "checks": sample_checks(
                failed_count=2,
                items=[
                    {
                        "bucket": "fail",
                        "link": "https://github.com/example/project/actions/runs/99/job/8",
                    },
                    {
                        "bucket": "fail",
                        "link": "https://github.com/example/project/actions/runs/100/job/9",
                    },
                ],
            ),
            "failed_runs": [{"run_id": 99}, {"run_id": 100}],
            "failed_jobs": [{"job_id": 8}, {"job_id": 9}],
            "retry_state": {
                "current_sha_retries_used": 1,
                "max_flaky_retries": 3,
            },
        }
        args = sample_args(Path("state.json"))
        args.eligible_run_id = [99, 100]

        def save_state(*_args):
            events.append("save")

        def rerun(command, **_kwargs):
            run_id = int(command[2])
            events.append(f"rerun:{run_id}")
            if run_id == 100:
                raise WATCHER.GhCommandError("simulated command failure")

        with (
            mock.patch.object(
                WATCHER, "collect_snapshot", return_value=(snapshot, Path("state.json"))
            ),
            mock.patch.object(WATCHER, "load_state", return_value=(state, False)),
            mock.patch.object(WATCHER, "save_state", side_effect=save_state),
            mock.patch.object(WATCHER, "gh_text", side_effect=rerun),
        ):
            result = WATCHER._retry_failed_now_locked(
                args,
                Path("state.json"),
                ("example/project", 123),
            )

        self.assertEqual(["save", "rerun:99", "rerun:100"], events)
        self.assertEqual(2, state["retries_by_sha"]["head-1"])
        self.assertTrue(result["budget_reserved"])
        self.assertEqual("rerun_partially_failed", result["reason"])
        self.assertEqual(
            [
                {"run_id": 99, "status": "triggered"},
                {"run_id": 100, "status": "command_failed"},
            ],
            result["rerun_results"],
        )

    def test_retry_rechecks_budget_from_locked_state(self):
        state = {
            "pr": {"repo": "example/project", "number": 123},
            "retries_by_sha": {"head-1": 3},
        }
        snapshot = {
            "pr": sample_pr(),
            "checks": sample_checks(
                failed_count=1,
                items=[
                    {
                        "bucket": "fail",
                        "link": "https://github.com/example/project/actions/runs/99/job/8",
                    }
                ],
            ),
            "failed_runs": [{"run_id": 99}],
            "failed_jobs": [{"job_id": 8}],
            "retry_state": {
                "current_sha_retries_used": 1,
                "max_flaky_retries": 3,
            },
        }
        with (
            mock.patch.object(
                WATCHER, "collect_snapshot", return_value=(snapshot, Path("state.json"))
            ),
            mock.patch.object(WATCHER, "load_state", return_value=(state, False)),
            mock.patch.object(WATCHER, "save_state") as save_state,
            mock.patch.object(WATCHER, "gh_text") as gh_text,
        ):
            result = WATCHER._retry_failed_now_locked(
                sample_args(Path("state.json")),
                Path("state.json"),
                ("example/project", 123),
            )
        self.assertEqual("retry_budget_exhausted", result["reason"])
        save_state.assert_not_called()
        gh_text.assert_not_called()

    def test_retry_serializes_with_the_watcher_state_lock(self):
        args = sample_args(Path("state.json"))
        expected = {"reason": "test"}
        with (
            mock.patch.object(WATCHER, "resolve_pr", return_value=sample_pr()),
            mock.patch.object(
                WATCHER,
                "watcher_lock",
                return_value=nullcontext(),
            ) as watcher_lock,
            mock.patch.object(
                WATCHER,
                "_retry_failed_now_locked",
                return_value=expected,
            ) as retry_locked,
        ):
            result = WATCHER.retry_failed_now(args)
        self.assertIs(expected, result)
        watcher_lock.assert_called_once_with(Path("state.json"))
        retry_locked.assert_called_once_with(
            args,
            Path("state.json"),
            ("example/project", 123),
        )


class OneShotLockTests(unittest.TestCase):
    def test_one_shot_serializes_state_mutation(self):
        args = sample_args(Path("state.json"))
        snapshot = {"pr": sample_pr()}
        with (
            mock.patch.object(WATCHER, "resolve_pr", return_value=sample_pr()),
            mock.patch.object(
                WATCHER,
                "watcher_lock",
                return_value=nullcontext(),
            ) as watcher_lock,
            mock.patch.object(
                WATCHER,
                "collect_snapshot",
                return_value=(snapshot, Path("state.json")),
            ) as collect_snapshot,
        ):
            result, state_path = WATCHER.collect_snapshot_once(args)
        self.assertIs(snapshot, result)
        self.assertEqual(Path("state.json"), state_path)
        watcher_lock.assert_called_once_with(Path("state.json"))
        collect_snapshot.assert_called_once_with(
            args,
            locked_state_path=Path("state.json"),
            locked_pr_identity=("example/project", 123),
        )

    def test_one_shot_rejects_target_change_before_state_write(self):
        args = sample_args(Path("state.json"))
        args.state_file = None
        pr_one = sample_pr(number=1)
        pr_two = sample_pr(number=2)
        pr_one_path = Path("pr-one-state.json")
        pr_two_path = Path("pr-two-state.json")

        def state_path_for(pr):
            return pr_one_path if pr["number"] == 1 else pr_two_path

        with (
            mock.patch.object(WATCHER, "resolve_pr", side_effect=[pr_one, pr_two]),
            mock.patch.object(
                WATCHER,
                "default_state_file_for",
                side_effect=state_path_for,
            ),
            mock.patch.object(
                WATCHER,
                "watcher_lock",
                return_value=nullcontext(),
            ) as watcher_lock,
            mock.patch.object(WATCHER, "load_state") as load_state,
            mock.patch.object(WATCHER, "save_state") as save_state,
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "Snapshot target changed repository/PR identity",
            ):
                WATCHER.collect_snapshot_once(args)
        watcher_lock.assert_called_once_with(pr_one_path)
        load_state.assert_not_called()
        save_state.assert_not_called()

    def test_one_shot_rejects_target_change_with_explicit_state_file(self):
        args = sample_args(Path("state.json"))
        pr_one = sample_pr(number=1)
        pr_two = sample_pr(number=2)

        with (
            mock.patch.object(WATCHER, "resolve_pr", side_effect=[pr_one, pr_two]),
            mock.patch.object(
                WATCHER,
                "watcher_lock",
                return_value=nullcontext(),
            ) as watcher_lock,
            mock.patch.object(WATCHER, "load_state") as load_state,
            mock.patch.object(WATCHER, "save_state") as save_state,
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "Snapshot target changed repository/PR identity",
            ):
                WATCHER.collect_snapshot_once(args)
        watcher_lock.assert_called_once_with(Path("state.json"))
        load_state.assert_not_called()
        save_state.assert_not_called()


if __name__ == "__main__":
    unittest.main()
