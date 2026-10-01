from __future__ import annotations

import hashlib
import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "import_pi_upstream.py"
SPEC = importlib.util.spec_from_file_location("import_pi_upstream_analysis", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load pi importer module")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def entry(path: str, content: bytes) -> object:
    digest = hashlib.sha256(content).hexdigest()
    return MODULE.DonorEntry(
        path=path,
        object_id="a" * 40,
        donor_sha256=digest,
        size=len(content),
        sha256=digest,
        content=content,
    )


class PiImportAnalysisTest(unittest.TestCase):
    def test_unique_equal_content_is_reported_as_rename(self) -> None:
        content = b"export const value = 1;\n"
        renames = MODULE.detect_renames(
            {"packages/a/old.ts": entry("packages/a/old.ts", content)},
            {"packages/a/new.ts": entry("packages/a/new.ts", content)},
        )
        self.assertEqual([{"from": "packages/a/old.ts", "to": "packages/a/new.ts"}], renames)

    def test_ambiguous_equal_content_is_not_reported_as_rename(self) -> None:
        content = b"same\n"
        renames = MODULE.detect_renames(
            {
                "packages/a/one.ts": entry("packages/a/one.ts", content),
                "packages/a/two.ts": entry("packages/a/two.ts", content),
            },
            {"packages/a/new.ts": entry("packages/a/new.ts", content)},
        )
        self.assertEqual([], renames)

    def test_content_scan_uses_digest_and_checker_revision_cache(self) -> None:
        token_prefix = b"gh" + b"p_"
        candidate = entry("packages/a/token.ts", b"const token = '" + token_prefix + b"abcdefghijklmnopqrstuvwxyz';\n")
        first = MODULE.scan_content(candidate)
        second = MODULE.scan_content(candidate)
        self.assertIs(first, second)
        self.assertTrue(first["secret"])


if __name__ == "__main__":
    unittest.main()
