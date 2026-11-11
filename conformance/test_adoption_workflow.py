#!/usr/bin/env python3
"""End-to-end orchestration and consent regressions for adoption modes."""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "conformance"))
import adoption_workflow as workflow  # noqa: E402


def write(root: Path, relative: str, text: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def fixture(root: Path, *, manifests: bool = True) -> None:
    write(root, "src/orders/service.py", "def place():\n    return 1\n")
    write(root, "src/billing/service.py", "def charge():\n    return 1\n")
    if manifests:
        write(root, "src/orders/pyproject.toml", "[project]\nname = 'orders'\n")
        write(root, "src/billing/pyproject.toml", "[project]\nname = 'billing'\n")


def snapshot(root: Path) -> dict[str, bytes]:
    return {path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob("*") if path.is_file()}


def map_review(root: Path) -> Path:
    proposal = json.loads((root / ".acima/module-map.proposal.json").read_text(encoding="utf-8"))
    review = {
        "schemaVersion": "1.0", "proposalId": proposal["proposalId"],
        "reviewer": "Repository owner", "reviewedOn": workflow._today(),
        "mapDecision": "accept",
        "moduleDecisions": [{"id": item["id"], "decision": "accept"}
                            for item in proposal["modules"]],
        "recommendationDecisions": [{"id": item["id"], "decision": "accept"}
                                    for item in proposal.get("recommendations", [])],
    }
    path = root.parent / (root.name + "-map-review.json")
    path.write_text(json.dumps(review), encoding="utf-8")
    return path


def scope(root: Path) -> Path:
    path = root.parent / (root.name + "-scope.json")
    path.write_text(json.dumps({
        "version": 1, "approvedBy": "Repository owner", "approvedOn": workflow._today(),
        "objectives": [
            {"id": "assessment", "disposition": "required"},
            {"id": "local-enforcement", "disposition": "approved"},
            {"id": "baseline-waivers", "disposition": "approved"},
            {"id": "ci-enforcement", "disposition": "deferred"},
            {"id": "developer-handoff", "disposition": "approved"},
            {"id": "agent-guidance", "disposition": "approved"},
        ],
    }), encoding="utf-8")
    return path


class AdoptionWorkflowTests(unittest.TestCase):
    def test_guided_start_generates_deliverables_but_no_implementation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            before = snapshot(root)
            state = workflow.start(root, "guided")
            self.assertEqual(state["mode"], "guided")
            self.assertEqual(state["stages"]["module_map"]["status"], "awaiting_approval")
            self.assertEqual(state["stages"]["adoption_proposal"]["status"], "awaiting_approval")
            self.assertFalse((root / "acima.config.json").exists())
            self.assertFalse((root / "tools/acima_arch.py").exists())
            self.assertTrue((root / ".acima/module-map.proposal.json").is_file())
            self.assertTrue((root / "docs/acima/adoption-proposal.md").is_file())
            self.assertTrue((root / ".acima/adoption-workflow.json").is_file())
            after = snapshot(root)
            unchanged = {path for path in before if path.startswith("src/")}
            self.assertTrue(all(after[path] == before[path] for path in unchanged))

    def test_full_requires_explicit_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            with self.assertRaises(workflow.WorkflowError):
                workflow.start(root, "full")
            self.assertFalse((root / ".acima/adoption-workflow.json").exists())

    def test_full_generates_enforcement_ci_state_and_verification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            write(root, ".github/workflows/existing.yml",
                  "name: existing\non: pull_request\njobs:\n  test:\n    runs-on: ubuntu-latest\n")
            state = workflow.start(root, "full", authorize_full=True)
            self.assertEqual(state["mode"], "full")
            self.assertEqual(state["stages"]["module_map"]["status"], "complete")
            self.assertEqual(state["stages"]["adoption_proposal"]["status"], "complete")
            self.assertEqual(state["stages"]["implementation"]["status"], "complete")
            self.assertEqual(state["stages"]["ci"]["status"], "complete")
            self.assertEqual(state["stages"]["remediation"]["status"], "awaiting_approval")
            self.assertEqual(state["stages"]["verification"]["status"], "in_progress")
            self.assertTrue((root / "acima.config.json").is_file())
            self.assertTrue((root / "tools/acima_arch.py").is_file())
            self.assertTrue((root / ".github/workflows/acima.yml").is_file())
            self.assertTrue((root / "docs/acima/remediation-plan.json").is_file())
            before = snapshot(root)
            source_before = {path: data for path, data in before.items() if path.startswith("src/")}
            state = workflow.remediate(root, "none", approved_by="Repository owner")
            self.assertEqual(state["stages"]["remediation"]["status"], "complete")
            self.assertEqual(state["remediation"]["outcome"], "declined")
            after = snapshot(root)
            self.assertTrue(all(after[path] == data for path, data in source_before.items()))
            verification = json.loads((root / "docs/acima/verification.json").read_text(encoding="utf-8"))
            self.assertEqual(verification["positive"]["status"], "valid")
            self.assertEqual(verification["negative"]["status"], "detected")
            self.assertEqual(verification["status"], "verified")
            self.assertEqual(state["stages"]["verification"]["status"], "complete")
            self.assertIn("docs/acima/adoption-handoff.md", state["artifacts"]["handoff"])

    def test_full_pauses_low_confidence_ownership_without_writing_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root, manifests=False)
            state = workflow.start(root, "full", authorize_full=True)
            self.assertEqual(state["stages"]["module_map"]["status"], "blocked")
            self.assertFalse((root / "acima.config.json").exists())
            self.assertFalse((root / "tools/acima_arch.py").exists())
            self.assertTrue((root / ".acima/module-map.proposal.json").is_file())
            self.assertEqual(state["next"]["approvalRequired"], True)

    def test_guided_approves_individual_map_and_scope_then_implements(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            workflow.start(root, "guided")
            state = workflow.approve(root, map_decisions=map_review(root), scope=scope(root))
            self.assertEqual(state["stages"]["module_map"]["status"], "complete")
            self.assertEqual(state["stages"]["adoption_proposal"]["status"], "complete")
            self.assertTrue((root / "acima.config.json").is_file())
            self.assertTrue((root / "tools/acima_arch.py").is_file())
            self.assertTrue((root / "docs/acima/verification.json").is_file())

    def test_no_ci_provider_gets_concrete_instructions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            state = workflow.start(root, "full", authorize_full=True)
            ci = json.loads((root / "docs/acima/ci-integration.json").read_text(encoding="utf-8"))
            self.assertEqual(ci["provider"], None)
            self.assertEqual(ci["status"], "no_provider")
            self.assertTrue(ci["instructions"])
            self.assertNotIn("remote", ci["claim"].lower())
            self.assertEqual(state["stages"]["ci"]["status"], "complete")

    def test_existing_ci_is_detected_and_a_gate_is_added(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            write(root, ".gitlab-ci.yml", "test:\n  script: echo ok\n")
            state = workflow.start(root, "full", authorize_full=True)
            ci = json.loads((root / "docs/acima/ci-integration.json").read_text(encoding="utf-8"))
            self.assertEqual(ci["provider"], "gitlab-ci")
            self.assertEqual(ci["status"], "manual_instructions")
            self.assertIn("pull-request", " ".join(ci["instructions"]))
            self.assertEqual(state["stages"]["ci"]["status"], "complete")

    def test_state_is_read_only_status_and_stale_artifacts_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            workflow.start(root, "guided")
            before = snapshot(root)
            report = workflow.status(root)
            self.assertEqual(snapshot(root), before)
            self.assertEqual(report["mode"], "guided")
            self.assertFalse(report["stale"])
            write(root, "src/orders/service.py", "def place():\n    return 2\n")
            self.assertTrue(workflow.status(root)["stale"])

    def test_guided_map_approval_does_not_authorize_scope(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            workflow.start(root, "guided")
            state = workflow.approve(root, map_decisions=map_review(root))
            self.assertEqual(state["stages"]["module_map"]["status"], "complete")
            self.assertFalse((root / ".acima/adoption-scope.json").exists())
            self.assertFalse((root / "tools/acima_arch.py").exists())
            self.assertTrue(state["next"]["approvalRequired"])

    def test_resume_preserves_the_map_approval_and_waits_for_scope(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            workflow.start(root, "guided")
            workflow.approve(root, map_decisions=map_review(root))
            # A new process/load must recover the approved map and ask only for the missing scope.
            resumed = workflow.continue_workflow(root)
            self.assertEqual(resumed["stages"]["module_map"]["status"], "complete")
            self.assertIn("scope", resumed["next"]["action"].lower())
            self.assertFalse((root / ".acima/adoption-scope.json").exists())
            state = workflow.approve(root, scope=scope(root))
            self.assertEqual(state["stages"]["adoption_proposal"]["status"], "complete")
            self.assertEqual(state["stages"]["remediation"]["status"], "awaiting_approval")
            self.assertFalse((root / "docs/acima/adoption-handoff.md").exists())
            state = workflow.remediate(root, "none", approved_by="Repository owner")
            self.assertTrue((root / "docs/acima/adoption-handoff.md").is_file())

    def test_preflight_requires_an_explicit_full_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            command = [sys.executable, str(ROOT / "skills/acima-adoption/scripts/preflight.py"),
                       "--project", str(root), "--format", "json"]
            no_choice = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(no_choice.returncode, 0, no_choice.stderr)
            self.assertIsNone(json.loads(no_choice.stdout)["automation"]["mode"])
            unauthorized = subprocess.run(command + ["--automation-mode", "full"],
                                          capture_output=True, text=True)
            self.assertEqual(unauthorized.returncode, 2)
            self.assertIn("authorize-full-automation", unauthorized.stderr)
            authorized = subprocess.run(command + ["--automation-mode", "full",
                                                   "--authorize-full-automation"],
                                        capture_output=True, text=True)
            self.assertEqual(authorized.returncode, 0, authorized.stderr)
            self.assertEqual(json.loads(authorized.stdout)["automation"]["mode"], "full")

    def test_cli_exposes_the_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            result = subprocess.run(
                [sys.executable, str(ROOT / "tools/acima.py"), "adoption", "start",
                 "--root", str(root), "--mode", "guided", "--format", "json"],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["mode"], "guided")
            status = subprocess.run(
                [sys.executable, str(ROOT / "tools/acima.py"), "adoption", "status",
                 "--root", str(root), "--format", "json"], capture_output=True, text=True)
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertEqual(json.loads(status.stdout)["mode"], "guided")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            full = subprocess.run(
                [sys.executable, str(ROOT / "tools/acima.py"), "adoption", "start",
                 "--root", str(root), "--mode", "full", "--authorize-full", "--format", "json"],
                capture_output=True, text=True)
            self.assertEqual(full.returncode, 0, full.stderr)
            declined = subprocess.run(
                [sys.executable, str(ROOT / "tools/acima.py"), "adoption", "remediate",
                 "--root", str(root), "--choice", "none", "--format", "json"],
                capture_output=True, text=True)
            self.assertEqual(declined.returncode, 0, declined.stderr)
            self.assertEqual(json.loads(declined.stdout)["remediation"]["outcome"], "declined")

    def test_remediation_selected_all_greenfield_and_stale_behavior(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            workflow.start(root, "full", authorize_full=True)
            plan = json.loads((root / "docs/acima/remediation-plan.json").read_text(encoding="utf-8"))
            self.assertEqual(plan["maturity"]["mode"], "greenfield")
            unconfirmed = workflow.remediate(root, "all", approved_by="Owner")
            self.assertEqual(unconfirmed["stages"]["remediation"]["status"], "awaiting_approval")
            self.assertIn("return 1", (root / "src/orders/service.py").read_text(encoding="utf-8"))
            self.assertIn("Apply all", plan["recommendation"])
            self.assertFalse(plan["risk"]["requiresTwoConfirmations"])
            plan["recommendations"] = [
                {"id": "orders", "title": "Update orders", "status": "ready", "affectedFiles": ["src/orders/service.py"],
                 "changes": [{"action": "replace", "path": "src/orders/service.py", "find": "return 1", "replace": "return 2"}]},
                {"id": "billing", "title": "Update billing", "status": "ready", "affectedFiles": ["src/billing/service.py"],
                 "changes": [{"action": "replace", "path": "src/billing/service.py", "find": "return 1", "replace": "return 3"}]},
            ]
            (root / "docs/acima/remediation-plan.json").write_text(json.dumps(plan), encoding="utf-8")
            state = workflow.remediate(root, "selected", selected=["orders"], approved_by="Owner", confirm=True)
            self.assertEqual(state["remediation"]["outcome"], "complete")
            self.assertIn("return 2", (root / "src/orders/service.py").read_text(encoding="utf-8"))
            self.assertIn("return 1", (root / "src/billing/service.py").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            workflow.start(root, "full", authorize_full=True)
            plan = json.loads((root / "docs/acima/remediation-plan.json").read_text(encoding="utf-8"))
            plan["recommendations"] = [
                {"id": "orders", "title": "Update orders", "status": "ready", "affectedFiles": ["src/orders/service.py"],
                 "changes": [{"action": "replace", "path": "src/orders/service.py", "find": "return 1", "replace": "return 2"}]},
                {"id": "billing", "title": "Update billing", "status": "ready", "affectedFiles": ["src/billing/service.py"],
                 "changes": [{"action": "replace", "path": "src/billing/service.py", "find": "return 1", "replace": "return 3"}]},
            ]
            (root / "docs/acima/remediation-plan.json").write_text(json.dumps(plan), encoding="utf-8")
            state = workflow.remediate(root, "all", approved_by="Owner", confirm=True)
            self.assertEqual(state["remediation"]["outcome"], "complete")
            self.assertIn("return 2", (root / "src/orders/service.py").read_text(encoding="utf-8"))
            self.assertIn("return 3", (root / "src/billing/service.py").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            workflow.start(root, "full", authorize_full=True)
            write(root, "src/orders/service.py", "def place():\n    return 9\n")
            state = workflow.remediate(root, "all", approved_by="Owner", confirm=True)
            self.assertEqual(state["stages"]["remediation"]["status"], "blocked")
            self.assertIn("return 9", (root / "src/orders/service.py").read_text(encoding="utf-8"))

    def test_small_brownfield_needs_one_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            for index in range(12):
                write(root, "src/orders/extra%s.py" % index, "def value():\n    return %s\n" % index)
            workflow.start(root, "full", authorize_full=True)
            plan = json.loads((root / "docs/acima/remediation-plan.json").read_text(encoding="utf-8"))
            self.assertEqual(plan["maturity"]["mode"], "brownfield")
            self.assertFalse(plan["risk"]["requiresTwoConfirmations"])
            plan["recommendations"] = [{
                "id": "orders", "title": "Update orders", "status": "ready",
                "affectedFiles": ["src/orders/service.py"],
                "changes": [{"action": "replace", "path": "src/orders/service.py",
                             "find": "return 1", "replace": "return 2"}],
            }]
            (root / "docs/acima/remediation-plan.json").write_text(json.dumps(plan), encoding="utf-8")
            state = workflow.remediate(root, "all", approved_by="Owner", confirm=True)
            self.assertEqual(state["remediation"]["outcome"], "complete")
            self.assertIn("return 2", (root / "src/orders/service.py").read_text(encoding="utf-8"))

    def test_large_brownfield_needs_two_distinct_confirmations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            for index in range(24):
                write(root, "src/orders/extra%s.py" % index, "def value():\n    return %s\n" % index)
            workflow.start(root, "full", authorize_full=True)
            plan = json.loads((root / "docs/acima/remediation-plan.json").read_text(encoding="utf-8"))
            self.assertEqual(plan["maturity"]["mode"], "brownfield")
            plan["recommendations"] = [{
                "id": "contract", "title": "Change contract", "status": "ready",
                "affectedFiles": ["src/orders/service.py"],
                "changes": [{"action": "replace", "path": "src/orders/service.py", "find": "return 1", "replace": "return 2",
                             "contractChange": True}],
            }]
            (root / "docs/acima/remediation-plan.json").write_text(json.dumps(plan), encoding="utf-8")
            first = workflow.remediate(root, "all", approved_by="Owner", confirm_scope=True)
            self.assertEqual(first["stages"]["remediation"]["status"], "awaiting_approval")
            self.assertEqual(first["remediation"]["scopeAcknowledged"], True)
            self.assertIn("return 1", (root / "src/orders/service.py").read_text(encoding="utf-8"))
            second = workflow.remediate(root, "all", approved_by="Owner", confirm_implementation=True)
            self.assertEqual(second["remediation"]["outcome"], "complete")
            self.assertIn("return 2", (root / "src/orders/service.py").read_text(encoding="utf-8"))

    def test_manual_recommendations_are_not_reported_as_complete(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            workflow.start(root, "full", authorize_full=True)
            state = workflow.remediate(root, "all", approved_by="Owner", confirm=True)
            self.assertEqual(state["stages"]["remediation"]["status"], "blocked")
            result = json.loads((root / "docs/acima/remediation-result.json").read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "blocked")
            self.assertTrue(result["failures"])
            self.assertFalse(result["changed"])

    def test_report_renders_workflow_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            workflow.start(root, "guided")
            model = {
                "schemaVersion": "1.0", "generatedAt": "2026-11-11T00:00:00Z",
                "repository": {"name": "target", "path": str(root)},
                "recommendation": {"status": "INSUFFICIENT_EVIDENCE", "summary": "Review needed."},
                "overview": {"plainLanguage": "A proposal is waiting."},
                "adoptionWorkflow": workflow.status(root),
                "remediation": {"choice": "none", "status": "declined",
                                "claim": "No application source was changed."},
            }
            source = root / "model.json"
            source.write_text(json.dumps(model), encoding="utf-8")
            target = root / "report"
            result = subprocess.run([sys.executable, str(ROOT / "skills/acima-adoption/scripts/render_report.py"),
                                     "--input", str(source), "--out-dir", str(target)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            plan = (target / "plan.html").read_text(encoding="utf-8")
            self.assertIn("ADOPTION WORKFLOW", plan)
            self.assertIn("Guided", plan)
            self.assertIn("Review the proposed module map", plan)
            self.assertIn("IMMEDIATE REMEDIATION", plan)
            self.assertIn("No application source was changed", plan)

    def test_reports_are_never_modified_outside_the_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root = parent / "target"
            root.mkdir()
            fixture(root)
            outside = parent / "outside.txt"
            outside.write_text("do not touch", encoding="utf-8")
            before = outside.read_bytes()
            workflow.start(root, "guided")
            self.assertEqual(outside.read_bytes(), before)
            self.assertEqual(workflow.status(root)["mode"], "guided")


if __name__ == "__main__":
    unittest.main()
