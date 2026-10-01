#!/usr/bin/env python3
"""Verify traced subprocess workers receive exclusive scheduling."""
import unittest

from scripts import check_hook_coverage as coverage_runner


class PersistentWorkerIsolationTest(unittest.TestCase):
    """Protect persistent JSON workers from traced process contention."""

    def test_persistent_worker_modules_are_exclusive(self):
        labels = (
            "test_block_destructive_bash.py::MassOperationTest",
            "test_block_destructive_powershell.py::CorpusTest",
            "test_cloudflare_pages_policy.py::CloudflarePolicyTest",
            "test_gate_parity.py::GateParityTest",
        )
        for label in labels:
            with self.subTest(label=label):
                self.assertTrue(coverage_runner.is_exclusive_shard(label))

    def test_unrelated_shards_remain_parallel(self):
        label = "test_check_ascii.py::AsciiPolicyTest"
        self.assertFalse(coverage_runner.is_exclusive_shard(label))


if __name__ == "__main__":
    unittest.main()
