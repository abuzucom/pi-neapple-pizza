#!/usr/bin/env python3
"""Test pi-only governance paths that the gate-integrity check protects."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import check_gate_pr_integrity as integrity

PI_GOVERNANCE_PATHS = (
    "tools/git_policy_hook.py",
    "tools/git-hooks/pre-commit",
    "tools/git-hooks/commit-msg",
    "tools/git-hooks/pre-push",
    "tools/adopt_agents_bundle.py",
    "tools/bundle_transaction.py",
    "scripts/check_native_hook_launchers.py",
)


class PiGovernancePathTest(unittest.TestCase):
    """Pi enforcement code needs the same approval as canonical gates."""

    def test_each_pi_governance_path_requires_approval(self) -> None:
        for path in PI_GOVERNANCE_PATHS:
            with self.subTest(path=path):
                self.assertTrue(integrity.requires_approval([path]))

    def test_case_variant_of_pi_path_requires_approval(self) -> None:
        self.assertTrue(integrity.requires_approval(["Tools/Git_Policy_Hook.py"]))
        self.assertTrue(integrity.requires_approval(["TOOLS/git-hooks/pre-push"]))

    def test_unrelated_tools_path_does_not_require_approval(self) -> None:
        self.assertFalse(integrity.requires_approval(["tools/hook-trace/sitecustomize.py"]))
        self.assertFalse(integrity.requires_approval(["tools/new_helper.py"]))


if __name__ == "__main__":
    unittest.main()
