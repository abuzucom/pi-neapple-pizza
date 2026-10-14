"""Deny native tools the adapter cannot inspect and check multi-file reads."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ADAPTER = ROOT / "hooks/native_client_gate.py"
CREDENTIAL = str(ROOT / ".aws/credentials")


def invoke(client, tool, arguments):
    """Invoke the adapter without executing the proposed operation."""
    payload = {"cwd": str(ROOT), "tool_name": tool, "tool_input": arguments}
    if client == "antigravity":
        payload = {"workspacePaths": [str(ROOT)], "toolCall": {"name": tool, "args": arguments}}
    return subprocess.run([sys.executable, str(ADAPTER), "--client", client],
                          input=json.dumps(payload), capture_output=True, text=True,
                          encoding="utf-8", timeout=30, check=False)


class NativeUnknownToolsTest(unittest.TestCase):
    """Uninspected tools fail closed and multi-file reads check every entry."""

    def assert_denied(self, client, tool, arguments):
        result = invoke(client, tool, arguments)
        output = json.loads(result.stdout)
        if client == "codex":
            self.assertEqual(result.returncode, 2)
            self.assertEqual(output["hookSpecificOutput"]["permissionDecision"], "deny")
        else:
            self.assertEqual(result.returncode, 0)
            self.assertEqual(output["decision"], "deny")

    def assert_allowed(self, client, tool, arguments):
        result = invoke(client, tool, arguments)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "")

    def test_read_many_files_checks_every_path_and_include(self):
        for key in ("paths", "include"):
            with self.subTest(key=key):
                self.assert_denied("gemini", "read_many_files",
                                   {key: [str(ROOT / "README.md"), CREDENTIAL]})

    def test_read_many_files_requires_inspectable_entries(self):
        self.assert_denied("gemini", "read_many_files", {})
        self.assert_denied("gemini", "read_many_files", {"paths": "README.md"})
        self.assert_denied("gemini", "read_many_files", {"paths": [7]})

    def test_read_many_files_allows_ordinary_paths(self):
        self.assert_allowed("gemini", "read_many_files", {"paths": [str(ROOT / "README.md")]})

    def test_view_file_outline_checks_its_path(self):
        self.assert_denied("antigravity", "view_file_outline", {"AbsolutePath": CREDENTIAL})

    def test_unknown_tools_deny(self):
        for client in ("codex", "gemini", "antigravity"):
            for tool in ("mcp__server__read_secret", "future_tool"):
                with self.subTest(client=client, tool=tool):
                    self.assert_denied(client, tool, {"path": CREDENTIAL})

    def test_non_file_tools_pass(self):
        for client, tool in (("codex", "update_plan"), ("gemini", "google_web_search"),
                             ("gemini", "web_fetch"), ("gemini", "write_todos"),
                             ("antigravity", "search_web"), ("antigravity", "read_url_content")):
            with self.subTest(client=client, tool=tool):
                self.assert_allowed(client, tool, {"query": "policy"})


if __name__ == "__main__":
    unittest.main()
