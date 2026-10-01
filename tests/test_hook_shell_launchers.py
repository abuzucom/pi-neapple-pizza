"""Exercise registered launchers through native shell command parsing."""
import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path

from scripts.check_native_hook_launchers import CONFIGS, collect_commands

ROOT = Path(__file__).resolve().parent.parent
TIMEOUT_SECONDS = 30


def resolve_shells() -> list[list[str]]:
    """Return fixed installed shell programs without invoking a model client."""
    if os.name != 'nt':
        return [['/bin/sh', '-c']]
    return [[str(Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'),
             '-NoProfile', '-NonInteractive', '-Command'],
            [str(Path(os.environ['SystemRoot']) / 'System32/cmd.exe'), '/D', '/S', '/C'],
            [str(Path(os.environ['ProgramFiles']) / 'Git/bin/bash.exe'), '-c']]


class HookShellLauncherTest(unittest.TestCase):
    """Fixed source survives native shell parsing without losing gate execution."""

    def test_registered_branch_commands_execute_through_every_shell(self):
        payload = {'hook_event_name': 'PreToolUse', 'cwd': str(ROOT),
                   'tool_name': 'Bash', 'tool_input': {'command': 'git branch claude/forbidden'},
                   'workspacePaths': [str(ROOT)],
                   'toolCall': {'name': 'run_command',
                                'args': {'CommandLine': 'git branch claude/forbidden'}}}
        for client, relative in CONFIGS:
            document = json.loads((ROOT / relative).read_text(encoding='utf-8'))
            command = next(value for value in collect_commands(document)
                           if 'enforce_branch_name.py --client ' + client in value)
            for shell in resolve_shells():
                with self.subTest(client=client, shell=shell[0]):
                    self.assertTrue(Path(shell[0]).is_file(), shell[0])
                    invocation = command
                    if shell[-1] == '-Command':
                        invocation += ';exit $LASTEXITCODE'
                    result = subprocess.run([*shell, invocation], cwd=ROOT / '.agents',
                                            input=json.dumps(payload), capture_output=True,
                                            text=True, encoding='utf-8', errors='replace',
                                            timeout=TIMEOUT_SECONDS, check=False)
                    if client == 'codex':
                        self.assertEqual(result.returncode, 2, result.stderr)
                        self.assertTrue(result.stderr.strip())
                    else:
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertEqual(json.loads(result.stdout)['decision'], 'deny')


if __name__ == '__main__':
    unittest.main()
