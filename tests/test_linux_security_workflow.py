"""Regression coverage for Linux security workflow boundaries."""

from __future__ import annotations

import unittest
from pathlib import Path


WORKFLOW_PATH = Path(__file__).resolve().parents[1] / ".github/workflows/sync-check.yml"


class LinuxSecurityWorkflowTest(unittest.TestCase):
    """Verify the workflow keeps blocking security validation isolated."""

    def test_linux_security_job_uses_read_only_permissions(self) -> None:
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

        self.assertIn("linux-security:", workflow)
        self.assertIn("contents: read", workflow)
        self.assertIn("npm ci --ignore-scripts", workflow)
        self.assertIn("npm run build:offline", workflow)
        self.assertIn("enforcement-concurrency-security.test.ts", workflow)

