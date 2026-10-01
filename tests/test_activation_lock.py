"""Exercise exclusive activation through the operating-system file lock."""
import tempfile
import unittest
from pathlib import Path

from tools.bundle_transaction import exclusive_activation


class ActivationLockTest(unittest.TestCase):
    """Prevent overlapping publishers from sharing a retained transaction."""

    def test_second_publisher_cannot_acquire_lock(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with exclusive_activation(root):
                with self.assertRaises(OSError):
                    with exclusive_activation(root):
                        self.fail("concurrent publisher acquired the lock")

    def test_completed_publisher_releases_lock(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with exclusive_activation(root):
                self.assertTrue((root / ".gate-staging" / "activation.lock").is_file())
            with exclusive_activation(root):
                self.assertTrue((root / ".gate-staging" / "activation.lock").is_file())
