#!/usr/bin/env python3
"""Cover the cost and the scope of the infrastructure sweep.

The sweep reads every YAML and JSON file in a search root to test whether it
holds a Kubernetes manifest. A sweep over a large repository costs seconds,
so the sweep skips a directory the repository ignores. A directory that
carries a protected marker, or that holds one at the first level below it,
stays in the sweep, so an ignore rule cannot hide a credential directory.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))
import _gate_core

PROTECTED_FILE = "main.tf"
PROTECTED_CONTENT = "terraform {}\n"


class IgnoredDirectoryScanTest(unittest.TestCase):
    """The sweep skips a repository ignored directory."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = temporary.name
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=self.root,
                       check=True, capture_output=True)
        Path(self.root, ".gitignore").write_text("build/\n", encoding="utf-8")
        self.clear_caches()

    def clear_caches(self):
        """Drop the per-process caches the sweep and the manifest read hold."""
        _gate_core._ignored_directory_paths.cache_clear()
        _gate_core._cached_manifest_text.cache_clear()

    def ignore(self, pattern: str):
        """Add one ignore rule to the fixture repository."""
        with open(Path(self.root, ".gitignore"), "a", encoding="utf-8") as handle:
            handle.write(pattern + "\n")

    def write_protected_file(self, directory: str):
        """Write one protected file into a directory of the fixture."""
        target = Path(self.root, directory)
        target.mkdir(parents=True, exist_ok=True)
        Path(target, PROTECTED_FILE).write_text(PROTECTED_CONTENT, encoding="utf-8")

    def test_ignored_directory_is_skipped(self):
        self.write_protected_file("build")
        self.assertFalse(_gate_core.tree_contains_protected_infrastructure(self.root))

    def test_unignored_directory_is_scanned(self):
        self.write_protected_file("src")
        self.assertTrue(_gate_core.tree_contains_protected_infrastructure(self.root))

    def test_ignored_marker_path_is_scanned(self):
        credentials = Path(self.root, ".aws")
        credentials.mkdir()
        Path(credentials, "credentials").write_text("[default]\n", encoding="utf-8")
        self.ignore(".aws/")
        self.assertTrue(_gate_core.tree_contains_protected_infrastructure(self.root))

    def test_ignored_marker_child_is_scanned(self):
        vault = Path(self.root, "vault")
        (vault / ".aws").mkdir(parents=True)
        Path(vault, ".aws", "credentials").write_text("[default]\n", encoding="utf-8")
        self.ignore("vault/")
        self.assertTrue(_gate_core.tree_contains_protected_infrastructure(self.root))

    def test_root_without_repository_is_scanned(self):
        with tempfile.TemporaryDirectory() as outside:
            Path(outside, PROTECTED_FILE).write_text(PROTECTED_CONTENT, encoding="utf-8")
            self.clear_caches()
            self.assertTrue(_gate_core.tree_contains_protected_infrastructure(outside))

    def test_missing_git_scans_every_directory(self):
        self.write_protected_file("build")
        with patch.object(_gate_core, "_trusted_config_executable", side_effect=OSError("no git")):
            self.clear_caches()
            self.assertTrue(_gate_core.tree_contains_protected_infrastructure(self.root))

    def test_rejected_resolver_scans_every_directory(self):
        self.write_protected_file("build")
        with patch.object(_gate_core, "_trusted_config_executable", side_effect=ValueError("rejected")):
            self.clear_caches()
            self.assertTrue(_gate_core.tree_contains_protected_infrastructure(self.root))

    def test_failed_query_scans_every_directory(self):
        self.write_protected_file("build")
        with patch.object(_gate_core, "_repository_top_level", return_value=self.root):
            with patch.object(_gate_core, "_run_ignored_path_query", side_effect=OSError("failed")):
                self.clear_caches()
                self.assertTrue(_gate_core.tree_contains_protected_infrastructure(self.root))

    def test_oversized_answer_scans_every_directory(self):
        self.write_protected_file("build")
        with patch.object(_gate_core, "MAX_IGNORED_PATH_BYTES", 1):
            self.clear_caches()
            self.assertTrue(_gate_core.tree_contains_protected_infrastructure(self.root))

    def test_empty_top_level_scans_every_directory(self):
        self.write_protected_file("build")
        with patch.object(_gate_core, "_repository_top_level", return_value=""):
            self.clear_caches()
            self.assertTrue(_gate_core.tree_contains_protected_infrastructure(self.root))

    def test_ignored_file_is_skipped(self):
        Path(self.root, "notes.log").write_text("line\n", encoding="utf-8")
        self.ignore("*.log")
        self.clear_caches()
        self.assertFalse(_gate_core.tree_contains_protected_infrastructure(self.root))

    def test_unreadable_ignored_directory_is_scanned(self):
        self.write_protected_file("build")
        real_scandir = os.scandir

        def refuse(path="."):
            if os.path.realpath(path) == os.path.realpath(str(Path(self.root, "build"))):
                raise PermissionError(f"synthetic refusal: {path}")
            return real_scandir(path)

        with patch.object(_gate_core.os, "scandir", side_effect=refuse):
            self.clear_caches()
            self.assertTrue(_gate_core.tree_contains_protected_infrastructure(self.root))

    def test_a_linked_root_still_skips(self):
        # Git reports the resolved repository root. A linked path must reach
        # the same answer, or no directory is skipped on a host where the
        # temporary path carries a link.
        self.write_protected_file("build")
        link = Path(self.root).parent / (Path(self.root).name + "-link")
        self.addCleanup(self.remove_link, link)
        self.create_link(link, Path(self.root))
        self.clear_caches()
        self.assertFalse(_gate_core.tree_contains_protected_infrastructure(str(link)))

    def create_link(self, link: Path, target: Path):
        """Create a directory link that needs no elevated privilege."""
        if os.name == "nt":
            environment = dict(os.environ)
            environment["MSYS_NO_PATHCONV"] = "1"
            result = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(link), str(target)],
                capture_output=True, text=True, env=environment, check=False)
            if result.returncode == 0:
                return
        link.symlink_to(target, target_is_directory=True)

    def remove_link(self, link: Path):
        """Remove the directory link the fixture created."""
        if link.is_symlink():
            link.unlink()
        elif link.exists():
            shutil.rmtree(link, ignore_errors=True)


