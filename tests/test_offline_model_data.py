"""Verify checked-in model data supports offline validation."""

from __future__ import annotations

import subprocess
import unittest
import os
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
NPM_EXECUTABLE = "npm.cmd" if os.name == "nt" else "npm"


class OfflineModelDataTest(unittest.TestCase):
    """Exercise the real generated model-data validator."""

    def test_generated_model_data_is_valid(self) -> None:
        result = subprocess.run(
            [NPM_EXECUTABLE, "--prefix", "packages/ai", "run", "check:model-data"],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
