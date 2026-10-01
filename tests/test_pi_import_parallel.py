#!/usr/bin/env python3
"""Verify bounded deterministic import generation."""
import threading
import unittest

from tools import import_pi_upstream as importer


class BoundedParallelGenerationTest(unittest.TestCase):
    """Exercise the real bounded generation coordinator."""

    def test_parallel_map_preserves_order_and_worker_bound(self):
        barrier = threading.Barrier(importer.MAX_GENERATION_WORKERS)
        active = 0
        maximum_active = 0
        lock = threading.Lock()

        def observe(value: int) -> int:
            nonlocal active, maximum_active
            with lock:
                active += 1
                maximum_active = max(maximum_active, active)
            barrier.wait(timeout=5)
            with lock:
                active -= 1
            return value * 2

        values = list(range(importer.MAX_GENERATION_WORKERS))
        self.assertEqual(
            importer.bounded_parallel_map(observe, values),
            [value * 2 for value in values],
        )
        self.assertEqual(maximum_active, importer.MAX_GENERATION_WORKERS)

    def test_none_is_data_instead_of_an_exhaustion_marker(self):
        self.assertEqual(
            importer.bounded_parallel_map(lambda value: value, [None, 1]),
            [None, 1],
        )


if __name__ == "__main__":
    unittest.main()
