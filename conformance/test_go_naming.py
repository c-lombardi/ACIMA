"""Go N002 coverage for generic responsibility names."""
from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "conformance/fixtures/naming/go"
GO = ["go", "run", "./tools/archtest"]


def run(root: Path, config: str = "acima.config.json") -> dict:
    result = subprocess.run(
        GO + ["--root", str(root), "--config", config, "--format", "json"],
        cwd=ROOT / "examples/go", capture_output=True, text=True,
    )
    if not result.stdout.strip():
        raise AssertionError(result.stderr or "the Go enforcer printed nothing")
    return json.loads(result.stdout)


class GoNamingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("go") is None:
            raise unittest.SkipTest("go toolchain is not installed")

    def test_gallery_fires_n002_at_the_naming_fixture(self) -> None:
        payload = run(ROOT / "examples/go", "acima.gallery.config.json")
        findings = [finding for finding in payload["findings"]
                    if finding["rule"] == "ACIMA-N002"]
        self.assertEqual({finding["path"] for finding in findings},
                         {"violations/naming_conventions.go"})
        self.assertTrue(payload["execution"]["ACIMA-N002"]["executed"])
        self.assertFalse(payload["execution"]["ACIMA-N001"]["executed"])

    def test_exact_names_and_suffixes_only(self) -> None:
        payload = run(ROOT / "examples/go", "acima.gallery.config.json")
        messages = [finding["message"] for finding in payload["findings"]
                    if finding["rule"] == "ACIMA-N002"]
        for generic in ("OrderHelper", "Manager", "PaymentProcessor"):
            self.assertTrue(any(generic in message for message in messages), generic)
        for precise in ("OrderService", "RequestHandler", "OrderFactory"):
            self.assertFalse(any(precise in message for message in messages), precise)

    def test_clean_fixture_reports_no_findings(self) -> None:
        payload = run(FIXTURE)
        self.assertEqual(payload["findings"], [])
        self.assertTrue(payload["execution"]["ACIMA-N002"]["executed"])
        self.assertFalse(payload["execution"]["ACIMA-N001"]["executed"])
        self.assertFalse(payload["execution"]["ACIMA-N003"]["executed"])


if __name__ == "__main__":
    unittest.main()
