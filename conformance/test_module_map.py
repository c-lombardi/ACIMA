"""Module-map discovery, review, approval and reporting regressions.

The tests use disposable repositories and the real discovery/assessment code. They do not
pretend a synthetic proposal is a real end-to-end agent conversation.
"""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "conformance"))
sys.path.insert(0, str(ROOT / "tools"))
import module_map  # noqa: E402
import acima  # noqa: E402
from test_html_report import model as report_model, add_complete_review  # noqa: E402

REPORT = ROOT / "skills/acima-adoption/scripts/render_report.py"
CATALOG = json.loads((ROOT / "tools/acima-spec/rules.json").read_text(encoding="utf-8"))
VERSION = CATALOG["version"]


def write(root: Path, relative: str, text: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def config(root: Path, units: list[dict]) -> None:
    write(root, "acima.config.json", json.dumps({
        "standard": VERSION, "mode": "base", "language": "python", "level": "L1",
        "root": ".", "units": units,
    }))


def clean_repo(root: Path) -> None:
    write(root, "src/orders/service.py", "def place():\n    return 1\n")
    write(root, "src/billing/service.py", "def charge():\n    return 1\n")


def proposal_for(root: Path) -> dict:
    return module_map.discover(root)


def decision_doc(proposal: dict, *, map_decision: str = "accept",
                 module: str = "accept", recommendation: str = "accept",
                 reviewed_on: str = "2026-11-11") -> dict:
    inner = proposal["proposal"]
    return {
        "schemaVersion": "1.0", "proposalId": inner["proposalId"],
        "reviewer": "Repository owner", "reviewedOn": reviewed_on,
        "mapDecision": map_decision,
        "moduleDecisions": [{"id": item["id"], "decision": module}
                            for item in inner["modules"]],
        "recommendationDecisions": [{"id": item["id"], "decision": recommendation}
                                    for item in inner["recommendations"]],
    }


class ModuleMapTests(unittest.TestCase):
    def test_no_map_generates_a_proposal_automatically(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clean_repo(root)
            data = module_map.discover(root)
            self.assertEqual(data["status"], "proposal_required")
            self.assertIsNotNone(data["proposal"])
            self.assertEqual({item["name"] for item in data["proposal"]["modules"]},
                             {"Orders", "Billing"})
            self.assertTrue(data["proposal"]["proposalId"].startswith("sha256:"))
            self.assertFalse((root / "acima.config.json").exists())

    def test_partial_map_preserves_existing_units_and_proposes_missing_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clean_repo(root)
            config(root, [{"id": "orders", "module": "orders", "role": "implementation",
                           "paths": ["src/orders"]}])
            data = module_map.discover(root)
            self.assertEqual(data["authoritativeMap"]["status"], "incomplete")
            modules = {item["name"]: item for item in data["proposal"]["modules"]}
            self.assertEqual(modules["Orders"]["status"], "existing")
            self.assertEqual(modules["Orders"]["contracts"]["paths"], [])
            self.assertEqual(modules["Billing"]["status"], "candidate")
            self.assertIn("src/billing/service.py", data["authoritativeMap"]["unownedPaths"])

    def test_authoritative_map_is_evaluated_not_replaced(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clean_repo(root)
            config(root, [
                {"id": "orders", "module": "orders", "role": "implementation",
                 "paths": ["src/orders"]},
                {"id": "billing", "module": "billing", "role": "implementation",
                 "paths": ["src/billing"]},
            ])
            before = (root / "acima.config.json").read_bytes()
            data = module_map.discover(root)
            self.assertEqual(data["status"], "authoritative")
            self.assertIsNone(data["proposal"])
            self.assertEqual(data["authoritativeMap"]["status"], "complete")
            self.assertEqual((root / "acima.config.json").read_bytes(), before)

    def test_independent_qualitative_review_survives_missing_map(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(root, "src/app.py", "VALUE = 1\n")
            review = root / "review.json"
            model = {"repository": {"path": str(root)}, "coverage": {}}
            add_complete_review(model, root)
            review.write_text(json.dumps(model["qualitativeReview"]), encoding="utf-8")
            _, report = acima.assess_project(root, review_path=review)
            self.assertEqual(report["verdict"], "NEEDS_UNIT_MAP")
            self.assertTrue(report["comprehensiveRuleReview"]["coverageComplete"])
            self.assertEqual(report["ownershipGate"]["status"], "blocked")
            self.assertTrue(report["ownershipGate"]["independentReviewContinues"])

    def test_ownership_dependent_rules_are_explicitly_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(root, "src/app.py", "VALUE = 1\n")
            _, report = acima.assess_project(root)
            gate = report["ownershipGate"]
            self.assertEqual(gate["status"], "blocked")
            self.assertTrue(gate["deterministicChecksBlocked"])
            self.assertIn("ACIMA-D001", gate["ownershipDependentRules"])
            self.assertLess(len(gate["ownershipDependentRules"]), len(CATALOG["rules"]))

    def test_all_catalog_requirements_are_reviewed_once(self) -> None:
        review = acima._comprehensive_rule_review(CATALOG)
        self.assertEqual(len(review["rules"]), len(CATALOG["rules"]))
        self.assertEqual(len({item["rule"] for item in review["rules"]}), len(CATALOG["rules"]))
        self.assertEqual(review["pending"], len(CATALOG["rules"]))

    def test_directory_and_project_boundaries_are_not_authoritative_modules(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clean_repo(root)
            data = module_map.discover(root)
            self.assertEqual(data["authoritativeMap"]["status"], "absent")
            for module in data["proposal"]["modules"]:
                self.assertEqual(module["ownership"], "inferred")
                self.assertEqual(module["status"], "candidate")
                self.assertIn("requires owner confirmation", module["responsibility"])

    def test_proposal_evidence_distinguishes_observation_inference_and_recommendation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clean_repo(root)
            data = module_map.discover(root)
            module = data["proposal"]["modules"][0]
            self.assertTrue(module["evidence"])
            self.assertTrue(all(item["classification"] == "observed" for item in module["evidence"]))
            self.assertEqual(data["proposal"]["classification"], "inference")
            for recommendation in data["proposal"]["recommendations"]:
                for key in ("observed", "whyItMatters", "recommendation", "benefit", "risk",
                            "uncertainty", "requiresUserInput"):
                    self.assertTrue(recommendation[key], (recommendation["id"], key))

    def test_unassigned_production_code_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(root, "main.py", "VALUE = 1\n")
            write(root, "src/orders/service.py", "def place(): return 1\n")
            data = module_map.discover(root)
            paths = {item["path"] for item in data["proposal"]["unassigned"]}
            self.assertIn("main.py", paths)
            self.assertTrue(any(item["id"].startswith("MMR-")
                                and "Unassigned production code" in item["title"]
                                for item in data["proposal"]["recommendations"]))

    def test_decisions_allow_accept_modify_reject_and_defer_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clean_repo(root)
            data = proposal_for(root)
            inner = data["proposal"]
            decisions = decision_doc(data, module="modify", recommendation="accept")
            decisions["moduleDecisions"][0].update({
                "name": "Order ownership", "responsibility": "Owns order placement and lifecycle.",
                "paths": ["src/orders"],
            })
            result = module_map.apply_review(data, decisions, root=root)
            self.assertIn(result["status"], {"partially_approved", "approved"})
            modified = next(item for item in result["modules"] if item["id"] == inner["modules"][0]["id"])
            self.assertEqual(modified["reviewDecision"], "modify")
            self.assertEqual(modified["name"], "Order ownership")

            deferred = decision_doc(data, map_decision="defer", module="defer")
            self.assertEqual(module_map.apply_review(data, deferred, root=root)["status"], "deferred")
            rejected = decision_doc(data, map_decision="reject")
            self.assertEqual(module_map.apply_review(data, rejected, root=root)["status"], "rejected")

    def test_recommendation_decisions_are_scoped_and_independent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(root, "src/orders/service.py",
                  "from src.billing.impl.charge import charge\ndef place(): return charge()\n")
            write(root, "src/billing/impl/charge.py", "def charge(): return 1\n")
            data = proposal_for(root)
            recommendations = data["proposal"]["recommendations"]
            self.assertTrue(recommendations)
            decisions = decision_doc(data, module="accept", recommendation="reject")
            result = module_map.apply_review(data, decisions, root=root)
            self.assertEqual(result["status"], "approved")
            self.assertTrue(all(item["decision"] == "reject"
                                for item in result["recommendations"]))
            self.assertIn("approved", result["approval"]["status"])

    def test_inferred_ownership_cannot_be_authoritative_before_review(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clean_repo(root)
            data = proposal_for(root)
            with self.assertRaises(module_map.ModuleMapError):
                module_map.build_config(data, {"approval": {"canWriteConfig": False}})
            self.assertFalse((root / "acima.config.json").exists())

    def test_approved_map_enables_config_and_assessment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clean_repo(root)
            data = proposal_for(root)
            result = module_map.apply_review(data, decision_doc(data), root=root)
            self.assertEqual(result["status"], "approved", result["approval"])
            config = module_map.build_config(data, result)
            write(root, "acima.config.json", json.dumps(config))
            _, report = acima.assess_project(root)
            self.assertNotEqual(report["verdict"], "NEEDS_UNIT_MAP")
            self.assertEqual(report["moduleMap"]["authoritativeMap"]["status"], "complete")
            self.assertEqual(report["ownershipGate"]["status"], "ready")

    def test_discovery_never_writes_to_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clean_repo(root)
            before = {path.relative_to(root).as_posix(): path.read_bytes()
                      for path in root.rglob("*") if path.is_file()}
            module_map.discover(root)
            acima.assess_project(root)
            after = {path.relative_to(root).as_posix(): path.read_bytes()
                     for path in root.rglob("*") if path.is_file()}
            self.assertEqual(after, before)

    def test_report_renders_module_map_review_and_ownership_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clean_repo(root)
            data = proposal_for(root)
            d = report_model()
            d["moduleMap"] = data
            d["ownershipGate"] = {
                "status": "blocked",
                "reason": "Ownership-dependent checks require an approved map.",
                "ownershipDependentRules": ["ACIMA-D001", "ACIMA-D003"],
                "independentReviewContinues": True,
                "deterministicChecksBlocked": True,
                "proposalReviewRequired": True,
            }
            src = root / "model.json"
            src.write_text(json.dumps(d), encoding="utf-8")
            out = root / "report"
            import subprocess
            result = subprocess.run([sys.executable, str(REPORT), "--input", str(src),
                                     "--out-dir", str(out)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            index = (out / "index.html").read_text(encoding="utf-8")
            proposal = (out / "proposal.html").read_text(encoding="utf-8")
            evidence = (out / "evidence.html").read_text(encoding="utf-8")
            for text in ("Proposed module map", "not authoritative", "OWNERSHIP GATE",
                         "Module-map proposal", "Checks that depend on module ownership"):
                self.assertTrue(text in proposal or text in index or text in evidence, text)
            self.assertIn("Decisions requiring user input", proposal)
            self.assertIn("ACIMA-D001", evidence)
            self.assertIn("not authoritative", index)
            self.assertIn("No review or approval is recorded", proposal)
            self.assertIn("Conformance verification", index)
            self.assertIn("Assessment", index)


if __name__ == "__main__":
    unittest.main()
