"""Exercise native Git execution after real hook publication."""
import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.trusted_git import resolve_git
from tools.bundle_transaction import prepare_transaction, publish_transaction


class NativeGitHookTest(unittest.TestCase):
    """Verify delivery through Git without creating a commit."""

    def test_published_hook_runs_through_native_git(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            executable = resolve_git(root)
            subprocess.run([executable, "-C", str(root), "init", "-q",
                            "--initial-branch=chore/verify-native-hooks"], check=True)
            subprocess.run([executable, "-C", str(root), "config", "core.hooksPath", ".git/hooks"], check=True)
            source = root / "hook-source"
            source.write_bytes(b"#!/bin/sh\nprintf 'native hook delivery\\n'\n")
            relative = ".git/hooks/pre-commit"
            files = {relative: hashlib.sha256(source.read_bytes()).hexdigest()}
            transaction = prepare_transaction(root, {relative: source}, files)
            publish_transaction(root, transaction)
            result = subprocess.run([executable, "-C", str(root), "hook", "run", "pre-commit"],
                                    capture_output=True, text=True, encoding="utf-8", check=True)
            self.assertEqual(result.stdout, "")
            self.assertEqual(result.stderr.strip(), "native hook delivery")
