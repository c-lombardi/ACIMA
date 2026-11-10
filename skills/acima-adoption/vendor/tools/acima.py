#!/usr/bin/env python3
"""ACIMA's developer entry point.

This is a thin, deterministic wrapper over the rules and enforcers in this repository.
It does not implement a second rule engine.

    python3 tools/acima.py assess  --root /path/to/repo     # read-only, changes nothing
    python3 tools/acima.py inspect --root examples/python
    python3 tools/acima.py analyze --root examples/python --format text
    python3 tools/acima.py report  --root examples/python --format markdown
    python3 tools/acima.py verify
"""
from __future__ import annotations

import argparse
import hashlib
from datetime import date, timedelta
import json
import re
import shlex
import shutil
import subprocess
import urllib.parse
import sys
from collections import defaultdict
from pathlib import Path

ACIMA_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ACIMA_ROOT / "conformance"))
from acima_claim import (  # noqa: E402 - path is set above deliberately
    EVIDENCE_FILE, FULL, INVALID, ClaimError, assess as assess_claim,
    load_catalog, load_evidence, render_markdown as render_claim_markdown,
    validate_run_artefact, validate_waivers,
)
CONFIG_NAME = "acima.config.json"
PRUNE = {".git", "node_modules", "bin", "obj", "dist", "build", "target", "out",
         ".venv", "venv", "__pycache__", ".next", ".nuxt", "coverage"}
SOURCE_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".mjs", ".cjs", ".cs", ".go", ".java"}
CATEGORY = {
    "D": "Dependency and structure",
    "L": "Layering inside a module",
    "C": "Contract shape and immutability",
    "A": "Autonomy at runtime",
    "N": "Intent-revealing naming",
    "G": "Governance and exceptions",
}
# Rules the portable reference enforcers deliberately do not decide from source text.
NON_PORTABLE = {
    "ACIMA-C003", "ACIMA-C007", "ACIMA-C008", "ACIMA-L004",
    "ACIMA-A002", "ACIMA-A004", "ACIMA-A010", "ACIMA-A011",
    "ACIMA-A012", "ACIMA-A013", "ACIMA-A014", "ACIMA-A015",
    "ACIMA-G004", "ACIMA-N003",
}
# Five tier rules are implemented by the Python and TypeScript enforcers in this revision; the Go
# and .NET enforcers report them executed:false, so a report must never imply they were decided.
TIER_RULES = {"ACIMA-L005", "ACIMA-L006", "ACIMA-L007", "ACIMA-D010", "ACIMA-G006"}
EXPLICIT_RULES = {"ACIMA-D011", "ACIMA-D012"}
VALUES_RULES = {"ACIMA-A005", "ACIMA-A006"}
COMPOSITION_RULES = {"ACIMA-D013", "ACIMA-D014"}
FUNCTIONAL_RULES = {"ACIMA-D015", "ACIMA-D016"}
LIFECYCLE_RULES = {"ACIMA-A007", "ACIMA-A008", "ACIMA-A009"}
NAMING_RULES = {"ACIMA-N001", "ACIMA-N002", "ACIMA-N003"}
LANGUAGE_GAPS: dict[str, set[str]] = {
    "go": set(TIER_RULES) | EXPLICIT_RULES | VALUES_RULES | COMPOSITION_RULES | FUNCTIONAL_RULES | LIFECYCLE_RULES | NAMING_RULES,
    "dotnet": set(TIER_RULES) | EXPLICIT_RULES | VALUES_RULES | COMPOSITION_RULES | FUNCTIONAL_RULES | LIFECYCLE_RULES | NAMING_RULES,
}
LANGUAGE_MARKERS = {
    "dotnet": (".csproj", ".sln", "global.json"),
    "go": ("go.mod",),
    "typescript": ("package.json", "tsconfig.json"),
    "python": ("pyproject.toml", "setup.py", "setup.cfg", "requirements.txt"),
    "java": ("pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle"),
}


def _walk(root: Path):
    """Yield files under root, pruning build output and hidden paths.

    Pruning uses the path *relative to root*: a repository that happens to live under a
    dot-directory (for example `/home/x/.local/src/app`) must not report zero source files.
    """
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if any(part in PRUNE or part.startswith(".") for part in relative.parts):
            continue
        if path.is_file():
            yield path


class ConfigError(Exception):
    """A configuration file exists but cannot be trusted."""


def read_config(root: Path, name: str = CONFIG_NAME) -> dict | None:
    path = root / name
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ConfigError(f"cannot read config {path}: {error}") from error


def detect_languages(root: Path) -> list[str]:
    found: list[str] = []
    for language, markers in LANGUAGE_MARKERS.items():
        if any((root / marker).exists() for marker in markers):
            found.append(language)
    counts: dict[str, int] = defaultdict(int)
    for path in _walk(root):
        suffix = path.suffix.lower()
        if suffix in SOURCE_EXTENSIONS:
            language = {
                ".py": "python", ".ts": "typescript", ".tsx": "typescript",
                ".js": "typescript", ".mjs": "typescript", ".cjs": "typescript",
                ".cs": "dotnet", ".go": "go", ".java": "java",
            }.get(suffix)
            if language:
                counts[language] += 1
    for language, _count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        if language not in found:
            found.append(language)
    return found


def inspect_project(root: Path, config_name: str = CONFIG_NAME) -> dict:
    root = root.resolve()
    config = read_config(root, config_name)
    languages = detect_languages(root)
    declared = (config or {}).get("language")
    if declared:
        languages = [declared] + [language for language in languages if language != declared]
    counts: dict[str, int] = defaultdict(int)
    for path in _walk(root):
        if path.suffix.lower() in SOURCE_EXTENSIONS:
            counts[path.suffix.lower()] += 1
    enforcer = enforcer_spec(languages[0] if languages else "")
    available = bool(enforcer and enforcer["path"].exists()
                     and shutil.which(enforcer["run"][0]))
    return {
        "root": str(root),
        "config": config_name if config is not None else None,
        "mode": "adopting" if config is not None else "unconfigured",
        "languages": languages,
        "language": languages[0] if languages else None,
        "declaredLevel": (config or {}).get("level"),
        "units": [
            {"id": unit.get("id"), "role": unit.get("role"), "module": unit.get("module"),
             "paths": unit.get("paths", [])}
            for unit in (config or {}).get("units", [])
        ],
        "sourceCounts": dict(sorted(counts.items())),
        "enforcer": enforcer["path"].relative_to(ACIMA_ROOT).as_posix() if enforcer else None,
        "enforcerAvailable": available,
        "next": (
            "Run the adoption preflight before declaring units."
            if config is None else
            "Run `acima analyze --root .` to measure the declared level."
        ),
    }


def enforcer_spec(language: str) -> dict | None:
    specs = {
        "python": {
            "path": ACIMA_ROOT / "examples/python/tools/acima_arch.py",
            "run": [sys.executable, "examples/python/tools/acima_arch.py"],
            "cwd": ACIMA_ROOT,
        },
        "typescript": {
            "path": ACIMA_ROOT / "examples/typescript/tools/acima-arch.mjs",
            "run": ["node", "examples/typescript/tools/acima-arch.mjs"],
            "cwd": ACIMA_ROOT,
        },
        "go": {
            "path": ACIMA_ROOT / "examples/go/tools/archtest/main.go",
            "run": ["go", "run", "./tools/archtest"],
            "cwd": ACIMA_ROOT / "examples/go",
        },
        "dotnet": {
            "path": ACIMA_ROOT / "examples/dotnet/tools/Acima.ArchTests/Program.cs",
            "run": ["dotnet", "run", "--project", "examples/dotnet/tools/Acima.ArchTests", "--"],
            "cwd": ACIMA_ROOT,
        },
    }
    return specs.get(language)


def run_enforcer(root: Path, language: str, config_name: str | None = None,
                 level: str | None = None) -> tuple[int, dict | None, str]:
    spec = enforcer_spec(language)
    if spec is None:
        return 2, None, f"no reference enforcer for language: {language or 'unknown'}"
    if shutil.which(spec["run"][0]) is None:
        return 2, None, f"{spec['run'][0]} is not installed"
    command = list(spec["run"]) + ["--root", str(root.resolve())]
    if config_name:
        command += ["--config", config_name]
    if level:
        command += ["--level", level]
    command += ["--format", "json"]
    try:
        result = subprocess.run(command, cwd=spec["cwd"], capture_output=True, text=True)
    except OSError as error:
        return 2, None, str(error)
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return 2, None, (result.stderr or result.stdout or "enforcer produced no JSON").strip()
    return result.returncode, payload, result.stderr.strip()


def analyze_project(root: Path, language: str | None = None, config_name: str | None = None,
                    level: str | None = None) -> tuple[int, dict | None, str, str]:
    root = root.resolve()
    config = read_config(root, config_name or CONFIG_NAME)
    detected = detect_languages(root)
    selected = language or (config or {}).get("language") or (detected[0] if detected else "")
    code, payload, error = run_enforcer(root, selected, config_name, level)
    return code, payload, error, selected


def summarize(payload: dict) -> dict:
    findings = payload.get("findings", [])
    by_category: dict[str, dict[str, int]] = {}
    for prefix, title in CATEGORY.items():
        by_category[prefix] = {"title": title, "error": 0, "warning": 0, "info": 0}
    for finding in findings:
        prefix = finding.get("rule", "ACIMA-?000").split("-")[1][:1]
        severity = finding.get("severity", "error")
        if prefix in by_category and severity in by_category[prefix]:
            by_category[prefix][severity] += 1
    severity = {key: sum(1 for finding in findings if finding.get("severity") == key)
                for key in ("error", "warning", "info")}
    return {
        "total": len(findings),
        "severity": severity,
        "byCategory": by_category,
        "affectedPaths": sorted({finding.get("path", "") for finding in findings}),
    }


def not_evaluated(language: str) -> list[str]:
    try:
        catalog = json.loads((ACIMA_ROOT / "tools/acima-spec/rules.json").read_text())
    except (OSError, json.JSONDecodeError):
        return sorted(NON_PORTABLE)
    ids = {rule["id"] for rule in catalog.get("rules", [])}
    return sorted(NON_PORTABLE | LANGUAGE_GAPS.get(language, set()) & ids)


def claim_for(root: Path, payload: dict) -> dict:
    """Compute the claim class without letting a bad evidence file crash the report."""
    evidence_path = root / EVIDENCE_FILE
    try:
        evidence = load_evidence(evidence_path)
        return assess_claim(
            payload, load_catalog(ACIMA_ROOT), evidence=evidence,
            evidence_path=EVIDENCE_FILE, root=root,
        )
    except ClaimError as error:
        return {"claim": INVALID, "eligible": False, "error": str(error)}


def report_markdown(root: Path, payload: dict, language: str, config: dict | None,
                    claim: dict | None = None) -> str:
    summary = summarize(payload)
    level = payload.get("level") or (config or {}).get("level") or "unknown"
    lines = [
        "# ACIMA architecture report",
        "",
        f"- Repository: `{root.resolve()}`",
        f"- Language: `{language}`",
        f"- Declared level: `{level}`",
        f"- Findings: **{summary['total']}** "
        f"({summary['severity']['error']} error, {summary['severity']['warning']} warning, "
        f"{summary['severity']['info']} info)",
        "",
        "This is an evidence report over the rules the reference enforcer actually executed. "
        "It is not a productivity metric and it is not a single health score.",
        "",
        "## Findings by category",
        "",
        "| Category | Errors | Warnings | Info |",
        "|---|---:|---:|---:|",
    ]
    for prefix, data in summary["byCategory"].items():
        lines.append(f"| {data['title']} | {data['error']} | {data['warning']} | {data['info']} |")
    lines += ["", "## Findings", ""]
    if not summary["total"]:
        lines.append("No findings were produced by the executed rules.")
    else:
        grouped: dict[str, list[dict]] = defaultdict(list)
        for finding in payload.get("findings", []):
            grouped[finding["rule"]].append(finding)
        for rule in sorted(grouped):
            prefix = rule.split("-")[1][:1]
            lines.append(f"### {CATEGORY.get(prefix, prefix)} — `{rule}`")
            for finding in grouped[rule]:
                evidence = f" — `{finding['evidence']}`" if finding.get("evidence") else ""
                lines.append(f"- {finding['severity']}: {finding['message']} "
                             f"(`{finding['path']}:{finding['line']}`){evidence}")
            lines.append("")
    missing = not_evaluated(language)
    lines += [
        "## Not evaluated by this run",
        "",
        "These rules were not decided by the reference enforcer. A clean run is not evidence "
        "that they pass.",
        "",
    ]
    if missing:
        lines.extend(f"- `{rule}`" for rule in missing)
    else:
        lines.append("- None for this language profile.")
    lines += [
        "",
        "## Evidence",
        "",
        f"- Configuration: `{(config or {}).get('standard', 'unknown')}`",
        "- Rule catalog: `tools/acima-spec/rules.json`",
        "- Enforcer: reference runner for the selected language",
        "",
        "See `docs/status.md` for the verified/proposed capability matrix and "
        "`docs/standard/08-conformance.md` for what counts as a conformance claim.",
        "",
    ]
    if claim:
        lines.append(render_claim_markdown(claim))
    return "\n".join(lines)


VERDICT_MEANING = {
    "ASSESSED": "the reference enforcer ran against the declared unit map",
    "NEEDS_UNIT_MAP": "no acima.config.json, so files cannot be classified into units yet",
    "UNSUPPORTED_LANGUAGE": "no reference enforcer exists for the detected language",
    "UNSUPPORTED_PROFILE": "the declared architecture profile is not supported by this revision",
    "TOOLCHAIN_MISSING": "the toolchain required to run that enforcer is not installed",
    "NO_SOURCE": "no source files were discovered",
    "INVALID_ROOT": "the path given as --root does not exist or is not a directory",
    "INVALID_CONFIG": "acima.config.json exists but cannot be parsed",
    "INVALID_ASSESSMENT": "the enforcer failed or returned no parseable report",
}


def _source_inventory(root: Path) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for path in _walk(root):
        suffix = path.suffix.lower()
        if suffix in SOURCE_EXTENSIONS:
            counts[suffix] += 1
    return dict(sorted(counts.items()))


def _next_steps(report: dict) -> list[str]:
    verdict = report["verdict"]
    steps: list[str] = []
    if verdict == "NEEDS_UNIT_MAP":
        steps.append("Decide module ownership with the people who own the system, then declare "
                     "units in acima.config.json. `preflight.py --write-draft` produces a "
                     "heuristic starting point that a human must review.")
        steps.append("Re-run `acima assess` once the map exists; a repository without a map is "
                     "unassessed, not clean.")
    elif verdict == "UNSUPPORTED_LANGUAGE":
        steps.append("This language has a documented profile but no reference enforcer in this "
                     "revision. An assessment must fail closed rather than report zero findings.")
    elif verdict == "UNSUPPORTED_PROFILE":
        steps.append("This architecture profile is not supported by this revision. The "
                     "assessment must fail closed rather than apply the base unit model.")
    elif verdict == "TOOLCHAIN_MISSING":
        steps.append("Install the toolchain (%s) and re-run the assessment."
                     % report.get("detail", "see docs/status.md"))
    elif verdict == "INVALID_CONFIG":
        steps.append("Fix or remove acima.config.json; a malformed map is a tool failure, not "
                     "an architecture result.")
    elif verdict == "ASSESSED":
        findings = report.get("findings", {})
        if findings.get("total"):
            steps.append("Review the findings above with the module owner. Each one names a rule, "
                         "a path and the evidence the enforcer used.")
            steps.append("Decide whether to adopt: an adoption baseline records existing findings "
                         "as owned, expiring waivers so the gate fails only on new violations.")
        else:
            steps.append("Zero findings require proof that the enforcer saw files: check "
                         "sourceFiles > 0 and the coverage table before trusting the result.")
        if report.get("coverage", {}).get("notExecuted"):
            steps.append("Record manual evidence for the unevaluated rules if a full claim is "
                         "needed (see docs/standard/08-conformance.md).")
    steps.append("Capability and limitation detail: docs/status.md; release gates: "
                 "docs/product-contract.md.")
    return steps


