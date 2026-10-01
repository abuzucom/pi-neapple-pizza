"""Exercise Windows parsing against every configured agent launcher."""
import json
import os
import shlex
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIGS = ('.codex/hooks.json', '.gemini/settings.json', '.agents/hooks.json',
           '.claude/settings.json', 'hooks/claude-code-settings.example.json')
TIMEOUT_SECONDS = 30


def collect_entries(value: object) -> list[dict]:
    """Collect command registrations without changing their argument shape."""
    if isinstance(value, list):
        return [entry for child in value for entry in collect_entries(child)]
    if not isinstance(value, dict):
        return []
    if value.get('type') == 'command':
        return [value]
    return [entry for child in value.values() for entry in collect_entries(child)]


def resolve_arguments(entry: dict, root: Path) -> list[str]:
    """Retain Windows quotes instead of silently applying POSIX parsing."""
    command = entry.get('commandWindows', entry['command'])
    arguments = shlex.split(command, posix=False)
    arguments.extend(argument.replace('${CLAUDE_PROJECT_DIR}', str(root))
                     for argument in entry.get('args', []))
    arguments[0] = sys.executable
    return arguments


class RegisteredWindowsLauncherTest(unittest.TestCase):
    """Configured launchers execute gates instead of quoted Python literals."""

    def test_every_python_source_survives_quote_retaining_parsing(self):
        for relative in CONFIGS:
            document = json.loads((ROOT / relative).read_text(encoding='utf-8'))
            for entry in collect_entries(document):
                with self.subTest(config=relative, command=entry['command']):
                    arguments = resolve_arguments(entry, ROOT)
                    if '-c' in arguments:
                        source = arguments[arguments.index('-c') + 1]
                        compile(source, '<registered-hook>', 'exec')
                        self.assertFalse(source.startswith(('"', "'")))

    def test_every_registered_branch_gate_executes_from_nested_cwd(self):
        payload = {'hook_event_name': 'PreToolUse', 'cwd': str(ROOT),
                   'tool_name': 'Bash', 'tool_input': {'command': 'git branch claude/forbidden'},
                   'workspacePaths': [str(ROOT)],
                   'toolCall': {'name': 'run_command',
                                'args': {'CommandLine': 'git branch claude/forbidden'}}}
        for relative in CONFIGS:
            document = json.loads((ROOT / relative).read_text(encoding='utf-8'))
            entries = [entry for entry in collect_entries(document)
                       if 'enforce_branch_name.py' in ' '.join(
                           [entry['command'], *entry.get('args', [])])]
            self.assertTrue(entries, relative)
            for entry in entries:
                with self.subTest(config=relative):
                    result = subprocess.run(resolve_arguments(entry, ROOT), cwd=ROOT / '.agents',
                                            input=json.dumps(payload), capture_output=True,
                                            text=True, encoding='utf-8', errors='replace',
                                            timeout=TIMEOUT_SECONDS, check=False)
                    self.assertNotIn('SyntaxError', result.stderr)
                    self.assertIn(result.returncode, (0, 2), result.stderr)
                    if result.returncode == 0:
                        self.assertEqual(json.loads(result.stdout).get('decision'), 'deny')
                    else:
                        self.assertTrue(result.stderr.strip())


if __name__ == '__main__':
    unittest.main()
