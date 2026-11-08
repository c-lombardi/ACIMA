"""Regression tests for discovery completeness in the adoption preflight.

These exist because two controlled repositories exposed unsafe behavior:

* a source-bearing tree with no discoverable boundary exited 0 with only warnings;
* a tree with eighteen candidate modules was silently truncated to sixteen.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = ROOT / "skills/acima-adoption/scripts/preflight.py"


def run_preflight(directory: Path) -> tuple[int, dict]:
    result = subprocess.run(
        [sys.executable, str(PREFLIGHT), "--project", str(directory), "--format", "json"],
        cwd=ROOT, capture_output=True, text=True,
    )
    payload = json.loads(result.stdout) if result.stdout.strip() else {}
    return result.returncode, payload


class PreflightDiscoveryTests(unittest.TestCase):
    def test_source_without_discoverable_units_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory(prefix="acima-no-units-") as temp:
            directory = Path(temp)
            (directory / "main.py").write_text('print("hello")\n', encoding="utf-8")
            code, payload = run_preflight(directory)
            self.assertEqual(code, 1)
            checks = {check["id"]: check for check in payload["checks"]}
            self.assertEqual(checks["TGT-004"]["status"], "fail")
            self.assertIn("TGT-004", payload["blockers"])

    def test_more_than_sixteen_candidates_are_all_proposed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="acima-many-units-") as temp:
            directory = Path(temp)
            source = directory / "src"
            source.mkdir()
            for index in range(18):
                module = source / f"mod{index:02d}"
                module.mkdir()
                (module / "file.py").write_text("VALUE = 1\n", encoding="utf-8")
            code, payload = run_preflight(directory)
            self.assertEqual(code, 0)
            self.assertEqual(len(payload["proposedUnits"]), 18)
            checks = {check["id"]: check for check in payload["checks"]}
            self.assertEqual(checks["TGT-004"]["status"], "pass")
            self.assertEqual(checks["TGT-005"]["status"], "pass")


if __name__ == "__main__":
    unittest.main()