LEVEL_GUIDANCE = {
    "L1": {
        "establishes": "module boundaries and a dependency graph the gate can check",
        "checks": ("cross-module implementation imports, contract dependency purity, cycles, "
                   "unclassified source and unowned exceptions"),
        "requires": ("a reviewed unit map, a measured baseline and owned exceptions for "
                     "pre-existing findings"),
        "doesNotEstablish": ("runtime isolation, persistence ownership or configuration "
                             "ownership"),
        "nextLevelWhen": ("the structural graph is stable and remaining findings sit inside "
                          "modules rather than between them"),
    },
    "L2": {
        "establishes": "contracts that are immutable data and safe to depend on",
        "checks": ("behaviour or framework types in contracts, mutable collections, documented "
                   "contract surface and reviewed API changes"),
        "requires": ("the L1 gate plus contract recreation, API baselines and manual evidence "
                     "for contract judgement rules"),
        "doesNotEstablish": ("persistence ownership, runtime autonomy or effect ownership"),
        "nextLevelWhen": ("contracts change only through reviewed, additive-or-breaking "
                          "decisions"),
    },
    "L3": {
        "establishes": "modules that own their persistence, configuration and externally visible effects",
        "checks": ("persistence and configuration ownership, shared mutable state, static state, "
                   "retry/duplicate/consistency/cancellation semantics and telemetry boundaries"),
        "requires": ("L1 and L2 plus data ownership maps, effect reviews and repository-scoped "
                     "manual evidence for the judgement rules"),
        "doesNotEstablish": ("correctness, performance, security or operational autonomy"),
        "nextLevelWhen": "the owner needs independently deployable or independently owned modules",
    },
}


ARCHITECTURE_MARKERS = ("domain", "application", "infrastructure", "adapters", "ports",
                        "contracts", "services", "api")


def infer_architecture(root: Path, units: list[dict]) -> list[dict]:
    """Low-confidence layout signals, never presented as an ownership decision."""
    names = {path.name.lower() for path in root.iterdir() if path.is_dir()} if root.is_dir() else set()
    signals: list[dict] = []
    layered = sorted(names & {"domain", "application", "infrastructure"})
    if {"domain", "application"} <= names:
        signals.append({"candidate": "layered domain architecture (Clean or hexagonal shape)",
                        "evidence": layered, "confidence": "low"})
    if {"adapters", "ports"} <= names:
        signals.append({"candidate": "ports and adapters (Hexagonal)",
                        "evidence": ["adapters/", "ports/"], "confidence": "low"})
    implementations = [unit for unit in units if unit.get("role") == "implementation"]
    if len(implementations) >= 2 and "domain" in names:
        signals.append({"candidate": "modular monolith or DDD bounded contexts",
                        "evidence": [f"{len(implementations)} implementation units", "domain/"],
                        "confidence": "low"})
    if not signals:
        signals.append({"candidate": "not determined from layout",
                        "evidence": ["no domain/application/adapters markers"],
                        "confidence": "low"})
    return signals


OUTCOME_RECOMMENDED = "RECOMMENDED"
OUTCOME_WITH_LIMITATIONS = "RECOMMENDED_WITH_LIMITATIONS"
OUTCOME_NOT_RECOMMENDED = "NOT_RECOMMENDED"
OUTCOME_INSUFFICIENT = "INSUFFICIENT_EVIDENCE"
OUTCOME_NOT_SUPPORTED = "NOT_SUPPORTED"
ASSESSMENT_OUTCOMES = (
    OUTCOME_RECOMMENDED, OUTCOME_WITH_LIMITATIONS, OUTCOME_NOT_RECOMMENDED,
    OUTCOME_INSUFFICIENT, OUTCOME_NOT_SUPPORTED,
)

BENEFIT_TODAY = "available-today"
BENEFIT_ADOPTION = "achievable-through-adoption"
BENEFIT_WORK = "requires-additional-work"
BENEFIT_NOT_APPLICABLE = "not-applicable"

ENFORCEMENT_TOKENS = (
    "import-linter", "importlinter", "dependency-cruiser", "depcruise", "archunit",
    "netarchtest", "ts-arch", "eslint-plugin-boundaries", "architecture test",
    "architecture-test", "archtest", "acima_arch",
)
BOUNDARY_CONFIG_FILES = (
    "pyproject.toml", "setup.cfg", "package.json", ".importlinter", "importlinter.ini",
    "archunit.properties", "pom.xml", "build.gradle", "build.gradle.kts",
)
IGNORED_LAYOUT_DIRS = frozenset({
    "test", "tests", "__tests__", "spec", "specs", "docs", "doc", "examples", "example",
    "tools", "scripts", "migrations", "build", "dist", "target", "out", "coverage",
    "node_modules", "vendor", ".venv", "venv", "bin", "obj",
})


def _dimension(status: str, summary: str, evidence: list[str],
               confidence: str = "medium") -> dict:
    return {"status": status, "summary": summary, "evidence": evidence,
            "confidence": confidence}


def _source_layout(root: Path) -> dict:
    files = [path for path in _walk(root) if path.suffix.lower() in SOURCE_EXTENSIONS]
    relative = [path.relative_to(root) for path in files]
    modules: set[str] = set()
    for item in relative:
        parts = [part for part in item.parent.parts if part not in ("", ".")]
        if any(part.lower() in IGNORED_LAYOUT_DIRS for part in parts):
            continue
        if parts:
            modules.add("/".join(parts))
    return {
        "sourceFiles": len(files),
        "moduleDirectories": sorted(modules),
        "rootSourceFiles": sum(1 for item in relative if item.parent == Path(".")),
    }


def _architectural_substance(root: Path, config: dict | None) -> dict:
    if config:
        units = config.get("units") or []
        modules = sorted({str(unit.get("module")) for unit in units if unit.get("module")})
        implementations = [unit for unit in units if unit.get("role") == "implementation"]
        contracts = [unit for unit in units
                     if unit.get("role") in ("contracts", "port")]
        evidence = [f"{len(units)} declared unit(s)"]
        if modules:
            evidence.append("modules: " + ", ".join(modules))
        if implementations:
            evidence.append(f"{len(implementations)} implementation unit(s)")
        if contracts:
            evidence.append(f"{len(contracts)} contract/port unit(s)")
        if len(modules) >= 2 or (implementations and contracts):
            return _dimension(
                "meaningful",
                "The declared unit map identifies distinct module ownership or a "
                "contracts/implementation boundary worth enforcing.",
                evidence, "medium")
        if units:
            return _dimension(
                "weak",
                "Units are declared, but they do not identify distinct module ownership "
                "or a contract boundary that ACIMA could protect.",
                evidence, "medium")
        return _dimension("unknown", "acima.config.json declares no units.",
                          evidence, "low")

    layout = _source_layout(root)
    if layout["sourceFiles"] <= 1 or not layout["moduleDirectories"]:
        return _dimension(
            "none",
            "No meaningful ownership boundaries were found: the repository is a single "
            "source area, not a set of modules.",
            [f"{layout['sourceFiles']} source file(s)",
             f"{len(layout['moduleDirectories'])} module director(ies)"],
            "medium")
    if len(layout["moduleDirectories"]) >= 2:
        return _dimension(
            "candidate",
            "The layout suggests more than one source-owning area, but no unit map declares "
            "who owns each one.",
            layout["moduleDirectories"][:8], "low")
    return _dimension(
        "unknown",
        "Source files exist, but the layout does not establish module ownership and no "
        "unit map was declared.",
        [f"{layout['sourceFiles']} source files in {len(layout['moduleDirectories'])} "
         "source director(ies)"], "low")


def _existing_enforcement(root: Path) -> dict:
    mechanisms: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def add(kind: str, path: str, detail: str) -> None:
        key = (kind, path)
        if key in seen:
            return
        seen.add(key)
        mechanisms.append({"kind": kind, "path": path, "detail": detail,
                           "execution": "configured-not-observed"})

    for entry in _gate_workflows(root):
        if entry.get("validInvocations"):
            first = entry["validInvocations"][0]
            add("acima-gate", entry["path"],
                "workflow invokes an ACIMA enforcer" +
                (f" at {first['level']}" if first.get("level") else ""))

    workflow_dir = root / ".github/workflows"
    if workflow_dir.is_dir():
        for path in sorted(list(workflow_dir.glob("*.yml")) + list(workflow_dir.glob("*.yaml"))):
            try:
                text = path.read_text(encoding="utf-8", errors="replace").lower()
            except OSError:
                continue
            hits = sorted(token for token in ENFORCEMENT_TOKENS if token in text)
            if hits:
                add("ci-boundary-check", path.relative_to(root).as_posix(),
                    "CI workflow mentions " + ", ".join(hits))

    for name in BOUNDARY_CONFIG_FILES:
        path = root / name
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace").lower()
        except OSError:
            continue
        hits = sorted(token for token in ENFORCEMENT_TOKENS if token in text)
        if hits:
            add("boundary-configuration", name, "configuration declares " + ", ".join(hits))

    for pattern in ("*.csproj", "dependency-cruiser.*", ".dependency-cruiser.*"):
        for path in sorted(root.glob(pattern)):
            try:
                text = path.read_text(encoding="utf-8", errors="replace").lower()
            except OSError:
                continue
            hits = sorted(token for token in ENFORCEMENT_TOKENS if token in text)
            if hits:
                add("boundary-configuration", path.relative_to(root).as_posix(),
                    "configuration declares " + ", ".join(hits))

    for path in sorted(_walk(root)):
        relative = path.relative_to(root).as_posix()
        if not re.search(
                r"(^|/)(test[_-].*arch|.*arch.*test|.*architecture.*test|"
                r".*boundar(y|ies).*test)", relative.lower()):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace").lower()
        except OSError:
            continue
        if any(token in text for token in ("acima", "importlinter", "dependency-cruiser",
                                           "archunit", "netarchtest", "architecture",
                                           "boundary", "boundaries")):
            add("architecture-test", relative, "test file asserts architecture constraints")

    has_acima = any(item["kind"] == "acima-gate" for item in mechanisms)
    has_linter = any(item["kind"] == "boundary-configuration" for item in mechanisms)
    has_test = any(item["kind"] == "architecture-test" for item in mechanisms)
    has_ci = any(item["kind"] == "ci-boundary-check" for item in mechanisms)
    strong = has_acima or (has_ci and (has_linter or has_test))
    status = "strong" if strong else ("partial" if mechanisms else "none")
    if status == "strong":
        summary = ("Configured boundary enforcement was found"
                   + (", including an ACIMA gate" if has_acima else "")
                   + "; execution was not observed by this read-only assessment.")
        confidence = "medium"
    elif status == "partial":
        summary = ("Some boundary-related checks were found, but their CI coverage or "
                   "scope is incomplete.")
        confidence = "low"
    else:
        summary = "No repository evidence of automated boundary enforcement was found."
        confidence = "medium"
    return {
        "status": status,
        "summary": summary,
        "mechanisms": mechanisms,
        "execution": "configured-not-observed",
        "confidence": confidence,
    }


def _adoption_cost(report: dict, config: dict | None, substance: dict,
                   enforcement: dict, findings: dict) -> dict:
    errors = (findings.get("bySeverity") or {}).get("error", 0)
    rules = findings.get("byRule") or {}
    drivers: list[str] = []
    if config is None:
        drivers.append("declare and review a unit map")
    if enforcement["status"] == "none":
        drivers.append("add and operate an automated pull-request gate")
    elif enforcement["status"] == "strong":
        drivers.append("reconcile ACIMA with the checks already in place")
    if errors:
        drivers.append(f"remediate or own {errors} existing error finding(s)")
    if any(str(rule).startswith(("ACIMA-D", "ACIMA-C", "ACIMA-A")) for rule in rules):
        drivers.append("review the boundaries implicated by the findings")
    if report.get("requestedLevel") in ("L2", "L3"):
        drivers.append("contract and manual-evidence work for the requested level")
    if not drivers:
        drivers.append("maintain the gate, catalog updates and waiver review")

    if substance["status"] in ("none", "weak"):
        status = "low"
        summary = "Low: there are no meaningful module boundaries to configure or enforce."
    elif enforcement["status"] == "none" and errors:
        status = "high"
        summary = ("High: existing boundary findings must be fixed or owned while a new gate "
                   "is introduced.")
    elif config is not None and enforcement["status"] == "strong" and not errors:
        status = "low"
        summary = "Low: the unit map exists and existing checks already cover the boundaries."
    else:
        status = "moderate"
        summary = ("Moderate: adoption needs configuration, ownership decisions and a gate, "
                   "but does not require a rewrite.")
    return {"status": status, "summary": summary, "evidence": drivers,
            "confidence": "medium", "drivers": drivers,
            "organizational": ["confirm module ownership", "assign exception owners"],
            "migration": "No source rewrite is required; existing findings may be fixed or owned.",
            "maintenance": ("Ongoing: review exceptions before they expire and update the unit "
                            "map when ownership or modules change."),
            "estimate": "Qualitative estimate only; no time or price is inferred."}


def _conditional_benefits(report: dict, config: dict | None, substance: dict,
                          enforcement: dict, errors: int) -> list[dict]:
    details: list[dict] = []

    def add(benefit: str, classification: str, basis: str) -> None:
        details.append({"benefit": benefit, "classification": classification,
                        "basis": basis})

    if config is not None and report.get("findings") is not None:
        add("The reference enforcer can report boundary violations with the rule, path "
            "and remedy today.", BENEFIT_TODAY,
            "the assessment ran the enforcer; this is a report, not a merge gate")
    else:
        add("A read-only assessment can inspect the repository without changing it.",
            BENEFIT_TODAY, "the assessment reads source and configuration only")

    if substance["status"] in ("meaningful", "candidate"):
        if enforcement["status"] != "strong":
            add("A pull-request gate could reject new cross-module implementation imports "
                "and name the remedy.", BENEFIT_ADOPTION,
                "this becomes true only after a gate is approved, added and running")
            add("Existing findings can be frozen as owned, expiring exceptions so the gate "
                "fails only on new violations.", BENEFIT_ADOPTION,
                "requires explicit ownership, scope and expiry decisions")
        else:
            add("ACIMA could add contract and ownership checks beyond the existing boundary "
                "checks.", BENEFIT_ADOPTION,
                "the existing checks already cover part of the boundary guarantee")
    if config is None:
        add("Declaring and reviewing the unit map is required before any automated check.",
            BENEFIT_WORK, "ownership is a human decision, not a directory-name inference")
    if errors:
        add("Each existing finding must be fixed or covered by an owned exception.",
            BENEFIT_WORK, "the assessment found errors that no gate can honestly ignore")
    if enforcement["status"] == "none":
        add("A CI gate must be approved, added and observed on a pull request.",
            BENEFIT_WORK, "repository configuration alone is not an observed gate")
    if enforcement["status"] == "strong":
        add("A new boundary gate is not applicable; configured checks already exist.",
            BENEFIT_NOT_APPLICABLE,
            "only their execution and coverage remain unverified")
    if substance["status"] in ("none", "weak"):
        add("Module-boundary enforcement is not applicable because no meaningful module "
            "ownership was found.", BENEFIT_NOT_APPLICABLE,
            "there is no boundary for ACIMA to make executable")
    return details


