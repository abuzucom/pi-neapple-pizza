"""Keep working-directory modules out of registered native hook launchers."""
import json
import shlex
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from check_native_hook_launchers import CONFIGS, collect_commands, launch_command

HIJACK_MODULE = """import sys
sys.exit(0)
"""


class NativeLauncherIsolationTest(unittest.TestCase):
    """Registered launchers ignore modules planted in the working directory."""

    def test_every_registration_runs_python_isolated(self):
        for _client, relative in CONFIGS:
            document = json.loads((ROOT / relative).read_text(encoding="utf-8"))
            for command in collect_commands(document):
                with self.subTest(config=relative, command=command[:60]):
                    self.assertEqual(shlex.split(command)[:3], ["python", "-I", "-c"])

    def test_planted_modules_cannot_allow_a_denied_call(self):
        with tempfile.TemporaryDirectory(prefix="native launcher isolation ") as temporary:
            root = Path(temporary)
            (root / ".git").mkdir()
            shutil.copytree(ROOT / "hooks", root / "hooks")
            for module in ("pathlib.py", "runpy.py", "json.py"):
                (root / module).write_text(HIJACK_MODULE, encoding="utf-8")
            for client, relative in CONFIGS:
                document = json.loads((ROOT / relative).read_text(encoding="utf-8"))
                command = next(value for value in collect_commands(document)
                               if "native_client_gate.py --client " + client in value)
                payload = {"cwd": str(root), "tool_name": "Bash",
                           "tool_input": {"command": "rm -rf /"}}
                with self.subTest(client=client):
                    result = launch_command(command, payload, root)
                    if client == "codex":
                        self.assertEqual(result.returncode, 2, result.stderr)
                    else:
                        self.assertEqual(json.loads(result.stdout)["decision"], "deny")


if __name__ == "__main__":
    unittest.main()
