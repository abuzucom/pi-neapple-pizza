from __future__ import annotations

import importlib.util
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "trusted_gh.py"
SPEC = importlib.util.spec_from_file_location("trusted_gh_workflow", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load trusted GitHub wrapper")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class TrustedGhWorkflowModeTest(unittest.TestCase):
    def workflow_environment(self) -> dict[str, str]:
        return {
            "GITHUB_ACTIONS": "true",
            "GITHUB_EVENT_NAME": "workflow_dispatch",
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_SHA": "a" * 40,
            "GITHUB_REPOSITORY": "abuzucom/pi-neapple-pizza",
            "GITHUB_TRIGGERING_ACTOR": "itsjustatank",
        }

    def test_requires_manual_dispatch_from_main(self) -> None:
        environment = self.workflow_environment()
        environment["GITHUB_REF"] = "refs/heads/feature"
        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaisesRegex(ValueError, "main"):
                MODULE.validate_workflow_context(ROOT)

    def test_resolves_triggering_actor_through_public_user_api(self) -> None:
        response = subprocess.CompletedProcess(
            [],
            0,
            stdout="654939\titsjustatank\n",
            stderr="",
        )
        with patch.dict(os.environ, self.workflow_environment(), clear=True):
            with patch.object(MODULE, "run_gh", return_value=response) as run_gh:
                account = MODULE.workflow_actor(ROOT)
        self.assertEqual({"id": 654939, "login": "itsjustatank"}, account)
        self.assertEqual(
            ["api", "users/itsjustatank", "--jq", "[.id,.login]|@tsv"],
            run_gh.call_args.args[1],
        )

    def test_allows_only_draft_creation_and_required_reads(self) -> None:
        allowed = [
            "pr",
            "create",
            "--draft",
            "--base",
            "main",
            "--head",
            "chore/import-pi-update-2026-10-01",
            "--title",
            "chore: import pi update 2026-10-01",
            "--body-file",
            "/tmp/body.md",
        ]
        self.assertTrue(MODULE.workflow_command_allowed(allowed))
        self.assertFalse(MODULE.workflow_command_allowed(["pr", "create", "--label", "security"]))
        self.assertFalse(
            MODULE.workflow_command_allowed(
                [
                    "pr",
                    "create",
                    "--draft",
                    "--base",
                    "main",
                    "--head",
                    "chore/import-pi-update-2026-10-01-extra",
                    "--title",
                    "chore: import pi update 2026-10-01-extra",
                    "--body-file",
                    "/tmp/body.md",
                ]
            )
        )
        invalid_date = [
            "chore/import-pi-update-2026-99-99"
            if value == "chore/import-pi-update-2026-10-01"
            else "chore: import pi update 2026-99-99"
            if value == "chore: import pi update 2026-10-01"
            else value
            for value in allowed
        ]
        self.assertFalse(MODULE.workflow_command_allowed(invalid_date))
        self.assertFalse(MODULE.workflow_command_allowed(["pr", "ready", "1"]))
        self.assertFalse(MODULE.workflow_command_allowed(["pr", "merge", "1"]))

    def test_allows_only_exact_pull_request_read_shapes(self) -> None:
        branch_read = [
            "pr",
            "list",
            "--state",
            "all",
            "--head",
            "chore/import-pi-update-2026-10-01",
            "--json",
            "url",
            "--limit",
            "1",
        ]
        digest_read = [
            "pr",
            "list",
            "--state",
            "all",
            "--search",
            f"{'a' * 64} in:body",
            "--json",
            "url",
            "--limit",
            "1",
        ]
        self.assertTrue(MODULE.workflow_command_allowed(branch_read))
        self.assertTrue(MODULE.workflow_command_allowed(digest_read))
        self.assertFalse(MODULE.workflow_command_allowed([*branch_read, "--head", "main"]))
        bad_json = ["labels" if value == "url" else value for value in branch_read]
        self.assertFalse(MODULE.workflow_command_allowed(bad_json))

    def test_draft_body_file_is_limited_to_the_publication_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            runner_temp = Path(temporary_directory)
            report_directory = runner_temp / "pi-import-publication"
            report_directory.mkdir()
            body = report_directory / "pull-request-body.md"
            body.write_text("reviewed body", encoding="ascii")
            unrelated = runner_temp / "unrelated.txt"
            unrelated.write_text("private runner data", encoding="ascii")
            environment = {**self.workflow_environment(), "RUNNER_TEMP": str(runner_temp)}

            with patch.dict(os.environ, environment, clear=True):
                self.assertEqual(body.resolve(), MODULE.validate_workflow_body_file(str(body)))
                with self.assertRaisesRegex(ValueError, "publication report"):
                    MODULE.validate_workflow_body_file(str(unrelated))


if __name__ == "__main__":
    unittest.main()