def _recommendation(verdict: str, mode: str, substance: dict, enforcement: dict,
                    incremental: dict, cost: dict, errors: int,
                    config: dict | None) -> tuple[str, str]:
    if verdict in ("UNSUPPORTED_LANGUAGE", "UNSUPPORTED_PROFILE") or mode != "base":
        return (OUTCOME_NOT_SUPPORTED,
                "The language or architecture profile is explicitly outside the supported "
                "assessment surface.")
    if verdict in ("NO_SOURCE", "INVALID_ROOT", "INVALID_CONFIG", "TOOLCHAIN_MISSING",
                   "INVALID_ASSESSMENT"):
        return (OUTCOME_INSUFFICIENT,
                "The assessment could not produce trustworthy architectural evidence.")
    if substance["status"] in ("none", "weak"):
        return (OUTCOME_NOT_RECOMMENDED,
                "There are no meaningful ownership boundaries for ACIMA to enforce, so it "
                "would add process without adding a guarantee.")
    if enforcement["status"] == "strong" and errors == 0:
        return (OUTCOME_NOT_RECOMMENDED,
                "Existing configured checks already cover the boundary guarantee, and no "
                "meaningful additional guarantee was found.")
    if incremental["status"] == "none":
        return (OUTCOME_NOT_RECOMMENDED,
                "No incremental boundary guarantee was identified from the available evidence.")
    if incremental["status"] == "limited" and cost["status"] == "high":
        return (OUTCOME_NOT_RECOMMENDED,
                "Any additional guarantee is limited while the adoption and migration cost is high.")
    if substance["status"] == "unknown":
        return (OUTCOME_INSUFFICIENT,
                "Module ownership is not established, so a fit recommendation would be a guess.")
    if errors:
        return (OUTCOME_WITH_LIMITATIONS,
                "The boundaries are meaningful, but existing findings need remediation or "
                "owned exceptions before a gate can be honest.")
    if cost["status"] == "high":
        return (OUTCOME_WITH_LIMITATIONS,
                "The boundaries are meaningful, but adoption carries high migration or "
                "enforcement cost.")
    if config is None or substance["status"] == "candidate":
        return (OUTCOME_WITH_LIMITATIONS,
                "The layout suggests meaningful boundaries, but unit ownership is not declared "
                "or approved.")
    if enforcement["status"] in ("strong", "partial") and incremental["status"] == "limited":
        return (OUTCOME_WITH_LIMITATIONS,
                "Existing checks cover part of the boundary guarantee; ACIMA adds a narrower "
                "set of contract and ownership checks.")
    return (OUTCOME_RECOMMENDED,
            "Meaningful boundaries exist, no effective automated enforcement covers them, and "
            "the smallest adoption can add a real gate.")


def _assessment_benefits(details: list[dict]) -> list[str]:
    """Compatibility view: only capabilities that exist today without adoption work."""
    return [item["benefit"] for item in details
            if item["classification"] == BENEFIT_TODAY]


def build_assessment_result(report: dict, config: dict | None) -> dict:
    """Evidence-based fit assessment: dimensions first, recommendation second.

    A clean report is one input, never a recommendation. The result separates observed facts,
    inferred layout characteristics, unresolved questions and the decision.
    """
    root = Path(report.get("root") or ".")
    verdict = report.get("verdict")
    findings = report.get("findings") or {}
    coverage = report.get("coverage") or {}
    errors = (findings.get("bySeverity") or {}).get("error") if findings else 0
    mode = (config or {}).get("mode") or "base"
    layout = _source_layout(root)
    substance = _architectural_substance(root, config)
    enforcement = _existing_enforcement(root)
    units = (config or {}).get("units") or []

    if verdict in ("UNSUPPORTED_LANGUAGE", "UNSUPPORTED_PROFILE") or mode != "base":
        technical = _dimension(
            "unsupported",
            "The language or architecture profile is not supported by this assessment revision.",
            [f"verdict: {verdict}", f"mode: {mode}"], "high")
    elif verdict in ("NO_SOURCE", "INVALID_ROOT"):
        technical = _dimension(
            "unknown", "There is no analysable application to assess.",
            [f"verdict: {verdict}"], "low")
    elif verdict in ("INVALID_CONFIG", "TOOLCHAIN_MISSING", "INVALID_ASSESSMENT"):
        technical = _dimension(
            "unknown", "The tooling could not establish technical compatibility.",
            [f"verdict: {verdict}"], "low")
    elif config is None:
        technical = _dimension(
            "partial",
            "The language is supported, but no unit map expresses the boundaries.",
            ["no acima.config.json", f"language: {report.get('language') or 'unknown'}"],
            "medium")
    elif not units:
        technical = _dimension("partial", "The configuration declares no units.", [], "low")
    else:
        technical = _dimension(
            "compatible",
            "The language and base architecture mode can express ACIMA's boundaries.",
            [f"language: {report.get('language') or 'unknown'}", "mode: base",
             f"{len(units)} declared unit(s)"], "medium")

    if technical["status"] == "unsupported":
        practical = _dimension("unsupported", technical["summary"], technical["evidence"], "high")
    elif substance["status"] == "none":
        practical = _dimension(
            "not-applicable",
            "ACIMA's module-boundary requirements do not apply to this single ownership area.",
            substance["evidence"], "medium")
    elif verdict == "NO_SOURCE":
        practical = _dimension("unknown", "No application code was found to assess.",
                              ["no source files"], "low")
    else:
        practical = _dimension(
            "applicable",
            "The base architecture mode is applicable; deployment topology and framework "
            "choice remain the team's decisions.", [f"mode: {mode}"], "medium")

    if substance["status"] in ("none", "weak"):
        incremental = _dimension(
            "none", "No additional boundary guarantee is available because there is no "
            "meaningful boundary to enforce.", substance["evidence"], "medium")
    elif enforcement["status"] == "strong":
        incremental = _dimension(
            "none" if errors == 0 else "limited",
            "Existing checks already cover the core boundary guarantee"
            + ("; the remaining value is contract and ownership detail." if errors else "."),
            [item["path"] for item in enforcement["mechanisms"]], "medium")
    elif substance["status"] == "candidate" or config is None:
        incremental = _dimension(
            "high", "Declaring the units and adding a gate would make otherwise implicit "
            "boundaries executable.", substance["evidence"], "low")
    else:
        incremental = _dimension(
            "high", "No effective automated boundary enforcement was found, so a gate would "
            "add a real guarantee.", substance["evidence"], "medium")

    cost = _adoption_cost(report, config, substance, enforcement, findings)
    outcome, why = _recommendation(verdict, mode, substance, enforcement, incremental,
                                   cost, errors, config)

    if outcome in (OUTCOME_NOT_SUPPORTED, OUTCOME_INSUFFICIENT):
        confidence = "low"
    elif config is None:
        confidence = "low"
    else:
        confidence = "medium"

    benefit_details = _conditional_benefits(report, config, substance, enforcement, errors)
    what_it_will_not_solve = [
        "It does not choose module ownership for the team.",
        "It does not migrate persistence or split services.",
        "It does not prove correctness, performance or security.",
    ]
    if enforcement["status"] == "none":
        what_it_will_not_solve.append(
            "It does not block merges until a gate is approved, added and running.")
    if enforcement["status"] == "strong":
        what_it_will_not_solve.append(
            "It does not prove that the existing configured checks actually run or pass.")

    unknowns = [
        "The application's purpose and business requirements were not inferred from names; "
        "the owner must confirm them.",
        "Runtime behaviour, data ownership and operational autonomy are not established by a "
        "static read-only assessment.",
    ]
    if config is None:
        unknowns.append("Module ownership is not declared, so findings cannot be attributed "
                        "to an owner.")
    if enforcement["status"] in ("strong", "partial"):
        unknowns.append("Configured boundary checks were not executed by this assessment; "
                        "their actual coverage and enforcement are unverified.")
    if coverage and not coverage.get("complete"):
        unknowns.append(f"{len(coverage.get('notExecuted') or [])} required rule(s) did not "
                        "execute; they are not evidence of a pass.")

    questions: list[str] = []
    if config is None and substance["status"] in ("candidate", "unknown"):
        questions.append("Who owns each source area, and does the proposed unit map match "
                         "that ownership?")
    if enforcement["status"] in ("strong", "partial"):
        questions.append("Are the configured checks required on the default branch and "
                         "currently passing?")
    if errors:
        questions.append("Which existing findings will be fixed before adoption, and which "
                         "need owned, expiring exceptions?")
    if enforcement["status"] == "none" and substance["status"] in ("meaningful", "candidate"):
        questions.append("Is a pull-request gate approved, and who will own it?")
    questions = questions[:3]

    unit_map = report.get("unitMap") or {}
    application = (f"{report.get('language') or 'Unknown-language'} repository with "
                   f"{report.get('sourceFiles', layout['sourceFiles'])} source file(s); "
                   + (f"{unit_map.get('count', 0)} declared unit(s)."
                      if unit_map.get("present") else "no unit map is declared."))
    what_acima_adds = {
        "high": "It would make the declared boundaries executable and fail a new violation "
                "at the boundary.",
        "limited": "It would add contract and ownership checks beyond the existing boundary "
                   "checks.",
        "none": "No additional boundary guarantee was identified from the available evidence.",
        "unknown": "The additional guarantee cannot be established without unit ownership.",
    }[incremental["status"]]

    explanation = {
        "application": application,
        "boundaries": substance["evidence"],
        "existingEnforcement": enforcement["summary"],
        "whatAcimaAdds": what_acima_adds,
        "whatAcimaWillNotAdd": what_it_will_not_solve,
        "adoptionCost": cost["summary"],
        "maintenanceCost": cost["maintenance"],
        "why": why,
        "confidence": confidence,
        "unresolvedQuestions": questions,
    }
    recommendations = {
        OUTCOME_RECOMMENDED: f"ACIMA is a good fit. {why}",
        OUTCOME_WITH_LIMITATIONS: f"ACIMA is worth adopting with limitations. {why}",
        OUTCOME_NOT_RECOMMENDED: f"Do not adopt ACIMA for this repository. {why}",
        OUTCOME_INSUFFICIENT: f"There is not enough evidence to recommend adoption. {why}",
        OUTCOME_NOT_SUPPORTED: f"ACIMA cannot assess this repository. {why}",
    }
    legacy = outcome.lower().replace("_", "-")
    level = ((report.get("assessment") or {}).get("level")
             or report.get("requestedLevel") or "L1")
    return {
        "facts": {
            "languages": report.get("languages"),
            "sourceFiles": report.get("sourceFiles", layout["sourceFiles"]),
            "layout": layout,
            "unitMap": report.get("unitMap"),
            "reportedLevel": (report.get("assessment") or {}).get("level"),
            "purpose": None,
            "purposeBasis": "not inferred from repository names; the owner must confirm it",
        },
        "inferences": infer_architecture(root, units),
        "dimensions": {
            "technicalCompatibility": technical,
            "architecturalSubstance": substance,
            "existingEnforcement": _dimension(
                enforcement["status"], enforcement["summary"],
                [item["path"] for item in enforcement["mechanisms"]],
                enforcement["confidence"]),
            "incrementalValue": incremental,
            "adoptionCost": cost,
            "practicalApplicability": practical,
        },
        "existingEnforcement": enforcement,
        "unknowns": unknowns,
        "unresolvedQuestions": questions,
        "fit": outcome,
        "outcome": outcome,
        "fitLegacy": legacy,
        "confidence": confidence,
        "recommendation": recommendations[outcome],
        "why": why,
        "benefits": _assessment_benefits(benefit_details),
        "benefitDetails": benefit_details,
        "whatItWillNotSolve": what_it_will_not_solve,
        "levelGuidance": LEVEL_GUIDANCE.get(level or "L1", LEVEL_GUIDANCE["L1"]),
        "recommendedNextAction": (report.get("nextSteps") or [None])[0],
        "explanation": explanation,
    }


def assess_project(root: Path, language: str | None = None,
                   level: str | None = None) -> tuple[int, dict]:
    """Read-only compatibility assessment: never writes to the target repository."""
    root = root.resolve()
    if not root.is_dir():
        return 2, {
            "readOnly": True,
            "root": str(root),
            "verdict": "INVALID_ROOT",
            "verdictMeaning": VERDICT_MEANING["INVALID_ROOT"],
            "error": "no such directory: %s" % root,
            "nextSteps": ["Pass the repository root: `acima assess --root <path>`. A missing "
                          "path is a tool failure, not an empty architecture."],
            "limitation": "Read-only assessment; nothing was read and nothing was written.",
        }
    counts = _source_inventory(root)
    languages = detect_languages(root)
    report: dict = {
        "readOnly": True,
        "root": str(root),
        "languages": languages,
        "sourceFiles": sum(counts.values()),
        "sourceCounts": counts,
        "requestedLevel": level or "L1",
        "limitation": ("Read-only assessment. It is not a conformance claim and it computes no "
                       "health score; rules without evidence are reported as not evaluated."),
    }

    if report["sourceFiles"] == 0:
        report["verdict"] = "NO_SOURCE"
        report["verdictMeaning"] = VERDICT_MEANING["NO_SOURCE"]
        report["nextSteps"] = _next_steps(report)
        report["assessmentResult"] = build_assessment_result(report, None)
        return 0, report

    try:
        config = read_config(root)
    except ConfigError as error:
        report.update({"verdict": "INVALID_CONFIG",
                       "verdictMeaning": VERDICT_MEANING["INVALID_CONFIG"],
                       "error": str(error)})
        report["nextSteps"] = _next_steps(report)
        report["assessmentResult"] = build_assessment_result(report, None)
        return 2, report

    selected = language or (config or {}).get("language") or (languages[0] if languages else None)
    units = (config or {}).get("units", [])
    report["language"] = selected
    report["unitMap"] = {
        "present": config is not None,
        "declaredMode": (config or {}).get("mode", "base" if config else None),
        "count": len(units),
        "modules": sorted({u.get("module") for u in units if u.get("module")}),
        "units": [{"id": u.get("id"), "role": u.get("role"), "module": u.get("module"),
                   "paths": u.get("paths", [])} for u in units],
    }
    catalog = json.loads((ACIMA_ROOT / "tools/acima-spec/rules.json").read_text(encoding="utf-8"))
    manual = sorted(rule["id"] for rule in catalog["rules"]
                    if rule.get("automation") == "manual")
    report["applicable"] = {
        "catalogRules": len(catalog["rules"]),
        "portableRules": len(catalog["rules"]) - len(manual),
        "manualEvidence": manual,
    }

    def finish(verdict: str, code: int = 0, **extra) -> tuple[int, dict]:
        report["verdict"] = verdict
        report["verdictMeaning"] = VERDICT_MEANING[verdict]
        report.update(extra)
        report["nextSteps"] = _next_steps(report)
        report["assessmentResult"] = build_assessment_result(report, config)
        return code, report

    mode = (config or {}).get("mode") or "base"
    if mode != "base" or (root / "acima.topology.json").is_file():
        return finish("UNSUPPORTED_PROFILE",
                      detail="architecture mode %r is not supported by this revision" % mode)

    spec = enforcer_spec(selected or "")
    if spec is None:
        return finish("UNSUPPORTED_LANGUAGE")
    if shutil.which(spec["run"][0]) is None:
        return finish("TOOLCHAIN_MISSING", detail="%s is not installed" % spec["run"][0])
    if config is None:
        return finish("NEEDS_UNIT_MAP")

    code, payload, error = run_enforcer(root, selected, None, level)
    if payload is None:
        return finish("INVALID_ASSESSMENT", 2, error=error)
    execution = payload.get("execution") or {}
    executed = sorted(rule for rule, value in execution.items() if value.get("executed") is True)
    not_executed = {rule: value.get("reason", "")
                    for rule, value in execution.items() if value.get("executed") is False}
    findings = payload.get("findings", [])
    by_rule: dict[str, int] = defaultdict(int)
    for finding in findings:
        by_rule[finding["rule"]] += 1
    report["coverage"] = {
        "executed": len(executed),
        "notExecuted": sorted(not_executed),
        "notExecutedReasons": not_executed,
        "complete": not not_executed,
    }
    report["findings"] = {
        "total": len(findings),
        "bySeverity": {key: sum(1 for f in findings if f.get("severity") == key)
                       for key in ("error", "warning", "info")},
        "byRule": dict(sorted(by_rule.items())),
        "items": findings,
    }
    report["assessment"] = {
        "standard": payload.get("standard"), "level": payload.get("level"),
        "analysedSourceFiles": payload.get("sourceFiles"), "profile": payload.get("profile"),
    }
    return finish("ASSESSED", 0)


