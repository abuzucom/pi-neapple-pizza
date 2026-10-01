"""Run canonical repository checks from installed Git hook entry points."""
import re
import shlex
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts.trusted_git import run_git

STAGES = frozenset(("pre-commit", "pre-push", "commit-msg"))
MAX_CONFIG_BYTES = 1024 * 1024
MAX_PUSH_BYTES = 64 * 1024
MAX_GIT_OUTPUT_CHARS = 16 * 1024 * 1024
REVISION_PATTERN = re.compile(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})\Z")
HOOK_FIELDS = frozenset(("id", "name", "entry", "language", "pass_filenames",
                         "always_run", "additional_dependencies", "files", "stages"))


def compile_hook(hook: dict, defaults: list[str]) -> tuple:
    """Validate one supported local hook before compiling its matcher."""
    if not isinstance(hook, dict) or set(hook) - HOOK_FIELDS or hook.get("language") != "python":
        raise ValueError("unsupported canonical hook configuration")
    stages = hook.get("stages", defaults)
    if not isinstance(stages, list) or not stages:
        raise ValueError("invalid hook stages")
    if any(not isinstance(stage, str) or stage not in STAGES for stage in stages):
        raise ValueError("invalid hook stages")
    for field in ("always_run", "pass_filenames"):
        if field in hook and not isinstance(hook[field], bool):
            raise ValueError("invalid hook Boolean option")
    dependencies = hook.get("additional_dependencies", [])
    if not isinstance(dependencies, list) or any(value != "PyYAML==6.0.3" for value in dependencies):
        raise ValueError("unapproved hook dependency")
    if not isinstance(hook.get("entry"), str) or not isinstance(hook.get("files", ""), str):
        raise ValueError("invalid hook entry or file matcher")
    command = shlex.split(hook["entry"])
    if len(command) < 2 or command[0] != "python" or not command[1].startswith("scripts/"):
        raise ValueError("unapproved hook entry")
    target = ROOT / command[1]
    if target.is_symlink() or not target.resolve().is_relative_to(ROOT / "scripts") or not target.is_file():
        raise ValueError("hook entry escapes canonical scripts")
    return hook, stages, re.compile(hook.get("files", "")), command[1:]


def load_hooks() -> list[tuple]:
    """Load current approved configuration without cross-invocation caching."""
    path = ROOT / ".pre-commit-config.yaml"
    if path.is_symlink() or path.stat().st_size > MAX_CONFIG_BYTES:
        raise ValueError("hook configuration is linked or oversized")
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or set(document) - {"repos", "default_stages"}:
        raise ValueError("invalid canonical hook document")
    repositories = document.get("repos")
    if not isinstance(repositories, list) or not repositories:
        raise ValueError("canonical hook repositories are missing")
    compiled = []
    for repository in repositories:
        if not isinstance(repository, dict) or repository.get("repo") != "local":
            raise ValueError("unapproved external hook manager")
        hooks = repository.get("hooks")
        if not isinstance(hooks, list) or not hooks:
            raise ValueError("canonical hooks are missing")
        compiled.extend(compile_hook(hook, document.get("default_stages", sorted(STAGES))) for hook in hooks)
    return compiled


def select_checks(kind: str, changed: list[str], arguments: list[str]) -> list[list[str]]:
    """Preserve canonical stage selection, matchers, and filename forwarding."""
    if kind not in STAGES:
        raise ValueError("unsupported Git hook invocation")
    checks = []
    for hook, stages, pattern, command in load_hooks():
        if kind not in stages:
            continue
        selected = [name for name in changed if pattern.search(name)]
        if not selected and not hook.get("always_run", False):
            continue
        forwarded = arguments if kind == "commit-msg" else selected
        checks.append(command + (forwarded if hook.get("pass_filenames", True) else []))
    return checks


def parse_push_records(text: str) -> list[tuple[str, str]]:
    """Validate complete Git push records before using object identifiers."""
    if len(text.encode("utf-8")) > MAX_PUSH_BYTES:
        raise ValueError("push metadata exceeds its bound")
    records = []
    for line in text.splitlines():
        fields = line.split()
        if len(fields) != 4:
            raise ValueError("invalid push record")
        local, remote = fields[1], fields[3]
        if not REVISION_PATTERN.fullmatch(local) or not REVISION_PATTERN.fullmatch(remote):
            raise ValueError("invalid push revision")
        if len(local) != len(remote):
            raise ValueError("push revision formats differ")
        records.append((local, remote))
    return records


def read_changed_paths(arguments: list[str]) -> list[str]:
    """Read a fixed Git operation through the trusted executable resolver."""
    result = run_git(ROOT, arguments, check=True, timeout=30)
    if len(result.stdout) > MAX_GIT_OUTPUT_CHARS:
        raise ValueError("Git file inventory exceeds its bound")
    return [name for name in result.stdout.split("\0") if name]


def changed_paths(kind: str, arguments: list[str]) -> list[str]:
    """Select staged files, pushed trees, or the exact commit-message file."""
    if kind == "pre-commit" and not arguments:
        return read_changed_paths(["diff", "--cached", "--no-ext-diff", "--no-textconv",
                                   "--name-only", "--diff-filter=ACMR", "-z", "--"])
    if kind == "commit-msg" and len(arguments) == 1:
        return arguments
    if kind != "pre-push" or len(arguments) != 2:
        raise ValueError("invalid Git hook argument count")
    records = parse_push_records(sys.stdin.read(MAX_PUSH_BYTES + 1))
    names = set()
    for local, remote in records:
        if not local.strip("0"):
            continue
        if not remote.strip("0"):
            names.update(read_changed_paths(["ls-tree", "-r", "--name-only", "-z", local]))
        else:
            names.update(read_changed_paths(["diff", "--no-ext-diff", "--no-textconv",
                                             "--name-only", "--diff-filter=ACMR", "-z", remote, local, "--"]))
    return sorted(names)


def run_hook(kind: str, arguments: list[str]) -> int:
    """Run canonical checker argument arrays without shell evaluation."""
    if yaml.__version__ != "6.0.3":
        raise ValueError("install the approved PyYAML 6.0.3 dependency")
    changed = changed_paths(kind, arguments)
    failure = 0
    for script, *options in select_checks(kind, changed, arguments):
        result = subprocess.run([sys.executable, str(ROOT / script), *options], cwd=ROOT)
        failure = failure or result.returncode
    return failure


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("missing Git hook stage; invoke an installed hook")
    raise SystemExit(run_hook(sys.argv[1], sys.argv[2:]))
