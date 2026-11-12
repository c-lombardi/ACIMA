#!/usr/bin/env python3
"""End-to-end adoption scenario matrix for the adoption skill (Improvement 5).

Scenarios A-M exercise the real preflight, assessment, status, enforcer and fix tools in
disposable repositories. Every scenario asserts observable state: the workflow phase, whether
anything was written, the assessment outcome, the approved scope, the next action, and that no
completion or conformance is claimed without evidence.

Conversation quality cannot be executed deterministically. Each scenario therefore also has a
structured response specification (initial message, repository fixture, expected discovery,
allowed and forbidden modifications, expected next state). The matrix reports those prose checks
as NOT EXECUTED; it never treats the specification as evidence that a model produced the right
answer. Scoring is fixed: an executable scenario is PASS only when every assertion holds, and
FAIL on an assertion or unexpected exception. Prose is NOT EXECUTED unless a real conversation is
run and scored; a specification is never a pass.

    python3 conformance/test_adoption_scenarios.py     # matrix, exit 1 on any failure
    python3 -m unittest conformance.test_adoption_scenarios
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/acima-adoption"
ACIMA = ROOT / "tools/acima.py"
PREFLIGHT = SKILL / "scripts/preflight.py"
ENFORCER = ROOT / "examples/python/tools/acima_arch.py"
CATALOG = json.loads((ROOT / "tools/acima-spec/rules.json").read_text(encoding="utf-8"))
CATALOG_VERSION = CATALOG["version"]

SPEC = importlib.util.spec_from_file_location("acima_scenarios", ACIMA)
acima = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules["acima_scenarios"] = acima
SPEC.loader.exec_module(acima)


# ---------------------------------------------------------------------------------------------
# Fixtures and evidence helpers
# ---------------------------------------------------------------------------------------------

def write(root: Path, relative: str, content: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def write_json(root: Path, relative: str, payload: dict) -> Path:
    return write(root, relative, json.dumps(payload, indent=2) + "\n")


def snapshot(root: Path) -> dict[str, str]:
    """Content identity for every file under the target, including optional documents."""
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*")) if path.is_file()
    }


def changed(before: dict[str, str], after: dict[str, str]) -> tuple[set[str], set[str], set[str]]:
    added = set(after) - set(before)
    removed = set(before) - set(after)
    modified = {path for path in set(before) & set(after) if before[path] != after[path]}
    return added, removed, modified


def invoke(args: list[object], cwd: Path = ROOT) -> subprocess.CompletedProcess:
    return subprocess.run([str(arg) for arg in args], cwd=str(cwd),
                          capture_output=True, text=True)


def invoke_json(args: list[object], cwd: Path = ROOT) -> tuple[int, dict]:
    result = invoke(args, cwd)
    assert result.stdout.strip(), result.stderr[-1000:]
    return result.returncode, json.loads(result.stdout)


def preflight(root: Path, *extra: object, manifest: Path | None = None) -> tuple[int, dict]:
    args: list[object] = [sys.executable, PREFLIGHT, "--project", root, "--format", "json"]
    args.extend(extra)
    if manifest is not None:
        args.extend(["--manifest", manifest])
    return invoke_json(args)


def config(root: Path, *, level: str = "L1", units: int = 3) -> None:
    definitions = [
        {"id": "orders", "module": "orders", "role": "implementation", "paths": ["src/orders"]},
        {"id": "billing", "module": "billing", "role": "implementation", "paths": ["src/billing"]},
        {"id": "payments", "module": "payments", "role": "implementation",
         "paths": ["src/payments"]},
    ]
    write_json(root, "acima.config.json", {
        "standard": CATALOG_VERSION, "mode": "base", "language": "python",
        "level": level, "root": ".",
        "units": definitions[:units],
        "exclude": ["tests", "**/__pycache__"],
    })


def modular(root: Path, *, violating: bool = False, payments: bool = False,
            new_feature: bool = False) -> None:
    if violating:
        write(root, "src/orders/service.py",
              "from src.billing.impl.charge import charge\n\n\n"
              "def place():\n    return charge()\n")
    elif new_feature:
        write(root, "src/orders/service.py", "def place():\n    return 1\n")
        write(root, "src/orders/new_feature.py", "VALUE = 2\n")
    else:
        write(root, "src/orders/service.py", "def place():\n    return 1\n")
    write(root, "src/billing/impl/charge.py", "def charge():\n    return 1\n")
    write(root, "src/billing/contracts/api.py", "VALUE = 1\n")
    if payments:
        write(root, "src/orders/impl/place.py", "def place():\n    return 1\n")
        write(root, "src/payments/service.py",
              "from src.orders.impl.place import place\n\n\n"
              "def pay():\n    return place()\n")


def enforcer(root: Path) -> dict:
    result = invoke([sys.executable, ENFORCER, "--root", root, "--format", "json"])
    assert result.returncode in (0, 1), (result.returncode, result.stdout[-1000:],
                                         result.stderr[-1000:])
    return json.loads(result.stdout)


def record_baseline(root: Path, name: str = "baseline-2026-01-01.json") -> dict:
    payload = enforcer(root)
    assert payload.get("sourceFiles", 0) > 0, "a zero-source run cannot be a baseline"
    write_json(root, f"acima/evidence/{name}", payload)
    return payload


def assess_tool(root: Path) -> dict:
    code, payload = invoke_json([sys.executable, ACIMA, "assess", "--root", root,
                                 "--format", "json"])
    assert code == 0, payload
    return payload


def record_assessment(root: Path) -> dict:
    payload = assess_tool(root)
    write_json(root, "acima/evidence/assessment.json", payload)
    return payload


def scope(root: Path, objectives: dict[str, str], approved_on: str = "2026-01-01") -> None:
    write_json(root, "acima/evidence/adoption-scope.json", {
        "version": 1, "approvedBy": "repository-owner", "approvedOn": approved_on,
        "objectives": [{"id": key, "disposition": value} for key, value in objectives.items()],
    })


def workflow(root: Path, level: str = "L1") -> None:
    write(root, ".github/workflows/acima.yml",
          "on: pull_request\njobs:\n  gate:\n    steps:\n"
          f"      - run: python3 examples/python/tools/acima_arch.py --root . --level {level}\n")


def step(report: dict, name: str) -> dict:
    return {entry["name"]: entry for entry in report["steps"]}[name]


def objective(report: dict, identifier: str) -> dict:
    return {entry["id"]: entry for entry in report["objectives"]}[identifier]


def no_adoption_artifacts(root: Path) -> None:
    assert not (root / "acima.config.json").exists(), "config was written without approval"
    assert not (root / "acima").exists(), "acima/ was written without approval"
    assert not (root / ".github").exists(), "CI was written without approval"
    assert not (root / "docs").exists(), "documents were written without approval"


def assert_plain(text: str) -> None:
    assert "ACIMA-A" not in text and "ACIMA-C" not in text and "ACIMA-D" not in text, text


# ---------------------------------------------------------------------------------------------
# Scenarios A-M
# ---------------------------------------------------------------------------------------------

def scenario_a(root: Path) -> str:
    """First-time user asks what ACIMA is and whether it would help."""
    modular(root)
    before = snapshot(root)

    code, report = preflight(root)
    assert code == 0, report.get("blockers")
    proposed = {unit["id"] for unit in report["proposedUnits"]}
    assert {"orders", "billing"} <= proposed, proposed
    assert any("no files were written" in item.lower() for item in report["next"]), report["next"]

    assessment = assess_tool(root)
    result = assessment["assessmentResult"]
    assert assessment["verdict"] == "NEEDS_UNIT_MAP", assessment["verdict"]
    assert result["fit"] in ("RECOMMENDED_WITH_LIMITATIONS",
                             "INSUFFICIENT_EVIDENCE"), result["fit"]
    assert result["recommendation"] and result["explanation"]["why"]
    assert result["benefits"] and result["whatItWillNotSolve"]
    assert result["unknowns"], "the honest limits were not named"
    assert 1 <= len(result["unresolvedQuestions"]) <= 3, result["unresolvedQuestions"]
    assert any("own" in question.lower() or "ownership" in question.lower()
               for question in result["unresolvedQuestions"]), result["unresolvedQuestions"]
    assert_plain(result["recommendation"] + " " + result["explanation"]["why"])

    status = acima.status_project(root)
    next_step = status["next"]
    assert next_step["writes"] is False and next_step["approvalRequired"] is False, next_step
    assert "fit" in next_step["action"].lower(), next_step["action"]
    assert "preflight.py" in next_step["command"] and "assess" in next_step["command"]
    assert snapshot(root) == before, "the first-time read-only path changed the target"
    no_adoption_artifacts(root)
    return (f"preflight proposed {sorted(proposed)}; fit {result['fit']} with "
            f"{len(result['unresolvedQuestions'])} unresolved question(s), including ownership; "
            "next action read-only")


def scenario_b(root: Path) -> str:
    """Small utility has no meaningful module boundaries."""
    write(root, "app.py", "VALUE = 1\n")
    before = snapshot(root)

    code, report = preflight(root)
    checks = {check["id"]: check for check in report["checks"]}
    assert code == 1 and "TGT-004" in report["blockers"], report["blockers"]
    remedy = checks["TGT-004"]["remedy"].lower()
    assert "56-requirement" in remedy and "before making an adoption recommendation" in remedy, remedy
    assert any("56-requirement" in item.lower() for item in report["next"]), report["next"]

    assessment = assess_tool(root)
    result = assessment["assessmentResult"]
    assert result["fit"] == "INSUFFICIENT_EVIDENCE", result["fit"]
    assert "0/56" in result["why"], result["why"]
    assert "no meaningful ownership boundaries" in result["why"], result["why"]
    assert result["dimensions"]["architecturalSubstance"]["status"] == "none"
    assert any("all catalog requirements" in item.lower() for item in result["unresolvedQuestions"])
    assert any(item["classification"] == "not-applicable"
               for item in result["benefitDetails"]), result["benefitDetails"]
    assert_plain(result["recommendation"] + " " + result["why"])

    status = acima.status_project(root)
    assert status["next"]["writes"] is False, status["next"]
    assert snapshot(root) == before
    no_adoption_artifacts(root)
    return "preflight blocks adoption, qualitative review still required; no adoption artifacts written"


def scenario_c(root: Path) -> str:
    """Existing well-structured application already has effective enforcement."""
    modular(root)
    config(root)
    workflow(root)
    before = snapshot(root)

    payload = assess_tool(root)
    result = payload["assessmentResult"]
    assert payload["verdict"] == "ASSESSED", payload["verdict"]
    assert result["fit"] == "INSUFFICIENT_EVIDENCE", result["fit"]
    assert "0/56" in result["why"], result["why"]
    assert result["existingEnforcement"]["status"] == "strong", result["existingEnforcement"]
    mechanisms = result["existingEnforcement"]["mechanisms"]
    assert any(item["kind"] == "acima-gate" for item in mechanisms), mechanisms
    assert result["dimensions"]["incrementalValue"]["status"] == "none"
    assert any(item["classification"] == "not-applicable" and "gate" in item["benefit"].lower()
               for item in result["benefitDetails"]), result["benefitDetails"]
    assert "configured" in result["explanation"]["existingEnforcement"].lower()
    assert snapshot(root) == before
    return ("existing configured ACIMA gate detected as strong; recommendation held at INSUFFICIENT_EVIDENCE "
            "until 56-rule review; no duplicate gate proposed")


def scenario_d(root: Path) -> str:
    """Brownfield modular monolith with significant pre-existing violations."""
    modular(root, violating=True, payments=True)
    config(root)
    before = snapshot(root)

    payload = assess_tool(root)
    result = payload["assessmentResult"]
    assert payload["verdict"] == "ASSESSED", payload["verdict"]
    assert result["fit"] == "INSUFFICIENT_EVIDENCE", result["fit"]
    assert "0/56" in result["why"], result["why"]
    findings = payload["findings"]
    assert findings["byRule"].get("ACIMA-D001", 0) >= 2, findings
    assert "existing findings" in result["why"], result["why"]
    assert result["dimensions"]["adoptionCost"]["status"] == "high"
    assert "No source rewrite is required" in result["dimensions"]["adoptionCost"]["migration"]
    assert result["recommendedNextAction"], result
    assert "rewrite" not in result["recommendation"].lower()
    assert any(item["classification"] == "requires-additional-work"
               for item in result["benefitDetails"]), result["benefitDetails"]
    assert snapshot(root) == before
    return (f"preliminary fit held at INSUFFICIENT_EVIDENCE pending 56-rule review; "
            f"{findings['byRule'].get('ACIMA-D001', 0)} D001 of {findings['total']} finding(s) found; "
            "incremental, no rewrite, first step identified")


def scenario_e(root: Path) -> str:
    """Unsupported architecture or language."""
    java = root / "java"
    write(java, "src/Main.java", "class Main {}\n")
    write_json(java, "acima.config.json", {
        "standard": CATALOG_VERSION, "mode": "base", "language": "java", "level": "L1",
        "root": ".", "units": [{"id": "app", "role": "implementation", "paths": ["src"]}],
    })
    before_java = snapshot(java)
    code, report = preflight(java)
    checks = {check["id"]: check for check in report["checks"]}
    assert code == 1 and "GOV-002" in report["blockers"], report["blockers"]
    assert "no reference enforcer" in checks["GOV-002"]["detail"].lower(), checks["GOV-002"]
    assert "unsupported, not clean" in checks["GOV-002"]["detail"].lower(), checks["GOV-002"]

    java_assessment = assess_tool(java)
    assert java_assessment["verdict"] == "UNSUPPORTED_LANGUAGE"
    assert java_assessment["assessmentResult"]["fit"] == "NOT_SUPPORTED"
    assert "cannot assess" in java_assessment["assessmentResult"]["recommendation"].lower()
    assert snapshot(java) == before_java

    topology = root / "topology"
    write(topology, "src/app.py", "VALUE = 1\n")
    write_json(topology, "acima.config.json", {
        "standard": CATALOG_VERSION, "mode": "base", "language": "python", "level": "L1",
        "root": ".", "units": [{"id": "app", "role": "implementation", "paths": ["src"]}],
    })
    write(topology, "acima.topology.json", "{}\n")
    before_topology = snapshot(topology)
    topology_assessment = assess_tool(topology)
    assert topology_assessment["verdict"] == "UNSUPPORTED_PROFILE"
    assert topology_assessment["assessmentResult"]["fit"] == "NOT_SUPPORTED"
    assert snapshot(topology) == before_topology
    return "Java profile and service-topology mode both reported unsupported, not clean"


def scenario_f(root: Path) -> str:
    """Existing configuration without optional adoption or communication plans."""
    modular(root)
    config(root)
    record_assessment(root)
    scope(root, {"assessment": "required", "local-enforcement": "approved"})
    record_baseline(root)
    before = snapshot(root)

    report = acima.status_project(root)
    assert objective(report, "assessment")["state"] == "COMPLETE"
    assert objective(report, "local-enforcement")["state"] == "COMPLETE"
    assert report["engagement"]["complete"] is True, report["engagement"]
    assert all(item["present"] is False for item in report["optional"]), report["optional"]
    assert report["next"]["action"].startswith("No further action"), report["next"]
    assert report["next"]["writes"] is False
    text = acima.status_text(report)
    assert "adoption plan" not in text.lower()
    assert "communication plan" not in text.lower()
    for relative in ("acima/optional/adoption-plan.md", "acima/optional/communication-plan.md",
                     "acima/handoff/STATUS.md"):
        assert not (root / relative).exists(), relative
    assert snapshot(root) == before
    return "assessment-only/local scope completed without any optional document"


def scenario_g(root: Path) -> str:
    """Required language toolchain is missing."""
    modular(root)
    config(root)
    before = snapshot(root)

    with mock.patch.object(acima.shutil, "which", return_value=None):
        code, assessment = acima.assess_project(root)
    assert code == 0
    assert assessment["verdict"] == "TOOLCHAIN_MISSING", assessment["verdict"]
    result = assessment["assessmentResult"]
    assert result["fit"] == "INSUFFICIENT_EVIDENCE", result["fit"]
    assert "not enough evidence" in result["recommendation"].lower(), result["recommendation"]
    assert assessment["nextSteps"], assessment
    assert snapshot(root) == before

    manifest = json.loads((SKILL / "manifest.json").read_text(encoding="utf-8"))
    manifest["enforcers"]["python"]["run"] = ["acima-missing-toolchain-xyz"]
    missing_manifest = root.parent / "missing-toolchain-manifest.json"
    write_json(root.parent, missing_manifest.name, manifest)
    code, report = preflight(root, manifest=missing_manifest)
    checks = {check["id"]: check for check in report["checks"]}
    assert code == 1 and "GOV-002" in report["blockers"], report["blockers"]
    detail = checks["GOV-002"]["detail"].lower()
    assert "not installed" in detail and "acima-missing-toolchain-xyz" in detail, detail
    assert "invalid or truncated" not in detail, detail
    assert "baseline is clean" not in detail
    assert snapshot(root) == before
    return "assessment INSUFFICIENT_EVIDENCE and preflight names the missing toolchain"


def scenario_h(root: Path) -> str:
    """Owner approves the unit map and local check, declines CI."""
    modular(root)
    before = snapshot(root)

    code, draft_report = preflight(root, "--write-draft", "acima.config.json")
    assert code == 0, draft_report.get("blockers")
    after_draft = snapshot(root)
    assert set(after_draft) - set(before) == {"acima.config.json"}
    draft = json.loads((root / "acima.config.json").read_text(encoding="utf-8"))
    assert {unit["id"] for unit in draft["units"]} >= {"orders", "billing"}, draft["units"]
    assert not (root / ".github").exists() and not (root / "docs").exists()

    record_assessment(root)
    record_baseline(root)
    scope(root, {"assessment": "required", "local-enforcement": "approved",
                 "ci-enforcement": "declined"})
    source_before = {path: digest for path, digest in before.items()}
    source_after = {path: digest for path, digest in snapshot(root).items()
                    if path in source_before}
    assert source_after == source_before, "approved local work changed application source"

    status_before = snapshot(root)
    report = acima.status_project(root)
    assert objective(report, "local-enforcement")["state"] == "COMPLETE"
    assert objective(report, "ci-enforcement")["state"] == "DECLINED"
    assert "ci-enforcement" in report["engagement"]["declined"]
    assert report["engagement"]["complete"] is True
    assert report["next"]["writes"] is False
    assert report["next"]["action"].startswith("No further action")
    assert not (root / ".github").exists(), "declined CI was created anyway"
    assert snapshot(root) == status_before
    return ("config, scope, assessment and local baseline added; CI declined, "
            "no workflow created")


def scenario_i(root: Path) -> str:
    """Owner decides not to proceed after the assessment."""
    modular(root, violating=True)
    config(root)
    payload = record_assessment(root)
    assert payload["findings"]["total"] > 0
    scope(root, {"assessment": "required", "local-enforcement": "declined",
                 "ci-enforcement": "declined", "baseline-waivers": "declined",
                 "full-conformance": "declined"})
    before = snapshot(root)

    status = acima.status_project(root)
    assert objective(status, "local-enforcement")["state"] == "DECLINED"
    assert objective(status, "ci-enforcement")["state"] == "DECLINED"
    assert status["engagement"]["complete"] is True
    assert status["next"]["action"].startswith("No further action"), status["next"]
    assert status["next"]["writes"] is False and status["next"]["approvalRequired"] is False
    assert "declined" in acima.status_text(status).lower()
    assert (root / "acima/evidence/assessment.json").is_file(), "read-only findings were discarded"
    assert snapshot(root) == before
    assert not (root / ".github").exists()
    return "decline respected; findings retained; no workflow, source or further write proposed"


def scenario_j(root: Path) -> str:
    """Owner asks to correct one specific finding, not the whole backlog."""
    modular(root, violating=True, payments=True)
    config(root)
    payload = enforcer(root)
    selected = [item for item in payload["findings"] if item["rule"] == "ACIMA-D001"]
    assert {item["path"] for item in selected} == {"src/orders/service.py",
                                                   "src/payments/service.py"}, selected
    report_path = root.parent / "run.json"
    write_json(root.parent, report_path.name, payload)
    before = snapshot(root)

    code, plan = invoke_json([sys.executable, ACIMA, "fix", "--report", report_path,
                              "--format", "json", "ACIMA-D001:src/orders/service.py"])
    assert code == 0, plan
    assert plan["total"] >= 2 and plan["selected"] == 1, plan
    assert plan["findings"][0]["path"] == "src/orders/service.py"
    assert "plan, not a patch" in plan["limitation"].lower()
    assert snapshot(root) == before, "the fix command edited the target"

    write(root, "src/orders/service.py", "def place():\n    return 1\n")
    after_run = enforcer(root)
    remaining = [item for item in after_run["findings"] if item["rule"] == "ACIMA-D001"]
    assert {item["path"] for item in remaining} == {"src/payments/service.py"}, remaining
    after = snapshot(root)
    added, removed, modified = changed(before, after)
    assert not added and not removed and modified == {"src/orders/service.py"}, (added, removed,
                                                                               modified)
    assert not (root / "acima").exists() and not (root / ".github").exists()
    return "fix plan stayed read-only; one authorized source correction removed only its finding"


def scenario_k(root: Path) -> str:
    """Installed skill outside the ACIMA checkout."""
    installed = root / "installed/acima-adoption"
    shutil.copytree(SKILL, installed,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    target = root / "application"
    write(target, "src/app.py", "VALUE = 1\n")
    before = snapshot(target)
    vendor_acima = installed / "vendor/tools/acima.py"
    assert vendor_acima.is_file()

    code, status = invoke_json([sys.executable, vendor_acima, "status",
                                "--root", target, "--format", "json"])
    assert code == 0, status
    assert status["context"]["context"] == "vendor", status["context"]
    command = status["next"]["command"]
    assert "vendor/tools/acima.py" in command, command
    for quoted in re.findall(r'"([^"]+)"', command):
        assert Path(quoted).is_file(), f"command path does not exist: {quoted}"
    assert str(ROOT / "tools/acima.py") not in command
    assert status["next"]["writes"] is False and status["next"]["approvalRequired"] is False

    code, report = invoke_json([sys.executable, installed / "scripts/preflight.py",
                                "--project", target, "--format", "json"])
    assert code in (0, 1), report
    checks = {check["id"]: check for check in report["checks"]}
    skill_checks = [check for check_id, check in checks.items() if check_id.startswith("SKL-")]
    assert skill_checks and all(check["status"] == "pass" for check in skill_checks), skill_checks

    code, assessment = invoke_json([sys.executable, vendor_acima, "assess",
                                    "--root", target, "--format", "json"])
    assert code == 0 and assessment["verdict"] == "NEEDS_UNIT_MAP", assessment["verdict"]
    assert assessment["readOnly"] is True

    code, deep = invoke_json([sys.executable, installed / "scripts/preflight.py",
                              "--project", target, "--deep", "--format", "json"])
    assert code in (0, 1), deep
    deep_checks = {check["id"]: check for check in deep["checks"]}
    assert "ENF-python" in deep_checks, sorted(deep_checks)
    assert deep_checks["ENF-python"]["status"] == "warn", deep_checks["ENF-python"]
    assert "not bundled" in deep_checks["ENF-python"]["detail"].lower()
    assert snapshot(target) == before
    return "vendor context resolves existing files; --deep explains the missing checkout"


def scenario_l(root: Path) -> str:
    """Resume an adoption after a pause and a repository change."""
    modular(root)
    config(root)
    assessment = record_assessment(root)
    scope(root, {"assessment": "required", "local-enforcement": "approved",
                 "ci-enforcement": "deferred"}, approved_on="2024-03-01")
    before_first = snapshot(root)

    first = acima.status_project(root)
    assert objective(first, "assessment")["state"] == "COMPLETE"
    assert objective(first, "local-enforcement")["state"] == "READY"
    assert objective(first, "ci-enforcement")["state"] == "DEFERRED"
    assert first["scope"]["approvedOn"] == "2024-03-01"
    assert first["engagement"]["complete"] is False
    assert "measure" in first["next"]["action"].lower(), first["next"]["action"]
    assert "assessment" not in first["next"]["action"].lower(), first["next"]["action"]
    assert snapshot(root) == before_first

    write(root, "src/orders/new_feature.py", "VALUE = 2\n")
    before_changed = snapshot(root)
    changed_state = acima.status_project(root)
    assert changed_state["sourceFiles"] == first["sourceFiles"] + 1
    assert assessment["sourceFiles"] != changed_state["sourceFiles"]
    assert objective(changed_state, "assessment")["state"] == "COMPLETE", \
        "resume repeated a completed assessment"
    assert "measure" in changed_state["next"]["action"].lower()
    assert snapshot(root) == before_changed

    record_baseline(root)
    before_complete = snapshot(root)
    complete = acima.status_project(root)
    assert objective(complete, "local-enforcement")["state"] == "COMPLETE"
    assert objective(complete, "ci-enforcement")["state"] == "DEFERRED"
    assert complete["engagement"]["complete"] is True
    assert complete["next"]["action"].startswith("No further action")
    assert snapshot(root) == before_complete
    return ("approved scope recovered; assessment not repeated; new source file present and "
            "measurement requested before completion")


def scenario_m(root: Path) -> str:
    """User says 'do everything' without naming a limited scope."""
    modular(root)
    before = snapshot(root)

    code, report = preflight(root)
    assert code == 0, report.get("blockers")
    assert report["proposedUnits"]
    assert any("present the adoption proposal" in item.lower() and "no files were written"
               in item.lower() for item in report["next"]), report["next"]

    assessment = assess_tool(root)
    result = assessment["assessmentResult"]
    assert result["fit"] in ("RECOMMENDED_WITH_LIMITATIONS",
                             "INSUFFICIENT_EVIDENCE"), result["fit"]
    assert result["fit"] != "RECOMMENDED", "a broad request turned a qualified fit into approval"
    assert result["unresolvedQuestions"]
    assert any(item["classification"] == "requires-additional-work"
               for item in result["benefitDetails"])

    status = acima.status_project(root)
    assert status["next"]["writes"] is False and status["next"]["approvalRequired"] is False
    assert "preflight.py" in status["next"]["command"]
    assert snapshot(root) == before
    no_adoption_artifacts(root)

    guidance = " ".join((SKILL / "SKILL.md").read_text(encoding="utf-8").split())
    workflow = " ".join((SKILL / "references/22-workflow.md").read_text(encoding="utf-8").split())
    for phrase in ("Analysis is never authorization", "A fix plan is not a patch"):
        assert phrase in guidance, phrase
    assert "Approval to change files never authorizes merge" in workflow
    return ("read-only discovery and fit completed; no file or CI write and no scope "
            "expansion occurred")


# ---------------------------------------------------------------------------------------------
# Conversation specifications (not executed)
# ---------------------------------------------------------------------------------------------

SCENARIO_SPECS: dict[str, dict] = {
    "A": {
        "user": "What is ACIMA, and would it help my application?",
        "fixture": "brownfield Python app with src/orders and src/billing, no config",
        "phase": "1. Assess",
        "discovery": ["purpose and layout", "languages and manifests", "candidate modules",
                      "existing enforcement"],
        "status": "NEEDS_UNIT_MAP with INSUFFICIENT_EVIDENCE, or a supported verdict",
        "response": ["plain-English explanation", "what was found and how", "benefits and limits",
                     "honest recommendation", "one next step"],
        "allowed": ["read-only inspection"],
        "forbidden": ["config", "waivers", "CI", "documents", "source edits"],
        "nextState": "one read-only assessment action, no approval required",
    },
    "B": {
        "user": "Would ACIMA help this small utility?",
        "fixture": "single app.py utility with no module directories",
        "phase": "1. Assess",
        "discovery": ["one source area", "no meaningful module ownership"],
        "status": "INSUFFICIENT_EVIDENCE until all 56 requirements are reviewed",
        "response": ["complete the qualitative review", "retain the preliminary no-boundaries observation",
                     "do not recommend adoption until the review is complete"],
        "allowed": ["read-only inspection"],
        "forbidden": ["unit declaration", "config", "CI", "documents"],
        "nextState": "no adoption artifacts; assessment available",
    },
    "C": {
        "user": "We already have module boundaries and CI checks. Should we adopt ACIMA?",
        "fixture": "clean two-unit Python app with a pull-request ACIMA workflow",
        "phase": "1. Assess",
        "discovery": ["existing boundaries", "existing gate", "whether its execution is observed"],
        "status": "INSUFFICIENT_EVIDENCE until all 56 requirements are reviewed; then avoid duplicate enforcement if already covered",
        "response": ["name existing strengths", "separate configured from observed",
                     "avoid selling good practice back as work"],
        "allowed": ["read-only inspection"],
        "forbidden": ["duplicate gate", "config", "waivers", "source edits"],
        "nextState": "no adoption artifacts; existing checks left intact",
    },
    "D": {
        "user": "We have modules but a lot of boundary violations. Adopt ACIMA.",
        "fixture": "modular monolith with cross-module implementation imports",
        "phase": "1. Assess / 2. Propose",
        "discovery": ["modular layout", "pre-existing findings", "no observed enforcement"],
        "status": "INSUFFICIENT_EVIDENCE until all 56 requirements are reviewed; preliminary findings retained",
        "response": ["no rewrite", "incremental first boundary", "pre-existing vs new findings",
                     "owner decisions named"],
        "allowed": ["read-only analysis", "proposal in conversation"],
        "forbidden": ["source rewrite", "baseline without approval", "waivers without owners"],
        "nextState": "proposal with one scope-limited approval question",
    },
    "E": {
        "user": "Adopt ACIMA for this Java repository / service topology.",
        "fixture": "Java source and config; separate base-mode repo with a topology manifest",
        "phase": "1. Assess / stop",
        "discovery": ["language/profile", "reference enforcer availability"],
        "status": "NOT_SUPPORTED",
        "response": ["exactly what is unsupported", "no invented coverage",
                     "alternative or stop"],
        "allowed": ["read-only inspection"],
        "forbidden": ["config", "CI", "conformance claim", "unit map"],
        "nextState": "stop with an explicit limitation",
    },
    "F": {
        "user": "I have acima.config.json but no adoption-plan.md. Continue.",
        "fixture": "adopting config, assessment evidence and local baseline without optional docs",
        "phase": "4. Implement / 5. Verify",
        "discovery": ["config", "approved scope", "assessment evidence", "baseline"],
        "status": "READY or COMPLETE within scope; optional documents absent",
        "response": ["continue without plans", "do not manufacture documentation work"],
        "allowed": ["only the approved implementation paths"],
        "forbidden": ["adoption plan", "communication plan", "STATUS dashboard"],
        "nextState": "one approved action, or no further action",
    },
    "G": {
        "user": "Assess this repository even though the language toolchain is not installed.",
        "fixture": "configured Python app; absent toolchain probe and missing-executable manifest",
        "phase": "1. Assess / stop",
        "discovery": ["supported language", "missing executable", "what was not measured"],
        "status": "TOOLCHAIN_MISSING with INSUFFICIENT_EVIDENCE",
        "response": ["what could and could not be measured", "no full-assessment claim",
                     "practical install/alternative step"],
        "allowed": ["read-only inspection"],
        "forbidden": ["clean result", "config", "baseline", "conformance claim"],
        "nextState": "install the toolchain or use a read-only partial assessment",
    },
    "H": {
        "user": "Approve the unit map and local check, but not CI.",
        "fixture": "brownfield app with approved config and local run; CI declined",
        "phase": "4. Implement / 5. Verify",
        "discovery": ["approved unit map", "approved local measurement", "declined CI"],
        "status": "local enforcement COMPLETE; CI DECLINED; engagement complete",
        "response": ["implement only approved paths", "name the unavailable CI capability",
                     "no CI proposal"],
        "allowed": ["acima.config.json", "assessment evidence", "local baseline", "scope record"],
        "forbidden": [".github/workflows", "waivers", "plans", "source refactor"],
        "nextState": "no further action inside the approved scope",
    },
    "I": {
        "user": "We are not going to adopt ACIMA.",
        "fixture": "configured app with an existing D001 assessment and a declining scope",
        "phase": "Decision after assessment",
        "discovery": ["recorded findings", "declined scope"],
        "status": "declined objectives; no further action",
        "response": ["respect the decision", "stop proposing implementation",
                     "retain requested read-only findings"],
        "allowed": ["read-only inspection", "retain existing evidence"],
        "forbidden": ["config", "CI", "waivers", "source edits", "new documents"],
        "nextState": "unchanged repository; adoption closed",
    },
    "J": {
        "user": "Fix this one finding.",
        "fixture": "three-unit app with two D001 findings in different modules",
        "phase": "Slice",
        "discovery": ["selected finding", "rule remedy", "unrelated findings"],
        "status": "one named finding resolved; gate re-measured",
        "response": ["explanation vs plan vs patch", "one boundary changed",
                     "unrelated work left alone"],
        "allowed": ["the explicitly authorized source correction"],
        "forbidden": ["other findings", "CI", "waivers", "bulk refactor"],
        "nextState": "remaining findings unchanged and still reported",
    },
    "K": {
        "user": "Use the installed skill; the ACIMA checkout is not here.",
        "fixture": "copied skill with vendor/ and a separate target; no checkout",
        "phase": "Vendor context",
        "discovery": ["skill root", "bundled vendor tools", "missing checkout-only features"],
        "status": "vendor context; read-only workflow available",
        "response": ["commands that exist", "no source-checkout paths",
                     "explain missing prerequisites"],
        "allowed": ["bundled scripts and vendor tools"],
        "forbidden": ["paths under a nonexistent checkout", "invented flags"],
        "nextState": "one runnable vendor-context action",
    },
    "L": {
        "user": "Continue where we left off.",
        "fixture": "config, assessment and local scope; a new source file, then a baseline",
        "phase": "Resume",
        "discovery": ["scope record", "current evidence", "what changed since last run"],
        "status": "completed work retained; one remaining action",
        "response": ["recovered approved scope", "change since last run",
                     "do not repeat completed work"],
        "allowed": ["read-only status", "the single approved next action"],
        "forbidden": ["re-assessment of a complete assessment", "scope expansion"],
        "nextState": "measurement, or no further action when the scope is complete",
    },
    "M": {
        "user": "Do everything.",
        "fixture": "brownfield two-unit app with no config and a broad request",
        "phase": "1. Assess / 2. Propose",
        "discovery": ["repository facts", "candidate scope", "approval boundary"],
        "status": "fit established; implementation not authorized",
        "response": ["complete read-only discovery", "name every approval-required change",
                     "do not merge, publish or expand scope"],
        "allowed": ["read-only inspection and a proposal"],
        "forbidden": ["config", "CI", "waivers", "source edits", "merge or release"],
        "nextState": "one scope-limited approval question",
    },
}


# ---------------------------------------------------------------------------------------------
# Registry and execution
# ---------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Scenario:
    identifier: str
    title: str
    phase: str
    check: Callable[[Path], str]


SCENARIOS = [
    Scenario("A", "First-time user", "1. Assess", scenario_a),
    Scenario("B", "Small utility", "1. Assess", scenario_b),
    Scenario("C", "Already structured and enforced", "1. Assess", scenario_c),
    Scenario("D", "Brownfield modular monolith", "1. Assess / 2. Propose", scenario_d),
    Scenario("E", "Unsupported architecture or language", "1. Assess / stop", scenario_e),
    Scenario("F", "Config without optional documents", "4. Implement / 5. Verify", scenario_f),
    Scenario("G", "Missing toolchain", "1. Assess / stop", scenario_g),
    Scenario("H", "Partial approval", "4. Implement / 5. Verify", scenario_h),
    Scenario("I", "Declined adoption", "Decision after assessment", scenario_i),
    Scenario("J", "One-finding correction", "Slice", scenario_j),
    Scenario("K", "Installed skill outside checkout", "Vendor context", scenario_k),
    Scenario("L", "Resumed adoption", "Resume", scenario_l),
    Scenario("M", "Do everything", "1. Assess / 2. Propose", scenario_m),
]


def execute(scenario: Scenario) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix=f"acima-scenario-{scenario.identifier.lower()}-") as temp:
        root = Path(temp) / "target"
        root.mkdir()
        try:
            return True, scenario.check(root)
        except AssertionError as error:
            return False, str(error) or "assertion failed"
        except Exception as error:  # a scenario failure is reported, never swallowed
            return False, f"{type(error).__name__}: {error}"


class AdoptionScenarioTests(unittest.TestCase):
    def test_response_specs_cover_every_scenario(self) -> None:
        self.assertEqual([scenario.identifier for scenario in SCENARIOS],
                         list(SCENARIO_SPECS))
        required = {"user", "fixture", "phase", "discovery", "status", "response", "allowed",
                    "forbidden", "nextState"}
        for scenario in SCENARIOS:
            spec = SCENARIO_SPECS[scenario.identifier]
            self.assertEqual(set(spec), required, scenario.identifier)
            self.assertEqual(spec["phase"], scenario.phase, scenario.identifier)
            for key in ("fixture", "discovery", "response", "allowed", "forbidden"):
                self.assertTrue(spec[key], f"{scenario.identifier}: {key} is empty")


def _scenario_test(scenario: Scenario):
    def test(self: unittest.TestCase) -> None:
        ok, detail = execute(scenario)
        self.assertTrue(ok, detail)
    return test


for _scenario in SCENARIOS:
    setattr(AdoptionScenarioTests,
            f"test_{_scenario.identifier.lower()}_{_scenario.title.lower().replace(' ', '_')}",
            _scenario_test(_scenario))


def main() -> int:
    rows: list[tuple[str, str, str, bool, str]] = []
    for scenario in SCENARIOS:
        ok, detail = execute(scenario)
        rows.append((scenario.identifier, scenario.title, scenario.phase, ok, detail))
    width = max(len(row[1]) for row in rows)
    print("ACIMA adoption scenario matrix (executable tool-level checks)\n")
    print(f"{'ID':<3} {'Scenario':<{width}}  {'Phase':<24}  Result  Evidence")
    for identifier, title, phase, ok, detail in rows:
        print(f"{identifier:<3} {title:<{width}}  {phase:<24}  "
              f"{'PASS' if ok else 'FAIL':<6}  {detail}")
    print()
    print("Conversation prose: NOT EXECUTED. Structured response specs are present and complete")
    print("for all 13 scenarios, but no model conversation was run or scored.")
    failed = [row for row in rows if not row[3]]
    print(f"{len(rows) - len(failed)}/{len(rows)} executable scenario checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
