from __future__ import annotations

import unittest

import helpers  # noqa: F401
from metadata import (
    ChangesetMetadata,
    MetadataError,
    embed_pr_metadata,
    parse_commit_message,
    parse_pr_metadata,
    render_pr_metadata,
    stamp_commit_message,
)


class MetadataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.metadata = ChangesetMetadata(
            slug="api-foundation",
            index=2,
            source_branch="feature/report",
            source_sha="a" * 40,
        )

    def test_commit_message_round_trips_through_git_interpret_trailers(self) -> None:
        message = stamp_commit_message("feat: add API foundation", self.metadata)

        self.assertIn("Changeset-Slug: api-foundation", message)
        self.assertEqual(self.metadata, parse_commit_message(message))

    def test_parse_commit_message_rejects_missing_trailer(self) -> None:
        with self.assertRaisesRegex(MetadataError, "Changeset-Source"):
            parse_commit_message(
                "feat: incomplete\n\nChangeset-Slug: incomplete\nChangeset-Index: 1\n"
            )

    def test_pr_metadata_survives_human_body_edits(self) -> None:
        body = embed_pr_metadata("## Summary\n\nOriginal prose.\n", self.metadata)
        edited = "Reviewer context added.\n\n" + body.replace("Original", "Improved")

        self.assertEqual(self.metadata, parse_pr_metadata(edited))

    def test_embedding_replaces_one_existing_block(self) -> None:
        old = ChangesetMetadata("old", 1, "feature/report", "b" * 40)
        body = f"Human prose.\n\n{render_pr_metadata(old)}\n"

        updated = embed_pr_metadata(body, self.metadata)

        self.assertEqual(1, updated.count("carve-changesets:metadata:v1"))
        self.assertEqual(self.metadata, parse_pr_metadata(updated))

    def test_pr_metadata_rejects_multiple_blocks(self) -> None:
        block = render_pr_metadata(self.metadata)
        with self.assertRaisesRegex(MetadataError, "multiple"):
            parse_pr_metadata(f"{block}\n{block}\n")


if __name__ == "__main__":
    unittest.main()
