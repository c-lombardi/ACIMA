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
    Requires ``--authorize-full``.  Prepare the complete adoption package, then wait for a
    consolidated user review and explicit scope approval before applying selected stages.

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
from qualitative_review import ReviewValidationError, load_and_validate_review  # noqa: E402
from adoption_reports import AdoptionReportError, render_proposal_report, report_digest  # noqa: E402

STATE_FILE = ".acima/adoption-workflow.json"
PREFLIGHT_FILE = ".acima/preflight.json"
PROPOSAL_JSON = ".acima/module-map.proposal.json"
OWNER_MAP_REVIEW_FILE = "docs/acima/module-map-decisions.json"
SCOPE_FILE = ".acima/adoption-scope.json"
ADOPTION_PROPOSAL = "docs/acima/adoption-proposal.md"
ADOPTION_PROPOSAL_JSON = "docs/acima/adoption-proposal.json"
ADOPTION_NOTIFICATIONS_PROPOSAL = "docs/acima/adoption-notifications-proposal.json"
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
    "proposal_report", "implementation", "architecture_tests", "ci", "remediation",
    "verification", "agent_guidance", "adoption_notifications", "handoff",
)
STAGE_LABEL = {
    "preflight": "Pre-flight authorization",
    "discovery": "Repository discovery",
    "assessment": "Comprehensive assessment",
    "module_map": "Module map",
    "adoption_proposal": "Adoption proposal",
    "proposal_report": "HTML proposal review",
    "implementation": "Enforcement implementation",
    "architecture_tests": "Architectural tests",
    "ci": "CI integration",
    "remediation": "Immediate remediation",
    "verification": "Fresh verification",
    "agent_guidance": "AI agent guidance",
    "adoption_notifications": "ACIMA adoption notifications",
    "handoff": "Final handoff",
}
COMPLETE = "complete"
IN_PROGRESS = "in_progress"
AWAITING = "awaiting_approval"
BLOCKED = "blocked"
DEFERRED = "deferred"
DECLINED = "declined"
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


def _walk_files(root: Path, skip: set[str] | None = None):
    """Walk files once, pruning excluded directories before descent."""
    skipped = set(skip or {".git", ".acima"})
    for current, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(name for name in dirnames if name not in skipped)
        for name in sorted(filenames):
            if name in skipped:
                continue
            path = Path(current) / name
            if path.is_file():
                yield path


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
                status = subprocess.run(["git", "-C", str(root), "status", "--porcelain", "--untracked-files=all"],
                                        capture_output=True, text=True, timeout=15)
                diff = subprocess.run(["git", "-C", str(root), "diff", "--binary", "HEAD"],
                                      capture_output=True, text=False, timeout=30)
                branch = subprocess.run(["git", "-C", str(root), "branch", "--show-current"],
                                        capture_output=True, text=True, timeout=15)
                untracked = subprocess.run(
                    ["git", "-C", str(root), "ls-files", "--others", "--exclude-standard"],
                    capture_output=True, text=True, timeout=15)
                tree_parts = [diff.stdout if diff.returncode == 0 else b""]
                for relative in (untracked.stdout.splitlines() if untracked.returncode == 0 else []):
                    if relative.replace("\\", "/") in {STATE_FILE, SCOPE_FILE}:
                        continue
                    candidate = root / relative
                    if candidate.is_file():
                        tree_parts.extend([relative.encode("utf-8"), candidate.read_bytes()])
                tree_digest = hashlib.sha256(b"\\0".join(tree_parts)).hexdigest()
                return {
                    "head": result.stdout.strip(),
                    "dirty": bool(status.stdout.strip()),
                    "branch": branch.stdout.strip() if branch.returncode == 0 else None,
                    "workingTree": tree_digest,
                }
    except (OSError, subprocess.SubprocessError):
        pass
    tracked = []
    workflow_owned = {
        CONFIG_NAME, "tools/acima_arch.py", "tools/acima-arch.mjs",
        "tools/Acima.ArchTests/Acima.ArchTests.csproj",
        "tools/Acima.ArchTests/Program.cs",
        ".github/workflows/acima.yml",
    }
    for path in _walk_files(root, {".git", ".acima"}):
        relative = path.relative_to(root).as_posix()
        if relative.startswith("docs/acima/") or relative in workflow_owned:
            continue
        if relative.startswith("tools/Acima.ArchTests/"):
            continue
        tracked.append("%s:%s" % (relative, hashlib.sha256(path.read_bytes()).hexdigest()))
    digest = hashlib.sha256("\n".join(tracked).encode("utf-8")).hexdigest()
    return {"head": "tree:" + digest[:40], "dirty": False}


def _application_revision(root: Path) -> str:
    """Hash application source and behavior inputs, not workflow/enforcement artifacts."""
    tracked = []
    for path in _walk_files(root, {".git", ".acima"}):
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
    for path in _walk_files(root, {".git", "node_modules", "dist", "build", "target",
                                   "bin", "obj", ".venv", "venv", "tools", "examples",
                                   "docs", ".acima"}):
        relative = path.relative_to(root).as_posix().lower()
        if path.suffix.lower() not in source_suffixes:
            continue
        (tests if ("test" in relative or "spec" in relative) else production).append(relative)
    modules = len((config or {}).get("units") or [])
    manifests = sum(1 for name in ("pyproject.toml", "package.json", "go.mod", "Cargo.toml")
                    for path in _walk_files(root, {".git"}) if path.name == name)
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
    parents = Path(__file__).resolve().parents
    candidates = [ROOT / "skills/acima-adoption/scripts/preflight.py"]
    if len(parents) > 2:
        candidates.append(parents[2] / "scripts/preflight.py")
    if len(parents) > 1:
        candidates.append(parents[1] / "skills/acima-adoption/scripts/preflight.py")
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



def _attach_adoption_notifications_review(state: dict) -> None:
    """Keep the notification proposal visible alongside the primary workflow action."""
    notification = state.get("adoptionNotifications") or {}
    if notification.get("status") != "proposal_prepared" or notification.get("implementationDecision"):
        return
    next_action = state.setdefault("next", {})
    next_action["additionalReview"] = {
        "action": "Review the separate ACIMA adoption-notifications proposal",
        "artifact": ADOPTION_NOTIFICATIONS_PROPOSAL,
        "proposalSha256": notification.get("proposalSha256"),
        "command": "Open %s and decide whether to request a separate implementation plan, defer it, or decline it." % ADOPTION_NOTIFICATIONS_PROPOSAL,
        "approvalRequired": True,
        "writes": False,
        "implementationAuthorized": False,
        "why": "The selected scope authorized proposal preparation only. Notification source, providers, UI and configuration require a second review and exact-path approval.",
    }

