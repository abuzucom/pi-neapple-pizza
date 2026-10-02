#!/usr/bin/env python3
"""Run trusted orchestration steps for the manual pi import workflow."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any


SOURCE_URL = "https://github.com/abuzucom/pi.git"
PUBLICATION_ORIGIN = "https://github.com/abuzucom/pi-neapple-pizza.git"
FULL_SHA = re.compile(r"[0-9a-f]{40}")
SAFE_REF = re.compile(r"(?:refs/(?:heads|tags)/)?[A-Za-z0-9][A-Za-z0-9._/-]{0,254}")
BRANCH_PREFIX = "chore/import-pi-update-"
MAX_PR_BODY_BYTES = 65_536
MAX_CANDIDATE_PATCH_BYTES = 536_870_912
MAX_CANDIDATE_REPORT_BYTES = 5_242_880
MAX_CANDIDATE_CHANGED_FILES = 5_000
MAX_CANDIDATE_TOTAL_BYTES = 536_870_912
MAX_CANDIDATE_FILE_BYTES = 52_428_800
MAX_COMMAND_PATHS = 100
STREAM_CHUNK_BYTES = 1_048_576
CANDIDATE_FILES = frozenset(
    {"candidate.patch", "manifest.json", "import-report.json", "approval-digests.json"}
)
WEAK_HASH_SUFFIXES = frozenset(
    {".c", ".cc", ".cpp", ".go", ".java", ".js", ".jsx", ".mjs", ".py", ".pyw", ".rs", ".ts", ".tsx"}
)
PROTECTED_ROOTS = frozenset(
    {".agents", ".claude", ".codex", ".gemini", ".git", ".github", "hooks", "plan", "tests", "tools"}
)
PROTECTED_FILES = frozenset(
    {"AGENTS.md", "CLAUDE.md", "GEMINI.md", "shared-files.json"}
)
PROTECTED_ROOT_KEYS = frozenset(value.casefold() for value in PROTECTED_ROOTS)
PROTECTED_FILE_KEYS = frozenset(value.casefold() for value in PROTECTED_FILES)


class WorkflowFailure(RuntimeError):
    """Report one fail-closed workflow condition."""


def run(
    arguments: list[str],
    *,
    check: bool = True,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run one argument-array command and capture UTF-8 output."""
    return subprocess.run(
        arguments,
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=cwd,
        env=env,
    )


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
    run(["git", "fetch", "--no-tags", SOURCE_URL, validated], cwd=workspace)
    resolved = run(
        ["git", "rev-parse", "--verify", "FETCH_HEAD^{commit}"],
        cwd=workspace,
    ).stdout.strip().lower()
    if FULL_SHA.fullmatch(resolved) is None:
        raise WorkflowFailure("Git returned an invalid donor commit SHA")
    if mode == "apply" and resolved != validated:
        raise WorkflowFailure("fetched donor commit differs from the approved SHA")
    base_sha = load_receipt_sha(workspace)
    if base_sha is not None and base_sha != resolved:
        run(["git", "fetch", "--no-tags", SOURCE_URL, base_sha], cwd=workspace)
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
    if any(ord(character) < 32 or ord(character) == 127 for character in path):
        raise WorkflowFailure("Git reported an unsafe changed path")
    normalized = PurePosixPath(path.replace("\\", "/"))
    if normalized.is_absolute() or any(part in {"", ".", ".."} for part in normalized.parts):
        raise WorkflowFailure("Git reported an unsafe changed path")
    value = normalized.as_posix()
    if normalized.parts[0].casefold() in PROTECTED_ROOT_KEYS or value.casefold() in PROTECTED_FILE_KEYS:
        raise WorkflowFailure(f"import changed protected policy path: {value}")
    if normalized.parts[0].casefold() == "scripts" and normalized.suffix.casefold() == ".py":
        raise WorkflowFailure(f"candidate bundle contains donor Python under scripts: {value}")
    return value


def changed_paths(workspace: Path | None = None) -> list[str]:
    """Read and validate changed paths through one NUL-delimited Git call."""
    result = subprocess.run(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        check=True,
        capture_output=True,
        cwd=workspace,
    )
    return sorted(set(parse_porcelain_paths(result.stdout)))


