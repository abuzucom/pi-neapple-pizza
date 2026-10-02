#!/usr/bin/env python3
"""Preview and apply bounded source imports from the fixed abuzucom/pi donor."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from collections import deque
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable, TypeVar


SOURCE_REPOSITORY = "abuzucom/pi"
SOURCE_URL = "https://github.com/abuzucom/pi.git"
RECEIPT_PATH = "docs/pi-import.json"
PENDING_RECEIPT_PATH = "docs/pi-import-pending.json"
CONFLICT_PATH = "docs/pi-import-conflicts.json"
MAX_CHANGED_FILES = 5_000
MAX_TOTAL_BYTES = 536_870_912
MAX_FILE_BYTES = 52_428_800
MAX_REPORT_BYTES = 5_242_880
MAX_GENERATION_WORKERS = 4
MAX_GENERATION_QUEUE = 8
MAX_DEPENDENCY_VERSION_LENGTH = 256
SHA_PATTERN = re.compile(r"[0-9a-f]{40}")
SEMVER_PATTERN = re.compile(
    r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"
    r"(?:-(?:0|[1-9][0-9]*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*))*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
)
TEST_PATTERN = re.compile(r"(^|/)(tests?|__tests__)(/|$)|\.(test|spec)\.[^/]+$")
DEPENDENCY_SECTIONS = ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies", "overrides")
APPROVED_OVERRIDES = {
    "brace-expansion": "5.0.12",
    "protobufjs": "7.6.6",
}
CHECKER_REVISION = "pi-import-content-v1"
PRIVATE_KEY_PATTERN = re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")
TOKEN_PATTERNS = (
    re.compile(rb"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(rb"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(rb"\bAKIA[0-9A-Z]{16}\b"),
)
WEAK_HASH_PATTERN = re.compile(rb"\b(?:md5|sha1|sha-1)\b", re.IGNORECASE)
CONTENT_SCAN_CACHE: dict[tuple[str, str], dict[str, bool]] = {}
InputValue = TypeVar("InputValue")
OutputValue = TypeVar("OutputValue")
ROOT_FILES = frozenset(
    {
        ".npmrc",
        "biome.json",
        "mini-test.sh",
        "package.json",
        "pi-test.bat",
        "pi-test.ps1",
        "pi-test.sh",
        "test.sh",
        "tsconfig.base.json",
        "tsconfig.json",
        "tui-plan.md",
        "vitest.base.ts",
    }
)
PROTECTED_ROOTS = frozenset(
    {
        ".agents",
        ".claude",
        ".codex",
        ".gemini",
        ".github",
        ".husky",
        ".pi",
        "ci",
        "docs",
        "hooks",
        "plan",
        "tests",
        "tools",
    }
)
PROTECTED_ROOT_FILES = frozenset(
    {
        ".gitattributes",
        ".gitignore",
        "AGENTS.md",
        "CHANGELOG.md",
        "CLAUDE.md",
        "CONTRIBUTING.md",
        "GEMINI.md",
        "LICENSE",
        "README.md",
        "SECURITY.md",
        "shared-files.json",
    }
)


class ImportFailure(RuntimeError):
    """Report an import condition that requires active review."""


@dataclass(frozen=True)
class DonorEntry:
    path: str
    object_id: str
    donor_sha256: str
    size: int
    sha256: str
    content: bytes


def bounded_parallel_map(
    operation: Callable[[InputValue], OutputValue],
    values: Iterable[InputValue],
) -> list[OutputValue]:
    """Run independent generation work with bounded deterministic ordering."""
    iterator = iter(values)
    results: list[OutputValue] = []
    exhausted = object()
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=MAX_GENERATION_WORKERS,
        thread_name_prefix="pi-import",
    ) as executor:
        active: deque[concurrent.futures.Future[OutputValue]] = deque()
        for _ in range(MAX_GENERATION_QUEUE):
            value = next(iterator, exhausted)
            if value is exhausted:
                break
            active.append(executor.submit(operation, value))
        while active:
            results.append(active.popleft().result())
            value = next(iterator, exhausted)
            if value is not exhausted:
                active.append(executor.submit(operation, value))
    return results


def run_git(arguments: list[str], *, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    """Run Git with an argument array and a bounded environment."""
    environment = os.environ.copy()
    environment["GIT_CONFIG_NOSYSTEM"] = "1"
    environment["GIT_CONFIG_GLOBAL"] = os.devnull
    return subprocess.run(
        ["git", *arguments],
        check=check,
        capture_output=True,
        env=environment,
    )


def validate_sha(value: str) -> str:
    """Return a validated lowercase full commit identifier."""
    normalized = value.lower()
    if SHA_PATTERN.fullmatch(normalized) is None:
        raise ImportFailure("source SHA must contain exactly 40 lowercase hexadecimal characters")
    result = run_git(["cat-file", "-e", f"{normalized}^{{commit}}"], check=False)
    if result.returncode != 0:
        raise ImportFailure("source SHA does not identify an available commit")
    return normalized


def validate_path(value: str) -> str:
    """Validate one Git tree path before filesystem use."""
    if "\\" in value or any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ImportFailure(f"unsafe donor path: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise ImportFailure(f"unsafe donor path: {value!r}")
    if path.parts[0].endswith(":"):
        raise ImportFailure(f"unsafe donor path: {value!r}")
    return path.as_posix()


def import_path_allowed(path: str) -> bool:
    """Return whether the source path belongs to the product import surface."""
    parts = PurePosixPath(path).parts
    if parts[-1] in {"package-lock.json", "npm-shrinkwrap.json"}:
        return False
    if len(parts) == 1:
        return path in ROOT_FILES
    if parts[0] == "packages":
        return True
    if parts[0] == "scripts":
        if PurePosixPath(path).suffix.lower() == ".py":
            raise ImportFailure(f"donor Python files under scripts are blocked: {path}")
        return True
    if parts[0] in PROTECTED_ROOTS:
        return False
    return False


def pin_manifest_version(value: str) -> str:
    """Require one exact semantic version for a dependency declaration."""
    if len(value) > MAX_DEPENDENCY_VERSION_LENGTH or SEMVER_PATTERN.fullmatch(value) is None:
        raise ImportFailure(f"dependency declaration must use an exact semantic version: {value}")
    return value


def transform_manifest(path: str, content: bytes) -> bytes:
    """Apply deterministic dependency policy to one imported package manifest."""
    try:
        manifest = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ImportFailure(f"package manifest is not valid UTF-8 JSON: {path}") from error
    if not isinstance(manifest, dict):
        raise ImportFailure(f"package manifest root must be an object: {path}")
    for section in DEPENDENCY_SECTIONS:
        values = manifest.get(section)
        if values is None:
            continue
        if not isinstance(values, dict):
            raise ImportFailure(f"package dependency section must be an object: {path}:{section}")
        for name, version in list(values.items()):
            if not isinstance(name, str) or not isinstance(version, str):
                raise ImportFailure(f"package dependency entry must use strings: {path}:{section}")
            values[name] = pin_manifest_version(version)
    if path in {
        "package.json",
        "packages/coding-agent/package.json",
        "packages/coding-agent/install-lock/package.json",
    }:
        overrides = manifest.get("overrides")
        if overrides is None:
            overrides = {}
            manifest["overrides"] = overrides
        if not isinstance(overrides, dict):
            raise ImportFailure(f"package overrides must be an object: {path}")
        overrides.update(APPROVED_OVERRIDES)
    if path == "package.json":
        scripts = manifest.get("scripts")
        if isinstance(scripts, dict):
            scripts.pop("prepare", None)
        development = manifest.get("devDependencies")
        if not isinstance(development, dict):
            raise ImportFailure("root devDependencies must be an object")
        development.pop("husky", None)
        development["@anthropic-ai/sandbox-runtime"] = "0.0.77"
    if path == "packages/coding-agent/examples/extensions/sandbox/package.json":
        dependencies = manifest.get("dependencies")
        if not isinstance(dependencies, dict):
            raise ImportFailure("sandbox example dependencies must be an object")
        dependencies["@anthropic-ai/sandbox-runtime"] = "0.0.77"
    encoded = json.dumps(manifest, ensure_ascii=True, indent="\t") + "\n"
    return encoded.encode("ascii")


def transform_content(path: str, content: bytes) -> bytes:
    """Apply approved deterministic source adaptations before hashing."""
    if PurePosixPath(path).name == "package.json":
        return transform_manifest(path, content)
    return content


def read_blobs(expected_sizes: dict[str, int]) -> dict[str, bytes]:
    """Read validated Git blobs through one bounded batch process."""
    for object_id, expected_size in expected_sizes.items():
        if SHA_PATTERN.fullmatch(object_id) is None:
            raise ImportFailure("donor tree contains an invalid object identifier")
        if expected_size < 0 or expected_size > MAX_FILE_BYTES:
            raise ImportFailure("donor tree violates the individual file byte bound")
    environment = os.environ.copy()
    environment["GIT_CONFIG_NOSYSTEM"] = "1"
    environment["GIT_CONFIG_GLOBAL"] = os.devnull
    with tempfile.TemporaryFile() as error_stream:
        process = subprocess.Popen(
            ["git", "cat-file", "--batch"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=error_stream,
            env=environment,
        )
        if process.stdin is None or process.stdout is None:
            process.kill()
            process.wait()
            raise ImportFailure("cannot open bounded donor blob streams")
        try:
            blobs: dict[str, bytes] = {}
            for requested_id, expected_size in expected_sizes.items():
                process.stdin.write(requested_id.encode("ascii") + b"\n")
                process.stdin.flush()
                header = process.stdout.readline(256)
                if not header.endswith(b"\n"):
                    raise ImportFailure("donor blob batch ended before its header")
                fields = header.rstrip(b"\n").split(b" ")
                if len(fields) != 3 or fields[1] != b"blob":
                    raise ImportFailure("donor blob batch returned an invalid header")
                try:
                    returned_id = fields[0].decode("ascii")
                    size = int(fields[2].decode("ascii"))
                except (UnicodeDecodeError, ValueError) as error:
                    raise ImportFailure("donor blob batch returned malformed metadata") from error
                if returned_id != requested_id or size != expected_size:
                    raise ImportFailure("donor blob batch violated its requested identifier or size bound")
                content = process.stdout.read(size)
                if len(content) != size or process.stdout.read(1) != b"\n":
                    raise ImportFailure("donor blob batch returned truncated content")
                blobs[requested_id] = content
            process.stdin.close()
            if process.stdout.read(1):
                raise ImportFailure("donor blob batch returned unexpected trailing data")
            return_code = process.wait()
            if return_code != 0:
                error_stream.seek(0)
                message = error_stream.read(MAX_REPORT_BYTES).decode("utf-8", errors="replace").strip()
                raise ImportFailure(f"cannot read donor blobs: {message}")
            return blobs
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            if not process.stdin.closed:
                process.stdin.close()
            process.stdout.close()


def build_donor_entry(source: tuple[str, str, bytes]) -> DonorEntry:
    """Transform and hash one validated donor blob."""
    path, object_id, donor_content = source
    content = transform_content(path, donor_content)
    return DonorEntry(
        path=path,
        object_id=object_id,
        donor_sha256=hashlib.sha256(donor_content).hexdigest(),
        size=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        content=content,
    )


def load_tree(commit: str) -> tuple[dict[str, DonorEntry], list[str]]:
    """Load allowed blobs once and list excluded paths."""
    result = run_git(["ls-tree", "-r", "-z", "-l", "--full-tree", commit])
    allowed_metadata: list[tuple[str, str, int]] = []
    excluded: list[str] = []
    records = result.stdout.split(b"\0")
    for raw_record in records:
        if not raw_record:
            continue
        metadata, separator, raw_path = raw_record.partition(b"\t")
        if not separator:
            raise ImportFailure("donor tree record lacks a path separator")
        try:
            mode, object_type, object_id, raw_size = metadata.decode("ascii").split()
            path = validate_path(raw_path.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as error:
            raise ImportFailure("donor tree contains malformed metadata") from error
        if not import_path_allowed(path):
            excluded.append(path)
            continue
        if object_type != "blob" or mode not in {"100644", "100755"}:
            raise ImportFailure(f"unsupported donor entry at {path}")
        try:
            size = int(raw_size)
        except ValueError as error:
            raise ImportFailure(f"donor tree contains an invalid blob size at {path}") from error
        if size < 0 or size > MAX_FILE_BYTES:
            raise ImportFailure("donor tree violates the individual file byte bound")
        allowed_metadata.append((path, object_id, size))
    if len(allowed_metadata) > MAX_CHANGED_FILES:
        raise ImportFailure("donor import exceeds the file-count bound")
    donor_total = sum(size for _, _, size in allowed_metadata)
    if donor_total > MAX_TOTAL_BYTES:
        raise ImportFailure("donor import exceeds the aggregate byte bound")
    expected_sizes: dict[str, int] = {}
    for _, object_id, size in allowed_metadata:
        previous_size = expected_sizes.setdefault(object_id, size)
        if previous_size != size:
            raise ImportFailure("donor tree reports inconsistent blob sizes")
    blobs = read_blobs(expected_sizes)
    entry_sources = (
        (path, object_id, blobs[object_id])
        for path, object_id, _ in allowed_metadata
    )
    transformed_entries = bounded_parallel_map(build_donor_entry, entry_sources)
    entries: dict[str, DonorEntry] = {}
    total_bytes = 0
    for entry in transformed_entries:
        total_bytes += entry.size
        if total_bytes > MAX_TOTAL_BYTES:
            raise ImportFailure("donor import exceeds the aggregate byte bound")
        entries[entry.path] = entry
    return entries, sorted(excluded)


def read_json(path: Path) -> dict[str, Any] | None:
    """Read one JSON object when it exists."""
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ImportFailure(f"cannot read JSON object at {path}") from error
    if not isinstance(value, dict):
        raise ImportFailure(f"JSON root must be an object at {path}")
    return value


def canonical_bytes(value: Any) -> bytes:
    """Encode deterministic JSON for content-bound approvals."""
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode("ascii")


def digest_value(value: Any) -> str:
    """Return a SHA-256 digest for deterministic JSON data."""
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def scan_content(entry: DonorEntry) -> dict[str, bool]:
    """Scan one transformed blob once per content and checker revision."""
    key = (entry.sha256, CHECKER_REVISION)
    cached = CONTENT_SCAN_CACHE.get(key)
    if cached is not None:
        return cached
    result = {
        "secret": PRIVATE_KEY_PATTERN.search(entry.content) is not None
        or any(pattern.search(entry.content) is not None for pattern in TOKEN_PATTERNS),
        "weakHash": WEAK_HASH_PATTERN.search(entry.content) is not None,
    }
    CONTENT_SCAN_CACHE[key] = result
    return result


def detect_renames(
    base_entries: dict[str, DonorEntry], target_entries: dict[str, DonorEntry]
) -> list[dict[str, str]]:
    """Pair unique donor deletions and additions with identical transformed content."""
    deleted_by_digest: dict[str, list[str]] = {}
    added_by_digest: dict[str, list[str]] = {}
    for path, entry in base_entries.items():
        if path not in target_entries:
            deleted_by_digest.setdefault(entry.sha256, []).append(path)
    for path, entry in target_entries.items():
        if path not in base_entries:
            added_by_digest.setdefault(entry.sha256, []).append(path)
    renames: list[dict[str, str]] = []
    for digest in sorted(set(deleted_by_digest) & set(added_by_digest)):
        deleted = sorted(deleted_by_digest[digest])
        added = sorted(added_by_digest[digest])
        if len(deleted) == 1 and len(added) == 1:
            renames.append({"from": deleted[0], "to": added[0]})
    return renames


def write_json(path: Path, value: Any) -> None:
    """Write bounded deterministic JSON with LF line endings."""
    encoded = json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    if len(encoded.encode("ascii")) > MAX_REPORT_BYTES:
        raise ImportFailure(f"JSON output exceeds the report byte bound: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(encoded, encoding="ascii", newline="\n")


def receipt_files(receipt: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    """Validate and return imported file records from a completed receipt."""
    if receipt is None:
        return {}
    source_repository = receipt.get("sourceRepository")
    source_sha = receipt.get("sourceSha")
    files = receipt.get("files")
    if source_repository != SOURCE_REPOSITORY or not isinstance(source_sha, str) or not isinstance(files, dict):
        raise ImportFailure("completed import receipt has an invalid source or file map")
    return files


def workspace_target(workspace: Path, path: str) -> Path:
    """Resolve one validated child path without crossing a linked parent."""
    target = workspace.joinpath(*PurePosixPath(path).parts)
    resolved_workspace = workspace.resolve()
    resolved_parent = target.parent.resolve()
    if resolved_parent != resolved_workspace and resolved_workspace not in resolved_parent.parents:
        raise ImportFailure(f"import destination escapes the workspace: {path}")
    return target


def local_digest(workspace: Path, path: str) -> str | None:
    """Return the current SHA-256 digest without following unsafe file types."""
    target = workspace_target(workspace, path)
    if not target.exists():
        return None
    if target.is_symlink() or not target.is_file():
        raise ImportFailure(f"workspace path has an unsupported file type: {path}")
    return hashlib.sha256(target.read_bytes()).hexdigest()


def read_local_digest(source: tuple[Path, str]) -> tuple[str, str | None]:
    """Read one local digest for bounded parallel preview generation."""
    workspace, path = source
    return path, local_digest(workspace, path)


def flatten_dependencies(entries: dict[str, DonorEntry]) -> dict[str, dict[str, str]]:
    """Collect direct dependency declarations from imported manifests."""
    inventory: dict[str, dict[str, str]] = {}
    for path, entry in sorted(entries.items()):
        if PurePosixPath(path).name != "package.json":
            continue
        try:
            manifest = json.loads(entry.content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ImportFailure(f"package manifest is not valid UTF-8 JSON: {path}") from error
        if not isinstance(manifest, dict):
            raise ImportFailure(f"package manifest root must be an object: {path}")
        declarations: dict[str, str] = {}
        for section in DEPENDENCY_SECTIONS:
            values = manifest.get(section, {})
            if not isinstance(values, dict):
                raise ImportFailure(f"package dependency section must be an object: {path}:{section}")
            for name, version in values.items():
                if not isinstance(name, str) or not isinstance(version, str):
                    raise ImportFailure(f"package dependency entry must use strings: {path}:{section}")
                declarations[f"{section}:{name}"] = version
        if declarations:
            inventory[path] = dict(sorted(declarations.items()))
    return inventory


def changed_dependencies(
    base_entries: dict[str, DonorEntry], target_entries: dict[str, DonorEntry]
) -> dict[str, dict[str, dict[str, str | None]]]:
    """Describe direct dependency additions, removals, and version changes."""
    base_inventory = flatten_dependencies(base_entries)
    target_inventory = flatten_dependencies(target_entries)
    changes: dict[str, dict[str, dict[str, str | None]]] = {}
    for path in sorted(set(base_inventory) | set(target_inventory)):
        before = base_inventory.get(path, {})
        after = target_inventory.get(path, {})
        path_changes: dict[str, dict[str, str | None]] = {}
        for key in sorted(set(before) | set(after)):
            if before.get(key) != after.get(key):
                path_changes[key] = {"before": before.get(key), "after": after.get(key)}
        if path_changes:
            changes[path] = path_changes
    return changes


def is_existing_test_change(path: str, base_entries: dict[str, DonorEntry], target_entries: dict[str, DonorEntry]) -> bool:
    """Return whether an existing donor test changed or disappeared."""
    return TEST_PATTERN.search(path) is not None and path in base_entries and (
        path not in target_entries or base_entries[path].sha256 != target_entries[path].sha256
    )


def ensure_ancestry(base_sha: str | None, source_sha: str) -> None:
    """Reject a donor target that rewrites or abandons completed history."""
    if base_sha is None or base_sha == source_sha:
        return
    base = validate_sha(base_sha)
    result = run_git(["merge-base", "--is-ancestor", base, source_sha], check=False)
    if result.returncode != 0:
        raise ImportFailure("source SHA does not descend from the completed donor revision")


def build_preview(workspace: Path, source_sha: str) -> tuple[dict[str, Any], dict[str, str], dict[str, DonorEntry]]:
    """Build one immutable import preview without writing the workspace."""
    receipt = read_json(workspace / RECEIPT_PATH)
    imported_files = receipt_files(receipt)
    base_sha_value = None if receipt is None else receipt.get("sourceSha")
    base_sha = base_sha_value if isinstance(base_sha_value, str) else None
    ensure_ancestry(base_sha, source_sha)
    target_entries, excluded = load_tree(source_sha)
    base_entries = {} if base_sha is None else load_tree(base_sha)[0]
    added: list[str] = []
    modified: list[str] = []
    deleted: list[str] = []
    locally_modified: list[str] = []
    conflicts: list[str] = []
    protected_collisions: list[str] = []
    all_paths = sorted(set(target_entries) | set(imported_files))
    local_digests = dict(
        bounded_parallel_map(
            read_local_digest,
            ((workspace, path) for path in all_paths),
        )
    )
    for path in all_paths:
        target = target_entries.get(path)
        base_record = imported_files.get(path)
        base_digest = base_record.get("sha256") if isinstance(base_record, dict) else None
        current_digest = local_digests[path]
        target_digest = None if target is None else target.sha256
        if base_record is None and current_digest is not None:
            protected_collisions.append(path)
            continue
        if current_digest != base_digest and base_record is not None:
            locally_modified.append(path)
        donor_changed = target_digest != base_digest
        local_changed = current_digest != base_digest
        if donor_changed and local_changed and target_digest != current_digest:
            conflicts.append(path)
        if base_record is None and target is not None:
            added.append(path)
        elif target is None:
            deleted.append(path)
        elif target_digest != base_digest:
            modified.append(path)
    dependency_changes = changed_dependencies(base_entries, target_entries)
    test_changes = [
        path
        for path in sorted(set(base_entries) | set(target_entries))
        if is_existing_test_change(path, base_entries, target_entries)
    ]
    renames = detect_renames(base_entries, target_entries)
    renamed_from = {item["from"] for item in renames}
    renamed_to = {item["to"] for item in renames}
    added = [path for path in added if path not in renamed_to]
    deleted = [path for path in deleted if path not in renamed_from]
    changed_target_paths = set(added) | set(modified) | renamed_to
    content_findings = {path: scan_content(target_entries[path]) for path in sorted(changed_target_paths)}
    secret_findings = [path for path, findings in content_findings.items() if findings["secret"]]
    weak_hash_findings = [path for path, findings in content_findings.items() if findings["weakHash"]]
    changes = {"added": added, "modified": modified, "deleted": deleted, "renamed": renames}
    approval_subject = {
        "baseSha": base_sha,
        "sourceRepository": SOURCE_REPOSITORY,
        "sourceSha": source_sha,
        "changes": changes,
        "conflicts": conflicts,
        "protectedCollisions": protected_collisions,
        "secretFindings": secret_findings,
        "targetFiles": {
            path: {
                "blob": entry.object_id,
                "donorSha256": entry.donor_sha256,
                "sha256": entry.sha256,
                "size": entry.size,
            }
            for path, entry in sorted(target_entries.items())
        },
    }
    digests = {
        "import": digest_value(approval_subject),
        "dependencies": digest_value(dependency_changes),
        "tests": digest_value(test_changes),
    }
    report = {
        **approval_subject,
        "dependencyChanges": dependency_changes,
        "excluded": excluded,
        "locallyModified": locally_modified,
        "testChanges": test_changes,
        "unsafeLinks": [],
        "unsupportedFileTypes": [],
        "weakHashFindings": weak_hash_findings,
        "volume": {
            "fileCount": len(target_entries),
            "totalBytes": sum(entry.size for entry in target_entries.values()),
        },
        "approvalDigests": digests,
    }
    return report, digests, target_entries


def verify_approval(name: str, supplied: str | None, expected: str, required: bool = True) -> None:
    """Require one exact approval digest when its protected category changed."""
    if not required and supplied is None:
        return
    if supplied != expected:
        raise ImportFailure(f"{name} approval digest does not match the current preview")


def marker_content(local: bytes, donor: bytes, path: str) -> bytes | None:
    """Create text conflict markers without corrupting binary files."""
    try:
        local_text = local.decode("utf-8")
        donor_text = donor.decode("utf-8")
    except UnicodeDecodeError:
        return None
    return (
        "<<<<<<< LOCAL\n"
        f"{local_text.rstrip(chr(10))}\n"
        "=======\n"
        f"{donor_text.rstrip(chr(10))}\n"
        f">>>>>>> ABUZUCOM_PI {path}\n"
    ).encode("utf-8")


def write_imported_file(workspace: Path, path: str, content: bytes) -> None:
    """Write one validated imported file beneath the workspace."""
    target = workspace_target(workspace, path)
    if target.is_symlink() or (target.exists() and not target.is_file()):
        raise ImportFailure(f"cannot overwrite unsupported workspace entry: {path}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)


def remove_imported_file(workspace: Path, path: str) -> None:
    """Remove one previously imported regular file."""
    target = workspace_target(workspace, path)
    if target.is_symlink() or (target.exists() and not target.is_file()):
        raise ImportFailure(f"cannot remove unsupported workspace entry: {path}")
    if target.exists():
        target.unlink()


def build_receipt(source_sha: str, entries: dict[str, DonorEntry], excluded: list[str]) -> dict[str, Any]:
    """Build the completed import receipt."""
    return {
        "schemaVersion": 1,
        "sourceRepository": SOURCE_REPOSITORY,
        "sourceUrl": SOURCE_URL,
        "sourceSha": source_sha,
        "excluded": excluded,
        "files": {
            path: {
                "blob": entry.object_id,
                "donorSha256": entry.donor_sha256,
                "sha256": entry.sha256,
                "size": entry.size,
            }
            for path, entry in sorted(entries.items())
        },
    }


def apply_import(
    workspace: Path,
    report: dict[str, Any],
    source_sha: str,
    target_entries: dict[str, DonorEntry],
) -> None:
    """Apply one verified preview and stage conflicts for review."""
    if report["protectedCollisions"]:
        names = ", ".join(report["protectedCollisions"][:10])
        raise ImportFailure(f"import collides with protected local paths: {names}")
    if report["secretFindings"]:
        names = ", ".join(report["secretFindings"][:10])
        raise ImportFailure(f"import contains secret findings: {names}")
    if report["unsafeLinks"] or report["unsupportedFileTypes"]:
        raise ImportFailure("import contains unsafe links or unsupported file types")
    completed = read_json(workspace / RECEIPT_PATH)
    imported_files = receipt_files(completed)
    conflicts = set(report["conflicts"])
    conflict_records: list[dict[str, str]] = []
    for path in sorted(set(target_entries) | set(imported_files)):
        target = target_entries.get(path)
        if path in conflicts:
            local_path = workspace_target(workspace, path)
            if local_path.is_symlink() or (local_path.exists() and not local_path.is_file()):
                raise ImportFailure(f"workspace path has an unsupported file type: {path}")
            local_content = local_path.read_bytes() if local_path.exists() else b""
            donor_content = b"" if target is None else target.content
            marked = marker_content(local_content, donor_content, path)
            if marked is not None:
                write_imported_file(workspace, path, marked)
                conflict_records.append({"path": path, "type": "text"})
            else:
                conflict_records.append({"path": path, "type": "binary"})
            continue
        base_record = imported_files.get(path)
        base_digest = base_record.get("sha256") if isinstance(base_record, dict) else None
        current_digest = local_digest(workspace, path)
        if base_record is not None and current_digest != base_digest:
            continue
        if target is None:
            remove_imported_file(workspace, path)
        else:
            write_imported_file(workspace, path, target.content)
    excluded = report["excluded"]
    receipt = build_receipt(source_sha, target_entries, excluded)
    if conflict_records:
        write_json(workspace / CONFLICT_PATH, {"schemaVersion": 1, "conflicts": conflict_records})
        write_json(workspace / PENDING_RECEIPT_PATH, receipt)
        return
    write_json(workspace / RECEIPT_PATH, receipt)
    for stale_path in (PENDING_RECEIPT_PATH, CONFLICT_PATH):
        stale = workspace / stale_path
        if stale.exists():
            stale.unlink()


def parse_arguments() -> argparse.Namespace:
    """Parse the preview or apply invocation."""
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("preview", "apply"))
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--report-directory", type=Path, required=True)
    parser.add_argument("--import-approval-digest")
    parser.add_argument("--dependency-approval-digest")
    parser.add_argument("--test-change-approval-digest")
    return parser.parse_args()


def main() -> int:
    """Run preview or apply with fail-closed validation."""
    arguments = parse_arguments()
    try:
        source_sha = validate_sha(arguments.source_sha)
        workspace = arguments.workspace.resolve()
        report_directory = arguments.report_directory.resolve()
        report, digests, target_entries = build_preview(workspace, source_sha)
        write_json(report_directory / "import-report.json", report)
        write_json(report_directory / "approval-digests.json", digests)
        if arguments.mode == "preview":
            print(json.dumps(digests, sort_keys=True))
            return 0
        verify_approval("import", arguments.import_approval_digest, digests["import"])
        dependency_required = bool(report["dependencyChanges"])
        verify_approval(
            "dependency",
            arguments.dependency_approval_digest,
            digests["dependencies"],
            required=dependency_required,
        )
        test_required = bool(report["testChanges"])
        verify_approval(
            "test change",
            arguments.test_change_approval_digest,
            digests["tests"],
            required=test_required,
        )
        apply_import(workspace, report, source_sha, target_entries)
        print(json.dumps({"conflicts": len(report["conflicts"]), "sourceSha": source_sha}, sort_keys=True))
        return 0
    except ImportFailure as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
