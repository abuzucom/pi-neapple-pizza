from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IMPORT_WORKFLOW = ROOT / ".github" / "workflows" / "import-pi-upstream.yml"
SYNC_WORKFLOW = ROOT / ".github" / "workflows" / "sync-check.yml"
DOWNLOAD_ARTIFACT_PIN = "3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c"
PRODUCT_VALIDATION = ROOT / "tools" / "run_pi_product_validation.py"


class ImportWorkflowSecurityTest(unittest.TestCase):
    def test_apply_uses_three_separate_jobs(self) -> None:
        workflow = IMPORT_WORKFLOW.read_text(encoding="utf-8")
        for job in ("prepare-apply:", "validate-apply:", "publish-apply:"):
            self.assertIn(job, workflow)
        self.assertIn("environment: upstream-import", workflow)
        self.assertEqual(1, workflow.count("GH_TOKEN:"))

    def test_entry_jobs_fail_non_main_dispatches(self) -> None:
        workflow = IMPORT_WORKFLOW.read_text(encoding="utf-8")
        preview_job = workflow.split("  preview:", 1)[1].split("  prepare-apply:", 1)[0]
        prepare_job = workflow.split("  prepare-apply:", 1)[1].split("  validate-apply:", 1)[0]
        for job in (preview_job, prepare_job):
            self.assertIn("if: github.ref != 'refs/heads/main'", job)
            self.assertIn("run: exit 1", job)

    def test_every_checkout_uses_dispatch_sha_without_credentials(self) -> None:
        workflow = IMPORT_WORKFLOW.read_text(encoding="utf-8")
        checkout_count = workflow.count("uses: actions/checkout@")
        self.assertGreaterEqual(checkout_count, 4)
        self.assertEqual(checkout_count, workflow.count("ref: ${{ github.sha }}"))
        self.assertEqual(checkout_count, workflow.count("persist-credentials: false"))
        self.assertNotIn("persist-credentials: true", workflow)

    def test_candidate_download_uses_the_approved_full_pin(self) -> None:
        workflow = IMPORT_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn(f"actions/download-artifact@{DOWNLOAD_ARTIFACT_PIN} # v8.0.1", workflow)

    def test_linux_security_job_has_no_write_permission(self) -> None:
        workflow = SYNC_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("linux-security:", workflow)
        self.assertIn("permissions:\n      contents: read", workflow)
        self.assertIn("npm ci --ignore-scripts", workflow)
        self.assertIn("npm run build:offline", workflow)

    def test_apply_dependency_install_is_report_only_evidence(self) -> None:
        workflow = IMPORT_WORKFLOW.read_text(encoding="utf-8")
        validate_job = workflow.split("  validate-apply:", 1)[1].split("  publish-apply:", 1)[0]
        validation_script = PRODUCT_VALIDATION.read_text(encoding="utf-8")

        self.assertNotIn("Install pinned dependencies", validate_job)
        self.assertIn('(\"install\", [NPM_EXECUTABLE, \"ci\", \"--ignore-scripts\"])', validation_script)


if __name__ == "__main__":
    unittest.main()
