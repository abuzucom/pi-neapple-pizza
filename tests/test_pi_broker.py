#!/usr/bin/env python3
"""Cover the policy broker that decides pi tool calls.

The broker pins the digest of every gate in the decision path, records every
decision in an append-only log, and consumes one approval per act. The tests
run the broker as a command and read its answer.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BROKER = ROOT / "broker" / "pi_broker.py"
ADAPTER = ROOT / "hooks" / "pi_client_gate.py"
TIMEOUT_SECONDS = 120


def run_broker(state: Path, command: str, request: dict = None) -> dict:
    """Run one broker command and return its answer."""
    environment = dict(os.environ)
    environment["PI_BROKER_STATE"] = str(state)
    payload = json.dumps(request) if request is not None else ""
    result = subprocess.run(
        [sys.executable, str(BROKER), command], input=payload,
        capture_output=True, text=True, encoding="utf-8", timeout=TIMEOUT_SECONDS,
        env=environment, cwd=str(ROOT), check=False)
    return json.loads(result.stdout)


class BrokerStateTest(unittest.TestCase):
    """The broker answers from the state directory it was given."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.state = Path(temporary.name).resolve()
        self.repository = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.repository, True)
        for arguments in (["init", "-q", "-b", "main"],
                          ["config", "user.name", "Test User"],
                          ["config", "user.email", "test@example.com"]):
            subprocess.run(["git", *arguments], cwd=str(self.repository),
                           check=True, capture_output=True)
        (self.repository / "README.md").write_text("# Fixture\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=str(self.repository),
                       check=True, capture_output=True)
        subprocess.run(["git", "commit", "-q", "-m", "feat: add fixture"],
                       cwd=str(self.repository), check=True, capture_output=True)
        subprocess.run(["git", "checkout", "-q", "-b", "feat/broker-test"],
                       cwd=str(self.repository), check=True, capture_output=True)

    def pin(self) -> dict:
        """Record the current digests in the state directory."""
        return run_broker(self.state, "pin")

    def decide(self, request: dict) -> dict:
        """Answer one request through the broker."""
        return run_broker(self.state, "decide", request)

    def test_pin_records_the_decision_path(self):
        answer = self.pin()
        self.assertGreater(answer["pinned"], 0)
        self.assertEqual(answer["shared_mismatched"], [])
        status = run_broker(self.state, "status")
        self.assertTrue(status["pinned"])
        self.assertEqual(status["pin_failure"], "")

    def test_decision_without_a_pin_denies(self):
        answer = self.decide({
            "tool": "bash", "arguments": {"command": "echo hello"},
            "cwd": str(self.repository)})
        self.assertEqual(answer["decision"], "deny")
        self.assertIn("pin", answer["reason"])

    def test_ordinary_command_is_allowed_and_recorded(self):
        self.pin()
        answer = self.decide({
            "tool": "bash", "arguments": {"command": "echo hello"},
            "cwd": str(self.repository)})
        self.assertEqual(answer["decision"], "allow")
        status = run_broker(self.state, "status")
        self.assertEqual(status["records"], 1)

    def test_destructive_command_is_denied_and_recorded(self):
        self.pin()
        answer = self.decide({
            "tool": "bash", "arguments": {"command": "rm -rf /"},
            "cwd": str(self.repository)})
        self.assertEqual(answer["decision"], "deny")
        status = run_broker(self.state, "status")
        self.assertEqual(status["records"], 1)

    def test_unknown_tool_is_denied(self):
        self.pin()
        answer = self.decide({
            "tool": "web_search", "arguments": {"query": "anything"},
            "cwd": str(self.repository)})
        self.assertEqual(answer["decision"], "deny")

    def test_malformed_request_is_denied(self):
        self.pin()
        answer = self.decide({"tool": "bash", "cwd": str(self.repository)})
        self.assertEqual(answer["decision"], "deny")

    def test_ask_waits_for_an_approval(self):
        self.pin()
        existing = ROOT / "tests" / "test_pi_broker.py"
        request = {"tool": "write",
                   "arguments": {"path": str(existing), "content": "changed\n"},
                   "cwd": str(self.repository)}
        answer = self.decide(request)
        self.assertEqual(answer["decision"], "ask")
        approval = run_broker(self.state, "approve", request)
        confirmed = self.decide({**request, "approval": approval["approval"]})
        self.assertEqual(confirmed["decision"], "allow")

    def test_approval_binds_one_request(self):
        self.pin()
        first = {"tool": "write",
                 "arguments": {"path": str(ROOT / "tests" / "test_pi_broker.py"),
                               "content": "changed\n"},
                 "cwd": str(self.repository)}
        second = {"tool": "write",
                  "arguments": {"path": str(ROOT / "tests" / "test_pi_client_gate.py"),
                                "content": "changed\n"},
                  "cwd": str(self.repository)}
        approval = run_broker(self.state, "approve", first)
        answer = self.decide({**second, "approval": approval["approval"]})
        self.assertNotEqual(answer["decision"], "allow")

    def test_an_approval_covers_one_act(self):
        self.pin()
        request = {"tool": "write",
                   "arguments": {"path": str(ROOT / "tests" / "test_pi_broker.py"),
                                 "content": "changed\n"},
                   "cwd": str(self.repository)}
        approval = run_broker(self.state, "approve", request)
        first = self.decide({**request, "approval": approval["approval"]})
        self.assertEqual(first["decision"], "allow")
        second = self.decide({**request, "approval": approval["approval"]})
        self.assertEqual(second["decision"], "ask")

    def test_the_log_links_every_record(self):
        self.pin()
        self.decide({"tool": "bash", "arguments": {"command": "echo one"},
                     "cwd": str(self.repository)})
        self.decide({"tool": "bash", "arguments": {"command": "echo two"},
                     "cwd": str(self.repository)})
        lines = [json.loads(line) for line in
                 (self.state / "decisions.jsonl").read_text(encoding="utf-8").splitlines()
                 if line.strip()]
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0]["previous"], "")
        self.assertEqual(lines[1]["previous"], lines[0]["digest"])

    def test_the_state_directory_sits_outside_the_repository(self):
        environment = dict(os.environ)
        environment.pop("PI_BROKER_STATE", None)
        result = subprocess.run(
            [sys.executable, str(BROKER), "status"], capture_output=True,
            text=True, encoding="utf-8", timeout=TIMEOUT_SECONDS,
            env=environment, cwd=str(ROOT), check=False)
        answer = json.loads(result.stdout)
        self.assertFalse(str(Path(answer["state"]).resolve()).startswith(str(ROOT)))

    def test_the_state_directory_is_private(self):
        if os.name == "nt":
            self.skipTest("the mode bits do not apply on this platform")
        self.pin()
        mode = (self.state).stat().st_mode & 0o777
        self.assertEqual(mode, 0o700)

    def test_a_truncated_log_breaks_the_chain(self):
        self.pin()
        self.decide({"tool": "bash", "arguments": {"command": "echo one"},
                     "cwd": str(self.repository)})
        self.decide({"tool": "bash", "arguments": {"command": "echo two"},
                     "cwd": str(self.repository)})
        log = self.state / "decisions.jsonl"
        lines = log.read_text(encoding="utf-8").splitlines()
        log.write_text(lines[1] + "\n", encoding="utf-8")
        answer = self.decide({"tool": "bash", "arguments": {"command": "echo three"},
                              "cwd": str(self.repository)})
        self.assertEqual(answer["decision"], "deny")
        self.assertIn("chain", answer["reason"])


