"""Realistic end-to-end adoption evaluations.

Run ``python conformance/evaluate_adoption.py``. Each scenario uses a temporary repository and
the real tools, so the evaluation checks the evidence, guidance and consent boundary the agent is
given. It deliberately does not test prose generation or a model.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/acima-adoption"
CATALOG = json.loads((ROOT / "tools/acima-spec/rules.json").read_text(encoding="utf-8"))
SPEC = importlib.util.spec_from_file_location("acima_tool", ROOT / "tools/acima.py")
acima = importlib.util.module_from_spec(SPEC)
sys.modules["acima_tool"] = acima
SPEC.loader.exec_module(acima)

RESULTS: list[tuple[str, bool, str]] = []


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def config(root: Path) -> None:
    write(root / "acima.config.json", json.dumps({
        "standard": CATALOG["version"], "level": "L2", "mode": "base", "language": "python",
        "units": [{"id": "u0", "module": "app", "role": "implementation", "paths": ["src/a.py"]},
                  {"id": "u1", "module": "shared", "role": "implementation", "paths": ["src/b.py"]}],
    }))
    write(root / "src/a.py", "VALUE = 1\n")
    write(root / "src/b.py", "OTHER = 2\n")


def run_payload(findings: list[dict], sources: int = 2) -> dict:
    return {"standard": CATALOG["version"], "level": "L2", "sourceFiles": sources,
            "execution": {"ACIMA-L001": True, "ACIMA-D001": True},
            "findings": findings}


def baseline(root: Path, findings: list[dict], name: str = "baseline-a.json") -> None:
    write(root / "docs/acima" / name, json.dumps(run_payload(findings)))


def assessment(root: Path) -> None:
    write(root / "docs/acima/assessment.json", json.dumps({
        "readOnly": True, "root": str(root.resolve()), "verdict": "ASSESSED",
        "verdictMeaning": acima.VERDICT_MEANING["ASSESSED"], "sourceFiles": 2,
    }))


def scope(root: Path, objectives: dict[str, str]) -> None:
    write(root / ".acima/adoption-scope.json", json.dumps({
        "version": 1, "approvedBy": "repository-owner", "approvedOn": "2026-01-01",
        "objectives": [{"id": key, "disposition": value}
                       for key, value in objectives.items()],
    }))


def error(fingerprint: str) -> dict:
    return {"rule": "ACIMA-D001", "severity": "error", "message": "crosses a boundary",
            "path": "src/a.py", "line": 1, "fingerprint": "sha256:" + fingerprint * 64}


def observation(root: Path) -> None:
    sha = __import__("hashlib").sha256(
        (ROOT / "tools/acima-spec/rules.json").read_bytes()).hexdigest()
    write(root / ".github/workflows/acima.yml",
          "on: pull_request\njobs:\n  gate:\n    steps:\n"
          "      - run: python3 examples/python/tools/acima_arch.py --root . --level L2\n")
    write(root / "docs/acima/gate-observed.json", json.dumps({
        "manual": True, "repository": root.name, "commit": "a" * 40,
        "workflow": ".github/workflows/acima.yml",
        "command": "acima_arch.py --root .", "executedAt": "2026-11-09T10:00:00Z",
        "standard": CATALOG["version"], "catalogSha256": sha, "level": "L2",
        "exitCode": 0, "sourceFiles": 2,
    }))


def evaluate(name: str, function) -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        try:
            detail = function(root) or "ok"
            RESULTS.append((name, True, detail))
        except AssertionError as error_text:
            RESULTS.append((name, False, str(error_text)))
        except Exception as error_text:  # a scenario failure must be reported, not raised
            RESULTS.append((name, False, f"{type(error_text).__name__}: {error_text}"))


def novice(root: Path) -> str:
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert "ACIMA-L001" not in text[:3000], "the introduction exposes rule ids too early"
    write(root / "app.py", "VALUE = 1\n")
    status = acima.status_project(root)
    assert not status["next"]["approvalRequired"], "the first read is already gated"
    assert status["next"]["command"], "the first action has no command"
    return status["next"]["action"]


def unclear_monolith(root: Path) -> str:
    write(root / "src/service.py", "VALUE = 1\n")
    write(root / "src/other.py", "OTHER = 2\n")
    status = acima.status_project(root)
    assert "fit" in status["next"]["action"].lower(), status["next"]["action"]
    _, assessment = acima.assess_project(root)
    assert assessment["verdict"] == "NEEDS_UNIT_MAP", assessment["verdict"]
    assert assessment["assessmentResult"]["fit"] == "INSUFFICIENT_EVIDENCE"
    return "read-only fit path with named unknowns"


def aligned(root: Path) -> str:
    config(root)
    baseline(root, [])
    scope(root, {"assessment": "required", "local-enforcement": "approved",
                 "baseline-waivers": "approved", "ci-enforcement": "approved"})
    assessment(root)
    status = acima.status_project(root)
    own = {step["name"]: step for step in status["steps"]}["own"]
    assert own["state"] == "NOT_APPLICABLE", own
    assert status["next"]["approvalRequired"] is True
    assert "gate" in status["next"]["action"].lower()
    return status["next"]["action"]


def coupling(root: Path) -> str:
    config(root)
    baseline(root, [error("a")])
    scope(root, {"assessment": "required", "local-enforcement": "approved",
                 "baseline-waivers": "approved"})
    assessment(root)
    status = acima.status_project(root)
    own = {step["name"]: step for step in status["steps"]}["own"]
    assert own["state"] == "NOT_STARTED", own
    assert "exception" in status["next"]["action"].lower(), status["next"]["action"]
    assert status["next"]["approvalRequired"] is True
    return status["next"]["action"]


def unsupported(root: Path) -> str:
    write(root / "src/Main.java", "class Main {}\n")
    _, assessment = acima.assess_project(root)
    assert assessment["verdict"] == "UNSUPPORTED_LANGUAGE", assessment["verdict"]
    assert assessment["assessmentResult"]["fit"] == "NOT_SUPPORTED"
    return "unsupported profile reported without a conformance claim"


def copied(root: Path) -> str:
    skill = root / "installed/acima-adoption"
    shutil.copytree(SKILL, skill)
    target = root / "application"
    write(target / "src/app.py", "VALUE = 1\n")
    result = subprocess.run(
        [sys.executable, str(skill / "vendor/tools/acima.py"), "status",
         "--root", str(target), "--format", "json"],
        cwd=target, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["context"]["context"] == "vendor"
    assert "vendor/tools/acima.py" in report["next"]["command"]
    return "vendor context resolves its own commands"


def worthwhile(root: Path) -> str:
    write(root / "src/app.py", "VALUE = 1\n")
    _, assessment = acima.assess_project(root)
    result = assessment["assessmentResult"]
    assert result["benefits"], "no benefits were offered"
    assert result["levelGuidance"]["doesNotEstablish"], "no limit was explained"
    assert result["recommendation"]
    assert result["unknowns"]
    return result["recommendation"]


def everything_without_approval(root: Path) -> str:
    config(root)
    baseline(root, [error("a")])
    status = acima.status_project(root)
    assert status["next"]["approvalRequired"] is True
    assert status["next"]["writes"] is True
    assert "wait" in (SKILL / "SKILL.md").read_text(encoding="utf-8").lower()
    return "writes require explicit approval"


def partial_approval(root: Path) -> str:
    proposal = (SKILL / "assets/adoption-proposal.md").read_text(encoding="utf-8").lower()
    text = proposal + (SKILL / "SKILL.md").read_text(encoding="utf-8").lower()
    assert "partial" in text and "approve" in text
    return "partial approval is a supported path"


def returning_user(root: Path) -> str:
    config(root)
    baseline(root, [])
    scope(root, {"assessment": "required", "local-enforcement": "approved",
                 "baseline-waivers": "approved", "ci-enforcement": "approved"})
    assessment(root)
    observation(root)
    status = acima.status_project(root)
    gate = {step["name"]: step for step in status["steps"]}["gate"]
    assert gate["state"] == "IN_PROGRESS", gate
    assert status["next"]["doneWhen"]
    assert "provenance" in status["next"]["action"].lower()
    return status["next"]["action"]


SCENARIOS = [
    ("first-time user", novice),
    ("modular monolith with unclear boundaries", unclear_monolith),
    ("application already aligned with ACIMA", aligned),
    ("significant existing coupling", coupling),
    ("unsupported language profile", unsupported),
    ("copied skill without the checkout", copied),
    ("is adoption worthwhile", worthwhile),
    ("implement everything without approval", everything_without_approval),
    ("approve only part of the proposal", partial_approval),
    ("returning user asks what happens next", returning_user),
]


def main() -> int:
    for name, function in SCENARIOS:
        evaluate(name, function)
    width = max(len(name) for name, _ in SCENARIOS)
    for name, ok, detail in RESULTS:
        print(f"{'PASS' if ok else 'FAIL'}  {name:<{width}}  {detail}")
    failed = sum(1 for _, ok, _ in RESULTS if not ok)
    print(f"\n{len(RESULTS) - failed}/{len(RESULTS)} scenarios passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