def assess_text(report: dict) -> str:
    lines = [
        "ACIMA assessment (read-only)",
        "  repository  %s" % report["root"],
        "  verdict     %s - %s" % (report["verdict"], report["verdictMeaning"]),
        "  language    %s - sources %s" % (report.get("language") or "unknown",
                                           report.get("sourceFiles", 0)),
    ]
    unit_map = report.get("unitMap") or {}
    declared = "declared: %s units" % unit_map.get("count", 0) if unit_map.get("present") else "absent"
    lines.append("  unit map    %s" % declared)
    if unit_map.get("modules"):
        shown = ", ".join(unit_map["modules"][:8])
        lines.append("  modules     %s%s" % (shown, " ..." if len(unit_map["modules"]) > 8 else ""))
    result = report.get("assessmentResult") or {}
    if result:
        lines.append("  fit         %s (%s confidence)" % (result["fit"], result["confidence"]))
        lines.append("  recommend   " + result["recommendation"])
        for label, key in (("technical  ", "technicalCompatibility"),
                           ("boundaries ", "architecturalSubstance"),
                           ("enforcement", "existingEnforcement"),
                           ("value      ", "incrementalValue"),
                           ("cost       ", "adoptionCost"),
                           ("applicable ", "practicalApplicability")):
            dimension = (result.get("dimensions") or {}).get(key) or {}
            if dimension:
                lines.append("  %s %s - %s" % (label, dimension["status"],
                                                dimension["summary"]))
        for signal in result.get("inferences") or []:
            lines.append("  layout      %s - evidence: %s (confidence: %s)"
                         % (signal["candidate"], ", ".join(signal["evidence"]) or "none",
                            signal["confidence"]))
    coverage = report.get("coverage")
    if coverage:
        lines.append("  coverage    %s rules executed - %s not evaluated"
                     % (coverage["executed"], len(coverage["notExecuted"])))
    findings = report.get("findings")
    if findings:
        severity = findings["bySeverity"]
        lines.append("  findings    %s (%s error, %s warning, %s info)"
                     % (findings["total"], severity["error"], severity["warning"],
                        severity["info"]))
        for rule, count in findings["byRule"].items():
            lines.append("    %-12s %s" % (rule, count))
        for item in findings["items"][:12]:
            lines.append("    - %s %s:%s - %s"
                         % (item["rule"], item["path"], item["line"], item["message"]))
        if findings["total"] > 12:
            lines.append("    ... %s more (use --format json for all)"
                         % (findings["total"] - 12))
    manual = (report.get("applicable") or {}).get("manualEvidence") or []
    if manual:
        lines.append("  human       %s rule(s) need recorded evidence: %s"
                     % (len(manual), ", ".join(manual)))
    if report.get("error"):
        lines.append("  error       %s" % report["error"])
    lines.append("")
    lines.append("  This is an assessment, not a conformance claim and not a score.")
    lines.append("  next")
    for index, step in enumerate(report.get("nextSteps", []), 1):
        lines.append("    %s. %s" % (index, step))
    return chr(10).join(lines)


def assess_markdown(report: dict) -> str:
    lines = [
        "# ACIMA assessment",
        "",
        "- Repository: `%s`" % report["root"],
        "- Verdict: **%s** - %s" % (report["verdict"], report["verdictMeaning"]),
        "- Language: `%s` - source files: %s" % (report.get("language") or "unknown",
                                                 report.get("sourceFiles", 0)),
        "- Level requested: `%s`" % report.get("requestedLevel"),
        "",
        "> Read-only assessment. No conformance claim, no health score, no code changes.",
        "",
        "## Recommendation",
        "",
        "**%s** — %s" % (report.get("assessmentResult", {}).get("fit"),
                          report.get("assessmentResult", {}).get("recommendation")),
        "",
    ]
    dimensions = (report.get("assessmentResult") or {}).get("dimensions") or {}
    if dimensions:
        lines += ["| Dimension | Evidence status | Summary |", "|---|---|---|"]
        for label, key in (("Technical compatibility", "technicalCompatibility"),
                           ("Architectural substance", "architecturalSubstance"),
                           ("Existing enforcement", "existingEnforcement"),
                           ("Incremental value", "incrementalValue"),
                           ("Adoption cost", "adoptionCost"),
                           ("Practical applicability", "practicalApplicability")):
            value = dimensions.get(key) or {}
            lines.append("| %s | `%s` | %s |" % (label, value.get("status", ""),
                                                  value.get("summary", "")))
        lines.append("")
    explanation = (report.get("assessmentResult") or {}).get("explanation") or {}
    if explanation:
        lines += ["## Why this recommendation", "", explanation.get("why", ""), "",
                  "**What ACIMA adds:** " + explanation.get("whatAcimaAdds", ""), "",
                  "**Adoption cost:** " + explanation.get("adoptionCost", ""), ""]
    lines += ["## Unit map", "",]
    unit_map = report.get("unitMap") or {}
    if unit_map.get("present"):
        lines.append("- Declared units: **%s**" % unit_map.get("count", 0))
        lines.append("- Modules: %s" % (", ".join(unit_map.get("modules") or []) or "none"))
    else:
        lines.append("- No `acima.config.json`: the repository cannot be classified into units, "
                     "so no architectural verdict is drawn.")
    coverage = report.get("coverage")
    if coverage:
        lines += ["", "## Verification coverage", "",
                  "- Rules executed: **%s**" % coverage["executed"],
                  "- Not evaluated: **%s** (%s)"
                  % (len(coverage["notExecuted"]),
                     ", ".join(coverage["notExecuted"]) or "none")]
    findings = report.get("findings")
    if findings:
        lines += ["", "## Findings", "",
                  "Total **%s** (%s error, %s warning, %s info)."
                  % (findings["total"], findings["bySeverity"]["error"],
                     findings["bySeverity"]["warning"], findings["bySeverity"]["info"]), ""]
        if findings["byRule"]:
            lines += ["| Rule | Count |", "|---|---:|"]
            lines += ["| `%s` | %s |" % (rule, count)
                      for rule, count in findings["byRule"].items()]
            lines.append("")
        for item in findings["items"][:40]:
            lines.append("- `%s` %s (`%s:%s`)"
                         % (item["rule"], item["message"], item["path"], item["line"]))
    manual = (report.get("applicable") or {}).get("manualEvidence") or []
    if manual:
        lines += ["", "## Requires human evidence", "",
                  "These rules were not decided by the enforcer: "
                  + ", ".join("`%s`" % rule for rule in manual) + "."]
    lines += ["", "## Recommended next steps", ""]
    lines += ["%s. %s" % (index, step)
              for index, step in enumerate(report.get("nextSteps", []), 1)]
    return chr(10).join(lines)


def _enforcer_command(language: str | None) -> str:
    return {
        "python": "python3 examples/python/tools/acima_arch.py",
        "typescript": "node examples/typescript/tools/acima-arch.mjs",
        "go": "(cd examples/go && go run ./tools/archtest)",
        "dotnet": "dotnet run --project examples/dotnet/tools/Acima.ArchTests --",
    }.get(language or "", "the reference enforcer for your language")


def _waiver_document(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


STEP_NOT_STARTED = "NOT_STARTED"
STEP_READY = "READY"
STEP_IN_PROGRESS = "IN_PROGRESS"
STEP_BLOCKED = "BLOCKED"
STEP_COMPLETE = "COMPLETE"
STEP_NOT_APPLICABLE = "NOT_APPLICABLE"
STEP_UNKNOWN = "UNKNOWN"
STATE_LABEL = {
    STEP_NOT_STARTED: "not started",
    STEP_READY: "ready",
    STEP_IN_PROGRESS: "in progress",
    STEP_BLOCKED: "blocked",
    STEP_COMPLETE: "complete",
    STEP_NOT_APPLICABLE: "not applicable",
    STEP_UNKNOWN: "unverified",
}
CALIBRATION_MANIFEST = Path("skills/acima-adoption/manifest.json")
def _step(number: int, name: str, state: str, evidence: str, remedy: str = "") -> dict:
    return {"n": number, "name": name, "state": state, "label": STATE_LABEL[state],
            "verified": state == STEP_COMPLETE, "evidence": evidence, "remedy": remedy}


def execution_context() -> dict:
    """Resolve where this copy of the tool is running and which commands are valid there."""
    root = ACIMA_ROOT
    if (root / "skills/acima-adoption").is_dir():
        context, skill_root = "checkout", root / "skills/acima-adoption"
    elif (root / "MANIFEST.json").is_file():
        context, skill_root = "vendor", root.parent
    else:
        context, skill_root = "installed", root

    def python(path: Path) -> str:
        return 'python3 "%s"' % path.as_posix()

    enforcers = {
        "python": python(root / "examples/python/tools/acima_arch.py"),
        "typescript": 'node "%s"' % (root / "examples/typescript/tools/acima-arch.mjs").as_posix(),
        "go": '(cd "%s" && go run ./tools/archtest)' % (root / "examples/go").as_posix(),
        "dotnet": 'dotnet run --project "%s" --'
                  % (root / "examples/dotnet/tools/Acima.ArchTests").as_posix(),
        "java": None,
    }
    return {
        "context": context,
        "standardRoot": str(root),
        "skillRoot": str(skill_root),
        "commands": {
            "acima": python(root / "tools/acima.py"),
            "preflight": python(skill_root / "scripts/preflight.py"),
            "inject": python(skill_root / "scripts/inject_violation.py"),
            "summarize": python(skill_root / "scripts/summarize.py"),
            "enforcers": enforcers,
        },
        "checkoutOnly": ["preflight --deep", "acima.py verify"],
    }


def _enforcer_command(language: str | None) -> str:
    command = execution_context()["commands"]["enforcers"].get(language or "")
    return command or "the reference enforcer for your language"


def _calibration() -> dict:
    """Compare the skill's pinned catalog against the catalog on disk."""
    try:
        manifest_path = Path(execution_context()["skillRoot"]) / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        raw = (ACIMA_ROOT / "tools/acima-spec/rules.json").read_bytes()
        catalog = json.loads(raw)
    except (OSError, json.JSONDecodeError) as error:
        return _step(0, "calibration", STEP_UNKNOWN, f"cannot verify the skill pin: {error}",
                     "run preflight.py from an ACIMA checkout or bundled skill")
    pinned = manifest.get("catalog") or {}
    digest = hashlib.sha256(raw).hexdigest()
    rules = catalog.get("rules") or []
    automated = sorted(rule["id"] for rule in rules if rule.get("automation") != "manual")
    manual = sorted(rule["id"] for rule in rules if rule.get("automation") == "manual")
    problems = []
    if pinned.get("sha256") != digest:
        problems.append("the manifest pin does not match rules.json")
    if sorted(pinned.get("portableIds") or []) != automated:
        problems.append("the pinned automated rule ids do not match the catalog")
    if sorted(pinned.get("notPortableIds") or []) != manual:
        problems.append("the pinned manual rule ids do not match the catalog")
    if pinned.get("rules") != len(rules):
        problems.append("the pinned rule count does not match the catalog")
    if problems:
        return _step(0, "calibration", STEP_BLOCKED, "; ".join(problems),
                     "run preflight.py, then re-calibrate the skill against this catalog")
    return _step(0, "calibration", STEP_COMPLETE,
                 f"pin matches {len(rules)} rules ({digest[:12]}...)")


def _catalog_version_and_hash() -> tuple[str | None, str | None]:
    try:
        raw = (ACIMA_ROOT / "tools/acima-spec/rules.json").read_bytes()
        return json.loads(raw).get("version"), hashlib.sha256(raw).hexdigest()
    except (OSError, json.JSONDecodeError):
        return None, None


def _run_artefacts(root: Path, catalog_version: str | None) -> tuple[list[dict], list[str]]:
    directory = root / "docs/acima"
    usable: list[dict] = []
    rejected: list[str] = []
    if not directory.is_dir():
        return usable, rejected
    for path in sorted(list(directory.glob("baseline-*.json")) + list(directory.glob("gate-*.json"))):
        name = path.relative_to(root).as_posix()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            rejected.append(f"{name}: not valid JSON")
            continue
        problems = validate_run_artefact(payload, catalog_version)
        if problems:
            rejected.append(f"{name}: " + "; ".join(problems))
            continue
        usable.append({"path": name, "payload": payload, "mtime": path.stat().st_mtime})
    usable.sort(key=lambda entry: entry["mtime"])
    return usable, rejected


def _git_head(root: Path) -> str | None:
    try:
        result = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                                capture_output=True, text=True)
    except OSError:
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def _git_remote(root: Path) -> str | None:
    try:
        result = subprocess.run(["git", "-C", str(root), "remote", "get-url", "origin"],
                                capture_output=True, text=True)
    except OSError:
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def _repository_identity(value: str) -> str:
    value = value.strip().removesuffix(".git")
    value = re.sub(r"^[a-z]+://[^/]+/", "", value, flags=re.I)
    value = re.sub(r"^git@[^:]+:", "", value, flags=re.I)
    return value.lower().strip("/")


