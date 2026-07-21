from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import helpers
from metadata import ChangesetMetadata, embed_pr_metadata, stamp_commit_message
from rehydrate import PullRequestRecord, RehydrationError, rehydrate_chain
from status import status_from_live


class RehydrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.repo, self.bare, self.source_sha = helpers.init_repo(self.temp_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir)

    def _materialize(
        self, indices: tuple[int, ...] = (1, 2)
    ) -> tuple[dict[int, str], list[PullRequestRecord]]:
        heads: dict[int, str] = {}
        prs: list[PullRequestRecord] = []
        previous = "main"
        for index in indices:
            branch = f"feature/report-{index}"
            helpers.run(self.repo, "git", "checkout", "-b", branch, previous)
            (self.repo / f"changeset-{index}.txt").write_text(f"changeset {index}\n")
            helpers.run(self.repo, "git", "add", f"changeset-{index}.txt")
            metadata = ChangesetMetadata(
                slug=f"part-{index}",
                index=index,
                source_branch="feature/report",
                source_sha=self.source_sha,
            )
            heads[index] = helpers.commit(
                self.repo,
                stamp_commit_message(f"feat: changeset {index}", metadata),
            )
            helpers.run(self.repo, "git", "push", "-u", "origin", branch)
            base = "main" if index == 1 else f"feature/report-{index - 1}"
            prs.append(
                PullRequestRecord(
                    number=100 + index,
                    head_branch=branch,
                    head_sha=heads[index],
                    base_branch=base,
                    state="MERGED" if index == 1 else "OPEN",
                    body=embed_pr_metadata(
                        f"## Overall Feature\n\nReport API\n\n## This Changeset ({index} of 2)\n",
                        metadata,
                    ),
                )
            )
            previous = branch
        return heads, prs

    def _fresh_clone(self) -> Path:
        clone = self.temp_dir / "fresh"
        helpers.run(self.temp_dir, "git", "clone", str(self.bare), str(clone))
        helpers.run(clone, "git", "fetch", "--prune", "origin")
        return clone

    def test_rehydrates_full_chain_after_local_state_is_deleted(self) -> None:
        heads, prs = self._materialize()
        state_dir = self.repo / ".carve-changesets"
        state_dir.mkdir()
        (state_dir / "plan.json").write_text("{}\n")
        shutil.rmtree(state_dir)
        clone = self._fresh_clone()

        chain = rehydrate_chain(
            source_branch="feature/report", pull_requests=prs, cwd=clone
        )

        self.assertEqual("main", chain.base_branch)
        self.assertEqual(self.source_sha, chain.source_sha)
        self.assertEqual(
            ["part-1", "part-2"], [item.metadata.slug for item in chain.changesets]
        )
        self.assertEqual([heads[1], heads[2]], [item.head for item in chain.changesets])
        self.assertEqual([101, 102], [item.pr_number for item in chain.changesets])
        self.assertEqual(
            ["main", "feature/report-1"], [item.base for item in chain.changesets]
        )

    def test_status_is_rendered_from_rehydration_without_local_files(self) -> None:
        _, prs = self._materialize()
        clone = self._fresh_clone()
        output = status_from_live(
            source_branch="feature/report", pull_requests=prs, cwd=clone
        )

        self.assertIn("feature/report-1", output)
        self.assertIn("#101", output)
        self.assertIn("MERGED", output)
        self.assertIn("feature/report-2", output)
        self.assertIn("OPEN", output)

    def test_trailers_survive_propagation_rebase(self) -> None:
        _, _ = self._materialize()
        helpers.run(self.repo, "git", "checkout", "feature/report-1")
        (self.repo / "upstream.txt").write_text("upstream\n")
        helpers.run(self.repo, "git", "add", "upstream.txt")
        helpers.commit(self.repo, "feat: update first changeset")
        helpers.run(self.repo, "git", "checkout", "feature/report-2")
        helpers.run(self.repo, "git", "rebase", "feature/report-1")
        message = helpers.run(self.repo, "git", "show", "-s", "--format=%B", "HEAD")

        from metadata import parse_commit_message

        parsed = parse_commit_message(message)
        self.assertEqual(2, parsed.index)
        self.assertEqual("part-2", parsed.slug)
        self.assertEqual(self.source_sha, parsed.source_sha)

    def test_missing_branch_index_fails_closed(self) -> None:
        self._materialize(indices=(1, 3))
        clone = self._fresh_clone()

        with self.assertRaisesRegex(RehydrationError, "missing index 2"):
            rehydrate_chain(
                source_branch="feature/report", base_branch="main", cwd=clone
            )

    def test_missing_commit_trailer_fails_closed(self) -> None:
        helpers.run(self.repo, "git", "checkout", "-b", "feature/report-1", "main")
        (self.repo / "plain.txt").write_text("plain\n")
        helpers.run(self.repo, "git", "add", "plain.txt")
        helpers.commit(self.repo, "feat: no trailers")
        helpers.run(self.repo, "git", "push", "-u", "origin", "feature/report-1")
        clone = self._fresh_clone()

        with self.assertRaisesRegex(
            RehydrationError, "Missing required changeset trailer"
        ):
            rehydrate_chain(
                source_branch="feature/report", base_branch="main", cwd=clone
            )

    def test_conflicting_pr_base_fails_closed(self) -> None:
        _, prs = self._materialize()
        clone = self._fresh_clone()
        conflicting = [
            prs[0],
            PullRequestRecord(**{**prs[1].__dict__, "base_branch": "main"}),
        ]

        with self.assertRaisesRegex(RehydrationError, "conflicts with expected base"):
            rehydrate_chain(
                source_branch="feature/report", pull_requests=conflicting, cwd=clone
            )

    def test_trailer_and_pr_metadata_disagreement_fails_closed(self) -> None:
        _, prs = self._materialize()
        clone = self._fresh_clone()
        wrong = ChangesetMetadata("wrong", 2, "feature/report", self.source_sha)
        conflicting = [
            prs[0],
            PullRequestRecord(
                **{**prs[1].__dict__, "body": embed_pr_metadata(prs[1].body, wrong)}
            ),
        ]

        with self.assertRaisesRegex(RehydrationError, "metadata disagrees"):
            rehydrate_chain(
                source_branch="feature/report", pull_requests=conflicting, cwd=clone
            )


if __name__ == "__main__":
    unittest.main()
