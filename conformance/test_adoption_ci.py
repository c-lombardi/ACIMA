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

    def test_reentry_refreshes_the_report_before_planning_ci_again(self) -> None:
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
            first = state["artifacts"]["proposalReport"]["reportId"]
            source_before = {path.relative_to(root).as_posix(): path.read_bytes()
                             for path in (root / "src").rglob("*") if path.is_file()}
            workflow.ci(root, decline=True, reviewed_by="Repository owner",
                        reason="no merge policy yet")
            state = workflow.ci(root, plan_only=True, refresh=True,
                                reviewed_by="Repository owner")
            second = state["artifacts"]["proposalReport"]["reportId"]
            self.assertNotEqual(first, second)
            self.assertTrue((root / ci.PLAN_FILE).is_file())
            self.assertEqual(source_before,
                             {path.relative_to(root).as_posix(): path.read_bytes()
                              for path in (root / "src").rglob("*") if path.is_file()})

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