def _proof_step(root: Path, catalog_version: str | None, catalog_sha: str | None) -> dict:
    path = root / PROOF_ARTEFACT
    if not path.is_file():
        return _step(3, "trust the tool", STEP_UNKNOWN,
                     "no proof artefact; detection is unproven",
                     "run inject_violation.py with --out docs/acima/proof.json")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return _step(3, "trust the tool", STEP_BLOCKED, f"proof artefact unreadable: {error}",
                     "re-run inject_violation.py with --out")
    problems = []
    if not isinstance(data, dict):
        problems.append("not an object")
    else:
        if catalog_version and data.get("standard") != catalog_version:
            problems.append("standard does not match the catalog")
        if catalog_sha and data.get("catalogSha256") != catalog_sha:
            problems.append("catalog hash does not match")
        results = data.get("results")
        by_rule = {str(item.get("rule")): item for item in results
                   if isinstance(item, dict)} if isinstance(results, list) else {}
        for rule in ("ACIMA-L001", "ACIMA-D001"):
            entry = by_rule.get(rule)
            if not entry or entry.get("detected") is not True:
                problems.append(f"{rule} was not proven")
            elif entry.get("exitCode") != 1:
                problems.append(f"{rule} did not report a detected violation")
    if problems:
        return _step(3, "trust the tool", STEP_BLOCKED, "; ".join(problems),
                     "re-run the controlled-violation proof")
    return _step(3, "trust the tool", STEP_COMPLETE,
                 f"L001 and D001 were detected in controlled input ({path.name})")


GATE_TOKENS = ("acima_arch.py", "acima-arch.mjs", "./tools/archtest",
               "Acima.ArchTests", "acima.py analyze")
GATE_OBSERVATION = "docs/acima/gate-observed.json"
PROOF_ARTEFACT = "docs/acima/proof.json"
COMPARISON_FIELDS = ("standard", "level", "sourceFiles", "catalog", "executed")
GATE_PROVIDERS = {"github", "github-actions"}
PR_TRIGGERS = {"pull_request", "pull_request_target", "merge_group"}
GATE_REQUIRED_FIELDS = ("repository", "commit", "workflow", "command", "executedAt",
                        "standard", "catalogSha256", "level", "sourceFiles")


def _line_indent(line: str) -> int:
    expanded = line.expandtabs(2)
    return len(expanded) - len(expanded.lstrip(" "))


def _workflow_triggers(lines: list[str]) -> set[str]:
    """Read the top-level on: value, including a block mapping or an inline list."""
    triggers: set[str] = set()
    for index, line in enumerate(lines):
        match = re.match(r"^on\s*:\s*(.*)$", line.rstrip())
        if not match:
            continue
        value = match.group(1).strip()
        if value:
            for trigger in PR_TRIGGERS | {"push", "workflow_call", "workflow_dispatch",
                                          "schedule", "release", "issues"}:
                if re.search(r"(^|[\s\[{,:])" + re.escape(trigger) +
                             r"($|[\s\]},:])", value):
                    triggers.add(trigger)
            break
        cursor = index + 1
        while cursor < len(lines):
            candidate = lines[cursor]
            if not candidate.strip() or candidate.lstrip().startswith("#"):
                cursor += 1
                continue
            if _line_indent(candidate) == 0:
                break
            key = re.match(r"\s*([A-Za-z_][\w-]*)\s*:", candidate)
            if key:
                triggers.add(key.group(1))
            cursor += 1
        break
    return triggers


def _workflow_jobs(lines: list[str]) -> list[dict]:
    start = None
    for index, line in enumerate(lines):
        if re.match(r"^jobs\s*:\s*$", line.rstrip()):
            start = index
            break
    if start is None:
        return []
    jobs: list[dict] = []
    cursor = start + 1
    while cursor < len(lines):
        line = lines[cursor]
        if not line.strip() or line.lstrip().startswith("#"):
            cursor += 1
            continue
        if _line_indent(line) == 0:
            break
        header = re.match(r"\s*([A-Za-z0-9_.-]+)\s*:\s*$", line)
        if not header:
            cursor += 1
            continue
        name, indent = header.group(1), _line_indent(line)
        end = cursor + 1
        while end < len(lines):
            if lines[end].strip() and _line_indent(lines[end]) <= indent:
                break
            end += 1
        jobs.append({"name": name, "indent": indent, "lines": lines[cursor + 1:end]})
        cursor = end
    return jobs


def _job_base_indent(job: dict) -> int:
    indents = [_line_indent(line) for line in job["lines"]
               if line.strip() and not line.lstrip().startswith("#")
               and not line.lstrip().startswith("-")]
    return min(indents, default=job["indent"] + 2)


def _field_value(lines: list[str], key: str) -> str | None:
    for line in lines:
        match = re.match(r"^\s*" + re.escape(key) + r"\s*:\s*(.*)$", line)
        if match:
            return match.group(1).strip()
    return None


def _job_field_value(job: dict, key: str) -> str | None:
    """Read a job property, not the same key inside one of its steps."""
    base = _job_base_indent(job)
    for line in job["lines"]:
        if _line_indent(line) != base:
            continue
        match = re.match(r"^\s*" + re.escape(key) + r"\s*:\s*(.*)$", line)
        if match:
            return match.group(1).strip()
    return None


def _dedent(lines: list[str]) -> str:
    nonempty = [line for line in lines if line.strip()]
    if not nonempty:
        return ""
    common = min(_line_indent(line) for line in nonempty)
    return "\n".join(line[common:] if len(line) >= common else line for line in lines)


def _run_text(step_lines: list[str]) -> str | None:
    for index, line in enumerate(step_lines):
        match = re.match(r"^(\s*)run\s*:\s*(.*)$", line)
        if not match:
            continue
        value = match.group(2).strip()
        if value not in ("|", "|-", "|+", ">", ">-", ">+"):
            return value
        run_indent = len(match.group(1).expandtabs(2))
        body: list[str] = []
        cursor = index + 1
        while cursor < len(step_lines):
            candidate = step_lines[cursor]
            if candidate.strip() and _line_indent(candidate) <= run_indent:
                break
            body.append(candidate)
            cursor += 1
        return _dedent(body)
    return None


def _workflow_steps(job: dict) -> list[list[str]]:
    block = job["lines"]
    base = _job_base_indent(job)
    start = None
    for index, line in enumerate(block):
        if _line_indent(line) == base and re.match(r"^\s*steps\s*:\s*$", line):
            start = index
            break
    if start is None:
        return []
    steps: list[list[str]] = []
    cursor = start + 1
    while cursor < len(block):
        line = block[cursor]
        if not line.strip() or line.lstrip().startswith("#"):
            cursor += 1
            continue
        if _line_indent(line) <= base:
            break
        if not line.lstrip().startswith("-"):
            cursor += 1
            continue
        item_indent = _line_indent(line)
        end = cursor + 1
        while end < len(block):
            if block[end].strip() and _line_indent(block[end]) <= base:
                break
            if (block[end].strip().startswith("-")
                    and _line_indent(block[end]) == item_indent):
                break
            end += 1
        step_lines = block[cursor:end]
        if step_lines:
            step_lines = [re.sub(r"^(\s*)-\s?", r"\1", step_lines[0], count=1)] + step_lines[1:]
        steps.append(step_lines)
        cursor = end
    return steps


def _condition_state(value: str | None) -> str:
    if value is None or not value.strip():
        return "enabled"
    normalized = value.strip()
    normalized = re.sub(r"^\$\{\{\s*|\s*\}\}$", "", normalized).strip("'\" ")
    lowered = normalized.lower()
    if lowered in ("false", "0", "no", "null", "none"):
        return "disabled"
    if lowered in ("true", "1", "yes", "success()", "always()"):
        return "enabled"
    return "conditional"


def _continue_on_error(value: str | None) -> str:
    if value is None or not value.strip():
        return "no"
    normalized = value.strip().strip("'\"").lower()
    if normalized in ("true", "yes", "1"):
        return "advisory"
    if normalized in ("false", "no", "0"):
        return "no"
    return "unknown"


def _shell_segments(run: str) -> list[str]:
    segments: list[str] = []
    for line in run.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        for segment in re.split(r"\s*(?:&&|;)\s*", stripped):
            segment = segment.strip().strip("(){}")
            if segment:
                segments.append(segment)
    return segments


def _root_value(command: str) -> str | None:
    match = re.search(r"--root(?:=|\s+)(?:\"([^\"]+)\"|'([^']+)'|(\S+))", command)
    if not match:
        return None
    return next((group for group in match.groups() if group), None)


def _root_is_repository_root(value: str | None) -> bool:
    if value is None:
        return False
    normalized = value.strip().strip("'\"")
    return normalized in (".", "./", "${{ github.workspace }}", "$GITHUB_WORKSPACE",
                          "${GITHUB_WORKSPACE}", "${{github.workspace}}")


def _level_value(command: str) -> str | None:
    match = re.search(r"--level(?:=|\s+)(L[123])\b", command, flags=re.I)
    return match.group(1).upper() if match else None


def _parse_gate_command(segment: str) -> dict | None:
    """Recognise a gate only when a shell command actually invokes it.

    A name in an ``echo``, a workflow name, a comment or a step label is not an invocation.
    """
    text = segment.strip()
    if not text or text.startswith("#"):
        return None
    lowered = text.lower()
    if re.match(r"^(echo|printf|cat|grep|rg|true|false|:|set)\b", lowered):
        return None
    try:
        tokens = shlex.split(text)
    except ValueError:
        tokens = text.split()
    if not tokens:
        return None
    first = Path(tokens[0].lstrip("(")).name.lower()
    token: str | None = None
    language: str | None = None
    for index, item in enumerate(tokens):
        base = Path(item.strip("()")).name
        if base in ("acima_arch.py", "acima-arch.mjs"):
            token, language = base, ("python" if base.endswith(".py") else "typescript")
        elif base == "acima.py" and index + 1 < len(tokens) \
                and tokens[index + 1].strip("()") == "analyze":
            token, language = "acima.py analyze", None
        elif base == "archtest" and ("go" in [part.lower() for part in tokens[:index]]
                                     or first == "archtest"
                                     or tokens[0].startswith("(")):
            token, language = "./tools/archtest", "go"
        elif base == "Acima.ArchTests" and "dotnet" in [part.lower() for part in tokens]:
            token, language = "Acima.ArchTests", "dotnet"
    if token is None:
        return None
    if first not in ("python", "python3", "node", "dotnet", "go") \
            and not (first in ("acima_arch.py", "acima-arch.mjs", "acima.py", "archtest")):
        return None
    if token == "Acima.ArchTests" and "run" not in [part.lower() for part in tokens]:
        return None
    if token == "./tools/archtest" and first not in ("go", "archtest"):
        return None
    root = _root_value(text)
    level = _level_value(text)
    allowed_to_fail = bool(re.search(r"\|\|\s*(?:true|:|exit\s+0)\b", text))
    return {"token": token, "language": language, "command": text, "root": root,
            "level": level, "allowedToFail": allowed_to_fail}


def _parse_workflow(path: Path, root: Path, level: str | None) -> dict:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as error:
        return {"path": path.relative_to(root).as_posix(), "mentionsAcima": False,
                "triggers": [], "onPullRequest": False, "invocations": [],
                "validInvocations": [], "unsupported": [f"unreadable: {error}"],
                "problems": [], "state": "no-gate"}
    lines = text.splitlines()
    triggers = _workflow_triggers(lines)
    on_pull_request = bool(triggers & PR_TRIGGERS)
    invocations: list[dict] = []
    unsupported: list[str] = []
    problems: list[str] = []

    for job in _workflow_jobs(lines):
        base = _job_base_indent(job)
        job_if = _job_field_value(job, "if")
        job_continue = _continue_on_error(_job_field_value(job, "continue-on-error"))
        job_uses = _job_field_value(job, "uses") or ""
        if job_if is not None and _condition_state(job_if) != "enabled":
            job_condition = _condition_state(job_if)
        else:
            job_condition = "enabled"
        if job_continue in ("advisory", "unknown"):
            job_continue_state = job_continue
        else:
            job_continue_state = "no"
        if job_uses:
            unsupported.append(f"{job['name']}: reusable workflow {job_uses}")

        for step in _workflow_steps(job):
            step_if = _field_value(step, "if")
            step_continue = _continue_on_error(_field_value(step, "continue-on-error"))
            step_uses = _field_value(step, "uses") or ""
            if step_uses.startswith("./") and "action" in step_uses.lower():
                unsupported.append(f"{job['name']}: composite action {step_uses}")
            run = _run_text(step)
            if not run:
                continue
            for segment in _shell_segments(run):
                parsed = _parse_gate_command(segment)
                if not parsed:
                    continue
                invocation_problems: list[str] = []
                if not on_pull_request:
                    invocation_problems.append("workflow has no pull_request or merge_group trigger")
                if "pull_request_target" in triggers and "pull_request" not in triggers \
                        and "merge_group" not in triggers:
                    invocation_problems.append(
                        "pull_request_target does not verify the pull request commit")
                if job_condition == "disabled":
                    invocation_problems.append(f"job {job['name']} is disabled")
                elif job_condition == "conditional":
                    invocation_problems.append(
                        f"job {job['name']} has conditional execution that cannot be verified")
                if step_if is not None and _condition_state(step_if) == "disabled":
                    invocation_problems.append("step is disabled")
                elif step_if is not None and _condition_state(step_if) == "conditional":
                    invocation_problems.append(
                        "step has conditional execution that cannot be verified")
                if job_continue_state == "advisory":
                    invocation_problems.append(f"job {job['name']} allows failure")
                elif job_continue_state == "unknown":
                    invocation_problems.append(
                        f"job {job['name']} has an unevaluable continue-on-error")
                if step_continue == "advisory":
                    invocation_problems.append("step allows failure")
                elif step_continue == "unknown":
                    invocation_problems.append("step has an unevaluable continue-on-error")
                if not _root_is_repository_root(parsed["root"]):
                    invocation_problems.append(
                        f"does not use the repository root (--root {parsed['root'] or 'missing'})")
                if parsed["level"] is None:
                    if level not in (None, "L1"):
                        invocation_problems.append(
                            f"does not pin the declared {level} level")
                elif level and parsed["level"] != level:
                    invocation_problems.append(
                        f"uses {parsed['level']} but the declared level is {level}")
                if parsed["allowedToFail"]:
                    invocation_problems.append("command is allowed to fail")
                if "|" in parsed["command"] and "pipefail" not in run.lower():
                    invocation_problems.append(
                        "pipeline may lose the enforcer exit status without pipefail")
                invocations.append({
                    "workflow": path.relative_to(root).as_posix(),
                    "job": job["name"],
                    "step": _field_value(step, "name") or "",
                    "token": parsed["token"],
                    "language": parsed["language"],
                    "command": parsed["command"],
                    "root": parsed["root"],
                    "level": parsed["level"],
                    "onPullRequest": on_pull_request,
                    "problems": invocation_problems,
                    "valid": not invocation_problems,
                })
                problems.extend(invocation_problems)

    valid = [item for item in invocations if item["valid"]]
    if valid:
        state = "configured"
    elif invocations:
        if any("no pull_request" in problem for problem in problems):
            state = "not-pull-request"
        elif any("allows failure" in problem or "disabled" in problem
                 or "conditional execution" in problem or "unevaluable" in problem
                 for problem in problems):
            state = "disabled-or-advisory"
        else:
            state = "invalid-configuration"
    elif unsupported:
        state = "unsupported-workflow"
    elif "acima" in text.lower():
        state = "mention-only"
    else:
        state = "no-gate"
    return {
        "path": path.relative_to(root).as_posix(),
        "mentionsAcima": "acima" in text.lower(),
        "triggers": sorted(triggers),
        "onPullRequest": on_pull_request,
        "invocations": invocations,
        "validInvocations": valid,
        "unsupported": unsupported,
        "problems": problems,
        "state": state,
    }


