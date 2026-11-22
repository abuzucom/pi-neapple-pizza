#!/usr/bin/env python3
"""Decide pi tool calls outside the repository and record every decision.

The broker owns three things that a repository cannot hold safely.

The pin records the digest of every gate file the decision path runs and of
the broker itself. A gate that changed after the pin was written fails the
decision, so an edit to a gate in the working tree loses the decision until a
person pins the change again.

The audit log records every decision as an appended line that carries the
digest of the line before it. A record that was changed, removed, or
reordered breaks the chain, and the broker reports the break.

The approval store records one approval per act. An approval binds the
digest of the request it covers, and the broker consumes it once. A decision
that needs an answer from a human carries the ask to the caller, and the
caller returns an approval that the broker consumed.

The state directory lives outside the repository, so the tools that reach the
repository cannot reach the pin, the log, or the approvals. The operating
system boundary that keeps an agent out of the state directory belongs to the
sandbox work and is not in place yet.

Commands:

    pin      record the current digests of the decision path
    decide   read one request on standard input and answer it
    approve  record one approval for a request that a human accepted
    status   report the pin, the approvals, and the log
"""
import argparse
import hashlib
import json
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOKS = ROOT / "hooks"
SHARED_MANIFEST = ROOT / "shared-files.json"
BROKER = Path(__file__).resolve()
ADAPTER = HOOKS / "pi_client_gate.py"
MAX_REQUEST_BYTES = 65536
MAX_REASON_CHARACTERS = 512
MAX_CONTEXT_CHARACTERS = 8192
MAX_AUDIT_LINE_BYTES = 65536
MAX_APPROVAL_RECORDS = 4096
PIN_VERSION = 1


def state_directory() -> Path:
    """Return the state directory that holds the pin, the log, and approvals."""
    override = os.environ.get("PI_BROKER_STATE", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA", "").strip()
        if base:
            return Path(base) / "pi-neapple-pizza-broker"
        return Path.home() / "AppData" / "Local" / "pi-neapple-pizza-broker"
    base = os.environ.get("XDG_STATE_HOME", "").strip()
    if base:
        return Path(base) / "pi-neapple-pizza-broker"
    return Path.home() / ".local" / "state" / "pi-neapple-pizza-broker"


def normalized_digest(path: Path) -> str:
    """Return the digest of a file with the line endings normalized."""
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def decision_path_files() -> list:
    """Return the files the decision path runs, with their digests."""
    digests = {}
    for path in sorted(HOOKS.glob("*.py")):
        digests[f"hooks/{path.name}"] = normalized_digest(path)
    digests["broker/pi_broker.py"] = normalized_digest(BROKER)
    client = ROOT / "integrations" / "pi" / "agents-gate.ts"
    if client.is_file():
        digests["integrations/pi/agents-gate.ts"] = normalized_digest(client)
    return digests


def shared_manifest_digests() -> dict:
    """Return the recorded digests of the shared files."""
    if not SHARED_MANIFEST.is_file():
        return {}
    try:
        document = json.loads(SHARED_MANIFEST.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    shared = document.get("shared")
    return shared if isinstance(shared, dict) else {}


def pin_path(directory: Path) -> Path:
    """Return the path of the pin file."""
    return directory / "pin.json"


def log_path(directory: Path) -> Path:
    """Return the path of the audit log."""
    return directory / "decisions.jsonl"


def approvals_path(directory: Path) -> Path:
    """Return the path of the approval store."""
    return directory / "approvals.jsonl"


def request_digest(request: dict) -> str:
    """Return the digest of one request."""
    canonical = json.dumps(request, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def line_digest(record: dict, previous: str) -> str:
    """Return the digest of one audit line and the line before it."""
    body = dict(record)
    body["previous"] = previous
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def read_pin(directory: Path) -> dict:
    """Return the recorded pin, or an empty mapping when none exists."""
    path = pin_path(directory)
    if not path.is_file():
        return {}
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return document if isinstance(document, dict) else {}


def write_pin(directory: Path) -> int:
    """Record the current digests of the decision path."""
    directory.mkdir(parents=True, exist_ok=True)
    digests = decision_path_files()
    manifest = shared_manifest_digests()
    mismatched = sorted(
        name for name, digest in manifest.items()
        if name in digests and digests[name] != digest)
    document = {
        "version": PIN_VERSION,
        "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "digests": digests,
        "shared": manifest,
        "shared_mismatched": mismatched,
    }
    pin_path(directory).write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"pinned": len(digests), "shared": len(manifest),
                      "shared_mismatched": mismatched}))
    return 0


