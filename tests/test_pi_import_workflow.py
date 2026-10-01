from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "pi_import_workflow.py"
SPEC = importlib.util.spec_from_file_location("pi_import_workflow", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load pi import workflow module")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PiImportWorkflowTest(unittest.TestCase):
    def test_apply_requires_full_commit_sha(self) -> None:
        with self.assertRaisesRegex(MODULE.WorkflowFailure, "full lowercase commit SHA"):
            MODULE.validate_ref("main", "apply")

    def test_preview_rejects_unsafe_ref_shapes(self) -> None:
        for candidate in ("-main", "refs/heads/a..b", "refs/heads/a@{b", "refs/heads/a.lock"):
            with self.subTest(candidate=candidate):
                with self.assertRaises(MODULE.WorkflowFailure):
                    MODULE.validate_ref(candidate, "preview")

    def test_policy_paths_cannot_reach_publication(self) -> None:
        for candidate in ("AGENTS.md", ".github/workflows/replace.yml", "hooks/gate.py", "tools/import.py"):
            with self.subTest(candidate=candidate):
                with self.assertRaisesRegex(MODULE.WorkflowFailure, "protected policy path"):
                    MODULE.validate_changed_path(candidate)

    def test_documentation_commit_is_last(self) -> None:
        groups = MODULE.commit_groups(
            [
                "docs/pi-import.json",
                "packages/agent/src/index.ts",
                "packages/ai/src/index.ts",
                "package.json",
                "scripts/check.mjs",
            ]
        )
        self.assertEqual("docs: record pi import", groups[-1][0])
        self.assertEqual(["docs/pi-import.json"], groups[-1][1])

    def test_workflow_is_manual_draft_only_and_label_free(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "import-pi-upstream.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("pull_request:", workflow)
        self.assertNotIn("schedule:", workflow)
        self.assertIn("environment: upstream-import", workflow)
        self.assertIn('"--draft"', (ROOT / "tools" / "pi_import_workflow.py").read_text(encoding="utf-8"))
        self.assertNotIn("--label", workflow)
        self.assertNotIn('"--label"', (ROOT / "tools" / "pi_import_workflow.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
