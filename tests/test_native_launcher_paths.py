"""Exercise registered launchers in copied workspaces containing spaces."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from check_native_hook_launchers import CONFIGS, collect_commands, launch_command


class NativeLauncherPathsTest(unittest.TestCase):
    """Exact registrations anchor to the policy root from nested directories."""

    def test_registered_commands_anchor_and_missing_script_blocks(self):
        with tempfile.TemporaryDirectory(prefix="native launcher spaces ") as temporary:
            root = Path(temporary)
            (root / ".git").mkdir()
            nested = root / "nested directory"
            nested.mkdir()
            shutil.copytree(ROOT / "hooks", root / "hooks")
            for client, relative in CONFIGS:
                document = json.loads((ROOT / relative).read_text(encoding="utf-8"))
                command = next(value for value in collect_commands(document)
                               if "native_client_gate.py --client " + client in value)
                payload = {"cwd": str(root), "tool_name": "Bash",
                           "tool_input": {"command": "rm -rf /"}}
                result = launch_command(command, payload, nested)
                if client == "codex":
                    self.assertEqual(result.returncode, 2, result.stderr)
                else:
                    self.assertEqual(json.loads(result.stdout)["decision"], "deny")
                missing = command.replace("native_client_gate.py --client", "missing_gate.py --client")
                result = launch_command(missing, payload, nested)
                self.assertEqual(result.returncode, 2, result.stderr)


if __name__ == "__main__":
    unittest.main()
