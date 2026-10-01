"""Verify review eligibility and activation prerequisites."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


class SecurityRemediationTest(unittest.TestCase):
    """Check the actual workflow script and unsupported-runtime entry point."""

    def test_fake_check_cannot_suppress_review(self):
        workflow = yaml.safe_load((ROOT / ".github/workflows/security-review-pr.yml").read_text())
        script = workflow["jobs"]["resolve-pr"]["steps"][0]["with"]["script"]
        program = """
const outputs = {};
const core = {setOutput: (key, value) => outputs[key] = value,
              setFailed: (message) => {throw new Error(message)}};
const context = {repo: {owner: 'abuzucom', repo: 'pi-neapple-pizza'},
                 payload: {workflow_run: {head_sha: 'a'.repeat(40)}}};
const repo = {full_name: 'abuzucom/pi-neapple-pizza', clone_url: 'https://github.com/abuzucom/pi-neapple-pizza.git'};
const pr = {number: 1, base: {repo, sha: 'b'.repeat(40)}, head: {repo, sha: 'a'.repeat(40)}};
const github = {rest: {repos: {listPullRequestsAssociatedWithCommit: 'prs'}, checks: {listForRef: 'checks'}},
    paginate: async (method) => method === 'prs' ? [pr] : [{status: 'completed', output: {summary: 'VERDICT: APPROVE'}}]};
(async () => {
SCRIPT
process.stdout.write(JSON.stringify(outputs));
})();
""".replace("SCRIPT", script)
        result = subprocess.run(["node", "-e", program], capture_output=True, text=True,
                                encoding="utf-8", timeout=15, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        outputs = json.loads(result.stdout)
        self.assertEqual(outputs["same_repository"], "true")
        self.assertNotEqual(outputs.get("already_reviewed"), "true")
        self.assertNotIn("already_reviewed", workflow["jobs"]["review"]["if"])

    def test_python_minimum_rejects_before_activation_io(self):
        code = ("import sys; sys.version_info=(3,11,0); "
                "from tools.bundle_transaction import checked_target; "
                "from pathlib import Path; checked_target(Path('absent-runtime-root'), 'file')")
        result = subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                                capture_output=True, text=True, encoding="utf-8", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Python 3.12", result.stderr)
        self.assertFalse((ROOT / "absent-runtime-root").exists())


if __name__ == "__main__":
    unittest.main()
