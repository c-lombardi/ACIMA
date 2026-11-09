"""Regression tests for the executable conformance claim model."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "conformance"))
import acima_claim as claim  # noqa: E402

CATALOG = claim.load_catalog(ROOT)
MANUAL = {
    "ACIMA-A002", "ACIMA-A004", "ACIMA-A010", "ACIMA-A011", "ACIMA-A012", "ACIMA-A013",
    "ACIMA-A014", "ACIMA-A015",
    "ACIMA-C003", "ACIMA-C007", "ACIMA-C008", "ACIMA-G004", "ACIMA-L004", "ACIMA-N003",
}


def payload(level: str = "L3", unexecuted: set[str] | None = None,
            findings: list[dict] | None = None) -> dict:
    unexecuted = unexecuted or set()
    rules = claim.required_rules(CATALOG, level)
    execution = {}
    for rule in rules:
        if rule["id"] in unexecuted:
            execution[rule["id"]] = {"executed": False,
                                     "reason": "not decided by the portable enforcer"}
        else:
            execution[rule["id"]] = {"executed": True}
    return {
        "standard": "1.0.0-draft.1",
        "level": level,
        "sourceFiles": 12,
        "execution": execution,
        "findings": findings or [],
    }


def evidence_document(rules: set[str], root: Path, *,
                      scope: str = "repository",
                      expires: str | None = None) -> dict:
    reviewed = date.today().isoformat()
    expiry = expires or (date.today() + timedelta(days=180)).isoformat()
    entries = []
    for rule in sorted(rules):
        artifact = root / "reviews" / f"{rule}.md"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text("reviewed\n", encoding="utf-8")
        entries.append({
            "rule": rule,
            "scope": scope,
            "owner": "team-contracts",
            "reviewer": "architecture-review",
            "method": "review",
            "artifact": artifact.relative_to(root).as_posix(),
            "reviewedOn": reviewed,
            "expires": expiry,
            "result": "pass",
        })
    return {"standard": "1.0.0-draft.1", "evidence": entries}


class ClaimModelTests(unittest.TestCase):
    def test_required_rule_counts_and_manual_partition(self) -> None:
        self.assertEqual(len(claim.required_rules(CATALOG, "L1")), 27)
        self.assertEqual(len(claim.required_rules(CATALOG, "L2")), 37)
        self.assertEqual(len(claim.required_rules(CATALOG, "L3")), 55)
        self.assertEqual(
            {rule["id"] for rule in CATALOG["rules"] if rule["automation"] == "manual"},
            MANUAL,
        )
        self.assertEqual(sum(1 for rule in CATALOG["rules"]
                             if rule["automation"] == "automated"), 41)
        self.assertEqual(
            {rule["id"] for rule in claim.required_rules(CATALOG, "L2")
             if rule["automation"] == "manual"},
            {"ACIMA-C003", "ACIMA-C007", "ACIMA-C008", "ACIMA-G004", "ACIMA-L004"},
        )

    def test_complete_automated_run_with_valid_manual_evidence_is_full(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = evidence_document(MANUAL, root)
            result = claim.assess(payload("L3", MANUAL), CATALOG,
                                  evidence=document["evidence"], root=root)
            self.assertEqual(result["claim"], claim.FULL)
            self.assertTrue(result["eligible"])
            self.assertEqual(result["missing"], [])
            self.assertEqual(result["executed"], 41)
            self.assertEqual(result["manualEvidence"], 14)

    def test_manual_rule_reported_as_executed_cannot_supplant_evidence(self) -> None:
        # A clean automated run cannot establish full conformance by asserting that
        # catalog-manual rules executed. An unsupported check must not pass silently.
        result = claim.assess(payload("L3"), CATALOG)
        self.assertEqual(result["claim"], claim.PARTIAL)
        self.assertFalse(result["eligible"])
        self.assertEqual(set(result["unsupportedExecution"]), MANUAL)
        self.assertEqual(set(result["missing"]), MANUAL)
        self.assertTrue(any("cannot substitute" in reason for reason in result["reasons"]))

    def test_missing_manual_evidence_is_partial_and_named(self) -> None:
        result = claim.assess(payload("L3", MANUAL), CATALOG)
        self.assertEqual(result["claim"], claim.PARTIAL)
        self.assertFalse(result["eligible"])
        self.assertEqual(set(result["missing"]), MANUAL)
        self.assertEqual(set(result["missingManual"]), MANUAL)
        self.assertEqual(result["missingAutomated"], [])
        self.assertTrue(result["reasons"])

    def test_valid_repository_scoped_evidence_makes_full(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = evidence_document(MANUAL, root)
            result = claim.assess(payload("L3", MANUAL), CATALOG,
                                  evidence=document["evidence"], root=root)
            self.assertEqual(result["claim"], claim.FULL)
            self.assertEqual(result["manualEvidence"], 14)

    def test_expired_evidence_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = evidence_document(MANUAL, root, expires="2020-01-01")
            result = claim.assess(payload("L3", MANUAL), CATALOG,
                                  evidence=document["evidence"], root=root)
            self.assertEqual(result["claim"], claim.PARTIAL)
            self.assertEqual(set(result["missing"]), MANUAL)
            self.assertTrue(any("expired" in error
                                for entry in result["invalidEvidence"]
                                for error in entry["errors"]))

    def test_c008_is_required_at_l2(self) -> None:
        l2_manual = {"ACIMA-C003", "ACIMA-C007", "ACIMA-C008", "ACIMA-L004", "ACIMA-G004"}
        result = claim.assess(payload("L2", l2_manual), CATALOG)
        self.assertEqual(result["claim"], claim.PARTIAL)
        self.assertIn("ACIMA-C008", result["missing"])

    def test_unit_scoped_evidence_cannot_certify_the_repository(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = evidence_document(MANUAL, root, scope="unit:catalog")
            result = claim.assess(payload("L3", MANUAL), CATALOG,
                                  evidence=document["evidence"], root=root)
            self.assertEqual(result["claim"], claim.PARTIAL)
            self.assertTrue(any("repository-scoped" in error
                                for entry in result["invalidEvidence"]
                                for error in entry["errors"]))

    def test_unwaived_error_blocks_full_even_with_all_rules_executed(self) -> None:
        finding = {"rule": "ACIMA-D001", "severity": "error", "message": "bad",
                   "path": "src/a.py", "line": 1}
        result = claim.assess(payload("L3", findings=[finding]), CATALOG)
        self.assertEqual(result["claim"], claim.PARTIAL)
        self.assertEqual(result["blockingFindings"], 1)

    def test_incomplete_execution_map_cannot_establish_full_conformance(self) -> None:
        document = payload("L2", {"ACIMA-L004"})
        del document["execution"]["ACIMA-C003"]
        with self.assertRaises(claim.ClaimError):
            claim.assess(document, CATALOG)

    def test_level_mismatch_is_invalid(self) -> None:
        with self.assertRaises(claim.ClaimError):
            claim.assess(payload("L2"), CATALOG, level="L3")


class ClaimCliTests(unittest.TestCase):
    def _run(self, report: Path, evidence: Path | None, require: str,
             root: Path | None = None) -> subprocess.CompletedProcess:
        command = [sys.executable, str(ROOT / "tools/acima.py"), "claim",
                   "--root", str(root or ROOT), "--report", str(report),
                   "--require", require, "--format", "json"]
        if evidence is not None:
            command += ["--evidence", str(evidence)]
        return subprocess.run(command, cwd=ROOT, capture_output=True, text=True)

    def test_full_claim_requires_evidence_and_cli_reports_partial(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / "acima.json"
            report.write_text(json.dumps(payload("L3", MANUAL)), encoding="utf-8")
            result = self._run(report, None, "full")
            self.assertEqual(result.returncode, 1, result.stderr)
            computed = json.loads(result.stdout)
            self.assertEqual(computed["claim"], claim.PARTIAL)
            self.assertEqual(set(computed["missing"]), MANUAL)

    def test_full_claim_passes_with_accepted_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / "acima.json"
            report.write_text(json.dumps(payload("L3", MANUAL)), encoding="utf-8")
            document = evidence_document(MANUAL, root)
            evidence = root / ".acima" / "manual-evidence.json"
            evidence.parent.mkdir(parents=True)
            evidence.write_text(json.dumps(document), encoding="utf-8")
            result = self._run(report, evidence, "full", root=root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            computed = json.loads(result.stdout)
            self.assertEqual(computed["claim"], claim.FULL)

    def test_malformed_report_exits_two(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "broken.json"
            report.write_text("{not json", encoding="utf-8")
            result = self._run(report, None, "partial")
            self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
