from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_VERSION = "5.0.12"


class BraceExpansionOverrideTest(unittest.TestCase):
    def test_manifests_pin_the_approved_override(self) -> None:
        manifests = (
            ROOT / "package.json",
            ROOT / "packages" / "coding-agent" / "package.json",
            ROOT / "packages" / "coding-agent" / "install-lock" / "package.json",
        )
        for path in manifests:
            with self.subTest(path=path):
                value = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(EXPECTED_VERSION, value["overrides"]["brace-expansion"])

    def test_release_locks_resolve_the_approved_version(self) -> None:
        locks = (
            ROOT / "package-lock.json",
            ROOT / "packages" / "coding-agent" / "npm-shrinkwrap.json",
            ROOT / "packages" / "coding-agent" / "install-lock" / "package-lock.json",
        )
        for path in locks:
            with self.subTest(path=path):
                value = json.loads(path.read_text(encoding="utf-8"))
                package = value["packages"]["node_modules/brace-expansion"]
                self.assertEqual(EXPECTED_VERSION, package["version"])
                self.assertIn(f"brace-expansion-{EXPECTED_VERSION}.tgz", package["resolved"])


if __name__ == "__main__":
    unittest.main()
