"""Regression tests for level-scoped, complete assessment coverage."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import date, timedelta
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "conformance"))
import acima_claim  # noqa: E402

sys.path.insert(0, str(ROOT / "tools"))
import acima  # noqa: E402

CATALOG = acima_claim.load_catalog(ROOT)


def execution_map(level: str) -> dict:
    return {
        rule["id"]: {"executed": rule["automation"] == "automated",
                     **({} if rule["automation"] == "automated" else
                        {"reason": "requires manual evidence"})}
        for rule in acima_claim.required_rules(CATALOG, level)
    }


class AssessmentCoverageTests(unittest.TestCase):
    def test_coverage_denominator_and_manual_partition_follow_selected_level(self) -> None:
        expected = {
            "L1": (27, 26, 1),
            "L2": (37, 32, 5),
            "L3": (55, 41, 14),
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for level, (required, automated, manual) in expected.items():
                coverage = acima._assessment_rule_coverage(
                    root, CATALOG, level, execution_map(level))
                self.assertEqual(coverage["required"], required)
                self.assertEqual(coverage["automated"]["required"], automated)
                self.assertEqual(coverage["automated"]["checked"], automated)
                self.assertEqual(coverage["manual"]["required"], manual)
                self.assertEqual(coverage["manual"]["acceptedEvidence"], 0)
                self.assertEqual(coverage["accountedFor"], automated)
                self.assertEqual(coverage["notAssessed"], manual)
                self.assertEqual(len(coverage["rules"]), required)
                self.assertFalse(coverage["complete"])

    def test_manual_rule_cannot_be_counted_as_deterministically_executed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            execution = execution_map("L1")
            manual_rule = next(rule["id"] for rule in acima_claim.required_rules(CATALOG, "L1")
                               if rule["automation"] == "manual")
            execution[manual_rule] = {"executed": True}
            coverage = acima._assessment_rule_coverage(root, CATALOG, "L1", execution)
            self.assertEqual(coverage["automated"]["checked"], 26)
            self.assertEqual(coverage["manual"]["acceptedEvidence"], 0)
            self.assertEqual(coverage["notAssessed"], 1)
            item = next(item for item in coverage["rules"] if item["rule"] == manual_rule)
            self.assertEqual(item["status"], "manual_evidence_required")

    def test_valid_manual_evidence_is_counted_only_for_its_required_rule(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rule = next(item for item in acima_claim.required_rules(CATALOG, "L1")
                        if item["automation"] == "manual")
            artifact = root / "reviews" / "l1.md"
            artifact.parent.mkdir()
            artifact.write_text("review completed", encoding="utf-8")
            evidence = {
                "evidence": [{
                    "rule": rule["id"], "scope": "repository", "owner": "team",
                    "reviewer": "reviewer", "method": "review",
                    "artifact": "reviews/l1.md", "reviewedOn": date.today().isoformat(),
                    "expires": (date.today() + timedelta(days=180)).isoformat(),
                    "result": "pass",
                }]
            }
            (root / ".acima").mkdir()
            (root / ".acima/manual-evidence.json").write_text(
                json.dumps(evidence), encoding="utf-8")
            coverage = acima._assessment_rule_coverage(
                root, CATALOG, "L1", execution_map("L1"))
            self.assertEqual(coverage["manual"]["acceptedEvidence"], 1)
            self.assertEqual(coverage["accountedFor"], 27)
            self.assertEqual(coverage["notAssessed"], 0)
            self.assertTrue(coverage["complete"])

    def test_invalid_manual_evidence_is_not_counted_and_explains_why(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rule = next(item for item in acima_claim.required_rules(CATALOG, "L1")
                        if item["automation"] == "manual")
            (root / ".acima").mkdir()
            evidence = {"evidence": [{
                "rule": rule["id"], "scope": "repository", "owner": "team",
                "reviewer": "reviewer", "method": "review", "artifact": "missing.md",
                "reviewedOn": date.today().isoformat(),
                "expires": (date.today() + timedelta(days=30)).isoformat(), "result": "pass",
            }]}
            (root / ".acima/manual-evidence.json").write_text(
                json.dumps(evidence), encoding="utf-8")
            coverage = acima._assessment_rule_coverage(
                root, CATALOG, "L1", execution_map("L1"))
            self.assertEqual(coverage["manual"]["acceptedEvidence"], 0)
            self.assertEqual(coverage["notAssessed"], 1)
            self.assertTrue(any("artifact does not exist" in item
                                for item in coverage["manual"]["missingEvidence"][0]["reason"].split("; ")))
            self.assertTrue(coverage["invalidEvidence"])

    def test_omitted_automated_rule_is_unassessed_with_reason(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            execution = execution_map("L1")
            missing = next(rule["id"] for rule in acima_claim.required_rules(CATALOG, "L1")
                           if rule["automation"] == "automated")
            del execution[missing]
            coverage = acima._assessment_rule_coverage(Path(directory), CATALOG, "L1", execution)
            self.assertEqual(coverage["automated"]["checked"], 25)
            self.assertEqual(coverage["notAssessed"], 2)
            self.assertEqual(coverage["automated"]["notExecuted"][0]["rule"], missing)
            self.assertIn("omitted", coverage["automated"]["notExecuted"][0]["reason"])

    def test_assessment_without_unit_map_still_accounts_for_every_required_rule(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src").mkdir()
            (root / "src/app.py").write_text("VALUE = 1\n", encoding="utf-8")
            code, report = acima.assess_project(root)
            self.assertEqual(code, 0)
            self.assertEqual(report["verdict"], "NEEDS_UNIT_MAP")
            coverage = report["coverage"]
            self.assertEqual(coverage["required"], 27)
            self.assertEqual(coverage["accountedFor"], 0)
            self.assertEqual(coverage["notAssessed"], 27)
            self.assertEqual(coverage["automated"]["notExecuted"][0]["reason"],
                             report["verdictMeaning"])
            self.assertFalse(coverage["executionAvailable"])

    def test_enforcer_level_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src").mkdir()
            (root / "src/app.py").write_text("VALUE = 1\n", encoding="utf-8")
            (root / "acima.config.json").write_text(json.dumps({
                "standard": "1.0.0", "level": "L1", "language": "python", "mode": "base",
                "units": [],
            }), encoding="utf-8")
            payload = {"level": "L2", "execution": execution_map("L2"),
                       "findings": [], "sourceFiles": 1, "standard": "1.0.0"}
            with patch.object(acima, "run_enforcer", return_value=(0, payload, "")):
                code, report = acima.assess_project(root)
            self.assertEqual(code, 2)
            self.assertEqual(report["verdict"], "INVALID_ASSESSMENT")
            self.assertIn("measured level 'L2'", report["error"])
            self.assertIn("requested 'L1'", report["error"])

    def test_standard_requires_level_scoped_accounting_and_separates_coverage_from_conformance(self) -> None:
        standard = (ROOT / "docs/standard/08-conformance.md").read_text(encoding="utf-8")
        self.assertIn("Rules above the selected level are outside that assessment", standard)
        self.assertIn("An enforcer's `executed: true` flag cannot satisfy a manual rule", standard)
        self.assertIn("Complete coverage is not a conformance claim", standard)

    def test_read_only_assessment_uses_declared_level_and_reports_complete_accounting(self) -> None:
        code, report = acima.assess_project(ROOT / "examples/python")
        self.assertEqual(code, 0, report.get("error"))
        self.assertEqual(report["requestedLevel"], "L3")
        coverage = report["coverage"]
        self.assertEqual(coverage["level"], "L3")
        self.assertEqual(coverage["required"], 55)
        self.assertEqual(coverage["automated"]["checked"], 41)
        self.assertEqual(coverage["manual"]["required"], 14)
        self.assertEqual(coverage["notAssessed"], 14)
        self.assertFalse(coverage["complete"])
        markdown = acima.assess_markdown(report)
        self.assertIn("Required at `L3`: **55**", markdown)
        self.assertIn("Manual evidence: **0/14 accepted**", markdown)
        self.assertIn("Manual evidence still required: **14**", markdown)
        self.assertIn("Coverage complete: **no**", markdown)
        self.assertIn("does not mean the repository has no findings", markdown)

    def test_explicit_level_overrides_declared_level_for_assessment_coverage(self) -> None:
        code, report = acima.assess_project(ROOT / "examples/python", level="L1")
        self.assertEqual(code, 0, report.get("error"))
        self.assertEqual(report["requestedLevel"], "L1")
        self.assertEqual(report["coverage"]["required"], 27)
        self.assertEqual(report["coverage"]["automated"]["required"], 26)
        self.assertEqual(report["coverage"]["manual"]["required"], 1)


if __name__ == "__main__":
    unittest.main()
