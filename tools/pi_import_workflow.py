#!/usr/bin/env python3
"""Run trusted orchestration steps for the manual pi import workflow."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any


SOURCE_URL = "https://github.com/abuzucom/pi.git"
FULL_SHA = re.compile(r"[0-9a-f]{40}")
SAFE_REF = re.compile(r"(?:refs/(?:heads|tags)/)?[A-Za-z0-9][A-Za-z0-9._/-]{0,254}")
BRANCH_PREFIX = "chore/import-pi-update-"
MAX_PR_BODY_BYTES = 65_536
PROTECTED_ROOTS = frozenset(
    {".agents", ".claude", ".codex", ".gemini", ".github", "hooks", "plan", "tests", "tools"}
)
PROTECTED_FILES = frozenset(
    {"AGENTS.md", "CLAUDE.md", "GEMINI.md", "shared-files.json"}
)


class WorkflowFailure(RuntimeError):
    """Report one fail-closed workflow condition."""


def run(arguments: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run one argument-array command and capture UTF-8 output."""
    return subprocess.run(arguments, check=check, capture_output=True, text=True, encoding="utf-8", errors="replace")


def load_receipt_sha(workspace: Path) -> str | None:
    """Read the validated completed donor revision when present."""
    receipt_path = workspace / "docs" / "pi-import.json"
    if not receipt_path.exists():
        return None
    value = json.loads(receipt_path.read_text(encoding="utf-8"))
    source_sha = value.get("sourceSha") if isinstance(value, dict) else None
    if not isinstance(source_sha, str) or FULL_SHA.fullmatch(source_sha) is None:
        raise WorkflowFailure("completed import receipt contains an invalid source SHA")
    return source_sha


def validate_ref(value: str, mode: str) -> str:
    """Validate one donor ref before passing it to Git."""
    if mode == "apply":
        if FULL_SHA.fullmatch(value) is None:
            raise WorkflowFailure("apply mode requires a full lowercase commit SHA")
        return value
    if SAFE_REF.fullmatch(value) is None:
        raise WorkflowFailure("preview source ref contains unsupported characters")
    forbidden = ("..", "@{", "//")
    if any(token in value for token in forbidden) or value.endswith((".", ".lock")):
        raise WorkflowFailure("preview source ref has an unsafe Git ref shape")
    return value


def fetch_source(workspace: Path, source_ref: str, mode: str) -> str:
    """Fetch and resolve one donor target without merging donor history."""
    validated = validate_ref(source_ref, mode)
    run(["git", "fetch", "--no-tags", SOURCE_URL, validated])
    resolved = run(["git", "rev-parse", "--verify", "FETCH_HEAD^{commit}"]).stdout.strip().lower()
    if FULL_SHA.fullmatch(resolved) is None:
        raise WorkflowFailure("Git returned an invalid donor commit SHA")
    if mode == "apply" and resolved != validated:
        raise WorkflowFailure("fetched donor commit differs from the approved SHA")
    base_sha = load_receipt_sha(workspace)
    if base_sha is not None and base_sha != resolved:
        run(["git", "fetch", "--no-tags", SOURCE_URL, base_sha])
    return resolved


def write_output(name: str, value: str) -> None:
    """Write one validated scalar to the GitHub output file."""
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path is None:
        print(f"{name}={value}")
        return
    with Path(output_path).open("a", encoding="utf-8", newline="\n") as output:
        output.write(f"{name}={value}\n")


def importer_arguments(mode: str, source_sha: str, workspace: Path, report_directory: Path) -> list[str]:
    """Build the fixed importer argument array from validated values."""
    arguments = [
        sys.executable,
        "tools/import_pi_upstream.py",
        mode,
        "--source-sha",
        source_sha,
        "--workspace",
        str(workspace),
        "--report-directory",
        str(report_directory),
    ]
    if mode == "apply":
        arguments.extend(["--import-approval-digest", os.environ.get("IMPORT_APPROVAL_DIGEST", "")])
        dependency_digest = os.environ.get("DEPENDENCY_APPROVAL_DIGEST", "")
        test_digest = os.environ.get("TEST_CHANGE_APPROVAL_DIGEST", "")
        if dependency_digest:
            arguments.extend(["--dependency-approval-digest", dependency_digest])
        if test_digest:
            arguments.extend(["--test-change-approval-digest", test_digest])
    return arguments


