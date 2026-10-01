#!/usr/bin/env python3
"""Require external approval for pull requests that alter gate enforcement."""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

APPROVAL_LABEL = "gate-change-approved"
MAX_LABEL_BYTES = 4096
SHA_PATTERN = re.compile(r"[0-9a-f]{40,64}")
PROTECTED_PREFIXES = (
    "hooks/",
    ".claude/",
    ".codex/",
    ".agents/",
    ".gemini/",
    ".github/workflows/",
)
PROTECTED_FILES = frozenset({
    "shared-files.json",
    "scripts/check_gate_adoption.py",
    "scripts/check_gate_pr_integrity.py",
    "scripts/check_hook_coverage.py",
    "scripts/check_hook_launchers.py",
    "scripts/sync.py",
})
FETCH_TIMEOUT_SECONDS = 30
GIT_TIMEOUT_SECONDS = 10


def requires_approval(paths: list[str]) -> bool:
    """Return whether changed paths reach gate-enforcement surfaces."""
    return any(
        path in PROTECTED_FILES or path.startswith(PROTECTED_PREFIXES)
        for path in paths
    )


def has_approval_label(labels: list[str]) -> bool:
    """Return whether trusted pull-request metadata contains the exact label."""
    return APPROVAL_LABEL in labels


def _revision(value: str) -> str:
    """Validate one immutable Git object identifier."""
    if not SHA_PATTERN.fullmatch(value):
        raise ValueError("revision must be a 40 to 64 character lowercase SHA")
    return value


def _labels(value: str) -> list[str]:
    """Parse bounded pull-request labels as untrusted JSON data."""
    if len(value.encode("utf-8")) > MAX_LABEL_BYTES:
        raise ValueError("label data exceeds the size limit")
    parsed = json.loads(value)
    if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
        raise ValueError("label data must be a JSON string list")
    return parsed


def _run(command: list[str], root: Path, timeout: int) -> subprocess.CompletedProcess:
    """Run one fixed argument-array command with bounded text output."""
    return subprocess.run(
        command,
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def _fetch_head(root: Path, number: int) -> None:
    """Fetch one validated pull-request head through the trusted Git wrapper."""
    wrapper = root / "scripts" / "trusted_git.py"
    refspec = f"refs/pull/{number}/head"
    result = _run(
        [sys.executable, "-E", "-s", str(wrapper), "fetch", ".", "origin", refspec],
        root,
        FETCH_TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        raise RuntimeError("trusted fetch of the pull-request head failed")


def _has_revision(root: Path, revision: str) -> bool:
    """Return whether one validated commit already exists locally."""
    result = _run(
        ["git", "cat-file", "-e", f"{revision}^{{commit}}"],
        root,
        GIT_TIMEOUT_SECONDS,
    )
    return result.returncode == 0


def _changed_paths(root: Path, base: str, head: str) -> list[str]:
    """Return validated repository-relative paths changed by one pull request."""
    result = _run(
        ["git", "diff", "--name-only", "--no-renames", base, head],
        root,
        GIT_TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        raise RuntimeError("Git could not list pull-request changes")
    paths = [line for line in result.stdout.splitlines() if line]
    if any("\\" in path or path.startswith("/") or ".." in Path(path).parts for path in paths):
        raise ValueError("changed path is not a safe repository-relative path")
    return paths


def main(argv: list[str]) -> int:
    """Fail unapproved protected changes using trusted base-branch code."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--pr-number", required=True, type=int)
    parser.add_argument("--labels-json", required=True)
    options = parser.parse_args(argv)
    try:
        base = _revision(options.base)
        head = _revision(options.head)
        if options.pr_number < 1:
            raise ValueError("pull-request number must be positive")
        labels = _labels(options.labels_json)
        root = Path.cwd().resolve(strict=True)
        if not _has_revision(root, head):
            _fetch_head(root, options.pr_number)
        paths = _changed_paths(root, base, head)
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
        print(f"gate integrity check failed: {error}", file=sys.stderr)
        return 1
    if requires_approval(paths) and not has_approval_label(labels):
        print(
            f"protected gate changes require the {APPROVAL_LABEL} label",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
