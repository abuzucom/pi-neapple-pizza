#!/usr/bin/env python3
"""Exercise the pi client adapter against the unchanged canonical gates."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

try:
    from tests.json_line_worker import JsonLineWorkerProcess
except ImportError:
    from json_line_worker import JsonLineWorkerProcess

ROOT = Path(__file__).resolve().parent.parent
ADAPTER = ROOT / "hooks" / "pi_client_gate.py"
IDENTITY_SCRIPTS = ("check_git_identity.py", "trusted_git.py", "trusted_gh.py")
REQUEST_TIMEOUT_SECONDS = 120
_ADAPTER_WORKER = None


def adapter_worker():
    """Return the process-local persistent adapter worker."""
    global _ADAPTER_WORKER
    if _ADAPTER_WORKER is None:
        _ADAPTER_WORKER = JsonLineWorkerProcess(
            "main", ADAPTER, request_timeout=REQUEST_TIMEOUT_SECONDS)
    return _ADAPTER_WORKER


def run_git(repository: Path, *arguments: str) -> None:
    """Run a real git command in a throwaway test repository."""
    subprocess.run(["git", *arguments], cwd=repository, check=True,
                   capture_output=True, text=True)


class PiClientGateTest(unittest.TestCase):
    """Cover the decisions the pi adapter produces from canonical gates."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.repository = Path(self.directory.name)
        run_git(self.repository, "init", "-q", "-b", "main")
        run_git(self.repository, "config", "user.name", "Test User")
        run_git(self.repository, "config", "user.email", "test@example.com")
        (self.repository / "README.md").write_text("# Fixture\n", encoding="utf-8")
        run_git(self.repository, "add", "README.md")
        run_git(self.repository, "commit", "-q", "-m", "feat: add fixture")
        run_git(self.repository, "checkout", "-q", "-b", "feat/pi-adapter-test")

    def tearDown(self):
        self.directory.cleanup()

    def install_identity_checker(self):
        """Copy the canonical identity checker into the session repository."""
        scripts = self.repository / "scripts"
        scripts.mkdir()
        for name in IDENTITY_SCRIPTS:
            shutil.copy(ROOT / "scripts" / name, scripts / name)

    def decide(self, payload: dict, event: str = "tool") -> dict:
        """Return the parsed adapter decision for one request."""
        response = adapter_worker().request({
            "arguments": ["--event", event],
            "stdin": json.dumps(payload),
            "cwd": str(self.repository),
            "environment": dict(os.environ),
        })
        stdout = response.get("stdout", "")
        self.assertTrue(stdout.strip(), response.get("stderr", ""))
        decision = json.loads(stdout)
        self.assertIsInstance(decision, dict)
        return decision

    def call(self, tool: str, arguments: dict) -> dict:
        """Return the decision for one pi tool call."""
        return self.decide({"tool": tool, "arguments": arguments,
                            "cwd": str(self.repository)})

    def test_ordinary_shell_command_is_allowed(self):
        decision = self.call("bash", {"command": "echo hello"})
        self.assertEqual(decision["decision"], "allow")

    def test_recursive_delete_of_the_root_is_denied(self):
        decision = self.call("bash", {"command": "rm -rf /"})
        self.assertEqual(decision["decision"], "deny")

    def test_forced_push_is_denied(self):
        decision = self.call("bash", {"command": "git push --force origin main"})
        self.assertEqual(decision["decision"], "deny")

    def test_prohibited_agent_branch_command_is_denied(self):
        decision = self.call("bash", {"command": "git checkout -b claude/side-quest"})
        self.assertEqual(decision["decision"], "deny")

    def test_unknown_tool_is_denied(self):
        decision = self.call("web_search", {"query": "anything"})
        self.assertEqual(decision["decision"], "deny")

    def test_infrastructure_credential_read_is_denied(self):
        decision = self.call("read", {"path": ".aws/credentials"})
        self.assertEqual(decision["decision"], "deny")

    def test_edit_of_an_existing_test_file_is_denied(self):
        tests = self.repository / "tests"
        tests.mkdir()
        (tests / "test_existing.py").write_text("def test_one():\n    pass\n",
                                                encoding="utf-8")
        decision = self.call("edit", {"path": "tests/test_existing.py",
                                      "edits": [{"oldText": "pass", "newText": "fail"}]})
        self.assertEqual(decision["decision"], "deny")

    def test_write_of_a_new_test_file_is_allowed(self):
        decision = self.call("write", {"path": "tests/test_new.py",
                                       "content": "def test_one():\n    pass\n"})
        self.assertEqual(decision["decision"], "allow")

    def test_write_to_a_protected_gate_file_is_denied(self):
        decision = self.call("write", {"path": "hooks/other_gate.py",
                                       "content": "print('x')\n"})
        self.assertEqual(decision["decision"], "deny")

    def test_malformed_payload_is_denied(self):
        response = adapter_worker().request({
            "arguments": ["--event", "tool"],
            "stdin": "not json",
            "cwd": str(self.repository),
            "environment": dict(os.environ),
        })
        decision = json.loads(response["stdout"])
        self.assertEqual(decision["decision"], "deny")

    def test_missing_working_directory_is_denied(self):
        decision = self.decide({"tool": "bash", "arguments": {"command": "echo hello"}})
        self.assertEqual(decision["decision"], "deny")

    def test_working_directory_outside_a_directory_is_denied(self):
        readme = self.repository / "README.md"
        decision = self.decide({"tool": "bash", "arguments": {"command": "echo hello"},
                                 "cwd": str(readme)})
        self.assertEqual(decision["decision"], "deny")

    def test_payload_outside_an_object_is_denied(self):
        response = adapter_worker().request({
            "arguments": ["--event", "tool"],
            "stdin": "[1, 2]",
            "cwd": str(self.repository),
            "environment": dict(os.environ),
        })
        decision = json.loads(response["stdout"])
        self.assertEqual(decision["decision"], "deny")

    def test_missing_tool_name_is_denied(self):
        decision = self.decide({"arguments": {"command": "echo hello"},
                                "cwd": str(self.repository)})
        self.assertEqual(decision["decision"], "deny")

    def test_missing_tool_arguments_are_denied(self):
        decision = self.decide({"tool": "bash", "cwd": str(self.repository)})
        self.assertEqual(decision["decision"], "deny")

    def test_payload_beyond_the_inspection_bound_is_denied(self):
        payload = {"tool": "bash", "arguments": {"command": "echo " + "a" * 70000},
                   "cwd": str(self.repository)}
        decision = self.decide(payload)
        self.assertEqual(decision["decision"], "deny")

    def test_edit_arguments_outside_a_list_are_allowed(self):
        decision = self.call("edit", {"path": "notes.txt", "edits": "not a list"})
        self.assertEqual(decision["decision"], "allow")

    def test_edit_entry_outside_an_object_is_allowed(self):
        decision = self.call("edit", {"path": "notes.txt", "edits": ["not an object"]})
        self.assertEqual(decision["decision"], "allow")

    def test_commit_with_a_disallowed_identity_is_denied(self):
        self.install_identity_checker()
        decision = self.call("bash", {"command": "git commit -m 'feat: add notes'"})
        self.assertEqual(decision["decision"], "deny")
        self.assertIn("identity", decision["reason"])

    def test_session_reports_the_identity_advisory(self):
        self.install_identity_checker()
        decision = self.decide({"cwd": str(self.repository)}, event="session")
        self.assertEqual(decision["decision"], "allow")
        self.assertIn("GIT IDENTITY VIOLATION", decision["warning"])

    def test_session_on_a_compliant_branch_is_allowed(self):
        decision = self.decide({"cwd": str(self.repository)}, event="session")
        self.assertEqual(decision["decision"], "allow")
        self.assertNotIn("context", decision)

    def test_session_on_a_primary_branch_is_denied(self):
        run_git(self.repository, "checkout", "-q", "main")
        decision = self.decide({"cwd": str(self.repository)}, event="session")
        self.assertEqual(decision["decision"], "deny")
        self.assertIn("BRANCH PREFLIGHT FAILED", decision["context"])

    def test_session_outside_a_repository_is_denied(self):
        with tempfile.TemporaryDirectory() as outside:
            decision = self.decide({"cwd": outside}, event="session")
            self.assertEqual(decision["decision"], "deny")

    def test_tool_call_on_a_primary_branch_is_denied(self):
        run_git(self.repository, "checkout", "-q", "main")
        decision = self.call("bash", {"command": "echo hello"})
        self.assertEqual(decision["decision"], "deny")
        self.assertIn("branch preflight failed", decision["reason"])


if __name__ == "__main__":
    unittest.main()
