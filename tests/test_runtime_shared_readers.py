"""Verify overlapping readers through the real configured hook launcher."""
import json
import unittest
from pathlib import Path
from scripts.verified_hook_runtime import runtime_lock
from scripts.check_native_hook_launchers import collect_commands, launch_command

ROOT = Path(__file__).resolve().parent.parent


class RuntimeSharedReadersTest(unittest.TestCase):
    """Independent hooks can inspect the same complete generation concurrently."""

    def test_parallel_reader_remains_available(self):
        document = json.loads((ROOT / ".codex/hooks.json").read_text(encoding="utf-8"))
        command = next(value for value in collect_commands(document)
                       if "native_client_gate.py --client codex" in value)
        payload = {"cwd": str(ROOT), "tool_name": "Bash", "tool_input": {"command": "echo hello"}}
        with runtime_lock(ROOT):
            result = launch_command(command, payload, ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
