#!/usr/bin/env python3
"""Run every product validation and retain all failures for a draft import PR."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path


MAX_CAPTURE_BYTES = 262_144
NPM_EXECUTABLE = "npm.cmd" if os.name == "nt" else "npm"
VALIDATIONS = (
    ("biome", [NPM_EXECUTABLE, "exec", "--", "biome", "check", "--error-on-warnings", "."]),
    ("typescript", [NPM_EXECUTABLE, "exec", "--", "tsc", "--noEmit"]),
    ("build", [NPM_EXECUTABLE, "run", "build:offline"]),
    ("tests", [NPM_EXECUTABLE, "test"]),
)


def bounded_text(content: bytes) -> str:
    """Decode one bounded tail for diagnostic artifacts."""
    retained = content[-MAX_CAPTURE_BYTES:]
    return retained.decode("utf-8", errors="replace")


def run_validations() -> dict[str, object]:
    """Run every fixed validation without hiding later failures."""
    results: list[dict[str, object]] = []
    for name, command in VALIDATIONS:
        completed = subprocess.run(command, check=False, capture_output=True)
        results.append(
            {
                "name": name,
                "status": completed.returncode,
                "stdout": bounded_text(completed.stdout),
                "stderr": bounded_text(completed.stderr),
            }
        )
    return {"failures": [result["name"] for result in results if result["status"] != 0], "results": results}


def main() -> int:
    """Write deterministic validation evidence and keep draft delivery reachable."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    report = run_validations()
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(report, ensure_ascii=True, indent=2) + "\n", encoding="ascii", newline="\n")
    for failure in report["failures"]:
        print(f"validation failed: {failure}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