def _new_state(root: Path, mode: str, reviewer: str | None) -> dict:
    return {
        "schemaVersion": 1,
        "mode": mode,
        "authorized": mode == "full",
        "authorizedBy": reviewer if mode == "full" else None,
        "authorizedOn": _today() if mode == "full" else None,
        "authorization": ("The user selected automated adoption in pre-flight. This authorizes assessment and preparation only; implementation requires a later, explicit scope approval."
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
    units = (module_map.get("authoritativeMap") or {}).get("units") or []
    if not modules:
        # An authoritative map is already the ownership input; describe its declared units
        # instead of treating the absence of a proposal as absent ownership.
        grouped: dict[str, dict] = {}
        for unit in units:
            if not isinstance(unit, dict) or not unit.get("module"):
                continue
            item = grouped.setdefault(str(unit["module"]), {
                "name": str(unit["module"]), "confidence": "declared",
                "unitRoles": {}, "contracts": {"paths": []},
                "implementation": {"paths": []},
            })
            role = str(unit.get("role") or "unclassified")
            item["unitRoles"].setdefault(role, []).extend(unit.get("paths") or [])
            if role == "contracts":
                item["contracts"]["paths"].extend(unit.get("paths") or [])
            elif role == "implementation":
                item["implementation"]["paths"].extend(unit.get("paths") or [])
        modules = list(grouped.values())
    recommendations = proposal.get("recommendations") or []
    existing_architecture = (
        proposal.get("existingArchitecture")
        or module_map.get("existingArchitecture")
        or {}
    )
    strengths = []
    if existing_architecture.get("paths"):
        strengths.append("Existing architecture or enforcement evidence was found at: %s." %
                         ", ".join(existing_architecture["paths"][:8]))
    contract_modules = [module for module in modules if module.get("contracts", {}).get("paths")]
    if contract_modules:
        strengths.append("%s of %s declared or proposed modules have an identified contract-shaped area "
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
    authoritative_status = (module_map.get("authoritativeMap") or {}).get("status")
    if not required and authoritative_status != "complete":
        required.append({
            "id": "owner-led-ownership-review",
            "title": "Resolve module ownership before enforcement",
            "requirement": "The current evidence does not establish a complete authoritative ownership map.",
            "outcome": "Every production source path has an owner-approved module or explicit non-module disposition.",
            "implementation": "Complete owner-led discovery and review. ACIMA will not infer ownership from project, package or directory layout.",
            "status": "blocked",
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
        "maturity": _maturity(root, {"units": units}),
        "mode": state["mode"],
        "recommendation": "RECOMMENDED_WITH_LIMITATIONS" if modules else "INSUFFICIENT_EVIDENCE",
        "summary": (
            "A complete authoritative module map already exists. Preserve it and evaluate which enforcement, governance and developer-guidance capabilities are still missing."
            if authoritative_status == "complete" else
            ("Adopt the proposed module boundaries incrementally, preserve existing "
             "architecture, and make enforcement executable." if modules else
             "No safe ownership proposal is available; complete owner discovery first.")
        ),
        "existingStrengths": strengths,
        "existingArchitecture": existing_architecture,
        "coverage": proposal.get("coverage") or {
            "sourceFiles": (module_map.get("authoritativeMap") or {}).get("productionFiles", 0),
            "moduleCovered": (module_map.get("authoritativeMap") or {}).get("coveredProduction", 0),
            "classifiedNonModule": (module_map.get("authoritativeMap") or {}).get("classifiedNonModule", 0),
            "unresolvedProduction": len((module_map.get("authoritativeMap") or {}).get("unownedPaths", [])),
        },
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
    if not document["requiredChanges"]:
        if (document.get("moduleMap") or {}).get("status") == "authoritative":
            lines.append("- No module ownership rewrite is proposed. The existing authoritative map is preserved; remaining adoption work is evaluated separately.")
        else:
            lines.append("- No implementation change is proposed from the current discovery evidence. Resolve the outstanding ownership or evidence questions before enforcement.")
        lines.append("")
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
    # This document is a draft for the owner to edit. Nothing is pre-approved,
    # regardless of whether the agent selected guided or automated preparation.
    objectives = [
        {"id": "assessment", "disposition": "required"},
        {"id": "local-enforcement", "disposition": "deferred",
         "reason": "Requires explicit approval after reviewing the exact HTML proposal."},
        {"id": "baseline-waivers", "disposition": "deferred",
         "reason": "Creating waiver state requires a separate owner decision."},
        {"id": "ci-enforcement", "disposition": "deferred",
         "reason": "CI changes require a separate provider-specific approval."},
        {"id": "developer-handoff", "disposition": "deferred",
         "reason": "Changing future agent behavior requires separate approval."},
        {"id": "agent-guidance", "disposition": "deferred",
         "reason": "Existing instruction files are not changed without separate approval."},
        {"id": "adoption-notifications", "disposition": "deferred",
         "reason": "A separate user decision is required; selecting it authorizes proposal preparation only, not notification code."},
        {"id": "source-remediation", "disposition": "deferred",
         "reason": "Application source changes require separate file-scoped approval after remediation review."},
        {"id": "full-conformance", "disposition": "deferred",
         "reason": "Verification evidence is not a full-conformance claim."},
        {"id": "communication-governance", "disposition": "optional"},
    ]
    return {
        "version": 2,
        "approvedBy": "",
        "approvedOn": "",
        "proposal": ADOPTION_PROPOSAL,
        "reportReview": {"status": "not_reviewed"},
        "approvedPaths": [],
        "objectives": objectives,
        "authorization": {
            "mode": state["mode"], "explicit": False,
            "scope": "Draft only. Editing or saving this document does not approve implementation.",
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
        "requirementsWithAutomatedEnforcement": len(
            (_read_json(ROOT / "conformance/coverage.json").get("profiles", {}).get(language) or {}).get("executed", [])
        ),
        "requirementsWithoutAutomatedEnforcement": len(
            (_read_json(ROOT / "conformance/coverage.json").get("profiles", {}).get(language) or {}).get("notExecuted", [])
        ) if language in (_read_json(ROOT / "conformance/coverage.json").get("profiles", {}))
          else len(_read_json(ROOT / "tools/acima-spec/rules.json").get("rules", [])),
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


def _positive_fixture(language: str) -> dict:
    """Run the language's known-compliant reference fixture, isolated from the target."""
    example = ROOT / "examples" / language
    if not example.is_dir():
        return {"status": "unsupported", "reason": "No compliant reference fixture exists for %s." % language}
    commands = {
        "dotnet": ["dotnet", "run", "--project", "tools/Acima.ArchTests", "--",
                   "--root", ".", "--config", "acima.config.json", "--format", "json"],
        "python": [sys.executable, "tools/acima_arch.py", "--root", ".",
                   "--config", "acima.config.json", "--format", "json"],
        "typescript": ["node", "tools/acima-arch.mjs", "--root", ".",
                       "--config", "acima.config.json", "--format", "json"],
        "go": ["go", "run", "./tools/archtest", "--root", ".",
               "--config", "acima.config.json", "--format", "json"],
    }
    command = commands.get(language)
    if not command:
        return {"status": "unsupported", "reason": "No positive-fixture command is defined for %s." % language}
    try:
        with tempfile.TemporaryDirectory(prefix="acima-positive-") as directory:
            fixture = Path(directory)
            shutil.copytree(example, fixture, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns(".git", "bin", "obj", "node_modules", "__pycache__"))
            code, out, err = _run(command, fixture, timeout=300)
    except (OSError, shutil.Error) as error:
        return {"status": "failed", "reason": "Could not prepare the isolated positive fixture: %s" % error}
    try:
        payload = json.loads(out)
    except json.JSONDecodeError:
        return {"status": "failed", "exitCode": code,
                "reason": (err or out or "positive fixture returned invalid JSON")[:500]}
    findings = payload.get("findings")
    valid = (code == 0 and isinstance(payload.get("sourceFiles"), int)
             and payload.get("sourceFiles", 0) > 0 and isinstance(findings, list)
             and len(findings) == 0)
    return {
        "status": "valid" if valid else "failed",
        "exitCode": code,
        "sourceFiles": payload.get("sourceFiles"),
        "findingCount": len(findings) if isinstance(findings, list) else None,
        "command": " ".join(command),
        "evidenceType": "isolated-known-compliant-fixture",
        "reason": None if valid else "The compliant fixture must exit 0, scan source files and report zero findings.",
    }


def _verify(root: Path, state: dict, config: dict) -> dict:
    language = config.get("language") or _language(root)
    item = _enforcer(root, language)
    result = {
        "schemaVersion": 1,
        "status": "not_run",
        "language": language,
        "assessment": {},
        "positive": _positive_fixture(language),
        "targetScan": {"status": "not_run"},
        "negative": {"status": "not_run"},
        "ci": {},
        "limitations": [],
    }
    if item:
        targets = [root / entry["target"] for entry in item["files"]]
        if all(path.exists() for path in targets):
            code, out, err = _run(item["argv"], root, timeout=300)
            try:
                payload = json.loads(out)
            except json.JSONDecodeError:
                result["targetScan"] = {"status": "invalid_output", "exitCode": code,
                                        "reason": (err or out or "invalid JSON")[:500]}
            else:
                findings = payload.get("findings")
                result["targetScan"] = {
                    "status": "clean" if code == 0 and isinstance(findings, list) and not findings else "findings",
                    "exitCode": code, "sourceFiles": payload.get("sourceFiles"),
                    "findingCount": len(findings) if isinstance(findings, list) else None,
                    "command": item["command"],
                    "evidenceType": "actual-target-scan",
                }
        else:
            result["targetScan"] = {"status": "blocked", "reason": "The enforcer is not present in the target."}
    else:
        result["targetScan"] = {"status": "unsupported", "reason": "No portable target enforcer."}
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
    # Selecting the guidance objective authorizes preparation only. The owner must
    # inspect the exact generated instructions and explicitly approve their application.
    if not approve:
        _stage(state, "agent_guidance", AWAITING,
               "The instructions are proposed but existing instruction files are not modified without approval.",
               evidence=agent_guidance.PROPOSAL_FILE)
        _next(state, "Review the proposed AI agent instructions",
              "python3 tools/acima.py adoption guidance --root . --approve",
              approval=True, writes=True,
              why="Updating repository instructions changes future agent behavior and may alter user-authored guidance.",
              done="The owner approves the generated instruction update; existing content remains preserved.")
        state["repository"]["revision"] = _revision(root)
        state["repository"]["applicationRevision"] = _application_revision(root)
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
              maturity_choice: str | None = None,
              approved_plan_sha256: str | None = None,
              approved_paths: list[str] | None = None) -> dict:
    """Record and execute the final none/selected/all remediation decision."""
    root = root.resolve()
    state = _load(root)
    if choice not in ("none", "selected", "all"):
        raise WorkflowError("remediation choice must be none, selected, or all")
    if state["stages"].get("ci", {}).get("status") not in (
            COMPLETE, BLOCKED, NOT_APPLICABLE, DEFERRED, DECLINED):
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
    if choice != "none":
        try:
            _require_approved_scope(root, state)
        except WorkflowError as error:
            _stage(state, "remediation", BLOCKED,
                   "Source remediation was not authorized: %s. No application source was changed." % error,
                   evidence=REMEDIATION_PLAN)
            state.setdefault("blockers", []).append("source remediation blocked by missing, stale, or mismatched owner approval")
            _next(state, "Reassess and obtain explicit source-change approval",
                  "Refresh the HTML proposal and remediation plan, then approve the exact report, plan digest, recommendation IDs, and file paths. Do not select a recovery branch as a substitute.",
                  approval=True, writes=False,
                  why="This guard prevents a stale, branch-switched, or unreviewed scope from writing application source.",
                  done="The exact report and remediation plan are current and the owner separately authorizes the named source files.")
            _save(root, state)
            return state
        if not str(approved_by or "").strip():
            raise WorkflowError("source remediation requires the explicit name of the approving owner")
        current_plan_digest = _sha(plan_path)
        if not approved_plan_sha256 or approved_plan_sha256 != current_plan_digest:
            raise WorkflowError("source remediation is blocked: review the current remediation plan and supply its exact SHA-256 digest")
        expected_source_paths = sorted({
            str(change.get("path")).replace("\\", "/")
            for item in chosen for change in (item.get("changes") or [])
            if isinstance(change, dict) and change.get("path")
        })
        supplied_source_paths = sorted(set(
            str(path).replace("\\", "/") for path in (approved_paths or [])
        ))
        # A reviewed plan may legitimately contain only manual recommendations.
        # In that case the exact approved path set is empty and the result records
        # that no deterministic source change was made.
        if supplied_source_paths != expected_source_paths:
            raise WorkflowError(
                "source remediation requires exact path approval; expected %s, received %s"
                % (", ".join(expected_source_paths), ", ".join(supplied_source_paths) or "no paths")
            )
        state["sourceRemediationApproval"] = {
            "status": "approved",
            "approvedBy": approved_by.strip(),
            "approvedOn": _today(),
            "planSha256": current_plan_digest,
            "selected": [item.get("id") for item in chosen],
            "approvedPaths": supplied_source_paths,
        }
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
    active_scope = _read_json(root / SCOPE_FILE) if (root / SCOPE_FILE).is_file() else {}
    guidance_approved = "agent-guidance" in _approved_objectives(active_scope)
    guidance = _apply_agent_guidance(root, state) if guidance_approved else None
    if guidance_approved and guidance is None:
        _save(root, state)
        return state
    handoff_approved = "developer-handoff" in _approved_objectives(active_scope)
    if handoff_approved:
        _stage(state, "handoff", COMPLETE, "The approved handoff file includes remediation and AI guidance outcomes.", evidence=HANDOFF_FILE)
        _handoff(root, state, verification)
    else:
        _stage(state, "handoff", DEFERRED,
               "A target handoff document was not authorized; the final outcome will be provided in the agent response.")
    # These source edits were separately authorized; measure later edits from the new baseline.
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
    _attach_adoption_notifications_review(state)
    _save(root, state)
    return state


def guidance(root: Path, *, approve: bool = False) -> dict:
    """Approve and apply generated agent instructions, then write the final handoff."""
    root = root.resolve()
    state = _load(root)
    if state["stages"].get("agent_guidance", {}).get("status") == COMPLETE:
        return state
    approved_scope = _require_approved_scope(root, state)
    if "agent-guidance" not in _approved_objectives(approved_scope):
        raise WorkflowError("agent-guidance was not selected in the owner-approved adoption scope")
    if state["stages"].get("agent_guidance", {}).get("status") != AWAITING:
        raise WorkflowError("no reviewed agent-guidance proposal is awaiting approval")
    if not approve:
        raise WorkflowError("updating repository instructions requires the explicit --approve confirmation after reviewing the proposal")
    if state["stages"].get("remediation", {}).get("status") not in (COMPLETE, NOT_APPLICABLE, DEFERRED):
        raise WorkflowError("decide immediate remediation before applying agent guidance")
    result = _apply_agent_guidance(root, state, approve=True)
    if result is None:
        return state
    verification = _read_json(root / VERIFICATION_FILE) if (root / VERIFICATION_FILE).is_file() else {}
    if "developer-handoff" in _approved_objectives(approved_scope):
        _stage(state, "handoff", COMPLETE, "The approved handoff file includes the AI guidance validation.", evidence=HANDOFF_FILE)
        _handoff(root, state, verification)
    else:
        _stage(state, "handoff", DEFERRED,
               "A target handoff document was not authorized; provide the verified outcome in the agent response.")
    state["repository"]["revision"] = _revision(root)
    state["repository"]["applicationRevision"] = _application_revision(root)
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
    _attach_adoption_notifications_review(state)
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


def _proposal_report(root: Path, state: dict, module_map: dict, proposal: dict) -> dict:
    review_path = root / (state.get("assessmentReview") or {}).get("path", "")
    if not review_path.is_file():
        raise WorkflowError("the validated qualitative review disappeared; regenerate it before creating the HTML proposal")
    try:
        report = render_proposal_report(root, review_path, module_map, proposal, state)
    except (AdoptionReportError, OSError, ValueError, KeyError) as error:
        raise WorkflowError("the required HTML proposal could not be generated and validated: %s" % error) from error
    proposal_path = root / ADOPTION_PROPOSAL_JSON
    report["proposalSha256"] = _sha(proposal_path) if proposal_path.is_file() else None
    state.setdefault("artifacts", {})["proposalReport"] = report
    # Pin approval to the exact post-preparation target state. This digest includes
    # staged/unstaged and untracked repository changes, not only HEAD and branch.
    state.setdefault("repository", {})["revision"] = _revision(root)
    state["repository"]["applicationRevision"] = _application_revision(root)
    report["repositoryRevision"] = state["repository"]["revision"]
    report["indexUrl"] = Path(report["indexHtml"]).as_uri()
    report["pageUrls"] = {name: Path(path).as_uri() for name, path in report["pages"].items()}
    state["proposalReview"] = {
        "status": "awaiting_review",
        "reportId": report["reportId"],
        "reportSha256": report["sha256"],
        "proposalSha256": report["proposalSha256"],
        "directory": report["directory"],
    }
    _stage(state, "proposal_report", AWAITING,
           "The six-page HTML proposal was generated and validated. It must now be opened and shown to the owner. Implementation is blocked until the owner inspects this exact report and approves a scoped set of paths.",
           evidence={"indexHtml": report["indexHtml"], "indexUrl": report["indexUrl"],
                     "proposalHtml": report["proposalHtml"], "pageUrls": report["pageUrls"],
                     "sha256": report["sha256"], "proposalSha256": report["proposalSha256"]})
    _next(state, "Open and review the HTML adoption proposal",
          "Open the user-facing report now: %s . Inspect the Overview, Proposal, Findings, Files, and Evidence pages. Answer the separate ACIMA adoption-notifications decision (prepare a proposal, use only interactive messages, defer, or decline), then record approval for the exact report digest %s and select implementation objectives and paths. This review alone does not authorize implementation." % (
              report["indexUrl"], report["sha256"]),
          approval=True, writes=False,
          why="A Markdown proposal or branch selection is not a substitute for reviewing the complete HTML decision document.",
          done="The owner explicitly records that the exact HTML report digest was reviewed, then selects the implementation objectives and exact target paths.")
    return report


def _report_review_valid(root: Path, state: dict, report_sha256: str,
                         reviewed_by: str) -> dict:
    report = state.get("artifacts", {}).get("proposalReport") or {}
    receipt = state.get("proposalReview") or {}
    if not reviewed_by.strip():
        raise WorkflowError("the person who reviewed the HTML report must be identified")
    if not report.get("directory") or not report.get("sha256"):
        raise WorkflowError("no generated HTML proposal report is available; implementation is blocked")
    current_digest = report_digest(Path(report["directory"]))
    if current_digest != report.get("sha256"):
        raise WorkflowError("the HTML proposal report changed after generation; regenerate it and review the new version")
    if report_sha256 != current_digest:
        raise WorkflowError("the supplied report digest does not match the exact HTML proposal that was generated")
    proposal_path = root / ADOPTION_PROPOSAL_JSON
    if not proposal_path.is_file() or _sha(proposal_path) != report.get("proposalSha256"):
        raise WorkflowError("the adoption proposal changed after the HTML report was generated; regenerate and review it again")
    baseline = state.get("repository", {}).get("revision") or {}
    current = _revision(root)
    if (current.get("head") != baseline.get("head")
            or current.get("branch") != baseline.get("branch")
            or current.get("workingTree") != baseline.get("workingTree")):
        raise WorkflowError("the repository branch, commit, or working-tree content changed since assessment; refresh the assessment and HTML proposal before approval")
    receipt.update({
        "status": "reviewed",
        "reviewedBy": reviewed_by.strip(),
        "reviewedOn": _today(),
        "reportSha256": current_digest,
        "proposalSha256": report.get("proposalSha256"),
        "reportId": report.get("reportId"),
    })
    return receipt


def _approved_objectives(scope: dict) -> set[str]:
    return {
        str(item.get("id")) for item in scope.get("objectives", [])
        if isinstance(item, dict) and item.get("disposition") in {"approved", "required"}
    }


def _prepare_adoption_notifications(root: Path, state: dict, scope: dict) -> dict:
    """Prepare a repository-grounded notification proposal without implementing it."""
    target = root / ADOPTION_NOTIFICATIONS_PROPOSAL
    if target.exists():
        raise WorkflowError(
            "an adoption-notifications proposal already exists; review or explicitly supersede it rather than overwriting it"
        )
    extensions = {".py", ".cs", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".go",
                  ".java", ".kt", ".rs", ".rb", ".php", ".json", ".yml", ".yaml"}
    skipped = {".git", ".vs", "node_modules", "bin", "obj", "dist", "build",
               "coverage", ".venv", "venv", ".acima"}
    signals = ("notification", "toast", "snackbar", "alert", "webhook",
               "email", "mailer", "push", "signalr", "websocket", "in-app")
    observed: list[dict] = []
    inspected = 0
    for path in _walk_files(root, skipped):
        if path.suffix.lower() not in extensions:
            continue
        relative = path.relative_to(root)
        inspected += 1
        if inspected > 12000:
            break
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        lowered = content.lower()
        matches = [term for term in signals if term in lowered]
        if matches:
            observed.append({
                "path": relative.as_posix(),
                "signals": matches,
                "meaning": "Candidate for owner inspection only; token presence does not prove an existing notification capability.",
            })
            if len(observed) >= 150:
                break
    proposal = {
        "schemaVersion": "1.0",
        "status": "proposal_only",
        "generatedAt": _now(),
        "repository": {
            "name": root.name,
            "revision": state.get("repository", {}).get("revision"),
        },
        "decision": {
            "objective": "ACIMA adoption notifications",
            "selectedBy": (scope.get("approvedBy") or ""),
            "selectionMeaning": "The owner authorized preparation and review of this proposal only.",
            "implementationAuthorized": False,
        },
        "purpose": "Provide clear, user-controlled notifications about ACIMA adoption decisions and progress without conflating them with application-domain notifications.",
        "observedNotificationEvidence": {
            "filesInspected": inspected,
            "matches": observed,
            "interpretation": "These are discovery signals, not a determination that a reusable notification system exists. A human review must inspect the referenced code and actual delivery surfaces.",
        },
        "proposedMilestones": [
            "Assessment started and completed",
            "Module-map review required, approved, modified, deferred or rejected",
            "HTML proposal generated and awaiting review",
            "CI provider discovered and CI decision recorded",
            "Implementation scope approved, blocked, started and completed",
            "Remediation decision recorded and source changes verified",
            "Final verification and handoff completed",
        ],
        "designDecisionsRequired": [
            "Where the notices should appear: interactive agent conversation, target application UI, or both",
            "Who receives them and which events each audience should see",
            "Whether notices are ephemeral, persisted, or both",
            "User preferences, opt-out and quieting behavior",
            "Deduplication, ordering, retry and failure semantics",
            "Privacy and data minimization for repository paths, findings and user decisions",
            "Whether any external provider or channel is necessary",
        ],
        "recommendedApproach": "Prefer the existing interaction surface for workflow progress unless repository evidence and owner requirements justify a persistent product notification capability. Do not add a provider, persistence layer or new UI abstraction without evidence.",
        "implementationImpact": {
            "sourceChangesProposed": [],
            "pathsAuthorizedForModification": [],
            "providerAuthorized": False,
            "externalIntegrationAuthorized": False,
        },
        "nextDecision": "Review this proposal, then explicitly approve or decline a separate implementation plan that names every source/configuration path. This proposal is not permission to modify application code.",
    }
    _write_json(root, ADOPTION_NOTIFICATIONS_PROPOSAL, proposal)
    state.setdefault("artifacts", {})["adoptionNotificationsProposal"] = ADOPTION_NOTIFICATIONS_PROPOSAL
    state["adoptionNotifications"] = {
        "status": "proposal_prepared",
        "implementationAuthorized": False,
        "proposalSha256": _sha(target),
        "observedFiles": len(observed),
        "filesInspected": inspected,
    }
    _stage(
        state, "adoption_notifications", COMPLETE,
        "The owner requested a separate adoption-notifications proposal. It is prepared for review; no notification source code, provider, UI, persistence or configuration was changed.",
        evidence=ADOPTION_NOTIFICATIONS_PROPOSAL,
    )
    state["decisions"].append({
        "id": "adoption-notifications",
        "decision": "proposal_prepared",
        "by": scope.get("approvedBy"),
        "on": _today(),
        "proposalSha256": state["adoptionNotifications"]["proposalSha256"],
        "implementationAuthorized": False,
    })
    return proposal


def _implementation_paths(root: Path, scope: dict | None = None) -> list[str]:
    """Return every file the approved infrastructure stage may create or modify."""
    scope = scope or {}
    language = _language(root)
    plan = _enforcer(root, language)
    objectives = _approved_objectives(scope)
    paths: list[str] = []
    if "local-enforcement" in objectives:
        paths.extend([
            STATE_FILE, SCOPE_FILE, CONFIG_NAME, APPROVAL_FILE,
            ENFORCEMENT_FILE, ARCH_TESTS_FILE, WAIVERS_FILE, REMEDIATION_PLAN,
            VERIFICATION_FILE, REMEDIATION_RESULT,
        ])
        if plan:
            paths.extend(item["target"] for item in plan.get("files", []))
    if "adoption-notifications" in objectives:
        paths.append(ADOPTION_NOTIFICATIONS_PROPOSAL)
    if "ci-enforcement" in objectives:
        paths.append(CI_FILE)
        if _ci(root).get("provider") == "github-actions" and (scope.get("ciOptions") or {}).get("createWorkflow", True):
            paths.append(".github/workflows/acima.yml")
    if "agent-guidance" in objectives:
        discovery = agent_guidance.discover(root)
        paths.extend([
            agent_guidance.PROPOSAL_FILE, agent_guidance.RESULT_FILE,
            discovery.get("primary") or "AGENTS.md",
            agent_guidance.ARCH_FILE, agent_guidance.ENFORCEMENT_FILE,
            agent_guidance.JUDGMENT_FILE, agent_guidance.WORKFLOW_FILE,
        ])
    if "developer-handoff" in objectives:
        paths.append(HANDOFF_FILE)
    return sorted(set(paths))


def _require_approved_scope(root: Path, state: dict) -> dict:
    """Fail closed unless scope, report review, proposal, repository and paths all match."""
    scope_path = root / SCOPE_FILE
    if not scope_path.is_file():
        raise WorkflowError("no owner-approved adoption scope exists; selecting a mode or branch is not implementation consent")
    scope = _read_json(scope_path)
    if scope.get("authorization", {}).get("explicit") is not True:
        raise WorkflowError("the adoption scope is a draft, not explicit implementation authorization")
    report_review = scope.get("reportReview") or {}
    report = state.get("artifacts", {}).get("proposalReport") or {}
    if not report.get("directory") or report_digest(Path(report["directory"])) != report.get("sha256"):
        raise WorkflowError("the HTML report is missing or has changed since its approval")
    proposal_file = root / ADOPTION_PROPOSAL_JSON
    if not proposal_file.is_file() or _sha(proposal_file) != report.get("proposalSha256"):
        raise WorkflowError("the proposal changed after approval; regenerate the report and obtain fresh consent")
    if (report_review.get("status") != "reviewed"
            or report_review.get("reportSha256") != report.get("sha256")
            or report_review.get("proposalSha256") != report.get("proposalSha256")
            or state.get("proposalReview", {}).get("status") != "reviewed"):
        raise WorkflowError("the exact HTML proposal has not been reviewed and recorded; no target implementation is authorized")
    if report_review.get("reviewedBy") != scope.get("approvedBy"):
        raise WorkflowError("the report reviewer and implementation approver must be explicitly identified and match")
    if not str(scope.get("approvedBy", "")).strip():
        raise WorkflowError("scope.approvedBy is required")
    try:
        date.fromisoformat(str(scope.get("approvedOn")))
    except (TypeError, ValueError) as error:
        raise WorkflowError("scope.approvedOn must be a valid YYYY-MM-DD date") from error
    objectives = _approved_objectives(scope)
    if "local-enforcement" not in objectives:
        raise WorkflowError("local enforcement was not explicitly approved; no enforcer, waiver, or architecture-test files may be written")
    if "baseline-waivers" not in objectives:
        raise WorkflowError("the adoption enforcement stage creates a waiver-baseline file; explicitly approve that artifact or defer implementation")
    approved_paths = scope.get("approvedPaths")
    if not isinstance(approved_paths, list) or not approved_paths or any(not isinstance(path, str) or not path.strip() for path in approved_paths):
        raise WorkflowError("scope.approvedPaths must list every exact target file approved for implementation")
    approved_paths = {Path(path).as_posix() for path in approved_paths}
    required = set(_implementation_paths(root, scope))
    missing = sorted(required - approved_paths)
    if missing:
        raise WorkflowError("implementation scope does not approve every required file path: %s" % ", ".join(missing))
    if any(Path(path).is_absolute() or ".." in Path(path).parts for path in approved_paths):
        raise WorkflowError("approved paths must be repository-relative and cannot escape the target")
    # A branch picker or recovery branch is context only. The reviewed scope is invalid
    # if the branch or commit moved since the report was produced.
    baseline = state.get("repository", {}).get("revision") or {}
    current = _revision(root)
    if (current.get("head") != baseline.get("head")
            or current.get("branch") != baseline.get("branch")
            or current.get("workingTree") != baseline.get("workingTree")):
        raise WorkflowError("branch, commit, or working-tree content changed after report review; reassess and obtain fresh scope approval")
    if state.get("repository", {}).get("applicationRevision") != _application_revision(root):
        raise WorkflowError("application source changed after assessment; refresh the report and approval before implementation")
    approval = state.get("implementationApproval") or {}
    if (approval.get("status") != "approved"
            or approval.get("reportSha256") != report_review.get("reportSha256")
            or approval.get("proposalSha256") != report_review.get("proposalSha256")
            or approval.get("approvedBy") != scope.get("approvedBy")
            or approval.get("scopeSha256") != _sha(scope_path)
            or approval.get("approvedPaths") != scope.get("approvedPaths")
            or approval.get("approvedObjectives") != sorted(objectives)):
        raise WorkflowError("the workflow has no matching persisted implementation-approval receipt")
    return scope


def _apply(root: Path, state: dict) -> dict:
    # This is the last safety boundary before target writes. Never trust a mode,
    # branch name, existing config, or a leftover scope file as approval.
    approved_scope = _require_approved_scope(root, state)
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
    scope = approved_scope
    ci_objective = next((item for item in scope.get("objectives", [])
                         if isinstance(item, dict) and item.get("id") == "ci-enforcement"), None)
    ci_decision = ci_objective.get("disposition") if ci_objective else "deferred"
    ci = {"status": "deferred", "provider": _ci(root).get("provider"),
          "claim": "CI integration was not authorized. No CI workflow was changed."}
    if ci_decision in {"approved", "required"}:
        ci = _integrate_ci(root, state, command)
        ci_status = (COMPLETE if ci.get("status") in
                     ("configured", "already_present", "no_provider", "manual_instructions") else BLOCKED)
        state["artifacts"]["ci"] = CI_FILE
    else:
        ci_status = DEFERRED if ci_decision == "deferred" else DECLINED
    _stage(state, "ci", ci_status, ci.get("claim", "No CI claim recorded."),
           evidence=CI_FILE if ci_decision in {"approved", "required"} else None)
    guidance_decision = next((item.get("disposition") for item in scope.get("objectives", [])
                              if isinstance(item, dict) and item.get("id") == "agent-guidance"), "deferred")
    if guidance_decision in {"approved", "required"}:
        guidance_proposal = agent_guidance.proposal(root, state)
        state["artifacts"]["agentGuidanceProposal"] = agent_guidance.PROPOSAL_FILE
        state["artifacts"]["agentGuidanceData"] = agent_guidance.RESULT_FILE
        state["agentGuidance"] = guidance_proposal
        _stage(state, "agent_guidance", AWAITING,
               "Agent instructions were proposed. They will not be applied until separately approved.",
               evidence=agent_guidance.PROPOSAL_FILE)
    else:
        _stage(state, "agent_guidance", DEFERRED,
               "Agent instructions were not authorized and no instruction file was changed.")
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
    # The approved enforcement stage just changed repository files. Refresh the
    # baseline so the later, separately approved remediation stage can fail closed
    # against any changes made after this point.
    state["repository"]["revision"] = _revision(root)
    state["repository"]["applicationRevision"] = _application_revision(root)
    _attach_adoption_notifications_review(state)
    _save(root, state)
    return state


def _validate_qualitative_review(root: Path, review_path: Path | None) -> dict:
    if review_path is not None and not review_path.is_absolute():
        review_path = root / review_path
    candidates = [review_path] if review_path else [
        root / "docs/acima/qualitative-review.json",
        root / ".acima/qualitative-review.json",
    ]
    selected = next((path for path in candidates if path is not None and path.is_file()), None)
    catalog_path = ROOT / "tools/acima-spec/rules.json"
    catalog = _read_json(catalog_path)
    required_rules = len(catalog.get("rules", []))
    if selected is None:
        raise WorkflowError(
            ("the %s-rule qualitative review is mandatory before adoption starts; " % required_rules)
            + "create docs/acima/qualitative-review.json and validate it with "
            "tools/acima.py validate-review --root . --file docs/acima/qualitative-review.json"
        )
    selected = selected.resolve()
    try:
        selected.relative_to(root.resolve())
    except ValueError as error:
        raise WorkflowError("the qualitative review file must be inside the assessed repository") from error
    validation = load_and_validate_review(
        selected, root, catalog, hashlib.sha256(catalog_path.read_bytes()).hexdigest()
    )
    if (validation.get("decisionComplete") is not True
            or validation.get("reviewed") != required_rules
            or validation.get("required") != required_rules
            or validation.get("unresolved") != 0):
        raise WorkflowError(
            "the qualitative review is not decision-complete: %s/%s valid reviews, %s unresolved; "
            "resolve every missing, invalid or insufficient-evidence disposition before adoption"
            % (validation.get("reviewed"), validation.get("required"), validation.get("unresolved"))
        )
    return {
        "path": selected.relative_to(root.resolve()).as_posix(),
        "reviewed": validation["reviewed"],
        "required": validation["required"],
        "counts": validation["counts"],
        "catalogSha256": hashlib.sha256(catalog_path.read_bytes()).hexdigest(),
        "reviewer": _read_json(selected).get("reviewer"),
        "reviewedOn": _read_json(selected).get("reviewedOn"),
        "validation": "decision_complete",
    }


def start(root: Path, mode: str, *, authorize_full: bool = False,
          reviewer: str | None = None, review_path: Path | None = None) -> dict:
    root = root.resolve()
    if not root.is_dir():
        raise WorkflowError("project does not exist: %s" % root)
    if mode not in MODES:
        raise WorkflowError("mode must be guided or full")
    if mode == "full" and not authorize_full:
        raise WorkflowError("full automation requires the explicit --authorize-full flag")
    if mode == "full" and not (reviewer or "").strip():
        reviewer = "Automated adoption mode selection"
    state_path = root / STATE_FILE
    if state_path.is_file():
        existing = _load(root)
        if existing.get("mode") != mode:
            raise WorkflowError("the repository already has a %s workflow; resume it or start a new "
                                "engagement explicitly" % existing.get("mode"))
        return continue_workflow(root)
    assessment_review = _validate_qualitative_review(root, review_path)
    state = _new_state(root, mode, reviewer)
    state["assessmentReview"] = assessment_review
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
    _stage(state, "assessment", COMPLETE,
           "The complete %s-rule qualitative review was validated against the current catalog with repository-grounded evidence." % assessment_review["required"],
           evidence={"review": assessment_review["path"], "reviewed": assessment_review["reviewed"],
                     "required": assessment_review["required"], "catalogSha256": assessment_review["catalogSha256"]})
    if module_map.get("proposal"):
        _write_json(root, PROPOSAL_JSON, module_map.get("proposal"))
        state["artifacts"]["moduleMapProposal"] = PROPOSAL_JSON
    adopted = False
    reason = ""
    if mode == "full":
        # Automated preparation never makes a candidate ownership map authoritative.
        if module_map.get("authoritativeMap", {}).get("status") == "complete":
            adopted, reason = True, "An authoritative map already exists; its presence does not authorize implementation."
        else:
            reason = "Automated mode prepares the candidate map; explicit owner approval is still required."
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
    proposal_document = None
    if mode != "guided" or adopted:
        proposal_document = _write_proposal(root, module_map, state)
    if mode == "full":
        # Prepare reviewable proposals only. These are not active target enforcement,
        # CI configuration, or agent-instruction changes.
        language = _language(root)
        enforcement_proposal = {
            "status": "proposed",
            "language": language,
            "enforcerAvailable": _enforcer(root, language) is not None,
            "existingArchitecture": module_map.get("existingArchitecture", {}),
            "claim": "No enforcement tooling has been installed or activated.",
        }
        _write_json(root, "docs/acima/enforcement-proposal.json", enforcement_proposal)
        ci_discovery = _ci(root)
        ci_proposal = {
            "status": "proposed",
            "discovery": ci_discovery,
            "userDecisionRequired": True,
            "claim": "No CI workflow has been changed.",
        }
        _write_json(root, "docs/acima/ci-proposal.json", ci_proposal)
        # Do not create or replace repository-level agent instructions during preparation.
        # The agent-guidance proposal is a separately selectable implementation stage.
        remediation_proposal = write_remediation_plan(root, state)
        state["artifacts"]["enforcementProposal"] = "docs/acima/enforcement-proposal.json"
        state["artifacts"]["ciProposal"] = "docs/acima/ci-proposal.json"
        state["artifacts"]["remediationPlan"] = REMEDIATION_PLAN
    if mode == "guided":
        map_pending = state["stages"].get("module_map", {}).get("status") == AWAITING
        if map_pending:
            _stage(state, "adoption_proposal", IN_PROGRESS,
                   "Proposal generation is deliberately held until the user approves the module map.")
        else:
            _stage(state, "adoption_proposal", COMPLETE,
                   "The adoption proposal data is ready for HTML rendering.",
                   evidence=ADOPTION_PROPOSAL)
            proposal_document = proposal_document or _read_json(root / ADOPTION_PROPOSAL_JSON)
            _proposal_report(root, state, module_map, proposal_document)
        if map_pending:
            _next(state, "Review the proposed module map",
                  "python3 conformance/adoption_workflow.py approve --project . --map-decisions <review.json>",
                  approval=True, writes=True,
                  why="Inferred ownership must not become authoritative before the map review.",
                  done="The map review approves a complete map; only then is the six-page HTML adoption proposal generated.")
        else:
            report = state["artifacts"]["proposalReport"]
            _next(state, "Open and review the HTML adoption proposal",
                  "Open the user-facing report now: %s . Inspect all six pages. Then answer the separate ACIMA adoption-notifications question (prepare a proposal, use only interactive messages, defer, or decline), record explicit approval for report digest %s, and select exact objectives and paths." % (report["indexUrl"], report["sha256"]),
                  approval=True, writes=False,
                  why="A Markdown summary, a vague 'continue', or a branch selection is not review of the HTML proposal and does not authorize implementation.",
                  done="The owner has inspected all six pages and submits a scope bound to this report digest with explicit objectives and target paths.")
        _save(root, state)
        return state
    # Automated mode prepares the package and then stops at one consolidated user review.
    # Selecting automated mode is not consent to apply every proposed change.
    if not adopted:
        _stage(state, "module_map", AWAITING,
               "The complete map proposal is included in the consolidated review; ownership is not approved.",
               evidence=PROPOSAL_JSON)
    _stage(state, "adoption_proposal", AWAITING,
           "The adoption package is prepared and awaits the user's consolidated scope decision.",
           evidence=ADOPTION_PROPOSAL)
    for stage_name, detail, evidence in (
        ("implementation", "Enforcement changes are proposed but await consolidated scope approval.",
         "docs/acima/enforcement-proposal.json"),
        ("agent_guidance", "Agent guidance is an optional stage and has not been applied.",
         None),
        ("ci", "CI integration is proposed and awaits the user's explicit CI decision.",
         "docs/acima/ci-proposal.json"),
        ("remediation", "Application source remediation is a separate later decision.",
         REMEDIATION_PLAN),
    ):
        _stage(state, stage_name, AWAITING, detail, evidence=evidence)
    if proposal_document is None:
        proposal_document = _read_json(root / ADOPTION_PROPOSAL_JSON)
    _proposal_report(root, state, module_map, proposal_document)
    report = state["artifacts"]["proposalReport"]
    _next(state, "Open and review the consolidated HTML adoption proposal",
          "Open the user-facing report now: %s . Inspect all six pages. Then answer the separate ACIMA adoption-notifications question (prepare a proposal, use only interactive messages, defer, or decline), explicitly approve the exact report digest %s, choose the stages to implement, and list the target paths." % (report["indexUrl"], report["sha256"]),
          approval=True, writes=False,
          why="Automated mode automates preparation and approved execution, not consent. Report review, branch selection, or choosing 'recover' never authorizes file changes.",
          done="The owner has inspected the complete report and explicitly approved the selected stages and exact files. No other files may be changed.")
    _save(root, state)
    return state


def approve(root: Path, *, map_decisions: Path | None = None,
            scope: Path | None = None, reviewer: str | None = None,
            reviewed_report_sha256: str | None = None,
            reviewed_by: str | None = None) -> dict:
    root = root.resolve()
    state = _load(root)
    if state.get("mode") == "guided" and map_decisions and scope:
        raise WorkflowError("guided adoption requires a separate adoption-proposal review after module-map approval")
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
                # A map review is its own authorized target change. The proposal and
                # implementation gates begin from the post-map state, not the pre-map tree.
                state["repository"]["revision"] = _revision(root)
                state["repository"]["applicationRevision"] = _application_revision(root)
                if state.get("mode") == "guided":
                    reviewed_map = discover_module_map(root)
                    proposal_document = _write_proposal(root, reviewed_map, state)
                    _stage(state, "adoption_proposal", COMPLETE,
                           "The owner-approved module map is reflected in the adoption proposal.",
                           evidence=ADOPTION_PROPOSAL)
                    _proposal_report(root, state, reviewed_map, proposal_document)
            else:
                _stage(state, "module_map", AWAITING, "The review is %s; no config was written." %
                       result.get("status"), evidence=APPROVAL_FILE)
        else:
            raise WorkflowError("no module-map proposal is available at %s" % PROPOSAL_JSON)
    if scope:
        if not (root / CONFIG_NAME).is_file():
            raise WorkflowError("an adoption scope cannot be approved before an authoritative module map exists")
        approval = _read_json(root / APPROVAL_FILE) if (root / APPROVAL_FILE).is_file() else {}
        authoritative = discover_module_map(root).get("authoritativeMap", {}).get("status") == "complete"
        if not authoritative and (
                approval.get("status") != "approved"
                or not (approval.get("approval") or {}).get("canWriteConfig")):
            raise WorkflowError("the module map is not approved and cannot authorize an implementation scope")
        document = _read_json(scope)
        for key in ("approvedBy", "approvedOn", "objectives", "approvedPaths"):
            if key not in document:
                raise WorkflowError("scope is missing %s" % key)
        if not str(document.get("approvedBy", "")).strip():
            raise WorkflowError("scope.approvedBy is required")
        try:
            date.fromisoformat(str(document.get("approvedOn")))
        except (TypeError, ValueError) as error:
            raise WorkflowError("scope.approvedOn must be a YYYY-MM-DD date") from error
        objectives = document.get("objectives")
        if not isinstance(objectives, list) or not objectives:
            raise WorkflowError("scope.objectives must contain at least one objective")
        allowed_objectives = {
            "assessment", "local-enforcement", "baseline-waivers", "ci-enforcement",
            "developer-handoff", "agent-guidance", "adoption-notifications",
            "source-remediation", "full-conformance", "communication-governance",
        }
        seen_objectives = set()
        for objective in objectives:
            if not isinstance(objective, dict) or not objective.get("id"):
                raise WorkflowError("every scope objective needs an id")
            objective_id = objective.get("id")
            if objective_id not in allowed_objectives or objective_id in seen_objectives:
                raise WorkflowError("scope objective %s is unknown or duplicated" % objective_id)
            seen_objectives.add(objective_id)
            if objective.get("disposition") not in {"required", "approved", "deferred", "optional", "declined"}:
                raise WorkflowError("scope objective %s has an unknown disposition" % objective_id)
        if "adoption-notifications" not in seen_objectives:
            raise WorkflowError(
                "scope must explicitly answer the ACIMA adoption-notifications decision with approved, deferred, or declined"
            )
        reviewed = _report_review_valid(
            root, state, reviewed_report_sha256 or "",
            reviewed_by or "",
        )
        document["reportReview"] = reviewed
        document["authorization"] = {
            "mode": state["mode"],
            "explicit": True,
            "basis": "The owner reviewed the exact HTML report and explicitly selected implementation objectives and paths.",
            "reportSha256": reviewed["reportSha256"],
            "proposalSha256": reviewed["proposalSha256"],
        }
        if not isinstance(document.get("approvedPaths"), list):
            raise WorkflowError("scope.approvedPaths must be an explicit array of exact repository-relative paths")
        if any(not isinstance(path, str) or not path.strip() for path in document["approvedPaths"]):
            raise WorkflowError("scope.approvedPaths may contain only non-empty repository-relative paths")
        if any(Path(path).is_absolute() or ".." in Path(path).parts for path in document["approvedPaths"]):
            raise WorkflowError("scope.approvedPaths must not escape the repository")
        document["approvedPaths"] = sorted(set(Path(path).as_posix() for path in document["approvedPaths"]))
        selected_objectives = _approved_objectives(document)
        required_paths = set(_implementation_paths(root, document))
        missing_paths = sorted(required_paths - set(document["approvedPaths"]))
        if missing_paths:
            raise WorkflowError("scope does not explicitly approve every target path required for the selected stages: %s" % ", ".join(missing_paths))
        unexpected_paths = sorted(set(document["approvedPaths"]) - set(_implementation_paths(root, document)))
        if unexpected_paths:
            raise WorkflowError("scope includes paths outside the proposed adoption implementation package: %s" % ", ".join(unexpected_paths))
        _write_json(root, SCOPE_FILE, document)
        state["artifacts"]["scope"] = SCOPE_FILE
        state["proposalReview"] = reviewed
        if "adoption-notifications" in selected_objectives:
            _prepare_adoption_notifications(root, state, document)
        else:
            _stage(
                state, "adoption_notifications", DEFERRED,
                "The owner deferred or declined ACIMA adoption notifications. No notification feature was added.",
            )
        # The only target write authorized by adoption-notifications is the proposal
        # artifact itself. Re-pin the repository baseline before optional enforcement
        # runs so the approved proposal write is not mistaken for an external change.
        state["repository"]["revision"] = _revision(root)
        state["repository"]["applicationRevision"] = _application_revision(root)
        _stage(state, "proposal_report", COMPLETE,
               "The owner reviewed the exact generated HTML report and recorded its digest.",
               evidence={"sha256": reviewed["reportSha256"], "proposalSha256": reviewed["proposalSha256"]})
        state["decisions"].append({
            "id": "adoption-scope", "decision": "accepted",
            "by": document.get("approvedBy"), "on": _today(),
            "reportSha256": reviewed["reportSha256"],
            "approvedObjectives": sorted(selected_objectives),
            "approvedPaths": document["approvedPaths"],
        })
        _stage(state, "adoption_proposal", COMPLETE,
               "The exact HTML proposal was reviewed and the owner selected explicit adoption objectives and paths.",
               evidence={"reportSha256": reviewed["reportSha256"], SCOPE_FILE: True})
        if "local-enforcement" in selected_objectives:
            state["implementationApproval"] = {
                "status": "approved", "approvedBy": document["approvedBy"],
                "approvedOn": document["approvedOn"],
                "reportSha256": reviewed["reportSha256"],
                "proposalSha256": reviewed["proposalSha256"],
                "approvedPaths": document["approvedPaths"],
                "approvedObjectives": sorted(selected_objectives),
                "scopeSha256": _sha(root / SCOPE_FILE),
            }
        else:
            state["implementationApproval"] = {
                "status": "not_authorized", "approvedBy": document["approvedBy"],
                "approvedOn": document["approvedOn"],
                "reportSha256": reviewed["reportSha256"],
                "proposalSha256": reviewed["proposalSha256"],
            }
    if scope and (root / CONFIG_NAME).is_file() and "local-enforcement" in _approved_objectives(document):
        _save(root, state)
        return _apply(root, state)
    if scope and "local-enforcement" not in _approved_objectives(document):
        _stage(state, "implementation", DEFERRED,
               "The owner reviewed the proposal but did not authorize local enforcement. No enforcer or application files were changed.")
        if state.get("adoptionNotifications", {}).get("status") == "proposal_prepared":
            _next(state, "Review the separate ACIMA adoption-notifications proposal",
                  "Open %s . This proposal does not authorize notification source-code, provider, UI or configuration changes. Decide whether to request a separate implementation plan." % ADOPTION_NOTIFICATIONS_PROPOSAL,
                  approval=True, writes=False,
                  why="The owner authorized preparation only. A separate implementation plan and exact-path approval are required before any notification code is changed.",
                  done="The owner reviews the proposal and explicitly requests, defers or declines a subsequent implementation plan.")
        else:
            _next(state, "No implementation is authorized",
                  "The assessment and HTML proposal are retained. Start a new explicit scope review to authorize additional stages.",
                  approval=False, writes=False,
                  why="A report review without an explicit local-enforcement selection does not authorize target changes.",
                  done="The workflow remains read-only until a new, explicit scope approval is provided.")
    elif not scope and state["stages"].get("proposal_report", {}).get("status") != AWAITING:
        if state["stages"].get("module_map", {}).get("status") == COMPLETE:
            _stage(state, "adoption_proposal", AWAITING,
                   "The map is approved; the HTML adoption proposal must be reviewed before scope selection.",
                   evidence=ADOPTION_PROPOSAL)
            _next(state, "Open and review the HTML adoption proposal",
                  "Open the generated six-page report and inspect all sections before selecting any implementation scope.",
                  approval=True, writes=False,
                  why="A module-map approval does not authorize enforcement, CI, instructions, or application changes.",
                  done="The owner reviews the exact report and approves a scoped set of objectives and paths.")
    _save(root, state)
    return state


def _reconcile_owner_approved_module_map(root: Path, state: dict) -> bool:
    """Recover an owner-approved map written before workflow state was advanced.

    A complete config alone is not consent. Reconciliation requires the exact
    proposal review, a matching provenance marker in the config, a structurally
    valid approval, and an authoritative map that covers the current source.
    """
    stage = state.get("stages", {}).get("module_map", {})
    if stage.get("status") not in (AWAITING, BLOCKED):
        return False
    config_path = root / CONFIG_NAME
    proposal_path = root / PROPOSAL_JSON
    if not config_path.is_file() or not proposal_path.is_file():
        return False
    decision_candidates = (
        root / OWNER_MAP_REVIEW_FILE,
        root / ".acima/module-map-decisions.json",
    )
    decisions_path = next((path for path in decision_candidates if path.is_file()), None)
    if decisions_path is None:
        return False

    config = _read_json(config_path)
    marker = config.get("_moduleMapApproval") or {}
    proposal = _read_json(proposal_path)
    proposal_id = proposal.get("proposalId")
    decisions = _read_json(decisions_path)
    if (not proposal_id or decisions.get("proposalId") != proposal_id
            or marker.get("proposalId") != proposal_id
            or marker.get("status") != "approved"
            or marker.get("reviewer") != decisions.get("reviewer")
            or marker.get("reviewedOn") != decisions.get("reviewedOn")):
        raise WorkflowError(
            "an existing module map cannot advance adoption: the map review, config approval provenance, "
            "and current discovery proposal do not identify the same owner decision"
        )

    wrapper = {"proposal": proposal, "proposalId": proposal_id}
    review_result = apply_review(wrapper, decisions, root=root)
    if (review_result.get("status") != "approved"
            or not (review_result.get("approval") or {}).get("canWriteConfig")):
        raise WorkflowError(
            "the persisted module-map decisions are not a complete approval; unresolved ownership remains"
        )
    expected = build_config(wrapper, review_result, existing=config, language=_language(root))
    if expected.get("units") != config.get("units"):
        raise WorkflowError(
            "the persisted module map does not preserve the approved review's unit paths and roles; "
            "no workflow stage was advanced"
        )
    authoritative = discover_module_map(root).get("authoritativeMap") or {}
    if authoritative.get("status") != "complete":
        raise WorkflowError(
            "the owner-reviewed module map is not authoritative for the current source inventory: %s"
            % (authoritative.get("summary") or authoritative.get("status") or "unknown")
        )

    _write_json(root, APPROVAL_FILE, review_result)
    state.setdefault("artifacts", {})["moduleMapApproval"] = APPROVAL_FILE
    state["artifacts"]["moduleMap"] = CONFIG_NAME
    state["decisions"].append({
        "id": "module-map", "decision": "accepted",
        "by": decisions.get("reviewer"), "on": decisions.get("reviewedOn"),
        "proposalId": proposal_id, "reconciled": True,
        "decisionFile": decisions_path.relative_to(root).as_posix(),
    })
    _stage(
        state, "module_map", COMPLETE,
        "The previously recorded owner approval was validated against the current proposal and authoritative config.",
        evidence={"config": CONFIG_NAME, "approval": APPROVAL_FILE,
                  "decisionFile": decisions_path.relative_to(root).as_posix(),
                  "proposalId": proposal_id},
    )
    state["repository"]["revision"] = _revision(root)
    state["repository"]["applicationRevision"] = _application_revision(root)
    if state.get("mode") == "guided":
        reviewed_map = discover_module_map(root)
        proposal_document = _write_proposal(root, reviewed_map, state)
        _stage(
            state, "adoption_proposal", COMPLETE,
            "The reconciled owner-approved module map is reflected in the adoption proposal.",
            evidence=ADOPTION_PROPOSAL,
        )
        _proposal_report(root, state, reviewed_map, proposal_document)
    return True


def continue_workflow(root: Path) -> dict:
    root = root.resolve()
    state = _load(root)
    if state["stages"].get("handoff", {}).get("status") == COMPLETE:
        return state
    if state["stages"].get("module_map", {}).get("status") in (AWAITING, BLOCKED):
        try:
            reconciled = _reconcile_owner_approved_module_map(root, state)
        except (WorkflowError, ModuleMapError, OSError, ValueError) as error:
            _stage(state, "module_map", BLOCKED, "Persisted map approval could not be reconciled safely: %s" % error)
            state.setdefault("blockers", []).append("module map approval reconciliation failed")
            _next(
                state, "Resolve the module-map approval record",
                "Review the current proposal, decisions file and acima.config.json; do not implement until they agree.",
                approval=True, writes=False,
                why="ACIMA cannot infer consent from a config file or a conversation summary when approval provenance is inconsistent.",
                done="The proposal id, owner decisions, config approval marker and authoritative source coverage agree.",
            )
            _save(root, state)
            return state
        if reconciled:
            _save(root, state)
            return state
    if (state.get("adoptionNotifications", {}).get("status") == "proposal_prepared"
            and not state.get("adoptionNotifications", {}).get("implementationDecision")):
        _next(state, "Review the separate ACIMA adoption-notifications proposal",
              "Open %s . Decide whether to request a separate implementation plan, defer it, or decline it. No notification source or external integration is authorized by this proposal." % ADOPTION_NOTIFICATIONS_PROPOSAL,
              approval=True, writes=False,
              why="The scope approved proposal preparation only; implementation needs its own exact file-level review and approval.",
              done="The owner records a separate implementation-plan decision.")
        _save(root, state)
        return state
    if state["stages"].get("proposal_report", {}).get("status") == AWAITING:
        report = state.get("artifacts", {}).get("proposalReport") or {}
        _next(state, "Open and review the HTML adoption proposal",
              "Open the user-facing report now: %s . Inspect all six pages. Approval must identify report digest %s and the exact objectives and paths." % (
                  report.get("indexUrl", report.get("indexHtml", "the generated report index.html")),
                  report.get("sha256", "unavailable")),
              approval=True, writes=False,
              why="A previous approval, branch selection, or resumed workflow cannot bypass review of the exact current report.",
              done="The owner inspects this report version and explicitly approves the selected stages and paths.")
        _save(root, state)
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
    if ((root / CONFIG_NAME).is_file() and (root / SCOPE_FILE).is_file()
            and (state.get("implementationApproval") or {}).get("status") == "approved"):
        return _apply(root, state)
    if (root / SCOPE_FILE).is_file() and (state.get("implementationApproval") or {}).get("status") != "approved":
        _save(root, state)
        return state
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
            command.add_argument("--review", default=None,
                                 help="validated complete qualitative review JSON for the current catalog")
        elif name == "approve":
            command.add_argument("--map-decisions", default=None)
            command.add_argument("--scope", default=None)
            command.add_argument("--reviewer", default=None)
            command.add_argument("--reviewed-report-sha256", default=None,
                                 help="exact digest of the six-page HTML proposal the owner reviewed")
            command.add_argument("--reviewed-by", default=None,
                                 help="named owner who inspected the exact HTML proposal")
        elif name == "guidance":
            command.add_argument("--approve", action="store_true")
        elif name == "remediate":
            command.add_argument("--choice", choices=("none", "selected", "all"), required=True)
            command.add_argument("--maturity-choice", choices=("greenfield", "brownfield"), default=None)
            command.add_argument("--selected", action="append", default=[])
            command.add_argument("--approved-by", default=None)
            command.add_argument("--approved-plan-sha256", default=None,
                                 help="exact digest of the remediation plan reviewed by the owner")
            command.add_argument("--approved-path", action="append", default=[],
                                 help="exact repository-relative source file approved for modification; repeat as needed")
            command.add_argument("--confirm", action="store_true")
            command.add_argument("--confirm-scope", action="store_true", dest="confirm_scope")
            command.add_argument("--confirm-implementation", action="store_true",
                                 dest="confirm_implementation")
    args = parser.parse_args(argv)
    root = Path(args.project).resolve()
    try:
        if args.command == "start":
            result = start(root, args.mode, authorize_full=args.authorize_full,
                           reviewer=args.reviewer,
                           review_path=Path(args.review) if args.review else None)
        elif args.command == "status":
            result = status(root)
        elif args.command == "approve":
            result = approve(root,
                             map_decisions=Path(args.map_decisions) if args.map_decisions else None,
                             scope=Path(args.scope) if args.scope else None,
                             reviewer=args.reviewer,
                             reviewed_report_sha256=args.reviewed_report_sha256,
                             reviewed_by=args.reviewed_by)
        elif args.command == "apply":
            result = _apply(root, _load(root))
        elif args.command == "guidance":
            result = guidance(root, approve=args.approve)
        elif args.command == "remediate":
            result = remediate(root, args.choice, selected=args.selected,
                               approved_by=args.approved_by, confirm=args.confirm,
                               confirm_scope=args.confirm_scope,
                               confirm_implementation=args.confirm_implementation,
                               maturity_choice=args.maturity_choice,
                               approved_plan_sha256=args.approved_plan_sha256,
                               approved_paths=args.approved_path)
        else:
            result = continue_workflow(root)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        stages = result.get("stages") or []
        stage_values = stages.values() if isinstance(stages, dict) else stages
        hard_failure = any(
            isinstance(stage, dict) and stage.get("status") in {BLOCKED, "failed"}
            for stage in stage_values
        )
        # Awaiting a user review is a successful workflow transition, not a CLI failure.
        return 1 if hard_failure else 0
    except (WorkflowError, ModuleMapError, OSError, ValueError) as error:
        print("adoption_workflow: %s" % error, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
