"""Verify complete-bundle integrity before activation."""
import hashlib
import tempfile
import unittest
from pathlib import Path

from tools.adopt_agents_bundle import checked_target, verify_files


class AdoptionBundleTest(unittest.TestCase):
    """Exercise real path and content checks."""

    def test_parent_escape_is_rejected_before_access(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(ValueError):
                checked_target(Path(temporary), "../outside")

    def test_tampered_file_prevents_activation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact = root / "artifact.txt"
            artifact.write_bytes(b"modified")
            approved = hashlib.sha256(b"approved").hexdigest()
            with self.assertRaises(ValueError):
                verify_files(root, {"artifact.txt": approved})

    def test_complete_content_verification_accepts_matching_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact = root / "artifact.txt"
            artifact.write_bytes(b"approved")
            approved = hashlib.sha256(b"approved").hexdigest()
            verify_files(root, {"artifact.txt": approved})

    def test_symlink_target_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.txt"
            source.write_bytes(b"approved")
            link = root / "link.txt"
            try:
                link.symlink_to(source)
            except OSError:
                with self.assertRaises(ValueError):
                    checked_target(root, "../source.txt")
                return
            with self.assertRaises(ValueError):
                checked_target(root, "link.txt")