def parse_porcelain_paths(output: bytes) -> list[str]:
    """Parse both paths from NUL-delimited rename and copy records."""
    records = output.split(b"\0")
    paths: list[str] = []
    index = 0
    while index < len(records):
        record = records[index]
        index += 1
        if not record:
            continue
        if len(record) < 4:
            raise WorkflowFailure("Git returned malformed status output")
        raw_paths = [record[3:]]
        if b"R" in record[:2] or b"C" in record[:2]:
            if index >= len(records) or not records[index]:
                raise WorkflowFailure("Git returned a truncated rename or copy record")
            raw_paths.append(records[index])
            index += 1
        for raw_path in raw_paths:
            try:
                paths.append(validate_changed_path(raw_path.decode("utf-8")))
            except UnicodeDecodeError as error:
                raise WorkflowFailure("Git returned a non-UTF-8 changed path") from error
    return paths


def sha256_file(path: Path, maximum_bytes: int) -> str:
    """Hash one bounded regular file without following links."""
    metadata = path.lstat()
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise WorkflowFailure(f"candidate bundle entry must be a regular file: {path.name}")
    if metadata.st_size > maximum_bytes:
        raise WorkflowFailure(f"candidate bundle entry exceeds its byte bound: {path.name}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1_048_576):
            digest.update(chunk)
    return digest.hexdigest()


def load_bundle_manifest(bundle_directory: Path) -> dict[str, Any]:
    """Load one bounded canonical candidate manifest."""
    manifest_path = bundle_directory / "manifest.json"
    sha256_file(manifest_path, MAX_CANDIDATE_REPORT_BYTES)
    raw = manifest_path.read_bytes()
    try:
        value: Any = json.loads(raw.decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise WorkflowFailure("candidate bundle manifest is not canonical JSON") from error
    canonical = json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode("ascii") + b"\n"
    if raw != canonical or not isinstance(value, dict) or value.get("schemaVersion") != 1:
        raise WorkflowFailure("candidate bundle manifest is not canonical JSON")
    return value


def verify_candidate_bundle(bundle_directory: Path, expected_base_sha: str) -> dict[str, Any]:
    """Verify every immutable candidate bundle boundary before use."""
    actual_names = {entry.name for entry in bundle_directory.iterdir()}
    if actual_names != CANDIDATE_FILES:
        raise WorkflowFailure("candidate bundle contains unexpected files")
    manifest = load_bundle_manifest(bundle_directory)
    if manifest.get("trustedBaseSha") != expected_base_sha:
        raise WorkflowFailure("candidate bundle trusted base SHA does not match checkout")
    if FULL_SHA.fullmatch(str(manifest.get("donorSha", ""))) is None:
        raise WorkflowFailure("candidate bundle donor SHA is invalid")
    changed = manifest.get("changedPaths")
    if not isinstance(changed, list) or not changed:
        raise WorkflowFailure("candidate bundle changed-path inventory is invalid")
    if len(changed) > MAX_CANDIDATE_CHANGED_FILES:
        raise WorkflowFailure("candidate exceeds the changed-file bound")
    validated_paths = [validate_changed_path(path) for path in changed if isinstance(path, str)]
    if len(validated_paths) != len(changed) or sorted(set(validated_paths)) != changed:
        raise WorkflowFailure("candidate bundle changed-path inventory is invalid")
    files = manifest.get("files")
    expected_payloads = CANDIDATE_FILES - {"manifest.json"}
    if not isinstance(files, dict) or set(files) != expected_payloads:
        raise WorkflowFailure("candidate bundle file inventory is invalid")
    for name in sorted(expected_payloads):
        maximum = MAX_CANDIDATE_PATCH_BYTES if name == "candidate.patch" else MAX_CANDIDATE_REPORT_BYTES
        if files.get(name) != sha256_file(bundle_directory / name, maximum):
            raise WorkflowFailure(f"candidate bundle digest mismatch: {name}")
    return manifest


def write_candidate_patch(workspace: Path, patch_path: Path) -> None:
    """Capture one binary Git patch without crossing the patch byte bound."""
    with tempfile.TemporaryFile() as error_stream:
        process = subprocess.Popen(
            ["git", "diff", "--cached", "--binary", "--full-index", "--no-ext-diff", "--no-textconv"],
            cwd=workspace,
            stdout=subprocess.PIPE,
            stderr=error_stream,
        )
        if process.stdout is None:
            process.kill()
            process.wait()
            raise WorkflowFailure("cannot open the candidate patch stream")
        try:
            captured = 0
            with patch_path.open("wb") as patch_stream:
                while True:
                    remaining = MAX_CANDIDATE_PATCH_BYTES + 1 - captured
                    chunk = process.stdout.read(min(STREAM_CHUNK_BYTES, remaining))
                    if not chunk:
                        break
                    patch_stream.write(chunk)
                    captured += len(chunk)
                    if captured > MAX_CANDIDATE_PATCH_BYTES:
                        raise WorkflowFailure("candidate patch exceeds its byte bound")
            return_code = process.wait()
            if return_code != 0:
                error_stream.seek(0)
                message = error_stream.read(MAX_CANDIDATE_REPORT_BYTES).decode("utf-8", errors="replace").strip()
                raise WorkflowFailure(f"cannot create candidate patch: {message}")
        finally:
            process.stdout.close()
            if process.poll() is None:
                process.kill()
                process.wait()


def create_candidate_bundle(workspace: Path, report_directory: Path, bundle_directory: Path) -> None:
    """Create one immutable patch and canonical manifest from the staged candidate."""
    paths = changed_paths(workspace)
    if not paths:
        raise WorkflowFailure("approved import produced no repository changes")
    validate_candidate_workspace(workspace, paths)
    for start in range(0, len(paths), MAX_COMMAND_PATHS):
        run(["git", "add", "-A", "--", *paths[start : start + MAX_COMMAND_PATHS]], cwd=workspace)
    bundle_directory.mkdir(parents=True, exist_ok=False)
    patch_path = bundle_directory / "candidate.patch"
    write_candidate_patch(workspace, patch_path)
    for name in ("import-report.json", "approval-digests.json"):
        shutil.copyfile(report_directory / name, bundle_directory / name)
    report: Any = json.loads((bundle_directory / "import-report.json").read_text(encoding="utf-8"))
    approvals: Any = json.loads((bundle_directory / "approval-digests.json").read_text(encoding="utf-8"))
    source_sha = report.get("sourceSha") if isinstance(report, dict) else None
    if not isinstance(approvals, dict) or FULL_SHA.fullmatch(str(source_sha)) is None:
        raise WorkflowFailure("candidate import reports contain invalid metadata")
    base_sha = run(["git", "rev-parse", "HEAD"], cwd=workspace).stdout.strip()
    manifest = {
        "schemaVersion": 1,
        "trustedBaseSha": base_sha,
        "donorSha": source_sha,
        "approvalDigests": {
            "import": approvals.get("import"),
            "dependencies": approvals.get("dependencies"),
            "tests": approvals.get("tests"),
        },
        "changedPaths": sorted(paths),
        "files": {
            name: sha256_file(
                bundle_directory / name,
                MAX_CANDIDATE_PATCH_BYTES if name == "candidate.patch" else MAX_CANDIDATE_REPORT_BYTES,
            )
            for name in sorted(CANDIDATE_FILES - {"manifest.json"})
        },
    }
    manifest_bytes = json.dumps(manifest, ensure_ascii=True, separators=(",", ":"), sort_keys=True) + "\n"
    (bundle_directory / "manifest.json").write_text(manifest_bytes, encoding="ascii", newline="\n")


def apply_candidate_bundle(workspace: Path, bundle_directory: Path) -> dict[str, Any]:
    """Verify and apply one immutable candidate patch to a clean trusted checkout."""
    base_sha = run(["git", "rev-parse", "HEAD"], cwd=workspace).stdout.strip()
    manifest = verify_candidate_bundle(bundle_directory, base_sha)
    run(["git", "apply", "--index", "--binary", str(bundle_directory / "candidate.patch")], cwd=workspace)
    validate_candidate_workspace(workspace, manifest["changedPaths"])
    if sorted(changed_paths(workspace)) != manifest["changedPaths"]:
        raise WorkflowFailure("applied candidate paths differ from the immutable manifest")
    return manifest


def validate_candidate_workspace(workspace: Path, paths: list[str]) -> None:
    """Reject unsafe candidate entries and enforce the importer byte limits."""
    if len(paths) > MAX_CANDIDATE_CHANGED_FILES:
        raise WorkflowFailure("candidate exceeds the changed-file bound")
    resolved_workspace = workspace.resolve()
    total_bytes = 0
    for path in paths:
        target = workspace.joinpath(*PurePosixPath(validate_changed_path(path)).parts)
        resolved_parent = target.parent.resolve()
        if resolved_parent != resolved_workspace and resolved_workspace not in resolved_parent.parents:
            raise WorkflowFailure(f"candidate path escapes the workspace: {path}")
        if not target.exists() and not target.is_symlink():
            continue
        metadata = target.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise WorkflowFailure(f"candidate path must be a regular file: {path}")
        if metadata.st_size > MAX_CANDIDATE_FILE_BYTES:
            raise WorkflowFailure(f"candidate violates the individual file byte bound: {path}")
        total_bytes += metadata.st_size
        if total_bytes > MAX_CANDIDATE_TOTAL_BYTES:
            raise WorkflowFailure("candidate violates the aggregate byte bound")


def require_candidate_approvals(bundle_directory: Path, manifest: dict[str, Any]) -> None:
    """Bind publication inputs to the immutable candidate reports."""
    report: Any = json.loads((bundle_directory / "import-report.json").read_text(encoding="utf-8"))
    approvals: Any = json.loads((bundle_directory / "approval-digests.json").read_text(encoding="utf-8"))
    if not isinstance(report, dict) or not isinstance(approvals, dict):
        raise WorkflowFailure("candidate approval reports must contain JSON objects")
    if report.get("sourceSha") != manifest.get("donorSha") or report.get("approvalDigests") != approvals:
        raise WorkflowFailure("candidate manifest does not match its approval reports")
    if manifest.get("approvalDigests") != {
        "import": approvals.get("import"),
        "dependencies": approvals.get("dependencies"),
        "tests": approvals.get("tests"),
    }:
        raise WorkflowFailure("candidate manifest approval digests do not match")
    required = {
        "IMPORT_APPROVAL_DIGEST": (True, approvals.get("import")),
        "DEPENDENCY_APPROVAL_DIGEST": (bool(report.get("dependencyChanges")), approvals.get("dependencies")),
        "TEST_CHANGE_APPROVAL_DIGEST": (bool(report.get("testChanges")), approvals.get("tests")),
    }
    for name, (is_required, expected) in required.items():
        supplied = os.environ.get(name, "")
        if is_required and supplied != expected:
            raise WorkflowFailure(f"candidate approval input does not match: {name}")


def prepare_candidate(workspace: Path, report_directory: Path, bundle_directory: Path) -> None:
    """Apply one approved import and seal its candidate bundle."""
    run_import("apply", workspace, report_directory)
    create_candidate_bundle(workspace, report_directory, bundle_directory)


def run_checker(arguments: list[str], workspace: Path) -> None:
    """Run one trusted checker through an argument array."""
    result = run([sys.executable, *arguments], check=False, cwd=workspace)
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    if result.returncode != 0:
        raise WorkflowFailure(f"trusted candidate checker failed: {arguments[0]}")


def check_candidate(workspace: Path, bundle_directory: Path) -> None:
    """Run trusted policy checks against explicit candidate files."""
    base_sha = run(["git", "rev-parse", "HEAD"], cwd=workspace).stdout.strip()
    manifest = verify_candidate_bundle(bundle_directory, base_sha)
    validate_candidate_workspace(workspace, manifest["changedPaths"])
    if sorted(changed_paths(workspace)) != manifest["changedPaths"]:
        raise WorkflowFailure("candidate workspace differs from the immutable manifest")
    for script_and_arguments in (
        ["scripts/check_gate_adoption.py"],
        ["scripts/sync.py", "--check"],
        ["scripts/check_hook_launchers.py"],
    ):
        run_checker(script_and_arguments, workspace)
    candidates = [workspace.joinpath(*PurePosixPath(path).parts) for path in manifest["changedPaths"]]
    regular_files = [path for path in candidates if path.is_file() and not path.is_symlink()]
    for start in range(0, len(regular_files), MAX_COMMAND_PATHS):
        batch = regular_files[start : start + MAX_COMMAND_PATHS]
        run_checker(["scripts/check_secrets_heuristic.py", *[str(path) for path in batch]], workspace)
    weak_hash_files = [path for path in regular_files if path.suffix.lower() in WEAK_HASH_SUFFIXES]
    for start in range(0, len(weak_hash_files), MAX_COMMAND_PATHS):
        batch = weak_hash_files[start : start + MAX_COMMAND_PATHS]
        run_checker(["scripts/check_weak_hashing.py", *[str(path) for path in batch]], workspace)


def restore_bundle_reports(bundle_directory: Path, report_directory: Path) -> None:
    """Copy immutable reports into a separate publication report directory."""
    report_directory.mkdir(parents=True, exist_ok=True)
    for name in ("import-report.json", "approval-digests.json"):
        shutil.copyfile(bundle_directory / name, report_directory / name)


def restore_validation_report(validation_directory: Path, report_directory: Path) -> None:
    """Copy one bounded validation summary into publication evidence."""
    source = validation_directory / "product-validation.json"
    sha256_file(source, MAX_CANDIDATE_REPORT_BYTES)
    value: Any = json.loads(source.read_text(encoding="utf-8"))
    failures = value.get("failures") if isinstance(value, dict) else None
    if not isinstance(failures, list) or any(not isinstance(item, str) for item in failures):
        raise WorkflowFailure("product validation summary is invalid")
    shutil.copyfile(source, report_directory / "product-validation.json")


def verified_identity(workspace: Path | None = None) -> tuple[str, str]:
    """Resolve the triggering account through the trusted GitHub wrapper."""
    result = run([sys.executable, "scripts/trusted_gh.py", "workflow", "actor"], cwd=workspace)
    value: Any = json.loads(result.stdout)
    login = value.get("login") if isinstance(value, dict) else None
    account_id = value.get("id") if isinstance(value, dict) else None
    if not isinstance(login, str) or not login or not isinstance(account_id, int) or account_id <= 0:
        raise WorkflowFailure("trusted GitHub identity response is invalid")
    actor = os.environ.get("GITHUB_TRIGGERING_ACTOR", "")
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


def existing_pr_location(branch: str, workspace: Path | None = None) -> str:
    """Return one existing pull request location for a colliding branch."""
    existing = run(
        [
            sys.executable,
            "scripts/trusted_gh.py",
            "workflow",
            "gh",
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
        cwd=workspace,
    )
    if existing.returncode != 0:
        return ""
    listed: Any = json.loads(existing.stdout)
    if not isinstance(listed, list) or not listed or not isinstance(listed[0], dict):
        return ""
    url = listed[0].get("url")
    return f" at {url}" if isinstance(url, str) else ""


def require_publication_origin(workspace: Path | None = None) -> None:
    """Require the exact current repository origin before hosted publication."""
    result = run(["git", "remote", "get-url", "origin"], check=False, cwd=workspace)
    if result.returncode != 0 or result.stdout.strip() != PUBLICATION_ORIGIN:
        raise WorkflowFailure("publication origin differs from the fixed current repository")


def require_available_branch(branch: str, workspace: Path | None = None) -> None:
    """Reject a generated branch that already exists on the remote."""
    require_publication_origin(workspace)
    collision = run(
        ["git", "ls-remote", "--exit-code", "--heads", "origin", f"refs/heads/{branch}"],
        check=False,
        cwd=workspace,
    )
    if collision.returncode == 0:
        raise WorkflowFailure(f"import branch already exists{existing_pr_location(branch, workspace)}: {branch}")
    if collision.returncode not in {2}:
        raise WorkflowFailure("cannot verify the remote import branch")


def require_unreplayed_digest(report_directory: Path, workspace: Path | None = None) -> None:
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
            "workflow",
            "gh",
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
        ],
        cwd=workspace,
    )
    listed: Any = json.loads(existing.stdout)
    if isinstance(listed, list) and listed and isinstance(listed[0], dict):
        url = listed[0].get("url")
        location = f" at {url}" if isinstance(url, str) else ""
        raise WorkflowFailure(f"import approval digest was already published{location}")


def commit_import(paths: list[str], branch: str, workspace: Path | None = None) -> None:
    """Create the generated branch and package-scoped commits."""
    login, email = verified_identity(workspace)
    run(["git", "config", "--local", "user.name", login], cwd=workspace)
    run(["git", "config", "--local", "user.email", email], cwd=workspace)
    run(["git", "switch", "-c", branch], cwd=workspace)
    for subject, group_paths in commit_groups(paths):
        run(["git", "add", "--", *group_paths], cwd=workspace)
        run(["git", "commit", "-m", subject], cwd=workspace)
    push_import_branch(branch, workspace)


def push_import_branch(branch: str, workspace: Path | None = None) -> None:
    """Push one generated branch with an ephemeral token askpass helper."""
    require_publication_origin(workspace)
    token = os.environ.get("GH_TOKEN", "")
    if not token:
        raise WorkflowFailure("publication token is unavailable")
    with tempfile.TemporaryDirectory(prefix="pi-import-askpass-") as temporary_directory:
        helper = Path(temporary_directory) / "askpass.py"
        helper.write_text(
            "#!/usr/bin/env python3\n"
            "import os\n"
            "import sys\n"
            "prompt = sys.argv[1] if len(sys.argv) > 1 else ''\n"
            "print('x-access-token' if prompt.startswith('Username') else os.environ['GH_TOKEN'])\n",
            encoding="ascii",
            newline="\n",
        )
        helper.chmod(0o700)
        environment = os.environ.copy()
        environment["GIT_ASKPASS"] = str(helper)
        environment["GIT_TERMINAL_PROMPT"] = "0"
        run(["git", "push", "origin", branch], cwd=workspace, env=environment)


def markdown_code(value: str) -> str:
    """Wrap one untrusted value in a non-conflicting Markdown code fence."""
    longest_run = 0
    current_run = 0
    for character in value:
        if character == "`":
            current_run += 1
            longest_run = max(longest_run, current_run)
        else:
            current_run = 0
    fence = "`" * (longest_run + 1)
    padding = " " if value.startswith("`") or value.endswith("`") else ""
    return f"{fence}{padding}{value}{padding}{fence}"


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
        body_lines.extend(["", "Conflicts:", *[f"- {markdown_code(path)}" for path in conflicts]])
    if failures:
        body_lines.extend(["", "Product validation failures:", *[f"- {markdown_code(name)}" for name in failures]])
    body = "\n".join(body_lines) + "\n"
    if len(body.encode("utf-8")) > MAX_PR_BODY_BYTES:
        raise WorkflowFailure("draft pull request body exceeds its byte bound")

    return body


def create_draft_pr(
    report_directory: Path,
    branch: str,
    body: str,
    workspace: Path | None = None,
) -> None:
    """Create one draft pull request through the trusted GitHub wrapper."""
    body_path = report_directory / "pull-request-body.md"
    body_path.write_text(body, encoding="ascii", newline="\n")
    title = f"chore: import pi update {branch.removeprefix(BRANCH_PREFIX)}"
    result = run(
        [
            sys.executable,
            "scripts/trusted_gh.py",
            "workflow",
            "gh",
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
        ],
        cwd=workspace,
    )
    print(result.stdout.strip())


def publish(report_directory: Path, workspace: Path | None = None) -> None:
    """Create package commits and one draft pull request."""
    paths = changed_paths(workspace)
    if not paths:
        raise WorkflowFailure("approved import produced no repository changes")
    branch = branch_name()
    require_available_branch(branch, workspace)
    require_unreplayed_digest(report_directory, workspace)
    body = pull_request_body(report_directory)
    commit_import(paths, branch, workspace)
    create_draft_pr(report_directory, branch, body, workspace)


def parse_arguments() -> argparse.Namespace:
    """Parse one fixed workflow phase."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "phase",
        choices=(
            "preview",
            "apply",
            "publish",
            "prepare-apply",
            "check-candidate",
            "validate-apply",
            "publish-apply",
        ),
    )
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--report-directory", type=Path, required=True)
    parser.add_argument("--bundle-directory", type=Path)
    parser.add_argument("--validation-directory", type=Path)
    return parser.parse_args()


def main() -> int:
    """Run one import workflow phase."""
    arguments = parse_arguments()
    try:
        workspace = arguments.workspace.resolve()
        report_directory = arguments.report_directory.resolve()
        report_directory.mkdir(parents=True, exist_ok=True)
        bundle_directory = None if arguments.bundle_directory is None else arguments.bundle_directory.resolve()
        validation_directory = (
            None if arguments.validation_directory is None else arguments.validation_directory.resolve()
        )
        if arguments.phase in {"preview", "apply"}:
            run_import(arguments.phase, workspace, report_directory)
        elif arguments.phase == "prepare-apply":
            if bundle_directory is None:
                raise WorkflowFailure("prepare-apply requires a bundle directory")
            prepare_candidate(workspace, report_directory, bundle_directory)
        elif arguments.phase == "validate-apply":
            if bundle_directory is None:
                raise WorkflowFailure("validate-apply requires a bundle directory")
            apply_candidate_bundle(workspace, bundle_directory)
        elif arguments.phase == "check-candidate":
            if bundle_directory is None:
                raise WorkflowFailure("check-candidate requires a bundle directory")
            check_candidate(workspace, bundle_directory)
        elif arguments.phase == "publish-apply":
            if bundle_directory is None:
                raise WorkflowFailure("publish-apply requires a bundle directory")
            if validation_directory is None:
                raise WorkflowFailure("publish-apply requires a validation directory")
            manifest = apply_candidate_bundle(workspace, bundle_directory)
            require_candidate_approvals(bundle_directory, manifest)
            restore_bundle_reports(bundle_directory, report_directory)
            restore_validation_report(validation_directory, report_directory)
            publish(report_directory, workspace)
        else:
            publish(report_directory, workspace)
        return 0
    except (WorkflowFailure, OSError, subprocess.SubprocessError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
