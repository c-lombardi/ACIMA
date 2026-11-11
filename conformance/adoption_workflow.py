#!/usr/bin/env python3
"""End-to-end ACIMA adoption orchestration.

The engine is deliberately separate from the rule enforcers.  It decides which artifacts
exist, records why each stage is complete or blocked, and never turns a generated proposal
into ownership or a successful verification claim.

Modes
-----
guided
    Generate proposals and artifacts, then stop at the explicit map/scope approvals.
full
    Requires ``--authorize-full``.  Apply well-supported map decisions, generate enforcement,
    integrate an existing CI provider when safe, and verify the result.  Ambiguous ownership,
    destructive operations, deployment and publishing remain paused.

    python3 conformance/adoption_workflow.py start --project <repo> --mode guided
    python3 conformance/adoption_workflow.py start --project <repo> --mode full --authorize-full
    python3 conformance/adoption_workflow.py status --project <repo>
    python3 conformance/adoption_workflow.py approve --project <repo> --map-decisions <json> --scope <json>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "conformance"))
from module_map import (  # noqa: E402
    APPROVAL_FILE, CONFIG_NAME, ModuleMapError, apply_review, automatic_review,
    build_config, discover as discover_module_map, language_for, load_proposal,
    load_review, mode_can_auto_accept, proposed_units,
)
import agent_guidance  # noqa: E402

STATE_FILE = ".acima/adoption-workflow.json"
PREFLIGHT_FILE = ".acima/preflight.json"
PROPOSAL_JSON = ".acima/module-map.proposal.json"
SCOPE_FILE = ".acima/adoption-scope.json"
ADOPTION_PROPOSAL = "docs/acima/adoption-proposal.md"
ADOPTION_PROPOSAL_JSON = "docs/acima/adoption-proposal.json"
ENFORCEMENT_FILE = "docs/acima/enforcement.json"
ARCH_TESTS_FILE = ".acima/architecture-tests.json"
CI_FILE = "docs/acima/ci-integration.json"
VERIFICATION_FILE = "docs/acima/verification.json"
REMEDIATION_PLAN = "docs/acima/remediation-plan.json"
REMEDIATION_RESULT = "docs/acima/remediation-result.json"
HANDOFF_FILE = "docs/acima/adoption-handoff.md"
WAIVERS_FILE = ".acima/waivers.json"

MODES = ("guided", "full")
STAGE_ORDER = (
    "preflight", "discovery", "assessment", "module_map", "adoption_proposal",
    "implementation", "architecture_tests", "ci", "remediation", "verification",
    "agent_guidance", "handoff",
)
STAGE_LABEL = {
    "preflight": "Pre-flight authorization",
    "discovery": "Repository discovery",
    "assessment": "Comprehensive assessment",
    "module_map": "Module map",
    "adoption_proposal": "Adoption proposal",
    "implementation": "Enforcement implementation",
    "architecture_tests": "Architectural tests",
    "ci": "CI integration",
    "remediation": "Immediate remediation",
    "verification": "Fresh verification",
    "agent_guidance": "AI agent guidance",
    "handoff": "Final handoff",
}
COMPLETE = "complete"
IN_PROGRESS = "in_progress"
AWAITING = "awaiting_approval"
BLOCKED = "blocked"
NOT_APPLICABLE = "not_applicable"


class WorkflowError(ValueError):
    """The workflow cannot proceed safely."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> str:
    return date.today().isoformat()


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe(root: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise WorkflowError("workflow artifact path escapes the repository: %s" % relative)
    return root / candidate


def _write(root: Path, relative: str, text: str) -> Path:
    path = _safe(root, relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _write_json(root: Path, relative: str, value: dict) -> Path:
    return _write(root, relative, json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise WorkflowError("cannot read %s: %s" % (path, error)) from error
    if not isinstance(value, dict):
        raise WorkflowError("%s must contain a JSON object" % path)
    return value


def _revision(root: Path) -> dict:
    try:
        top = subprocess.run(["git", "-C", str(root), "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, timeout=15)
        # A temporary target nested under another checkout must not inherit that checkout's HEAD.
        if (top.returncode == 0 and top.stdout.strip()
                and Path(top.stdout.strip()).resolve() == root.resolve()):
            result = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                                    capture_output=True, text=True, timeout=15)
            if result.returncode == 0 and result.stdout.strip():
                status = subprocess.run(["git", "-C", str(root), "status", "--porcelain"],
                                        capture_output=True, text=True, timeout=15)
                return {"head": result.stdout.strip(), "dirty": bool(status.stdout.strip())}
    except (OSError, subprocess.SubprocessError):
        pass
    tracked = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or ".git" in path.parts or ".acima" in path.parts:
            continue
        relative = path.relative_to(root).as_posix()
        if relative.startswith("docs/acima/"):
            continue
        tracked.append("%s:%s" % (relative, hashlib.sha256(path.read_bytes()).hexdigest()))
    digest = hashlib.sha256("\n".join(tracked).encode("utf-8")).hexdigest()
    return {"head": "tree:" + digest[:40], "dirty": False}


def _application_revision(root: Path) -> str:
    """Hash application source and behavior inputs, not workflow/enforcement artifacts."""
    tracked = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or ".git" in path.parts or ".acima" in path.parts:
            continue
        relative = path.relative_to(root).as_posix()
        if (relative == CONFIG_NAME or relative.startswith("docs/acima/")
                or relative.startswith("tools/") or relative.startswith("examples/")
                or relative.startswith(".github/")):
            continue
        tracked.append("%s:%s" % (relative, hashlib.sha256(path.read_bytes()).hexdigest()))
    return hashlib.sha256("\n".join(tracked).encode("utf-8")).hexdigest()


def _maturity(root: Path, config: dict | None = None) -> dict:
    """Classify maturity from implementation and compatibility evidence, never age alone."""
    source_suffixes = {".py", ".ts", ".tsx", ".js", ".mjs", ".cjs", ".go", ".cs",
                       ".java", ".kt", ".rs", ".rb", ".php", ".scala", ".swift"}
    production = []
    tests = []
    for path in root.rglob("*"):
        if not path.is_file() or any(part in {".git", "node_modules", "dist", "build", "target",
                                               "bin", "obj", ".venv", "venv", "tools", "examples",
                                               "docs", ".acima"} for part in path.parts):
            continue
        if path.suffix.lower() not in source_suffixes:
            continue
        relative = path.relative_to(root).as_posix().lower()
        (tests if ("test" in relative or "spec" in relative) else production).append(relative)
    modules = len((config or {}).get("units") or [])
    manifests = sum(1 for name in ("pyproject.toml", "package.json", "go.mod", "Cargo.toml")
                    for path in root.rglob(name) if ".git" not in path.parts)
    commits = 0
    try:
        result = subprocess.run(["git", "-C", str(root), "rev-list", "--count", "HEAD"],
                                capture_output=True, text=True, timeout=15)
        if result.returncode == 0 and result.stdout.strip().isdigit():
            commits = int(result.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        pass
    signals = {"productionFiles": len(production), "testFiles": len(tests),
               "declaredUnits": modules, "manifests": manifests, "commitCount": commits}
    if not production:
        return {"mode": "unknown", "confidence": "low", "signals": signals,
                "evidence": ["No production source was found; maturity cannot be established."]}
    green = (len(production) <= 10 and modules <= 2 and manifests <= 2 and len(tests) == 0
             and commits <= 5)
    if green:
        return {"mode": "greenfield", "confidence": "high", "signals": signals,
                "evidence": ["Little production source, few ownership units, no regression tests and "
                             "a short history support greenfield treatment."]}
    return {"mode": "brownfield", "confidence": "high" if (len(production) > 20 or len(tests) > 0
                                                             or commits > 10) else "medium",
            "signals": signals,
            "evidence": ["Existing production source, ownership units, tests or history create "
                         "compatibility and regression obligations."]}


def _language(root: Path) -> str:
    """Select the dominant production language, not the first incidental source file."""
    return language_for(root)


def _dotnet_executable() -> str | None:
    found = shutil.which("dotnet")
    if found:
        return found
    configured = os.environ.get("DOTNET_ROOT")
    candidates = []
    if configured:
        candidates.append(Path(configured) / ("dotnet.exe" if os.name == "nt" else "dotnet"))
    candidates.extend([Path("C:/Program Files/dotnet/dotnet.exe"),
                       Path("C:/Program Files/dotnet/dotnet"),
                       Path("/c/Program Files/dotnet/dotnet.exe"),
                       Path("/mnt/c/Program Files/dotnet/dotnet.exe"),
                       Path("/usr/local/share/dotnet/dotnet"),
                       Path("/usr/bin/dotnet")])
    return next((str(path) for path in candidates if path.is_file()), None)


def _enforcer(root: Path, language: str) -> dict | None:
    """Describe a portable enforcer bundle and its invocation."""
    if language == "python":
        source = ROOT / "examples/python/tools/acima_arch.py"
        if not source.is_file():
            return None
        return {
            "language": language, "kind": "file", "target": "tools/acima_arch.py",
            "files": [{"source": str(source), "target": "tools/acima_arch.py"}],
            "command": "python3 tools/acima_arch.py --root . --config acima.config.json --format json",
            "argv": [sys.executable, "tools/acima_arch.py", "--root", ".", "--config",
                     CONFIG_NAME, "--format", "json"],
        }
    if language == "typescript":
        source = ROOT / "examples/typescript/tools/acima-arch.mjs"
        if not source.is_file():
            return None
        return {
            "language": language, "kind": "file", "target": "tools/acima-arch.mjs",
            "files": [{"source": str(source), "target": "tools/acima-arch.mjs"}],
            "command": "node tools/acima-arch.mjs --root . --config acima.config.json --format json",
            "argv": ["node", "tools/acima-arch.mjs", "--root", ".", "--config",
                     CONFIG_NAME, "--format", "json"],
        }
    if language == "dotnet":
        source_root = ROOT / "examples/dotnet"
        files = [
            {"source": str(source_root / "tools/Acima.ArchTests/Program.cs"),
             "target": "tools/Acima.ArchTests/Program.cs"},
            {"source": str(source_root / "tools/Acima.ArchTests/Acima.ArchTests.csproj"),
             "target": "tools/Acima.ArchTests/Acima.ArchTests.csproj"},
            {"source": str(source_root / "Directory.Build.props"),
             "target": "tools/Acima.ArchTests/Directory.Build.props"},
        ]
        if not all(Path(item["source"]).is_file() for item in files):
            return None
        return {
            "language": language, "kind": "project", "target": "tools/Acima.ArchTests",
            "files": files,
            "command": ("dotnet run --project tools/Acima.ArchTests -- --root . "
                        "--config acima.config.json --format json"),
            "argv": [_dotnet_executable() or "dotnet", "run", "--project",
                     "tools/Acima.ArchTests", "--", "--root", ".", "--config",
                     CONFIG_NAME, "--format", "json"],
        }
    return None


def _preflight_script() -> Path | None:
    candidates = [
        ROOT / "skills/acima-adoption/scripts/preflight.py",
        Path(__file__).resolve().parents[2] / "scripts/preflight.py",
        Path(__file__).resolve().parents[1] / "skills/acima-adoption/scripts/preflight.py",
    ]
    return next((path for path in candidates if path.is_file()), None)


def _run_preflight(root: Path) -> dict:
    script = _preflight_script()
    if script is None:
        return {"exitCode": 2, "payload": None, "error": "preflight.py was not found"}
    try:
        result = subprocess.run(
            [sys.executable, str(script), "--project", str(root), "--format", "json"],
            capture_output=True, text=True, timeout=300,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return {"exitCode": 2, "payload": None, "error": str(error)}
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = None
    return {"exitCode": result.returncode, "payload": payload,
            "error": result.stderr[-1000:] if result.stderr else ""}


def _ci(root: Path) -> dict:
    github = sorted((root / ".github/workflows").glob("*.yml")) + \
             sorted((root / ".github/workflows").glob("*.yaml")) if (root / ".github/workflows").is_dir() else []
    result = {
        "provider": None,
        "existing": [],
        "workflow": None,
        "status": "not_configured",
        "integration": "none",
        "instructions": [],
        "claim": "No remote run is claimed.",
    }
    if github:
        result.update(provider="github-actions", existing=[p.relative_to(root).as_posix() for p in github],
                      integration="existing-provider")
    elif (root / ".gitlab-ci.yml").is_file():
        result.update(provider="gitlab-ci", existing=[".gitlab-ci.yml"],
                      integration="existing-provider", status="manual_instructions")
    elif (root / "azure-pipelines.yml").is_file():
        result.update(provider="azure-devops", existing=["azure-pipelines.yml"],
                      integration="existing-provider", status="manual_instructions")
    elif (root / "Jenkinsfile").is_file():
        result.update(provider="jenkins", existing=["Jenkinsfile"],
                      integration="existing-provider", status="manual_instructions")
    else:
        result["instructions"] = [
            "No CI provider was detected. Keep the local enforcement command in the developer workflow.",
            "When CI is added, run the generated architectural command on pull requests and fail on a non-zero exit.",
        ]
    return result


def _stage(state: dict, name: str, status: str, detail: str,
           *, evidence: Any = None, next_action: str = "") -> None:
    state["stages"][name] = {
        "name": name,
        "label": STAGE_LABEL[name],
        "status": status,
        "detail": detail,
        "evidence": evidence,
        "nextAction": next_action,
        "updatedAt": _now(),
    }


def _next(state: dict, action: str, command: str, *, approval: bool = False,
          writes: bool = False, why: str = "", done: str = "") -> None:
    state["next"] = {"action": action, "command": command, "approvalRequired": approval,
                     "writes": writes, "why": why, "doneWhen": done}


def _new_state(root: Path, mode: str, reviewer: str | None) -> dict:
    return {
        "schemaVersion": 1,
        "mode": mode,
        "authorized": mode == "full",
        "authorizedBy": reviewer if mode == "full" else None,
        "authorizedOn": _today() if mode == "full" else None,
        "authorization": ("The user explicitly authorized the complete adoption workflow in pre-flight."
                          if mode == "full" else
                          "The user selected guided adoption; consequential changes await approval."),
        "repository": {"root": str(root.resolve()), "revision": _revision(root),
                       "applicationRevision": _application_revision(root)},
        "startedAt": _now(),
        "updatedAt": _now(),
        "stages": {},
        "artifacts": {},
        "decisions": [],
        "blockers": [],
        "next": {"action": "", "command": "", "approvalRequired": False,
                 "writes": False, "why": "", "doneWhen": ""},
    }


def _save(root: Path, state: dict) -> None:
    state["updatedAt"] = _now()
    _write_json(root, STATE_FILE, state)


def _load(root: Path) -> dict:
    path = root / STATE_FILE
    if not path.is_file():
        raise WorkflowError("no adoption workflow at %s; run `start --mode guided` or "
                            "`start --mode full --authorize-full` first" % STATE_FILE)
    state = _read_json(path)
    if state.get("mode") not in MODES:
        raise WorkflowError("workflow mode must be guided or full")
    if state["mode"] == "full" and state.get("authorized") is not True:
        raise WorkflowError("full automation was not explicitly authorized")
    return state


def _summary(state: dict) -> dict:
    stages = [state["stages"][name] for name in STAGE_ORDER if name in state["stages"]]
    return {
        "mode": state["mode"],
        "authorized": state.get("authorized", False),
        "repository": state.get("repository", {}),
        "stages": stages,
        "completed": [stage["name"] for stage in stages if stage["status"] == COMPLETE],
        "blocked": [stage["name"] for stage in stages if stage["status"] == BLOCKED],
        "awaiting": [stage["name"] for stage in stages if stage["status"] == AWAITING],
        "inProgress": [stage["name"] for stage in stages if stage["status"] == IN_PROGRESS],
        "artifacts": state.get("artifacts", {}),
        "decisions": state.get("decisions", []),
        "blockers": state.get("blockers", []),
        "remediation": state.get("remediation", {}),
        "agentGuidance": state.get("agentGuidance", {}),
        "verificationAfterRemediation": state.get("verificationAfterRemediation"),
        "next": state.get("next", {}),
    }


def _proposal_document(root: Path, module_map: dict, state: dict) -> dict:
    proposal = module_map.get("proposal") or {}
    modules = proposal.get("modules") or []
    if not modules:
        # An authoritative map is already the ownership input; describe its declared units
        # instead of treating the absence of a proposal as absent ownership.
        units = (module_map.get("authoritativeMap") or {}).get("units") or []
        grouped: dict[str, dict] = {}
        for unit in units:
            if not isinstance(unit, dict) or not unit.get("module"):
                continue
            item = grouped.setdefault(str(unit["module"]), {
                "name": str(unit["module"]), "confidence": "high",
                "contracts": {"paths": []}, "implementation": {"paths": []},
            })
            key = "contracts" if unit.get("role") == "contracts" else "implementation"
            item[key]["paths"].extend(unit.get("paths") or [])
        modules = list(grouped.values())
    recommendations = proposal.get("recommendations") or []
    existing_architecture = proposal.get("existingArchitecture") or {}
    strengths = []
    if existing_architecture.get("paths"):
        strengths.append("Existing architecture or enforcement evidence was found at: %s." %
                         ", ".join(existing_architecture["paths"][:8]))
    contract_modules = [module for module in modules if module.get("contracts", {}).get("paths")]
    if contract_modules:
        strengths.append("%s of %s candidate modules have an identified contract-shaped area "
                         "that can be preserved or made explicit." %
                         (len(contract_modules), len(modules)))
    manifest_modules = [module for module in modules
                        if module.get("confidence") in ("medium", "high")]
    if manifest_modules:
        strengths.append("%s candidate boundaries have project, package or existing-declaration evidence." %
                         len(manifest_modules))
    if proposal.get("coverage", {}).get("classifiedNonModule"):
        strengths.append("%s source file(s) can be accounted for as tests, tooling, fixtures, composition "
                         "or another explicit non-module role rather than silently becoming modules." %
                         proposal["coverage"]["classifiedNonModule"])
    if not strengths:
        strengths.append("No existing architecture declaration was established; the proposal records "
                         "that absence instead of presenting layout as ownership.")
    required = []
    for item in recommendations:
        required.append({
            "id": item.get("id"), "title": item.get("title"),
            "requirement": item.get("whyItMatters"),
            "outcome": item.get("benefit"),
            "implementation": item.get("recommendation"),
            "status": "proposed",
            "changes": item.get("changes") or [],
            "affectedFiles": item.get("affectedFiles") or [],
            "affectedModules": item.get("affectedModules") or [],
            "prerequisites": item.get("prerequisites") or [],
            "risks": item.get("risks") or [],
        })
    if not required:
        required.append({
            "id": "preserve-boundaries",
            "title": "Preserve the discovered boundaries",
            "requirement": "The repository has no structural recommendation from discovery; this is a proposal judgement, not proof of conformance.",
            "outcome": "No boundary is changed without evidence.",
            "implementation": "Keep the current implementation, record the boundary decision, and verify it with the enforcer.",
            "status": "proposed",
        })
    config = {"path": CONFIG_NAME, "purpose": "Declare the approved module ownership and level.",
              "status": "required", "action": "create" if not (root / CONFIG_NAME).exists() else "preserve"}
    tests = {"path": ARCH_TESTS_FILE, "purpose": "Record the positive and negative architectural test evidence.",
             "status": "required", "action": "create"}
    ci = {"path": CI_FILE, "purpose": "Record CI discovery and the integration outcome.",
          "status": "conditional", "action": "create"}
    existing_mechanism = ("Preserve and integrate the existing architecture declarations at %s; add only "
                         "the missing executable ACIMA configuration and checks." %
                         ", ".join(existing_architecture["paths"][:5])) if existing_architecture.get("paths") else \
        "Use the repository's dominant-language ACIMA reference enforcer plus an executable configuration."
    return {
        "schemaVersion": 1,
        "status": "proposed",
        "mode": state["mode"],
        "recommendation": "RECOMMENDED_WITH_LIMITATIONS" if modules else "INSUFFICIENT_EVIDENCE",
        "summary": ("Adopt the proposed module boundaries incrementally, preserve existing "
                    "architecture, and make enforcement executable." if modules else
                    "No safe ownership proposal is available; complete owner discovery first."),
        "existingStrengths": strengths,
        "existingArchitecture": existing_architecture,
        "coverage": proposal.get("coverage", {}),
        "pathDispositions": proposal.get("pathDispositions", []),
        "requiredChanges": required,
        "enforcementStrategy": {
            "mechanism": existing_mechanism,
            "positive": "Run the selected enforcer against compliant source and require a valid JSON result.",
            "negative": "Exercise a controlled violation and require the enforcer to detect it.",
            "manual": "Requirements that cannot be automated remain explicit manual evidence, not a pass.",
        },
        "implementationImpact": {
            "create": [config, tests, ci],
            "modify": [],
            "preserve": ["Existing application behavior and architecture that the evidence supports."],
            "estimated": False,
        },
        "risks": [
            "Discovery boundaries are inferred from layout and imports; owner review is required where confidence is low.",
            "A configured CI workflow is not evidence that a remote job ran.",
            "Requirements without automated enforcement remain unverified.",
        ],
        "verificationCriteria": [
            "The approved map covers all production source.",
            "The generated enforcer accepts a compliant fixture.",
            "A controlled violation is rejected.",
            "A fresh assessment after implementation records the resulting map and verification limits.",
        ],
        "decisions": proposal.get("decisions", []),
        "moduleMap": {
            "status": module_map.get("status"),
            "proposalId": module_map.get("proposalId"),
            "review": module_map.get("review"),
            "coverage": proposal.get("coverage", {}),
            "pathDispositions": proposal.get("pathDispositions", []),
            "existingArchitecture": existing_architecture,
        },
        "limitations": proposal.get("limitations", []),
        "generatedAt": _now(),
    }


def _proposal_markdown(document: dict, root: Path) -> str:
    lines = [
        "# Proposed ACIMA adoption — %s" % root.name,
        "",
        "> Generated by the ACIMA adoption workflow. This is a proposal, not authorization.",
        "",
        "## 1. Recommendation",
        "",
        "**%s**" % document["recommendation"],
        "",
        document["summary"],
        "",
        "## 2. Existing strengths to preserve",
        "",
    ]
    lines += ["- " + item for item in document["existingStrengths"]]
    lines += ["", "## 3. Repository coverage and dispositions", ""]
    coverage = document.get("coverage") or {}
    lines += ["- Source files inspected: %s" % coverage.get("sourceFiles", 0),
              "- Covered by module ownership: %s" % coverage.get("moduleCovered", 0),
              "- Explicitly classified as non-module: %s" % coverage.get("classifiedNonModule", 0),
              "- Unresolved production ownership: %s" % coverage.get("unresolvedProduction", 0), ""]
    dispositions = document.get("pathDispositions") or []
    if dispositions:
        lines.append("### Path dispositions")
        lines.append("")
        for item in dispositions:
            lines.append("- **%s** — `%s` (%s confidence): %s" %
                         (item.get("classification"), ", ".join(item.get("paths", [])),
                          item.get("confidence"), item.get("reason", "")))
        lines.append("")
    lines += ["## 4. Required changes", ""]
    for item in document["requiredChanges"]:
        lines += [
            "### %s" % item["title"],
            "",
            "- Requirement: %s" % item["requirement"],
            "- Required outcome: %s" % item["outcome"],
            "- Proposed implementation: %s" % item["implementation"],
            "- Affected files: %s" % (", ".join(item.get("affectedFiles", [])) or "Not established"),
            "- Affected modules: %s" % (", ".join(item.get("affectedModules", [])) or "Not established"),
            "- Status: %s" % item["status"],
            "",
        ]
    lines += ["## 5. Enforcement strategy", "",
              "**Mechanism:** %s" % document["enforcementStrategy"]["mechanism"], "",
              "- Positive: %s" % document["enforcementStrategy"]["positive"],
              "- Negative: %s" % document["enforcementStrategy"]["negative"],
              "- Manual: %s" % document["enforcementStrategy"]["manual"], "",
              "## 6. Implementation impact", ""]
    for item in document["implementationImpact"]["create"]:
        lines.append("- Create `%s`: %s (%s)." % (item["path"], item["purpose"], item["status"]))
    lines += ["", "## 7. Risks and tradeoffs", ""]
    lines += ["- " + item for item in document["risks"]]
    lines += ["", "## 8. Verification criteria", ""]
    lines += ["- " + item for item in document["verificationCriteria"]]
    lines += ["", "## 9. Decisions requiring the owner", ""]
    decisions = document.get("decisions") or []
    if decisions:
        for item in decisions:
            lines.append("- **%s** — %s (essential: %s; status: %s)" %
                         (item.get("question"), item.get("recommendation"),
                          "yes" if item.get("essential") else "no", item.get("status")))
    else:
        lines.append("- No module-level decision was generated; this is not proof that ownership is settled.")
    lines += ["", "## 10. Approval", "",
              "Guided adoption: approve the module-map decisions and this scope before implementation.",
              "Full automation: continue only within the explicit pre-flight authorization and safety boundaries.",
              "No application source is changed by this proposal.", ""]
    return "\n".join(lines)


def _write_proposal(root: Path, module_map: dict, state: dict) -> dict:
    document = _proposal_document(root, module_map, state)
    _write(root, ADOPTION_PROPOSAL, _proposal_markdown(document, root))
    _write_json(root, ADOPTION_PROPOSAL_JSON, document)
    state["artifacts"]["adoptionProposal"] = ADOPTION_PROPOSAL
    state["artifacts"]["adoptionProposalData"] = ADOPTION_PROPOSAL_JSON
    return document


def _review_for(proposal: dict, reviewer: str) -> dict:
    return automatic_review(proposal, reviewer)


def _can_auto_accept(proposal: dict) -> tuple[bool, str]:
    return mode_can_auto_accept(proposal)


def _adopt_map(root: Path, state: dict, module_map: dict, reviewer: str) -> tuple[bool, str]:
    proposal = module_map.get("proposal")
    if not proposal:
        authoritative = (module_map.get("authoritativeMap") or {})
        if authoritative.get("status") == "complete":
            state["artifacts"]["moduleMap"] = CONFIG_NAME
            return True, "An authoritative map already covers all production source."
        return False, "no proposal and no complete authoritative map"
    allowed, reason = _can_auto_accept(module_map)
    if not allowed:
        return False, reason
    review = _review_for(module_map, reviewer)
    try:
        result = apply_review(module_map, review, root=root)
        if result.get("status") != "approved":
            approval = result.get("approval") or {}
            pending = (approval.get("undecidedModules") or []) + \
                      (approval.get("undecidedPathDispositions") or [])
            detail = "; ".join(pending[:6])
            return False, ("automatic review did not approve a complete map: %s%s" %
                           (result.get("status"), (" (" + detail + ")") if detail else ""))
        existing = _read_json(root / CONFIG_NAME) if (root / CONFIG_NAME).is_file() else None
        config = build_config(module_map, result, existing=existing, language=_language(root))
        _write_json(root, CONFIG_NAME, config)
        _write_json(root, APPROVAL_FILE, result)
        state["artifacts"]["moduleMapApproval"] = APPROVAL_FILE
        state["artifacts"]["moduleMap"] = CONFIG_NAME
        state["decisions"].append({
            "id": "module-map", "decision": "accepted", "by": reviewer,
            "on": _today(), "basis": "explicit full-automation pre-flight authorization",
            "proposalId": module_map.get("proposalId"),
        })
        state["blockers"] = [item for item in state.get("blockers", [])
                             if not str(item).startswith("TGT-")]
        return True, reason
    except (ModuleMapError, OSError, ValueError) as error:
        return False, str(error)


def _scope_document(state: dict, root: Path, *, ci_available: bool) -> dict:
    objectives = [
        {"id": "assessment", "disposition": "required"},
        {"id": "local-enforcement", "disposition": "approved"},
        {"id": "baseline-waivers", "disposition": "approved"},
        {"id": "ci-enforcement", "disposition": "approved" if ci_available else "deferred",
         "reason": "" if ci_available else "No supported CI provider was detected."},
        {"id": "developer-handoff", "disposition": "approved"},
        {"id": "agent-guidance", "disposition": "approved"},
        {"id": "full-conformance", "disposition": "deferred",
         "reason": "Verification evidence is not a full-conformance claim."},
        {"id": "communication-governance", "disposition": "optional"},
    ]
    return {
        "version": 1,
        "approvedBy": state.get("authorizedBy") or "full-automation",
        "approvedOn": _today(),
        "proposal": ADOPTION_PROPOSAL,
        "objectives": objectives,
        "authorization": {
            "mode": state["mode"], "explicit": True,
            "scope": "ACIMA adoption inside the selected repository only; no deployment, release, commit or push.",
        },
    }


def _write_scope(root: Path, state: dict) -> dict:
    ci = _ci(root)
    document = _scope_document(state, root, ci_available=bool(ci.get("provider")))
    _write_json(root, SCOPE_FILE, document)
    state["artifacts"]["scope"] = SCOPE_FILE
    return document


def _copy_enforcer(root: Path, language: str) -> dict:
    plan = _enforcer(root, language)
    if not plan:
        return {"status": "unsupported", "reason": "No portable enforcer for %s." % language,
                "command": None, "path": None, "files": []}
    copied = []
    preserved = []
    for item in plan["files"]:
        source = Path(item["source"])
        target = item["target"]
        destination = root / target
        if destination.exists():
            if not destination.is_file() or destination.read_bytes() != source.read_bytes():
                return {"status": "blocked", "path": plan["target"],
                        "command": plan["command"], "files": copied,
                        "reason": "The target already has different content at %s; refusing to overwrite it." % target}
            preserved.append(target)
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied.append(target)
    return {"status": "implemented" if copied else "preserved",
            "path": plan["target"], "command": plan["command"],
            "files": copied or preserved, "language": language}


def _write_waivers(root: Path, config: dict) -> None:
    path = root / WAIVERS_FILE
    if not path.is_file():
        _write_json(root, WAIVERS_FILE, {"standard": config.get("standard", "1.9.0-draft.1"),
                                         "waivers": []})


def _run(command: list[str], cwd: Path, timeout: int = 120) -> tuple[int, str, str]:
    try:
        result = subprocess.run(command, cwd=str(cwd), capture_output=True, text=True,
                                timeout=timeout)
        return result.returncode, result.stdout, result.stderr
    except (OSError, subprocess.SubprocessError) as error:
        return 127, "", str(error)


def _negative_probe(root: Path, language: str) -> dict:
    """Prove the copied enforcer rejects a controlled dependency violation."""
    plan = _enforcer(root, language)
    if not plan:
        return {"status": "unsupported", "reason": "No portable enforcer for %s." % language}
    if language not in {"python", "dotnet"}:
        return {"status": "not_run",
                "reason": "A controlled negative probe is implemented for Python and .NET in this revision."}
    with tempfile.TemporaryDirectory() as directory:
        probe = Path(directory)
        for item in plan["files"]:
            destination = probe / item["target"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item["source"], destination)
        if language == "python":
            for relative, text in {
                "src/a/impl/service.py": "from src.b.impl.internal import VALUE\n\ndef use():\n    return VALUE\n",
                "src/b/impl/internal.py": "VALUE = 1\n",
            }.items():
                path = probe / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
            config = {
                "standard": "1.9.0-draft.1", "mode": "base", "language": "python",
                "level": "L1", "root": ".", "units": [
                    {"id": "a", "module": "a", "role": "implementation", "paths": ["src/a/impl"]},
                    {"id": "b", "module": "b", "role": "implementation", "paths": ["src/b/impl"]},
                ],
            }
        else:
            for relative, text in {
                "src/a/impl/A.csproj": '<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net8.0</TargetFramework></PropertyGroup><ItemGroup><ProjectReference Include="../../b/impl/B.csproj" /></ItemGroup></Project>',
                "src/a/impl/Service.cs": "namespace A; public sealed class Service { public object Read() => new B.Internal(); }\n",
                "src/b/impl/B.csproj": '<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net8.0</TargetFramework></PropertyGroup></Project>',
                "src/b/impl/Internal.cs": "namespace B; public sealed class Internal { }\n",
            }.items():
                path = probe / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
            config = {
                "standard": "1.9.0-draft.1", "mode": "base", "language": "dotnet",
                "level": "L1", "root": ".", "units": [
                    {"id": "a", "module": "a", "role": "implementation", "paths": ["src/a/impl"]},
                    {"id": "b", "module": "b", "role": "implementation", "paths": ["src/b/impl"]},
                ],
            }
        (probe / CONFIG_NAME).write_text(json.dumps(config), encoding="utf-8")
        code, out, err = _run(plan["argv"], probe)
        try:
            payload = json.loads(out)
        except json.JSONDecodeError:
            return {"status": "failed", "reason": (err or out or "invalid JSON")[:400]}
        findings = payload.get("findings") or []
        detected = any(item.get("rule") == "ACIMA-D001" for item in findings)
        return {"status": "detected" if detected else "missed", "rule": "ACIMA-D001",
                "exitCode": code, "findingCount": len(findings)}


def _write_enforcement(root: Path, state: dict, config: dict) -> dict:
    language = config.get("language") or _language(root)
    result = _copy_enforcer(root, language)
    _write_waivers(root, config)
    tests = {
        "schemaVersion": 1,
        "language": language,
        "status": result.get("status"),
        "enforcer": result,
        "positive": {"status": "not_run", "command": result.get("command")},
        "negative": {"status": "not_run", "rule": "ACIMA-D001"},
        "limitations": [],
    }
    _write_json(root, ARCH_TESTS_FILE, tests)
    enforcement = {
        "schemaVersion": 1,
        "status": result.get("status"),
        "config": CONFIG_NAME,
        "enforcer": result,
        "waivers": WAIVERS_FILE,
        "architectureTests": ARCH_TESTS_FILE,
        "requirementsWithAutomatedEnforcement": {"python": 41, "typescript": 41, "dotnet": 31}.get(language, 0),
        "requirementsWithoutAutomatedEnforcement": {"python": 14, "typescript": 14, "dotnet": 24}.get(language, 55),
        "limitations": [],
    }
    _write_json(root, ENFORCEMENT_FILE, enforcement)
    state["artifacts"]["enforcement"] = ENFORCEMENT_FILE
    state["artifacts"]["architectureTests"] = ARCH_TESTS_FILE
    return enforcement


def _integrate_ci(root: Path, state: dict, command: str | None) -> dict:
    discovered = _ci(root)
    document = dict(discovered)
    document["command"] = command
    if not command:
        document["status"] = "blocked"
        document["reason"] = "No executable enforcer command is available."
    elif discovered.get("provider") == "github-actions" and state["mode"] == "full":
        workflow = root / ".github/workflows/acima.yml"
        if not workflow.exists():
            workflow.parent.mkdir(parents=True, exist_ok=True)
            workflow.write_text(
                "name: ACIMA architecture\non:\n  pull_request:\n  merge_group:\n"
                "jobs:\n  architecture:\n    runs-on: ubuntu-latest\n    steps:\n"
                "      - uses: actions/checkout@v4\n"
                "      - name: Run ACIMA enforcement\n        run: %s\n" % command,
                encoding="utf-8")
            document.update(status="configured", integration="generated-workflow",
                            workflow=".github/workflows/acima.yml")
        else:
            document.update(status="already_present", integration="existing-workflow",
                            workflow=".github/workflows/acima.yml")
    elif discovered.get("provider"):
        document["status"] = "manual_instructions"
        document["instructions"] = [
            "Add the command to the detected provider's pull-request validation stage.",
            "Fail the job on a non-zero exit code and preserve the JSON result as an artifact.",
        ]
    else:
        document["status"] = "no_provider"
    document["claim"] = ("Configured locally; no remote CI run was observed or claimed."
                         if document["status"] in ("configured", "already_present", "manual_instructions")
                         else "No CI integration was made.")
    _write_json(root, CI_FILE, document)
    state["artifacts"]["ci"] = CI_FILE
    return document


def _verify(root: Path, state: dict, config: dict) -> dict:
    language = config.get("language") or _language(root)
    item = _enforcer(root, language)
    result = {
        "schemaVersion": 1,
        "status": "not_run",
        "language": language,
        "assessment": {},
        "positive": {"status": "not_run"},
        "negative": {"status": "not_run"},
        "ci": {},
        "limitations": [],
    }
    if item:
        targets = [root / entry["target"] for entry in item["files"]]
        if all(path.exists() for path in targets):
            code, out, err = _run(item["argv"], root, timeout=240)
            try:
                payload = json.loads(out)
            except json.JSONDecodeError:
                result["positive"] = {"status": "failed", "exitCode": code,
                                      "reason": (err or out or "invalid JSON")[:400]}
            else:
                findings = payload.get("findings") or []
                result["positive"] = {
                    "status": "valid" if code in (0, 1) and isinstance(payload.get("sourceFiles"), int)
                    else "failed",
                    "exitCode": code, "sourceFiles": payload.get("sourceFiles"),
                    "findingCount": len(findings),
                    "findings": len(findings),
                    "command": item["command"],
                }
        else:
            result["positive"] = {"status": "blocked", "reason": "The enforcer is not present in the target."}
    else:
        result["positive"] = {"status": "unsupported", "reason": "No portable enforcer."}
    result["negative"] = _negative_probe(root, language)
    map_now = discover_module_map(root)
    result["assessment"] = {
        "status": map_now.get("status"),
        "authoritativeMap": map_now.get("authoritativeMap", {}).get("status"),
        "ownershipGate": "ready" if map_now.get("authoritativeMap", {}).get("status") == "complete" else "blocked",
    }
    ci = _read_json(root / CI_FILE) if (root / CI_FILE).is_file() else {}
    result["ci"] = {"status": ci.get("status"), "provider": ci.get("provider"),
                    "claim": ci.get("claim")}
    ok = (result["positive"].get("status") == "valid" and
          result["negative"].get("status") == "detected")
    result["status"] = "verified" if ok else "incomplete"
    if not ok:
        result["limitations"].append("Positive and negative enforcement evidence are both required; "
                                     "a missing probe is not a pass.")
    _write_json(root, VERIFICATION_FILE, result)
    state["artifacts"]["verification"] = VERIFICATION_FILE
    return result


def _remediation_items(root: Path, state: dict) -> list[dict]:
    proposal_path = root / ADOPTION_PROPOSAL_JSON
    proposal = _read_json(proposal_path) if proposal_path.is_file() else {}
    items = []
    for index, change in enumerate(proposal.get("requiredChanges") or []):
        if not isinstance(change, dict):
            continue
        actions = [item for item in (change.get("changes") or []) if isinstance(item, dict)]
        items.append({
            "id": change.get("id") or "recommendation-%s" % (index + 1),
            "title": change.get("title") or "Architectural recommendation",
            "requirement": change.get("requirement") or "",
            "outcome": change.get("outcome") or "",
            "impact": change.get("implementation") or "",
            "affectedFiles": change.get("affectedFiles") or
                            sorted({str(action.get("path")) for action in actions if action.get("path")}),
            "prerequisites": change.get("prerequisites") or [],
            "risks": change.get("risks") or [],
            "changes": actions,
            "status": "ready" if actions else "manual",
            "reason": "" if actions else "No deterministic file change was supplied for this recommendation; it needs implementation guidance or owner review.",
        })
    if not items:
        items.append({
            "id": "preserve-boundaries", "title": "Preserve the discovered boundaries",
            "requirement": "No structural recommendation was generated.",
            "outcome": "No application source is changed without evidence.",
            "impact": "Keep the current implementation and maintain enforcement.",
            "affectedFiles": [], "prerequisites": [], "risks": [], "changes": [],
            "status": "manual", "reason": "No actionable recommendation was supplied.",
        })
    return items


def _remediation_risk(items: list[dict], maturity: dict) -> dict:
    files = sorted({str(path) for item in items for path in item.get("affectedFiles", []) if path})
    modules = sorted({str(module) for item in items for module in item.get("affectedModules", []) if module})
    high_flags = []
    for item in items:
        for change in item.get("changes", []):
            if change.get("contractChange"):
                high_flags.append("public contract change")
            if change.get("dataChange") or change.get("migration"):
                high_flags.append("data or migration change")
    large = (len(files) > 20 or len(modules) > 3 or len(items) > 8 or bool(high_flags))
    level = "large" if large else "moderate" if (len(files) > 3 or len(items) > 1) else "small"
    brownfield = maturity.get("mode") == "brownfield"
    return {"level": level, "affectedFiles": files, "affectedModules": modules,
            "reasons": high_flags + (["Broad file or recommendation scope."] if len(files) > 20 or len(items) > 8 else []),
            "requiresTwoConfirmations": bool(brownfield and level == "large"),
            "mode": maturity.get("mode")}


def write_remediation_plan(root: Path, state: dict) -> dict:
    """Write the final decision aid after CI; never apply a recommendation here."""
    proposal_path = root / ADOPTION_PROPOSAL_JSON
    proposal = _read_json(proposal_path) if proposal_path.is_file() else {}
    config_path = root / CONFIG_NAME
    config = _read_json(config_path) if config_path.is_file() else {}
    maturity = _maturity(root, config)
    items = _remediation_items(root, state)
    risk = _remediation_risk(items, maturity)
    plan = {
        "schemaVersion": 1, "status": "awaiting_decision", "generatedAt": _now(),
        "position": "after CI integration and before final verification",
        "maturity": maturity, "classificationRequired": maturity.get("mode") not in ("greenfield", "brownfield"),
        "risk": risk,
        "recommendation": ("Apply all applicable recommendations now to establish the intended "
                           "architecture while the greenfield codebase is still small."
                           if maturity.get("mode") == "greenfield" else
                           "Choose a bounded remediation scope; preserve existing behavior and verify before release."),
        "options": [
            {"id": "none", "label": "Apply none now", "description": "Keep the implementation and document the remaining work."},
            {"id": "selected", "label": "Apply selected fixes", "description": "Implement only the named recommendation IDs."},
            {"id": "all", "label": "Apply all applicable fixes", "description": "Implement every evidence-supported recommendation with a deterministic change."},
        ],
        "recommendations": items,
        "claim": "No recommendation is applied by this plan.",
    }
    _write_json(root, REMEDIATION_PLAN, plan)
    state["artifacts"]["remediationPlan"] = REMEDIATION_PLAN
    state.setdefault("remediation", {})
    state["remediation"].update({"plan": REMEDIATION_PLAN, "maturity": maturity,
                                "risk": risk, "choice": None, "scopeAcknowledged": False})
    return plan


def _apply_changes(root: Path, item: dict) -> dict:
    applied = []
    backups: dict[Path, bytes | None] = {}

    def restore() -> None:
        for path, data in reversed(list(backups.items())):
            if data is None:
                if path.exists():
                    path.unlink()
            else:
                path.write_bytes(data)

    def fail(reason: str) -> dict:
        restore()
        return {"status": "failed", "reason": reason}

    for change in item.get("changes") or []:
        relative = change.get("path")
        if not relative:
            return fail("A change has no path.")
        path = _safe(root, str(relative))
        action = change.get("action", "replace")
        if action == "create":
            if path.exists():
                return fail("Refusing to overwrite existing %s." % relative)
            backups.setdefault(path, None)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(str(change.get("content", "")), encoding="utf-8")
            applied.append(str(relative))
            continue
        if action != "replace":
            return fail("Unsupported change action %s." % action)
        if not path.is_file():
            return fail("Missing target %s." % relative)
        before = path.read_text(encoding="utf-8")
        find = change.get("find")
        replace = change.get("replace")
        if not isinstance(find, str) or not find or replace is None:
            return fail("Replace changes need find and replace text.")
        if find not in before:
            return fail("The stated original text is not present in %s; revalidate the finding." % relative)
        backups.setdefault(path, before.encode("utf-8"))
        path.write_text(before.replace(find, str(replace), 1), encoding="utf-8")
        applied.append(str(relative))
    return {"status": "applied", "files": applied}


def _fresh_assessment(root: Path, state: dict, config: dict) -> dict:
    # The final assessment must be a new discovery, not a reused pre-remediation result.
    verification = _verify(root, state, config)
    state["verificationAfterRemediation"] = verification.get("status")
    return verification


def _apply_agent_guidance(root: Path, state: dict, *, approve: bool = False) -> dict | None:
    """Refresh the proposal, then apply it only within the approved adoption scope."""
    proposal = agent_guidance.proposal(root, state)
    state["artifacts"]["agentGuidanceProposal"] = agent_guidance.PROPOSAL_FILE
    state["artifacts"]["agentGuidanceData"] = agent_guidance.RESULT_FILE
    state["agentGuidance"] = proposal
    if not (approve or agent_guidance.authorize(root, state)):
        _stage(state, "agent_guidance", AWAITING,
               "The instructions are proposed but existing instruction files are not modified without approval.",
               evidence=agent_guidance.PROPOSAL_FILE)
        _next(state, "Review the proposed AI agent instructions",
              "python3 tools/acima.py adoption guidance --root . --approve",
              approval=True, writes=True,
              why="Updating repository instructions changes future agent behavior and may alter user-authored guidance.",
              done="The owner approves the generated instruction update; existing content remains preserved.")
        _save(root, state)
        return None
    result = agent_guidance.apply(root, state)
    validation = result.get("validation") or {}
    good = validation.get("status") == "valid" and result.get("preservedExisting", True)
    _stage(state, "agent_guidance",
           COMPLETE if good else BLOCKED,
           "Generated agent instructions: %s; preserved existing content: %s; validation: %s." %
           (result.get("status"), result.get("preservedExisting"), validation.get("status")),
           evidence={agent_guidance.RESULT_FILE: True, "primary": result.get("primaryFile")})
    state["agentGuidance"] = result
    state["decisions"].append({"id": "agent-guidance", "decision": "applied" if good else "blocked",
                               "by": state.get("authorizedBy") or state.get("mode"), "on": _today(),
                               "basis": "generated from the approved map and actual enforcement record"})
    _save(root, state)
    return result


def remediate(root: Path, choice: str, *, selected: list[str] | None = None,
              approved_by: str = "", confirm: bool = False,
              confirm_scope: bool = False, confirm_implementation: bool = False,
              maturity_choice: str | None = None) -> dict:
    """Record and execute the final none/selected/all remediation decision."""
    root = root.resolve()
    state = _load(root)
    if choice not in ("none", "selected", "all"):
        raise WorkflowError("remediation choice must be none, selected, or all")
    if state["stages"].get("ci", {}).get("status") not in (COMPLETE, BLOCKED, NOT_APPLICABLE):
        raise WorkflowError("CI integration must be decided before immediate remediation")
    plan_path = root / REMEDIATION_PLAN
    plan = _read_json(plan_path) if plan_path.is_file() else write_remediation_plan(root, state)
    if state["stages"].get("remediation", {}).get("status") == COMPLETE:
        raise WorkflowError("immediate remediation was already decided")
    before = _read_json(root / VERIFICATION_FILE) if (root / VERIFICATION_FILE).is_file() else {}
    items = plan.get("recommendations") or []
    if choice != "none" and plan.get("maturity", {}).get("mode") not in ("greenfield", "brownfield"):
        if maturity_choice not in ("greenfield", "brownfield"):
            _stage(state, "remediation", AWAITING,
                   "The repository maturity is ambiguous; classify it before authorizing source changes.",
                   evidence=REMEDIATION_PLAN)
            _next(state, "Confirm whether this is greenfield or brownfield work",
                  "Repeat remediate with --maturity-choice greenfield|brownfield after reviewing the evidence.",
                  approval=True, writes=True,
                  why="The confirmation and risk requirements differ by maturity.",
                  done="The owner classifies the application and the plan is refreshed.")
            _save(root, state)
            return state
        plan.setdefault("maturity", {})["mode"] = maturity_choice
        plan["maturity"]["classificationBasis"] = "owner-confirmed"
        _write_json(root, REMEDIATION_PLAN, plan)
    selected = list(dict.fromkeys(selected or []))
    if choice == "selected" and not selected:
        raise WorkflowError("selected remediation needs at least one recommendation id")
    if choice == "none":
        chosen = []
        status = "declined"
    elif choice == "all":
        chosen = [item for item in items if item.get("status") == "ready"]
        status = "selected"
    else:
        known = {item.get("id"): item for item in items}
        unknown = [item for item in selected if item not in known]
        if unknown:
            raise WorkflowError("unknown remediation recommendation(s): %s" % ", ".join(unknown))
        chosen = [known[item] for item in selected]
        status = "selected"
    risk = _remediation_risk(chosen, plan.get("maturity") or {"mode": "unknown"})
    if choice != "none" and risk.get("requiresTwoConfirmations"):
        remediation_state = state.setdefault("remediation", {})
        if not remediation_state.get("scopeAcknowledged"):
            if not confirm_scope:
                remediation_state.update({"choice": choice, "selected": selected,
                                          "risk": risk, "scopeAcknowledged": False})
                _stage(state, "remediation", AWAITING,
                       "A large brownfield remediation needs a first acknowledgement of scope and risk.",
                       evidence=REMEDIATION_PLAN)
                _next(state, "Acknowledge the large brownfield remediation scope",
                      "Provide --confirm-scope, then review the final scope and provide --confirm-implementation.",
                      approval=True, writes=True,
                      why="The affected files, compatibility boundaries and regression risk are substantial.",
                      done="The owner acknowledges the disclosed scope and then separately authorizes implementation.")
                _save(root, state)
                return state
            remediation_state["scopeAcknowledged"] = True
            _stage(state, "remediation", AWAITING,
                   "Scope acknowledged. A second, distinct confirmation is required before implementation.",
                   evidence=REMEDIATION_PLAN)
            _next(state, "Authorize the final remediation scope",
                  "Repeat remediate with --confirm-implementation after reviewing the final scope.",
                  approval=True, writes=True,
                  why="A single acknowledgement must not silently authorize a large brownfield change.",
                  done="A second explicit confirmation authorizes the disclosed implementation scope.")
            _save(root, state)
            return state
        if not confirm_implementation:
            _stage(state, "remediation", AWAITING,
                   "Scope acknowledged; the second explicit implementation confirmation is still missing.",
                   evidence=REMEDIATION_PLAN)
            _next(state, "Provide the second explicit remediation confirmation",
                  "Repeat remediate with --confirm-implementation.",
                  approval=True, writes=True,
                  why="Two distinct affirmative confirmations are required for large brownfield work.",
                  done="The second confirmation explicitly authorizes the final scope.")
            _save(root, state)
            return state
    elif choice != "none" and not (confirm or confirm_scope or confirm_implementation):
        _stage(state, "remediation", AWAITING,
               "The selected remediation scope needs one affirmative confirmation.",
               evidence=REMEDIATION_PLAN)
        _next(state, "Confirm the selected remediation scope",
              "Repeat remediate with --confirm after reviewing the affected files.",
              approval=True, writes=True,
              why="No application source changes without an explicit scope confirmation.",
              done="The owner confirms the bounded remediation scope.")
        _save(root, state)
        return state
    if (state["repository"].get("applicationRevision")
            and state["repository"].get("applicationRevision") != _application_revision(root)):
        _stage(state, "remediation", BLOCKED,
               "The application changed since assessment; findings must be revalidated before applying fixes.",
               evidence=REMEDIATION_PLAN)
        state["blockers"].append("remediation blocked by a changed application revision")
        _next(state, "Revalidate the remediation findings",
              "Run a fresh adoption assessment and review the changed findings before authorizing fixes.",
              approval=True, writes=True,
              why="Applying stale recommendations could overwrite or misdiagnose changed code.",
              done="The changed findings are revalidated and the remediation plan is refreshed.")
        _save(root, state)
        return state
    config = _read_json(root / CONFIG_NAME) if (root / CONFIG_NAME).is_file() else {}
    if not config:
        _stage(state, "remediation", BLOCKED, "No authoritative config is available.")
        state["blockers"].append("remediation requires an approved module map")
        _save(root, state)
        return state
    changes, failures = [], []
    chosen_ids = [item.get("id") for item in chosen]
    deferred = [item.get("id") for item in items
                if item.get("id") not in chosen_ids or item.get("status") != "ready"]
    if choice == "all":
        for item in items:
            if item.get("status") != "ready":
                failures.append({"id": item.get("id"), "status": "manual",
                                 "reason": item.get("reason") or "No deterministic change."})
    for item in chosen:
        if item.get("status") != "ready":
            failures.append({"id": item.get("id"), "status": "manual",
                             "reason": item.get("reason") or "No deterministic change."})
            continue
        result = _apply_changes(root, item)
        if result.get("status") == "applied":
            changes.append({"id": item.get("id"), "files": result.get("files", [])})
        else:
            failures.append({"id": item.get("id"), "status": "failed", "reason": result.get("reason")})
    verification = _fresh_assessment(root, state, config)
    outcome = ("declined" if choice == "none" else "complete" if not failures else
               "partial" if changes else "blocked")
    decision = {
        "schemaVersion": 1, "choice": choice, "status": outcome,
        "approvedBy": approved_by or "Repository owner", "decidedOn": _today(),
        "selected": chosen_ids,
        "changed": changes, "failures": failures, "deferred": deferred,
        "recommendations": plan.get("recommendations", []),
        "before": {"positive": before.get("positive"), "negative": before.get("negative")},
        "risk": risk, "maturity": plan.get("maturity"),
        "verification": VERIFICATION_FILE,
        "claim": ("No application source was changed." if not changes else
                  "Only the selected recommendations with deterministic changes were applied; manual or failed items remain outstanding."),
    }
    _write_json(root, REMEDIATION_RESULT, decision)
    state["artifacts"]["remediationResult"] = REMEDIATION_RESULT
    state["remediation"].update({"choice": choice, "selected": chosen_ids, "deferred": deferred,
                                 "result": REMEDIATION_RESULT, "outcome": outcome, "risk": risk})
    _stage(state, "remediation", COMPLETE if outcome in ("declined", "complete") else BLOCKED,
           "Decision: %s; outcome: %s; changed %s file(s); %s failed/manual item(s)." %
           (choice, outcome, len(changes), len(failures)), evidence=REMEDIATION_RESULT)
    _stage(state, "verification", COMPLETE if verification.get("status") == "verified" else BLOCKED,
           "Fresh post-remediation assessment: %s." % verification.get("status"), evidence=VERIFICATION_FILE)
    guidance = _apply_agent_guidance(root, state)
    if guidance is None:
        _save(root, state)
        return state
    _stage(state, "handoff", COMPLETE, "The handoff includes remediation and AI guidance outcomes.", evidence=HANDOFF_FILE)
    _handoff(root, state, verification)
    # These source edits were explicitly authorized; measure later edits from the new baseline.
    state["repository"]["applicationRevision"] = _application_revision(root)
    state["decisions"].append({"id": "remediation", "decision": choice, "by": approved_by or "Repository owner",
                               "on": _today(), "outcome": outcome})
    if outcome == "declined":
        _next(state, "No immediate fixes were applied",
              "Review the deferred recommendations and schedule reassessment when ownership changes.",
              why="The owner preserved the implementation and chose not to remediate now.",
              done="The owner later selects a remediation scope or changes the architecture.")
    elif failures:
        _next(state, "Review the blocked or manual remediation items",
              "Inspect docs/acima/remediation-result.json; implement or revalidate the remaining items.",
              approval=True, writes=True,
              why="A partial or blocked fix set must not be reported as complete.",
              done="Each selected item has an implemented or explicitly deferred disposition.")
    else:
        _next(state, "No further action in the authorized scope",
              "Review the handoff and schedule reassessment when ownership or enforcement changes.",
              why="Selected fixes were applied and verified against a fresh assessment.",
              done="Ownership, contracts or enforcement changes; then reassess.")
    _save(root, state)
    return state


def guidance(root: Path, *, approve: bool = False) -> dict:
    """Approve and apply generated agent instructions, then write the final handoff."""
    root = root.resolve()
    state = _load(root)
    if state["stages"].get("agent_guidance", {}).get("status") == COMPLETE:
        return state
    if state["stages"].get("remediation", {}).get("status") not in (COMPLETE, NOT_APPLICABLE):
        raise WorkflowError("decide immediate remediation before applying agent guidance")
    result = _apply_agent_guidance(root, state, approve=approve)
    if result is None:
        return state
    verification = _read_json(root / VERIFICATION_FILE) if (root / VERIFICATION_FILE).is_file() else {}
    _stage(state, "handoff", COMPLETE, "The handoff includes the AI guidance validation.", evidence=HANDOFF_FILE)
    _handoff(root, state, verification)
    if state["stages"].get("agent_guidance", {}).get("status") == COMPLETE:
        _next(state, "No further action in the authorized scope",
              "Review the handoff and refresh agent guidance when the map, enforcement or CI changes.",
              why="The instructions were generated from the approved architecture and validated against the actual artifacts.",
              done="Ownership, enforcement, CI or adoption decisions change; then refresh the guidance.")
    else:
        _next(state, "Resolve the AI guidance validation problem",
              "Inspect .acima/agent-guidance.json and docs/architecture/acima; correct the missing or stale reference.",
              approval=True, writes=True,
              why="Invalid or incomplete agent guidance must not be presented as a completed adoption deliverable.",
              done="The primary instructions and support references validate against the repository.")
    _save(root, state)
    return state


def _handoff(root: Path, state: dict, verification: dict) -> str:
    stages = _summary(state)["stages"]
    remediation = _read_json(root / REMEDIATION_RESULT) if (root / REMEDIATION_RESULT).is_file() else {}
    lines = [
        "# ACIMA adoption handoff — %s" % root.name,
        "",
        "## Adoption outcome",
        "",
        "Mode: **%s**. The final workflow state is **%s**." %
        (state["mode"], "verified" if verification.get("status") == "verified" else "incomplete"),
        "",
        "## Module map",
        "",
        "The approved map is recorded in `%s`; approval provenance is in `%s`." %
        (CONFIG_NAME, APPROVAL_FILE),
        "",
        "## Changes implemented",
        "",
    ]
    for name, value in state.get("artifacts", {}).items():
        lines.append("- %s: `%s`" % (name, value))
    guidance = state.get("agentGuidance") or {}
    guidance_validation = guidance.get("validation") or {}
    lines += ["", "## AI agent guidance", "",
              "- Primary instruction file: `%s`." % (guidance.get("primaryFile") or "not recorded"),
              "- Support files: `%s`." % "`, `".join(guidance.get("supportFiles") or []),
              "- Validation: %s; existing content preserved: %s." %
              (guidance_validation.get("status") or "not recorded", guidance.get("preservedExisting")),
              "- Agent behavior is not guaranteed by file validation; representative tasks remain a manual evaluation.",
              "", "## Immediate remediation", "",
              "- Decision: %s" % (remediation.get("choice") or "not recorded"),
              "- Outcome: %s" % (remediation.get("status") or "not recorded"),
              "- Changed files: %s" % (len(remediation.get("changed") or [])),
              "- Remaining manual or failed items: %s" % (len(remediation.get("failures") or [])),
              "", "## Verification", "",
              "- Positive enforcement: %s" % verification.get("positive", {}).get("status"),
              "- Controlled negative probe: %s" % verification.get("negative", {}).get("status"),
              "- CI: %s" % (verification.get("ci", {}).get("status") or "not configured"),
              "- Requirements without automated evidence remain unverified; this handoff is not a conformance claim.",
              "", "## Run the checks", "",
              "```bash",
              verification.get("positive", {}).get("command") or "No executable command was generated.",
              "```", "",
              "## Reassess when", "",
              "- module ownership, contracts or dependencies change;",
              "- a new module or composition boundary is introduced;",
              "- data/configuration ownership or architectural enforcement changes;",
              "- a significant refactoring lands.",
              "", "## Cadence", "",
              "No universal frequency is imposed. Reassess on the triggers above and at the team's normal architecture review cadence.",
              "", "## Limitations", ""]
    lines += ["- " + item for item in verification.get("limitations", [])] or ["- None recorded."]
    lines += ["", "This workflow did not commit, push, deploy or release."]
    _write(root, HANDOFF_FILE, "\n".join(lines) + "\n")
    state["artifacts"]["handoff"] = HANDOFF_FILE
    return HANDOFF_FILE


def _apply(root: Path, state: dict) -> dict:
    config_path = root / CONFIG_NAME
    if not config_path.is_file():
        _stage(state, "implementation", BLOCKED, "No authoritative config is present.",
               next_action="Approve the module-map decisions first.")
        state["blockers"].append("module map is not approved")
        _save(root, state)
        return state
    config = _read_json(config_path)
    _stage(state, "implementation", IN_PROGRESS, "Writing the executable enforcement artifacts.")
    enforcement = _write_enforcement(root, state, config)
    if enforcement.get("status") == "blocked":
        _stage(state, "implementation", BLOCKED, enforcement.get("reason", "Enforcement could not be written."))
        state["blockers"].append("enforcement file collision")
        _save(root, state)
        return state
    _stage(state, "implementation", COMPLETE, "The enforcer, configuration, waiver file and test record exist.",
           evidence={ENFORCEMENT_FILE: True, ARCH_TESTS_FILE: True})

    command = ((enforcement.get("enforcer") or {}).get("command"))
    _stage(state, "architecture_tests", IN_PROGRESS, "Running the generated positive and negative checks.")
    verification = _verify(root, state, config)
    _stage(state, "architecture_tests",
           COMPLETE if verification.get("status") == "verified" else BLOCKED,
           "Positive enforcement: %s; controlled violation: %s." %
           (verification.get("positive", {}).get("status"),
            verification.get("negative", {}).get("status")),
           evidence=VERIFICATION_FILE)
    if verification.get("status") != "verified":
        state["blockers"].append("architectural enforcement verification did not pass")
        _save(root, state)
        return state
    ci = _integrate_ci(root, state, command)
    _stage(state, "ci", COMPLETE if ci.get("status") in ("configured", "already_present", "no_provider",
                                                         "manual_instructions") else BLOCKED,
           ci.get("claim", "No CI claim recorded."), evidence=CI_FILE)
    guidance_proposal = agent_guidance.proposal(root, state)
    state["artifacts"]["agentGuidanceProposal"] = agent_guidance.PROPOSAL_FILE
    state["artifacts"]["agentGuidanceData"] = agent_guidance.RESULT_FILE
    state["agentGuidance"] = guidance_proposal
    _stage(state, "agent_guidance", IN_PROGRESS,
           "Proposed repository instructions were generated; they will be applied after remediation and verification.",
           evidence=agent_guidance.PROPOSAL_FILE)
    write_remediation_plan(root, state)
    _stage(state, "remediation", AWAITING,
           "Enforcement and CI are complete. Choose none, selected, or all recommended fixes.",
           evidence=REMEDIATION_PLAN)
    _stage(state, "verification", IN_PROGRESS,
           "Final verification follows the immediate-remediation decision.",
           evidence=VERIFICATION_FILE)
    _next(state, "Choose immediate remediation: none, selected, or all",
          "python3 tools/acima.py adoption remediate --root . --choice none|selected|all",
          approval=True, writes=True,
          why="The final remediation decision is separate from CI and must be made after seeing its outcome.",
          done="The owner records none, selected IDs, or all; authorized source changes are implemented and freshly verified.")
    _save(root, state)
    return state


def start(root: Path, mode: str, *, authorize_full: bool = False,
          reviewer: str | None = None) -> dict:
    root = root.resolve()
    if not root.is_dir():
        raise WorkflowError("project does not exist: %s" % root)
    if mode not in MODES:
        raise WorkflowError("mode must be guided or full")
    if mode == "full" and not authorize_full:
        raise WorkflowError("full automation requires the explicit --authorize-full flag")
    if mode == "full" and not (reviewer or "").strip():
        reviewer = "Full automation consent"
    state_path = root / STATE_FILE
    if state_path.is_file():
        existing = _load(root)
        if existing.get("mode") != mode:
            raise WorkflowError("the repository already has a %s workflow; resume it or start a new "
                                "engagement explicitly" % existing.get("mode"))
        return continue_workflow(root)
    state = _new_state(root, mode, reviewer)
    if mode == "full":
        state["authorized"] = True
        state["authorizedBy"] = reviewer or "Full automation consent"
        state["authorizedOn"] = _today()
    preflight = _run_preflight(root)
    if preflight.get("payload"):
        _write_json(root, PREFLIGHT_FILE, preflight["payload"])
        state["artifacts"]["preflight"] = PREFLIGHT_FILE
    blockers = list((preflight.get("payload") or {}).get("blockers") or [])
    if preflight.get("exitCode") == 0 and not blockers:
        _stage(state, "preflight", COMPLETE,
               "Preflight passed for %s adoption." % mode,
               evidence={"mode": mode, "explicitAuthorization": mode == "full",
                         "preflight": PREFLIGHT_FILE})
    else:
        detail = ("Preflight blocked adoption: %s." % ", ".join(blockers)
                  if blockers else
                  "Preflight did not complete: %s" % (preflight.get("error") or "no valid result"))
        _stage(state, "preflight", BLOCKED, detail,
               evidence={"mode": mode, "explicitAuthorization": mode == "full",
                         "preflight": PREFLIGHT_FILE})
        state["blockers"].extend(blockers or ["preflight did not complete"])
    _stage(state, "discovery", IN_PROGRESS, "Discovering repository ownership, contracts and enforcement.")
    try:
        module_map = discover_module_map(root)
    except (ModuleMapError, OSError) as error:
        _stage(state, "discovery", BLOCKED, "Module-map discovery failed: %s" % error)
        state["blockers"].append("discovery failed")
        _next(state, "Complete discovery manually", "Repair the discovery error before proceeding.",
              why="No proposal can be generated from an unreadable repository.", done="Discovery returns a proposal or authoritative map.")
        _save(root, state)
        return state
    _stage(state, "discovery", COMPLETE,
           "Discovery found %s candidate module(s)." %
           len((module_map.get("proposal") or {}).get("modules", [])),
           evidence={"proposalId": module_map.get("proposalId"),
                     "authoritative": module_map.get("authoritativeMap", {}).get("status")})
    _stage(state, "assessment", IN_PROGRESS,
           "The mandatory 55-requirement qualitative review has not been recorded. "
           "Discovery and ownership decisions may continue independently, but no complete "
           "assessment is claimed and ownership-dependent checks remain qualified.",
           evidence={"catalog": "tools/acima-spec/rules.json", "requiredRules": 55})
    if module_map.get("proposal"):
        _write_json(root, PROPOSAL_JSON, module_map.get("proposal"))
        state["artifacts"]["moduleMapProposal"] = PROPOSAL_JSON
    adopted = False
    reason = ""
    if mode == "full":
        adopted, reason = _adopt_map(root, state, module_map, reviewer or "Full automation consent")
    elif module_map.get("authoritativeMap", {}).get("status") == "complete":
        adopted, reason = True, "An authoritative map already covers all production source."
    if adopted:
        _stage(state, "module_map", COMPLETE, reason,
               evidence={"config": CONFIG_NAME, "approval": APPROVAL_FILE})
    elif mode == "guided":
        _stage(state, "module_map", AWAITING,
               "A proposal is ready; individual module and recommendation decisions are not approved.",
               evidence=PROPOSAL_JSON)
        _next(state, "Review the proposed module map",
              "python3 conformance/adoption_workflow.py approve --project . --map-decisions <review.json>",
              approval=True, writes=True,
              why="Inferred ownership must not become authoritative without explicit review.",
              done="The review approves every boundary and essential recommendation, or the owner defers it.")
    else:
        _stage(state, "module_map", BLOCKED,
               "Full automation paused: %s." % (reason or "ownership is not sufficiently supported"),
               evidence=PROPOSAL_JSON)
        state["blockers"].append(reason or "module map could not be approved automatically")
        _next(state, "Resolve the ownership decision",
              "Review the module-map proposal; use `approve` with explicit decisions.",
              approval=True, writes=True,
              why="The workflow must not invent architectural intent where evidence is inadequate.",
              done="The map is approved or a supported boundary is supplied.")
    _write_proposal(root, module_map, state)
    if mode == "guided":
        _stage(state, "adoption_proposal", AWAITING,
               "The adoption proposal is generated and waits for scope approval.",
               evidence=ADOPTION_PROPOSAL)
        if state["stages"].get("module_map", {}).get("status") == AWAITING:
            _next(state, "Review the proposed module map",
                  "python3 conformance/adoption_workflow.py approve --project . --map-decisions <review.json>",
                  approval=True, writes=True,
                  why="Inferred ownership must not become authoritative before the map review.",
                  done="The map review approves a complete map; the adoption scope is asked for separately.")
        else:
            _next(state, "Review the adoption proposal",
                  "python3 conformance/adoption_workflow.py approve --project . --scope <scope.json>",
                  approval=True, writes=True,
                  why="The proposal is complete, but implementation and CI are consequential changes.",
                  done="The owner approves a scope with concrete objectives.")
        _save(root, state)
        return state
    if not adopted:
        _stage(state, "adoption_proposal", COMPLETE,
               "The proposal is generated; it remains blocked on ownership.",
               evidence=ADOPTION_PROPOSAL)
        _save(root, state)
        return state
    _write_scope(root, state)
    _stage(state, "adoption_proposal", COMPLETE,
           "The proposal and the explicit full-automation scope are recorded.",
           evidence={ADOPTION_PROPOSAL: True, SCOPE_FILE: True})
    state["decisions"].append({"id": "adoption-scope", "decision": "accepted",
                               "by": state.get("authorizedBy"), "on": _today(),
                               "basis": "explicit full-automation pre-flight authorization"})
    _save(root, state)
    return _apply(root, state)


def approve(root: Path, *, map_decisions: Path | None = None,
            scope: Path | None = None, reviewer: str | None = None) -> dict:
    root = root.resolve()
    state = _load(root)
    if map_decisions:
        module_map = _read_json(root / PROPOSAL_JSON) if (root / PROPOSAL_JSON).is_file() else None
        if module_map is not None:
            # The saved proposal is the inner proposal; discover wraps it for apply_review.
            wrapper = {"proposal": module_map, "proposalId": module_map.get("proposalId")}
            decisions = load_review(map_decisions)
            result = apply_review(wrapper, decisions, root=root)
            _write_json(root, APPROVAL_FILE, result)
            if result.get("status") == "approved":
                existing = _read_json(root / CONFIG_NAME) if (root / CONFIG_NAME).is_file() else None
                config = build_config(wrapper, result, existing=existing, language=_language(root))
                _write_json(root, CONFIG_NAME, config)
                state["artifacts"]["moduleMapApproval"] = APPROVAL_FILE
                state["artifacts"]["moduleMap"] = CONFIG_NAME
                state["decisions"].append({"id": "module-map", "decision": "accepted",
                                           "by": reviewer or decisions.get("reviewer"),
                                           "on": _today(), "proposalId": module_map.get("proposalId")})
                _stage(state, "module_map", COMPLETE, "The owner-approved map is authoritative.",
                       evidence={"config": CONFIG_NAME, "approval": APPROVAL_FILE})
            else:
                _stage(state, "module_map", AWAITING, "The review is %s; no config was written." %
                       result.get("status"), evidence=APPROVAL_FILE)
        else:
            raise WorkflowError("no module-map proposal is available at %s" % PROPOSAL_JSON)
    if scope:
        if not (root / CONFIG_NAME).is_file():
            raise WorkflowError("an adoption scope cannot be approved before an authoritative module map exists")
        approval = _read_json(root / APPROVAL_FILE) if (root / APPROVAL_FILE).is_file() else {}
        if (approval.get("status") != "approved"
                or not (approval.get("approval") or {}).get("canWriteConfig")):
            raise WorkflowError("the module map is not approved and cannot authorize an implementation scope")
        document = _read_json(scope)
        for key in ("approvedBy", "approvedOn", "objectives"):
            if key not in document:
                raise WorkflowError("scope is missing %s" % key)
        if not str(document.get("approvedBy", "")).strip():
            raise WorkflowError("scope.approvedBy is required")
        try:
            date.fromisoformat(str(document.get("approvedOn")))
        except ValueError as error:
            raise WorkflowError("scope.approvedOn must be a YYYY-MM-DD date") from error
        objectives = document.get("objectives")
        if not isinstance(objectives, list) or not objectives:
            raise WorkflowError("scope.objectives must contain at least one objective")
        for objective in objectives:
            if not isinstance(objective, dict) or not objective.get("id"):
                raise WorkflowError("every scope objective needs an id")
            if objective.get("disposition") not in {"required", "approved", "deferred", "optional", "declined"}:
                raise WorkflowError("scope objective %s has an unknown disposition" % objective.get("id"))
        _write_json(root, SCOPE_FILE, document)
        state["artifacts"]["scope"] = SCOPE_FILE
        state["decisions"].append({"id": "adoption-scope", "decision": "accepted",
                                   "by": document.get("approvedBy"), "on": _today()})
        _stage(state, "adoption_proposal", COMPLETE,
               "The authoritative map and owner-approved implementation scope are recorded.",
               evidence={ADOPTION_PROPOSAL: True, SCOPE_FILE: True, CONFIG_NAME: True})
    if (root / CONFIG_NAME).is_file() and (root / SCOPE_FILE).is_file():
        _save(root, state)
        return _apply(root, state)
    if state["stages"].get("module_map", {}).get("status") == COMPLETE:
        _stage(state, "adoption_proposal", AWAITING,
               "The map is approved; the adoption proposal still needs a scope decision.",
               evidence=ADOPTION_PROPOSAL)
        _next(state, "Approve the adoption scope",
              "python3 conformance/adoption_workflow.py approve --project . --scope <scope.json>",
              approval=True, writes=True,
              why="Approving a map does not authorize application or CI changes.",
              done="The owner approves local enforcement and the other desired objectives.")
    _save(root, state)
    return state


def continue_workflow(root: Path) -> dict:
    root = root.resolve()
    state = _load(root)
    if state["stages"].get("handoff", {}).get("status") == COMPLETE:
        return state
    if state["stages"].get("agent_guidance", {}).get("status") == AWAITING:
        _next(state, "Review the proposed AI agent instructions",
              "python3 tools/acima.py adoption guidance --root . --approve",
              approval=True, writes=True,
              why="The instruction update is a separate consequential change to future agent behavior.",
              done="The owner approves the generated instructions and their validation passes.")
        _save(root, state)
        return state
    if state["stages"].get("remediation", {}).get("status") == AWAITING:
        _next(state, "Choose immediate remediation: none, selected, or all",
              "python3 tools/acima.py adoption remediate --root . --choice none|selected|all",
              approval=True, writes=True,
              why="The final remediation decision follows CI and must not be inferred from adoption consent.",
              done="The owner records none, selected IDs, or all; authorized changes are then verified.")
        _save(root, state)
        return state
    if (root / CONFIG_NAME).is_file() and (root / SCOPE_FILE).is_file():
        return _apply(root, state)
    if state["stages"].get("module_map", {}).get("status") in (AWAITING, BLOCKED):
        _next(state, "Review the proposed module map",
              "python3 conformance/adoption_workflow.py approve --project . --map-decisions <review.json>",
              approval=True, writes=True,
              why="No ownership is authoritative yet.",
              done="The map review approves a complete map.")
    elif state["stages"].get("adoption_proposal", {}).get("status") == AWAITING:
        _next(state, "Approve the adoption scope",
              "python3 conformance/adoption_workflow.py approve --project . --scope <scope.json>",
              approval=True, writes=True,
              why="The map is approved, but implementation and CI still need a scope.",
              done="The owner approves the proposal objectives.")
    _save(root, state)
    return state


def status(root: Path) -> dict:
    state = _load(root)
    summary = _summary(state)
    current = next((stage for stage in summary["stages"]
                    if stage["status"] not in (COMPLETE, NOT_APPLICABLE)), None)
    summary["currentStage"] = current
    guidance = summary.get("agentGuidance") or {}
    if guidance.get("status") == "applied":
        stale, changed = agent_guidance.stale(root, guidance)
        guidance["stale"] = stale
        guidance["staleSources"] = changed
        if stale:
            summary["staleWarning"] = ("AI agent guidance references changed sources: %s. "
                                       "Refresh it before treating the instructions as current." %
                                       ", ".join(changed))
    remediation = summary.get("remediation") or {}
    result_path = remediation.get("result")
    if result_path and (root / result_path).is_file():
        remediation["resultData"] = _read_json(root / result_path)
    baseline = state.get("repository", {}).get("applicationRevision")
    summary["stale"] = bool(baseline and baseline != _application_revision(root))
    if summary["stale"]:
        summary["staleWarning"] = ("The repository revision changed since the workflow began; "
                                   "reassess the affected artifacts before treating them as current.")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ACIMA end-to-end adoption workflow")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("start", "status", "approve", "apply", "continue", "remediate", "guidance"):
        command = sub.add_parser(name)
        command.add_argument("--project", default=".")
        command.add_argument("--format", choices=("json", "text"), default="json")
        if name == "start":
            command.add_argument("--mode", choices=MODES, required=True)
            command.add_argument("--authorize-full", action="store_true", dest="authorize_full")
            command.add_argument("--reviewer", default=None)
        elif name == "approve":
            command.add_argument("--map-decisions", default=None)
            command.add_argument("--scope", default=None)
            command.add_argument("--reviewer", default=None)
        elif name == "guidance":
            command.add_argument("--approve", action="store_true")
        elif name == "remediate":
            command.add_argument("--choice", choices=("none", "selected", "all"), required=True)
            command.add_argument("--maturity-choice", choices=("greenfield", "brownfield"), default=None)
            command.add_argument("--selected", action="append", default=[])
            command.add_argument("--approved-by", default="Repository owner")
            command.add_argument("--confirm", action="store_true")
            command.add_argument("--confirm-scope", action="store_true", dest="confirm_scope")
            command.add_argument("--confirm-implementation", action="store_true",
                                 dest="confirm_implementation")
    args = parser.parse_args(argv)
    root = Path(args.project).resolve()
    try:
        if args.command == "start":
            result = start(root, args.mode, authorize_full=args.authorize_full,
                           reviewer=args.reviewer)
        elif args.command == "status":
            result = status(root)
        elif args.command == "approve":
            result = approve(root,
                             map_decisions=Path(args.map_decisions) if args.map_decisions else None,
                             scope=Path(args.scope) if args.scope else None,
                             reviewer=args.reviewer)
        elif args.command == "apply":
            result = _apply(root, _load(root))
        elif args.command == "guidance":
            result = guidance(root, approve=args.approve)
        elif args.command == "remediate":
            result = remediate(root, args.choice, selected=args.selected,
                               approved_by=args.approved_by, confirm=args.confirm,
                               confirm_scope=args.confirm_scope,
                               confirm_implementation=args.confirm_implementation,
                               maturity_choice=args.maturity_choice)
        else:
            result = continue_workflow(root)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if not result.get("blockers") else 1
    except (WorkflowError, ModuleMapError, OSError, ValueError) as error:
        print("adoption_workflow: %s" % error, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
