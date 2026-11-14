"""Go G006 coverage for approved direct dependencies in go.mod."""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "conformance/fixtures/go-g006"
GO = ["go", "run", "./tools/archtest"]


def run(root: Path, config: str = "acima.config.json") -> dict:
    result = subprocess.run(
        GO + ["--root", str(root), "--config", config, "--format", "json"],
        cwd=ROOT / "examples/go", capture_output=True, text=True,
    )
    if not result.stdout.strip():
        raise AssertionError(result.stderr or "the Go enforcer printed nothing")
    return json.loads(result.stdout)


class GoDependencyPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("go") is None:
            raise unittest.SkipTest("go toolchain is not installed")

    def test_clean_fixture_ignores_approved_and_indirect_requirements(self) -> None:
        payload = run(FIXTURES / "clean")
        self.assertEqual(payload["findings"], [])
        self.assertTrue(payload["execution"]["ACIMA-G006"]["executed"])

    def test_violating_fixture_reports_only_the_direct_unapproved_requirement(self) -> None:
        payload = run(FIXTURES / "violating")
        self.assertTrue(payload["execution"]["ACIMA-G006"]["executed"])
        findings = [finding for finding in payload["findings"]
                    if finding["rule"] == "ACIMA-G006"]
        self.assertEqual(len(findings), 1, payload["findings"])
        finding = findings[0]
        self.assertEqual(finding["path"], "go.mod")
        self.assertEqual(finding["line"], 7)
        self.assertEqual(finding["evidence"], "example.com/unapproved")
        self.assertIn("example.com/unapproved", finding["message"])
        self.assertNotIn("example.com/approved", finding["message"])
        self.assertNotIn("example.com/indirect", finding["message"])

    def test_absent_policy_reports_not_executed_instead_of_passing_silently(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "violating"
            shutil.copytree(FIXTURES / "violating", root)
            config = json.loads((root / "acima.config.json").read_text(encoding="utf-8"))
            config.pop("approvedDependencies")
            (root / "acima.config.json").write_text(json.dumps(config), encoding="utf-8")
            payload = run(root)
        self.assertEqual(payload["findings"], [])
        self.assertFalse(payload["execution"]["ACIMA-G006"]["executed"])
        self.assertIn("approvedDependencies", payload["execution"]["ACIMA-G006"]["reason"])

    def test_gallery_checks_the_configured_manifest(self) -> None:
        payload = run(ROOT / "examples/go", "acima.gallery.config.json")
        findings = [finding for finding in payload["findings"]
                    if finding["rule"] == "ACIMA-G006"]
        self.assertEqual(len(findings), 1, findings)
        self.assertEqual(findings[0]["path"], "violations/g006/go.mod")
        self.assertEqual(findings[0]["evidence"], "example.com/unapproved")


if __name__ == "__main__":
    unittest.main()
