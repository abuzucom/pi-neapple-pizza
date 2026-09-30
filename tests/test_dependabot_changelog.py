"""Test the trusted Dependabot changelog companion boundaries."""
import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "create_dependabot_changelog_pr.py"
WORKFLOW = ROOT / ".github" / "workflows" / "dependabot-changelog.yml"
SYNC_WORKFLOW = ROOT / ".github" / "workflows" / "sync-check.yml"


def load_module():
    """Load the companion automation without running its CLI."""
    spec = importlib.util.spec_from_file_location("dependabot_changelog", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DependabotChangelogTest(unittest.TestCase):
    """Keep the companion workflow limited to the trusted bot account."""

    def test_patch_version_increments_only_patch_component(self):
        module = load_module()
        self.assertEqual(module._next_version("## [2.0.43] (2026-09-17)\n"), (2, 0, 44))

    def test_entry_contains_original_pull_request_number(self):
        module = load_module()
        entry = module._insert_entry(
            "# Changelog\n\n## [2.0.43] (2026-09-17)\n",
            (2, 0, 44),
            80,
        )
        self.assertIn("## [2.0.44]", entry)
        self.assertIn("pull request #80", entry)

    def test_workflow_requires_successful_pull_request_run(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("github.event.workflow_run.event == 'pull_request'", text)
        self.assertIn("github.event.workflow_run.conclusion == 'success'", text)
        self.assertIn("github.event.pull_request.user.id", SYNC_WORKFLOW.read_text(encoding="utf-8"))

    def test_dependabot_identity_is_immutable_numeric_id(self):
        module = load_module()
        self.assertEqual(module.DEPENDABOT_ID, 49699333)
        self.assertNotIn("pull_request.user.login", WORKFLOW.read_text(encoding="utf-8"))

    def test_non_dependabot_pull_request_has_no_companion(self):
        module = load_module()
        module._api_json = lambda _path: [{"number": 81, "user": {"id": 7}, "state": "open"}]
        self.assertIsNone(module._find_dependabot_pr("abuzucom/agents", "a" * 40))

    def test_empty_pulls_list_returns_none(self):
        module = load_module()
        module._api_json = lambda _path: []
        self.assertIsNone(module._find_dependabot_pr("abuzucom/agents", "a" * 40))

    def test_multiple_non_dependabot_pulls_returns_none(self):
        module = load_module()
        module._api_json = lambda _path: [
            {"number": 81, "user": {"id": 7}, "state": "open"},
            {"number": 82, "user": {"id": 8}, "state": "open"},
        ]
        self.assertIsNone(module._find_dependabot_pr("abuzucom/agents", "a" * 40))

    def test_closed_dependabot_pull_request_returns_none(self):
        module = load_module()
        module._api_json = lambda _path: [
            {"number": 80, "user": {"id": module.DEPENDABOT_ID}, "state": "closed"}
        ]
        self.assertIsNone(module._find_dependabot_pr("abuzucom/agents", "a" * 40))

    def test_closed_dependabot_detail_returns_none(self):
        module = load_module()
        module._api_json = lambda path: (
            [{"number": 80, "user": {"id": module.DEPENDABOT_ID}, "state": "open"}]
            if "commits" in path else
            {"number": 80, "state": "closed", "base": {"ref": "main"}, "head": {"ref": "dependabot/pip/foo"}}
        )
        self.assertIsNone(module._find_dependabot_pr("abuzucom/agents", "a" * 40))

    def test_open_dependabot_detail_returns_detail(self):
        module = load_module()
        expected = {
            "number": 80,
            "state": "open",
            "base": {"ref": "main"},
            "head": {"ref": "dependabot/pip/foo"},
        }
        module._api_json = lambda path: (
            [{"number": 80, "user": {"id": module.DEPENDABOT_ID}, "state": "open"}]
            if "commits" in path else
            expected
        )
        self.assertEqual(module._find_dependabot_pr("abuzucom/agents", "a" * 40), expected)

    def test_create_companion_switches_branch_before_writing(self):
        import tempfile
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            changelog = repo / "CHANGELOG.md"
            changelog.write_text("## [2.2.0] (2026-09-18)\n\n### Added\n- Feature.\n", encoding="utf-8")
            git_calls = []
            module._existing_companion = lambda _b: False
            module.run_git = lambda _r, args, **_kw: (
                git_calls.append(args) or type("Result", (), {"stdout": ""})()
            )
            module._run_gh = lambda _args: ""
            module._repository = lambda: "abuzucom/agents"
            module._changed_files = lambda _r, _n: ["requirements.txt"]
            pull = {
                "number": 80,
                "title": "bump foo from 1 to 2",
                "base": {"ref": "main"},
                "head": {"ref": "dependabot/pip/foo"},
            }
            module.create_companion(repo, pull)
            self.assertEqual(git_calls[0], ["switch", "-c", "chore/dependabot-changelog-80"])
            self.assertEqual(git_calls[1], ["add", "CHANGELOG.md"])


if __name__ == "__main__":
    unittest.main()
