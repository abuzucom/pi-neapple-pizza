"""Exercise real native adapters with client argument schemas."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class NativeSchemaRegressionTest(unittest.TestCase):
    """Require a denial before unsupported or uninspected operations run."""

    def assert_denied(self, client, name, arguments):
        payload = {"cwd": str(ROOT), "tool_name": name, "tool_input": arguments}
        if client == "antigravity":
            payload = {"workspacePaths": [str(ROOT)],
                       "toolCall": {"name": name, "args": arguments}}
        result = subprocess.run(
            [sys.executable, str(ROOT / "hooks/native_client_gate.py"), "--client", client],
            input=json.dumps(payload), capture_output=True, text=True, timeout=15, check=False)
        verdict = json.loads(result.stdout)
        if client == "codex":
            self.assertEqual(verdict["hookSpecificOutput"]["permissionDecision"], "deny")
        else:
            self.assertEqual(verdict["decision"], "deny")

    def test_unknown_tools_deny(self):
        for client in ("codex", "gemini", "antigravity"):
            with self.subTest(client=client):
                self.assert_denied(client, "unregistered_transfer", {"destination": "example.test"})

    def test_gemini_multi_file_read_denies_uninspected_globs(self):
        self.assert_denied("gemini", "read_many_files", {"include": ["**/*"]})

    def test_gemini_shell_directory_requires_validation(self):
        self.assert_denied("gemini", "run_shell_command",
                           {"command": "echo hello", "dir_path": "absent-native-working-directory"})

    def test_gemini_directory_target_requires_inspection(self):
        with tempfile.TemporaryDirectory() as temporary:
            protected = Path(temporary) / ".aws"
            protected.mkdir()
            self.assert_denied("gemini", "list_directory", {"dir_path": str(protected)})

    def test_antigravity_code_content_requires_inspection(self):
        self.assert_denied("antigravity", "write_to_file",
                           {"TargetFile": str(ROOT / "app.yaml"),
                            "CodeContent": "apiVersion: v1\nkind: Pod\n"})

    def test_antigravity_replacement_chunks_require_inspection(self):
        self.assert_denied("antigravity", "multi_replace_file_content",
                           {"TargetFile": str(ROOT / "app.yaml"),
                            "ReplacementChunks": [{"TargetContent": "plain",
                                                   "ReplacementContent": "apiVersion: v1\nkind: Pod\n"}]})


if __name__ == "__main__":
    unittest.main()
