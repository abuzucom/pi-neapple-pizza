"""Reject substituted hook code before entering an untrusted nested repository."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from check_native_hook_launchers import CONFIGS, collect_commands, launch_command


class NestedHookSubstitutionTest(unittest.TestCase):
    """A matching hook filename grants no authority to execute its contents."""

    def test_fake_nested_hook_never_executes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / ".git").mkdir()
            (root / "hooks").mkdir()
            (root / "hooks/native_client_gate.py").write_text(
                "print('SUBSTITUTED_GATE_EXECUTED')", encoding="utf-8")
            for client, relative in CONFIGS:
                document = json.loads((ROOT / relative).read_text(encoding="utf-8"))
                command = next(value for value in collect_commands(document)
                               if "native_client_gate.py --client " + client in value)
                result = launch_command(command, {}, root)
                self.assertNotIn("SUBSTITUTED_GATE_EXECUTED", result.stdout)
                self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
