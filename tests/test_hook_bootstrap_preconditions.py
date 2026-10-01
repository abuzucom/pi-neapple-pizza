"""Require bootstrap preconditions before argument and target access."""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOTSTRAP = ROOT / 'scripts/hook_launcher_bootstrap.py'


class HookBootstrapPreconditionsTest(unittest.TestCase):
    """Absent arguments and unregistered destinations deny before execution."""

    def test_invalid_arguments_deny_before_target_use(self):
        for arguments in ([], ['../README.md'], ['README.md'], ['native_client_gate.py/extra']):
            with self.subTest(arguments=arguments):
                result = subprocess.run([sys.executable, str(BOOTSTRAP), *arguments],
                                        cwd=ROOT, capture_output=True, text=True,
                                        encoding='utf-8', errors='replace', timeout=30, check=False)
                self.assertEqual(result.returncode, 2)
                self.assertIn('restore the complete verified gate set', result.stderr)
                self.assertEqual(result.stdout, '')
                self.assertNotIn('Traceback', result.stderr)


if __name__ == '__main__':
    unittest.main()
