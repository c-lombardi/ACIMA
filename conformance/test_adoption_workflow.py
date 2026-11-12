#!/usr/bin/env python3
"""End-to-end orchestration and consent regressions for adoption modes."""
from __future__ import annotations

import hashlib
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


def write_review(root: Path) -> Path:
    catalog_path = ROOT / "tools/acima-spec/rules.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    evidence_lines = [
        "Synthetic fixture inventory evidence for catalog requirement %s." % rule["id"]
        for rule in catalog["rules"]
    ]
    write(root, "acima/evidence/review-evidence.txt", "\n".join(evidence_lines) + "\n")
    document = {
        "schemaVersion": "1.0",
        "reviewer": "Automated test fixture",
        "reviewedOn": workflow._today(),
        "catalogSha256": hashlib.sha256(catalog_path.read_bytes()).hexdigest(),
        "rules": [
            {
                "rule": rule["id"],
                "status": "gap",
                "rationale": "Synthetic test disposition for %s; this fixture exercises review validation, not semantic conformance." % rule["id"],
                "evidence": [{
                    "kind": "inventory",
                    "path": "acima/evidence/review-evidence.txt",
                    "startLine": index + 1,
                    "endLine": index + 1,
                    "quote": evidence_lines[index],
                    "observation": "Inspected the dedicated fixture evidence line for %s." % rule["id"],
                }],
            }
            for index, rule in enumerate(catalog["rules"])
        ],
    }
    path = write(root, "acima/evidence/qualitative-review.json", json.dumps(document))
    return path


def fixture(root: Path, *, manifests: bool = True) -> None:
    write(root, "src/orders/service.py", "def place():\n    return 1\n")
    write(root, "src/billing/service.py", "def charge():\n    return 1\n")
    if manifests:
        write(root, "src/orders/pyproject.toml", "[project]\nname = 'orders'\n")
        write(root, "src/billing/pyproject.toml", "[project]\nname = 'billing'\n")
    write_review(root)


def snapshot(root: Path) -> dict[str, bytes]:
    return {path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob("*") if path.is_file()}


def map_review(root: Path) -> Path:
    proposal = json.loads((root / "acima/evidence/module-map.proposal.json").read_text(encoding="utf-8"))
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
    document = {
        "version": 2, "approvedBy": "Repository owner", "approvedOn": workflow._today(),
        "objectives": [
            {"id": "assessment", "disposition": "required"},
            {"id": "local-enforcement", "disposition": "approved"},
            {"id": "baseline-waivers", "disposition": "approved"},
            {"id": "ci-enforcement", "disposition": "approved"},
            {"id": "developer-handoff", "disposition": "approved"},
            {"id": "agent-guidance", "disposition": "approved"},
            {"id": "adoption-notifications", "disposition": "deferred"},
            {"id": "source-remediation", "disposition": "deferred"},
        ],
        "approvedPaths": [],
    }
    document["approvedPaths"] = workflow._implementation_paths(root, document)
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def approve_scope(root: Path, scope_path: Path) -> dict:
    state = workflow._load(root)
    report = state["artifacts"]["proposalReport"]
    return workflow.approve(
        root, scope=scope_path,
        reviewed_report_sha256=report["sha256"],
        reviewed_by="Repository owner",
    )


def remediate(root: Path, choice: str, *, selected: list[str] | None = None,
              approved_by: str = "Repository owner", **kwargs) -> dict:
    if choice == "none":
        return workflow.remediate(root, choice, approved_by=approved_by, **kwargs)
    plan_path = root / workflow.REMEDIATION_PLAN
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    items = plan.get("recommendations") or []
    if choice == "all":
        chosen = [item for item in items if item.get("status") == "ready"]
    else:
        ids = set(selected or [])
        chosen = [item for item in items if item.get("id") in ids]
    paths = sorted({
        str(change.get("path")).replace("\\", "/")
        for item in chosen for change in (item.get("changes") or [])
        if isinstance(change, dict) and change.get("path")
    })
    return workflow.remediate(
        root, choice, selected=selected, approved_by=approved_by,
        approved_plan_sha256=workflow._sha(plan_path),
        approved_paths=paths, **kwargs,
    )


def full_start(root: Path) -> dict:
    # Full/automated preparation must be reviewed before application. These tests
    # explicitly provide a pre-existing authoritative map and a user-approved scope.
    catalog = json.loads((ROOT / "tools/acima-spec/rules.json").read_text(encoding="utf-8"))
    write(root, "acima.config.json", json.dumps({
        "standard": catalog["version"], "mode": "base", "language": "python",
        "level": "L1", "root": ".",
        "units": [
            {"id": "orders", "module": "Orders", "role": "implementation", "paths": ["src/orders"]},
            {"id": "billing", "module": "Billing", "role": "implementation", "paths": ["src/billing"]},
        ],
    }))
    workflow.start(root, "full", authorize_full=True, reviewer="test mode selection")
    return approve_scope(root, scope(root))


