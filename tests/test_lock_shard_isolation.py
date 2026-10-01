"""Require repository lock tests to run without cross-test interference."""
import unittest

from scripts import check_hook_coverage


class LockShardIsolationTest(unittest.TestCase):
    """The coverage runner serializes tests that share the activation lock."""

    def test_repository_lock_shards_are_exclusive(self):
        required = {
            "test_runtime_reader_lock.py::RuntimeReaderLockTest",
            "test_runtime_shared_readers.py::RuntimeSharedReadersTest",
        }
        self.assertTrue(required.issubset(check_hook_coverage.EXCLUSIVE_TEST_SHARDS))


if __name__ == "__main__":
    unittest.main()