def _gate_workflows(root: Path, level: str | None = None) -> list[dict]:
    directory = root / ".github/workflows"
    entries: list[dict] = []
    if not directory.is_dir():
        return entries
    for path in sorted(list(directory.glob("*.yml")) + list(directory.glob("*.yaml"))):
        entry = _parse_workflow(path, root, level)
        if entry["mentionsAcima"] or entry["invocations"] or entry["unsupported"]:
            entries.append(entry)
    return entries


def _observation_command_matches(command: str, invocation: dict) -> bool:
    parsed = _parse_gate_command(command)
    if not parsed or parsed["token"] != invocation["token"]:
        return False
    if parsed["root"] and parsed["root"] != invocation["root"]:
        return False
    if parsed["level"] and invocation["level"] and parsed["level"] != invocation["level"]:
        return False
    return True


def _run_url_problem(url: str, repository: str, run_id: str) -> str | None:
    try:
        parsed = urllib.parse.urlsplit(url)
    except ValueError:
        return "runUrl is not a valid URL"
    if parsed.scheme != "https" or parsed.hostname not in ("github.com", "www.github.com"):
        return "runUrl is not a GitHub provider URL"
    normalized = parsed.path.lower()
    if repository and repository.lower() not in normalized:
        return "runUrl does not name the observation repository"
    if run_id and f"/actions/runs/{run_id.lower()}" not in normalized:
        return "runUrl does not name the observation run"
    return None


def _gate_step(root: Path, workflows: list[dict], level: str | None,
               catalog_version: str | None, catalog_sha: str | None) -> dict:
    path = root / GATE_OBSERVATION
    valid = [item for entry in workflows for item in entry["validInvocations"]]
    valid_paths = {item["workflow"] for item in valid}

    def gate_result(state: str, gate_state: str, evidence: str, remedy: str = "",
                    details: dict | None = None) -> dict:
        step = _step(8, "gate", state, evidence, remedy)
        step["gateState"] = gate_state
        step["gate"] = details or {}
        return step

    if not path.is_file():
        if valid:
            first = valid[0]
            return gate_result(
                STEP_IN_PROGRESS, "configured-not-observed",
                f"{first['workflow']} invokes {first['token']}; configured, not observed "
                "on a pull request",
                "keep a provider-sourced observation record for a real run",
                {"workflows": workflows, "validInvocations": valid})
        if workflows:
            first = workflows[0]
            if first["state"] == "mention-only":
                return gate_result(
                    STEP_BLOCKED, "mention-only",
                    f"{first['path']} mentions ACIMA but invokes no gate command",
                    "make the workflow run an enforcer, or remove the misleading file",
                    {"workflows": workflows})
            if first["state"] == "not-pull-request":
                return gate_result(
                    STEP_BLOCKED, "not-pull-request",
                    f"{first['path']} invokes {first['invocations'][0]['token']} but does "
                    "not run for pull requests",
                    "add a pull_request or merge_group trigger and re-check the workflow",
                    {"workflows": workflows})
            if first["state"] == "unsupported-workflow":
                return gate_result(
                    STEP_BLOCKED, "unsupported-workflow",
                    "workflow cannot be interpreted safely: " + "; ".join(first["unsupported"]),
                    "use a direct, unconditional enforcer step on pull requests",
                    {"workflows": workflows})
            if first["state"] in ("disabled-or-advisory", "invalid-configuration"):
                detail = "; ".join((first.get("problems") or ["the invocation is not valid"])[:3])
                return gate_result(
                    STEP_BLOCKED, first["state"], f"{first['path']}: {detail}",
                    "fix the workflow root, level, triggers and failure semantics",
                    {"workflows": workflows})
        return gate_result(STEP_NOT_STARTED, "not-found",
                           "no workflow invokes a gate",
                           "propose a CI gate and wait for approval")

    if not valid and workflows:
        first = workflows[0]
        if first["state"] == "mention-only":
            return gate_result(
                STEP_BLOCKED, "mention-only",
                f"{first['path']} mentions ACIMA but invokes no gate command",
                "make the workflow run an enforcer, or remove the misleading file",
                {"workflows": workflows})
        if first["state"] == "not-pull-request":
            return gate_result(
                STEP_BLOCKED, "not-pull-request",
                f"{first['path']} invokes {first['invocations'][0]['token']} but does not "
                "run for pull requests",
                "add a pull_request or merge_group trigger and re-check the workflow",
                {"workflows": workflows})
        if first["state"] == "unsupported-workflow":
            return gate_result(
                STEP_BLOCKED, "unsupported-workflow",
                "workflow cannot be interpreted safely: " + "; ".join(first["unsupported"]),
                "use a direct, unconditional enforcer step on pull requests",
                {"workflows": workflows})
        if first["state"] in ("disabled-or-advisory", "invalid-configuration"):
            detail = "; ".join((first.get("problems") or ["the invocation is not valid"])[:3])
            return gate_result(
                STEP_BLOCKED, first["state"], f"{first['path']}: {detail}",
                "fix the workflow root, level, triggers and failure semantics",
                {"workflows": workflows})

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return gate_result(STEP_BLOCKED, "observation-malformed",
                           f"observation unreadable: {error}",
                           "replace it with a valid observation record")
    problems: list[str] = []
    unverified: list[str] = []
    if not isinstance(data, dict):
        data, problems = {}, ["observation is not an object"]
    else:
        for field in GATE_REQUIRED_FIELDS:
            if not str(data.get(field, "")).strip():
                problems.append(f"missing {field}")
        workflow = str(data.get("workflow", "")).strip()
        if workflow and workflow not in valid_paths:
            problems.append("workflow does not exist or does not invoke a valid gate")
        repository = str(data.get("repository", "")).strip()
        remote = _git_remote(root)
        if repository and remote and _repository_identity(repository) != _repository_identity(remote):
            problems.append("repository does not match the origin remote")
        if repository and not remote:
            unverified.append("repository cannot be cross-checked against an origin remote")
        if str(data.get("standard", "")) != str(catalog_version):
            problems.append("standard does not match the catalog")
        if data.get("catalogSha256") != catalog_sha:
            problems.append("catalog hash does not match")
        if level and data.get("level") != level:
            problems.append("level does not match the declared level")
        if data.get("exitCode") not in (0, 1):
            problems.append("exitCode is not 0 or 1")
        try:
            date.fromisoformat(str(data.get("executedAt", ""))[:10])
        except ValueError:
            problems.append("executedAt is not an ISO date")
        sources = data.get("sourceFiles")
        if isinstance(sources, bool) or not isinstance(sources, int) or sources <= 0:
            problems.append("sourceFiles is not a positive count")
        commit = str(data.get("commit", "")).strip()
        if commit and not re.fullmatch(r"[0-9a-f]{7,40}", commit):
            problems.append("commit is not a git SHA")
        if data.get("enforcerExecuted") is False or data.get("skipped") is True \
                or str(data.get("stepOutcome", "")).lower() in ("skipped", "cancelled") \
                or str(data.get("conclusion", "")).lower() in ("skipped", "cancelled"):
            problems.append("observation reports that the enforcer did not execute")
        command = str(data.get("command", "")).strip()
        workflow_invocations = [item for item in valid if item["workflow"] == workflow]
        if command and not any(_observation_command_matches(command, item)
                               for item in workflow_invocations):
            problems.append("command does not match a valid invocation in the observed workflow")
        status = str(data.get("status", "")).strip().lower()
        conclusion = str(data.get("conclusion", "")).strip().lower()
        if status and status not in ("completed", "success"):
            unverified.append("the provider run is not complete")
        if conclusion and conclusion not in ("success", "failure", "timed_out",
                                             "startup_failure"):
            problems.append(f"observation reports a {conclusion!r} conclusion")
        run_id = str(data.get("runId", "")).strip()
        provider = str(data.get("provider", "")).strip().lower()
        if provider and provider not in GATE_PROVIDERS:
            unverified.append(f"provider {provider!r} is not supported")
        if not provider or not run_id:
            unverified.append("provider or runId is missing")
        if data.get("verified") is not True:
            unverified.append("the provider verification flag is not true")
        if data.get("manual") is True:
            unverified.append("the observation is marked manual")
        run_url = str(data.get("runUrl", "")).strip()
        if run_url:
            url_problem = _run_url_problem(run_url, repository, run_id)
            if url_problem:
                problems.append(url_problem)
        head = _git_head(root)
        if head and commit and not head.startswith(commit):
            problems.append(f"observation is stale: commit {commit[:12]} is not HEAD {head[:12]}")
        if not head:
            unverified.append("the commit cannot be cross-checked here")
        if problems:
            gate_state = "observation-stale" if any("stale" in item for item in problems) \
                else "observation-mismatch"
            return gate_result(
                STEP_BLOCKED, gate_state, "; ".join(problems),
                "record a fresh observation with repository, commit, workflow, command and "
                "catalog provenance", {"observationProblems": problems, "workflows": workflows})
        if data.get("exitCode") == 1 or conclusion in ("failure", "timed_out",
                                                       "startup_failure"):
            return gate_result(
                STEP_IN_PROGRESS, "observation-failed",
                f"observed gate failure at {commit[:12]}; the gate ran and rejected the commit",
                "fix the finding, then record a passing observation",
                {"observation": data, "workflows": workflows})
        if unverified:
            return gate_result(
                STEP_IN_PROGRESS, "observation-unverified",
                f"observed at {commit[:12]}; not independently verified: "
                + "; ".join(unverified),
                "attach provider and run identifier, and cross-check the repository and HEAD",
                {"observation": data, "unverified": unverified, "workflows": workflows})
        return gate_result(
            STEP_COMPLETE, "verified",
            f"independently recorded run {data.get('runId')} at {commit[:12]}",
            details={"observation": data, "workflows": workflows})


def _count_errors(payload: dict) -> int:
    return sum(1 for finding in payload.get("findings") or []
               if str(finding.get("severity", "")).lower() == "error")


def _finding_key(finding: dict) -> str:
    fingerprint = str(finding.get("fingerprint") or "").strip()
    if fingerprint:
        return fingerprint
    return "%s@%s:%s" % (finding.get("rule"), finding.get("path"), finding.get("line"))


def _run_identity(payload: dict) -> dict:
    execution = payload.get("execution") or {}
    return {
        "standard": payload.get("standard"),
        "level": payload.get("level"),
        "sourceFiles": payload.get("sourceFiles"),
        "catalog": payload.get("catalogSha256") or payload.get("catalog"),
        "executed": sum(1 for value in execution.values()
                        if isinstance(value, dict) and value.get("executed") is True),
    }


def _slice_step(runs: list[dict]) -> dict:
    if not runs:
        return _step(9, "slice", STEP_NOT_STARTED, "no measured run",
                     "measure the current state first")
    if len(runs) < 2:
        return _step(9, "slice", STEP_IN_PROGRESS,
                     "one measurement; no boundary change is evidenced yet",
                     "land one approved boundary change, then re-measure")
    first, last = runs[0], runs[-1]
    identity_first, identity_last = _run_identity(first["payload"]), _run_identity(last["payload"])
    differences = [key for key in COMPARISON_FIELDS
                   if identity_first.get(key) != identity_last.get(key)]
    if differences:
        return _step(9, "slice", STEP_IN_PROGRESS,
                     "measurements are not comparable: " + ", ".join(differences) + " differ",
                     "re-measure the same scope, level and configuration before comparing")
    before = {_finding_key(finding) for finding in first["payload"].get("findings") or []
              if str(finding.get("severity", "")).lower() == "error"}
    after = {_finding_key(finding) for finding in last["payload"].get("findings") or []
             if str(finding.get("severity", "")).lower() == "error"}
    resolved, added = before - after, after - before
    errors_first, errors_last = _count_errors(first["payload"]), _count_errors(last["payload"])
    if errors_last < errors_first and resolved and not added:
        return _step(9, "slice", STEP_COMPLETE,
                     f"errors fell {errors_first} -> {errors_last}; {len(resolved)} named "
                     "finding(s) resolved with no new errors")
    if added:
        return _step(9, "slice", STEP_IN_PROGRESS,
                     f"errors {errors_first} -> {errors_last}, but {len(added)} new error "
                     "finding(s) appeared; not a verified boundary improvement",
                     "separate the new findings from the intended correction")
    return _step(9, "slice", STEP_IN_PROGRESS,
                 f"errors did not fall ({errors_first} -> {errors_last})",
                 "land one boundary change and re-measure")


def _claim_step(root: Path, runs: list[dict], level: str | None) -> dict:
    if not runs:
        return _step(10, "claim", STEP_NOT_STARTED, "no measured run to base a claim on",
                     "measure a run, then record manual evidence where a rule is manual")
    newest = runs[-1]
    evidence_path = root / EVIDENCE_FILE
    try:
        evidence = load_evidence(evidence_path) if evidence_path.is_file() else {}
        claim = assess_claim(
            newest["payload"], load_catalog(ACIMA_ROOT),
            level=level or newest["payload"].get("level") or "L1",
            evidence=evidence, evidence_path=EVIDENCE_FILE, root=root,
        )
    except (ClaimError, OSError, json.JSONDecodeError, ValueError) as error:
        return _step(10, "claim", STEP_BLOCKED, f"{newest['path']}: {error}",
                     "fix or replace the manual evidence, then recompute the claim")
    invalid = claim.get("invalidEvidence") or []
    if invalid:
        return _step(10, "claim", STEP_BLOCKED,
                     f"{len(invalid)} evidence entr(y/ies) are invalid; the claim is {claim['claim']}",
                     "correct the evidence fields or expiry, then recompute")
    if claim["claim"] == FULL:
        return _step(10, "claim", STEP_COMPLETE,
                     f"FULL CONFORMANCE at {claim.get('level')} from {newest['path']}")
    missing = claim.get("missing") or []
    return _step(10, "claim", STEP_IN_PROGRESS,
                 f"PARTIAL ASSESSMENT at {claim.get('level')}: "
                 f"{len(missing)} required rule(s) have no accepted evidence",
                 "record repository-scoped manual evidence for the named rules")


