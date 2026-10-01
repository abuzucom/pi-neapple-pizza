"""Exercise exact native registrations with validated argument-array launch."""
import json
import os
import shlex
import subprocess
from pathlib import Path

CONFIGS = (("codex", ".codex/hooks.json"), ("gemini", ".gemini/settings.json"),
           ("antigravity", ".agents/hooks.json"))
BLOCKING_HOOKS = ("enforce_branch_name.py", "native_client_gate.py")
TIMEOUT_SECONDS = 30
MAX_BOOTSTRAP_BYTES = 4096
MAX_CONFIG_BYTES = 16 * 1024 * 1024
HOOK_NAMES = ('reinject_agents_policy.py', 'enforce_gate_adoption.py',
              'enforce_branch_name.py', 'native_client_gate.py')


def collect_commands(value: object) -> list[str]:
    """Collect the exact configured command strings."""
    if isinstance(value, dict):
        result = []
        for key, child in value.items():
            if key in ("command", "commandWindows") and isinstance(child, str):
                result.append(child)
            else:
                result.extend(collect_commands(child))
        return result
    if isinstance(value, list):
        return [command for child in value for command in collect_commands(child)]
    return []


def launch_command(command: str, payload: dict, cwd: Path,
                   *, windows: bool = False) -> subprocess.CompletedProcess:
    """Parse fixed registration text without executing shell substitutions."""
    arguments = shlex.split(command, posix=not windows)
    if not arguments or arguments[0] != "python":
        raise ValueError("native hook launcher is unsupported")
    environment = dict(os.environ)
    environment.pop("CLAUDE_PROJECT_DIR", None)
    return subprocess.run(arguments, input=json.dumps(payload), cwd=cwd,
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          env=environment, timeout=TIMEOUT_SECONDS, check=False)


def check_claude_launchers(root: Path) -> None:
    """Exercise structured Claude arguments through the real branch gate."""
    for relative in ('.claude/settings.json', 'hooks/claude-code-settings.example.json'):
        document = json.loads((root / relative).read_text(encoding='utf-8'))
        entries = document['hooks']['PreToolUse']
        hooks = [hook for entry in entries for hook in entry['hooks']
                 if any('enforce_branch_name.py' in argument for argument in hook.get('args', []))]
        if not hooks:
            raise ValueError('Claude branch gate registration is absent')
        for hook in hooks:
            arguments = [hook['command'], *(argument.replace('${CLAUDE_PROJECT_DIR}', str(root))
                                            for argument in hook['args'])]
            payload = {'hook_event_name': 'PreToolUse', 'tool_name': 'Bash', 'cwd': str(root),
                       'tool_input': {'command': 'git branch claude/forbidden'}}
            result = subprocess.run(arguments, input=json.dumps(payload), cwd=root / '.agents',
                                    capture_output=True, text=True, encoding='utf-8', errors='replace',
                                    timeout=TIMEOUT_SECONDS, check=False)
            if result.returncode != 2 or not result.stderr.strip():
                raise ValueError('configured Claude branch gate did not block')


def check_command_modes(command: str, payload: dict, cwd: Path, client: str) -> None:
    """Require gate decisions under POSIX and quote-retaining tokenization."""
    for windows in (False, True):
        result = launch_command(command, payload, cwd, windows=windows)
        if client == 'codex':
            if result.returncode != 2 or not result.stderr.strip():
                raise ValueError('configured Codex gate did not block')
            continue
        verdict = json.loads(result.stdout)
        if result.returncode != 0 or verdict.get('decision') != 'deny':
            raise ValueError('configured native gate did not block')


def build_bootstrap_prefix(root: Path) -> str:
    """Bound readable source before building the fixed invocation prefix."""
    path = root / 'scripts/hook_launcher_bootstrap.py'
    if path.is_symlink() or not path.is_file():
        raise ValueError('readable bootstrap is absent or a symlink')
    if path.stat().st_size > MAX_BOOTSTRAP_BYTES:
        raise ValueError('readable bootstrap exceeds its size bound')
    source = path.read_bytes()
    if len(source) > MAX_BOOTSTRAP_BYTES:
        raise ValueError('readable bootstrap changed beyond its size bound')
    expression = 'exec(bytes([' + ','.join(str(byte) for byte in source) + ']))'
    return 'python -c f"' + "'';{" + expression + '}" '


def read_native_commands(root: Path, relative: str, client: str, prefix: str) -> tuple[str, ...]:
    """Validate fixed source and complete argument tails before execution."""
    if (client, relative) not in CONFIGS:
        raise ValueError('native configuration target is unsupported')
    path = root / relative
    if path.is_symlink() or not path.is_file():
        raise ValueError('native client configuration is absent or a symlink')
    if path.stat().st_size > MAX_CONFIG_BYTES:
        raise ValueError('native client configuration exceeds its size bound')
    content = path.read_bytes()
    if len(content) > MAX_CONFIG_BYTES:
        raise ValueError('native configuration changed beyond its size bound')
    commands = tuple(dict.fromkeys(collect_commands(json.loads(content))))
    suffixes = {name + ' --client ' + client for name in HOOK_NAMES}
    if any(not command.startswith(prefix) or command[len(prefix):] not in suffixes
           for command in commands):
        raise ValueError('registered bootstrap or argument tail is unsupported')
    if not any('native_client_gate.py --client ' + client in command for command in commands):
        raise ValueError('native enforcement registration is absent')
    return commands


def build_gate_payload(root: Path, client: str, command: str) -> dict:
    """Send fixed probes through each documented native payload shape."""
    probe = 'git branch claude/forbidden' if 'enforce_branch_name.py' in command else 'rm -rf /'
    if client == 'antigravity':
        return {'workspacePaths': [str(root)],
                'toolCall': {'name': 'run_command', 'args': {'CommandLine': probe}}}
    return {'hook_event_name': 'PreToolUse', 'cwd': str(root), 'tool_name': 'Bash',
            'tool_input': {'command': probe}}


def check_native_launchers(root: Path) -> None:
    """Require exact configured blocking commands to deny from subdirectories."""
    expected_prefix = build_bootstrap_prefix(root)
    for client, relative in CONFIGS:
        commands = read_native_commands(root, relative, client, expected_prefix)
        for command in commands:
            if not any(name in command for name in BLOCKING_HOOKS):
                continue
            command_payload = build_gate_payload(root, client, command)
            for cwd in (root, root / ".agents"):
                check_command_modes(command, command_payload, cwd, client)
    check_claude_launchers(root)
