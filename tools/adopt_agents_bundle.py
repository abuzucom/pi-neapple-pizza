"""Verify and activate a complete agents bundle with retained backups."""
import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

try:
    from tools.bundle_transaction import (
        checked_target, verify_files, read_record, prepare_transaction,
        publish_transaction, recover_transaction, write_journal, exclusive_activation,
    )
except ImportError:
    from bundle_transaction import (
        checked_target, verify_files, read_record, prepare_transaction,
        publish_transaction, recover_transaction, write_journal, exclusive_activation,
    )

REGISTRATIONS = {".agents/hooks.json", ".claude/settings.json", ".codex/hooks.json",
                 ".codex/config.toml", ".gemini/settings.json"}
GIT_HOOKS = ("pre-commit", "commit-msg", "pre-push")


def run_checks(root: Path) -> None:
    """Run fixed non-mutating candidate checks before or after activation."""
    for script, arguments in (
        ("check_branch_name.py", ["--strict-agent-preflight"]),
        ("sync.py", ["--check"]), ("sync.py", ["--check-shared"]),
        ("check_gate_adoption.py", []), ("check_policy_size.py", []),
        ("check_hook_launchers.py", []),
    ):
        subprocess.run([sys.executable, "-E", "-s", str(root / "scripts" / script), *arguments],
                       cwd=root, check=True, timeout=60)


def install_bundle(root: Path, candidate: Path, record: dict) -> None:
    """Activate all artifacts in one invocation with registrations last."""
    files = dict(record["files"])
    verify_files(candidate, files)
    run_checks(candidate)
    files["docs/agents-adoption.json"] = hashlib.sha256(
        (candidate / "docs" / "agents-adoption.json").read_bytes()).hexdigest()
    sources = {name: candidate / name for name in files}
    for name in GIT_HOOKS:
        relative = ".git/hooks/" + name
        sources[relative] = candidate / "tools" / "git-hooks" / name
        files[relative] = hashlib.sha256(sources[relative].read_bytes()).hexdigest()
    backup = root / ".gate-staging" / "activation-backup"
    order = sorted(files, key=lambda name: (name in REGISTRATIONS, name))
    transaction = prepare_transaction(root, sources, {name: files[name] for name in order})
    try:
        publish_transaction(root, transaction)
        verify_files(root, files)
        run_checks(root)
        transaction["state"] = "complete"
        write_journal(backup, transaction)
    except (OSError, ValueError, subprocess.SubprocessError, KeyboardInterrupt):
        recover_transaction(root, transaction)
        raise


def main() -> int:
    """Activate only a candidate below the current repository staging root."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--manifest-sha256", required=True)
    options = parser.parse_args()
    root = Path.cwd().resolve()
    candidate = Path(options.candidate).resolve()
    if not candidate.is_relative_to(root / ".gate-staging") or not candidate.is_dir():
        raise ValueError("candidate is outside the fixed staging root")
    with exclusive_activation(root):
        record = read_record(candidate / "docs" / "agents-adoption.json", options.manifest_sha256)
        install_bundle(root, candidate, record)
    print("Complete agents adoption activated; original files and transaction record remain retained.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
