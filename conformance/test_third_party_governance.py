"""The third-party seam: a positive fixture with zero findings, and a swap drill that can fail."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "conformance/fixtures/third-party/python"
ENFORCER = ROOT / "examples/python/tools/acima_arch.py"
DRILL = ROOT / "conformance/swap_drill.py"


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, *args], capture_output=True, text=True)


class ThirdPartyGovernanceTests(unittest.TestCase):
    def test_positive_fixture_reports_zero_findings(self) -> None:
        result = run(str(ENFORCER), "--root", str(FIXTURE), "--format", "json")
        self.assertIn(result.returncode, (0,), result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["findings"], [])
        self.assertGreater(payload["sourceFiles"], 0)
        for rule in ("ACIMA-L005", "ACIMA-L006", "ACIMA-L007", "ACIMA-D010", "ACIMA-G006"):
            self.assertTrue(payload["execution"][rule]["executed"], rule)

    def test_swap_drill_passes_on_the_positive_fixture(self) -> None:
        result = run(str(DRILL), "--project", str(FIXTURE))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("compile against the port", result.stdout)

    def test_swap_drill_fails_when_the_application_imports_the_vendor(self) -> None:
        with tempfile.TemporaryDirectory(prefix="acima-swap-negative-") as temporary:
            copy = Path(temporary) / "python"
            shutil.copytree(FIXTURE, copy)
            service = copy / "src/notes/impl/service.py"
            service.write_text("import monaco_editor\n" + service.read_text(encoding="utf-8"),
                               encoding="utf-8")
            result = run(str(DRILL), "--project", str(copy))
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("imports the vendor", result.stderr + result.stdout)

    def test_the_drill_is_not_vacuous_without_a_port_reference(self) -> None:
        with tempfile.TemporaryDirectory(prefix="acima-swap-unused-") as temporary:
            copy = Path(temporary) / "python"
            shutil.copytree(FIXTURE, copy)
            service = copy / "src/notes/impl/service.py"
            service.write_text('"""No port here."""\n\n\ndef edit(note: str) -> str:\n'
                               '    """Ignore the seam."""\n    return note\n', encoding="utf-8")
            result = run(str(DRILL), "--project", str(copy))
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("references the port", result.stderr + result.stdout)


if __name__ == "__main__":
    unittest.main()
