"""Bind native registrations to a complete reviewed runtime generation."""
import hashlib
import json
import shlex
from pathlib import Path
from check_native_hook_launchers import CONFIGS, build_bootstrap_prefix

ROOT = Path(__file__).resolve().parent.parent


def runtime_paths(root: Path) -> list[Path]:
    """Select executable and policy inputs without reading unrelated files."""
    paths = [root / "AGENTS.md", root / "docs/project-orientation.md"]
    for directory in ("hooks", "scripts", "tools"):
        paths.extend((root / directory).glob("*.py"))
        paths.extend((root / directory).glob("*.txt"))
    paths.extend((root / "docs/agent-policy").glob("*.md"))
    return sorted(set(paths))


def replace_commands(value: object, prefix: str) -> None:
    """Retain each event, matcher, hook name, and client argument."""
    if isinstance(value, list):
        for child in value:
            replace_commands(child, prefix)
        return
    if not isinstance(value, dict):
        return
    for key, child in value.items():
        if key not in ("command", "commandWindows"):
            replace_commands(child, prefix)
            continue
        arguments = shlex.split(child)
        if arguments[0] != "python" or "-c" not in arguments:
            raise ValueError("unexpected native launcher shape")
        tail = arguments[arguments.index("-c") + 2:]
        if len(tail) != 3 or tail[1] != "--client":
            raise ValueError("unexpected native hook arguments")
        value[key] = prefix + " ".join(tail)


def seal_runtime(root: Path) -> None:
    """Write the complete generation digest before updating registrations."""
    record = {}
    for path in runtime_paths(root):
        if path.is_symlink() or not path.is_file():
            raise ValueError("runtime input is absent or linked")
        record[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = root / "scripts/runtime-integrity.json"
    manifest.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8", newline="\n")
    prefix = build_bootstrap_prefix(root)
    for _client, relative in CONFIGS:
        path = root / relative
        document = json.loads(path.read_text(encoding="utf-8"))
        replace_commands(document, prefix)
        path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8", newline="\n")
    for relative in (".claude/settings.json", "hooks/claude-code-settings.example.json"):
        path = root / relative
        document = json.loads(path.read_text(encoding="utf-8"))
        bind_claude(document, shlex.split(prefix)[3])
        path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8", newline="\n")


def bind_claude(value: object, expression: str) -> None:
    """Preserve structured Claude argument arrays and every registered hook."""
    if isinstance(value, list):
        for child in value:
            bind_claude(child, expression)
        return
    if not isinstance(value, dict):
        return
    if value.get("type") == "command" and value.get("command") == "python":
        arguments = value["args"]
        if "-c" in arguments:
            arguments = arguments[arguments.index("-c") + 2:]
        else:
            arguments = [Path(arguments[0]).name, *arguments[1:]]
        value["args"] = ["-I", "-c", expression, *arguments]
        return
    for child in value.values():
        bind_claude(child, expression)


if __name__ == "__main__":
    seal_runtime(ROOT)