def status_project(root: Path) -> dict:
    """Report what the artefacts actually prove, and the one next action.

    Read-only. Each milestone is evaluated with the same validation its authoritative operation
    uses; where no authoritative artefact exists the state is UNKNOWN, never complete.
    """
    root = root.resolve()
    if not root.is_dir():
        raise ConfigError(f"not a directory: {root}")
    config_problem = ""
    try:
        config = read_config(root)
    except ConfigError as error:
        config = None
        config_problem = str(error)
    languages = detect_languages(root)
    language = (config or {}).get("language") or (languages[0] if languages else None)
    sources = sum(1 for path in _walk(root) if path.suffix.lower() in SOURCE_EXTENSIONS)
    units = list((config or {}).get("units") or [])
    level = (config or {}).get("level")
    mode = (config or {}).get("mode") or "base"
    context = execution_context()

    catalog_version, catalog_sha = _catalog_version_and_hash()
    calibration = _calibration()
    waiver_path = root / ((config or {}).get("waivers") or ".acima/waivers.json")
    waivers = _waiver_document(waiver_path) if waiver_path.is_file() else {"waivers": []}
    scopes = {str(unit.get("id")) for unit in units if unit.get("id")}
    scopes |= {str(unit.get("module")) for unit in units if unit.get("module")}
    waiver_report = validate_waivers(waivers, valid_scopes=scopes)
    fingerprinted = _waiver_document(root / ".acima/baseline.json").get("fingerprints")
    fingerprinted = fingerprinted if isinstance(fingerprinted, list) else []

    runs, rejected_runs = _run_artefacts(root, catalog_version)
    newest = runs[-1] if runs else None
    errors = _count_errors(newest["payload"]) if newest else 0
    workflows = _gate_workflows(root, level)

    steps = [_step(1, "recon", STEP_READY,
                   f"{sources} source file(s), {language or 'unknown language'}")]
    steps.append(_step(2, "fit", STEP_UNKNOWN,
                       "the fit decision is conversational; no artefact proves assessment or "
                       "unit-map approval",
                       "record the approved proposal path if the owner keeps one"))
    steps.append(_proof_step(root, catalog_version, catalog_sha))
    steps.append(_step(4, "calibrate", calibration["state"], calibration["evidence"],
                       calibration["remedy"]))
    if config_problem:
        declare = _step(5, "declare", STEP_BLOCKED, config_problem,
                        "repair acima.config.json; nothing else can be trusted until it parses")
    elif units:
        declare = _step(5, "declare", STEP_COMPLETE,
                        f"{len(units)} unit(s) at {level or 'unset level'}; review is not proven")
    elif config:
        declare = _step(5, "declare", STEP_BLOCKED, "the config declares no units",
                        "add at least one unit with its role and paths")
    else:
        declare = _step(5, "declare", STEP_NOT_STARTED, "no config",
                        "declare units only after approval")
    steps.append(declare)

    if rejected_runs and not runs:
        freeze = _step(6, "freeze", STEP_BLOCKED, "; ".join(rejected_runs[:3]),
                       "re-run the enforcer and keep its unmodified JSON output")
    elif runs:
        detail = f"{newest['path']}: {newest['payload'].get('sourceFiles')} source file(s), " \
                 f"{len(newest['payload'].get('findings') or [])} finding(s), {errors} error(s)"
        freeze = _step(6, "freeze", STEP_COMPLETE, detail)
    elif fingerprinted:
        freeze = _step(6, "freeze", STEP_IN_PROGRESS,
                       f".acima/baseline.json holds {len(fingerprinted)} fingerprint(s), but no "
                       "valid measured run proves the measurement",
                       "keep the enforcer's JSON as docs/acima/baseline-<date>.json")
    else:
        freeze = _step(6, "freeze", STEP_NOT_STARTED, "no measured run",
                       "measure the current state")
    steps.append(freeze)

    if not newest:
        own = _step(7, "own", STEP_NOT_STARTED, "no measured findings to own",
                    "freeze a baseline first")
    elif waiver_report["invalid"] or waiver_report["expired"] or waiver_report["unowned"]:
        first_problem = (waiver_report["invalid"][0].get("problems")
                         if waiver_report["invalid"] else [])
        detail = (f"{len(waiver_report['invalid'])} invalid, {len(waiver_report['expired'])} "
                  f"expired, {len(waiver_report['unowned'])} unowned of "
                  f"{waiver_report['total']} waiver(s)")
        if first_problem:
            detail += "; first: " + "; ".join(first_problem)
        own = _step(7, "own", STEP_BLOCKED, detail,
                    "complete every waiver field, scope and fingerprint, and renew individually")
    elif waiver_report["valid"]:
        own = _step(7, "own", STEP_COMPLETE,
                    f"{len(waiver_report['valid'])} valid, current waiver(s)")
    elif errors:
        own = _step(7, "own", STEP_NOT_STARTED,
                    f"{errors} unwaived error(s) and no valid waiver",
                    "propose scoped, owned waivers for pre-existing findings")
    else:
        own = _step(7, "own", STEP_NOT_APPLICABLE,
                    "no error findings require an exception")
    steps.append(own)
    steps.append(_gate_step(root, workflows, level, catalog_version, catalog_sha))
    steps.append(_slice_step(runs))
    steps.append(_claim_step(root, runs, level))
    steps.append(_step(11, "maintain", STEP_NOT_APPLICABLE,
                       "maintaining the standard is not part of adopting it"))

    optional = [{"name": name, "path": f"docs/acima/{name}",
                 "present": (root / "docs/acima" / name).is_file()}
                for name in ("adoption-plan.md", "communication-plan.md", "STATUS.md")]

    next_step = {"action": "", "why": "", "command": "", "doneWhen": "",
                 "approvalRequired": False, "writes": False}
    preflight = context["commands"]["preflight"] + " --project . --format text"
    assess = context["commands"]["acima"] + " assess --root ."

    if calibration["state"] == STEP_BLOCKED:
        next_step.update(action="Re-calibrate the skill before trusting any result",
                         why="A pin mismatch means the advice may describe an older standard.",
                         command=preflight,
                         doneWhen="preflight exits 0 and reports this catalog's hash.")
    elif config_problem or (config and not units):
        next_step.update(action="Repair the unit map", why="No unit map means nothing can be measured.",
                         command="edit acima.config.json: add units with roles and paths",
                         doneWhen="units parse and cover every source file.",
                         approvalRequired=True, writes=True)
    elif not config:
        next_step.update(action="Check whether ACIMA fits this repository, before changing anything",
                         why="A fit decision comes from read-only evidence, not from a template.",
                         command=f"{preflight} && {assess}",
                         doneWhen="a verdict and named gaps exist; no target file is written.")
    elif not runs:
        next_step.update(action="Measure the current architecture",
                         why="Without a validated run, findings and progress are guesses.",
                         command=f"{_enforcer_command(language)} --root . --format json",
                         doneWhen="the JSON parses, sourceFiles > 0, the level is set and the "
                                  "execution map is complete.")
    elif steps[6]["state"] == STEP_BLOCKED:
        next_step.update(action="Repair waiver governance before relying on the gate",
                         why="An invalid, expired or unowned exception hides new findings.",
                         command="edit .acima/waivers.json: complete every field, scope and expiry",
                         doneWhen="every waiver validates and none is expired.",
                         approvalRequired=True, writes=True)
    elif steps[6]["state"] == STEP_NOT_STARTED and errors:
        next_step.update(action="Ask the owner to approve owned exceptions for existing findings",
                         why="The baseline has errors but no valid waiver; the gate cannot be honest yet.",
                         command="propose scoped waivers, then write them only with approval",
                         doneWhen="each pre-existing finding has an owner and an expiry.",
                         approvalRequired=True, writes=True)
    elif steps[7]["state"] == STEP_NOT_STARTED:
        next_step.update(action="Ask the owner to approve a CI gate",
                         why="The gate is what stops new violations; it is a write and needs consent.",
                         command="propose .github/workflows/acima.yml running the enforcer for the declared level",
                         doneWhen="an approved workflow invokes the gate on pull requests.",
                         approvalRequired=True, writes=True)
    elif steps[7]["state"] == STEP_BLOCKED:
        gate_state = steps[7].get("gateState")
        if gate_state == "mention-only":
            next_step.update(action="Make the CI workflow run a real gate",
                             why="A workflow that mentions ACIMA without invoking it proves nothing.",
                             command="edit the workflow to run the enforcer with --root and the declared level",
                             doneWhen="the workflow invokes the gate and a failing pull request blocks.",
                             approvalRequired=True, writes=True)
        elif gate_state == "not-pull-request":
            next_step.update(action="Make the CI gate run on pull requests",
                             why="A correct enforcer command that runs only on push or manually does not protect merges.",
                             command="add a pull_request or merge_group trigger to the gate workflow",
                             doneWhen="the workflow runs the enforcer for pull requests and merge groups.",
                             approvalRequired=True, writes=True)
        elif gate_state in ("disabled-or-advisory", "invalid-configuration"):
            next_step.update(action="Fix the CI gate before trusting it",
                             why="The enforcer invocation is disabled, advisory, conditional or configured for the wrong scope.",
                             command="remove if: false and continue-on-error, use --root . and the declared level",
                             doneWhen="one unconditional step invokes the enforcer at the declared level.",
                             approvalRequired=True, writes=True)
        elif gate_state in ("observation-stale", "observation-mismatch"):
            next_step.update(action="Re-record the gate observation from the actual workflow",
                             why="The recorded run is stale, belongs to another workflow or does not match the current command.",
                             command="open a fresh pull request run and record its provider, run id, workflow and HEAD",
                             doneWhen="the observation references this workflow and its commit is HEAD.",
                             approvalRequired=True, writes=True)
        elif gate_state == "unsupported-workflow":
            next_step.update(action="Replace the reusable or composite gate with a directly verifiable step",
                             why="The current workflow cannot be tied to a concrete enforcer execution.",
                             command="run the enforcer directly in an unconditional pull-request job",
                             doneWhen="the workflow has one directly observable enforcer invocation.",
                             approvalRequired=True, writes=True)
        else:
            next_step.update(action="Make the CI workflow run a real gate",
                             why="The gate evidence is incomplete or invalid.",
                             command="edit the workflow to run the enforcer with --root and the declared level",
                             doneWhen="the workflow invokes the gate and a failing pull request blocks.",
                             approvalRequired=True, writes=True)
    elif steps[7]["state"] == STEP_IN_PROGRESS:
        if steps[7].get("gateState") == "observation-failed":
            next_step.update(action="Fix the failure the gate observed",
                             why="The gate ran and rejected the commit; that is not a passing milestone.",
                             command="fix the reported finding, then record a fresh passing run",
                             doneWhen="a provider-sourced observation at HEAD exits 0.")
        else:
            next_step.update(action="Confirm the gate runs on a pull request and record provider provenance",
                             why="Configured or manually recorded is not independently observed.",
                             command="open a pull request, then record commit, workflow and run id",
                             doneWhen="a provider-sourced observation matches HEAD and the declared level.")
    elif steps[8]["state"] in (STEP_NOT_STARTED, STEP_IN_PROGRESS):
        rule = ""
        if newest and newest["payload"].get("findings"):
            rule = str(newest["payload"]["findings"][0].get("rule") or "")
        next_step.update(action="Plan one boundary correction from the newest run",
                         why="One boundary per pull request keeps the gate explainable.",
                         command=f"{context['commands']['acima']} fix --report {newest['path']} "
                                 f"{rule or '--all'}".replace("  ", " "),
                         doneWhen="one correction is chosen, explained and separately approved.")
    elif steps[9]["state"] == STEP_IN_PROGRESS:
        next_step.update(action="Record the evidence the claim still needs",
                         why="A partial assessment is honest; accepted evidence is what can make it full.",
                         command="fill .acima/manual-evidence.json for the named manual rules",
                         doneWhen="acima.py claim --require full exits 0 at the declared level.",
                         approvalRequired=True, writes=True)
    else:
        next_step.update(action="Keep the count falling and the gate green",
                         why="The ratchet is the programme: flat or falling, never rising.",
                         command=f"{_enforcer_command(language)} --root . --format json",
                         doneWhen="the next run has no unwaived errors and the claim still holds.")

    verified = [step["name"] for step in steps if step["state"] == STEP_COMPLETE]
    blocked = [f"{step['name']}: {step['evidence']}" for step in steps if step["state"] == STEP_BLOCKED]
    remaining = [step["name"] for step in steps
                 if step["state"] in (STEP_NOT_STARTED, STEP_IN_PROGRESS, STEP_UNKNOWN)]

    return {
        "root": str(root), "language": language, "sourceFiles": sources,
        "context": context,
        "config": {"present": config is not None, "level": level, "mode": mode,
                   "units": len(units), "problem": config_problem or None},
        "evidence": {
            "runArtefacts": [entry["path"] for entry in runs],
            "rejectedArtefacts": rejected_runs,
            "runErrors": errors,
            "waivers": waiver_report["total"], "invalidWaivers": len(waiver_report["invalid"]),
            "expiredWaivers": len(waiver_report["expired"]),
            "unownedWaivers": len(waiver_report["unowned"]),
            "gateWorkflows": workflows, "proof": (root / PROOF_ARTEFACT).is_file(),
            "manualEvidence": (root / EVIDENCE_FILE).is_file(),
            "fingerprints": len(fingerprinted),
        },
        "steps": steps,
        "verified": verified,
        "remaining": remaining,
        "blocked": blocked,
        "optional": optional,
        "next": next_step,
        "limitation": ("Derived from artefacts and verified criteria; a missing, invalid or stale "
                       "artefact is reported, never assumed complete. Optional documents never "
                       "block adoption."),
    }


def status_text(report: dict) -> str:
    config = report["config"]
    lines = ["ACIMA status",
             "  repository  " + report["root"],
             "  context     %s (%s)" % (report["context"]["context"], report["context"]["standardRoot"]),
             "  language    %s - %s source file(s)"
             % (report["language"] or "unknown", report["sourceFiles"])]
    if config["present"]:
        lines.append("  config      acima.config.json - %s - %s - %s unit(s)"
                     % (config["level"] or "level unset", config["mode"], config["units"]))
    else:
        lines.append("  config      absent (not adopted)")
    lines.append("  verified    " + (", ".join(report["verified"]) or "nothing yet"))
    lines.append("  remaining   " + (", ".join(report["remaining"]) or "nothing"))
    lines.append("  blocked     " + ("; ".join(report["blocked"]) or "nothing"))
    optional = ", ".join("%s %s" % (item["name"].replace(".md", ""),
                                    "present" if item["present"] else "absent")
                         for item in report["optional"])
    lines.append("  optional    " + optional + " (never required)")
    lines += ["", "  steps"]
    for step in report["steps"]:
        lines.append("    %2s  %-14s %-14s %s"
                     % (step["n"], step["name"], step["label"], step["evidence"]))
    next_step = report["next"]
    lines += ["", "  next",
              "    " + next_step["action"],
              "    why: " + next_step["why"],
              "    done when: " + next_step["doneWhen"],
              "    $ " + next_step["command"],
              "    approval %s - %s"
              % ("required" if next_step["approvalRequired"] else "not needed",
                 "writes the target" if next_step["writes"] else "read-only")]
    return chr(10).join(lines)


CORRECTION_SHAPES = {
    "invert": "introduce or consume a port so the arrow points at contracts",
    "localise": "duplicate the shape or carry identity instead of the model",
    "remove": "delete the reference or state; nothing replaces it",
    "restructure": "process manager, event, or merge - only when the graph itself is wrong",
    "contract": "reshape the contract; see the rule page's Fix section",
    "governance": "complete the governance record; never suppress the finding",
}
SHAPE_BY_RULE = {
    "ACIMA-D001": "invert", "ACIMA-D002": "invert", "ACIMA-D003": "localise",
    "ACIMA-D004": "localise", "ACIMA-D005": "restructure", "ACIMA-D006": "remove",
    "ACIMA-D007": "restructure", "ACIMA-D008": "restructure", "ACIMA-D009": "invert",
    "ACIMA-L001": "invert", "ACIMA-L002": "localise", "ACIMA-L003": "invert",
    "ACIMA-L004": "invert",
    "ACIMA-A001": "invert", "ACIMA-A002": "localise", "ACIMA-A003": "remove",
    "ACIMA-A004": "invert",
}


