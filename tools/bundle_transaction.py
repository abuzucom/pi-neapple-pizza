"""Validate complete inventories and retain durable transaction recovery."""
import hashlib
import json
import os
import shutil
import stat
import sys
from contextlib import contextmanager
from pathlib import Path, PurePosixPath

MAX_RECORD_BYTES = 1024 * 1024
MAX_ARTIFACT_BYTES = 16 * 1024 * 1024
MAX_ARTIFACT_COUNT = 1024
DIGEST_LENGTH = 64
SOURCE_REVISION = "24f62e1c415313f1bc4bbd8cff30328ae6d69ae5"
GIT_HOOK_TARGETS = frozenset((".git/hooks/pre-commit", ".git/hooks/commit-msg", ".git/hooks/pre-push"))
EXECUTABLE_BITS = stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH


@contextmanager
def exclusive_activation(root: Path):
    """Keep the operating-system lock until publication or recovery ends."""
    path = checked_target(root, ".gate-staging/activation.lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        stream.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        if os.fstat(stream.fileno()).st_size == 0:
            stream.write(b"\0")
            stream.flush()
            os.fsync(stream.fileno())
        yield


def checked_target(root: Path, relative: str) -> Path:
    """Reject ambiguous paths and symlink components before access."""
    if sys.version_info < (3, 12):
        raise ValueError("Python 3.12 or newer is required before bundle activation")
    if not isinstance(relative, str) or any(value in relative for value in ("\\", ":", "\0")):
        raise ValueError("invalid bundle path")
    if any(ord(character) < 32 or ord(character) > 126 for character in relative):
        raise ValueError("bundle path contains unsupported characters")
    path = PurePosixPath(relative)
    if path.is_absolute() or not path.parts or ".." in path.parts or path.as_posix() != relative:
        raise ValueError("invalid bundle path")
    target = root.joinpath(*path.parts)
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError("bundle target escapes its root")
    current = root
    for part in path.parts:
        current = current / part
        if current.is_symlink() or current.is_junction():
            raise ValueError("bundle path contains a link")
    return target


def validate_digest(value: str) -> None:
    """Require a canonical SHA-256 digest before comparison."""
    if not isinstance(value, str) or len(value) != DIGEST_LENGTH:
        raise ValueError("invalid SHA-256 digest")
    if any(character not in "0123456789abcdef" for character in value):
        raise ValueError("invalid SHA-256 digest")


def file_digest(path: Path) -> str:
    """Hash a bounded regular artifact without following links."""
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_ARTIFACT_BYTES:
        raise ValueError("artifact is absent, linked, or oversized")
    with path.open("rb") as stream:
        content = stream.read(MAX_ARTIFACT_BYTES + 1)
    if len(content) > MAX_ARTIFACT_BYTES:
        raise ValueError("artifact grew beyond its bound")
    return hashlib.sha256(content).hexdigest()


def verify_files(root: Path, files: dict[str, str]) -> None:
    """Verify current bytes for every operation without a freshness cache."""
    for relative, expected in files.items():
        validate_digest(expected)
        target = checked_target(root, relative)
        if file_digest(target) != expected:
            raise ValueError(f"bundle integrity mismatch: {relative}")


def read_record(path: Path, approved_digest: str) -> dict:
    """Validate approved manifest bytes and shape before using fields."""
    validate_digest(approved_digest)
    if path.is_symlink() or not path.is_file():
        raise ValueError("adoption manifest is absent or linked")
    with path.open("rb") as stream:
        content = stream.read(MAX_RECORD_BYTES + 1)
    if len(content) > MAX_RECORD_BYTES or hashlib.sha256(content).hexdigest() != approved_digest:
        raise ValueError("adoption manifest differs from the approved digest")
    record = json.loads(content)
    if not isinstance(record, dict) or record.get("revision") != SOURCE_REVISION:
        raise ValueError("invalid source revision")
    files = record.get("files")
    if not isinstance(files, dict) or not 0 < len(files) <= MAX_ARTIFACT_COUNT:
        raise ValueError("invalid adoption file inventory")
    normalized = set()
    for relative, digest in files.items():
        checked_target(path.parent.parent, relative)
        validate_digest(digest)
        if relative.startswith((".git/", ".gate-staging/")) or relative.casefold() in normalized:
            raise ValueError("protected or duplicate manifest target")
        if relative == "docs/agents-adoption.json":
            raise ValueError("manifest cannot require its own content digest")
        normalized.add(relative.casefold())
    return record


def write_journal(backup: Path, transaction: dict) -> None:
    """Persist intent before publishing target bytes."""
    pending = checked_target(backup, "journal.pending")
    checked_target(backup, "transaction.json")
    with pending.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(transaction, stream, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(pending, backup / "transaction.json")


def replace_file(source: Path, target: Path, work: Path, expected: str, *, executable: bool = False) -> None:
    """Check source and copied bytes before replacing a target."""
    if file_digest(source) != expected:
        raise ValueError("source changed before publication")
    target.parent.mkdir(parents=True, exist_ok=True)
    work.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, work)
    if file_digest(work) != expected:
        raise ValueError("copied artifact differs from approved bytes")
    with work.open("r+b") as stream:
        stream.flush()
        os.fsync(stream.fileno())
    if executable:
        work.chmod(work.stat().st_mode | EXECUTABLE_BITS)
    os.replace(work, target)


def prepare_transaction(root: Path, sources: dict[str, Path], files: dict[str, str],
                        *, backup_relative: str = ".gate-staging/activation-backup") -> dict:
    """Back up every target before writing a durable publication intent."""
    if sources.keys() != files.keys():
        raise ValueError("source inventory differs from target inventory")
    backup = checked_target(root, backup_relative)
    if (backup / "transaction.json").exists():
        raise ValueError("retained transaction requires verification or recovery")
    operations = []
    for relative, expected in files.items():
        validate_digest(expected)
        target = checked_target(root, relative)
        if file_digest(sources[relative]) != expected:
            raise ValueError("candidate changed before transaction preparation")
        previous = file_digest(target) if target.exists() else None
        if previous is not None:
            original = checked_target(backup / "original", relative)
            replace_file(target, original, backup / "backup-work" / relative, previous)
        operations.append({"path": relative, "source": str(sources[relative]),
                           "digest": expected, "previous": previous})
    backup.mkdir(parents=True, exist_ok=True)
    transaction = {"state": "prepared", "operations": operations}
    write_journal(backup, transaction)
    return transaction


def publish_transaction(root: Path, transaction: dict,
                        *, backup_relative: str = ".gate-staging/activation-backup") -> None:
    """Reject concurrent target changes before each ordered replacement."""
    if transaction["state"] != "prepared":
        raise ValueError("transaction is not prepared")
    backup = checked_target(root, backup_relative)
    for operation in transaction["operations"]:
        target = checked_target(root, operation["path"])
        current = file_digest(target) if target.exists() else None
        if current != operation["previous"]:
            raise ValueError("target changed after transaction preparation")
        replace_file(Path(operation["source"]), target,
                     backup / "publish" / operation["path"], operation["digest"],
                     executable=operation["path"] in GIT_HOOK_TARGETS)


def recover_transaction(root: Path, transaction: dict,
                        *, backup_relative: str = ".gate-staging/activation-backup") -> None:
    """Restore approved originals without overwriting unrelated changes."""
    backup = checked_target(root, backup_relative)
    for operation in transaction["operations"]:
        target = checked_target(root, operation["path"])
        current = file_digest(target) if target.exists() else None
        if current not in (operation["previous"], operation["digest"]):
            raise ValueError("recovery target contains unrelated changes")
        if operation["previous"] is not None:
            original = checked_target(backup / "original", operation["path"])
            if file_digest(original) != operation["previous"]:
                raise ValueError("recovery backup integrity mismatch")
    for operation in reversed(transaction["operations"]):
        target = checked_target(root, operation["path"])
        current = file_digest(target) if target.exists() else None
        if current not in (operation["previous"], operation["digest"]):
            raise ValueError("recovery target changed before restoration")
        if operation["previous"] is not None:
            replace_file(backup / "original" / operation["path"], target,
                         backup / "restore" / operation["path"], operation["previous"])
        elif target.exists():
            if file_digest(target) != operation["digest"]:
                raise ValueError("recovery target changed before removal")
            target.unlink()
    transaction["state"] = "restored"
    write_journal(backup, transaction)
