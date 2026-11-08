"""Regression tests for the adoption skill's fail-closed assessment contract."""
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "acima_preflight", ROOT / "skills/acima-adoption/scripts/preflight.py")
preflight = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = preflight
SPEC.loader.exec_module(preflight)


def valid_payload() -> dict:
    catalog = json.loads((ROOT / "tools/acima-spec/rules.json").read_text(encoding="utf-8"))
    return {
        "standard": "1.0.0",
        "level": "L1",
        "sourceFiles": 1,
        "execution": {rule["id"]: {"executed": True} for rule in catalog["rules"]},
        "findings": [],
    }


class AssessmentValidationTests(unittest.TestCase):
    def test_valid_payload_is_accepted(self) -> None:
        self.assertEqual(preflight.validate_assessment(valid_payload(), 0, {}), [])

    def test_zero_source_files_is_not_a_clean_run(self) -> None:
        payload = valid_payload()
        payload["sourceFiles"] = 0
        errors = preflight.validate_assessment(payload, 0, {})
        self.assertTrue(any("source files" in error for error in errors))

    def test_missing_execution_map_is_rejected(self) -> None:
        payload = valid_payload()
        del payload["execution"]
        errors = preflight.validate_assessment(payload, 0, {})
        self.assertTrue(any("execution map" in error for error in errors))

    def test_unexecuted_rule_needs_a_reason(self) -> None:
        payload = valid_payload()
        payload["execution"]["ACIMA-C003"] = {"executed": False}
        errors = preflight.validate_assessment(payload, 0, {})
        self.assertTrue(any("without a reason" in error for error in errors))

    def test_invalid_json_is_not_zero_findings(self) -> None:
        errors = preflight.validate_assessment(None, 1, {})
        self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main()