class ChangedGateTest(unittest.TestCase):
    """A gate that changed after the pin loses the decision."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.state = Path(temporary.name).resolve()
        self.tree = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.tree, True)
        shutil.copytree(ROOT / "hooks", self.tree / "hooks")
        (self.tree / "broker").mkdir()
        shutil.copy(BROKER, self.tree / "broker" / "pi_broker.py")

    def run_broker(self, command: str, request: dict = None) -> dict:
        """Run the copied broker and return its answer."""
        environment = dict(os.environ)
        environment["PI_BROKER_STATE"] = str(self.state)
        payload = json.dumps(request) if request is not None else ""
        result = subprocess.run(
            [sys.executable, str(self.tree / "broker" / "pi_broker.py"), command],
            input=payload, capture_output=True, text=True, encoding="utf-8",
            timeout=TIMEOUT_SECONDS, env=environment, cwd=str(self.tree), check=False)
        return json.loads(result.stdout)

    def test_a_changed_gate_denies_the_call(self):
        self.run_broker("pin")
        gate = self.tree / "hooks" / "_gate_core.py"
        gate.write_text(gate.read_text(encoding="utf-8") + "\n# changed\n", encoding="utf-8")
        answer = self.run_broker("decide", {
            "tool": "bash", "arguments": {"command": "echo hello"},
            "cwd": str(self.tree)})
        self.assertEqual(answer["decision"], "deny")
        self.assertIn("changed after the pin", answer["reason"])

    def test_a_new_gate_denies_the_call(self):
        self.run_broker("pin")
        (self.tree / "hooks" / "extra_gate.py").write_text("print('x')\n", encoding="utf-8")
        answer = self.run_broker("decide", {
            "tool": "bash", "arguments": {"command": "echo hello"},
            "cwd": str(self.tree)})
        self.assertEqual(answer["decision"], "deny")
        self.assertIn("does not record", answer["reason"])


if __name__ == "__main__":
    unittest.main()
