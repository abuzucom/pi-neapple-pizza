#!/usr/bin/env python3
"""Verify Windows parity checks use a neutral project directory."""
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "sync-check.yml"


class WindowsParityRootTest(unittest.TestCase):
    """Keep repository content outside neutral parity command fixtures."""

    def test_parity_step_uses_prepared_clean_root(self):
        workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
        steps = workflow["jobs"]["tests-windows"]["steps"]
        setup = next(
            step for step in steps
            if step.get("name") == "Prepare clean gate parity root"
        )
        parity = next(
            step for step in steps
            if step.get("name") == "Verify trusted GitHub CLI routing"
        )
        self.assertIn("gate-parity-clean", setup["run"])
        self.assertEqual(
            parity["env"]["CLAUDE_PROJECT_DIR"],
            "${{ runner.temp }}\\gate-parity-clean",
        )


if __name__ == "__main__":
    unittest.main()
