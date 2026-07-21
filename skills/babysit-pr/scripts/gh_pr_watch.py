#!/usr/bin/env python3
"""Normalize GitHub pull-request state for repository-owned PR babysitting.

Adapted from OpenAI Codex commit a770e5b8470d3320eb53a56a286ea4a0a70a1f59
under Apache License 2.0. See ../LICENSE.apache-2.0 and
../references/upstream.md.
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse

try:
    import fcntl
except (
    ImportError
):  # pragma: no cover - Windows is not a supported Git worktree host yet.
    fcntl = None

FAILED_RUN_CONCLUSIONS = {
    "failure",
    "timed_out",
    "cancelled",
    "action_required",
    "startup_failure",
    "stale",
}
PENDING_CHECK_STATES = {
    "QUEUED",
    "IN_PROGRESS",
    "PENDING",
    "WAITING",
    "REQUESTED",
}
MERGE_BLOCKING_REVIEW_DECISIONS = {
    "REVIEW_REQUIRED",
    "CHANGES_REQUESTED",
}
COMPLETION_POLICIES = {
    "ready_to_merge",
    "merge_when_ready",
    "watch_until_closed",
}
STATE_VERSION = 1
MERGE_CONFLICT_OR_BLOCKING_STATES = {
    "BLOCKED",
    "DIRTY",
    "DRAFT",
    "UNKNOWN",
}


class GhCommandError(RuntimeError):
    pass


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Normalize PR/CI/review state for PR babysitting and optionally "
            "trigger flaky reruns."
        )
    )
    parser.add_argument(
        "--pr",
        default="auto",
        help=(
            "PR number or PR URL. `auto` resolves from the current branch; "
            "prefer an explicit number or URL in multi-PR repositories."
        ),
    )
    parser.add_argument("--repo", help="Optional OWNER/REPO override")
    parser.add_argument(
        "--poll-seconds", type=int, default=30, help="Watch poll interval"
    )
    parser.add_argument(
        "--max-transient-failures",
        type=int,
        default=5,
        help=(
            "Consecutive transient GitHub CLI failures tolerated in --watch "
            "mode before exiting nonzero"
        ),
    )
    parser.add_argument(
        "--max-polls",
        type=int,
        default=0,
        help=(
            "Exit --watch after this many successful snapshots (0 = unlimited). "
            "Use for bounded foreground execution windows."
        ),
    )
    parser.add_argument(
        "--stop-when-clear",
        action="store_true",
        help=(
            "Exit --watch once GitHub-native gates are clear "
            "(the `verify_external_gates` action). The controller must still "
            "verify repository-specific gates and feedback disposition."
        ),
    )
    parser.add_argument(
        "--max-flaky-retries",
        type=int,
        default=3,
        help="Max rerun cycles per head SHA before stop recommendation",
    )
    parser.add_argument("--state-file", help="Path to state JSON file")
    parser.add_argument(
        "--completion-policy",
        choices=sorted(COMPLETION_POLICIES),
        default=None,
        help=(
            "Controller-selected terminal policy (reported but not enforced "
            "alone). Defaults to watch_until_closed, or ready_to_merge when "
            "--stop-when-clear is given."
        ),
    )
    parser.add_argument(
        "--once", action="store_true", help="Emit one snapshot and exit"
    )
    parser.add_argument(
        "--watch", action="store_true", help="Continuously emit JSONL snapshots"
    )
    parser.add_argument(
        "--retry-failed-now",
        action="store_true",
        help="Rerun failed jobs for current failed workflow runs when policy allows",
    )
    parser.add_argument(
        "--eligible-run-id",
        action="append",
        default=[],
        type=int,
        help="Diagnosed current-PR workflow run eligible for retry (repeatable)",
    )
    args = parser.parse_args()

    if args.poll_seconds <= 0:
        parser.error("--poll-seconds must be > 0")
    if args.max_flaky_retries < 0:
        parser.error("--max-flaky-retries must be >= 0")
    if args.max_transient_failures < 0:
        parser.error("--max-transient-failures must be >= 0")
    if args.max_polls < 0:
        parser.error("--max-polls must be >= 0")
    if (args.max_polls or args.stop_when_clear) and not args.watch:
        parser.error("--max-polls and --stop-when-clear require --watch")
    if args.stop_when_clear and args.completion_policy == "watch_until_closed":
        parser.error(
            "--stop-when-clear conflicts with an explicit watch_until_closed; "
            "a ready snapshot is progress, not terminal, under that policy"
        )
    if args.completion_policy is None:
        args.completion_policy = (
            "ready_to_merge" if args.stop_when_clear else "watch_until_closed"
        )
    if args.watch and args.retry_failed_now:
        parser.error("--watch cannot be combined with --retry-failed-now")
    if args.once and args.watch:
        parser.error("--once cannot be combined with --watch")
    if args.once and args.retry_failed_now:
        parser.error("--once cannot be combined with --retry-failed-now")
    if args.repo and args.pr == "auto":
        parser.error("--repo requires an explicit --pr number or URL")
    if args.eligible_run_id and not args.retry_failed_now:
        parser.error("--eligible-run-id requires --retry-failed-now")
    if args.retry_failed_now and not args.eligible_run_id:
        parser.error("--retry-failed-now requires at least one --eligible-run-id")
    if not args.once and not args.watch and not args.retry_failed_now:
        args.once = True
    return args


def _format_gh_error(cmd, err):
    stdout = (err.stdout or "").strip()
    stderr = (err.stderr or "").strip()
    parts = [f"GitHub CLI command failed: {' '.join(cmd)}"]
    if stdout:
        parts.append(f"stdout: {stdout}")
    if stderr:
        parts.append(f"stderr: {stderr}")
    return "\n".join(parts)


def gh_capture(args, repo=None, allowed_returncodes=()):
    """Run gh and return (stdout, stderr), tolerating allowed exit codes."""
    cmd = ["gh"]
    # `gh api` does not accept `-R/--repo` on all gh versions. The watcher's
    # API calls use explicit endpoints (e.g. repos/{owner}/{repo}/...), so the
    # repo flag is unnecessary there.
    if repo and (not args or args[0] != "api"):
        cmd.extend(["-R", repo])
    cmd.extend(args)
    try:
        proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
    except FileNotFoundError as err:
        raise GhCommandError("`gh` command not found") from err
    except subprocess.CalledProcessError as err:
        if err.returncode in allowed_returncodes:
            return err.stdout or "", err.stderr or ""
        raise GhCommandError(_format_gh_error(cmd, err)) from err
    return proc.stdout, proc.stderr or ""


def gh_text(args, repo=None, allowed_returncodes=()):
    stdout, _ = gh_capture(args, repo=repo, allowed_returncodes=allowed_returncodes)
    return stdout


def gh_json(args, repo=None, allowed_returncodes=()):
    raw = gh_text(
        args,
        repo=repo,
        allowed_returncodes=allowed_returncodes,
    ).strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as err:
        raise GhCommandError(
            f"Failed to parse JSON from gh output for {' '.join(args)}"
        ) from err


def parse_pr_spec(pr_spec):
    if pr_spec == "auto":
        return {"mode": "auto", "value": None}
    if re.fullmatch(r"\d+", pr_spec):
        return {"mode": "number", "value": pr_spec}
    parsed = urlparse(pr_spec)
    if parsed.scheme and parsed.netloc and "/pull/" in parsed.path:
        return {"mode": "url", "value": pr_spec}
    raise ValueError("--pr must be 'auto', a PR number, or a PR URL")


def pr_view_fields():
    return (
        "number,url,state,mergedAt,closedAt,isDraft,headRefName,headRefOid,"
        "baseRefName,baseRefOid,"
        "headRepository,headRepositoryOwner,mergeable,mergeStateStatus,reviewDecision"
    )


def checks_fields():
    return "name,state,bucket,link,workflow,event,startedAt,completedAt"


def resolve_pr(pr_spec, repo_override=None):
    parsed = parse_pr_spec(pr_spec)
    cmd = ["pr", "view"]
    if parsed["value"] is not None:
        cmd.append(parsed["value"])
    cmd.extend(["--json", pr_view_fields()])
    data = gh_json(cmd, repo=repo_override)
    if not isinstance(data, dict):
        raise GhCommandError("Unexpected PR payload from `gh pr view`")

    pr_url = str(data.get("url") or "")
    repo = (
        repo_override
        or extract_repo_from_pr_url(pr_url)
        or extract_repo_from_pr_view(data)
    )
    if not repo:
        raise GhCommandError("Unable to determine OWNER/REPO for the PR")

    state = str(data.get("state") or "")
    merged = bool(data.get("mergedAt"))
    closed = bool(data.get("closedAt")) or state.upper() == "CLOSED"

    return {
        "number": int(data["number"]),
        "url": pr_url,
        "repo": repo,
        "head_repo": extract_repo_from_pr_view(data) or repo,
        "head_sha": str(data.get("headRefOid") or ""),
        "head_branch": str(data.get("headRefName") or ""),
        "base_sha": str(data.get("baseRefOid") or ""),
        "base_branch": str(data.get("baseRefName") or ""),
        "state": state,
        "merged": merged,
        "closed": closed,
        "draft": bool(data.get("isDraft")),
        "mergeable": str(data.get("mergeable") or ""),
        "merge_state_status": str(data.get("mergeStateStatus") or ""),
        "review_decision": str(data.get("reviewDecision") or ""),
    }


def extract_repo_from_pr_view(data):
    head_repo = data.get("headRepository")
    head_owner = data.get("headRepositoryOwner")
    owner = None
    name = None
    if isinstance(head_owner, dict):
        owner = head_owner.get("login") or head_owner.get("name")
    elif isinstance(head_owner, str):
        owner = head_owner
    if isinstance(head_repo, dict):
        name = head_repo.get("name")
        repo_owner = head_repo.get("owner")
        if not owner and isinstance(repo_owner, dict):
            owner = repo_owner.get("login") or repo_owner.get("name")
    elif isinstance(head_repo, str):
        name = head_repo
    if owner and name:
        return f"{owner}/{name}"
    return None


def extract_repo_from_pr_url(pr_url):
    parsed = urlparse(pr_url)
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) >= 4 and parts[2] == "pull":
        return f"{parts[0]}/{parts[1]}"
    return None


def load_state(path):
    if path.exists():
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError as err:
            raise RuntimeError(f"State file is not valid JSON: {path}") from err
        if not isinstance(data, dict):
            raise RuntimeError(f"State file must contain an object: {path}")
        return data, False
    return {
        "version": STATE_VERSION,
        "pr": {},
        "started_at": None,
        "last_seen_head_sha": None,
        "last_seen_base_sha": None,
        "retries_by_sha": {},
        "seen_issue_comment_ids": [],
        "seen_review_comment_ids": [],
        "seen_review_ids": [],
        "last_snapshot_at": None,
    }, True


def save_state(path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(state, indent=2, sort_keys=True) + "\n"
    fd, tmp_name = tempfile.mkstemp(
        prefix=f"{path.name}.", suffix=".tmp", dir=path.parent
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
            tmp_file.write(payload)
        os.replace(tmp_path, path)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def default_state_directory():
    """Per-user, mode-0700 state directory under the system temp directory.

    State content is trusted (seen-feedback IDs, retry budgets), so on shared
    multi-user hosts it must not live at a predictable world-writable path.
    chmod fails closed when another user pre-created the directory.
    """
    getuid = getattr(os, "getuid", None)
    owner = str(getuid()) if getuid else "user"
    directory = Path(tempfile.gettempdir()) / f"agent-babysit-pr-{owner}"
    directory.mkdir(mode=0o700, exist_ok=True)
    os.chmod(directory, 0o700)
    return directory


def default_state_file_for(pr):
    # The slug keeps the filename readable; the digest of the exact
    # repository string guarantees distinct repositories can never collide
    # on one state file (e.g. `a-b/c` vs `a/b-c`). GitHub slugs are
    # case-insensitive, so normalize case first: `--repo Owner/Repo` and a
    # URL-derived `owner/repo` must share one state file and one lock.
    repo = pr["repo"].lower()
    repo_slug = re.sub(r"[^a-z0-9_.-]+", "-", repo).strip("-")
    digest = hashlib.sha256(repo.encode("utf-8")).hexdigest()[:8]
    return default_state_directory() / (
        f"agent-babysit-pr-{repo_slug}-{digest}-pr{pr['number']}.json"
    )


def validate_state_target(state, pr, state_path):
    stored = state.get("pr") or {}
    if not stored:
        return
    stored_repo = str(stored.get("repo") or "")
    stored_number = stored.get("number")
    try:
        number_matches = int(stored_number) == int(pr["number"])
    except (TypeError, ValueError):
        number_matches = False
    # GitHub slugs are case-insensitive; match the normalization used by
    # default_state_file_for so mixed-case invocations share one state file.
    if stored_repo.lower() != pr["repo"].lower() or not number_matches:
        raise RuntimeError(
            "State file target does not match live PR: "
            f"{state_path} stores {stored_repo}#{stored_number}, "
            f"requested {pr['repo']}#{pr['number']}"
        )


@contextmanager
def watcher_lock(state_path):
    if fcntl is None:
        raise RuntimeError(
            "This watcher requires POSIX file-lock support (fcntl); every "
            "mode, including --once, shares the repository/PR state lock"
        )
    lock_path = state_path.with_suffix(state_path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as err:
            raise RuntimeError(
                f"Another watcher owns the state lock: {lock_path}"
            ) from err
        try:
            yield lock_path
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def get_pr_checks(pr_spec, repo):
    parsed = parse_pr_spec(pr_spec)
    cmd = ["pr", "checks"]
    if parsed["value"] is not None:
        cmd.append(parsed["value"])
    cmd.extend(["--json", checks_fields()])
    # gh exits 1 when checks failed and 8 when checks are pending, still
    # emitting JSON. An empty payload on those codes is a real error unless
    # gh explicitly reports that the PR has no checks; otherwise treating it
    # as zero checks would mask a failure as a benign policy state.
    stdout, stderr = gh_capture(cmd, repo=repo, allowed_returncodes=(1, 8))
    raw = stdout.strip()
    if not raw:
        if "no checks reported" in stderr.lower():
            return []
        raise GhCommandError(
            "`gh pr checks` returned no JSON payload; check state is unknown"
            + (f"\nstderr: {stderr.strip()}" if stderr.strip() else "")
        )
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as err:
        raise GhCommandError("Failed to parse JSON from `gh pr checks`") from err
    if not isinstance(data, list):
        raise GhCommandError("Unexpected payload from `gh pr checks`")
    return data


def is_pending_check(check):
    bucket = str(check.get("bucket") or "").lower()
    state = str(check.get("state") or "").upper()
    return bucket == "pending" or state in PENDING_CHECK_STATES


def summarize_checks(checks):
    pending_count = 0
    failed_count = 0
    passed_count = 0
    cancelled_count = 0
    for check in checks:
        bucket = str(check.get("bucket") or "").lower()
        if is_pending_check(check):
            pending_count += 1
        if bucket == "fail":
            failed_count += 1
        if bucket == "pass":
            passed_count += 1
        # gh buckets cancelled checks as `cancel`, not `fail`; a cancelled
        # required check must never read as clean.
        if bucket == "cancel":
            cancelled_count += 1
    return {
        "total_count": len(checks),
        "pending_count": pending_count,
        "failed_count": failed_count,
        "passed_count": passed_count,
        "cancelled_count": cancelled_count,
        "all_terminal": pending_count == 0,
        "items": checks,
    }


def workflow_run_ids_from_checks(checks):
    run_ids = set()
    for check in checks:
        if not isinstance(check, dict):
            continue
        # Details links take several shapes: .../runs/123, .../runs/123/job/456,
        # the legacy .../runs/123?check_suite_focus=true, and fragments.
        match = re.search(
            r"/actions/runs/(\d+)(?:[/?#]|$)", str(check.get("link") or "")
        )
        if match:
            run_ids.add(int(match.group(1)))
    return run_ids


def get_workflow_runs_for_sha(repo, head_sha):
    endpoint = f"repos/{repo}/actions/runs"
    return gh_api_object_list_paginated(
        endpoint,
        "workflow_runs",
        repo=repo,
        parameters={"head_sha": head_sha},
    )


def failed_runs_from_workflow_runs(runs, head_sha):
    failed_runs = []
    for run in runs:
        if not isinstance(run, dict):
            continue
        if str(run.get("head_sha") or "") != head_sha:
            continue
        conclusion = str(run.get("conclusion") or "")
        if conclusion not in FAILED_RUN_CONCLUSIONS:
            continue
        failed_runs.append(
            {
                "run_id": run.get("id"),
                "workflow_name": run.get("name") or run.get("display_title") or "",
                "status": str(run.get("status") or ""),
                "conclusion": conclusion,
                "html_url": str(run.get("html_url") or ""),
            }
        )
    failed_runs.sort(
        key=lambda item: (
            str(item.get("workflow_name") or ""),
            str(item.get("run_id") or ""),
        )
    )
    return failed_runs


def partition_runs_by_pr_checks(failed_runs, pr_check_run_ids):
    """Split failed runs into PR-check-backed runs and other head workflows."""
    pr_check_runs = []
    other_runs = []
    for run in failed_runs:
        if run.get("run_id") in pr_check_run_ids:
            pr_check_runs.append(run)
        else:
            other_runs.append(run)
    return pr_check_runs, other_runs


def get_jobs_for_run(repo, run_id):
    endpoint = f"repos/{repo}/actions/runs/{run_id}/jobs"
    return gh_api_object_list_paginated(endpoint, "jobs", repo=repo)


def failed_jobs_from_workflow_runs(repo, runs, head_sha):
    failed_jobs = []
    for run in runs:
        if not isinstance(run, dict):
            continue
        if str(run.get("head_sha") or "") != head_sha:
            continue
        run_id = run.get("id")
        if run_id in (None, ""):
            continue
        run_status = str(run.get("status") or "")
        run_conclusion = str(run.get("conclusion") or "")
        if (
            run_status.lower() == "completed"
            and run_conclusion not in FAILED_RUN_CONCLUSIONS
        ):
            continue
        jobs = get_jobs_for_run(repo, run_id)
        for job in jobs:
            if not isinstance(job, dict):
                continue
            conclusion = str(job.get("conclusion") or "")
            if conclusion not in FAILED_RUN_CONCLUSIONS:
                continue
            job_id = job.get("id")
            logs_endpoint = None
            if job_id not in (None, ""):
                logs_endpoint = f"repos/{repo}/actions/jobs/{job_id}/logs"
            failed_jobs.append(
                {
                    "run_id": run_id,
                    "workflow_name": run.get("name") or run.get("display_title") or "",
                    "run_status": run_status,
                    "run_conclusion": run_conclusion,
                    "job_id": job_id,
                    "job_name": str(job.get("name") or ""),
                    "status": str(job.get("status") or ""),
                    "conclusion": conclusion,
                    "html_url": str(job.get("html_url") or ""),
                    "logs_endpoint": logs_endpoint,
                }
            )
    failed_jobs.sort(
        key=lambda item: (
            str(item.get("workflow_name") or ""),
            str(item.get("job_name") or ""),
            str(item.get("job_id") or ""),
        )
    )
    return failed_jobs


_authenticated_login_cache = None


def get_authenticated_login():
    global _authenticated_login_cache
    if _authenticated_login_cache is not None:
        return _authenticated_login_cache
    data = gh_json(["api", "user"])
    if not isinstance(data, dict) or not data.get("login"):
        raise GhCommandError(
            "Unable to determine authenticated GitHub login from `gh api user`"
        )
    _authenticated_login_cache = str(data["login"])
    return _authenticated_login_cache


def comment_endpoints(repo, pr_number):
    return {
        "issue_comment": f"repos/{repo}/issues/{pr_number}/comments",
        "review_comment": f"repos/{repo}/pulls/{pr_number}/comments",
        "review": f"repos/{repo}/pulls/{pr_number}/reviews",
    }


def gh_api_list_paginated(endpoint, repo=None, per_page=100):
    items = []
    page = 1
    while True:
        sep = "&" if "?" in endpoint else "?"
        page_endpoint = f"{endpoint}{sep}per_page={per_page}&page={page}"
        payload = gh_json(["api", page_endpoint], repo=repo)
        if payload is None:
            break
        if not isinstance(payload, list):
            raise GhCommandError(f"Unexpected paginated payload from gh api {endpoint}")
        items.extend(payload)
        if len(payload) < per_page:
            break
        page += 1
    return items


def gh_api_object_list_paginated(
    endpoint,
    list_key,
    repo=None,
    parameters=None,
    per_page=100,
):
    items = []
    page = 1
    parameters = parameters or {}
    while True:
        command = [
            "api",
            endpoint,
            "-X",
            "GET",
            "-f",
            f"per_page={per_page}",
            "-f",
            f"page={page}",
        ]
        for key, value in sorted(parameters.items()):
            command.extend(["-f", f"{key}={value}"])
        payload = gh_json(command, repo=repo)
        if not isinstance(payload, dict):
            raise GhCommandError(f"Unexpected payload from gh api {endpoint}")
        page_items = payload.get(list_key) or []
        if not isinstance(page_items, list):
            raise GhCommandError(f"Expected `{list_key}` list from gh api {endpoint}")
        items.extend(page_items)
        if len(page_items) < per_page:
            break
        page += 1
    return items


def get_review_threads(pr, authenticated_login=None):
    owner, name = pr["repo"].split("/", 1)
    query = """
