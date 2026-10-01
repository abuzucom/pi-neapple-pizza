"""Exercise review policy provenance against real immutable Git revisions."""
import hashlib
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from tests.retrying_temp_directory import RetryingTemporaryDirectory
from tests.test_immutable_compliance import _initialize_repo, _write_file, _commit_all

ROOT = Path(__file__).resolve().parent.parent


class ReviewBaseProvenanceTest(unittest.TestCase):
    """Pull request policy changes remain untrusted review evidence."""

    def test_head_policy_cannot_replace_trusted_context(self):
        with RetryingTemporaryDirectory() as temporary:
            root = Path(temporary)
            _initialize_repo(root)
            _write_file(root, "AGENTS.md", "Approved base policy\n")
            base = _commit_all(root, "test: add approved base")
            _write_file(root, "AGENTS.md", "Untrusted head policy\n")
            head = _commit_all(root, "test: change review target")
            event = root / "event.json"
            event.write_text(json.dumps({"pull_request": {"title": "Review fixture", "body": ""}}),
                             encoding="utf-8")
            environment = dict(os.environ)
            environment.update({"EVENT_PATH": str(event), "BASE_SHA": base, "HEAD_SHA": head})
            result = subprocess.run([sys.executable, str(ROOT / "ci/build_pr_case.py")],
                                    cwd=root, env=environment, capture_output=True, text=True,
                                    timeout=15, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            envelope = json.loads((root / "case_text.txt").read_text(encoding="utf-8"))
            context = envelope["TRUSTED_HOOK_CONTEXT"]
            self.assertEqual(context["text"], "Approved base policy\n")
            self.assertEqual(context["source_revision"], base)
            self.assertEqual(context["sha256"], hashlib.sha256(context["text"].encode()).hexdigest())
            self.assertIn("Untrusted head policy", envelope["REVIEW_TARGET"]["text"])


if __name__ == "__main__":
    unittest.main()