class IgnoredPathQueryTest(unittest.TestCase):
    """The ignored path query stays bounded and reports its failures."""

    def test_failed_query_raises(self):
        with self.assertRaises(OSError):
            _gate_core._run_ignored_path_query(
                [sys.executable, "-c", "raise SystemExit(3)"], os.getcwd(),
                _gate_core._config_read_environment(dict(os.environ)))

    def test_timed_out_query_raises(self):
        with patch.object(_gate_core, "IGNORED_PATH_QUERY_TIMEOUT_SECONDS", 0.05):
            with self.assertRaises(OSError):
                _gate_core._run_ignored_path_query(
                    [sys.executable, "-c", "import time; time.sleep(5)"],
                    os.getcwd(),
                    _gate_core._config_read_environment(dict(os.environ)))

    def test_empty_answer_names_no_top_level(self):
        with patch.object(_gate_core, "_run_ignored_path_query", return_value=b""):
            self.assertEqual(_gate_core._repository_top_level("git", os.getcwd(), {}), "")

    def test_unreadable_output_raises(self):
        class UnreadablePipe:
            def read(self, size):
                raise OSError("synthetic read failure")

        class FailingProcess:
            returncode = 0
            stdout = UnreadablePipe()
            stderr = None

            def poll(self):
                return 0

            def wait(self, timeout=None):
                return 0

            def kill(self):
                return None

            def __enter__(self):
                return self

            def __exit__(self, *arguments):
                return False

        with patch.object(_gate_core.subprocess, "Popen", return_value=FailingProcess()):
            with self.assertRaises(OSError):
                _gate_core._run_ignored_path_query(["git"], os.getcwd(), {})


class ManifestReadCacheTest(unittest.TestCase):
    """The manifest prefix is read once per file state."""

    def test_manifest_text_follows_the_file(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root, "manifest.yaml")
            path.write_text("apiVersion: v1\nkind: ConfigMap\n", encoding="utf-8")
            self.assertTrue(_gate_core.is_protected_infrastructure_path(str(path), root))
            path.write_text("plain: value\n", encoding="utf-8")
            self.assertFalse(_gate_core.is_protected_infrastructure_path(str(path), root))


if __name__ == "__main__":
    unittest.main()