query($owner:String!,$name:String!,$number:Int!,$after:String) {
  repository(owner:$owner,name:$name) {
    pullRequest(number:$number) {
      reviewThreads(first:100,after:$after) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          isResolved
          isOutdated
          path
          line
          originalLine
          comments(first:100) {
            pageInfo { hasNextPage }
            nodes {
              databaseId
              author { login }
              authorAssociation
              body
              createdAt
              url
              pullRequestReview {
                databaseId
                state
                commit { oid }
              }
            }
          }
        }
      }
    }
  }
}
""".strip()
    threads = []
    cursor = None
    while True:
        command = [
            "api",
            "graphql",
            "-f",
            f"query={query}",
            "-f",
            f"owner={owner}",
            "-f",
            f"name={name}",
            "-F",
            f"number={pr['number']}",
        ]
        if cursor:
            command.extend(["-f", f"after={cursor}"])
        payload = gh_json(command, repo=pr["repo"])
        if isinstance(payload, dict) and payload.get("errors"):
            raise GhCommandError(
                "reviewThreads GraphQL returned errors; "
                "refusing to report partial thread evidence"
            )
        try:
            connection = payload["data"]["repository"]["pullRequest"]["reviewThreads"]
        except (KeyError, TypeError) as err:
            raise GhCommandError("Unexpected reviewThreads GraphQL payload") from err
        for node in connection.get("nodes") or []:
            comments_connection = node.get("comments") or {}
            if (comments_connection.get("pageInfo") or {}).get("hasNextPage"):
                raise GhCommandError(
                    "A review thread contains more than 100 comments; "
                    "refusing to report partial thread evidence"
                )
            comments = []
            for comment in comments_connection.get("nodes") or []:
                review = comment.get("pullRequestReview") or {}
                if str(review.get("state") or "").upper() == "PENDING":
                    continue
                normalized = {
                    "id": str(comment.get("databaseId") or ""),
                    "author": extract_login(comment.get("author")),
                    "author_association": str(comment.get("authorAssociation") or ""),
                    "body": str(comment.get("body") or ""),
                    "created_at": str(comment.get("createdAt") or ""),
                    "url": str(comment.get("url") or ""),
                    "review_id": str(review.get("databaseId") or ""),
                    "review_state": str(review.get("state") or "").upper(),
                    "candidate_sha": str((review.get("commit") or {}).get("oid") or ""),
                }
                normalized["source_class"] = classify_author(
                    normalized,
                    authenticated_login,
                )
                comments.append(normalized)
            if not comments:
                continue
            threads.append(
                {
                    "id": str(node.get("id") or ""),
                    "resolved": bool(node.get("isResolved")),
                    "outdated": bool(node.get("isOutdated")),
                    "path": node.get("path"),
                    "line": node.get("line"),
                    "original_line": node.get("originalLine"),
                    "comments": comments,
                }
            )
        page_info = connection.get("pageInfo") or {}
        if not page_info.get("hasNextPage"):
            break
        cursor = page_info.get("endCursor")
        if not cursor:
            raise GhCommandError("reviewThreads pagination omitted endCursor")
    return threads


def normalize_issue_comments(items):
    out = []
    for item in items:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "kind": "issue_comment",
                "id": str(item.get("id") or ""),
                "author": extract_login(item.get("user")),
                "author_association": str(item.get("author_association") or ""),
                "candidate_sha": None,
                "review_state": None,
                "created_at": str(item.get("created_at") or ""),
                "body": str(item.get("body") or ""),
                "path": None,
                "line": None,
                "url": str(item.get("html_url") or ""),
            }
        )
    return out


def normalize_review_comments(items, review_states):
    out = []
    for item in items:
        if not isinstance(item, dict):
            continue
        review_id = str(item.get("pull_request_review_id") or "")
        if review_states.get(review_id) == "PENDING":
            continue
        line = item.get("line")
        if line is None:
            line = item.get("original_line")
        out.append(
            {
                "kind": "review_comment",
                "id": str(item.get("id") or ""),
                "author": extract_login(item.get("user")),
                "author_association": str(item.get("author_association") or ""),
                "candidate_sha": str(
                    item.get("commit_id") or item.get("original_commit_id") or ""
                ),
                "review_id": review_id,
                "review_state": review_states.get(review_id),
                "created_at": str(item.get("created_at") or ""),
                "body": str(item.get("body") or ""),
                "path": item.get("path"),
                "line": line,
                "url": str(item.get("html_url") or ""),
            }
        )
    return out


def normalize_reviews(items):
    out = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if str(item.get("state") or "").upper() == "PENDING":
            continue
        out.append(
            {
                "kind": "review",
                "id": str(item.get("id") or ""),
                "author": extract_login(item.get("user")),
                "author_association": str(item.get("author_association") or ""),
                "candidate_sha": str(item.get("commit_id") or ""),
                "review_state": str(item.get("state") or "").upper(),
                "created_at": str(
                    item.get("submitted_at") or item.get("created_at") or ""
                ),
                "body": str(item.get("body") or ""),
                "path": None,
                "line": None,
                "url": str(item.get("html_url") or ""),
            }
        )
    return out


def extract_login(user_obj):
    if isinstance(user_obj, dict):
        return str(user_obj.get("login") or "")
    return ""


def is_bot_login(login):
    return bool(login) and login.endswith("[bot]")


def classify_author(item, authenticated_login):
    author = str(item.get("author") or "")
    if authenticated_login and author == authenticated_login:
        return "authenticated_operator"
    if is_bot_login(author):
        return "bot"
    association = str(item.get("author_association") or "").upper()
    if association in {"OWNER", "MEMBER", "COLLABORATOR"}:
        return "repository_member"
    return "external"


def _review_payloads(pr):
    repo = pr["repo"]
    pr_number = pr["number"]
    endpoints = comment_endpoints(repo, pr_number)
    return (
        gh_api_list_paginated(endpoints["issue_comment"], repo=repo),
        gh_api_list_paginated(endpoints["review_comment"], repo=repo),
        gh_api_list_paginated(endpoints["review"], repo=repo),
    )


def fetch_review_state(pr, state, authenticated_login=None):
    issue_payload, review_comment_payload, review_payload = _review_payloads(pr)

    issue_items = normalize_issue_comments(issue_payload)
    review_states = {
        str(item.get("id")): str(item.get("state") or "").upper()
        for item in review_payload
        if isinstance(item, dict) and item.get("id") not in (None, "")
    }
    pending_review_ids = {
        review_id
        for review_id, review_state in review_states.items()
        if review_state == "PENDING"
    }
    pending_review_comment_ids = {
        str(item.get("id"))
        for item in review_comment_payload
        if isinstance(item, dict)
        and item.get("id") not in (None, "")
        and str(item.get("pull_request_review_id") or "") in pending_review_ids
    }
    all_items = (
        issue_items
        + normalize_review_comments(review_comment_payload, review_states)
        + normalize_reviews(review_payload)
    )
    for item in all_items:
        item["source_class"] = classify_author(item, authenticated_login)

    seen_issue = {str(value) for value in state.get("seen_issue_comment_ids") or []}
    seen_review_comment = {
        str(value) for value in state.get("seen_review_comment_ids") or []
    }
    seen_review = {str(value) for value in state.get("seen_review_ids") or []}
    seen_review_comment.difference_update(pending_review_comment_ids)
    seen_review.difference_update(pending_review_ids)

    new_items = []
    for item in all_items:
        item_id = item.get("id")
        # Keep items with a deleted ("ghost") author: they still carry
        # published feedback and must surface as new exactly once.
        if not item_id:
            continue
        kind = item["kind"]
        seen = {
            "issue_comment": seen_issue,
            "review_comment": seen_review_comment,
            "review": seen_review,
        }[kind]
        if item_id in seen:
            continue
        new_items.append(item)
        seen.add(item_id)

    def sort_key(item):
        return (
            item.get("created_at") or "",
            item.get("kind") or "",
            item.get("id") or "",
        )

    all_items.sort(key=sort_key)
    new_items.sort(key=sort_key)
    state["seen_issue_comment_ids"] = sorted(seen_issue)
    state["seen_review_comment_ids"] = sorted(seen_review_comment)
    state["seen_review_ids"] = sorted(seen_review)
    return all_items, new_items


def current_retry_count(state, head_sha):
    retries = state.get("retries_by_sha") or {}
    value = retries.get(head_sha, 0)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def set_retry_count(state, head_sha, count):
    retries = state.get("retries_by_sha")
    if not isinstance(retries, dict):
        retries = {}
    retries[head_sha] = int(count)
    state["retries_by_sha"] = retries


def unique_actions(actions):
    out = []
    seen = set()
    for action in actions:
        if action not in seen:
            out.append(action)
            seen.add(action)
    return out


def has_failed_pr_checks(checks_summary, failed_runs, failed_jobs):
    """One shared failed-PR-check predicate.

    recommend_actions, is_github_candidate_clear, and the retry gate must
    all agree on what counts as a failed PR check; two diverging copies of
    this test have twice produced recommend/refuse contradictions.
    """
    return (
        checks_summary["failed_count"] > 0
        or int(checks_summary.get("cancelled_count") or 0) > 0
        or bool(failed_runs)
        or bool(failed_jobs)
    )


def is_github_candidate_clear(
    pr,
    checks_summary,
    failed_runs,
    failed_jobs,
    new_review_items,
    unresolved_threads,
):
    if pr["closed"] or pr["merged"]:
        return False
    if pr.get("draft"):
        return False
    if not pr.get("head_sha") or not pr.get("base_sha"):
        return False
    if int(checks_summary.get("total_count") or 0) == 0:
        return False
    if not checks_summary["all_terminal"]:
        return False
    if checks_summary["pending_count"] > 0:
        return False
    if has_failed_pr_checks(checks_summary, failed_runs, failed_jobs):
        return False
    if new_review_items:
        return False
    if unresolved_threads:
        return False
    if str(pr.get("mergeable") or "") != "MERGEABLE":
        return False
    if str(pr.get("merge_state_status") or "") in MERGE_CONFLICT_OR_BLOCKING_STATES:
        return False
    if str(pr.get("review_decision") or "") in MERGE_BLOCKING_REVIEW_DECISIONS:
        return False
    return True


def recommend_actions(
    pr,
    checks_summary,
    failed_runs,
    failed_jobs,
    new_review_items,
    unresolved_threads,
    candidate_changed,
    retries_used,
    max_retries,
    has_published_feedback=False,
):
    actions = []
    if pr["closed"] or pr["merged"]:
        if new_review_items or unresolved_threads:
            actions.append("process_review_feedback")
        actions.append("stop_pr_closed")
        return unique_actions(actions)

    if candidate_changed:
        actions.append("rebuild_candidate_evidence")

    # Draft and conflicting states are the ones that most need controller
    # action; never let them degenerate to a bare `idle`.
    if pr.get("draft"):
        actions.append("resolve_draft_state")
    if (
        str(pr.get("mergeable") or "") == "CONFLICTING"
        or str(pr.get("merge_state_status") or "") == "DIRTY"
    ):
        actions.append("resolve_merge_conflict")

    if new_review_items or unresolved_threads:
        actions.append("process_review_feedback")

    if has_failed_pr_checks(checks_summary, failed_runs, failed_jobs):
        if checks_summary["all_terminal"] and retries_used >= max_retries:
            # The exhausted budget only ends flaky retries; a new fixable
            # branch-caused failure at this head still deserves diagnosis.
            actions.append("diagnose_ci_failure")
            actions.append("stop_exhausted_retries")
        else:
            actions.append("diagnose_ci_failure")
            if (
                checks_summary["all_terminal"]
                and failed_runs
                and retries_used < max_retries
            ):
                actions.append("retry_failed_checks")

    if checks_summary["pending_count"] > 0:
        actions.append("wait_for_checks")
    elif int(checks_summary.get("total_count") or 0) == 0:
        actions.append("verify_required_check_policy")

    if is_github_candidate_clear(
        pr,
        checks_summary,
        failed_runs,
        failed_jobs,
        new_review_items,
        unresolved_threads,
    ):
        actions.append("verify_external_gates")
        # The watcher can dedupe conversation comments as "seen" but cannot
        # verify that the controller dispositioned them; issue comments have
        # no resolvable thread. `verify_external_gates` therefore asserts only
        # GitHub-native gates. Remind the controller whenever any published
        # feedback exists for this PR.
        if has_published_feedback:
            actions.append("confirm_feedback_disposition")
    elif str(pr.get("mergeable") or "") not in {"MERGEABLE", "CONFLICTING"}:
        actions.append("wait_for_mergeability")

    if not actions:
        actions.append("idle")
    return unique_actions(actions)


def pr_identity(pr):
    return str(pr["repo"]), int(pr["number"])


def collect_snapshot(args, locked_state_path, locked_pr_identity):
    pr = resolve_pr(args.pr, repo_override=args.repo)
    if pr_identity(pr) != locked_pr_identity:
        raise RuntimeError("Snapshot target changed repository/PR identity")
    state_path = (
        Path(args.state_file) if args.state_file else default_state_file_for(pr)
    )
    if state_path != locked_state_path:
        raise RuntimeError("Snapshot target changed state-file identity")
    state, _ = load_state(state_path)
    validate_state_target(state, pr, state_path)

    if not state.get("started_at"):
        state["started_at"] = int(time.time())

    prior_head = str(state.get("last_seen_head_sha") or "")
    prior_base = str(state.get("last_seen_base_sha") or "")
    head_changed = bool(prior_head and prior_head != pr["head_sha"])
    base_changed = bool(prior_base and prior_base != pr["base_sha"])
    candidate_changed = head_changed or base_changed

    authenticated_login = get_authenticated_login()
    all_review_items, new_review_items = fetch_review_state(
        pr,
        state,
        authenticated_login=authenticated_login,
    )
    review_threads = get_review_threads(
        pr,
        authenticated_login=authenticated_login,
    )
    unresolved_threads = [
        thread for thread in review_threads if not thread.get("resolved")
    ]
    # Surface review feedback before drilling into CI and mergeability details.
    # That keeps the babysitter responsive to new comments even when other
    # actions are also available.
    # `gh pr checks -R <repo>` requires an explicit PR/branch/url argument.
    # After resolving `--pr auto`, reuse the concrete PR number.
    checks = get_pr_checks(str(pr["number"]), repo=pr["repo"])
    checks_summary = summarize_checks(checks)
    pr_check_run_ids = workflow_run_ids_from_checks(checks)
    workflow_runs = get_workflow_runs_for_sha(pr["repo"], pr["head_sha"])
    all_failed_runs = failed_runs_from_workflow_runs(workflow_runs, pr["head_sha"])
    # Only workflow runs backing the PR's own checks gate readiness, diagnosis,
    # and retries. Other failed head-SHA workflows (push- or schedule-triggered)
    # are reported informationally so they can never wedge the watcher in an
    # unretryable, unclearable state.
    failed_runs, non_pr_check_failed_runs = partition_runs_by_pr_checks(
        all_failed_runs,
        pr_check_run_ids,
    )
    pr_check_workflow_runs = [
        run
        for run in workflow_runs
        if isinstance(run, dict) and run.get("id") in pr_check_run_ids
    ]
    failed_jobs = failed_jobs_from_workflow_runs(
        pr["repo"],
        pr_check_workflow_runs,
        pr["head_sha"],
    )

    retries_used = current_retry_count(state, pr["head_sha"])
    actions = recommend_actions(
        pr,
        checks_summary,
        failed_runs,
        failed_jobs,
        new_review_items,
        unresolved_threads,
        candidate_changed,
        retries_used,
        args.max_flaky_retries,
        has_published_feedback=bool(all_review_items or review_threads),
    )

    state["version"] = STATE_VERSION
    state["pr"] = {"repo": pr["repo"], "number": pr["number"]}
    state["last_seen_head_sha"] = pr["head_sha"]
    state["last_seen_base_sha"] = pr["base_sha"]
    state["last_snapshot_at"] = int(time.time())
    save_state(state_path, state)

    snapshot = {
        "pr": pr,
        "checks": checks_summary,
        "failed_runs": failed_runs,
        "non_pr_check_failed_runs": non_pr_check_failed_runs,
        "failed_jobs": failed_jobs,
        "review_items": all_review_items,
        "new_review_items": new_review_items,
        "review_threads": review_threads,
        "unresolved_threads": unresolved_threads,
        "candidate_change": {
            "head_changed": head_changed,
            "base_changed": base_changed,
            "previous_head_sha": prior_head or None,
            "previous_base_sha": prior_base or None,
        },
        "completion_policy": getattr(
            args,
            "completion_policy",
            "watch_until_closed",
        ),
        "actions": actions,
        "retry_state": {
            "current_sha_retries_used": retries_used,
            "max_flaky_retries": args.max_flaky_retries,
            "remaining": max(0, args.max_flaky_retries - retries_used),
        },
    }
    return snapshot, state_path


def resolve_locked_target(args):
    initial_pr = resolve_pr(args.pr, repo_override=args.repo)
    state_path = (
        Path(args.state_file) if args.state_file else default_state_file_for(initial_pr)
    )
    return state_path, pr_identity(initial_pr)


def retry_failed_now(args):
    state_path, locked_pr_identity = resolve_locked_target(args)
    with watcher_lock(state_path):
        return _retry_failed_now_locked(args, state_path, locked_pr_identity)


def _retry_failed_now_locked(args, state_path, locked_pr_identity):
    snapshot, _ = collect_snapshot(
        args,
        locked_state_path=state_path,
        locked_pr_identity=locked_pr_identity,
    )
    pr = snapshot["pr"]
    checks_summary = snapshot["checks"]
    failed_runs = snapshot["failed_runs"]
    retries_used = snapshot["retry_state"]["current_sha_retries_used"]
    max_retries = snapshot["retry_state"]["max_flaky_retries"]

    result = {
        "snapshot": snapshot,
        "state_file": str(state_path),
        "rerun_attempted": False,
        "rerun_count": 0,
        "rerun_run_ids": [],
        "rerun_results": [],
        "requested_run_ids": sorted(set(args.eligible_run_id)),
        "rejected_run_ids": [],
        "budget_reserved": False,
        "reserved_retry_count": None,
        "reason": None,
    }

    if pr["closed"] or pr["merged"]:
        result["reason"] = "pr_closed"
        return result
    # Use the exact predicate recommend_actions uses, so a recommended retry
    # is never refused with no_failed_pr_checks.
    if not has_failed_pr_checks(checks_summary, failed_runs, snapshot["failed_jobs"]):
        result["reason"] = "no_failed_pr_checks"
        return result
    if not failed_runs:
        result["reason"] = "no_failed_runs"
        return result
    if not checks_summary["all_terminal"]:
        result["reason"] = "checks_still_pending"
        return result
    if retries_used >= max_retries:
        result["reason"] = "retry_budget_exhausted"
        return result

    failed_run_ids = {
        int(run["run_id"]) for run in failed_runs if run.get("run_id") not in (None, "")
    }
    current_pr_run_ids = workflow_run_ids_from_checks(checks_summary["items"])
    requested_run_ids = set(args.eligible_run_id)
    rejected_run_ids = sorted(
        requested_run_ids - failed_run_ids.intersection(current_pr_run_ids)
    )
    if rejected_run_ids:
        result["rejected_run_ids"] = rejected_run_ids
        result["reason"] = "eligible_runs_not_current_failed_pr_checks"
        return result

    state, _ = load_state(state_path)
    validate_state_target(state, pr, state_path)
    live_retries_used = current_retry_count(state, pr["head_sha"])
    if live_retries_used >= max_retries:
        result["reason"] = "retry_budget_exhausted"
        return result

    reserved_retry_count = live_retries_used + 1
    set_retry_count(state, pr["head_sha"], reserved_retry_count)
    state["last_snapshot_at"] = int(time.time())
    save_state(state_path, state)
    result["budget_reserved"] = True
    result["reserved_retry_count"] = reserved_retry_count
    result["snapshot"]["retry_state"]["current_sha_retries_used"] = reserved_retry_count
    result["snapshot"]["retry_state"]["remaining"] = max(
        0,
        max_retries - reserved_retry_count,
    )

    for run_id in sorted(requested_run_ids):
        try:
            gh_text(["run", "rerun", str(run_id), "--failed"], repo=pr["repo"])
        except GhCommandError:
            result["rerun_results"].append(
                {"run_id": run_id, "status": "command_failed"}
            )
        else:
            result["rerun_run_ids"].append(run_id)
            result["rerun_results"].append({"run_id": run_id, "status": "triggered"})

    result["rerun_attempted"] = True
    result["rerun_count"] = len(result["rerun_run_ids"])
    if result["rerun_count"] == len(requested_run_ids):
        result["reason"] = "rerun_triggered"
    elif result["rerun_count"]:
        result["reason"] = "rerun_partially_failed"
    else:
        result["reason"] = "rerun_failed"
    return result


def print_json(obj):
    sys.stdout.write(json.dumps(obj, sort_keys=True) + "\n")
    sys.stdout.flush()


def print_event(event, payload):
    print_json({"event": event, "payload": payload})


def transient_retry_delay(poll_seconds, consecutive_failures):
    return min(poll_seconds * (2 ** (consecutive_failures - 1)), 300)


def run_watch(args):
    state_path, locked_pr_identity = resolve_locked_target(args)
    max_transient_failures = getattr(args, "max_transient_failures", 5)
    max_polls = getattr(args, "max_polls", 0)
    stop_when_clear = getattr(args, "stop_when_clear", False)
    consecutive_failures = 0
    polls = 0
    with watcher_lock(state_path):
        while True:
            try:
                snapshot, _ = collect_snapshot(
                    args,
                    locked_state_path=state_path,
                    locked_pr_identity=locked_pr_identity,
                )
            except GhCommandError as err:
                # A persistent watcher must survive transient GitHub CLI and
                # network failures. Identity failures (RuntimeError) still
                # fail closed immediately.
                consecutive_failures += 1
                if consecutive_failures > max_transient_failures:
                    raise
                delay = transient_retry_delay(args.poll_seconds, consecutive_failures)
                print_event(
                    "transient_error",
                    {
                        "error": str(err),
                        "consecutive_failures": consecutive_failures,
                        "max_transient_failures": max_transient_failures,
                        "retry_in_seconds": delay,
                    },
                )
                time.sleep(delay)
                continue
            consecutive_failures = 0
            polls += 1
            print_event(
                "snapshot",
                {
                    "snapshot": snapshot,
                    "state_file": str(state_path),
                    "next_poll_seconds": args.poll_seconds,
                },
            )
            actions = set(snapshot.get("actions") or [])
            if actions.intersection({"stop_pr_closed", "stop_exhausted_retries"}):
                print_event(
                    "stop",
                    {
                        "reason": "terminal_actions",
                        "actions": snapshot.get("actions"),
                        "pr": snapshot.get("pr"),
                    },
                )
                return 0
            if stop_when_clear and "verify_external_gates" in actions:
                print_event(
                    "stop",
                    {
                        "reason": "github_candidate_clear",
                        "actions": snapshot.get("actions"),
                        "pr": snapshot.get("pr"),
                    },
                )
                return 0
            if max_polls and polls >= max_polls:
                print_event(
                    "stop",
                    {
                        "reason": "max_polls_reached",
                        "actions": snapshot.get("actions"),
                        "pr": snapshot.get("pr"),
                    },
                )
                return 0
            time.sleep(args.poll_seconds)


def collect_snapshot_once(args):
    state_path, locked_pr_identity = resolve_locked_target(args)
    with watcher_lock(state_path):
        snapshot, _ = collect_snapshot(
            args,
            locked_state_path=state_path,
            locked_pr_identity=locked_pr_identity,
        )
        return snapshot, state_path


def main():
    args = parse_args()
    try:
        if args.retry_failed_now:
            print_json(retry_failed_now(args))
            return 0
        if args.watch:
            return run_watch(args)
        snapshot, state_path = collect_snapshot_once(args)
        snapshot["state_file"] = str(state_path)
        print_json(snapshot)
        return 0
    except (GhCommandError, OSError, RuntimeError, ValueError) as err:
        sys.stderr.write(f"PR watcher error: {err}\n")
        return 1
    except KeyboardInterrupt:
        sys.stderr.write("PR watcher interrupted\n")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
