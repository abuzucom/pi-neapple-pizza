"""Verify canonical Git-hook selection and argument forwarding."""
import unittest

from tools.git_policy_hook import select_checks


class GitPolicyHookTest(unittest.TestCase):
    """Exercise the approved configuration without subprocess mocks."""

    def test_yaml_checker_receives_changed_workflow(self):
        checks = select_checks("pre-commit", [".github/workflows/sync-check.yml"], [])
        selected = next(check for check in checks if check[0] == "scripts/check_persist_credentials.py")
        self.assertEqual(selected[1:], [".github/workflows/sync-check.yml"])

    def test_pre_push_retains_identity_and_external_reference_checks(self):
        checks = select_checks("pre-push", [], [])
        self.assertIn(["scripts/check_git_identity.py", "--strict", "--unpushed"], checks)
        self.assertIn(["scripts/check_external_pr_refs.py", "--unpushed"], checks)

    def test_unknown_stage_is_rejected(self):
        with self.assertRaises(ValueError):
            select_checks("unknown", [], [])
