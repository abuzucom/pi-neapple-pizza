"""Trace fail-closed boundaries without replacing adapter behavior."""
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("native_gate_boundaries", ROOT / "hooks/native_client_gate.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class NativeGateBoundaryTest(unittest.TestCase):
    """Real adapters reject invalid shapes and invalid child responses."""

    def test_native_input_shapes(self):
        payloads = [[], {}, {"tool_name": [], "tool_input": {}, "cwd": str(ROOT)},
                    {"tool_name": "Bash", "tool_input": {}, "cwd": "missing-policy-root"},
                    {"toolCall": [], "workspacePaths": [str(ROOT)]},
                    {"toolCall": {}, "workspacePaths": [str(ROOT), str(ROOT)]}]
        for payload in payloads:
            raw = json.dumps(payload).encode("utf-8")
            stream = io.TextIOWrapper(io.BytesIO(raw), encoding="utf-8")
            with patch.object(sys, "stdin", stream):
                with self.assertRaises(ValueError):
                    gate.read_call("antigravity")
        raw = b" " * (gate.MAX_PAYLOAD_BYTES + 1)
        stream = io.TextIOWrapper(io.BytesIO(raw), encoding="utf-8")
        with patch.object(sys, "stdin", stream):
            with self.assertRaises(ValueError):
                gate.read_call("codex")

    def test_child_response_boundaries(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "hooks").mkdir()
            hook = root / "hooks/fixture.py"
            cases = [("raise SystemExit(2)", True), ("print('[]')", True),
                     ("print('{}')", True), ("print('not-json')", True),
                     ("print('x' * 1048577)", True),
                     ("print('{\"hookSpecificOutput\":{\"permissionDecision\":\"ask\"}}')", True),
                     ("print('{\"hookSpecificOutput\":{\"permissionDecision\":\"unknown\"}}')", True),
                     ("print('{\"hookSpecificOutput\":{\"permissionDecision\":\"allow\"}}'); raise SystemExit(2)", True),
                     ("print('{\"hookSpecificOutput\":{\"permissionDecision\":\"allow\"}}')", False),
                     ("import time; time.sleep(1)", True)]
            with patch.object(gate, "ROOT", root):
                with self.assertRaises(ValueError):
                    gate.run_gate("absent.py", "Bash", {}, str(root))
                for source, rejected in cases:
                    hook.write_text(source, encoding="utf-8")
                    with self.subTest(source=source):
                        if source.startswith("import time"):
                            with patch.object(gate, "CHECK_TIMEOUT_SECONDS", 0.05):
                                with self.assertRaises(subprocess.TimeoutExpired):
                                    gate.run_gate(hook.name, "Bash", {}, str(root))
                        elif rejected:
                            with self.assertRaises(ValueError):
                                gate.run_gate(hook.name, "Bash", {}, str(root))
                        else:
                            gate.run_gate(hook.name, "Bash", {}, str(root))

    def test_shell_identity_and_directory_boundaries(self):
        with self.assertRaises(ValueError):
            gate.inspect_shell({"command": "echo hello", "workdir": "absent-policy-root"}, str(ROOT))
        sys.path.insert(0, str(ROOT / "scripts"))
        from trusted_git import resolve_git
        with tempfile.TemporaryDirectory() as temporary:
            subprocess.run([resolve_git(ROOT), "init", "--initial-branch=chore/identity-fixture", temporary],
                           check=True, capture_output=True)
            subprocess.run([resolve_git(ROOT), "-C", temporary, "config", "user.email", "invalid"],
                           check=True, capture_output=True)
            with self.assertRaises(ValueError):
                gate.inspect_identity("git commit -m test", temporary)
        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(gate, "ROOT", Path(temporary)):
                with self.assertRaises(ValueError):
                    gate.inspect_identity("echo hello", temporary)

    def test_file_and_patch_shape_boundaries(self):
        with self.assertRaises(ValueError):
            gate.inspect_file("Write", {}, str(ROOT))
        gate.inspect_file("Write", {"TargetFile": str(ROOT / "new-native-fixture.txt"),
                                   "Content": "plain text", "ReplacementContent": "plain text"}, str(ROOT))
        with tempfile.TemporaryDirectory() as temporary:
            protected = Path(temporary) / ".aws"
            protected.mkdir()
            (protected / "credentials").write_text("synthetic fixture only", encoding="utf-8")
            with self.assertRaises(ValueError):
                gate.inspect_file("Glob", {}, temporary)
        for text in ("*** Begin Patch\n", "*** Begin Patch\n*** End Patch",
                     "*** Begin Patch\n*** Delete File: README.md\n*** End Patch"):
            with self.assertRaises(ValueError):
                gate.inspect_patch({"command": text}, str(ROOT))


if __name__ == "__main__":
    unittest.main()
