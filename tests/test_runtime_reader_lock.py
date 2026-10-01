"""Exercise runtime readers against the installer's real operating-system lock."""
import json
import subprocess
import sys
import unittest
from pathlib import Path
from tools.bundle_transaction import exclusive_activation
from scripts.check_native_hook_launchers import collect_commands, launch_command

ROOT = Path(__file__).resolve().parent.parent


class RuntimeReaderLockTest(unittest.TestCase):
    """Activation excludes readers before any approved hook code executes."""

    def test_activation_lock_blocks_registered_reader(self):
        document = json.loads((ROOT / ".codex/hooks.json").read_text(encoding="utf-8"))
        command = next(value for value in collect_commands(document)
                       if "native_client_gate.py --client codex" in value)
        payload = {"cwd": str(ROOT), "tool_name": "Bash", "tool_input": {"command": "echo hello"}}
        with exclusive_activation(ROOT):
            result = launch_command(command, payload, ROOT)
        self.assertEqual(result.returncode, 2)
        self.assertIn("Hook runtime verification failed", result.stdout)
        result = launch_command(command, payload, ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")

    def test_claude_unknown_tool_denies(self):
        payload = {"cwd": str(ROOT), "tool_name": "unregistered_transfer", "tool_input": {}}
        result = subprocess.run(
            [sys.executable, str(ROOT / "hooks/native_client_gate.py"), "--client", "claude"],
            input=json.dumps(payload), capture_output=True, text=True, timeout=15, check=False)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")


if __name__ == "__main__":
    unittest.main()
