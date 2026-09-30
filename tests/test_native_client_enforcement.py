"""Exercise native client payloads through real policy subprocesses."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ADAPTER = ROOT / "hooks/native_client_gate.py"


def invoke(client, tool, arguments):
    """Invoke the registered adapter without executing the proposed operation."""
    payload = {"cwd": str(ROOT), "tool_name": tool, "tool_input": arguments}
    if client == "antigravity":
        payload = {"workspacePaths": [str(ROOT)], "toolCall": {"name": tool, "args": arguments}}
    return subprocess.run([sys.executable, str(ADAPTER), "--client", client],
                          input=json.dumps(payload), capture_output=True, text=True,
                          encoding="utf-8", timeout=30, check=False)


class NativeClientEnforcementTest(unittest.TestCase):
    """Native clients preserve destructive, infrastructure, and consent decisions."""

    def assert_denied(self, client, tool, arguments):
        result = invoke(client, tool, arguments)
        output = json.loads(result.stdout)
        if client == "codex":
            self.assertEqual(result.returncode, 2)
            self.assertEqual(output["hookSpecificOutput"]["permissionDecision"], "deny")
        else:
            self.assertEqual(result.returncode, 0)
            self.assertEqual(output["decision"], "deny")

    def test_shell_denials_and_consent_remain_closed(self):
        for client, tool, key in (("codex", "Bash", "command"),
                                  ("gemini", "run_shell_command", "command"),
                                  ("antigravity", "run_command", "CommandLine")):
            for command in ("rm -rf /", "git push --force-with-lease", "ssh example.com"):
                with self.subTest(client=client, command=command):
                    self.assert_denied(client, tool, {key: command})

    def test_allowed_command_passes(self):
        for client in ("codex", "gemini", "antigravity"):
            result = invoke(client, "Bash", {"command": "echo hello"})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "")

    def test_existing_test_and_protected_file_writes_deny(self):
        for client, tool, key in (("gemini", "replace", "file_path"),
                                  ("antigravity", "replace_file_content", "TargetFile")):
            for path in ("tests/test_activation_lock.py", "hooks/require_consent.py", ".aws/credentials"):
                with self.subTest(client=client, path=path):
                    self.assert_denied(client, tool, {key: str(ROOT / path)})

    def test_patch_checks_every_destination_and_move(self):
        for patch in ("*** Begin Patch\n*** Update File: tests/test_activation_lock.py\n@@\n-x\n+y\n*** End Patch\n",
                      "*** Begin Patch\n*** Add File: safe.txt\n+x\n*** Update File: README.md\n*** Move to: hooks/new.py\n@@\n-x\n+y\n*** End Patch\n"):
            self.assert_denied("codex", "apply_patch", {"command": patch})

    def test_malformed_shell_and_patch_deny(self):
        self.assert_denied("codex", "Bash", {"command": []})
        self.assert_denied("codex", "apply_patch", {"command": "uninspectable"})


if __name__ == "__main__":
    unittest.main()
