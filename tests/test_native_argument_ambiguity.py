"""Reject conflicting native fields before choosing an execution target."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class NativeArgumentAmbiguityTest(unittest.TestCase):
    """Extra alias fields cannot conceal the actual client operation."""

    def deny(self, name, arguments):
        payload = {"workspacePaths": [str(ROOT)], "toolCall": {"name": name, "args": arguments}}
        result = subprocess.run(
            [sys.executable, str(ROOT / "hooks/native_client_gate.py"), "--client", "antigravity"],
            input=json.dumps(payload), capture_output=True, text=True, timeout=15, check=False)
        self.assertEqual(json.loads(result.stdout)["decision"], "deny")

    def test_conflicting_commands(self):
        self.deny("run_command", {"command": "echo hello", "CommandLine": "rm -rf /"})

    def test_conflicting_shell_directories(self):
        self.deny("run_command", {"CommandLine": "echo hello", "Cwd": str(ROOT), "dir_path": "hooks"})

    def test_conflicting_file_destinations(self):
        self.deny("write_to_file", {"file_path": "safe.txt", "TargetFile": ".aws/credentials",
                                    "CodeContent": "plain"})

    def test_conflicting_content(self):
        self.deny("write_to_file", {"TargetFile": "app.yaml", "content": "plain",
                                    "CodeContent": "apiVersion: v1\nkind: Pod\n"})

    def test_invalid_replacement_chunks(self):
        for chunks in (None, [], [None], [{}], [{"ReplacementContent": []}]):
            with self.subTest(chunks=chunks):
                self.deny("multi_replace_file_content", {"TargetFile": "safe.txt",
                                                         "ReplacementChunks": chunks})


if __name__ == "__main__":
    unittest.main()
