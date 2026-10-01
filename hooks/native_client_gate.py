"""Adapt observable native tool calls to the unchanged canonical gates."""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAX_PAYLOAD_BYTES = 65536
MAX_OUTPUT_BYTES = 1048576
CHECK_TIMEOUT_SECONDS = 20
SHELL_TOOLS = frozenset({"Bash", "PowerShell", "Cmd", "CMD", "CommandPrompt",
                         "run_shell_command", "run_command", "exec_command"})
FILE_TOOLS = {"Read": "Read", "read_file": "Read", "view_file": "Read",
              "Write": "Write", "write_file": "Write", "write_to_file": "Write",
              "Edit": "Edit", "replace": "Edit", "replace_file_content": "Edit",
              "MultiEdit": "MultiEdit", "multi_replace_file_content": "MultiEdit",
              "NotebookEdit": "NotebookEdit", "Glob": "Glob", "Grep": "Grep",
              "glob": "Glob", "grep_search": "Grep", "search_file_content": "Grep",
              "find_by_name": "Glob", "list_directory": "Glob", "list_dir": "Glob"}
SHELL_GATES = (("block_destructive_bash.py", "Bash"),
               ("block_destructive_powershell.py", "PowerShell"),
               ("block_destructive_cmd.py", "Cmd"))
CLAUDE_CANONICAL_TOOLS = frozenset({"Bash", "PowerShell", "Cmd", "CMD", "CommandPrompt",
                                  "Read", "Write", "Edit", "MultiEdit", "NotebookEdit", "Glob", "Grep"})
QUESTION_TOOLS = {"claude": "AskUserQuestion", "codex": "request_user_input",
                  "gemini": "ask_user", "antigravity": "notify_user"}


def deny_call(client: str, reason: str) -> int:
    """Emit only supported denial responses without a consent fallthrough."""
    message = "Native policy gate: " + reason
    if client in ("codex", "claude"):
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
              "permissionDecision": "deny", "permissionDecisionReason": message}}))
        print(message, file=sys.stderr)
        return 2
    print(json.dumps({"decision": "deny", "reason": message}))
    return 0


def read_call(client: str) -> tuple[str, dict, str]:
    """Validate bounded native input before selecting a tool path."""
    raw = sys.stdin.buffer.read(MAX_PAYLOAD_BYTES + 1)
    if len(raw) > MAX_PAYLOAD_BYTES:
        raise ValueError("tool payload exceeds the inspection bound")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("tool payload is not an object")
    if client == "antigravity" and "toolCall" in payload:
        call = payload["toolCall"]
        workspaces = payload.get("workspacePaths")
        if not isinstance(call, dict) or not isinstance(workspaces, list) or len(workspaces) != 1:
            raise ValueError("workspace or tool metadata is ambiguous")
        name, arguments, cwd = call.get("name"), call.get("args"), workspaces[0]
    else:
        name, arguments, cwd = payload.get("tool_name"), payload.get("tool_input"), payload.get("cwd")
    if not isinstance(name, str) or not isinstance(arguments, dict):
        raise ValueError("tool name or arguments cannot be inspected")
    if not isinstance(cwd, str) or not Path(cwd).is_dir():
        raise ValueError("tool working directory cannot be inspected")
    return name, arguments, cwd


def run_gate(filename: str, tool: str, arguments: dict, cwd: str) -> None:
    """Run the real gate with bounded capture and no command execution."""
    gate = ROOT / "hooks" / filename
    if not gate.is_file():
        raise ValueError("a required policy gate is absent")
    payload = {"hook_event_name": "PreToolUse", "tool_name": tool,
               "tool_input": arguments, "cwd": cwd, "permission_mode": "default"}
    environment = dict(os.environ)
    environment["CLAUDE_PROJECT_DIR"] = cwd
    with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as diagnostic:
        result = subprocess.run([sys.executable, "-E", "-s", str(gate)],
                                input=json.dumps(payload).encode("utf-8"), env=environment,
                                stdout=output, stderr=diagnostic, cwd=cwd,
                                timeout=CHECK_TIMEOUT_SECONDS, check=False)
        output.seek(0)
        raw = output.read(MAX_OUTPUT_BYTES + 1)
    if len(raw) > MAX_OUTPUT_BYTES:
        raise ValueError("the canonical gate response exceeds the inspection bound")
    if result.returncode and not raw.strip():
        raise ValueError("the canonical gate failed validation")
    if not raw.strip():
        return
    verdict = json.loads(raw)
    if not isinstance(verdict, dict):
        raise ValueError("the canonical gate response cannot be inspected")
    details = verdict.get("hookSpecificOutput")
    if not isinstance(details, dict):
        raise ValueError("the canonical gate decision is absent or malformed")
    decision = details.get("permissionDecision")
    if decision in ("ask", "deny"):
        reason = details.get("permissionDecisionReason")
        raise ValueError(reason if isinstance(reason, str) else "active-human authorization is required")
    if result.returncode:
        raise ValueError("the canonical gate failed validation")
    if decision != "allow":
        raise ValueError("the canonical gate response is unsupported")


