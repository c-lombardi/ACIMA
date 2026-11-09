#!/usr/bin/env python3
"""Regression proof for the adoption summary's presentation rules.

The renderer must group by rule/cause, keep rule identifiers as secondary labels, separate
detector artefacts from defects, and never promote a passing baseline to conformance.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/acima-adoption/scripts/summarize.py"
CATALOG = ROOT / "tools/acima-spec/rules.json"


def execution_map() -> dict:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    return {rule["id"]: {"executed": True} for rule in catalog["rules"]}


def run(tmp: Path, report: dict, claim: dict | None = None,
        initial: dict | None = None) -> dict:
    root = tmp / "target"
    (root / ".acima").mkdir(parents=True, exist_ok=True)
    (root / "acima.config.json").write_text(json.dumps({
        "standard": "1.0.0-draft.1", "level": "L1", "language": "dotnet",
        "units": [{"id": "orders", "module": "orders", "role": "implementation",
                   "paths": ["src/Orders"]},
                  {"id": "billing", "module": "billing", "role": "implementation",
                   "paths": ["src/Billing"]}],
    }), encoding="utf-8")
    (root / ".acima/baseline.json").write_text(json.dumps({
        "standard": "1.0.0-draft.1", "level": "L1", "sourceFiles": 2,
        "generatedOn": "2026-11-09",
        "fingerprints": [f["fingerprint"] for f in report.get("findings", [])],
        "findingCount": len(report.get("findings", [])),
    }), encoding="utf-8")
    (root / ".acima/waivers.json").write_text(json.dumps({
        "standard": "1.0.0-draft.1",
        "waivers": [{"rule": "ACIMA-D001", "scope": "unit:orders",
                     "fingerprint": "sha256:waived1", "owner": "owner",
                     "reason": "baseline", "expires": "2099-01-01",
                     "reviewedOn": "2026-11-09"}],
    }), encoding="utf-8")
    (root / ".acima/triage.json").write_text(json.dumps({
        "triage": [{"rule": "ACIMA-D009", "classification": "detector-artifact",
                    "owner": "owner", "reason": "bare identifier match"}],
    }), encoding="utf-8")
    (root / "docs/acima").mkdir(parents=True, exist_ok=True)
    (root / ".github/workflows").mkdir(parents=True, exist_ok=True)
    (root / ".github/workflows/acima.yml").write_text("name: gate\n", encoding="utf-8")
    report_path = root / "docs/acima/gate.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    command = [sys.executable, str(SCRIPT), "--root", str(root),
               "--report", str(report_path), "--catalog", str(CATALOG),
               "--format", "json"]
    if claim:
        claim_path = root / "claim.json"
        claim_path.write_text(json.dumps(claim), encoding="utf-8")
        command += ["--claim", str(claim_path)]
    if initial:
        initial_path = root / "docs/acima/gate-initial.json"
        initial_path.write_text(json.dumps(initial), encoding="utf-8")
        command += ["--initial-report", str(initial_path)]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def finding(rule: str, fingerprint: str, path: str = "src/Orders/A.cs",
            status: str = "pre-existing") -> dict:
    return {"rule": rule, "severity": "error", "message": "m", "path": path,
            "line": 1, "evidence": "", "fingerprint": fingerprint, "status": status}


def test_grouping_and_status() -> None:
    with tempfile.TemporaryDirectory() as directory:
        report = {
            "standard": "1.0.0-draft.1", "level": "L1", "sourceFiles": 2,
            "newFindings": 0, "execution": execution_map(),
            "findings": [finding("ACIMA-D001", "sha256:waived1"),
                         finding("ACIMA-D001", "sha256:open2", "src/Billing/B.cs"),
                         finding("ACIMA-D009", "sha256:artifact3")],
        }
        report["execution"]["ACIMA-G004"] = {"executed": False, "reason": "manual"}
        data = run(Path(directory), report)
        assert data["status"] == "Partially aligned", data["status"]
        d001 = next(g for g in data["groups"] if g["rule"] == "ACIMA-D001")
        assert d001["count"] == 2 and d001["waived"] == 1
        d009 = next(g for g in data["groups"] if g["rule"] == "ACIMA-D009")
        assert d009["classification"] == "detector-artifact"
        assert d009["priority"] == "Review"
        assert any("ACIMA-G004" in item for item in data["limitations"])
        assert any("Gate" in item or "gate" in item for item in data["limitations"])
        assert data["status"] != "Verified"


def test_zero_findings_is_not_conformance() -> None:
    with tempfile.TemporaryDirectory() as directory:
        report = {"standard": "1.0.0-draft.1", "level": "L1", "sourceFiles": 2,
                  "newFindings": 0, "execution": execution_map(), "findings": []}
        data = run(Path(directory), report)
        assert data["status"] == "Assessment incomplete", data["status"]
        assert any("No full-conformance claim" in item for item in data["limitations"])


def test_full_claim_is_the_only_verified_route() -> None:
    with tempfile.TemporaryDirectory() as directory:
        report = {"standard": "1.0.0-draft.1", "level": "L1", "sourceFiles": 2,
                  "newFindings": 0, "execution": execution_map(), "findings": []}
        data = run(Path(directory), report, claim={"claim": "FULL CONFORMANCE",
                                                   "level": "L1"})
        assert data["status"] == "Verified", data["status"]


def test_reconciliation_names_the_difference() -> None:
    with tempfile.TemporaryDirectory() as directory:
        first = {"standard": "1.0.0-draft.1", "level": "L1", "sourceFiles": 2,
                 "newFindings": 1, "execution": execution_map(),
                 "findings": [finding("ACIMA-G001", "sha256:g001",
                                      ".acima/waivers.json")]}
        report = {"standard": "1.0.0-draft.1", "level": "L1", "sourceFiles": 2,
                  "newFindings": 0, "execution": execution_map(), "findings": []}
        data = run(Path(directory), report, initial=first)
        text = " ".join(data["reconciliation"])
        assert "**1**" in text and "ACIMA-G001" in text
        assert "Undocumented exception" in text


def main() -> int:
    tests = [value for name, value in sorted(globals().items())
             if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"{len(tests)} reporting tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
