"""Evidence-based fit and recommendation tests.

These fixtures keep the architectural evidence explicit: a utility, an ambiguous layout, a
modular monolith, an already-enforced application, and a meaningful application with findings.
The recommendation is asserted together with the explanation that supports it.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("acima_assessment", ROOT / "tools/acima.py")
acima = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules["acima_assessment"] = acima
SPEC.loader.exec_module(acima)

CATALOG = json.loads((ROOT / "tools/acima-spec/rules.json").read_text(encoding="utf-8"))


def write(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def monolith(root: Path) -> dict:
    write(root, "src/orders/place.py", "VALUE = 1\n")
    write(root, "src/billing/charge.py", "OTHER = 2\n")
    config = {
        "standard": CATALOG["version"], "language": "python", "level": "L1", "mode": "base",
        "units": [
            {"id": "orders", "module": "orders", "role": "implementation",
             "paths": ["src/orders"]},
            {"id": "billing", "module": "billing", "role": "implementation",
             "paths": ["src/billing"]},
        ],
    }
    write(root, "acima.config.json", json.dumps(config))
    return config


def utility(root: Path, units: int = 1) -> dict:
    write(root, "app.py", "VALUE = 1\n")
    config = {
        "standard": CATALOG["version"], "language": "python", "level": "L1", "mode": "base",
        "units": [{"id": "app", "module": "app", "role": "implementation", "paths": ["."]}],
    }
    write(root, "acima.config.json", json.dumps(config))
    return config


def report(root: Path, config: dict | None, findings: list[dict] | None = None,
           sources: int = 4, verdict: str = "ASSESSED") -> dict:
    items = findings or []
    by_rule: dict[str, int] = {}
    for item in items:
        by_rule[item["rule"]] = by_rule.get(item["rule"], 0) + 1
    units = (config or {}).get("units") or []
    return {
        "root": str(root), "verdict": verdict, "languages": ["python"],
        "sourceFiles": sources, "requestedLevel": "L1",
        "language": "python",
        "unitMap": {"present": config is not None, "count": len(units),
                    "modules": sorted({unit.get("module") for unit in units
                                       if unit.get("module")}),
                    "units": units},
        "findings": {"total": len(items),
                     "bySeverity": {"error": sum(1 for item in items
                                                if item.get("severity") == "error"),
                                    "warning": 0, "info": 0},
                     "byRule": by_rule, "items": items},
        "coverage": {"executed": 41, "notExecuted": ["ACIMA-C003"], "complete": False},
        "assessment": {"standard": "1.0.0", "level": "L1", "analysedSourceFiles": sources},
        "nextSteps": ["Review the boundaries with the owner."],
    }


def finding() -> dict:
    return {"rule": "ACIMA-D001", "severity": "error",
            "message": "orders imports billing implementation",
            "path": "src/orders/place.py", "line": 1,
            "fingerprint": "sha256:" + "a" * 64}


class AssessmentRecommendationTests(unittest.TestCase):
    def test_single_source_utility_is_not_recommended_even_when_clean(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(root, "app.py", "VALUE = 1\n")
            code, assessment = acima.assess_project(root)
            self.assertEqual(code, 0)
            result = assessment["assessmentResult"]
            self.assertEqual(result["fit"], "INSUFFICIENT_EVIDENCE")
            self.assertIn("0/55", result["why"])
            self.assertIn("no meaningful ownership boundaries", result["why"])
            self.assertIn("purpose", result["facts"])
            self.assertIsNone(result["facts"]["purpose"])
            self.assertIn("not inferred", result["facts"]["purposeBasis"])
            self.assertTrue(result["explanation"]["application"])
            self.assertTrue(result["explanation"]["why"])
            self.assertEqual(result["dimensions"]["architecturalSubstance"]["status"], "none")
            # No future gate is described as an existing capability.
            today = [item["benefit"] for item in result["benefitDetails"]
                     if item["classification"] == "available-today"]
            self.assertFalse(any("pull request" in item.lower() for item in today))
            self.assertTrue(any(item["classification"] == "not-applicable"
                                for item in result["benefitDetails"]))

    def test_existing_enforcement_does_not_automatically_recommend_adoption(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = monolith(root)
            write(root, ".github/workflows/acima.yml",
                  "on: pull_request\njobs:\n  gate:\n    steps:\n"
                  "      - run: python3 examples/python/tools/acima_arch.py --root . --level L1\n")
            result = acima.build_assessment_result(report(root, config), config)
            self.assertEqual(result["fit"], "NOT_RECOMMENDED")
            self.assertEqual(result["dimensions"]["existingEnforcement"]["status"], "strong")
            self.assertIn("already cover", result["why"])
            self.assertTrue(any(item["classification"] == "not-applicable"
                                and "gate" in item["benefit"].lower()
                                for item in result["benefitDetails"]))

    def test_modular_monolith_without_enforcement_is_recommended(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = monolith(root)
            result = acima.build_assessment_result(report(root, config), config)
            self.assertEqual(result["fit"], "RECOMMENDED")
            self.assertEqual(result["dimensions"]["architecturalSubstance"]["status"],
                             "meaningful")
            self.assertEqual(result["dimensions"]["existingEnforcement"]["status"], "none")
            self.assertEqual(result["dimensions"]["incrementalValue"]["status"], "high")
            self.assertIn("no effective automated enforcement", result["why"])
            future = [item for item in result["benefitDetails"]
                      if item["classification"] == "achievable-through-adoption"]
            self.assertTrue(future)
            self.assertTrue(all("pull-request gate" in item["benefit"].lower()
                                or "owned, expiring" in item["benefit"].lower()
                                or "contract and ownership" in item["benefit"].lower()
                                for item in future))

    def test_existing_findings_are_limitations_not_an_automatic_recommendation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = monolith(root)
            result = acima.build_assessment_result(report(root, config, [finding()]), config)
            self.assertEqual(result["fit"], "RECOMMENDED_WITH_LIMITATIONS")
            self.assertIn("existing findings", result["why"])
            self.assertEqual(result["dimensions"]["adoptionCost"]["status"], "high")

    def test_existing_findings_without_boundaries_are_not_recommended(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = utility(root)
            result = acima.build_assessment_result(report(root, config, [finding()]), config)
            self.assertEqual(result["fit"], "NOT_RECOMMENDED")
            self.assertNotEqual(result["fit"], "RECOMMENDED_WITH_LIMITATIONS")

    def test_ambiguous_layout_has_insufficient_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(root, "src/a.py", "VALUE = 1\n")
            write(root, "src/b.py", "OTHER = 2\n")
            code, assessment = acima.assess_project(root)
            self.assertEqual(code, 0)
            result = assessment["assessmentResult"]
            self.assertEqual(result["fit"], "INSUFFICIENT_EVIDENCE")
            self.assertIn("ownership is not established", result["why"])
            self.assertTrue(result["unresolvedQuestions"])

    def test_unsupported_language_is_not_supported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(root, "src/Main.java", "class Main {}\n")
            code, assessment = acima.assess_project(root)
            self.assertEqual(code, 0)
            result = assessment["assessmentResult"]
            self.assertEqual(result["fit"], "NOT_SUPPORTED")
            self.assertEqual(result["dimensions"]["technicalCompatibility"]["status"],
                             "unsupported")

    def test_unsupported_architecture_profile_is_not_supported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(root, "src/app.py", "VALUE = 1\n")
            write(root, "acima.topology.json", "{}\n")
            code, assessment = acima.assess_project(root)
            self.assertEqual(code, 0)
            self.assertEqual(assessment["verdict"], "UNSUPPORTED_PROFILE")
            self.assertEqual(assessment["assessmentResult"]["fit"], "NOT_SUPPORTED")

    def test_all_dimensions_and_explanation_are_present(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = monolith(root)
            result = acima.build_assessment_result(report(root, config), config)
            self.assertEqual(set(result["dimensions"]), {
                "technicalCompatibility", "architecturalSubstance", "existingEnforcement",
                "incrementalValue", "adoptionCost", "practicalApplicability"})
            for dimension in result["dimensions"].values():
                self.assertIn("status", dimension)
                self.assertIn("summary", dimension)
                self.assertIn("evidence", dimension)
                self.assertIn("confidence", dimension)
            for key in ("application", "boundaries", "existingEnforcement", "whatAcimaAdds",
                        "whatAcimaWillNotAdd", "adoptionCost", "maintenanceCost", "why",
                        "confidence", "unresolvedQuestions"):
                self.assertIn(key, result["explanation"])


if __name__ == "__main__":
    unittest.main()
