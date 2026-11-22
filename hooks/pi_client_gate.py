#!/usr/bin/env python3
"""Route pi tool calls and session events through the unchanged canonical gates.

pi runs as an agent client inside this repository, and the adopted policy
registers gates for Claude, Codex, Gemini, and Antigravity. No registration
covers pi, so a pi tool call reaches the operating system with no policy check
behind it.

This adapter closes that gap without changing a canonical gate. It maps one pi
tool call onto the canonical gate scripts that the registered clients use,
reads the canonical decision, and reports it to the caller. It fails closed: a
request it cannot inspect, a gate it cannot run, and a decision it cannot read
all produce a denial.

The adapter denies every act that a canonical gate would put to a human. The
registered native clients deny those acts for the same reason, and pi offers no
authorization channel that an agent cannot reach on its own.

The caller supplies the request as JSON on standard input and reads the
decision as JSON on standard output. The request names the pi tool, its
arguments, and the session working directory.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOKS = ROOT / "hooks"
ADOPTION_CHECKER = ROOT / "scripts" / "check_gate_adoption.py"
BRANCH_GATE = "enforce_branch_name.py"
IDENTITY_GATE = "enforce_git_identity.py"
MAX_PAYLOAD_BYTES = 65536
MAX_OUTPUT_BYTES = 1048576
MAX_REASON_CHARACTERS = 512
MAX_CONTEXT_CHARACTERS = 8192
CHECK_TIMEOUT_SECONDS = 60

# pi tool name -> canonical tool name and the canonical gates that inspect it.
TOOL_GATES = {
    "bash": ("Bash", ("block_destructive_bash.py",)),
    "powershell": ("PowerShell", ("block_destructive_powershell.py",)),
    "read": ("Read", ("block_infrastructure_access.py",)),
    "find": ("Glob", ("block_infrastructure_access.py",)),
    "grep": ("Grep", ("block_infrastructure_access.py",)),
    "ls": ("Glob", ("block_infrastructure_access.py",)),
    "write": ("Write", ("block_infrastructure_access.py", "require_consent.py")),
    "edit": ("Edit", ("block_infrastructure_access.py", "require_consent.py")),
}
SHELL_TOOLS = frozenset({"bash", "powershell"})
READ_ONLY_TOOLS = frozenset({"read", "find", "grep", "ls"})


def bounded_reason(text: str) -> str:
    """Return one printable reason bounded for a decision payload."""
    collapsed = " ".join(str(text).splitlines())
    printable = "".join(character for character in collapsed if 32 <= ord(character) < 127)
    return printable[:MAX_REASON_CHARACTERS]


def emit(decision: str, reason: str = "", context: str = "", warning: str = "") -> int:
    """Print one decision and return the exit code the caller reads."""
    payload = {"decision": decision}
    if reason:
        payload["reason"] = bounded_reason(reason)
    if context:
        payload["context"] = context[:MAX_CONTEXT_CHARACTERS]
    if warning:
        payload["warning"] = warning[:MAX_CONTEXT_CHARACTERS]
    print(json.dumps(payload))
    return 0 if decision == "allow" else 2


def read_request() -> dict:
    """Return the request object read from standard input."""
    raw = sys.stdin.read(MAX_PAYLOAD_BYTES + 1)
    if len(raw) > MAX_PAYLOAD_BYTES:
        raise ValueError("the request payload exceeds the inspection bound")
    try:
        payload = json.loads(raw)
    except ValueError as error:
        raise ValueError("the request payload is not valid JSON") from error
    if not isinstance(payload, dict):
        raise ValueError("the request payload is not an object")
    return payload


def session_directory(value: object) -> str:
    """Return the existing session directory named by the request."""
    if not isinstance(value, str) or not value:
        raise ValueError("the session working directory is missing or malformed")
    if not Path(value).is_dir():
        raise ValueError("the session working directory cannot be inspected")
    return os.path.realpath(value)


def canonical_input(tool: str, arguments: dict) -> dict:
    """Return one canonical tool input for a pi tool call."""
    normalized = dict(arguments)
    path = arguments.get("path")
    if isinstance(path, str) and path:
        normalized["file_path"] = path
    if tool != "edit":
        return normalized
    edits = arguments.get("edits")
    if not isinstance(edits, list):
        return normalized
    converted = []
    for entry in edits:
        if not isinstance(entry, dict):
            converted.append(entry)
            continue
        item = dict(entry)
        if isinstance(item.get("newText"), str):
            item["new_string"] = item["newText"]
        converted.append(item)
    normalized["edits"] = converted
    return normalized


def read_decision(verdict: dict, filename: str, returncode: int, errors: str) -> tuple:
    """Return the decision, reason, and context carried by one gate response.

    The canonical gates report a PreToolUse decision in the Claude shape. A
    response in any other shape cannot be inspected, so the adapter refuses
    it instead of guessing.
    """
    details = verdict.get("hookSpecificOutput")
    if not isinstance(details, dict):
        raise ValueError(f"{filename} returned a decision that cannot be inspected")
    decision = details.get("permissionDecision")
    reason = details.get("permissionDecisionReason")
    if decision in ("deny", "ask"):
        return "deny", reason if isinstance(reason, str) else f"{filename} denied the call", ""
    if decision == "allow":
        if returncode:
            raise ValueError(errors.strip() or f"{filename} failed validation")
        return "allow", "", ""
    context = details.get("additionalContext")
    if isinstance(context, str) and context.strip():
        return "context", "", context
    raise ValueError(f"{filename} returned an unsupported decision")


def run_gate(filename: str, tool_name: str, tool_input: dict, cwd: str,
             event: str = "PreToolUse") -> tuple:
    """Run one canonical gate and return its decision, reason, and context.

    A gate that denies reports the denial on standard error and exits with a
    nonzero code. That is a decision, so the adapter reads it as one. A gate
    that cannot run at all also fails closed.
    """
    gate = HOOKS / filename
    if not gate.is_file():
        raise ValueError(f"the canonical gate {filename} is absent")
    payload = {"hook_event_name": event, "tool_name": tool_name,
               "tool_input": tool_input, "cwd": cwd, "permission_mode": "default"}
    environment = dict(os.environ)
    environment["CLAUDE_PROJECT_DIR"] = cwd
    with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as diagnostic:
        result = subprocess.run(
            [sys.executable, "-E", "-s", str(gate)],
            input=json.dumps(payload).encode("utf-8"), env=environment,
            stdout=output, stderr=diagnostic, cwd=cwd,
            timeout=CHECK_TIMEOUT_SECONDS, check=False)
        output.seek(0)
        raw = output.read(MAX_OUTPUT_BYTES + 1)
        diagnostic.seek(0)
        errors = diagnostic.read(MAX_REASON_CHARACTERS * 8).decode("utf-8", "replace")
    if len(raw) > MAX_OUTPUT_BYTES:
        raise ValueError("the canonical gate response exceeds the inspection bound")
    text = raw.decode("utf-8", "replace").strip()
    if not text:
        if result.returncode:
            return "deny", errors.strip() or f"{filename} failed validation", ""
        return "allow", "", ""
    try:
        verdict = json.loads(text)
    except ValueError as error:
        raise ValueError(f"{filename} returned a response that cannot be read") from error
    if not isinstance(verdict, dict):
        raise ValueError(f"{filename} returned a response that is not an object")
    return read_decision(verdict, filename, result.returncode, errors)


def check_adoption() -> str:
    """Return a bounded reason when the adopted gate set is incomplete."""
    if not ADOPTION_CHECKER.is_file():
        return "the gate-adoption checker is missing"
    try:
        result = subprocess.run(
            [sys.executable, "-E", "-s", str(ADOPTION_CHECKER), "--root", str(ROOT)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=CHECK_TIMEOUT_SECONDS, check=False)
    except (OSError, subprocess.SubprocessError) as error:
        return f"the gate-adoption checker failed: {bounded_reason(str(error))}"
    if result.returncode == 0:
        return ""
    return bounded_reason(result.stderr.strip() or "the gate-adoption checker rejected the set")


def inspect_tool(tool: str, arguments: dict, cwd: str) -> tuple:
    """Return the decision and reason for one pi tool call."""
    mapping = TOOL_GATES.get(tool)
    if mapping is None:
        return "deny", f"the tool {tool} has no canonical inspection path"
    canonical_tool, gates = mapping
    failure = check_adoption()
    if failure and tool not in READ_ONLY_TOOLS:
        return "deny", failure
    tool_input = canonical_input(tool, arguments)
    decision, reason, _context = run_gate(BRANCH_GATE, canonical_tool, tool_input, cwd)
    if decision == "deny":
        return "deny", reason
    if tool in SHELL_TOOLS:
        decision, reason, _context = run_gate(IDENTITY_GATE, canonical_tool, tool_input, cwd)
        if decision == "deny":
            return "deny", reason
    for gate in gates:
        decision, reason, _context = run_gate(gate, canonical_tool, tool_input, cwd)
        if decision == "deny":
            return "deny", reason
    return "allow", ""


def inspect_session(cwd: str) -> tuple:
    """Return the decision, reason, context, and warning for one session start."""
    failure = check_adoption()
    if failure:
        return "deny", failure, "", ""
    decision, reason, context = run_gate(BRANCH_GATE, "Bash", {}, cwd, event="SessionStart")
    if decision == "deny":
        return "deny", reason, context, ""
    if decision == "context":
        return ("deny",
                "the branch preflight failed, so ordinary actions stay blocked "
                "until a compliant branch is checked out",
                context, "")
    decision, reason, context = run_gate(IDENTITY_GATE, "Bash", {}, cwd, event="SessionStart")
    if decision == "deny":
        return "deny", reason, context, ""
    warning = context if decision == "context" else ""
    return "allow", "", "", warning


def main() -> int:
    """Decide one pi request and report the result."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", choices=("tool", "session"), default="tool")
    options = parser.parse_args()
    try:
        request = read_request()
        cwd = session_directory(request.get("cwd"))
        if options.event == "session":
            decision, reason, context, warning = inspect_session(cwd)
            return emit(decision, reason, context, warning)
        tool = request.get("tool")
        arguments = request.get("arguments")
        if not isinstance(tool, str) or not tool.strip():
            raise ValueError("the tool name is missing or malformed")
        if not isinstance(arguments, dict):
            raise ValueError("the tool arguments are missing or malformed")
        decision, reason = inspect_tool(tool, arguments, cwd)
        return emit(decision, reason)
    except (ValueError, OSError, subprocess.SubprocessError, UnicodeError) as error:
        return emit("deny", str(error))


if __name__ == "__main__":
    raise SystemExit(main())