def inspect_shell(arguments: dict, cwd: str) -> None:
    """Inspect every shell family before allowing a native shell operation."""
    commands = [arguments[key] for key in ("command", "CommandLine", "cmd") if key in arguments]
    if not commands or any(not isinstance(value, str) or not value.strip() for value in commands):
        raise ValueError("shell command cannot be inspected")
    command = commands[0]
    if any(value != command for value in commands):
        raise ValueError("conflicting shell command fields")
    effective = resolve_argument_path(arguments, ("dir_path", "workdir", "Cwd"), cwd, default=cwd)
    if not Path(effective).is_dir():
        raise ValueError("shell working directory cannot be inspected")
    for filename, tool in SHELL_GATES:
        run_gate(filename, tool, {"command": command}, effective)
    inspect_identity(command, effective)


def inspect_identity(command: str, cwd: str) -> None:
    """Preserve the canonical identity checker for each effective Git context."""
    sys.path.insert(0, str(ROOT / "hooks"))
    import enforce_git_identity
    if not (ROOT / "scripts/check_git_identity.py").is_file():
        raise ValueError("the canonical identity checker is absent")
    for invocation in enforce_git_identity.blocked_command(command, cwd):
        if enforce_git_identity._blocks_invocation(str(ROOT), invocation):
            raise ValueError("the Git operation failed canonical identity validation")


def inspect_file(tool: str, arguments: dict, cwd: str) -> None:
    """Normalize named paths while preserving the native write content."""
    normalized = dict(arguments)
    path = resolve_argument_path(arguments, ("file_path", "TargetFile", "AbsolutePath",
                 "DirectoryPath", "SearchDirectory", "dir_path", "path", "notebook_path"),
                 cwd, default=cwd if tool in ("Glob", "Grep") else None)
    normalized["file_path"] = path
    normalized["path"] = path
    if "Content" in arguments:
        normalized["content"] = arguments["Content"]
    if "CodeContent" in arguments:
        if not isinstance(arguments["CodeContent"], str):
            raise ValueError("write content cannot be inspected")
        normalized["content"] = arguments["CodeContent"]
    contents = [arguments[key] for key in ("content", "Content", "CodeContent") if key in arguments]
    if any(not isinstance(value, str) for value in contents):
        raise ValueError("write content cannot be inspected")
    if contents and any(value != contents[0] for value in contents):
        raise ValueError("conflicting write content fields")
    if "ReplacementContent" in arguments:
        normalized["new_string"] = arguments["ReplacementContent"]
    if "ReplacementChunks" in arguments:
        normalized["edits"] = normalize_replacement_chunks(arguments["ReplacementChunks"])
    run_gate("block_infrastructure_access.py", tool, normalized, cwd)
    if tool in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        run_gate("require_consent.py", tool, normalized, cwd)


def resolve_argument_path(arguments: dict, keys: tuple, cwd: str, *, default: str | None) -> str:
    """Reject ambiguous path aliases before choosing the effective target."""
    values = [arguments[key] for key in keys if key in arguments]
    if not values:
        values = [default]
    if any(not isinstance(value, str) or not value for value in values):
        raise ValueError("operation path cannot be inspected")
    paths = [str((Path(cwd) / value).resolve()) for value in values]
    if any(value != paths[0] for value in paths):
        raise ValueError("conflicting operation path fields")
    return paths[0]


def normalize_replacement_chunks(chunks: object) -> list[dict]:
    """Validate every native replacement before canonical content inspection."""
    if not isinstance(chunks, list) or not chunks:
        raise ValueError("replacement chunks cannot be inspected")
    edits = []
    for chunk in chunks:
        if not isinstance(chunk, dict) or not isinstance(chunk.get("ReplacementContent"), str):
            raise ValueError("replacement chunk content cannot be inspected")
        edits.append({"new_string": chunk["ReplacementContent"]})
    return edits


def inspect_patch(arguments: dict, cwd: str) -> None:
    """Inspect every patch destination without executing patch text."""
    patch = arguments.get("command")
    if not isinstance(patch, str) or not patch.startswith("*** Begin Patch\n"):
        raise ValueError("patch structure cannot be inspected")
    lines = patch.splitlines()
    if not lines or lines[-1] != "*** End Patch":
        raise ValueError("patch terminator is absent")
    paths = []
    for line in lines[1:-1]:
        for prefix in ("*** Add File: ", "*** Update File: ", "*** Delete File: ", "*** Move to: "):
            if not line.startswith(prefix):
                continue
            if prefix == "*** Delete File: ":
                raise ValueError("patch deletion requires active-human authorization")
            paths.append(line[len(prefix):])
    if not paths:
        raise ValueError("patch destinations are absent")
    for path in paths:
        inspect_file("Write", {"file_path": path, "content": patch}, cwd)


def main() -> int:
    """Deny malformed requests and preserve each canonical policy decision."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", required=True, choices=("claude", "codex", "gemini", "antigravity"))
    options = parser.parse_args()
    try:
        name, arguments, cwd = read_call(options.client)
        if options.client == "claude" and name in CLAUDE_CANONICAL_TOOLS:
            return 0
        if name == QUESTION_TOOLS[options.client]:
            return 0
        if name in SHELL_TOOLS:
            inspect_shell(arguments, cwd)
        elif name == "apply_patch":
            inspect_patch(arguments, cwd)
        elif name in FILE_TOOLS:
            inspect_file(FILE_TOOLS[name], arguments, cwd)
        else:
            raise ValueError("tool has no approved inspection adapter")
    except (ValueError, OSError, subprocess.SubprocessError, UnicodeError, ImportError) as error:
        reason = " ".join(str(error).splitlines())
        reason = "".join(character for character in reason if 32 <= ord(character) < 127)
        return deny_call(options.client, reason[:512])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
