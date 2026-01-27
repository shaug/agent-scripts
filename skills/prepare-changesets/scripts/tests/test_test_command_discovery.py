from __future__ import annotations

import json
import shutil
import unittest

import helpers  # noqa: F401  # ensures sys.path is set
from common import discover_test_command
from helpers import chdir, init_repo


class TestCommandDiscoveryTests(unittest.TestCase):
    def test_agents_single_command_is_selected(self) -> None:
        repo_dir, _plan = init_repo()
        try:
            (repo_dir / "AGENTS.md").write_text("```bash\njust test\n```\n")
            (repo_dir / "justfile").write_text("test:\n  echo ok\n")
            with chdir(repo_dir):
                discovery = discover_test_command("")
            self.assertEqual(discovery["command"], "just test")
            self.assertEqual(discovery["source"], "agents")
        finally:
            shutil.rmtree(repo_dir)

    def test_agents_ambiguous_returns_suggestions(self) -> None:
        repo_dir, _plan = init_repo()
        try:
            (repo_dir / "AGENTS.md").write_text("```bash\njust test\nmake test\n```\n")
            (repo_dir / "justfile").write_text("test:\n  echo ok\n")
            with chdir(repo_dir):
                discovery = discover_test_command("")
            self.assertIsNone(discovery["command"])
            self.assertEqual(discovery["reason"], "agents-ambiguous")
            self.assertIn("just test", discovery["suggestions"])
        finally:
            shutil.rmtree(repo_dir)

    def test_missing_agents_suggests_just_test(self) -> None:
        repo_dir, _plan = init_repo()
        try:
            (repo_dir / "justfile").write_text("test:\n  echo ok\n")
            with chdir(repo_dir):
                discovery = discover_test_command("")
            self.assertIsNone(discovery["command"])
            self.assertEqual(discovery["reason"], "agents-missing")
            self.assertIn("just test", discovery["suggestions"])
        finally:
            shutil.rmtree(repo_dir)

    def test_package_json_suggestions_include_tool_and_script(self) -> None:
        repo_dir, _plan = init_repo()
        try:
            (repo_dir / "package.json").write_text(
                json.dumps({"scripts": {"test": "vitest run"}}, indent=2) + "\n"
            )
            with chdir(repo_dir):
                discovery = discover_test_command("")
            self.assertIsNone(discovery["command"])
            self.assertIn("npm test", discovery["suggestions"])
            self.assertIn("vitest run", discovery["suggestions"])
        finally:
            shutil.rmtree(repo_dir)


if __name__ == "__main__":
    unittest.main()
