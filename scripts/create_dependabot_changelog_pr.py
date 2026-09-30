#!/usr/bin/env python3
"""Create a linked draft changelog pull request for a Dependabot update."""
import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

try:
    from scripts.trusted_git import run_git
except ModuleNotFoundError:
    from trusted_git import run_git


DEPENDABOT_ID = 49699333
VERSION_PATTERN = re.compile(
    r"^## \[(\d+)\.(\d+)\.(\d+)\] \((\d{4}-\d{2}-\d{2})\)$"
)
REPOSITORY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
BRANCH_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$")
MAX_TITLE_LENGTH = 160
MAX_FILES_IN_BODY = 20


def _event_path() -> Path:
    """Return the bounded GitHub event path."""
    value = os.environ.get("GITHUB_EVENT_PATH", "")
    path = Path(value)
    if not value or not path.is_file() or path.stat().st_size > 1_000_000:
        raise ValueError("GitHub event payload is unavailable or too large")
    return path


def _repository() -> str:
    """Return the validated repository name from the workflow environment."""
    value = os.environ.get("GITHUB_REPOSITORY", "")
    if not REPOSITORY_PATTERN.fullmatch(value):
        raise ValueError("GitHub repository metadata is invalid")
    return value


def _run_gh(arguments: list[str]) -> str:
    """Run trusted GitHub CLI with an argument array."""
    wrapper = Path(__file__).resolve().parent / "trusted_gh.py"
    result = subprocess.run(
        [sys.executable, str(wrapper), "run", *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "trusted GitHub CLI failed")
    return result.stdout


def _api_json(path: str) -> object:
    """Read one GitHub API resource through trusted GitHub CLI."""
    return json.loads(_run_gh(["api", path]))


def _event_data() -> dict:
    """Read the workflow event payload."""
    data = json.loads(_event_path().read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("GitHub event payload is not an object")
    return data


def _find_dependabot_pr(repository: str, head_sha: str) -> dict | None:
    """Resolve one trusted Dependabot PR from a workflow head SHA."""
    pulls = _api_json(f"repos/{repository}/commits/{head_sha}/pulls")
    if not isinstance(pulls, list):
        raise ValueError("pull request list is invalid")
    dependabot_pulls = [
        pull for pull in pulls
        if isinstance(pull, dict)
        and isinstance(pull.get("user"), dict)
        and pull["user"].get("id") == DEPENDABOT_ID
        and pull.get("state") == "open"
    ]
    if not dependabot_pulls:
        return None
    if len(dependabot_pulls) != 1:
        raise ValueError("workflow head SHA resolves to multiple open Dependabot pull requests")
    pull = dependabot_pulls[0]
    number = pull.get("number")
    if not isinstance(number, int) or number < 1:
        raise ValueError("pull request number is invalid")
    detail = _api_json(f"repos/{repository}/pulls/{number}")
    if not isinstance(detail, dict):
        raise ValueError("pull request detail is invalid")
    if detail.get("state") != "open":
        return None
    base = detail.get("base")
    head = detail.get("head")
    if (not isinstance(base, dict) or not isinstance(head, dict)
            or not BRANCH_PATTERN.fullmatch(str(base.get("ref", "")))
            or not BRANCH_PATTERN.fullmatch(str(head.get("ref", "")))):
        raise ValueError("pull request branch metadata is invalid")
    return detail


def _safe_text(value: object, limit: int = MAX_TITLE_LENGTH) -> str:
    """Return one safe, bounded line for generated Markdown."""
    text = " ".join(str(value or "").split())
    text = text.replace("`", "'")
    return text[:limit].rstrip()


def _first_version(text: str) -> tuple[int, int, int]:
    """Return the first stable release version."""
    for line in text.splitlines():
        match = VERSION_PATTERN.fullmatch(line)
        if match:
            return tuple(int(match.group(index)) for index in range(1, 4))
    raise ValueError("CHANGELOG.md has no stable version heading")


def _next_version(text: str) -> tuple[int, int, int]:
    """Return the next patch release version."""
    major, minor, patch = _first_version(text)
    return major, minor, patch + 1


def _insert_entry(text: str, version: tuple[int, int, int], number: int) -> str:
    """Insert a minimal patch entry before the current latest release."""
    marker = "## ["
    position = text.find(marker)
    if position < 0:
        raise ValueError("CHANGELOG.md has no release heading")
    version_text = ".".join(str(part) for part in version)
    entry = (
        f"## [{version_text}] ({date.today().isoformat()})\n\n"
        "### Fixed\n\n"
        f"- Record the Dependabot update from pull request #{number}.\n\n"
    )
    return text[:position] + entry + text[position:]


def _companion_branch(number: int) -> str:
    """Return the deterministic companion branch name."""
    return f"chore/dependabot-changelog-{number}"


def _existing_companion(branch: str) -> bool:
    """Return whether a companion pull request already exists."""
    output = _run_gh(["pr", "list", "--head", branch, "--state", "all", "--json", "number"])
    records = json.loads(output)
    return isinstance(records, list) and bool(records)


def _changed_files(repository: str, number: int) -> list[str]:
    """Return bounded changed file paths from the original pull request."""
    records = _api_json(f"repos/{repository}/pulls/{number}/files")
    if not isinstance(records, list):
        raise ValueError("pull request files are invalid")
    paths = [record.get("filename") for record in records if isinstance(record, dict)]
    safe_paths = [_safe_text(path, 200) for path in paths if isinstance(path, str)]
    return safe_paths[:MAX_FILES_IN_BODY]


def _body(repository: str, pull: dict, version: tuple[int, int, int], files: list[str]) -> str:
    """Build the companion pull request body."""
    number = pull["number"]
    title = _safe_text(pull.get("title"))
    base = _safe_text(pull.get("base", {}).get("ref"))
    head = _safe_text(pull.get("head", {}).get("ref"))
    version_text = ".".join(str(part) for part in version)
    file_lines = [f"- `{path}`" for path in files]
    if len(files) == MAX_FILES_IN_BODY:
        file_lines.append("- Additional changed files omitted from this summary.")
    return "\n".join(
        [
            "## Original Dependabot PR",
            "",
            f"- PR: [#{number}](https://github.com/{repository}/pull/{number})",
            f"- Title: `{title}`",
            f"- Author: `dependabot[bot]` (account ID `{DEPENDABOT_ID}`)",
            f"- Base branch: `{base}`",
            f"- Head branch: `{head}`",
            "- Changed files:",
            *file_lines,
            "",
            "## Changelog decision",
            "",
            f"- SemVer level: patch (`{version_text}`)",
            "- Reason: Dependabot dependency or tooling update without a public API change.",
            "",
            "Merging this companion changelog PR does not merge, approve, or resolve "
            f"the original Dependabot PR [#{number}](https://github.com/{repository}/pull/{number}).",
            "Review and merge the original Dependabot PR separately.",
            "",
        ]
    )


def _git(repository: Path, arguments: list[str], *, check: bool = True) -> str:
    """Run one trusted Git argument array."""
    result = run_git(repository, arguments, check=check)
    return result.stdout


def create_companion(repository: Path, pull: dict) -> int:
    """Create and publish one idempotent companion branch and draft PR."""
    number = pull["number"]
    branch = _companion_branch(number)
    if _existing_companion(branch):
        return 0
    changelog = repository / "CHANGELOG.md"
    current = changelog.read_text(encoding="utf-8")
    version = _next_version(current)
    updated_changelog = _insert_entry(current, version, number)
    _git(repository, ["switch", "-c", branch])
    changelog.write_text(updated_changelog, encoding="utf-8", newline="\n")
    _git(repository, ["add", "CHANGELOG.md"])
    _git(repository, ["commit", "-m", f"docs: add changelog for Dependabot #{number}"])
    _git(repository, ["push", "--set-upstream", "origin", branch])
    body_path = repository / ".dependabot-changelog-body.md"
    try:
        files = _changed_files(_repository(), number)
        body_text = _body(_repository(), pull, version, files)
        body_path.write_text(body_text, encoding="utf-8", newline="\n")
        title = f"docs: add changelog for Dependabot #{number}"
        _run_gh([
            "pr", "create", "--draft",
            "--base", pull["base"]["ref"],
            "--head", branch,
            "--title", title,
            "--body-file", str(body_path),
        ])
    finally:
        body_path.unlink(missing_ok=True)
    return 0


def main() -> int:
    """Create a companion pull request for a completed Dependabot check."""
    try:
        event = _event_data()
        run = event.get("workflow_run", {})
        if run.get("conclusion") != "success":
            return 0
        head_sha = run.get("head_sha")
        if not isinstance(head_sha, str) or not re.fullmatch(r"[0-9a-fA-F]{40}", head_sha):
            raise ValueError("workflow head SHA is invalid")
        repository_name = _repository()
        pull = _find_dependabot_pr(repository_name, head_sha)
        if pull is None:
            return 0
        return create_companion(Path.cwd(), pull)
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        print(f"error: Dependabot changelog automation failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
