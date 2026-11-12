"""Contract tests for A006: one immutable, reviewable owner for meaningful values."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = [sys.executable, str(ROOT / "examples/python/tools/acima_arch.py")]
TYPESCRIPT = ["node", str(ROOT / "examples/typescript/tools/acima-arch.mjs")]
FIXTURES = ROOT / "conformance/fixtures/value-ownership"


def run(command: list[str], root: Path, config: str = "acima.config.json"):
    result = subprocess.run(command + ["--root", str(root), "--config", config,
                                       "--format", "json"],
                            capture_output=True, text=True)
    if not result.stdout.strip():
        raise AssertionError(result.stderr or "the enforcer printed nothing")
    return result, json.loads(result.stdout)


def a006(report: dict) -> list[dict]:
    return [finding for finding in report["findings"] if finding["rule"] == "ACIMA-A006"]


def messages(report: dict) -> str:
    return "\n".join(finding["message"] for finding in a006(report))


class ValueOwnershipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.python_result, cls.python_report = run(PYTHON, FIXTURES / "python")
        cls.typescript_result, cls.typescript_report = run(TYPESCRIPT, FIXTURES / "typescript")

    def test_python_and_typescript_report_candidate_findings(self) -> None:
        for language, result, report in (
            ("python", self.python_result, self.python_report),
            ("typescript", self.typescript_result, self.typescript_report),
        ):
            with self.subTest(language=language):
                self.assertEqual(result.returncode, 0, report["findings"])
                findings = a006(report)
                self.assertEqual(len(findings), 8, findings)
                self.assertTrue(all(finding["classification"] == "candidate"
                                    for finding in findings))

    def test_inline_values_are_traced_to_receiving_parameters(self) -> None:
        for report in (self.python_report, self.typescript_report):
            inline = [finding["message"] for finding in a006(report)
                      if "embeds a meaningful value" in finding["message"]]
            self.assertEqual(len(inline), 3, inline)
            joined = "\n".join(inline).lower().replace("_", "")
            self.assertIn("retrylimit", joined)
            self.assertIn("requesttimeout", joined)

    def test_mutable_declarations_are_not_confirmed_semantic_violations(self) -> None:
        for report in (self.python_report, self.typescript_report):
            mutable = [finding for finding in a006(report)
                       if "declares the meaningful value" in finding["message"]]
            self.assertEqual(len(mutable), 1, mutable)
            self.assertIn("mutably", mutable[0]["message"])
            self.assertEqual(mutable[0]["classification"], "candidate")

    def test_immutable_named_declarations_are_not_findings(self) -> None:
        for report in (self.python_report, self.typescript_report):
            joined = messages(report)
            for name in ("MAX_ORDER_ATTEMPTS", "MAX_PAYMENT_ATTEMPTS",
                         "REQUEST_TIMEOUT_SECONDS", "REQUEST_TIMEOUT_MILLISECONDS",
                         "CACHE_TTL_SECONDS"):
                self.assertNotIn(name, joined)

    def test_incidental_loop_and_arithmetic_values_are_not_promoted(self) -> None:
        for report in (self.python_report, self.typescript_report):
            joined = messages(report).lower()
            for name in ("index", "total", "line"):
                self.assertNotIn(f"in {name}", joined)
            self.assertNotIn("range", joined)

    def test_equal_values_with_different_identifiers_remain_separate(self) -> None:
        for report in (self.python_report, self.typescript_report):
            joined = messages(report)
            self.assertNotIn("MAX_ORDER_ATTEMPTS", joined)
            self.assertNotIn("MAX_PAYMENT_ATTEMPTS", joined)
            self.assertNotIn("REQUEST_TIMEOUT", joined)

    def test_duplicate_candidates_are_review_only_and_module_scoped(self) -> None:
        for report in (self.python_report, self.typescript_report):
            duplicates = [finding for finding in a006(report)
                          if "same apparent meaning" in finding["message"]]
            self.assertEqual(len(duplicates), 2, duplicates)
            self.assertTrue(all(finding["classification"] == "candidate"
                                for finding in duplicates))
            self.assertTrue(all("highest common owner in module orders"
                                in finding["message"] for finding in duplicates))
            self.assertFalse(any(finding["path"].startswith("src/payments/")
                                 for finding in a006(report)))

    def test_configuration_and_secrets_are_classification_candidates(self) -> None:
        for report in (self.python_report, self.typescript_report):
            joined = messages(report)
            self.assertIn("ORDER_API_URL", joined)
            self.assertIn("deployment/runtime configuration", joined)
            self.assertIn("DB_PASSWORD", joined)
            self.assertIn("secret mechanism", joined)

    def test_a005_and_a002_behavior_is_preserved(self) -> None:
        _, report = run(PYTHON, ROOT / "examples/python", "acima.gallery.config.json")
        fired = {finding["rule"] for finding in report["findings"]}
        self.assertIn("ACIMA-A005", fired)
        self.assertFalse(report["execution"]["ACIMA-A002"]["executed"])
        self.assertTrue(report["execution"]["ACIMA-A005"]["executed"])
        self.assertTrue(report["execution"]["ACIMA-A006"]["executed"])

    def test_a006_fingerprint_identity_remains_stable(self) -> None:
        for report in (self.python_report, self.typescript_report):
            for finding in a006(report):
                expected = "sha256:" + hashlib.sha256(
                    f"{finding['rule']}\0{finding['path']}\0{finding['evidence']}".encode("utf-8")
                ).hexdigest()
                self.assertEqual(finding["fingerprint"], expected)

    def test_catalog_and_documentation_traceability(self) -> None:
        catalog = json.loads((ROOT / "tools/acima-spec/rules.json").read_text(encoding="utf-8"))
        rule = next(item for item in catalog["rules"] if item["id"] == "ACIMA-A006")
        self.assertEqual(rule["level"], "L3")
        self.assertEqual(rule["severity"], "warning")
        self.assertEqual(rule["severityRatchet"], {"to": "error", "at": "2.0.0"})
        self.assertEqual(rule["automation"], "automated")
        self.assertIn("immutable", rule["title"].lower() + rule["summary"].lower())
        self.assertIn("semantic", rule["summary"].lower())
        self.assertEqual(len(catalog["rules"]), 56)

        chapter = (ROOT / "docs/standard/14-values-and-configuration.md").read_text(
            encoding="utf-8").lower()
        for phrase in ("receiving identifier", "semantic identity", "immutable declaration",
                       "highest appropriate", "same name", "uncertain"):
            self.assertIn(phrase, chapter)
        rule_page = (ROOT / "docs/rules/autonomy.md").read_text(encoding="utf-8").lower()
        self.assertIn("acima-a006 · meaningful value", rule_page)
        self.assertIn("candidate", rule_page)

        skill = (ROOT / "skills/acima-adoption/references/70-corrections.md").read_text(
            encoding="utf-8").lower()
        for phrase in ("receiving identifier", "highest appropriate", "same value",
                       "same name", "secret", "uncertain"):
            self.assertIn(phrase, skill)


if __name__ == "__main__":
    unittest.main()
