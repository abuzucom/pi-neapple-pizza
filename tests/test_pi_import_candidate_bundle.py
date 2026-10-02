from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "pi_import_workflow.py"
SPEC = importlib.util.spec_from_file_location("pi_import_candidate_bundle", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load pi import workflow module")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CandidateBundleSecurityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.bundle = Path(self.temporary_directory.name)
        self.patch = self.bundle / "candidate.patch"
        self.report = self.bundle / "import-report.json"
        self.approvals = self.bundle / "approval-digests.json"
        self.patch.write_bytes(b"binary patch\n")
        self.report.write_text("{}\n", encoding="ascii")
        self.approvals.write_text("{}\n", encoding="ascii")
        manifest = {
            "schemaVersion": 1,
            "trustedBaseSha": "a" * 40,
            "donorSha": "b" * 40,
            "approvalDigests": {"import": "c" * 64, "dependencies": None, "tests": None},
            "changedPaths": ["packages/agent/src/index.ts"],
            "files": {
                "candidate.patch": digest(self.patch),
                "import-report.json": digest(self.report),
                "approval-digests.json": digest(self.approvals),
            },
        }
        (self.bundle / "manifest.json").write_text(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="ascii",
            newline="\n",
        )

    def test_accepts_an_exact_immutable_bundle(self) -> None:
        manifest = MODULE.verify_candidate_bundle(self.bundle, "a" * 40)
        self.assertEqual("b" * 40, manifest["donorSha"])

    def test_rejects_bundle_file_tampering(self) -> None:
        self.patch.write_bytes(b"changed\n")
        with self.assertRaisesRegex(MODULE.WorkflowFailure, "digest mismatch"):
            MODULE.verify_candidate_bundle(self.bundle, "a" * 40)

    def test_rejects_unexpected_bundle_files(self) -> None:
        (self.bundle / "extra.txt").write_text("extra\n", encoding="ascii")
        with self.assertRaisesRegex(MODULE.WorkflowFailure, "unexpected files"):
            MODULE.verify_candidate_bundle(self.bundle, "a" * 40)

    def test_rejects_a_changed_trusted_base(self) -> None:
        with self.assertRaisesRegex(MODULE.WorkflowFailure, "trusted base SHA"):
            MODULE.verify_candidate_bundle(self.bundle, "d" * 40)

    def test_changed_paths_uses_the_explicit_workspace(self) -> None:
        workspace = self.bundle / "workspace"
        workspace.mkdir()
        subprocess.run(["git", "init", "--quiet", str(workspace)], check=True)
        (workspace / "candidate.txt").write_text("candidate\n", encoding="ascii")

        self.assertEqual(["candidate.txt"], MODULE.changed_paths(workspace))

    def test_fetch_source_uses_the_explicit_workspace(self) -> None:
        source = self.bundle / "source"
        workspace = self.bundle / "fetch-workspace"
        decoy = self.bundle / "decoy"
        for repository in (source, workspace, decoy):
            repository.mkdir()
            subprocess.run(["git", "init", "--quiet", str(repository)], check=True)
        (source / "source.txt").write_text("source\n", encoding="ascii")
        subprocess.run(["git", "-C", str(source), "add", "source.txt"], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(source),
                "-c",
                "user.name=Import Test",
                "-c",
                "user.email=import-test@example.invalid",
                "commit",
                "--quiet",
                "-m",
                "test: add source fixture",
            ],
            check=True,
        )
        source_sha = subprocess.run(
            ["git", "-C", str(source), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        previous_directory = Path.cwd()
        try:
            os.chdir(decoy)
            with patch.object(MODULE, "SOURCE_URL", str(source)):
                self.assertEqual(source_sha, MODULE.fetch_source(workspace, source_sha, "apply"))
        finally:
            os.chdir(previous_directory)

        self.assertTrue((workspace / ".git" / "FETCH_HEAD").is_file())
        self.assertFalse((decoy / ".git" / "FETCH_HEAD").exists())

    def test_publication_requires_the_fixed_repository_origin(self) -> None:
        workspace = self.bundle / "publication-workspace"
        workspace.mkdir()
        subprocess.run(["git", "init", "--quiet", str(workspace)], check=True)
        subprocess.run(
            ["git", "-C", str(workspace), "remote", "add", "origin", "https://example.test/external.git"],
            check=True,
        )
        with self.assertRaisesRegex(MODULE.WorkflowFailure, "origin"):
            MODULE.require_publication_origin(workspace)

        subprocess.run(
            [
                "git",
                "-C",
                str(workspace),
                "remote",
                "set-url",
                "origin",
                "https://github.com/abuzucom/pi-neapple-pizza.git",
            ],
            check=True,
        )
        MODULE.require_publication_origin(workspace)

    def test_bundle_rejects_python_under_scripts(self) -> None:
        manifest_path = self.bundle / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="ascii"))
        manifest["changedPaths"] = ["scripts/json.py"]
        manifest_path.write_text(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="ascii",
            newline="\n",
        )

        with self.assertRaisesRegex(MODULE.WorkflowFailure, "donor Python"):
            MODULE.verify_candidate_bundle(self.bundle, "a" * 40)

    def test_bundle_rejects_control_characters_in_paths(self) -> None:
        manifest_path = self.bundle / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="ascii"))
        manifest["changedPaths"] = ["packages/agent/src/bad\npath.ts"]
        manifest_path.write_text(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="ascii",
            newline="\n",
        )

        with self.assertRaisesRegex(MODULE.WorkflowFailure, "unsafe changed path"):
            MODULE.verify_candidate_bundle(self.bundle, "a" * 40)

    def test_candidate_workspace_rejects_links_and_file_size_overflow(self) -> None:
        workspace = self.bundle / "candidate-workspace"
        workspace.mkdir()
        outside = self.bundle / "outside"
        outside.mkdir()
        (outside / "target.txt").write_text("target\n", encoding="ascii")
        link = workspace / "linked"
        if os.name == "nt":
            subprocess.run(
                ["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(outside)],
                check=True,
                capture_output=True,
            )
        else:
            link.symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(MODULE.WorkflowFailure, "escapes the workspace"):
            MODULE.validate_candidate_workspace(workspace, ["linked/target.txt"])

        oversized = workspace / "oversized.txt"
        oversized.write_bytes(b"xx")
        with patch.object(MODULE, "MAX_CANDIDATE_FILE_BYTES", 1):
            with self.assertRaisesRegex(MODULE.WorkflowFailure, "individual file byte bound"):
                MODULE.validate_candidate_workspace(workspace, ["oversized.txt"])

    def test_candidate_patch_capture_stops_at_the_byte_bound(self) -> None:
        workspace = self.bundle / "patch-workspace"
        workspace.mkdir()
        subprocess.run(["git", "init", "--quiet", str(workspace)], check=True)
        target = workspace / "candidate.txt"
        target.write_text("base\n", encoding="ascii")
        subprocess.run(["git", "-C", str(workspace), "add", "candidate.txt"], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(workspace),
                "-c",
                "user.name=Import Test",
                "-c",
                "user.email=import-test@example.invalid",
                "commit",
                "--quiet",
                "-m",
                "test: add patch fixture",
            ],
            check=True,
        )
        target.write_text("changed content that exceeds the patch test bound\n", encoding="ascii")
        report_directory = self.bundle / "patch-report"
        report_directory.mkdir()
        (report_directory / "import-report.json").write_text(
            json.dumps({"sourceSha": "b" * 40}) + "\n",
            encoding="ascii",
        )
        (report_directory / "approval-digests.json").write_text("{}\n", encoding="ascii")
        candidate_directory = self.bundle / "bounded-candidate"

        with patch.object(MODULE, "MAX_CANDIDATE_PATCH_BYTES", 16):
            with self.assertRaisesRegex(MODULE.WorkflowFailure, "patch exceeds"):
                MODULE.create_candidate_bundle(workspace, report_directory, candidate_directory)

        patch_path = candidate_directory / "candidate.patch"
        captured_size = patch_path.stat().st_size if patch_path.exists() else 0
        self.assertLessEqual(captured_size, 17)

    def test_pull_request_conflicts_remain_inside_code_fences(self) -> None:
        report_directory = self.bundle / "pull-request-report"
        report_directory.mkdir()
        conflict = "packages/agent/` owner/repo#1 `.ts"
        report = {
            "sourceSha": "b" * 40,
            "approvalDigests": {"import": "c" * 64},
            "conflicts": [conflict],
        }
        (report_directory / "import-report.json").write_text(
            json.dumps(report) + "\n",
            encoding="ascii",
        )

        body = MODULE.pull_request_body(report_directory)

        self.assertIn(f"- ``{conflict}``", body)
        self.assertNotIn(f"- `{conflict}`", body)


if __name__ == "__main__":
    unittest.main()