def _catalog_rules() -> dict:
    path = ACIMA_ROOT / "tools/acima-spec/rules.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {rule["id"]: rule for rule in data.get("rules", [])}


def _matches(finding: dict, selector: str) -> bool:
    rule = str(finding.get("rule", ""))
    path = str(finding.get("path", ""))
    fingerprint = str(finding.get("fingerprint", ""))
    if selector in (fingerprint, fingerprint.replace("sha256:", "")):
        return True
    if selector == rule:
        return True
    if selector.startswith(rule + "@") or selector.startswith(rule + ":"):
        target = selector[len(rule) + 1:]
        return bool(target) and (path == target or path.endswith("/" + target)
                                 or target in path)
    return "/" in selector and (path == selector or path.endswith("/" + selector))


def fix_plan(payload: dict, selectors: list[str], all_findings: bool = False) -> dict:
    """Select 1..many findings and attach the catalog remedy to each. Read-only."""
    findings = payload.get("findings", []) or []
    catalog = _catalog_rules()
    chosen: list[dict] = []
    unmatched: list[str] = []
    if all_findings:
        chosen = list(findings)
    else:
        for selector in selectors:
            matched = [finding for finding in findings if _matches(finding, selector.strip())]
            if not matched:
                unmatched.append(selector)
            for finding in matched:
                if finding not in chosen:
                    chosen.append(finding)
    entries = []
    for finding in chosen:
        rule_id = str(finding.get("rule", ""))
        shape = SHAPE_BY_RULE.get(rule_id, "contract" if rule_id.startswith("ACIMA-C")
                                  else "governance")
        entries.append({
            "rule": rule_id,
            "severity": finding.get("severity"),
            "message": finding.get("message"),
            "path": finding.get("path"),
            "line": finding.get("line"),
            "evidence": finding.get("evidence"),
            "fix": (catalog.get(rule_id) or {}).get("fix", ""),
            "shape": shape,
            "shapeMeaning": CORRECTION_SHAPES[shape],
        })
    return {
        "total": len(findings),
        "selected": len(entries),
        "findings": entries,
        "unmatched": unmatched,
        "code": 1 if unmatched else 0,
        "limitation": "A plan, not a patch: the command never edits code, and an entry with no fix text needs the rule page.",
    }


def fix_text(plan: dict) -> str:
    lines = ["ACIMA fix", "  %s selected of %s finding(s)" % (plan["selected"], plan["total"]), ""]
    for index, entry in enumerate(plan["findings"], 1):
        lines.append("  %s. %s  %s  %s:%s  [%s]"
                     % (index, entry["rule"], entry["severity"], entry["path"],
                        entry["line"], entry["shape"]))
        lines.append("     " + str(entry["message"]))
        if entry.get("evidence"):
            lines.append("     evidence: " + str(entry["evidence"]))
        lines.append("     fix: " + (entry["fix"] or "read the rule page's Fix section"))
        lines.append("     shape: " + entry["shape"] + " - " + entry["shapeMeaning"])
        lines.append("")
    if plan["unmatched"]:
        lines.append("  no finding matched: " + ", ".join(plan["unmatched"]))
        lines.append("  a selector that matches nothing is a failure, not an empty fix")
    return chr(10).join(lines).rstrip()


def fix_markdown(plan: dict) -> str:
    lines = ["# ACIMA fix", "",
             "Selected **%s** of **%s** finding(s). A plan, not a patch." % (plan["selected"], plan["total"]), ""]
    for entry in plan["findings"]:
        lines.append("## %s - `%s:%s`" % (entry["rule"], entry["path"], entry["line"]))
        lines.append("")
        lines.append("%s" % entry["message"])
        if entry.get("evidence"):
            lines.append("")
            lines.append("```")
            lines.append(str(entry["evidence"]).strip())
            lines.append("```")
        lines.append("")
        lines.append("- Shape: **%s** - %s" % (entry["shape"], entry["shapeMeaning"]))
        lines.append("- Fix: %s" % (entry["fix"] or "read the rule page's Fix section"))
        lines.append("")
    if plan["unmatched"]:
        lines.append("**No finding matched:** " + ", ".join(plan["unmatched"]))
    return chr(10).join(lines)


def read_manifests(root: Path, manifests: list[str]) -> list[str]:
    """Return every declared package name, from the configured manifests or the default set."""
    names: list[str] = []
    candidates = manifests or [name for name in
                               ("package.json", "pyproject.toml", "requirements.txt")
                               if (root / name).is_file()]
    for relative in candidates:
        path = root / relative
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if relative.endswith(".json"):
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                continue
            names.extend(str(name) for name in (data.get("dependencies") or {}))
        elif relative.endswith(".txt"):
            for line in text.splitlines():
                value = line.strip()
                if not value or value.startswith(("#", "-")):
                    continue
                name = re.split(r"[<>=!~\[\]; ]", value)[0]
                if name:
                    names.append(name)
        elif relative.endswith("pyproject.toml"):
            inside = False
            for line in text.splitlines():
                if re.match(r"\s*dependencies\s*=\s*\[", line):
                    inside = True
                if not inside:
                    continue
                for match in re.finditer(r"[\"']([A-Za-z0-9_.-]+)", line):
                    names.append(match.group(1))
                if "]" in line.split("dependencies", 1)[-1]:
                    inside = False
    return sorted(dict.fromkeys(names))


def externals_draft(config: dict, packages: list[str]) -> dict:
    """A starting declaration: one entry per manifest package, never overwriting an existing one."""
    today = date.today()
    existing = config.get("externals") if isinstance(config.get("externals"), dict) else {}
    draft = dict(existing)
    for package in packages:
        if package in draft:
            continue
        draft[package] = {
            "tier": "utility",
            "owner": "UNASSIGNED",
            "reason": ("Draft from the manifest; assign a tier, owner and reason, and set "
                       "adapter/port for an integration."),
            "reviewedOn": today.isoformat(),
            "expires": (today + timedelta(days=365)).isoformat(),
        }
    return draft


def main() -> int:
    parser = argparse.ArgumentParser(prog="acima", description="ACIMA developer entry point")
    sub = parser.add_subparsers(dest="command", required=True)

    inspect = sub.add_parser("inspect", help="read-only project and unit inventory")
    inspect.add_argument("--root", default=".")
    inspect.add_argument("--config", default=CONFIG_NAME)
    inspect.add_argument("--format", choices=("text", "json"), default="text")

    analyze = sub.add_parser("analyze", help="run the reference enforcer")
    analyze.add_argument("--root", default=".")
    analyze.add_argument("--config", default=None)
    analyze.add_argument("--language", default=None)
    analyze.add_argument("--level", default=None)
    analyze.add_argument("--format", choices=("text", "json"), default="text")

    report = sub.add_parser("report", help="evidence report with explicit unevaluated rules")
    report.add_argument("--root", default=".")
    report.add_argument("--config", default=None)
    report.add_argument("--language", default=None)
    report.add_argument("--level", default=None)
    report.add_argument("--format", choices=("markdown", "json"), default="markdown")

    claim = sub.add_parser("claim", help="compute FULL CONFORMANCE or PARTIAL ASSESSMENT")
    claim.add_argument("--report", required=True, help="JSON run artifact from an enforcer")
    claim.add_argument("--root", default=".", help="repository that owns the manual evidence")
    claim.add_argument("--evidence", default=None,
                       help=f"manual evidence path (default: <root>/{EVIDENCE_FILE})")
    claim.add_argument("--level", default=None, choices=("L1", "L2", "L3"))
    claim.add_argument("--require", choices=("partial", "full"), default="partial")
    claim.add_argument("--format", choices=("markdown", "json"), default="markdown")

    assess = sub.add_parser("assess", help="read-only compatibility assessment")
    assess.add_argument("--root", default=".")
    assess.add_argument("--language", default=None)
    assess.add_argument("--level", default=None)
    assess.add_argument("--format", choices=("text", "json", "markdown"), default="text")

    status = sub.add_parser("status", help="which steps are evidenced, and the next command")
    status.add_argument("--root", default=".")
    status.add_argument("--format", choices=("text", "json"), default="text")
    fix = sub.add_parser("fix", help="turn 1..many findings into named corrections")
    fix.add_argument("selectors", nargs="*",
                     help="rule id, rule@path, path fragment, or fingerprint")
    fix.add_argument("--report", default=None, help="JSON run artifact; omit to analyze --root")
    fix.add_argument("--root", default=".")
    fix.add_argument("--config", default=None)
    fix.add_argument("--language", default=None)
    fix.add_argument("--all", action="store_true", dest="all_findings",
                     help="select every finding in the report")
    fix.add_argument("--format", choices=("text", "markdown", "json"), default="text")
    externals = sub.add_parser("externals", help="draft the third-party declaration from the manifest")
    externals.add_argument("--root", default=".")
    externals.add_argument("--config", default=CONFIG_NAME)
    externals.add_argument("--write-draft", action="store_true", dest="write_draft",
                           help="merge the draft into acima.config.json; never overwrites an entry")
    verify = sub.add_parser("verify", help="run the full reference conformance suite")
    verify.add_argument("profiles", nargs="*")

    args = parser.parse_args()
    if args.command == "inspect":
        payload = inspect_project(Path(args.root), args.config)
        if args.format == "json":
            print(json.dumps(payload, indent=2))
        else:
            print(f"root: {payload['root']}")
            print(f"mode: {payload['mode']} · language: {payload['language'] or 'unknown'} · "
                  f"level: {payload['declaredLevel'] or 'unset'}")
            print(f"units: {len(payload['units'])} · enforcer: "
                  f"{'ready' if payload['enforcerAvailable'] else 'unavailable'}")
            for unit in payload["units"]:
                print(f"  {unit['id']:<24} {unit['role']:<16} {', '.join(unit['paths'])}")
            print(f"next: {payload['next']}")
        return 0

    if args.command == "analyze":
        code, payload, error, language = analyze_project(
            Path(args.root), args.language, args.config, args.level)
        if payload is None:
            print(f"acima: {error}", file=sys.stderr)
            return 2
        if args.format == "json":
            print(json.dumps(payload, indent=2))
        else:
            for finding in payload.get("findings", []):
                print(f"{finding['rule']}  {finding['severity']:<7} {finding['message']}")
                print(f"  {finding['path']}:{finding['line']}")
                if finding.get("evidence"):
                    print(f"  {finding['evidence']}")
            summary = summarize(payload)
            print(f"\n{summary['total']} finding(s), {summary['severity']['error']} error(s) "
                  f"at level {payload.get('level', '?')} ({language})")
        return code

    if args.command == "report":
        code, payload, error, language = analyze_project(
            Path(args.root), args.language, args.config, args.level)
        if payload is None:
            print(f"acima: {error}", file=sys.stderr)
            return 2
        root = Path(args.root).resolve()
        config = read_config(root, args.config or CONFIG_NAME)
        claim = claim_for(root, payload)
        if args.format == "json":
            print(json.dumps({
                "summary": summarize(payload),
                "findings": payload.get("findings", []),
                "language": language,
                "level": payload.get("level"),
                "notEvaluated": not_evaluated(language),
                "claim": claim,
                "limitation": "Evidence only; no productivity or health score is inferred.",
            }, indent=2))
        else:
            print(report_markdown(root, payload, language, config, claim))
        return code

    if args.command == "claim":
        root = Path(args.root).resolve()
        report_path = Path(args.report)
        try:
            payload = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            print(f"acima: cannot read run artifact {report_path}: {error}", file=sys.stderr)
            return 2
        explicit_evidence = args.evidence is not None
        evidence_path = Path(args.evidence) if explicit_evidence else root / EVIDENCE_FILE
        if explicit_evidence and not evidence_path.is_file():
            print(f"acima: manual evidence not found: {evidence_path}", file=sys.stderr)
            return 2
        try:
            evidence = load_evidence(evidence_path)
            claim = assess_claim(
                payload, load_catalog(ACIMA_ROOT), level=args.level,
                evidence=evidence, evidence_path=str(evidence_path), root=root,
            )
        except ClaimError as error:
            print(f"acima: {error}", file=sys.stderr)
            return 2
        if args.format == "json":
            print(json.dumps(claim, indent=2, sort_keys=True))
        else:
            print(render_claim_markdown(claim))
        if args.require == "full" and claim["claim"] != FULL:
            return 1
        return 0

    if args.command == "status":
        report = status_project(Path(args.root))
        if args.format == "json":
            print(json.dumps(report, indent=2))
        else:
            print(status_text(report))
        return 0
    if args.command == "fix":
        if args.report:
            try:
                payload = json.loads(Path(args.report).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                print(f"acima: cannot read run artifact {args.report}: {error}", file=sys.stderr)
                return 2
        else:
            _code, payload, error, _language = analyze_project(
                Path(args.root), args.language, args.config)
            if payload is None:
                print(f"acima: {error}", file=sys.stderr)
                return 2
        if not args.selectors and not args.all_findings:
            print("acima: name at least one finding, or pass --all", file=sys.stderr)
            return 2
        plan = fix_plan(payload, args.selectors, args.all_findings)
        if args.format == "json":
            print(json.dumps(plan, indent=2))
        elif args.format == "markdown":
            print(fix_markdown(plan))
        else:
            print(fix_text(plan))
        return plan["code"]
    if args.command == "assess":
        code, report = assess_project(Path(args.root), args.language, args.level)
        if args.format == "json":
            print(json.dumps(report, indent=2))
        elif args.format == "markdown":
            print(assess_markdown(report))
        else:
            print(assess_text(report))
        return code

    if args.command == "externals":
        root = Path(args.root).resolve()
        config = read_config(root, args.config)
        if config is None:
            print(f"acima: no {args.config} at {root}; declare units before the third-party tiers",
                  file=sys.stderr)
            return 2
        manifests = [str(value) for value in config.get("manifests", [])]
        packages = read_manifests(root, manifests)
        if not packages:
            print("acima: no manifest found; pass manifests[] in acima.config.json or add "
                  "package.json, pyproject.toml or requirements.txt", file=sys.stderr)
            return 2
        known = config.get("externals") if isinstance(config.get("externals"), dict) else {}
        draft = externals_draft(config, packages)
        added = [name for name in draft if name not in known]
        if args.write_draft:
            config["externals"] = dict(sorted(draft.items()))
            if not manifests:
                config["manifests"] = [name for name in
                                       ("package.json", "pyproject.toml", "requirements.txt")
                                       if (root / name).is_file()]
            (root / args.config).write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
            print(f"acima: wrote {len(added)} new externals entr"
                  f"{'y' if len(added) == 1 else 'ies'} to {args.config} ({len(draft)} total)")
        else:
            print(json.dumps({"externals": dict(sorted(draft.items()))}, indent=2))
        if added:
            print("acima: every draft entry is tier=utility with owner=UNASSIGNED; assign the tier, "
                  "owner, reason and - for an integration - the adapter and port", file=sys.stderr)
        return 0

    result = subprocess.run([sys.executable, str(ACIMA_ROOT / "conformance/run.py")] + args.profiles,
                            cwd=ACIMA_ROOT)
    return result.returncode


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ConfigError as error:
        print(f"acima: {error}", file=sys.stderr)
        raise SystemExit(2)