def verify_pin(directory: Path) -> str:
    """Return a reason when the decision path no longer matches the pin."""
    pin = read_pin(directory)
    if not pin:
        return ("the broker holds no pin, so an operator must run the pin "
                "command before the broker decides a call")
    recorded = pin.get("digests")
    if not isinstance(recorded, dict) or not recorded:
        return "the recorded pin holds no digests"
    current = decision_path_files()
    for name in sorted(recorded):
        expected = recorded[name]
        actual = current.get(name)
        if actual is None:
            return f"the pinned file {name} is absent from the decision path"
        if actual != expected:
            return (f"the pinned file {name} changed after the pin, so the "
                    "decision fails closed")
    manifest = shared_manifest_digests()
    for name, digest in manifest.items():
        actual = current.get(name)
        if actual is not None and actual != digest:
            return (f"the shared file {name} no longer matches the shared "
                    "manifest")
    return ""


def read_request() -> dict:
    """Return the request read from standard input."""
    raw = sys.stdin.read(MAX_REQUEST_BYTES + 1)
    if len(raw) > MAX_REQUEST_BYTES:
        raise ValueError("the request exceeds the inspection bound")
    try:
        request = json.loads(raw)
    except ValueError as error:
        raise ValueError("the request is not valid JSON") from error
    if not isinstance(request, dict):
        raise ValueError("the request is not an object")
    return request


def validate_request(request: dict) -> dict:
    """Return the request with the fields the decision path needs."""
    tool = request.get("tool")
    arguments = request.get("arguments")
    cwd = request.get("cwd")
    if not isinstance(cwd, str) or not cwd:
        raise ValueError("the request names no session directory")
    if tool is None:
        return {"cwd": cwd}
    if not isinstance(tool, str) or not tool.strip():
        raise ValueError("the request names no tool")
    if not isinstance(arguments, dict):
        raise ValueError("the request carries no tool arguments")
    return {"tool": tool, "arguments": arguments, "cwd": cwd}


