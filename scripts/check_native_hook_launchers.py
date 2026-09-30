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


def launch_command(command: str, payload: dict, cwd: Path) -> subprocess.CompletedProcess:
    """Parse fixed registration text without executing shell substitutions."""
    arguments = shlex.split(command, posix=True)
    if not arguments or arguments[0] != "python":
        raise ValueError("native hook launcher is unsupported")
    environment = dict(os.environ)
    environment.pop("CLAUDE_PROJECT_DIR", None)
    return subprocess.run(arguments, input=json.dumps(payload), cwd=cwd,
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          env=environment, timeout=TIMEOUT_SECONDS, check=False)


def check_native_launchers(root: Path) -> None:
    """Require exact configured blocking commands to deny from subdirectories."""
    for client, relative in CONFIGS:
        path = root / relative
        if not path.is_file():
            raise ValueError("native client configuration is absent")
        document = json.loads(path.read_text(encoding="utf-8"))
        commands = tuple(dict.fromkeys(collect_commands(document)))
        if not any("native_client_gate.py --client " + client in command for command in commands):
            raise ValueError("native enforcement registration is absent")
        payload = {"hook_event_name": "PreToolUse", "cwd": str(root), "tool_name": "Bash",
                   "tool_input": {"command": "rm -rf /"}}
        if client == "antigravity":
            payload = {"workspacePaths": [str(root)],
                       "toolCall": {"name": "run_command", "args": {"CommandLine": "rm -rf /"}}}
        for command in commands:
            if not any(name in command for name in BLOCKING_HOOKS):
                continue
            command_payload = json.loads(json.dumps(payload))
            if "enforce_branch_name.py" in command:
                if client == "antigravity":
                    command_payload["toolCall"]["args"]["CommandLine"] = "git branch claude/forbidden"
                else:
                    command_payload["tool_input"]["command"] = "git branch claude/forbidden"
            for cwd in (root, root / ".agents"):
                result = launch_command(command, command_payload, cwd)
                if client == "codex":
                    if result.returncode != 2:
                        raise ValueError("configured Codex gate did not block")
                else:
                    verdict = json.loads(result.stdout)
                    if result.returncode != 0 or verdict.get("decision") != "deny":
                        raise ValueError("configured native gate did not block")
