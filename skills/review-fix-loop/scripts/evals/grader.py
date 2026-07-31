"""Result-blind grading primitives for the review-fix-loop evaluation corpus.

Acceptance criterion: "Evaluators are result-blind and cannot pass solely
because the implementation asserts success." Every function here derives its
verdict from live Git state (or, for locks, live filesystem/`flock` state) —
never merely from the returned terminal-result document's own claims. A
scenario in `corpus.py` may still read `result["head"]["final"]` to know
*which* SHA to independently re-derive evidence about, but the grading
comparison itself is always against a value this module computed by asking
Git directly, so a terminal result that lies about the candidate's state
disagrees with these functions rather than being trusted by them.

`grade_case` itself is deliberately generic: it does not know about
"convergence" or "budget exhaustion" or any other scenario category. Each
scenario in `corpus.py` supplies its own `checks` mapping of
`name -> (expected, observed)` pairs, where `observed` was computed by one of
this module's independent-evidence helpers (or, for the two fields the
terminal-result contract itself defines, read from the result and compared
against this corpus's own independently decided expectation). `grade_case`
only diffs those pairs and reports exactly which named check failed for which
fixture — satisfying "evaluation output identifies the exact fixture,
observed evidence, and reason for failure."
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from helpers import LE  # noqa: E402


def rev_parse(repo: Path, ref: str) -> str | None:
    result = LE.git("rev-parse", "--verify", ref, cwd=repo, check=False)
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def ls_remote(remote: Path, ref: str) -> str | None:
    result = LE.git("ls-remote", str(remote), ref, check=False)
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return result.stdout.split()[0]


def show_file(repo: Path, ref: str, path: str) -> str | None:
    result = LE.git("show", f"{ref}:{path}", cwd=repo, check=False)
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def object_exists(repo: Path, sha: str) -> bool:
    return LE.git("cat-file", "-e", sha, cwd=repo, check=False).returncode == 0


def rev_list_count(repo: Path, old: str, new: str) -> int:
    return int(LE.git("rev-list", "--count", f"{old}..{new}", cwd=repo).stdout.strip())


def worktree_is_clean(repo: Path) -> bool:
    status = LE.worktree_status(repo)
    return not status["staged"] and not status["unstaged"] and not status["untracked"]


def untracked_paths(repo: Path) -> list[str]:
    return LE.worktree_status(repo)["untracked"]


def grade_case(case: dict[str, Any]) -> list[str]:
    """Return `f"{case_id}: {check_name}: expected ... observed ..."` failure
    strings for every mismatched `checks` entry. Empty means every
    independently derived expectation for this fixture held."""
    case_id = case["id"]
    failures: list[str] = []
    for name, (expected, observed) in case["checks"].items():
        if expected != observed:
            failures.append(
                f"{case_id}: {name}: expected {expected!r}, observed {observed!r}"
            )
    return failures
