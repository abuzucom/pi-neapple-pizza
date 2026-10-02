"""Cover bounded Windows shard cleanup."""

from __future__ import annotations

import subprocess
import unittest
from unittest.mock import patch

from scripts import check_hook_coverage


class Process:
    """Record parent termination after timed-out tree cleanup."""

    pid = 42

    def __init__(self) -> None:
        self.killed = False

    def kill(self) -> None:
        """Record the fallback termination."""
        self.killed = True

    def wait(self, timeout: float | None = None) -> None:
        """Accept the expected bounded wait."""


class HookCoverageTimeoutTest(unittest.TestCase):
    """Verify Windows cleanup does not wait forever for taskkill."""

    def test_windows_taskkill_timeout_terminates_parent(self) -> None:
        process = Process()
        with patch.object(check_hook_coverage.os, "name", "nt"):
            with patch.object(
                check_hook_coverage.subprocess,
                "run",
                side_effect=subprocess.TimeoutExpired("taskkill", 1),
            ) as run:
                check_hook_coverage.terminate_process_tree(process)

        self.assertTrue(process.killed)
        self.assertEqual(run.call_args.kwargs["timeout"], check_hook_coverage.PROCESS_SHUTDOWN_TIMEOUT_SECONDS)