def load_adapter():
    """Return the adapter module that runs the canonical gates."""
    if str(HOOKS) not in sys.path:
        sys.path.insert(0, str(HOOKS))
    import importlib.util

    spec = importlib.util.spec_from_file_location("pi_client_gate", ADAPTER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def decide(request: dict) -> tuple:
    """Return the canonical decision, reason, and context for one request."""
    adapter = load_adapter()
    if "tool" not in request:
        decision, reason, context, warning = adapter.inspect_session(request["cwd"])
        return decision, reason, context, warning
    decision, reason = adapter.inspect_tool(
        request["tool"], request["arguments"], request["cwd"])
    context = ""
    if decision == "ask":
        context = reason
        reason = ("the act needs an answer from the active human, and the "
                  "broker holds no approval for it")
    return decision, reason, context, ""


def append_record(path: Path, record: dict) -> str:
    """Append one record to a file and return the digest of the line."""
    path.parent.mkdir(parents=True, exist_ok=True)
    previous = ""
    if path.is_file():
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    previous = json.loads(line).get("digest", "")
    body = dict(record)
    body["previous"] = previous
    digest = line_digest(body, previous)
    body["digest"] = digest
    line = json.dumps(body, sort_keys=True, separators=(",", ":"))
    if len(line) > MAX_AUDIT_LINE_BYTES:
        line = json.dumps({"time": body.get("time"), "decision": "deny",
                           "reason": "the audit record exceeds the line bound",
                           "previous": previous, "digest": digest},
                          sort_keys=True, separators=(",", ":"))
    with open(path, "a", encoding="utf-8", newline="\n") as handle:
        handle.write(line + "\n")
    return digest


def read_approvals(directory: Path) -> list:
    """Return the recorded approvals."""
    path = approvals_path(directory)
    if not path.is_file():
        return []
    records = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    return records[-MAX_APPROVAL_RECORDS:]


def record_approval(directory: Path, request: dict) -> int:
    """Record one approval for a request that a human accepted."""
    validated = validate_request(request)
    token = secrets.token_hex(32)
    record = {
        "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "request": request_digest(validated),
        "token": token,
    }
    directory.mkdir(parents=True, exist_ok=True)
    append_record(approvals_path(directory), record)
    print(json.dumps({"approval": token, "request": record["request"]}))
    return 0


def consume_approval(directory: Path, digest: str, token: str) -> bool:
    """Return whether a matching approval was consumed for one request."""
    for record in read_approvals(directory):
        if record.get("token") != token:
            continue
        if record.get("request") != digest:
            return False
        append_record(approvals_path(directory), {
            "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "request": digest,
            "token": token,
            "consumed": True,
        })
        return True
    return False


def decide_command(request: dict) -> int:
    """Answer one request and record the decision."""
    directory = state_directory()
    failure = verify_pin(directory)
    validated = validate_request(request)
    digest = request_digest(validated)
    token = request.get("approval")
    consumed = False
    if isinstance(token, str) and token:
        consumed = consume_approval(directory, digest, token)
    if failure:
        decision, reason, context, warning = "deny", failure, "", ""
    else:
        decision, reason, context, warning = decide(validated)
        if decision == "ask" and consumed:
            decision = "allow"
            reason = ""
            context = ""
    record = {
        "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "request": digest,
        "tool": validated.get("tool", "session"),
        "decision": decision,
        "reason": reason[:MAX_REASON_CHARACTERS],
        "approval": consumed,
    }
    append_record(log_path(directory), record)
    print(json.dumps({"decision": decision, "reason": reason[:MAX_REASON_CHARACTERS],
                      "context": context[:MAX_CONTEXT_CHARACTERS],
                      "warning": warning[:MAX_CONTEXT_CHARACTERS],
                      "record": record["request"]}))
    return 0 if decision in ("allow", "ask") else 2


def status_command() -> int:
    """Report the pin, the approvals, and the audit log."""
    directory = state_directory()
    pin = read_pin(directory)
    failure = verify_pin(directory)
    approvals = read_approvals(directory)
    pending = [record for record in approvals if not record.get("consumed")]
    lines = 0
    if log_path(directory).is_file():
        with open(log_path(directory), "r", encoding="utf-8") as handle:
            lines = sum(1 for line in handle if line.strip())
    print(json.dumps({
        "state": str(directory),
        "pinned": bool(pin),
        "pin_failure": failure,
        "approvals": len(approvals),
        "pending_approvals": len(pending),
        "records": lines,
    }))
    return 0


def main() -> int:
    """Run one broker command."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("pin")
    commands.add_parser("decide")
    commands.add_parser("approve")
    commands.add_parser("status")
    options = parser.parse_args()
    try:
        if options.command == "pin":
            return write_pin(state_directory())
        if options.command == "approve":
            return record_approval(state_directory(), read_request())
        if options.command == "status":
            return status_command()
        return decide_command(read_request())
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        reason = " ".join(str(error).splitlines())
        print(json.dumps({"decision": "deny", "reason": reason[:MAX_REASON_CHARACTERS]}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
