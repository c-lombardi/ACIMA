"""Regression tests for evidence-backed review of every ACIMA catalog rule."""
from __future__ import annotations

import json
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "conformance"))
from acima_claim import load_catalog
from qualitative_review import validate_review
sys.path.insert(0, str(ROOT / "tools"))
import acima

CATALOG = load_catalog(ROOT)
CATALOG_SHA256 = hashlib.sha256((ROOT / "tools/acima-spec/rules.json").read_bytes()).hexdigest()


def valid_document(root: Path) -> dict:
    source = root / "src" / "sample.py"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("# Architecture ownership evidence\nclass Sample:\n    pass\n", encoding="utf-8")
    return {
        "schemaVersion": "1.0", "reviewer": "Architecture reviewer",
        "reviewedOn": "2026-11-10", "catalogSha256": CATALOG_SHA256,
        "rules": [{
            "rule": rule["id"], "status": "conforms",
            "rationale": "Inspected the implementation and found the requirement satisfied.",
            "evidence": [{"path": "src/sample.py", "kind": "source",
                          "startLine": 1, "endLine": 3,
                          "quote": "# Architecture ownership evidence",
                          "observation": "Inspected the source implementation and its ownership boundary."}],
        } for rule in CATALOG["rules"]],
    }


class QualitativeReviewTests(unittest.TestCase):
    def test_all_55_catalog_rules_with_grounded_evidence_complete_review(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = validate_review(valid_document(root), root, CATALOG, CATALOG_SHA256)
            self.assertTrue(result["complete"])
            self.assertEqual(result["required"], 55)
            self.assertEqual(result["reviewed"], 55)
            self.assertEqual(result["pending"], 0)

    def test_catalog_hash_mismatch_prevents_completion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = valid_document(root)
            document["catalogSha256"] = "0" * 64
            result = validate_review(document, root, CATALOG, CATALOG_SHA256)
            self.assertFalse(result["complete"])
            self.assertTrue(any("catalogSha256" in problem for item in result["problems"]
                                for problem in item["problems"]))

    def test_documented_gap_is_a_complete_review_not_a_conformance_pass(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = valid_document(root)
            document["rules"][0]["status"] = "gap"
            document["rules"][0]["rationale"] = "The implementation crosses this required boundary and must be corrected."
            result = validate_review(document, root, CATALOG, CATALOG_SHA256)
            self.assertTrue(result["complete"])
            self.assertEqual(result["counts"]["gap"], 1)

    def test_missing_rule_prevents_completion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = valid_document(root)
            document["rules"].pop()
            result = validate_review(document, root, CATALOG, CATALOG_SHA256)
            self.assertFalse(result["complete"])
            self.assertEqual(result["missing"], [CATALOG["rules"][-1]["id"]])

    def test_duplicate_and_unknown_rules_prevent_completion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = valid_document(root)
            document["rules"].append(dict(document["rules"][0]))
            document["rules"].append({"rule": "ACIMA-UNKNOWN", "status": "conforms"})
            result = validate_review(document, root, CATALOG, CATALOG_SHA256)
            self.assertFalse(result["complete"])
            self.assertTrue(result["duplicates"])
            self.assertTrue(result["extra"])

    def test_missing_or_unverifiable_evidence_prevents_completion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = valid_document(root)
            document["rules"][0]["evidence"] = []
            document["rules"][1]["evidence"][0]["path"] = "missing.py"
            document["rules"][2]["evidence"][0]["startLine"] = 99
            result = validate_review(document, root, CATALOG, CATALOG_SHA256)
            self.assertFalse(result["complete"])
            self.assertEqual(result["reviewed"], 52)

    def test_fabricated_quote_does_not_validate_as_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = valid_document(root)
            document["rules"][0]["evidence"][0]["quote"] = "This text is not in the file"
            result = validate_review(document, root, CATALOG, CATALOG_SHA256)
            self.assertFalse(result["complete"])

    def test_path_traversal_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = valid_document(root)
            document["rules"][0]["evidence"][0]["path"] = "../outside.py"
            result = validate_review(document, root, CATALOG, CATALOG_SHA256)
            self.assertFalse(result["complete"])

    def test_not_applicable_requires_reason_and_existing_absence_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = valid_document(root)
            entry = document["rules"][0]
            entry["status"] = "not_applicable"
            entry["rationale"] = "This requirement is not applicable because the assessed scope has no such capability."
            entry["evidence"] = [{"path": "src", "kind": "absence",
                                  "observation": "Inspected the source tree and confirmed no capability exists."}]
            result = validate_review(document, root, CATALOG, CATALOG_SHA256)
            self.assertTrue(result["complete"])
            self.assertEqual(result["counts"]["not_applicable"], 1)

    def test_insufficient_evidence_is_a_reviewed_but_unresolved_disposition(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = valid_document(root)
            document["rules"][0]["status"] = "insufficient_evidence"
            document["rules"][0]["rationale"] = "Insufficient evidence exists to decide this requirement."
            result = validate_review(document, root, CATALOG, CATALOG_SHA256)
            self.assertFalse(result["complete"])
            self.assertEqual(result["reviewed"], 55)
            self.assertEqual(result["unresolved"], 1)

    def test_assessment_completes_only_with_all_rules_unit_map_and_successful_run(self) -> None:
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "sample.py").write_text("class Sample: pass\n", encoding="utf-8")
            review_path = root / "qualitative-review.json"
            review_path.write_text(json.dumps(valid_document(root)), encoding="utf-8")
            config = {"mode": "base", "units": [{"id": "sample", "module": "sample",
                       "role": "implementation", "paths": ["sample.py"]}]}
            payload = {"execution": {rule["id"]: {"executed": rule["automation"] == "automated"}
                                     for rule in CATALOG["rules"]},
                       "level": "L3", "findings": [], "standard": "test-standard", "sourceFiles": 1}
            with patch.object(acima, "read_config", return_value=config), \
                 patch.object(acima, "run_enforcer", return_value=(0, payload, None)):
                code, report = acima.assess_project(root, "python", "L3", review_path)
            self.assertEqual(code, 0)
            self.assertEqual(report["verdict"], "ASSESSED")
            self.assertTrue(report["comprehensiveRuleReview"]["complete"])
            self.assertTrue(report["assessmentCompletion"]["complete"])
            markdown = acima.assess_markdown(report)
            self.assertIn("Assessment completion", markdown)
            self.assertIn("conforms", markdown)

    def test_validate_review_cli_returns_zero_only_for_complete_review(self) -> None:
        from contextlib import redirect_stdout
        from io import StringIO
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            review_path = root / "review.json"
            review_path.write_text(json.dumps(valid_document(root)), encoding="utf-8")
            with patch.object(sys, "argv", ["acima", "validate-review", "--root", str(root),
                                             "--file", str(review_path), "--format", "json"]), \
                 redirect_stdout(StringIO()):
                self.assertEqual(acima.main(), 0)
            document = valid_document(root)
            document["rules"].pop()
            review_path.write_text(json.dumps(document), encoding="utf-8")
            with patch.object(sys, "argv", ["acima", "validate-review", "--root", str(root),
                                             "--file", str(review_path), "--format", "json"]), \
                 redirect_stdout(StringIO()):
                self.assertEqual(acima.main(), 1)

    def test_assessment_cannot_be_complete_without_valid_review_and_unit_map(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            code, report = acima.assess_project(root)
            self.assertFalse(report["assessmentCompletion"]["complete"])
            self.assertFalse(report["comprehensiveRuleReview"]["complete"])


if __name__ == "__main__":
    unittest.main()
