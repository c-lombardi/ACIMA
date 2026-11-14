#!/usr/bin/env python3
"""End-to-end orchestration and consent regressions for adoption modes."""
from __future__ import annotations

import hashlib
import json
import re
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


def decisions_file(root: Path, state: dict, *, answers: list | None = None, review: bool = True,
                   **overrides) -> Path:
    report = state["artifacts"]["proposalReport"]
    document = {
        "schemaVersion": "1.0",
        "kind": "acima-adoption-decisions",
        "reportId": report["reportId"],
        "reportSha256": report["sha256"],
        "decisionSha256": report["decisionSha256"],
        "proposalSha256": report["proposalSha256"],
        "reviewer": "Repository owner",
        "decidedOn": workflow._today(),
        "source": "html-report",
        "package": "custom",
        "supersedes": None,
        "answers": ([{"kind": "report-review", "id": "all-pages", "decision": "accept"}]
                    if review else []),
    }
    document.update(overrides)
    document["answers"].extend(answers or [])
    path = root.parent / (root.name + "-decisions-%s.json" % len(list(root.parent.glob(root.name + "-decisions-*.json"))))
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def all_objectives_and_paths(root: Path, state: dict) -> tuple[list[str], list[str]]:
    document = workflow._scope_document(state, root, ci_available=True)
    objectives = [item["id"] for item in document["objectives"]]
    for item in document["objectives"]:
        item["disposition"] = "approved"
    return objectives, workflow._implementation_paths(root, document)


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
    # Legacy scenario name: the fixture starts one flow with a pre-existing authoritative map.
    catalog = json.loads((ROOT / "tools/acima-spec/rules.json").read_text(encoding="utf-8"))
    write(root, "acima.config.json", json.dumps({
        "standard": catalog["version"], "mode": "base", "language": "python",
        "level": "L1", "root": ".",
        "units": [
            {"id": "orders", "module": "Orders", "role": "implementation", "paths": ["src/orders"]},
            {"id": "billing", "module": "Billing", "role": "implementation", "paths": ["src/billing"]},
        ],
    }))
    workflow.start(root, "guided")
    state = approve_scope(root, scope(root))
    if state["stages"].get("ci", {}).get("status") == "awaiting_approval":
        workflow.ci(root, plan_only=True)
        state = workflow.ci(
            root, approve=True,
            plan_sha256=workflow._sha(root / workflow.adoption_ci.PLAN_FILE),
            reviewed_by="Repository owner",
        )
    return state


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

    def test_automated_adoption_cannot_be_started(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            with self.assertRaisesRegex(workflow.WorkflowError, "automated adoption was removed"):
                workflow.start(root, "full", authorize_full=True)
            self.assertFalse((root / "acima/state.json").exists())

    def test_full_generates_enforcement_ci_state_and_verification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            write(root, ".github/workflows/existing.yml",
                  "name: existing\non: pull_request\njobs:\n  test:\n    runs-on: ubuntu-latest\n")
            state = full_start(root)
            self.assertEqual(state["mode"], "guided")
            self.assertEqual(state["stages"]["module_map"]["status"], "complete")
            self.assertEqual(state["stages"]["adoption_proposal"]["status"], "complete")
            self.assertEqual(state["stages"]["implementation"]["status"], "complete")
            self.assertEqual(state["stages"]["ci"]["status"], "complete")
            self.assertEqual(state["stages"]["remediation"]["status"], "awaiting_approval")
            self.assertEqual(state["stages"]["verification"]["status"], "in_progress")
            self.assertTrue((root / "acima.config.json").is_file())
            self.assertTrue((root / "acima/tooling/python/acima_arch.py").is_file())
            self.assertTrue((root / ".github/workflows/acima.yml").is_file())
            self.assertIn("existing", (root / ".github/workflows/existing.yml").read_text(encoding="utf-8"))
            self.assertTrue((root / "acima/evidence/remediation-plan.json").is_file())
            before = snapshot(root)
            source_before = {path: data for path, data in before.items() if path.startswith("src/")}
            state = remediate(root, "none", approved_by="Repository owner")
            self.assertEqual(state["stages"]["remediation"]["status"], "deferred")
            self.assertEqual(state["remediation"]["outcome"], "declined")
            self.assertEqual(state["remediationRounds"][-1]["choice"], "none")
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

    def test_one_flow_holds_at_the_map_and_writes_no_preparation_package(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root, manifests=True)
            state = workflow.start(root, "guided")
            self.assertEqual(state["stages"]["module_map"]["status"], "awaiting_approval")
            self.assertFalse((root / "acima.config.json").exists())
            self.assertFalse((root / "acima/tooling/python/acima_arch.py").exists())
            self.assertTrue((root / "acima/evidence/module-map.proposal.json").is_file())
            self.assertFalse((root / "acima/report/enforcement-proposal.json").exists())
            self.assertFalse((root / "acima/report/ci-proposal.json").exists())
            self.assertFalse((root / "acima/evidence/remediation-plan.json").exists())
            self.assertFalse((root / "AGENTS.md").exists())
            self.assertNotIn("proposalReport", state["artifacts"])
            self.assertEqual(state["stages"]["adoption_proposal"]["status"], "in_progress")
            self.assertIn("map", state["next"]["action"].lower())

    def test_guided_approves_individual_map_and_scope_then_implements(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            workflow.start(root, "guided")
            state = workflow.approve(root, map_decisions=map_review(root))
            self.assertEqual(state["stages"]["module_map"]["status"], "complete")
            self.assertEqual(state["stages"]["adoption_proposal"]["status"], "complete")
            self.assertEqual(state["stages"]["proposal_report"]["status"], "awaiting_approval")
            # Map approval records a proposed config. Only implementation authorization writes
            # the root config.
            self.assertFalse((root / "acima.config.json").exists())
            self.assertTrue((root / workflow.PROPOSED_CONFIG).is_file())
            report = state["artifacts"]["proposalReport"]
            # Every save refreshes the report's progress sections, so the directory matches the
            # live digest while the reviewed generation digest remains the review identity.
            self.assertEqual(workflow.report_digest(Path(report["directory"])), report["liveSha256"])
            self.assertEqual(report["progressStatus"], "current")
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

    def test_report_progress_is_refreshed_without_a_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            workflow.start(root, "guided")
            workflow.approve(root, map_decisions=map_review(root))
            state = workflow._load(root)
            report = state["artifacts"]["proposalReport"]
            data_path = Path(report["directory"]) / "report-data.json"
            before = json.loads(data_path.read_text(encoding="utf-8"))
            reviewed, decision = report["sha256"], report["decisionSha256"]
            self.assertEqual(before["adoptionWorkflow"]["currentStage"]["name"], "proposal_report")
            approve_scope(root, scope(root))
            state = workflow._load(root)
            report = state["artifacts"]["proposalReport"]
            after = json.loads(data_path.read_text(encoding="utf-8"))
            stages = {stage["name"]: stage["status"]
                      for stage in after["adoptionWorkflow"]["stages"]}
            self.assertEqual(stages["implementation"], "complete")
            self.assertEqual(after["adoptionWorkflow"]["currentStage"]["name"], "ci")
            self.assertTrue(after["milestones"]["implementationComplete"])
            self.assertNotEqual(before["adoptionWorkflow"], after["adoptionWorkflow"])
            # The progress refresh must never touch the reviewed decision content.
            self.assertEqual(report["sha256"], reviewed)
            self.assertEqual(report["decisionSha256"], decision)
            for key in ("findings", "moduleMap", "fileImpact", "qualitativeReview"):
                self.assertEqual(after[key], before[key])
            self.assertEqual(report["progressStatus"], "current")
            plan_page = (Path(report["directory"]) / "plan.html").read_text(encoding="utf-8")
            self.assertIn("Enforcement implementation", plan_page)
            self.assertIn("Current stage: <b>CI integration", plan_page)

    def test_progress_refresh_tolerates_a_legacy_schema_11_report(self) -> None:
        import adoption_reports
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            workflow.start(root, "guided")
            state = workflow.approve(root, map_decisions=map_review(root))
            report = dict(state["artifacts"]["proposalReport"])
            data_path = Path(report["directory"]) / "report-data.json"
            legacy = json.loads(data_path.read_text(encoding="utf-8"))
            legacy["schemaVersion"] = "1.1"
            legacy.pop("progressSections", None)
            data_path.write_text(json.dumps(legacy), encoding="utf-8")
            report["decisionSha256"] = adoption_reports.decision_digest(legacy)
            report["progressSha256"] = "0" * 64
            refreshed = adoption_reports.refresh_progress_report(report, state)
            self.assertEqual(refreshed["reportId"], report["reportId"])
            self.assertEqual(refreshed["sha256"], report["sha256"])
            self.assertEqual(refreshed["progressStatus"], "current")
            stored = json.loads(data_path.read_text(encoding="utf-8"))
            self.assertEqual(stored["schemaVersion"], "1.1")
            self.assertNotIn("progressSections", stored)
            self.assertTrue(stored["adoptionWorkflow"]["asOf"])
            metadata = json.loads((data_path.parent / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["progressStatus"], "current")
            self.assertEqual(metadata["sha256"], report["sha256"])
            # A model that would widen the write surface, or predate the contract, is still refused.
            wider = dict(legacy)
            wider["progressSections"] = ["adoptionWorkflow", "milestones", "findings"]
            data_path.write_text(json.dumps(wider), encoding="utf-8")
            with self.assertRaisesRegex(adoption_reports.AdoptionReportError, "may replace only"):
                adoption_reports.refresh_progress_report(dict(refreshed), state)
            ancient = dict(legacy)
            ancient["schemaVersion"] = "1.0"
            data_path.write_text(json.dumps(ancient), encoding="utf-8")
            with self.assertRaisesRegex(adoption_reports.AdoptionReportError, "predates"):
                adoption_reports.refresh_progress_report(dict(refreshed), state)

    def test_report_lives_in_the_repository_with_its_own_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            fixture(root)
            workflow.start(root, "guided")
            state = workflow.approve(root, map_decisions=map_review(root))
            report = state["artifacts"]["proposalReport"]
            report_directory = Path(report["directory"])
            self.assertTrue(report_directory.is_relative_to(root))
            self.assertEqual(report["relativeDirectory"], "acima/report/" + report["reportId"])
            metadata = json.loads((report_directory / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["reportId"], report["reportId"])
            self.assertEqual(metadata["sha256"], report["sha256"])
            self.assertEqual(metadata["decisionSha256"], report["decisionSha256"])
            model = json.loads((report_directory / "report-data.json").read_text(encoding="utf-8"))
            self.assertEqual(model["schemaVersion"], "1.3")
            self.assertEqual(model["progressSections"], ["adoptionWorkflow", "milestones"])
            self.assertTrue(model["adoptionWorkflow"]["asOf"])
            summary = workflow.status(root)
            self.assertEqual(summary["report"]["directory"], report["relativeDirectory"])
            self.assertFalse(summary["report"]["decisionsFile"])
            self.assertEqual(summary["report"]["sha256"], report["sha256"])
            # A decision file beside the report is not part of the report's identity.
            before = workflow.report_digest(report_directory)
            (report_directory / "decisions.json").write_text("{}", encoding="utf-8")
            self.assertEqual(workflow.report_digest(report_directory), before)
            self.assertTrue(workflow.status(root)["report"]["decisionsFile"])

    def test_regenerate_creates_a_new_identity_and_invalidates_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            workflow.start(root, "guided")
            state = workflow.approve(root, map_decisions=map_review(root))
            first = state["artifacts"]["proposalReport"]
            decisions_path = decisions_file(root, state)
            workflow.decisions(root, decisions_path)
            self.assertTrue((Path(first["directory"]) / "decisions.json").is_file())
            state = workflow.regenerate(root, reason="the report directory was removed by the OS")
            second = state["artifacts"]["proposalReport"]
            self.assertNotEqual(second["reportId"], first["reportId"])
            self.assertEqual(second["generation"], 1)
            self.assertEqual(state["proposalReview"]["status"], "awaiting_review")
            self.assertTrue((Path(second["directory"]) / "index.html").is_file())
            self.assertTrue((Path(first["directory"]) / "index.html").is_file())
            self.assertEqual(state["decisionSources"][0]["reportId"], first["reportId"])
            self.assertIn("regenerated", state["decisionSources"][0]["staleReason"])
            self.assertEqual(state["decisions"][-1]["id"], "report-regeneration")
            with self.assertRaisesRegex(workflow.WorkflowError, "reason"):
                workflow.regenerate(root, reason="  ")

    def test_decisions_file_derives_a_scope_draft_that_still_needs_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            workflow.start(root, "guided")
            state = workflow.approve(root, map_decisions=map_review(root))
            objectives, paths = all_objectives_and_paths(root, state)
            answers = [{"kind": "scope-objective", "id": name, "decision": "accept"}
                       for name in objectives]
            answers += [{"kind": "scope-path", "id": path, "decision": "accept"} for path in paths]
            result = workflow.decisions(root, decisions_file(root, state, answers=answers))
            self.assertEqual(result["status"], "applied")
            self.assertEqual(result["scopeDraft"], workflow.SCOPE_FILE)
            scope = workflow._read_json(root / workflow.SCOPE_FILE)
            self.assertEqual(scope["approvedBy"], "Repository owner")
            self.assertEqual(sorted(scope["approvedPaths"]), sorted(paths))
            self.assertFalse(scope["authorization"]["explicit"])
            self.assertEqual(scope["reportReview"]["status"], "reviewed")
            state = workflow._load(root)
            self.assertEqual(state["proposalReview"]["status"], "reviewed")
            self.assertEqual(len(state["decisionSources"]), 1)
            self.assertFalse((root / "acima/tooling/python/acima_arch.py").exists())
            # The derived draft is not consent: the existing approval command still runs and records it.
            state = approve_scope(root, root / workflow.SCOPE_FILE)
            self.assertEqual(state["stages"]["implementation"]["status"], "complete")
            self.assertTrue((root / "acima/tooling/python/acima_arch.py").is_file())

    def test_decisions_file_derives_a_scope_after_map_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root, manifests=True)
            workflow.start(root, "guided")
            workflow.approve(root, map_decisions=map_review(root))
            state = workflow._load(root)
            self.assertEqual(state["stages"]["module_map"]["status"], "complete")
            self.assertFalse((root / "acima.config.json").exists())
            self.assertTrue((root / workflow.PROPOSED_CONFIG).is_file())

            objectives, paths = all_objectives_and_paths(root, state)
            answers = [{"kind": "scope-objective", "id": name, "decision": "accept"}
                       for name in objectives]
            answers += [{"kind": "scope-path", "id": path, "decision": "accept"} for path in paths]
            result = workflow.decisions(root, decisions_file(root, state, answers=answers))
            self.assertEqual(result["status"], "applied")
            self.assertEqual(result["scopeDraft"], workflow.SCOPE_FILE)
            scope = workflow._read_json(root / workflow.SCOPE_FILE)
            self.assertFalse(scope["authorization"]["explicit"])

    def test_one_approve_decisions_command_records_intent_and_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            workflow.start(root, "guided")
            state = workflow.approve(root, map_decisions=map_review(root))
            objectives, paths = all_objectives_and_paths(root, state)
            answers = [{"kind": "scope-objective", "id": name, "decision": "accept"}
                       for name in objectives]
            answers += [{"kind": "scope-path", "id": path, "decision": "accept"} for path in paths]
            source = decisions_file(root, state, answers=answers)
            state = workflow.approve(root, decision_source=source)
            self.assertEqual(state["stages"]["implementation"]["status"], "complete")
            self.assertEqual(state["implementationApproval"]["status"], "approved")
            scope = workflow._read_json(root / workflow.SCOPE_FILE)
            self.assertTrue(scope["authorization"]["explicit"])
            self.assertEqual(sorted(scope["approvedPaths"]), sorted(paths))
            self.assertTrue((root / "acima.config.json").is_file())
            self.assertEqual(len(state["decisionSources"]), 1)

    def test_decisions_refuse_a_stale_report_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            workflow.start(root, "guided")
            state = workflow.approve(root, map_decisions=map_review(root))
            document = decisions_file(root, state, reportSha256="0" * 64)
            with self.assertRaisesRegex(workflow.WorkflowError, "different report version"):
                workflow.decisions(root, document)
            self.assertFalse((root / workflow.SCOPE_FILE).exists())

    def test_decisions_refuse_conflicts_without_an_explicit_supersede(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            workflow.start(root, "guided")
            state = workflow.approve(root, map_decisions=map_review(root))
            first = decisions_file(root, state, answers=[
                {"kind": "scope-objective", "id": "ci-enforcement", "decision": "accept"}])
            workflow.decisions(root, first)
            second = decisions_file(root, state, answers=[
                {"kind": "scope-objective", "id": "ci-enforcement", "decision": "reject"}])
            with self.assertRaisesRegex(workflow.WorkflowError, "conflicting answers"):
                workflow.decisions(root, second)
            third = decisions_file(root, state, supersedes=workflow._sha(first), answers=[
                {"kind": "scope-objective", "id": "ci-enforcement", "decision": "reject"}])
            workflow.decisions(root, third)
            state = workflow._load(root)
            self.assertEqual(state["decisionSources"][0]["status"], "superseded")
            self.assertEqual(state["decisionSources"][1]["status"], "in force")
            scope = workflow._read_json(root / workflow.SCOPE_FILE)
            objectives = {item["id"]: item["disposition"] for item in scope["objectives"]}
            self.assertEqual(objectives["ci-enforcement"], "declined")

    def test_decisions_defer_an_objective_whose_required_path_was_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            workflow.start(root, "guided")
            state = workflow.approve(root, map_decisions=map_review(root))
            objectives, paths = all_objectives_and_paths(root, state)
            excluded = "acima.config.json"
            selected = [path for path in paths if path != excluded]
            answers = [{"kind": "scope-objective", "id": name, "decision": "accept"}
                       for name in objectives]
            answers += [{"kind": "scope-path", "id": path, "decision": "accept"} for path in selected]
            result = workflow.decisions(root, decisions_file(root, state, answers=answers))
            self.assertTrue(result["deferrals"])
            self.assertEqual(result["deferrals"][0]["objective"], "local-enforcement")
            self.assertIn(excluded, result["deferrals"][0]["missingPaths"])
            scope = workflow._read_json(root / workflow.SCOPE_FILE)
            objectives_by_id = {item["id"]: item["disposition"] for item in scope["objectives"]}
            self.assertEqual(objectives_by_id["local-enforcement"], "deferred")
            self.assertNotIn(excluded, scope["approvedPaths"])

    def test_decisions_refuse_unknown_paths_and_stale_map_answers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            workflow.start(root, "guided")
            state = workflow.approve(root, map_decisions=map_review(root))
            unknown = decisions_file(root, state, answers=[
                {"kind": "scope-path", "id": "src/not-in-the-proposal.py", "decision": "accept"}])
            with self.assertRaisesRegex(workflow.WorkflowError, "does not include"):
                workflow.decisions(root, unknown)
            proposal = json.loads((root / workflow.PROPOSAL_JSON).read_text(encoding="utf-8"))
            stale_map = decisions_file(root, state, answers=[
                {"kind": "module", "id": proposal["modules"][0]["id"], "decision": "accept"}])
            with self.assertRaisesRegex(workflow.WorkflowError, "already approved"):
                workflow.decisions(root, stale_map)

    def test_decisions_record_remediation_answers_as_intent_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            workflow.start(root, "guided")
            state = workflow.approve(root, map_decisions=map_review(root))
            result = workflow.decisions(root, decisions_file(root, state, answers=[
                {"kind": "remediation", "id": "ACIMA-D001", "decision": "defer"}]))
            self.assertEqual(result["remediationAnswers"], 1)
            state = workflow._load(root)
            self.assertEqual(state["remediationAnswers"][0]["id"], "ACIMA-D001")
            self.assertFalse((root / "acima/evidence/remediation-result.json").exists())

    def test_decisions_contract_rejects_malformed_owner_input(self) -> None:
        sys.path.insert(0, str(ROOT / "conformance"))
        import adoption_decisions
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            workflow.start(root, "guided")
            state = workflow.approve(root, map_decisions=map_review(root))
            base = json.loads(decisions_file(root, state).read_text(encoding="utf-8"))
            cases = [
                ({"reviewer": "  "}, "reviewer"),
                ({"decidedOn": "2999-01-01"}, "decidedOn"),
                ({"package": "everything"}, "package"),
                ({"schemaVersion": "2.0"}, "schemaVersion"),
                ({"reportSha256": "not-a-digest"}, "reportSha256"),
                ({"answers": []}, "answers"),
                ({"answers": [{"kind": "module", "id": "x", "decision": "maybe"}]}, "decision"),
                ({"answers": [{"kind": "report-review", "id": "all-pages", "decision": "accept"},
                              {"kind": "report-review", "id": "all-pages", "decision": "accept"}]},
                 "repeats"),
                ({"answers": [{"kind": "scope-objective", "id": "ci-enforcement",
                              "decision": "modify"}]}, "modification"),
            ]
            for index, (changes, message) in enumerate(cases):
                document = json.loads(json.dumps(base))
                document.update(changes)
                path = root.parent / ("invalid-decisions-%s.json" % index)
                path.write_text(json.dumps(document), encoding="utf-8")
                with self.assertRaisesRegex(adoption_decisions.DecisionError, message):
                    adoption_decisions.load(path)

    def test_guided_report_offers_console_controls_and_no_script_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            workflow.start(root, "guided")
            state = workflow.approve(root, map_decisions=map_review(root))
            report = state["artifacts"]["proposalReport"]
            plan = (Path(report["directory"]) / "plan.html").read_text(encoding="utf-8")
            files = (Path(report["directory"]) / "files.html").read_text(encoding="utf-8")
            self.assertIn('id="owner-answers"', plan)
            self.assertIn('name="objective:local-enforcement"', plan)
            self.assertIn('id="reviewed-all"', plan)
            self.assertIn("<noscript>", plan)
            self.assertIn('id="acima-console-state"', plan)
            self.assertIn('id="decision-log"', plan)
            # The page reads in workflow order: plan, then the answer controls, then the record.
            self.assertLess(plan.find('id="adoption-plan"'), plan.find('id="owner-answers"'))
            self.assertLess(plan.find('id="owner-answers"'), plan.find('id="decision-log"'))
            self.assertIn('name="path:acima.config.json"', files)
            self.assertIn('id="use-recommended"', files)
            self.assertIn("Select all proposed files", files)
            self.assertIn("Needed for", files)
            self.assertIn("Save answers file", plan)
            self.assertIn("Implement", plan)
            self.assertIn("Answers to paste back", plan)
            self.assertNotIn('checked="checked"', files)
            self.assertIn("<noscript>", files)
            self.assertIn('maxlength="120"', files)
            self.assertIn("Proposed files", files)
            model = json.loads((Path(report["directory"]) / "report-data.json").read_text(encoding="utf-8"))
            self.assertEqual(model["console"]["reportId"], report["reportId"])
            self.assertEqual(model["console"]["mode"], "guided")
            self.assertTrue(model["console"]["objectives"])

    def test_console_script_is_valid_javascript(self) -> None:
        node = shutil.which("node")
        if node is None:
            self.skipTest("node is not installed")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            workflow.start(root, "guided")
            state = workflow.approve(root, map_decisions=map_review(root))
            report = state["artifacts"]["proposalReport"]
            for page in ("plan", "files"):
                html = (Path(report["directory"]) / (page + ".html")).read_text(encoding="utf-8")
                script = re.findall(r"<script>(.*?)</script>", html, re.S)[-1]
                source = Path(directory) / (page + ".js")
                source.write_text(script, encoding="utf-8")
                result = subprocess.run([node, "--check", str(source)],
                                        capture_output=True, text=True, timeout=60)
                self.assertEqual(result.returncode, 0,
                                 "%s console script does not parse: %s" % (page, result.stderr))

    def test_the_one_flow_always_exposes_console_approval_controls(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            state = full_start(root)
            report = state["artifacts"]["proposalReport"]
            plan = (Path(report["directory"]) / "plan.html").read_text(encoding="utf-8")
            self.assertIn('id="owner-answers"', plan)
            self.assertIn('id="decision-log"', plan)
            self.assertLess(plan.find('id="adoption-plan"'), plan.find('id="decision-log"'))
            files = (Path(report["directory"]) / "files.html").read_text(encoding="utf-8")
            self.assertIn('id="scope-paths"', files)

    def test_console_answers_without_digests_are_completed_on_ingest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            workflow.start(root, "guided")
            state = workflow.approve(root, map_decisions=map_review(root))
            objectives, paths = all_objectives_and_paths(root, state)
            answers = [{"kind": "scope-objective", "id": name, "decision": "accept"} for name in objectives]
            answers += [{"kind": "scope-path", "id": path, "decision": "accept"} for path in paths]
            # A report page cannot hash its own bytes: no reportSha256 and no decisionSha256.
            document = decisions_file(root, state, answers=answers, reportSha256=None,
                                      decisionSha256=None, source="html-report", page="plan")
            result = workflow.decisions(root, document)
            self.assertEqual(result["status"], "applied")
            state = workflow._load(root)
            source = state["decisionSources"][0]
            self.assertEqual(source["reportSha256"], state["artifacts"]["proposalReport"]["sha256"])
            self.assertEqual(source["decisionSha256"], state["artifacts"]["proposalReport"]["decisionSha256"])
            self.assertTrue(state["decisionLog"])
            answers = state["consoleState"]["answers"]
            self.assertTrue(answers)
            self.assertTrue(all(entry.get("sourceSha256") for entry in answers),
                            "the page needs to know which file holds each answer it revises")

    def test_page_revision_replaces_only_the_file_it_supersedes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            workflow.start(root, "guided")
            state = workflow.approve(root, map_decisions=map_review(root))
            objectives, _paths = all_objectives_and_paths(root, state)
            answers = [{"kind": "scope-objective", "id": name, "decision": "accept"} for name in objectives]
            first = decisions_file(root, state, reportSha256=None, decisionSha256=None, answers=answers)
            workflow.decisions(root, first)
            first_sha = hashlib.sha256(first.read_bytes()).hexdigest()
            before = {item["id"]: item["disposition"]
                      for item in workflow._read_json(root / workflow.SCOPE_FILE)["objectives"]}
            revised = [{"kind": "scope-objective", "id": objectives[0], "decision": "defer"}]
            revised += [{"kind": "scope-objective", "id": name, "decision": "accept"} for name in objectives[1:]]
            second = decisions_file(root, state, reportSha256=None, decisionSha256=None,
                                    supersedes=first_sha, answers=revised)
            self.assertEqual(workflow.decisions(root, second)["status"], "applied")
            state = workflow._load(root)
            statuses = {source["fileSha256"]: source["status"] for source in state["decisionSources"]}
            self.assertEqual(statuses[first_sha], "superseded")
            scope = workflow._read_json(root / workflow.SCOPE_FILE)
            dispositions = {item["id"]: item["disposition"] for item in scope["objectives"]}
            self.assertEqual(dispositions[objectives[0]], "deferred")
            for name in objectives[1:]:
                self.assertEqual(dispositions[name], before[name], name)

    def test_supersede_does_not_waive_conflicts_from_other_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            workflow.start(root, "guided")
            state = workflow.approve(root, map_decisions=map_review(root))
            objectives, paths = all_objectives_and_paths(root, state)
            plan = decisions_file(root, state, reportSha256=None, decisionSha256=None,
                                  answers=[{"kind": "scope-objective", "id": name, "decision": "accept"}
                                           for name in objectives])
            workflow.decisions(root, plan)
            paths_file = decisions_file(root, state, review=False, reportSha256=None, decisionSha256=None,
                                        answers=[{"kind": "scope-path", "id": path, "decision": "accept"}
                                                 for path in paths])
            workflow.decisions(root, paths_file)
            wrong_target = hashlib.sha256(paths_file.read_bytes()).hexdigest()
            revised = [{"kind": "scope-objective", "id": objectives[0], "decision": "defer"}]
            revised += [{"kind": "scope-objective", "id": name, "decision": "accept"} for name in objectives[1:]]
            changing = decisions_file(root, state, reportSha256=None, decisionSha256=None,
                                      supersedes=wrong_target, answers=revised)
            with self.assertRaisesRegex(workflow.WorkflowError, "supersede"):
                workflow.decisions(root, changing)

    def test_page_files_merge_in_any_order_and_require_the_review_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            workflow.start(root, "guided")
            state = workflow.approve(root, map_decisions=map_review(root))
            objectives, paths = all_objectives_and_paths(root, state)
            path_only = decisions_file(root, state, review=False, reportSha256=None, decisionSha256=None,
                                       answers=[{"kind": "scope-path", "id": path, "decision": "accept"}
                                                for path in paths])
            with self.assertRaisesRegex(workflow.WorkflowError, "report review"):
                workflow.decisions(root, path_only)
            plan_only = decisions_file(root, state, reportSha256=None, decisionSha256=None,
                                       answers=[{"kind": "scope-objective", "id": name, "decision": "accept"}
                                                for name in objectives])
            workflow.decisions(root, plan_only)
            self.assertTrue(workflow._read_json(root / workflow.SCOPE_FILE)["objectives"])
            workflow.decisions(root, path_only)
            scope = workflow._read_json(root / workflow.SCOPE_FILE)
            self.assertEqual(sorted(scope["approvedPaths"]), sorted(paths))
            self.assertFalse(scope["authorization"]["explicit"])

    def test_progress_log_and_event_stream_record_the_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            workflow.start(root, "guided")
            state = workflow.approve(root, map_decisions=map_review(root))
            self.assertTrue(state["progressLog"])
            self.assertTrue(any(entry["stage"] == "module_map" for entry in state["progressLog"]))
            self.assertEqual(state["events"], workflow.EVENTS_FILE)
            events = (root / workflow.EVENTS_FILE).read_text(encoding="utf-8").splitlines()
            names = {json.loads(line)["event"] for line in events}
            self.assertIn("report.generated", names)
            self.assertIn("stage.changed", names)

    def test_since_review_reports_a_new_generation_and_marks_answers_stale(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            workflow.start(root, "guided")
            state = workflow.approve(root, map_decisions=map_review(root))
            workflow.decisions(root, decisions_file(root, state))
            state = workflow.regenerate(root, reason="the report directory was removed")
            self.assertEqual(state["sinceReview"]["status"], "changed")
            self.assertIn("a newer report generation", state["sinceReview"]["changed"])
            self.assertEqual(state["decisionSources"][0]["status"], "stale")

    def test_workflow_history_renders_missing_evidence_as_missing(self) -> None:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "report_renderer", ROOT / "skills/acima-adoption/scripts/render_report.py")
        renderer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(renderer)
        html = renderer.workflow_history({"adoptionWorkflow": {
            "evidenceIntegrity": {"status": "missing", "checked": 4,
                                  "missing": [{"name": "enforcement", "path": "acima/evidence/enforcement.json"}]},
            "decisionLog": [{"kind": "scope-objective", "id": "ci-enforcement", "decision": "accept",
                             "status": "in force", "reviewer": "Repository owner", "decidedOn": "2026-11-13"}],
            "progressLog": [{"stage": "module_map", "from": "awaiting_approval", "to": "complete",
                             "at": "2026-11-13T10:00:00+00:00", "detail": "approved"}],
        }})
        self.assertIn("Recorded but missing", html)
        self.assertIn("acima/evidence/enforcement.json", html)
        self.assertIn("Current answers", html)
        self.assertIn("Stage changes", html)

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

    def test_existing_ci_workflow_is_not_overwritten_by_adoption(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            existing = "name: existing\non: pull_request\njobs:\n  test:\n    runs-on: ubuntu-latest\n"
            write(root, ".github/workflows/existing.yml", existing)
            full_start(root)
            ci = json.loads((root / "acima/evidence/ci-integration.json").read_text(encoding="utf-8"))
            self.assertIn("acima/tooling/python/acima_arch.py", ci["command"])
            self.assertTrue((root / ".github/workflows/acima.yml").is_file())
            self.assertEqual((root / ".github/workflows/existing.yml").read_text(encoding="utf-8"),
                             existing)
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
            self.assertIn("How the product is divided today", proposal_page)
            self.assertIn("The product already has a written map.", proposal_page)
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
            self.assertFalse((root / "acima.config.json").exists())
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
            self.assertEqual(state["stages"]["ci"]["status"], "awaiting_approval")
            self.assertFalse((root / "acima/handoff/adoption-handoff.md").exists())
            workflow.ci(root, plan_only=True)
            state = workflow.ci(
                root, approve=True,
                plan_sha256=workflow._sha(root / workflow.adoption_ci.PLAN_FILE),
                reviewed_by="Repository owner",
            )
            self.assertEqual(state["stages"]["remediation"]["status"], "awaiting_approval")
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
            self.assertEqual(full.returncode, 2)
            self.assertIn("automated adoption was removed", full.stderr)
            self.assertFalse((root / "acima.config.json").exists())
            self.assertFalse((root / "acima/tooling/python/acima_arch.py").exists())

    def test_remediation_none_and_selected_rounds_are_repeatable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            full_start(root)
            state = workflow.remediate(root, "none", approved_by="Repository owner")
            self.assertEqual(state["stages"]["remediation"]["status"], "deferred")
            self.assertEqual(state["remediationRounds"][0]["choice"], "none")
            state = workflow.remediate(root, "none", approved_by="Repository owner")
            self.assertEqual(len(state["remediationRounds"]), 2)
            self.assertEqual(state["remediation"]["loop"], "available")
            state = workflow.remediate(root, "none", plan_only=True)
            self.assertEqual(state["remediation"]["planConsumed"], False)
            state = remediate(root, "all", approved_by="Repository owner", confirm=True)
            self.assertEqual(len(state["remediationRounds"]), 3)
            state = workflow.remediate(root, "none", approved_by="Repository owner")
            self.assertEqual(len(state["remediationRounds"]), 4)
            self.assertEqual(state["remediationRounds"][-1]["round"], 4)

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
            "assess", "review_and_authorize", "implement", "verify_and_hand_off"])
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
            module_map="complete", adoption_proposal="deferred"), "review_and_authorize")

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
