"""Exercise bounded review capture through real child processes."""
import sys
import unittest
from ci.build_pr_case import capture_bounded


class ReviewCaptureLimitsTest(unittest.TestCase):
    """Reject oversized output and terminate stalled review inputs."""

    def test_valid_output(self):
        output = capture_bounded([sys.executable, "-c", "print('review')"], 100, 5)
        self.assertEqual(output.strip(), "review")

    def test_excess_output(self):
        with self.assertRaises(RuntimeError):
            capture_bounded([sys.executable, "-c", "print('x' * 1024)"], 100, 5)

    def test_timeout(self):
        with self.assertRaises(RuntimeError):
            capture_bounded([sys.executable, "-c", "import time; time.sleep(5)"], 100, 0.1)

    def test_invalid_limit(self):
        with self.assertRaises(ValueError):
            capture_bounded([sys.executable, "-c", "raise SystemExit(0)"], 0, 5)


if __name__ == "__main__":
    unittest.main()