def run_import(mode: str, workspace: Path, report_directory: Path) -> None:
    """Resolve the donor ref and run preview or apply."""
    source_ref = os.environ.get("SOURCE_REF", "")
    source_sha = fetch_source(workspace, source_ref, mode)
    result = run(importer_arguments(mode, source_sha, workspace, report_directory), check=False)
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    if result.returncode != 0:
        raise WorkflowFailure(f"importer exited with status {result.returncode}")
    write_output("source_sha", source_sha)


def validate_changed_path(path: str) -> str:
    """Reject unsafe and policy-owned paths before workflow publication."""
    normalized = PurePosixPath(path.replace("\\", "/"))
    if normalized.is_absolute() or any(part in {"", ".", ".."} for part in normalized.parts):
        raise WorkflowFailure("Git reported an unsafe changed path")
    value = normalized.as_posix()
    if normalized.parts[0] in PROTECTED_ROOTS or value in PROTECTED_FILES:
        raise WorkflowFailure(f"import changed protected policy path: {value}")
    return value


def changed_paths() -> list[str]:
    """Read and validate changed paths through one NUL-delimited Git call."""
    result = subprocess.run(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        check=True,
        capture_output=True,
    )
    records = result.stdout.split(b"\0")
    paths: list[str] = []
    for record in records:
        if not record:
            continue
        if len(record) < 4:
            raise WorkflowFailure("Git returned malformed status output")
        raw_path = record[3:]
        try:
            paths.append(validate_changed_path(raw_path.decode("utf-8")))
        except UnicodeDecodeError as error:
            raise WorkflowFailure("Git returned a non-UTF-8 changed path") from error
    return sorted(set(paths))


def verified_identity() -> tuple[str, str]:
    """Resolve the triggering account through the trusted GitHub wrapper."""
    result = run([sys.executable, "scripts/trusted_gh.py", "run", "api", "user"])
    value: Any = json.loads(result.stdout)
    login = value.get("login") if isinstance(value, dict) else None
    account_id = value.get("id") if isinstance(value, dict) else None
    if not isinstance(login, str) or not login or not isinstance(account_id, int) or account_id <= 0:
        raise WorkflowFailure("trusted GitHub identity response is invalid")
    actor = os.environ.get("GITHUB_ACTOR", "")
    if not actor or actor.casefold() != login.casefold():
        raise WorkflowFailure("trusted GitHub account differs from the workflow triggering account")
    return login, f"{account_id}+{login}@users.noreply.github.com"


def branch_name() -> str:
    """Return the dated import branch name."""
    return f"{BRANCH_PREFIX}{dt.datetime.now(dt.timezone.utc).date().isoformat()}"


def commit_groups(paths: list[str]) -> list[tuple[str, list[str]]]:
    """Group imported files by package and keep receipt documents last."""
    packages: dict[str, list[str]] = {}
    scripts: list[str] = []
    roots: list[str] = []
    docs: list[str] = []
    for path in paths:
        parts = PurePosixPath(path).parts
        if parts[0] == "packages" and len(parts) > 1:
            packages.setdefault(parts[1], []).append(path)
        elif parts[0] == "scripts":
            scripts.append(path)
        elif parts[0] == "docs" or path == "DRIFT.md":
            docs.append(path)
        else:
            roots.append(path)
    groups = [(f"chore: import {name} package", values) for name, values in sorted(packages.items())]
    if scripts:
        groups.append(("chore: import pi scripts", scripts))
    if roots:
        groups.append(("chore: update pi workspace", roots))
    if docs:
        groups.append(("docs: record pi import", docs))
    return groups


def existing_pr_location(branch: str) -> str:
    """Return one existing pull request location for a colliding branch."""
    existing = run(
        [
            sys.executable,
            "scripts/trusted_gh.py",
            "run",
            "pr",
            "list",
            "--state",
            "all",
            "--head",
            branch,
            "--json",
            "url",
            "--limit",
            "1",
        ],
        check=False,
    )
    if existing.returncode != 0:
        return ""
    listed: Any = json.loads(existing.stdout)
    if not isinstance(listed, list) or not listed or not isinstance(listed[0], dict):
        return ""
    url = listed[0].get("url")
    return f" at {url}" if isinstance(url, str) else ""


def require_available_branch(branch: str) -> None:
    """Reject a generated branch that already exists on the remote."""
    collision = run(["git", "ls-remote", "--exit-code", "--heads", "origin", f"refs/heads/{branch}"], check=False)
    if collision.returncode == 0:
        raise WorkflowFailure(f"import branch already exists{existing_pr_location(branch)}: {branch}")
    if collision.returncode not in {2}:
        raise WorkflowFailure("cannot verify the remote import branch")


