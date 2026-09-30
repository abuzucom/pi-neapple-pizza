"""Exercise stage defaults and malformed Git-hook input."""
import unittest

from tools.git_policy_hook import select_checks, parse_push_records


class HookAdapterBoundariesTest(unittest.TestCase):
    """Keep canonical stage coverage and validate revisions before Git use."""

    def test_default_stage_retains_changelog_on_push(self):
        checks = select_checks("pre-push", [], [])
        self.assertIn(["scripts/check_changelog.py", "--staged"], checks)

    def test_commit_message_default_retains_always_run_checks(self):
        checks = select_checks("commit-msg", [".git/COMMIT_EDITMSG"], [".git/COMMIT_EDITMSG"])
        self.assertIn(["scripts/check_policy_size.py"], checks)

    def test_invalid_push_revision_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_push_records("refs/heads/work --exec=payload refs/heads/work " + "0" * 40)

    def test_valid_push_record_preserves_identifiers(self):
        local = "a" * 40
        remote = "0" * 40
        self.assertEqual(parse_push_records(f"refs/heads/work {local} refs/heads/work {remote}\n"),
                         [(local, remote)])

    def test_extra_record_fields_are_rejected(self):
        with self.assertRaises(ValueError):
            parse_push_records("refs/heads/work " + "a" * 40 + " refs/heads/work " + "0" * 40 + " extra")
