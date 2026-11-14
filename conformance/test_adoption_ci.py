"""CI socket and shrink-only baseline regressions."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "conformance"))
import adoption_ci as ci  # noqa: E402
import adoption_workflow as workflow  # noqa: E402
from test_adoption_workflow import fixture, map_review, scope  # noqa: E402


def scope_without_ci(root: Path) -> Path:
    path = scope(root)
    document = json.loads(path.read_text(encoding="utf-8"))
    for objective in document["objectives"]:
        if objective["id"] == "ci-enforcement":
            objective["disposition"] = "deferred"
    document["approvedPaths"] = workflow._implementation_paths(root, document)
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def finding(fp: str, *, line: int = 1, path: str = "src/a.py") -> dict:
    return {"rule": "ACIMA-D001", "severity": "error", "message": "uses an implementation",
            "path": path, "line": line, "fingerprint": "sha256:" + fp * 64}


class BaselineTests(unittest.TestCase):
    def test_fingerprint_ignores_the_line_and_uses_the_supplied_value(self) -> None:
        first = finding("a", line=1)
        second = finding("a", line=99)
        self.assertEqual(ci.fingerprint(first), ci.fingerprint(second))
        self.assertEqual(ci.fingerprint(first), "sha256:" + "a" * 64)

    def test_first_run_records_every_finding_and_second_run_refuses_growth(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = ci.record_initial(root, [finding("a"), finding("b")])
            self.assertEqual(len(document["entries"]), 2)
            with self.assertRaisesRegex(ci.CiError, "already exists"):
                ci.record_initial(root, [finding("a"), finding("b"), finding("c")])

    def test_existing_findings_warn_and_new_findings_error(self) -> None:
        baseline = ci.build_baseline([finding("a")])
        result = ci.evaluate([finding("a", line=8), finding("b")], baseline)
        self.assertEqual(result["status"], "new-findings")
        self.assertEqual(result["warningCount"], 1)
        self.assertEqual(result["errorCount"], 1)
        self.assertEqual(len(result["baseline"]["entries"]), 1)

    def test_resolved_findings_are_pruned_without_growth(self) -> None:
        baseline = ci.build_baseline([finding("a"), finding("b")])
        result = ci.evaluate([finding("a")], baseline)
        self.assertEqual(result["status"], "clean")
        self.assertEqual(result["resolved"], ["sha256:" + "b" * 64])
        self.assertEqual([item["fingerprint"] for item in result["baseline"]["entries"]],
                         ["sha256:" + "a" * 64])

    def test_reviewed_growth_requires_owner_reason_and_exact_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ci.record_initial(root, [finding("a")])
            path = root / ci.BASELINE_FILE
            with self.assertRaisesRegex(ci.CiError, "owner, reason"):
                ci.reviewed_growth(root, [finding("b")], owner="", reason="", reviewed_on="2026-11-13",
                                   baseline_sha256=ci._sha(path))
            with self.assertRaisesRegex(ci.CiError, "exact current baseline"):
                ci.reviewed_growth(root, [finding("b")], owner="Owner", reason="accepted debt",
                                   reviewed_on="2026-11-13", baseline_sha256="0" * 64)
            updated = ci.reviewed_growth(root, [finding("b")], owner="Owner",
                                         reason="accepted debt", reviewed_on="2026-11-13",
                                         baseline_sha256=ci._sha(path))
            self.assertEqual(len(updated["entries"]), 2)
            self.assertEqual(updated["reviewedUpdates"][0]["added"], 1)


class SocketTests(unittest.TestCase):
    def test_plan_writes_no_workflow_and_approval_requires_the_exact_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            workflow_text = "name: existing\non: pull_request\njobs: {}\n"
            target = root / ".github/workflows/existing.yml"
            target.parent.mkdir(parents=True)
            target.write_text(workflow_text, encoding="utf-8")
            workflow.start(root, "guided")
            state = workflow.approve(root, map_decisions=map_review(root))
            state = workflow.approve(
                root, scope=scope(root),
                reviewed_report_sha256=state["artifacts"]["proposalReport"]["sha256"],
                reviewed_by="Repository owner",
            )
            self.assertEqual(state["stages"]["ci"]["status"], "awaiting_approval")
            self.assertFalse((root / ci.WORKFLOW_FILE).exists())
            state = workflow.ci(root, plan_only=True)
            self.assertFalse((root / ci.WORKFLOW_FILE).exists())
            with self.assertRaisesRegex(ci.CiError, "exact SHA-256"):
                workflow.ci(root, approve=True, plan_sha256="0" * 64,
                            reviewed_by="Repository owner")
            state = workflow.ci(
                root, approve=True,
                plan_sha256=workflow._sha(root / ci.PLAN_FILE),
                reviewed_by="Repository owner",
            )
            self.assertEqual(state["stages"]["ci"]["status"], "complete")
            self.assertTrue((root / ci.WORKFLOW_FILE).is_file())
            self.assertEqual(target.read_text(encoding="utf-8"), workflow_text)
            self.assertTrue((root / ci.BASELINE_FILE).is_file())
            # The approved workflow is a target write; the revision must be re-pinned so the
            # separately approved remediation round is not blocked by the CI file itself.
            self.assertEqual(state["repository"]["revision"], workflow._revision(root))

    def test_ci_approval_refuses_a_scope_that_did_not_select_ci(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            workflow.start(root, "guided")
            workflow.approve(root, map_decisions=map_review(root))
            state = workflow._load(root)
            workflow.approve(
                root, scope=scope_without_ci(root),
                reviewed_report_sha256=state["artifacts"]["proposalReport"]["sha256"],
                reviewed_by="Repository owner",
            )
            workflow.ci(root, plan_only=True)
            with self.assertRaisesRegex(workflow.WorkflowError, "CI enforcement was not selected"):
                workflow.ci(
                    root, approve=True,
                    plan_sha256=workflow._sha(root / ci.PLAN_FILE),
                    reviewed_by="Repository owner",
                )
            self.assertFalse((root / ci.WORKFLOW_FILE).exists())

    def test_reentry_requires_fresh_scope_before_ci_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            workflow.start(root, "guided")
            state = workflow.approve(root, map_decisions=map_review(root))
            workflow.approve(
                root, scope=scope(root),
                reviewed_report_sha256=state["artifacts"]["proposalReport"]["sha256"],
                reviewed_by="Repository owner",
            )
            workflow.ci(root, plan_only=True)
            plan_sha256 = workflow._sha(root / ci.PLAN_FILE)
            workflow.regenerate(root, reason="repository changed after CI planning", refresh_map=True)
            with self.assertRaisesRegex(
                    workflow.WorkflowError, "reviewed|matching persisted implementation-approval"):
                workflow.ci(root, approve=True, plan_sha256=plan_sha256,
                            reviewed_by="Repository owner")
            self.assertFalse((root / ci.WORKFLOW_FILE).exists())

    def test_reentry_refreshes_evidence_map_and_config_before_planning_ci(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            workflow.start(root, "guided")
            state = workflow.approve(root, map_decisions=map_review(root))
            state = workflow.approve(
                root, scope=scope(root),
                reviewed_report_sha256=state["artifacts"]["proposalReport"]["sha256"],
                reviewed_by="Repository owner",
            )
            first_report = state["artifacts"]["proposalReport"]["reportId"]
            proposal_path = root / workflow.PROPOSAL_JSON
            config_path = root / workflow.PROPOSED_CONFIG
            preflight_path = root / workflow.PREFLIGHT_FILE
            approved_proposal_id = json.loads(
                (root / workflow.APPROVAL_FILE).read_text(encoding="utf-8"))["proposalId"]

            # Corrupt every refreshable input. A report-only refresh would leave these untouched.
            proposal_path.write_text(json.dumps({
                "proposalId": "sha256:" + "0" * 64,
                "modules": [{"id": "stale", "name": "Stale"}],
            }), encoding="utf-8")
            config_path.write_text(json.dumps({
                "units": [{"id": "stale", "module": "stale"}],
                "_moduleMapApproval": {"proposalId": "sha256:" + "0" * 64},
            }), encoding="utf-8")
            preflight_path.write_text(json.dumps({"blockers": ["stale preflight"]}),
                                      encoding="utf-8")

            def source_snapshot() -> dict[str, bytes]:
                return {path.relative_to(root).as_posix(): path.read_bytes()
                        for path in root.rglob("*")
                        if path.is_file()
                        and not path.relative_to(root).as_posix().startswith("acima/")}

            source_before = source_snapshot()
            workflow.ci(root, decline=True, reviewed_by="Repository owner",
                        reason="no merge policy yet")
            state = workflow.ci(root, plan_only=True, refresh=True,
                                reviewed_by="Repository owner")
            second_report = state["artifacts"]["proposalReport"]["reportId"]
            self.assertNotEqual(first_report, second_report)
            self.assertTrue((root / ci.PLAN_FILE).is_file())

            proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
            self.assertRegex(proposal["proposalId"], r"^sha256:[0-9a-f]{64}$")
            self.assertNotEqual(proposal["proposalId"], "sha256:" + "0" * 64)
            self.assertNotIn("stale", [module["id"] for module in proposal["modules"]])
            self.assertTrue(any("src/orders" in json.dumps(module)
                                for module in proposal["modules"]))
            config = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertNotIn("stale", json.dumps(config).lower())
            self.assertTrue(config.get("units"))
            self.assertEqual(config["_moduleMapApproval"]["proposalId"],
                             approved_proposal_id)
            preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
            self.assertNotIn("stale", json.dumps(preflight).lower())
            self.assertEqual(state["stages"]["assessment"]["status"], "complete")
            self.assertEqual(source_before, source_snapshot())

    def test_decline_writes_no_workflow_and_records_the_decision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            workflow.start(root, "guided")
            workflow.approve(root, map_decisions=map_review(root))
            state = workflow._load(root)
            state["stages"]["ci"] = {"name": "ci", "label": "CI", "status": "awaiting_approval"}
            workflow._save(root, state)
            state = workflow.ci(root, decline=True, reviewed_by="Repository owner",
                                reason="no merge policy yet")
            self.assertEqual(state["stages"]["ci"]["status"], "declined")
            self.assertFalse((root / ci.WORKFLOW_FILE).exists())
            record = json.loads((root / ci.CI_FILE).read_text(encoding="utf-8"))
            self.assertEqual(record["status"], "declined")


if __name__ == "__main__":
    unittest.main()