def require_unreplayed_digest(report_directory: Path) -> None:
    """Reject an import digest that already appears in a pull request body."""
    report = json.loads((report_directory / "import-report.json").read_text(encoding="utf-8"))
    digests = report.get("approvalDigests") if isinstance(report, dict) else None
    digest = digests.get("import") if isinstance(digests, dict) else None
    if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise WorkflowFailure("import report contains an invalid approval digest")
    existing = run(
        [
            sys.executable,
            "scripts/trusted_gh.py",
            "run",
            "pr",
            "list",
            "--state",
            "all",
            "--search",
            f"{digest} in:body",
            "--json",
            "url",
            "--limit",
            "1",
        ]
    )
    listed: Any = json.loads(existing.stdout)
    if isinstance(listed, list) and listed and isinstance(listed[0], dict):
        url = listed[0].get("url")
        location = f" at {url}" if isinstance(url, str) else ""
        raise WorkflowFailure(f"import approval digest was already published{location}")


def commit_import(paths: list[str], branch: str) -> None:
    """Create the generated branch and package-scoped commits."""
    login, email = verified_identity()
    run(["git", "config", "--local", "user.name", login])
    run(["git", "config", "--local", "user.email", email])
    run(["git", "switch", "-c", branch])
    for subject, group_paths in commit_groups(paths):
        run(["git", "add", "--", *group_paths])
        run(["git", "commit", "-m", subject])
    run(["git", "push", "origin", branch])


def pull_request_body(report_directory: Path) -> str:
    """Build one bounded draft pull request description."""
    report = json.loads((report_directory / "import-report.json").read_text(encoding="utf-8"))
    conflicts = report.get("conflicts", []) if isinstance(report, dict) else []
    validation_path = report_directory / "product-validation.json"
    validation = json.loads(validation_path.read_text(encoding="utf-8")) if validation_path.exists() else {}
    failures = validation.get("failures", []) if isinstance(validation, dict) else []
    body_lines = [
        "Imports the approved pi donor revision through the bounded importer.",
        "",
        f"Source SHA: `{report.get('sourceSha', 'unknown')}`",
        f"Import digest: `{report.get('approvalDigests', {}).get('import', 'unknown')}`",
        f"Conflict count: {len(conflicts)}",
        f"Product validation failures: {len(failures)}",
    ]
    if conflicts:
        body_lines.extend(["", "Conflicts:", *[f"- `{path}`" for path in conflicts]])
    if failures:
        body_lines.extend(["", "Product validation failures:", *[f"- `{name}`" for name in failures]])
    body = "\n".join(body_lines) + "\n"
    if len(body.encode("utf-8")) > MAX_PR_BODY_BYTES:
        raise WorkflowFailure("draft pull request body exceeds its byte bound")

    return body


def create_draft_pr(report_directory: Path, branch: str, body: str) -> None:
    """Create one draft pull request through the trusted GitHub wrapper."""
    body_path = report_directory / "pull-request-body.md"
    body_path.write_text(body, encoding="ascii", newline="\n")
    title = f"chore: import pi update {branch.removeprefix(BRANCH_PREFIX)}"
    result = run(
        [
            sys.executable,
            "scripts/trusted_gh.py",
            "run",
            "pr",
            "create",
            "--draft",
            "--base",
            "main",
            "--head",
            branch,
            "--title",
            title,
            "--body-file",
            str(body_path),
        ]
    )
    print(result.stdout.strip())


def publish(report_directory: Path) -> None:
    """Create package commits and one draft pull request."""
    paths = changed_paths()
    if not paths:
        raise WorkflowFailure("approved import produced no repository changes")
    branch = branch_name()
    require_available_branch(branch)
    require_unreplayed_digest(report_directory)
    body = pull_request_body(report_directory)
    commit_import(paths, branch)
    create_draft_pr(report_directory, branch, body)


def parse_arguments() -> argparse.Namespace:
    """Parse one fixed workflow phase."""
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("preview", "apply", "publish"))
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--report-directory", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    """Run one import workflow phase."""
    arguments = parse_arguments()
    try:
        workspace = arguments.workspace.resolve()
        report_directory = arguments.report_directory.resolve()
        report_directory.mkdir(parents=True, exist_ok=True)
        if arguments.phase in {"preview", "apply"}:
            run_import(arguments.phase, workspace, report_directory)
        else:
            publish(report_directory)
        return 0
    except (WorkflowFailure, OSError, subprocess.SubprocessError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
