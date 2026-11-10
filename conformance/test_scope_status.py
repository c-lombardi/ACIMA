"""Scope-aware adoption status scenarios.

Completion is relative to an explicitly approved objective set. These tests cover assessment-only
and local-only engagements, CI consent/unverified states, declined and deferred work, optional
documents, full-conformance evidence, invalid metadata, unsupported objectives and resumption.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("acima_scope_status", ROOT / "tools/acima.py")
acima = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(acima)

CATALOG = json.loads((ROOT / "tools/acima-spec/rules.json").read_text(encoding="utf-8"))
CATALOG_SHA = hashlib.sha256((ROOT / "tools/acima-spec/rules.json").read_bytes()).hexdigest()


def write_json(root: Path, relative: str, payload: dict) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def config(root: Path, level: str = "L2") -> None:
    write_json(root, "acima.config.json", {
        "standard": CATALOG["version"], "language": "python", "level": level, "mode": "base",
        "units": [{"id": "u0", "role": "implementation", "paths": ["src/u0"]}],
    })


def assessment(root: Path, verdict: str = "ASSESSED") -> None:
    write_json(root, "docs/acima/assessment.json", {
        "readOnly": True, "root": str(root.resolve()), "verdict": verdict,
        "verdictMeaning": acima.VERDICT_MEANING[verdict], "sourceFiles": 4,
        "languages": ["python"],
    })


def run_payload(findings: list[dict] | None = None) -> dict:
    execution = {}
    for rule in CATALOG["rules"]:
        execution[rule["id"]] = ({"executed": False, "reason": "manual rule"}
                                  if rule.get("automation") == "manual"
                                  else {"executed": True})
    return {"standard": CATALOG["version"], "level": "L2", "sourceFiles": 4,
            "execution": execution, "findings": findings or []}


def baseline(root: Path, findings: list[dict] | None = None) -> None:
    write_json(root, "docs/acima/baseline-2026-01-01.json", run_payload(findings))


def scope(root: Path, objectives: dict[str, str], *, approved_on: str = "2026-01-01",
          approved_by: str = "repository-owner") -> None:
    write_json(root, ".acima/adoption-scope.json", {
        "version": 1, "approvedBy": approved_by, "approvedOn": approved_on,
        "objectives": [{"id": key, "disposition": value} for key, value in objectives.items()],
    })


def by_id(report: dict) -> dict[str, dict]:
    return {entry["id"]: entry for entry in report["objectives"]}


def next_action(report: dict) -> str:
    return report["next"]["action"].lower()


class ScopeAwareStatusTests(unittest.TestCase):
    def test_assessment_only_scope_completes_without_ci_or_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src").mkdir()
            (root / "src" / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
            scope(root, {"assessment": "required"})
            assessment(root)
            report = acima.status_project(root)
            objectives = by_id(report)
            self.assertEqual(objectives["assessment"]["state"], "COMPLETE")
            self.assertEqual(objectives["local-enforcement"]["state"], "NOT_APPLICABLE")
            self.assertTrue(report["engagement"]["complete"])
            self.assertIn("No further action", report["next"]["action"])
            self.assertFalse(report["next"]["writes"])

    def test_local_only_scope_completes_without_ci(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config(root)
            scope(root, {"assessment": "required", "local-enforcement": "approved"})
            assessment(root)
            baseline(root)
            report = acima.status_project(root)
            objectives = by_id(report)
            self.assertEqual(objectives["local-enforcement"]["state"], "COMPLETE")
            self.assertEqual(objectives["ci-enforcement"]["state"], "NOT_APPLICABLE")
            self.assertTrue(report["engagement"]["complete"])
            self.assertIn("No further action", report["next"]["action"])

    def test_local_only_scope_does_not_require_an_assessment_artefact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config(root)
            scope(root, {"local-enforcement": "approved"})
            baseline(root)
            report = acima.status_project(root)
            self.assertEqual(by_id(report)["local-enforcement"]["state"], "COMPLETE")
            self.assertEqual(by_id(report)["assessment"]["state"], "NOT_APPLICABLE")
            self.assertTrue(report["engagement"]["complete"])

    def test_ci_approved_but_not_configured_is_the_next_action(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config(root)
            scope(root, {"assessment": "required", "local-enforcement": "approved",
                         "baseline-waivers": "approved", "ci-enforcement": "approved"})
            assessment(root)
            baseline(root)
            report = acima.status_project(root)
            self.assertEqual(by_id(report)["ci-enforcement"]["state"], "READY")
            self.assertIn("gate", next_action(report))
            self.assertTrue(report["next"]["approvalRequired"])
            self.assertFalse(report["engagement"]["complete"])

    def test_ci_configured_but_unverified_stays_in_progress(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config(root)
            scope(root, {"assessment": "required", "local-enforcement": "approved",
                         "baseline-waivers": "approved", "ci-enforcement": "approved"})
            assessment(root)
            baseline(root)
            workflow = root / ".github/workflows/acima.yml"
            workflow.parent.mkdir(parents=True)
            workflow.write_text(
                "on: pull_request\njobs:\n  gate:\n    steps:\n"
                "      - run: python3 examples/python/tools/acima_arch.py --root . --level L2\n",
                encoding="utf-8")
            report = acima.status_project(root)
            self.assertEqual(by_id(report)["ci-enforcement"]["state"], "IN_PROGRESS")
            self.assertIn("provenance", next_action(report))
            self.assertFalse(report["engagement"]["complete"])

    def test_ci_can_be_configured_without_a_separate_baseline_objective(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config(root)
            baseline(root)
            scope(root, {"local-enforcement": "approved", "ci-enforcement": "approved"})
            workflow = root / ".github/workflows/acima.yml"
            workflow.parent.mkdir(parents=True)
            workflow.write_text(
                "on: pull_request\njobs:\n  gate:\n    steps:\n"
                "      - run: python3 examples/python/tools/acima_arch.py --root . --level L2\n",
                encoding="utf-8")
            report = acima.status_project(root)
            self.assertEqual(by_id(report)["ci-enforcement"]["state"], "IN_PROGRESS")
            self.assertEqual(by_id(report)["baseline-waivers"]["state"], "NOT_APPLICABLE")

    def test_declined_communication_is_not_an_outstanding_requirement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scope(root, {"assessment": "required",
                         "communication-governance": "declined"})
            assessment(root)
            report = acima.status_project(root)
            self.assertEqual(by_id(report)["communication-governance"]["state"], "DECLINED")
            self.assertIn("communication-governance", report["engagement"]["declined"])
            self.assertNotIn("communication-governance", report["engagement"]["remaining"])
            self.assertTrue(report["engagement"]["complete"])

    def test_absent_optional_documents_never_block_or_become_next(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scope(root, {"assessment": "required", "developer-handoff": "optional",
                         "communication-governance": "optional"})
            assessment(root)
            report = acima.status_project(root)
            self.assertEqual(by_id(report)["developer-handoff"]["state"], "OPTIONAL")
            self.assertEqual(by_id(report)["communication-governance"]["state"], "OPTIONAL")
            self.assertNotIn("handoff", next_action(report))
            self.assertTrue(report["engagement"]["complete"])

    def test_full_conformance_requested_keeps_missing_manual_evidence_open(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config(root)
            scope(root, {"assessment": "required", "local-enforcement": "approved",
                         "full-conformance": "approved"})
            assessment(root)
            baseline(root)
            report = acima.status_project(root)
            objective = by_id(report)["full-conformance"]
            self.assertIn(objective["state"], {"IN_PROGRESS", "READY"})
            self.assertIn("evidence", next_action(report))
            self.assertFalse(report["engagement"]["complete"])

    def test_partial_approval_completes_only_the_approved_part(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config(root)
            scope(root, {"assessment": "required", "local-enforcement": "approved",
                         "ci-enforcement": "deferred",
                         "communication-governance": "declined"})
            assessment(root)
            baseline(root)
            report = acima.status_project(root)
            self.assertTrue(report["engagement"]["complete"])
            self.assertIn("ci-enforcement", report["engagement"]["deferred"])
            self.assertIn("communication-governance", report["engagement"]["declined"])

    def test_deferred_ci_does_not_block_local_completion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config(root)
            scope(root, {"assessment": "required", "local-enforcement": "approved",
                         "ci-enforcement": "deferred"})
            assessment(root)
            baseline(root)
            report = acima.status_project(root)
            self.assertEqual(by_id(report)["ci-enforcement"]["state"], "DEFERRED")
            self.assertTrue(report["engagement"]["complete"])
            self.assertNotIn("ci-enforcement", report["engagement"]["remaining"])

    def test_unsupported_objective_blocks_and_is_named(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scope(root, {"runtime-isolation": "approved"})
            report = acima.status_project(root)
            self.assertEqual(report["scope"]["state"], "BLOCKED")
            self.assertIn("runtime-isolation", report["scope"]["unsupported"])
            self.assertEqual(report["engagement"]["state"], "BLOCKED")
            self.assertIn("scope", next_action(report))

    def test_invalid_approval_metadata_blocks_before_any_action(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_json(root, ".acima/adoption-scope.json", {
                "version": 1, "approvedBy": "", "approvedOn": "not-a-date",
                "objectives": [{"id": "assessment", "disposition": "required"}],
            })
            report = acima.status_project(root)
            self.assertEqual(report["scope"]["state"], "BLOCKED")
            self.assertTrue(any("approvedBy" in problem for problem in report["scope"]["problems"]))
            self.assertIn("scope", next_action(report))

    def test_resumed_adoption_after_long_pause_still_uses_declared_scope(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config(root)
            scope(root, {"assessment": "required", "local-enforcement": "approved"},
                  approved_on="2023-01-01")
            assessment(root)
            baseline(root)
            report = acima.status_project(root)
            self.assertTrue(report["engagement"]["complete"])
            self.assertEqual(report["scope"]["approvedOn"], "2023-01-01")
            self.assertIn("No further action", report["next"]["action"])

    def test_config_without_scope_does_not_infer_full_adoption(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config(root)
            baseline(root)
            report = acima.status_project(root)
            self.assertEqual(report["scope"]["state"], "UNKNOWN")
            self.assertIn("scope", next_action(report))
            self.assertFalse(report["engagement"]["scopeDefined"])

    def test_markdown_renders_scope_and_single_next_action(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scope(root, {"assessment": "required"})
            assessment(root)
            text = acima.status_markdown(acima.status_project(root))
            self.assertIn("# ACIMA adoption status", text)
            self.assertIn("**Scope:**", text)
            self.assertIn("No further action", text)


if __name__ == "__main__":
    unittest.main()
