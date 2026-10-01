import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IMPORTER = ROOT / "tools" / "import_pi_upstream.py"


def run_git(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout.strip()


def write_file(root: Path, relative_path: str, content: str) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


class ImportPiUpstreamTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_directory.cleanup)
        self.root = Path(self.temp_directory.name)
        self.repository = self.root / "donor"
        self.workspace = self.root / "workspace"
        self.report_directory = self.root / "report"
        self.repository.mkdir()
        self.workspace.mkdir()
        run_git(self.repository, "init", "--initial-branch=main")
        run_git(self.repository, "config", "user.name", "Import Test")
        run_git(self.repository, "config", "user.email", "import-test@example.invalid")

    def commit_donor(self, message: str) -> str:
        run_git(self.repository, "add", ".")
        run_git(self.repository, "commit", "-m", message)
        return run_git(self.repository, "rev-parse", "HEAD")

    def run_importer(self, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(IMPORTER),
                *arguments,
                "--workspace",
                str(self.workspace),
                "--report-directory",
                str(self.report_directory),
            ],
            cwd=self.repository,
            check=check,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    def test_preview_excludes_policy_owned_paths_without_mutating_workspace(self) -> None:
        write_file(self.repository, "packages/agent/src/index.ts", "export const value = 1;\n")
        write_file(self.repository, "AGENTS.md", "donor policy\n")
        write_file(self.repository, ".pi/settings.json", "{}\n")
        write_file(self.repository, ".husky/pre-commit", "npm test\n")
        source_sha = self.commit_donor("initial")
        before = sorted(path.relative_to(self.workspace) for path in self.workspace.rglob("*"))

        self.run_importer("preview", "--source-sha", source_sha)

        after = sorted(path.relative_to(self.workspace) for path in self.workspace.rglob("*"))
        self.assertEqual(before, after)
        report = json.loads((self.report_directory / "import-report.json").read_text(encoding="utf-8"))
        self.assertEqual(["packages/agent/src/index.ts"], report["changes"]["added"])
        self.assertEqual([".husky/pre-commit", ".pi/settings.json", "AGENTS.md"], report["excluded"])

    def test_apply_rejects_an_import_digest_mismatch(self) -> None:
        write_file(self.repository, "packages/agent/src/index.ts", "export const value = 1;\n")
        source_sha = self.commit_donor("initial")
        self.run_importer("preview", "--source-sha", source_sha)

        result = self.run_importer(
            "apply",
            "--source-sha",
            source_sha,
            "--import-approval-digest",
            "0" * 64,
            check=False,
        )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("import approval digest does not match", result.stderr)
        self.assertFalse((self.workspace / "packages").exists())

    def test_apply_writes_content_and_a_sha256_receipt(self) -> None:
        content = "export const value = 1;\n"
        write_file(self.repository, "packages/agent/src/index.ts", content)
        source_sha = self.commit_donor("initial")
        self.run_importer("preview", "--source-sha", source_sha)
        preview = json.loads((self.report_directory / "approval-digests.json").read_text(encoding="utf-8"))

        self.run_importer(
            "apply",
            "--source-sha",
            source_sha,
            "--import-approval-digest",
            preview["import"],
            "--dependency-approval-digest",
            preview["dependencies"],
        )

        imported = self.workspace / "packages/agent/src/index.ts"
        self.assertEqual(content, imported.read_text(encoding="utf-8"))
        receipt = json.loads((self.workspace / "docs/pi-import.json").read_text(encoding="utf-8"))
        expected_digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        self.assertEqual(expected_digest, receipt["files"]["packages/agent/src/index.ts"]["sha256"])
        self.assertEqual(source_sha, receipt["sourceSha"])

    def test_apply_stages_text_conflicts_without_advancing_receipt(self) -> None:
        path = "packages/agent/src/index.ts"
        write_file(self.repository, path, "export const value = 1;\n")
        base_sha = self.commit_donor("base")
        self.run_importer("preview", "--source-sha", base_sha)
        base_digests = json.loads((self.report_directory / "approval-digests.json").read_text(encoding="utf-8"))
        self.run_importer(
            "apply",
            "--source-sha",
            base_sha,
            "--import-approval-digest",
            base_digests["import"],
            "--dependency-approval-digest",
            base_digests["dependencies"],
        )
        write_file(self.workspace, path, "export const localValue = 2;\n")
        write_file(self.repository, path, "export const donorValue = 3;\n")
        target_sha = self.commit_donor("target")
        self.run_importer("preview", "--source-sha", target_sha)
        target_digests = json.loads((self.report_directory / "approval-digests.json").read_text(encoding="utf-8"))

        self.run_importer(
            "apply",
            "--source-sha",
            target_sha,
            "--import-approval-digest",
            target_digests["import"],
            "--dependency-approval-digest",
            target_digests["dependencies"],
        )

        conflict_text = (self.workspace / path).read_text(encoding="utf-8")
        self.assertIn("<<<<<<< LOCAL", conflict_text)
        self.assertIn("=======", conflict_text)
        self.assertIn(">>>>>>> ABUZUCOM_PI", conflict_text)
        completed = json.loads((self.workspace / "docs/pi-import.json").read_text(encoding="utf-8"))
        pending = json.loads((self.workspace / "docs/pi-import-pending.json").read_text(encoding="utf-8"))
        self.assertEqual(base_sha, completed["sourceSha"])
        self.assertEqual(target_sha, pending["sourceSha"])


if __name__ == "__main__":
    unittest.main()