class AdoptionWorkflowTests(unittest.TestCase):
    def test_guided_start_generates_deliverables_but_no_implementation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            before = snapshot(root)
            state = workflow.start(root, "guided")
            self.assertEqual(state["mode"], "guided")
            self.assertEqual(state["stages"]["module_map"]["status"], "awaiting_approval")
            self.assertEqual(state["stages"]["adoption_proposal"]["status"], "in_progress")
            self.assertFalse((root / "acima.config.json").exists())
            self.assertFalse((root / "acima/tooling/python/acima_arch.py").exists())
            self.assertTrue((root / "acima/evidence/module-map.proposal.json").is_file())
            self.assertFalse((root / "acima/report/adoption-proposal.md").exists())
            self.assertTrue((root / "acima/state.json").is_file())
            after = snapshot(root)
            unchanged = {path for path in before if path.startswith("src/")}
            self.assertTrue(all(after[path] == before[path] for path in unchanged))

    def test_start_requires_a_complete_evidence_backed_56_rule_review(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(root, "src/orders/service.py", "def place():\\n    return 1\\n")
            with self.assertRaisesRegex(workflow.WorkflowError, "56-rule qualitative review is mandatory"):
                workflow.start(root, "guided")
            self.assertFalse((root / "acima/state.json").exists())

    def test_incomplete_qualitative_review_blocks_adoption(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            review_path = root / "acima/evidence/qualitative-review.json"
            document = json.loads(review_path.read_text(encoding="utf-8"))
            document["rules"].pop()
            review_path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(workflow.WorkflowError, "qualitative review is not decision-complete"):
                workflow.start(root, "guided")
            self.assertFalse((root / "acima/state.json").exists())

    def test_full_requires_explicit_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            with self.assertRaises(workflow.WorkflowError):
                workflow.start(root, "full")
            self.assertFalse((root / "acima/state.json").exists())

    def test_full_generates_enforcement_ci_state_and_verification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            write(root, ".github/workflows/existing.yml",
                  "name: existing\non: pull_request\njobs:\n  test:\n    runs-on: ubuntu-latest\n")
            state = full_start(root)
            self.assertEqual(state["mode"], "full")
            self.assertEqual(state["stages"]["module_map"]["status"], "complete")
            self.assertEqual(state["stages"]["adoption_proposal"]["status"], "complete")
            self.assertEqual(state["stages"]["implementation"]["status"], "complete")
            self.assertEqual(state["stages"]["ci"]["status"], "complete")
            self.assertEqual(state["stages"]["remediation"]["status"], "awaiting_approval")
            self.assertEqual(state["stages"]["verification"]["status"], "in_progress")
            self.assertTrue((root / "acima.config.json").is_file())
            self.assertTrue((root / "acima/tooling/python/acima_arch.py").is_file())
            self.assertTrue((root / ".github/workflows/acima.yml").is_file())
            self.assertTrue((root / "acima/evidence/remediation-plan.json").is_file())
            before = snapshot(root)
            source_before = {path: data for path, data in before.items() if path.startswith("src/")}
            state = remediate(root, "none", approved_by="Repository owner")
            self.assertEqual(state["stages"]["remediation"]["status"], "complete")
            self.assertEqual(state["remediation"]["outcome"], "declined")
            after = snapshot(root)
            self.assertTrue(all(after[path] == data for path, data in source_before.items()))
            verification = json.loads((root / "acima/evidence/verification.json").read_text(encoding="utf-8"))
            self.assertEqual(verification["positive"]["status"], "valid")
            self.assertEqual(verification["negative"]["status"], "detected")
            self.assertEqual(verification["status"], "verified")
            self.assertEqual(state["stages"]["verification"]["status"], "complete")
            self.assertEqual(state["stages"]["agent_guidance"]["status"], "awaiting_approval")
            self.assertNotIn("handoff", state["artifacts"])
            self.assertFalse((root / "acima/handoff/adoption-handoff.md").exists())
            state = workflow.guidance(root, approve=True)
            self.assertEqual(state["stages"]["agent_guidance"]["status"], "complete")
            self.assertEqual(state["stages"]["handoff"]["status"], "complete")
            self.assertIn("acima/handoff/adoption-handoff.md", state["artifacts"]["handoff"])

    def test_full_defers_manifest_only_candidate_ownership_without_writing_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root, manifests=True)
            state = workflow.start(root, "full", authorize_full=True, reviewer="candidate ownership test")
            self.assertEqual(state["stages"]["module_map"]["status"], "awaiting_approval")
            self.assertFalse((root / "acima.config.json").exists())
            self.assertFalse((root / "acima/tooling/python/acima_arch.py").exists())
            self.assertTrue((root / "acima/evidence/module-map.proposal.json").is_file())
            self.assertTrue((root / "acima/report/enforcement-proposal.json").is_file())
            self.assertTrue((root / "acima/report/ci-proposal.json").is_file())
            self.assertFalse((root / "acima/report/agent-guidance-proposal.md").exists())
            self.assertTrue((root / "acima/evidence/remediation-plan.json").is_file())
            self.assertFalse((root / "AGENTS.md").exists())
            report = state["artifacts"]["proposalReport"]
            self.assertEqual(state["stages"]["proposal_report"]["status"], "awaiting_approval")
            self.assertTrue((Path(report["directory"]) / "index.html").is_file())
            self.assertTrue((Path(report["directory"]) / "proposal.html").is_file())
            self.assertTrue((Path(report["directory"]) / "findings.html").is_file())
            self.assertTrue((Path(report["directory"]) / "files.html").is_file())
            self.assertTrue((Path(report["directory"]) / "plan.html").is_file())
            self.assertTrue((Path(report["directory"]) / "evidence.html").is_file())
            self.assertIn(report["sha256"], state["next"]["command"])
            report_data = json.loads((Path(report["directory"]) / "report-data.json").read_text(encoding="utf-8"))
            self.assertEqual(report_data["adoptionWorkflow"]["mode"], "full")
            self.assertEqual(report_data["moduleMap"]["authoritativeMap"]["unitCount"],
                             len(report_data["moduleMap"]["authoritativeUnits"]))
            proposal_page = (Path(report["directory"]) / "proposal.html").read_text(encoding="utf-8")
            self.assertIn("Proposed module boundaries", proposal_page)
            self.assertIn("CANDIDATE MODULES", proposal_page)
            self.assertNotIn("Existing authoritative ownership units", proposal_page)
            self.assertEqual(state["next"]["approvalRequired"], True)
            self.assertTrue(all(item.get("decision") != "accept" for item in
                                    state["artifacts"].get("moduleMap", {}).get("modules", []))
                            if state["artifacts"].get("moduleMap") else True)
            self.assertIn("ownership is not approved", state["stages"]["module_map"]["detail"].lower())

    def test_guided_approves_individual_map_and_scope_then_implements(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            workflow.start(root, "guided")
            state = workflow.approve(root, map_decisions=map_review(root))
            self.assertEqual(state["stages"]["module_map"]["status"], "complete")
            self.assertEqual(state["stages"]["adoption_proposal"]["status"], "complete")
            self.assertEqual(state["stages"]["proposal_report"]["status"], "awaiting_approval")
            report = state["artifacts"]["proposalReport"]
            self.assertEqual(workflow.report_digest(Path(report["directory"])), report["sha256"])
            self.assertTrue((Path(report["directory"]) / "index.html").is_file())
            self.assertTrue((Path(report["directory"]) / "proposal.html").is_file())
            report_data = json.loads((Path(report["directory"]) / "report-data.json").read_text(encoding="utf-8"))
            gap_ids = {item["rule"] for item in report_data["qualitativeReview"]["rules"] if item["status"] == "gap"}
            finding_ids = {ref for item in report_data["findings"] for ref in (item.get("requirementRefs") or [item.get("rule")]) if ref}
            self.assertEqual(gap_ids, finding_ids)
            benefit_details = report_data["assessmentSummary"]["benefitDetails"]
            self.assertEqual(len(report_data["outcomes"]), len(benefit_details))
            self.assertEqual(len(report_data["value"]["benefits"]), len(benefit_details))
            self.assertEqual(report_data["adoptionWorkflow"]["mode"], "guided")
            self.assertEqual(report_data["moduleMap"]["authoritativeMap"]["unitCount"],
                             len(report_data["moduleMap"]["authoritativeUnits"]))
            self.assertTrue((root / "acima/report/adoption-proposal.md").is_file())
            state = approve_scope(root, scope(root))
            self.assertEqual(state["stages"]["adoption_proposal"]["status"], "complete")
            self.assertTrue((root / "acima.config.json").is_file())
            self.assertTrue((root / "acima/tooling/python/acima_arch.py").is_file())
            self.assertTrue((root / "acima/evidence/verification.json").is_file())

    def test_workspace_readme_names_the_canonical_layout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            workflow.start(root, "guided")
            readme = (root / "acima/README.md").read_text(encoding="utf-8")
            for relative in ("acima/state.json", "acima/evidence/", "acima/report/",
                             "acima/handoff/", "acima/tooling/", "acima/optional/"):
                self.assertIn(relative, readme)
            self.assertFalse((root / "acima/tooling").exists())

    def test_generated_ci_command_runs_the_copied_tooling(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            write(root, ".github/workflows/existing.yml",
                  "name: existing\non: pull_request\njobs:\n  test:\n    runs-on: ubuntu-latest\n")
            full_start(root)
            ci = json.loads((root / "acima/evidence/ci-integration.json").read_text(encoding="utf-8"))
            self.assertIn("acima/tooling/python/acima_arch.py", ci["command"])
            workflow_text = (root / ".github/workflows/acima.yml").read_text(encoding="utf-8")
            self.assertIn(ci["command"], workflow_text)
            plan = workflow._enforcer(root, "python")
            self.assertIsNotNone(plan)
            code, out, err = workflow._run(plan["argv"], root)
            self.assertEqual(code, 0, err or out)
            payload = json.loads(out)
            self.assertEqual(payload.get("findings"), [])

    def test_no_ci_provider_gets_concrete_instructions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            state = full_start(root)
            ci = json.loads((root / "acima/evidence/ci-integration.json").read_text(encoding="utf-8"))
            report = state["artifacts"]["proposalReport"]
            report_data = json.loads((Path(report["directory"]) / "report-data.json").read_text(encoding="utf-8"))
            self.assertGreater(report_data["moduleMap"]["authoritativeMap"]["unitCount"], 0)
            self.assertEqual(report_data["moduleMap"]["authoritativeMap"]["unitCount"],
                             len(report_data["moduleMap"]["authoritativeUnits"]))
            proposal_page = (Path(report["directory"]) / "proposal.html").read_text(encoding="utf-8")
            self.assertIn("Existing authoritative ownership units", proposal_page)
            self.assertIn("Existing authoritative map", proposal_page)
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
            state = full_start(root)
            ci = json.loads((root / "acima/evidence/ci-integration.json").read_text(encoding="utf-8"))
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
            self.assertEqual(state["stages"]["proposal_report"]["status"], "awaiting_approval")
            self.assertFalse((root / "acima/evidence/adoption-scope.json").exists())
            self.assertFalse((root / "acima/tooling/python/acima_arch.py").exists())
            self.assertIn("HTML adoption proposal", state["next"]["action"])
            self.assertFalse(state["next"]["writes"])

    def test_scope_cannot_be_approved_before_the_map(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            workflow.start(root, "guided")
            with self.assertRaises(workflow.WorkflowError):
                workflow.approve(root, scope=scope(root))
            self.assertFalse((root / "acima.config.json").exists())
            self.assertFalse((root / "acima/evidence/adoption-scope.json").exists())

    def test_language_selection_uses_dominant_production_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index in range(5):
                write(root, "src/orders/service%s.cs" % index, "class Service%s {}" % index)
            write(root, "spike/probe.py", "VALUE = 1\n")
            write(root, "tests/test_probe.py", "def test(): pass\n")
            self.assertEqual(workflow._language(root), "dotnet")
            plan = workflow._enforcer(root, "dotnet")
            self.assertIsNotNone(plan)
            self.assertEqual(plan["target"], "acima/tooling/dotnet/Acima.ArchTests")
            copied = workflow._copy_enforcer(root, "dotnet")
            self.assertEqual(copied["status"], "implemented")
            self.assertTrue((root / "acima/tooling/dotnet/Acima.ArchTests/Program.cs").is_file())

    def test_resume_preserves_the_map_approval_and_waits_for_scope(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            workflow.start(root, "guided")
            workflow.approve(root, map_decisions=map_review(root))
            # A new process/load must recover the approved map and ask only for the missing scope.
            resumed = workflow.continue_workflow(root)
            self.assertEqual(resumed["stages"]["module_map"]["status"], "complete")
            self.assertIn("html", resumed["next"]["action"].lower())
            self.assertFalse((root / "acima/evidence/adoption-scope.json").exists())
            state = approve_scope(root, scope(root))
            self.assertEqual(state["stages"]["adoption_proposal"]["status"], "complete")
            self.assertEqual(state["stages"]["remediation"]["status"], "awaiting_approval")
            self.assertFalse((root / "acima/handoff/adoption-handoff.md").exists())
            state = remediate(root, "none", approved_by="Repository owner")
            self.assertEqual(state["stages"]["agent_guidance"]["status"], "awaiting_approval")
            self.assertFalse((root / "acima/handoff/adoption-handoff.md").exists())
            state = workflow.guidance(root, approve=True)
            self.assertEqual(state["stages"]["agent_guidance"]["status"], "complete")
            self.assertTrue((root / "acima/handoff/adoption-handoff.md").is_file())

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
            payload = json.loads(status.stdout)
            self.assertEqual(payload["mode"], "guided")
            self.assertEqual(payload["phase"], "assess")
            self.assertEqual(payload["phaseLabel"], "Phase 1 — Assess")
            human = subprocess.run(
                [sys.executable, str(ROOT / "tools/acima.py"), "adoption", "status",
                 "--root", str(root), "--format", "text"], capture_output=True, text=True)
            self.assertEqual(human.returncode, 0, human.stderr)
            self.assertIn("phase   Phase 1 — Assess", human.stdout)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            full = subprocess.run(
                [sys.executable, str(ROOT / "tools/acima.py"), "adoption", "start",
                 "--root", str(root), "--mode", "full", "--authorize-full", "--format", "json"],
                capture_output=True, text=True)
            self.assertEqual(full.returncode, 0, full.stderr)
            prepared = json.loads(full.stdout)
            self.assertEqual(prepared["stages"]["adoption_proposal"]["status"], "awaiting_approval")
            self.assertIn("consolidated", prepared["next"]["action"].lower())
            self.assertFalse((root / "acima.config.json").exists())
            self.assertFalse((root / "acima/tooling/python/acima_arch.py").exists())

    def test_remediation_selected_all_greenfield_and_stale_behavior(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            full_start(root)
            plan = json.loads((root / "acima/evidence/remediation-plan.json").read_text(encoding="utf-8"))
            self.assertEqual(plan["maturity"]["mode"], "greenfield")
            unconfirmed = remediate(root, "all", approved_by="Owner")
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
            (root / "acima/evidence/remediation-plan.json").write_text(json.dumps(plan), encoding="utf-8")
            state = remediate(root, "selected", selected=["orders"], approved_by="Owner", confirm=True)
            self.assertEqual(state["remediation"]["outcome"], "complete")
            self.assertIn("return 2", (root / "src/orders/service.py").read_text(encoding="utf-8"))
            self.assertIn("return 1", (root / "src/billing/service.py").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            full_start(root)
            plan = json.loads((root / "acima/evidence/remediation-plan.json").read_text(encoding="utf-8"))
            plan["recommendations"] = [
                {"id": "orders", "title": "Update orders", "status": "ready", "affectedFiles": ["src/orders/service.py"],
                 "changes": [{"action": "replace", "path": "src/orders/service.py", "find": "return 1", "replace": "return 2"}]},
                {"id": "billing", "title": "Update billing", "status": "ready", "affectedFiles": ["src/billing/service.py"],
                 "changes": [{"action": "replace", "path": "src/billing/service.py", "find": "return 1", "replace": "return 3"}]},
            ]
            (root / "acima/evidence/remediation-plan.json").write_text(json.dumps(plan), encoding="utf-8")
            state = remediate(root, "all", approved_by="Owner", confirm=True)
            self.assertEqual(state["remediation"]["outcome"], "complete")
            self.assertIn("return 2", (root / "src/orders/service.py").read_text(encoding="utf-8"))
            self.assertIn("return 3", (root / "src/billing/service.py").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            full_start(root)
            write(root, "src/orders/service.py", "def place():\n    return 9\n")
            state = remediate(root, "all", approved_by="Owner", confirm=True)
            self.assertEqual(state["stages"]["remediation"]["status"], "blocked")
            self.assertIn("return 9", (root / "src/orders/service.py").read_text(encoding="utf-8"))

    def test_small_brownfield_needs_one_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            for index in range(12):
                write(root, "src/orders/extra%s.py" % index, "def value():\n    return %s\n" % index)
            full_start(root)
            plan = json.loads((root / "acima/evidence/remediation-plan.json").read_text(encoding="utf-8"))
            self.assertEqual(plan["maturity"]["mode"], "brownfield")
            self.assertFalse(plan["risk"]["requiresTwoConfirmations"])
            plan["recommendations"] = [{
                "id": "orders", "title": "Update orders", "status": "ready",
                "affectedFiles": ["src/orders/service.py"],
                "changes": [{"action": "replace", "path": "src/orders/service.py",
                             "find": "return 1", "replace": "return 2"}],
            }]
            (root / "acima/evidence/remediation-plan.json").write_text(json.dumps(plan), encoding="utf-8")
            state = remediate(root, "all", approved_by="Owner", confirm=True)
            self.assertEqual(state["remediation"]["outcome"], "complete")
            self.assertIn("return 2", (root / "src/orders/service.py").read_text(encoding="utf-8"))

    def test_large_brownfield_needs_two_distinct_confirmations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            for index in range(24):
                write(root, "src/orders/extra%s.py" % index, "def value():\n    return %s\n" % index)
            full_start(root)
            plan = json.loads((root / "acima/evidence/remediation-plan.json").read_text(encoding="utf-8"))
            self.assertEqual(plan["maturity"]["mode"], "brownfield")
            plan["recommendations"] = [{
                "id": "contract", "title": "Change contract", "status": "ready",
                "affectedFiles": ["src/orders/service.py"],
                "changes": [{"action": "replace", "path": "src/orders/service.py", "find": "return 1", "replace": "return 2",
                             "contractChange": True}],
            }]
            (root / "acima/evidence/remediation-plan.json").write_text(json.dumps(plan), encoding="utf-8")
            first = remediate(root, "all", approved_by="Owner", confirm_scope=True)
            self.assertEqual(first["stages"]["remediation"]["status"], "awaiting_approval")
            self.assertEqual(first["remediation"]["scopeAcknowledged"], True)
            self.assertIn("return 1", (root / "src/orders/service.py").read_text(encoding="utf-8"))
            second = remediate(root, "all", approved_by="Owner", confirm_implementation=True)
            self.assertEqual(second["remediation"]["outcome"], "complete")
            self.assertIn("return 2", (root / "src/orders/service.py").read_text(encoding="utf-8"))

    def test_manual_recommendations_are_not_reported_as_complete(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            full_start(root)
            state = remediate(root, "all", approved_by="Owner", confirm=True)
            self.assertEqual(state["stages"]["remediation"]["status"], "blocked")
            result = json.loads((root / "acima/evidence/remediation-result.json").read_text(encoding="utf-8"))
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
            self.assertIn("Current phase: <b>Phase 1 — Assess</b>", plan)
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


    def test_direct_apply_cannot_use_a_draft_scope_or_existing_config_as_consent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            state = workflow.start(root, "guided")
            catalog = json.loads((ROOT / "tools/acima-spec/rules.json").read_text(encoding="utf-8"))
            write(root, "acima.config.json", json.dumps({
                "standard": catalog["version"], "mode": "base", "language": "python",
                "level": "L1", "root": ".",
                "units": [{"id": "orders", "module": "Orders", "role": "implementation",
                           "paths": ["src/orders"]}],
            }))
            workflow._write_scope(root, state)
            before = snapshot(root)
            with self.assertRaisesRegex(workflow.WorkflowError, "not explicit implementation authorization"):
                workflow._apply(root, state)
            after = snapshot(root)
            self.assertFalse((root / "acima/tooling/python/acima_arch.py").exists())
            self.assertFalse((root / "acima/evidence/enforcement.json").exists())
            self.assertEqual(after["src/orders/service.py"], before["src/orders/service.py"])

    def test_scope_without_reviewed_html_digest_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            workflow.start(root, "guided")
            workflow.approve(root, map_decisions=map_review(root))
            scope_path = scope(root)
            with self.assertRaisesRegex(workflow.WorkflowError, "must be identified"):
                workflow.approve(root, scope=scope_path)
            self.assertFalse((root / "acima/tooling/python/acima_arch.py").exists())
            self.assertFalse((root / "acima/evidence/adoption-scope.json").exists())

    def test_html_report_tampering_invalidates_the_review_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            workflow.start(root, "guided")
            state = workflow.approve(root, map_decisions=map_review(root))
            report = state["artifacts"]["proposalReport"]
            proposal_page = Path(report["proposalHtml"])
            proposal_page.write_text(proposal_page.read_text(encoding="utf-8") + "\n<!-- tampered -->\n",
                                     encoding="utf-8")
            with self.assertRaisesRegex(workflow.WorkflowError, "report changed after generation"):
                approve_scope(root, scope(root))
            self.assertFalse((root / "acima/tooling/python/acima_arch.py").exists())

    def test_recovery_branch_selection_does_not_authorize_implementation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            def git(*args: str) -> None:
                result = subprocess.run(["git", "-C", str(root), *args],
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
            git("init", "--initial-branch=main")
            git("config", "user.email", "acima-test@example.invalid")
            git("config", "user.name", "ACIMA test")
            git("add", ".")
            git("commit", "-m", "baseline")
            workflow.start(root, "guided")
            state = workflow.approve(root, map_decisions=map_review(root))
            report = state["artifacts"]["proposalReport"]
            git("switch", "-c", "recover-acima-adoption")
            with self.assertRaisesRegex(workflow.WorkflowError, "branch, commit, or working-tree content changed"):
                workflow.approve(
                    root, scope=scope(root),
                    reviewed_report_sha256=report["sha256"],
                    reviewed_by="Repository owner",
                )
            self.assertFalse((root / "acima/tooling/python/acima_arch.py").exists())
            self.assertFalse((root / "acima/evidence/enforcement.json").exists())

    def test_source_remediation_requires_plan_digest_and_exact_approved_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            full_start(root)
            plan_path = root / workflow.REMEDIATION_PLAN
            plan = {
                "maturity": {"mode": "greenfield"},
                "recommendations": [{
                    "id": "orders", "title": "Change orders", "status": "ready",
                    "changes": [{"action": "replace", "path": "src/orders/service.py",
                                 "find": "return 1", "replace": "return 2"}],
                }],
            }
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            before = (root / "src/orders/service.py").read_bytes()
            with self.assertRaisesRegex(workflow.WorkflowError, "exact SHA-256 digest"):
                workflow.remediate(root, "selected", selected=["orders"], approved_by="Owner",
                                    confirm=True)
            self.assertEqual((root / "src/orders/service.py").read_bytes(), before)
            with self.assertRaisesRegex(workflow.WorkflowError, "exact path approval"):
                workflow.remediate(
                    root, "selected", selected=["orders"], approved_by="Owner",
                    approved_plan_sha256=workflow._sha(plan_path), approved_paths=[],
                    confirm=True,
                )
            self.assertEqual((root / "src/orders/service.py").read_bytes(), before)

    def test_existing_scope_file_cannot_authorize_resume_without_approval_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            state = workflow.start(root, "guided")
            workflow._write_json(root, workflow.CONFIG_NAME, {
                "standard": "1.0.0", "mode": "base", "language": "python",
                "level": "L1", "root": ".",
                "units": [{"id": "orders", "module": "Orders", "role": "implementation",
                           "paths": ["src/orders"]}],
            })
            workflow._write_json(root, workflow.SCOPE_FILE, {
                "version": 1, "approvedBy": "Repository owner", "approvedOn": workflow._today(),
                "objectives": [{"id": "local-enforcement", "disposition": "approved"}],
                "approvedPaths": workflow._implementation_paths(root, {
                    "objectives": [{"id": "local-enforcement", "disposition": "approved"},
                                   {"id": "baseline-waivers", "disposition": "approved"}]
                }),
                "authorization": {"explicit": True},
            })
            state = workflow.continue_workflow(root)
            self.assertFalse((root / "acima/tooling/python/acima_arch.py").exists())
            self.assertNotEqual((state.get("implementationApproval") or {}).get("status"), "approved")

    def test_dotnet_positive_fixture_is_separate_and_known_compliant(self) -> None:
        result = workflow._positive_fixture("dotnet")
        self.assertEqual(result["status"], "valid", result)
        self.assertEqual(result["exitCode"], 0)
        self.assertGreater(result["sourceFiles"], 0)
        self.assertEqual(result["findingCount"], 0)
        self.assertEqual(result["evidenceType"], "isolated-known-compliant-fixture")


    def test_resume_reconciles_persisted_owner_map_approval_and_generates_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            state = workflow.start(root, "guided")
            proposal = json.loads((root / workflow.PROPOSAL_JSON).read_text(encoding="utf-8"))
            wrapper = {"proposal": proposal, "proposalId": proposal["proposalId"]}
            review_path = map_review(root)
            decisions = json.loads(review_path.read_text(encoding="utf-8"))
            write(root, workflow.OWNER_MAP_REVIEW_FILE, json.dumps(decisions))
            reviewed = workflow.apply_review(wrapper, decisions, root=root)
            self.assertEqual(reviewed["status"], "approved", reviewed.get("approval"))
            approved_config = workflow.build_config(
                wrapper, reviewed, language=workflow._language(root)
            )
            write(root, workflow.CONFIG_NAME, json.dumps(approved_config))
            # Simulate the agent having persisted the owner's approval/config after
            # the workflow checkpoint was created, but before the state was advanced.
            self.assertEqual(state["stages"]["module_map"]["status"], "awaiting_approval")
            self.assertFalse((Path(state["artifacts"].get("proposalReport", {}).get("directory", "missing"))
                              / "index.html").exists())

            resumed = workflow.continue_workflow(root)
            self.assertEqual(resumed["stages"]["module_map"]["status"], "complete")
            self.assertEqual(resumed["stages"]["adoption_proposal"]["status"], "complete")
            self.assertEqual(resumed["stages"]["proposal_report"]["status"], "awaiting_approval")
            self.assertTrue(resumed["decisions"][-1]["reconciled"])
            self.assertIn("HTML adoption proposal", resumed["next"]["action"])
            report = resumed["artifacts"]["proposalReport"]
            directory = Path(report["directory"])
            for page in ("index.html", "proposal.html", "findings.html",
                         "files.html", "plan.html", "evidence.html"):
                self.assertTrue((directory / page).is_file(), page)
            self.assertFalse((root / "acima/tooling/python/acima_arch.py").exists())
            self.assertFalse((root / "acima/evidence/adoption-scope.json").exists())

    def test_resume_does_not_infer_map_consent_from_config_without_matching_review(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            workflow.start(root, "guided")
            write(root, workflow.CONFIG_NAME, json.dumps({
                "standard": "1.9.0-draft.2", "mode": "base", "language": "python",
                "level": "L1", "root": ".", "units": [
                    {"id": "orders", "module": "orders", "role": "implementation",
                     "paths": ["src/orders"]},
                    {"id": "billing", "module": "billing", "role": "implementation",
                     "paths": ["src/billing"]},
                ],
            }))
            state = workflow.continue_workflow(root)
            self.assertEqual(state["stages"]["module_map"]["status"], "awaiting_approval")
            self.assertFalse((root / "acima/report/adoption-proposal.json").exists())
            self.assertFalse((root / "acima/tooling/python/acima_arch.py").exists())

class CanonicalPhaseTests(unittest.TestCase):
    """The product phase is derived from recorded stage status, never guessed by a caller."""

    def stage(self, name: str, status: str) -> dict:
        return {"name": name, "label": name, "status": status, "detail": "",
                "evidence": None, "nextAction": "", "updatedAt": ""}

    def phase(self, **statuses: str) -> str:
        return workflow._current_phase(
            {"stages": {name: self.stage(name, status) for name, status in statuses.items()}})

    def test_every_stage_belongs_to_one_canonical_phase(self) -> None:
        self.assertEqual(list(workflow.PHASE_ORDER), [
            "start", "assess", "explain_and_propose", "review_and_authorize",
            "implement", "verify_and_hand_off"])
        self.assertEqual(set(workflow.STAGE_PHASE), set(workflow.STAGE_ORDER))
        for phase in workflow.STAGE_PHASE.values():
            self.assertIn(phase, workflow.PHASE_ORDER)
        self.assertIn("review_and_authorize", set(workflow.STAGE_PHASE.values()))

    def test_empty_state_is_start(self) -> None:
        self.assertEqual(workflow._current_phase({"stages": {}}), "start")

    def test_assessment_stage_maps_to_assess(self) -> None:
        self.assertEqual(self.phase(assessment="in_progress"), "assess")

    def test_awaiting_review_stays_in_assess(self) -> None:
        self.assertEqual(self.phase(preflight="complete", module_map="awaiting_approval"), "assess")

    def test_html_report_review_maps_to_review_and_authorize(self) -> None:
        self.assertEqual(self.phase(
            preflight="complete", discovery="complete", assessment="complete",
            module_map="complete", adoption_proposal="complete",
            proposal_report="awaiting_approval"), "review_and_authorize")

    def test_blocked_stage_holds_its_phase(self) -> None:
        self.assertEqual(self.phase(
            preflight="complete", discovery="complete", assessment="complete",
            module_map="complete", adoption_proposal="complete", proposal_report="complete",
            ci="blocked"), "implement")

    def test_deferred_stage_does_not_advance_the_journey(self) -> None:
        self.assertEqual(self.phase(
            preflight="complete", discovery="complete", assessment="complete",
            module_map="complete", adoption_proposal="deferred"), "explain_and_propose")

    def test_implementation_stage_maps_to_implement(self) -> None:
        self.assertEqual(self.phase(proposal_report="complete", implementation="in_progress"),
                         "implement")

    def test_active_later_stage_is_not_pulled_back_by_missing_earlier_records(self) -> None:
        self.assertEqual(self.phase(implementation="in_progress"), "implement")

    def test_completed_later_stage_with_absent_earlier_records_holds_at_first_missing_phase(self) -> None:
        self.assertEqual(self.phase(proposal_report="complete"), "assess")

    def test_deferred_optional_stage_does_not_rewind_a_completed_workflow(self) -> None:
        self.assertEqual(self.phase(
            preflight="complete", discovery="complete", assessment="complete",
            module_map="complete", adoption_proposal="complete", proposal_report="complete",
            implementation="complete", architecture_tests="complete", ci="complete",
            remediation="complete", verification="complete", agent_guidance="deferred",
            adoption_notifications="deferred", handoff="complete"), "verify_and_hand_off")

    def test_all_complete_is_verify_and_hand_off(self) -> None:
        self.assertEqual(self.phase(**{name: "complete" for name in workflow.STAGE_ORDER}),
                         "verify_and_hand_off")

    def test_summary_exposes_the_canonical_label(self) -> None:
        summary = workflow._summary({"mode": "guided", "stages": {
            "preflight": self.stage("preflight", "complete"),
            "discovery": self.stage("discovery", "awaiting_approval")}})
        self.assertEqual(summary["phase"], "assess")
        self.assertEqual(summary["phaseLabel"], "Phase 1 — Assess")
        self.assertEqual(summary["phaseOrder"], list(workflow.PHASE_ORDER))


if __name__ == "__main__":
    unittest.main()
