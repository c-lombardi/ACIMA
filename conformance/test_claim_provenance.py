"""A claim is current only when it describes this repository, commit and configuration.

The fixtures keep the rule result valid while changing one provenance field at a time. That
separates rule coverage from evidence freshness: a historical FULL CONFORMANCE result stays
readable, but it cannot make the current status complete.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("acima_provenance", ROOT / "tools/acima.py")
acima = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules["acima_provenance"] = acima
SPEC.loader.exec_module(acima)

CATALOG = json.loads((ROOT / "tools/acima-spec/rules.json").read_text(encoding="utf-8"))
CATALOG_SHA = hashlib.sha256((ROOT / "tools/acima-spec/rules.json").read_bytes()).hexdigest()
HEAD = "a" * 40
OLD = "b" * 40
REMOTE = "https://github.com/owner/repo.git"


def write(root: Path, relative: str, content: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def config(root: Path, level: str = "L1") -> dict:
    payload = {
        "standard": CATALOG["version"], "language": "python", "level": level, "mode": "base",
        "units": [{"id": "u0", "module": "u0", "role": "implementation",
                   "paths": ["src/u0"]}],
    }
    write(root, "acima.config.json", json.dumps(payload))
    write(root, "src/u0/app.py", "VALUE = 1\n")
    return payload


def execution(level: str) -> dict:
    required = {rule["id"] for rule in CATALOG["rules"]
                if not rule.get("level") or int(rule["level"][1]) <= int(level[1])}
    result = {}
    for rule in CATALOG["rules"]:
        if rule["id"] not in required:
            continue
        if rule.get("automation") == "manual":
            result[rule["id"]] = {"executed": False, "reason": "manual review required"}
        else:
            result[rule["id"]] = {"executed": True}
    return result


def run_payload(root: Path, level: str = "L1", **overrides) -> dict:
    payload = {
        "standard": CATALOG["version"],
        "level": level,
        "sourceFiles": 1,
        "execution": execution(level),
        "findings": [],
        "repository": "owner/repo",
        "commit": HEAD,
        "catalogVersion": CATALOG["version"],
        "catalogSha256": CATALOG_SHA,
        "configurationSha256": hashlib.sha256(
            (root / "acima.config.json").read_bytes()).hexdigest(),
        "enforcerVersion": acima.ENFORCER_VERSION,
        "sourceInventory": acima._source_inventory(root),
        "sourceInventorySha256": acima._source_inventory_digest(
            acima._source_inventory(root)),
        "provenanceVersion": acima.PROVENANCE_VERSION,
    }
    payload.update(overrides)
    return payload


def baseline(root: Path, level: str = "L1", name: str = "baseline-2026-01-01.json",
             **overrides) -> Path:
    payload = run_payload(root, level, **overrides)
    return write(root, f"acima/evidence/{name}", json.dumps(payload))


def manual_evidence(root: Path, rules: tuple[str, ...] = ("ACIMA-C003",),
                    *, expires: str | None = None) -> None:
    artifact = write(root, "docs/reviews/C003.md", "reviewed\n")
    expiry = expires or (date.today() + timedelta(days=30)).isoformat()
    payload = {
        "standard": CATALOG["version"],
        "evidence": [{
            "rule": rule, "scope": "repository", "owner": "team",
            "reviewer": "architecture-review", "method": "review",
            "artifact": artifact.relative_to(root).as_posix(),
            "reviewedOn": (date.today() - timedelta(days=1)).isoformat(),
            "expires": expiry, "result": "pass",
        } for rule in rules],
    }
    write(root, "acima/evidence/manual-evidence.json", json.dumps(payload))


def status(root: Path) -> dict:
    with mock.patch.object(acima, "_git_head", return_value=HEAD), \
            mock.patch.object(acima, "_git_remote", return_value=REMOTE), \
            mock.patch.object(acima, "_git_dirty", return_value=[]):
        return acima.status_project(root)


def step(report: dict, name: str) -> dict:
    return {entry["name"]: entry for entry in report["steps"]}[name]


class ClaimProvenanceTests(unittest.TestCase):
    def test_current_commit_with_matching_provenance_is_current(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config(root)
            manual_evidence(root, ("ACIMA-L004",))
            baseline(root)
            claim = step(status(root), "claim")
            self.assertEqual(claim["state"], "COMPLETE", claim)
            self.assertEqual(claim["claimState"], "current", claim)
            self.assertEqual(claim["claim"]["claim"], "FULL CONFORMANCE")
            self.assertEqual(claim["provenance"]["state"], "current")

    def test_older_commit_is_historical_not_current(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config(root)
            manual_evidence(root, ("ACIMA-L004",))
            baseline(root, commit=OLD)
            report = status(root)
            claim = step(report, "claim")
            self.assertEqual(claim["claim"]["claim"], "FULL CONFORMANCE")
            self.assertEqual(claim["claimState"], "historical", claim)
            self.assertNotEqual(claim["state"], "COMPLETE")
            self.assertIn("historical", claim["evidence"])
            self.assertEqual(report["evidence"]["runArtefacts"], ["acima/evidence/baseline-2026-01-01.json"])

    def test_source_change_after_measurement_is_stale(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config(root)
            manual_evidence(root, ("ACIMA-L004",))
            baseline(root)
            write(root, "src/u0/other.py", "OTHER = 2\n")
            claim = step(status(root), "claim")
            self.assertEqual(claim["claimState"], "stale", claim)
            self.assertNotEqual(claim["state"], "COMPLETE")
            self.assertIn("source inventory", claim["evidence"])

    def test_different_repository_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config(root)
            baseline(root, repository="other/repo")
            claim = step(status(root), "claim")
            self.assertEqual(claim["claimState"], "stale", claim)
            self.assertNotEqual(claim["state"], "COMPLETE")
            self.assertIn("repository", claim["evidence"])

    def test_different_catalog_requires_recalibration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config(root)
            baseline(root, catalogSha256="0" * 64)
            claim = step(status(root), "claim")
            self.assertEqual(claim["claimState"], "stale", claim)
            self.assertIn("catalog", claim["evidence"])

    def test_different_standard_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config(root)
            baseline(root, standard="0.0.0")
            claim = step(status(root), "claim")
            self.assertEqual(claim["claimState"], "stale", claim)
            self.assertIn("standard", claim["evidence"])

    def test_different_configuration_requires_fresh_measurement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config(root)
            manual_evidence(root, ("ACIMA-L004",))
            baseline(root)
            changed = config(root)
            changed["units"].append({"id": "u1", "module": "u1", "role": "implementation",
                                     "paths": ["src/u1"]})
            write(root, "acima.config.json", json.dumps(changed))
            claim = step(status(root), "claim")
            self.assertEqual(claim["claimState"], "stale", claim)
            self.assertIn("configuration", claim["evidence"])

    def test_missing_catalog_hash_is_insufficient_not_stale(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config(root)
            manual_evidence(root, ("ACIMA-L004",))
            payload = run_payload(root)
            payload.pop("catalogSha256")
            write(root, "acima/evidence/baseline-2026-01-01.json", json.dumps(payload))
            claim = step(status(root), "claim")
            self.assertEqual(claim["claimState"], "incomplete", claim)
            self.assertNotEqual(claim["state"], "COMPLETE")
            self.assertIn("catalog", claim["evidence"])

    def test_missing_commit_cannot_establish_currentness(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config(root)
            manual_evidence(root, ("ACIMA-L004",))
            payload = run_payload(root)
            payload.pop("commit")
            write(root, "acima/evidence/baseline-2026-01-01.json", json.dumps(payload))
            claim = step(status(root), "claim")
            self.assertEqual(claim["claimState"], "incomplete", claim)
            self.assertNotEqual(claim["state"], "COMPLETE")
            self.assertIn("commit", claim["evidence"])

    def test_missing_manual_evidence_is_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config(root, "L2")
            baseline(root, "L2")
            claim = step(status(root), "claim")
            self.assertEqual(claim["claimState"], "incomplete", claim)
            self.assertNotEqual(claim["state"], "COMPLETE")
            self.assertIn("PARTIAL ASSESSMENT", claim["evidence"])

    def test_expired_manual_evidence_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config(root, "L2")
            manual_evidence(root, expires="2020-01-01")
            baseline(root, "L2")
            claim = step(status(root), "claim")
            self.assertEqual(claim["state"], "BLOCKED", claim)
            self.assertEqual(claim["claimState"], "invalid", claim)
            self.assertNotIn("FULL CONFORMANCE", acima.status_text(status(root)))

    def test_zero_findings_without_full_rule_coverage_is_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config(root, "L2")
            baseline(root, "L2", findings=[])
            claim = step(status(root), "claim")
            self.assertEqual(claim["claimState"], "incomplete", claim)
            self.assertNotEqual(claim["state"], "COMPLETE")
            self.assertEqual(claim["claim"]["claim"], "PARTIAL ASSESSMENT")

    def test_uncommitted_source_change_cannot_represent_the_working_tree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config(root)
            manual_evidence(root, ("ACIMA-L004",))
            baseline(root)
            with mock.patch.object(acima, "_git_head", return_value=HEAD), \
                    mock.patch.object(acima, "_git_remote", return_value=REMOTE), \
                    mock.patch.object(acima, "_git_dirty",
                                      return_value=["src/u0/app.py"]):
                claim = step(acima.status_project(root), "claim")
            self.assertEqual(claim["claimState"], "stale", claim)
            self.assertNotEqual(claim["state"], "COMPLETE")
            self.assertIn("working tree", claim["evidence"])

    def test_changed_baseline_requires_fresh_measurement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config(root)
            baseline_path = write(root, "acima/evidence/baseline.json", json.dumps(
                {"standard": CATALOG["version"], "level": "L1", "sourceFiles": 1,
                 "generatedOn": "2026-01-01", "fingerprints": []}))
            payload = run_payload(
                root, baselineSha256=hashlib.sha256(baseline_path.read_bytes()).hexdigest())
            baseline(root, findings=[])
            write(root, "acima/evidence/gate-current.json", json.dumps(payload))
            baseline_path.write_text(json.dumps(
                {"standard": CATALOG["version"], "level": "L1", "sourceFiles": 1,
                 "generatedOn": "2026-01-01", "fingerprints": ["sha256:changed"]}),
                encoding="utf-8")
            claim = step(status(root), "claim")
            self.assertEqual(claim["claimState"], "stale", claim)
            self.assertNotEqual(claim["state"], "COMPLETE")
            self.assertIn("baseline", claim["evidence"])

    def test_current_partial_run_supersedes_an_older_full_claim(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config(root)
            manual_evidence(root, ("ACIMA-L004",))
            old = baseline(root, commit=OLD)
            payload = run_payload(root, findings=[{
                "rule": "ACIMA-D001", "severity": "error", "message": "bad import",
                "path": "src/u0/app.py", "line": 1, "evidence": "",
                "fingerprint": "sha256:" + "0" * 64, "status": "new"}])
            recent = write(root, "acima/evidence/gate-current.json", json.dumps(payload))
            os.utime(old, (1, 1))
            os.utime(recent, (2, 2))
            claim = step(status(root), "claim")
            self.assertEqual(claim["claim"]["claim"], "PARTIAL ASSESSMENT")
            self.assertEqual(claim["claimState"], "incomplete", claim)
            self.assertNotEqual(claim["state"], "COMPLETE")
            self.assertNotIn("historical FULL CONFORMANCE", claim["evidence"])

    def test_claim_artifact_stays_readable_after_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config(root)
            manual_evidence(root, ("ACIMA-L004",))
            path = baseline(root, commit=OLD)
            self.assertTrue(path.is_file())
            with mock.patch.object(acima, "_git_head", return_value=HEAD), \
                    mock.patch.object(acima, "_git_remote", return_value=REMOTE), \
                    mock.patch.object(acima, "_git_dirty", return_value=[]):
                report = acima.claim_for(root, json.loads(path.read_text(encoding="utf-8")),
                                         config(root))
            self.assertEqual(report["claim"], "FULL CONFORMANCE")
            self.assertEqual(report["currentness"], "historical")
            self.assertFalse(report["current"])


if __name__ == "__main__":
    unittest.main()
