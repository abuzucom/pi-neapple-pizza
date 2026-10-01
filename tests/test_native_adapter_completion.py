"""Exercise native adapter decisions that require explicit schema coverage."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ADAPTER = ROOT / "hooks/native_client_gate.py"


class NativeAdapterCompletionTest(unittest.TestCase):
    """Reach each native adapter decision through its subprocess entry point."""

    def invoke(self, client, name, arguments):
        """Run one native adapter request and return the completed process."""
        payload = {"cwd": str(ROOT), "tool_name": name, "tool_input": arguments}
        return subprocess.run(
            [sys.executable, str(ADAPTER), "--client", client],
            input=json.dumps(payload), capture_output=True, text=True,
            timeout=15, check=False)

    def test_claude_canonical_tool_continues_to_specific_gates(self):
        result = self.invoke("claude", "Read", {"file_path": str(ROOT / "README.md")})
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_question_tool_remains_available(self):
        result = self.invoke("codex", "request_user_input", {})
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_native_content_alias_reaches_canonical_file_gate(self):
        result = self.invoke(
            "codex", "write_file",
            {"file_path": str(ROOT / "native-adapter-output.txt"), "Content": "plain"})
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_non_string_code_content_denies(self):
        result = self.invoke(
            "codex", "write_file",
            {"file_path": str(ROOT / "native-adapter-output.txt"), "CodeContent": []})
        verdict = json.loads(result.stdout)
        self.assertEqual(verdict["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_non_string_content_denies(self):
        result = self.invoke(
            "codex", "write_file",
            {"file_path": str(ROOT / "native-adapter-output.txt"), "content": []})
        verdict = json.loads(result.stdout)
        self.assertEqual(verdict["hookSpecificOutput"]["permissionDecision"], "deny")


if __name__ == "__main__":
    unittest.main()
