from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


IMPORTER = load_module("import_pi_upstream_security", ROOT / "tools" / "import_pi_upstream.py")
WORKFLOW = load_module("pi_import_workflow_security", ROOT / "tools" / "pi_import_workflow.py")


class ImporterSecurityTest(unittest.TestCase):
    def create_directory_link(self, link: Path, target: Path) -> None:
        if os.name == "nt":
            result = subprocess.run(
                ["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target)],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if result.returncode != 0:
                raise RuntimeError(f"cannot create test junction: {result.stderr}")
            return
        link.symlink_to(target, target_is_directory=True)

    def test_dependency_versions_must_be_exact_semver(self) -> None:
        accepted = ("1.2.3", "1.2.3-alpha.1", "1.2.3+build.4", "1.2.3-rc.1+build.4")
        rejected = (
            "^1.2.3",
            "~1.2.3",
            ">=1.2.3",
            "1.x",
            "latest",
            "workspace:*",
            "file:../package",
            "git+https://example.test/repository.git",
            f"1.2.3-{'a' * 300}",
        )
        for value in accepted:
            with self.subTest(value=value):
                self.assertEqual(value, IMPORTER.pin_manifest_version(value))
        for value in rejected:
            with self.subTest(value=value):
                with self.assertRaisesRegex(IMPORTER.ImportFailure, "exact semantic version"):
                    IMPORTER.pin_manifest_version(value)

    def test_donor_python_files_under_scripts_are_blockers(self) -> None:
        for path in ("scripts/json.py", "scripts/subprocess.py", "scripts/tool.py"):
            with self.subTest(path=path):
                with self.assertRaisesRegex(IMPORTER.ImportFailure, "Python files under scripts"):
                    IMPORTER.import_path_allowed(path)

    def test_oversized_tree_entry_fails_before_blob_capture(self) -> None:
        record = (
            b"100644 blob "
            + b"a" * 40
            + b" "
            + str(IMPORTER.MAX_FILE_BYTES + 1).encode("ascii")
            + b"\tpackages/agent/src/large.ts\0"
        )
        completed = type("Completed", (), {"stdout": record})()
        with patch.object(IMPORTER, "run_git", return_value=completed):
            with patch.object(IMPORTER, "read_blobs") as read_blobs:
                with self.assertRaisesRegex(IMPORTER.ImportFailure, "individual file byte bound"):
                    IMPORTER.load_tree("a" * 40)
        read_blobs.assert_not_called()

    def test_porcelain_rename_and_copy_records_keep_both_paths(self) -> None:
        records = b"R  new name.ts\0old name.ts\0C  copy.ts\0source.ts\0"
        self.assertEqual(
            ["new name.ts", "old name.ts", "copy.ts", "source.ts"],
            WORKFLOW.parse_porcelain_paths(records),
        )

    def test_candidate_paths_reject_protected_case_variants(self) -> None:
        for path in (".GitHub/workflows/import.yml", "HOOKS/gate.py", "Agents.md"):
            with self.subTest(path=path):
                with self.assertRaisesRegex(WORKFLOW.WorkflowFailure, "protected policy path"):
                    WORKFLOW.validate_changed_path(path)

    def test_workspace_reads_and_deletes_reject_linked_parents(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            workspace = root / "workspace"
            outside = root / "outside"
            workspace.mkdir()
            outside.mkdir()
            outside_file = outside / "target.ts"
            outside_file.write_text("outside\n", encoding="utf-8")
            self.create_directory_link(workspace / "packages", outside)

            with self.assertRaisesRegex(IMPORTER.ImportFailure, "escapes the workspace"):
                IMPORTER.local_digest(workspace, "packages/target.ts")
            with self.assertRaisesRegex(IMPORTER.ImportFailure, "escapes the workspace"):
                IMPORTER.remove_imported_file(workspace, "packages/target.ts")
            self.assertTrue(outside_file.is_file())


if __name__ == "__main__":
    unittest.main()
