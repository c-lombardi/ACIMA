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
import os
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
    required_rules, validate_evidence, validate_run_artefact, validate_waivers,
)
from qualitative_review import (  # noqa: E402
    ReviewValidationError, load_and_validate_review,
)
from module_map import (  # noqa: E402
    ModuleMapError, OWNERSHIP_DEPENDENT_RULES, discover as discover_module_map,
)
CONFIG_NAME = "acima.config.json"
PRUNE = {".git", "node_modules", "bin", "obj", "dist", "build", "target", "out",
         ".venv", "venv", "__pycache__", ".next", ".nuxt", "coverage"}
SOURCE_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".mjs", ".cjs", ".cs", ".go", ".java"}
ENFORCER_VERSION = "acima-reference-1"
PROVENANCE_VERSION = 1
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
    return result.returncode, _attach_run_provenance(root, payload), result.stderr.strip()


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


def claim_for(root: Path, payload: dict, config: dict | None = None) -> dict:
    """Compute the claim class without letting a bad evidence file crash the report."""
    evidence_path = root / EVIDENCE_FILE
    try:
        evidence = load_evidence(evidence_path)
        claim = assess_claim(
            payload, load_catalog(ACIMA_ROOT), evidence=evidence,
            evidence_path=EVIDENCE_FILE, root=root,
        )
        catalog_version, catalog_sha = _catalog_version_and_hash()
        currentness = _claim_currentness(
            root, payload, config, payload.get("level"), catalog_version, catalog_sha)
        claim.update({"currentness": currentness["state"],
                      "current": currentness["current"], "provenance": currentness})
        return claim
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
        proposal = (report.get("moduleMap") or {}).get("proposal") or {}
        if proposal:
            steps.append(f"Review the generated module-map proposal ({len(proposal.get('modules', []))} "
                         "candidate module(s)) and decide each boundary and recommendation. Discovery "
                         "does not make ownership authoritative.")
        steps.append("Decide module ownership with the people who own the system, then approve and "
                     "declare units in acima.config.json. `preflight.py --write-draft` produces a "
                     "heuristic starting point that a human must review.")
        steps.append("Continue the read-only qualitative review of every catalog requirement using "
                     "the discovered project and architecture evidence. The missing map blocks "
                     "deterministic conformance measurement only; do not report the architecture "
                     "as unassessed or clean.")
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
        coverage = report.get("coverage") or {}
        if coverage.get("notAssessed", 0):
            steps.append("Resolve every unassessed required rule: run the missing automated "
                         "checks and record current repository-scoped evidence for manual reviews "
                         "(see docs/standard/08-conformance.md).")
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
        automated_missing = len((coverage.get("automated") or {}).get("notExecuted") or [])
        manual_missing = len((coverage.get("manual") or {}).get("missingEvidence") or [])
        unknowns.append(
            f"{coverage.get('notAssessed', automated_missing + manual_missing)} required rule(s) "
            f"remain unassessed: {automated_missing} automated check(s) did not run and "
            f"{manual_missing} manual review(s) lack accepted evidence.")

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



def build_gated_assessment_result(report: dict, config: dict | None) -> dict:
    """Do not issue an adoption recommendation before the complete qualitative review gate."""
    result = build_assessment_result(report, config)
    review = report.get("comprehensiveRuleReview") or {}
    coverage_complete = bool(review.get("coverageComplete"))
    decision_complete = bool(review.get("decisionComplete", review.get("complete")))
    # Unsupported language/profile conclusions are explicit tool-capability limits, not
    # adoption recommendations, and remain the most accurate result for those targets.
    if result.get("fit") == OUTCOME_NOT_SUPPORTED:
        return result
    if coverage_complete and decision_complete:
        return result

    required = review.get("required", len((report.get("catalog") or {}).get("rules", [])))
    reviewed = review.get("reviewed", 0)
    unresolved = review.get("unresolved", 0)
    if not coverage_complete:
        reason = (f"The comprehensive review has {reviewed}/{required} valid evidence-backed dispositions. "
                  "All catalog requirements must be individually reviewed before ACIMA adoption can be recommended.")
    else:
        reason = (f"All {required} catalog requirements have explicit dispositions, but {unresolved} remain unresolved "
                  "because the available evidence is insufficient. Resolve those questions before an adoption recommendation.")
    gate_reason = reason
    preliminary_signal = result.get("why")
    if preliminary_signal:
        reason += " Preliminary repository fit signal: " + preliminary_signal
    result.update({
        "fit": OUTCOME_INSUFFICIENT,
        "outcome": OUTCOME_INSUFFICIENT,
        "fitLegacy": OUTCOME_INSUFFICIENT.lower().replace("_", "-"),
        "confidence": "low",
        "recommendation": "There is not enough evidence to recommend adoption. " + gate_reason,
        "why": reason,
    })
    explanation = result.get("explanation") or {}
    explanation["why"] = reason
    explanation["confidence"] = "low"
    result["explanation"] = explanation
    unknowns = result.setdefault("unknowns", [])
    if reason not in unknowns:
        unknowns.append(reason)
    questions = result.setdefault("unresolvedQuestions", [])
    gate_question = "Complete and validate the individual evidence-backed review for all catalog requirements."
    if gate_question not in questions:
        questions.append(gate_question)
    return result


def _assessment_rule_coverage(root: Path, catalog: dict, level: str,
                              execution: dict, default_reason: str | None = None) -> dict:
    """Account for every rule required at the requested level.

    Automated rules count only when the selected enforcer reports them executed. Manual
    requirements count only when current, repository-scoped evidence validates. A raw
    ``executed: true`` flag can never satisfy a catalog-manual rule.
    """
    rules = required_rules(catalog, level)
    required_ids = {rule["id"] for rule in rules}
    try:
        evidence_entries = load_evidence(root / EVIDENCE_FILE)
        evidence_error = None
    except ClaimError as error:
        evidence_entries = []
        evidence_error = str(error)

    evidence_by_rule: dict[str, list[dict]] = defaultdict(list)
    malformed_evidence = []
    for entry in evidence_entries:
        if not isinstance(entry, dict):
            malformed_evidence.append({"rule": None, "problems": ["entry is not an object"]})
        elif entry.get("rule") in required_ids:
            evidence_by_rule[str(entry["rule"])].append(entry)
        elif not str(entry.get("rule", "")).strip():
            malformed_evidence.append({"rule": None, "problems": ["rule is missing"]})

    details = []
    automated_required = automated_checked = 0
    manual_required = manual_accepted = 0
    automated_not_executed = []
    manual_missing = []
    invalid_evidence = list(malformed_evidence)
    evidence_problems: dict[str, list[str]] = defaultdict(list)

    for rule in rules:
        rule_id = rule["id"]
        automation = rule.get("automation")
        entry = execution.get(rule_id)
        executed = isinstance(entry, dict) and entry.get("executed") is True
        reason = (entry.get("reason", "") if isinstance(entry, dict)
                  else (default_reason or
                        "the enforcer omitted this required rule from its execution map"))
        status = "not_assessed"

        if automation == "automated":
            automated_required += 1
            if executed:
                automated_checked += 1
                status = "deterministically_checked"
            else:
                automated_not_executed.append({"rule": rule_id,
                                               "reason": reason or default_reason or
                                               "the automated check did not run"})
                status = "automated_check_not_run"
        elif automation == "manual":
            manual_required += 1
            accepted = False
            for evidence in evidence_by_rule.get(rule_id, []):
                problems = validate_evidence(evidence, rule_id, root, date.today())
                if problems:
                    invalid_evidence.append({"rule": rule_id, "problems": problems})
                    evidence_problems[rule_id].extend(problems)
                else:
                    accepted = True
                    break
            if accepted:
                manual_accepted += 1
                status = "manual_evidence_accepted"
            else:
                manual_missing.append({
                    "rule": rule_id,
                    "reason": ("manual evidence file could not be read: " + evidence_error
                               if evidence_error else
                               ("manual evidence is present but invalid: "
                                + "; ".join(dict.fromkeys(evidence_problems[rule_id]))
                                if evidence_problems[rule_id] else
                                "the enforcer cannot decide this requirement; "
                                "current repository-scoped manual evidence is required")),
                })
                status = "manual_evidence_required"
        else:
            raise ClaimError(f"catalog rule {rule_id} has unknown automation {automation!r}")

        details.append({"rule": rule_id, "title": rule.get("title", rule_id),
                        "level": rule.get("level"), "automation": automation,
                        "status": status, "reason": reason if status == "automated_check_not_run" else None})

    accounted = automated_checked + manual_accepted
    required = len(rules)
    unresolved = required - accounted
    return {
        "level": level,
        "executionAvailable": bool(execution),
        "catalogRules": len(catalog.get("rules", [])),
        "required": required,
        "accountedFor": accounted,
        "notAssessed": unresolved,
        "coveragePercent": round(accounted * 100 / required) if required else 100,
        "complete": unresolved == 0,
        "automated": {"required": automated_required, "checked": automated_checked,
                       "notExecuted": automated_not_executed},
        "manual": {"required": manual_required, "acceptedEvidence": manual_accepted,
                   "missingEvidence": manual_missing},
        "invalidEvidence": invalid_evidence,
        "evidenceError": evidence_error,
        "rules": details,
        "outsideLevel": sorted(rule["id"] for rule in catalog.get("rules", [])
                                if rule["id"] not in required_ids),
    }



PROJECT_MARKERS = {
    ".csproj": "dotnet", ".fsproj": "dotnet",
    "package.json": "typescript/javascript",
    "go.mod": "go", "pyproject.toml": "python", "setup.py": "python",
    "pom.xml": "java", "build.gradle": "java", "build.gradle.kts": "java",
}
ARCHITECTURE_MARKERS = (
    "architecture", "archtest", "dependency-cruiser", "madge", "nx.json",
    "eslint.config", ".eslintrc", "Directory.Build", "CODEOWNERS",
)


def _find_repository_root(root: Path) -> Path | None:
    for candidate in (root, *root.parents):
        marker = candidate / ".git"
        if marker.is_dir() or marker.is_file():
            return candidate
    return None


def _repository_context_evidence(project_root: Path, repository_root: Path | None) -> list[str]:
    if repository_root is None:
        return []
    candidates = (
        "arch", "docs/architecture-map.md", "docs/agents/repository-architecture.md",
        "docs/agents/architecture-enforcement.md", "scripts/architecture-gate.mjs",
        "scripts/architecture-map.mjs", ".github/workflows", ".azure/pipelines",
        "CODEOWNERS", ".editorconfig", "Directory.Build.props", "Directory.Build.targets",
    )
    found = []
    for relative in candidates:
        path = repository_root / relative
        if path.is_file():
            found.append(os.path.relpath(path, project_root).replace("\\", "/"))
        elif path.is_dir():
            for child in path.rglob("*"):
                if child.is_file():
                    found.append(os.path.relpath(child, project_root).replace("\\", "/"))
    return sorted(set(found))


def _repository_architecture_inventory(root: Path) -> dict:
    """Inventory project roots and architecture evidence without inferring ownership."""
    projects = []
    workspaces = []
    architecture = []
    source_roots = set()
    source_classification = {"production": 0, "tests": 0, "tooling": 0, "generated": 0}
    ci_workflows = []
    for path in _walk(root):
        relative = path.relative_to(root).as_posix()
        name = path.name.lower()
        language = PROJECT_MARKERS.get(path.suffix.lower())
        if name in PROJECT_MARKERS:
            language = PROJECT_MARKERS[name]
        if language and name not in {"package-lock.json", "pnpm-lock.yaml"}:
            projects.append({"manifest": relative, "directory": path.parent.relative_to(root).as_posix() or ".",
                             "kind": path.name, "language": language})
        if name.endswith((".sln", ".slnx")) or name in {"pnpm-workspace.yaml", "nx.json", "turbo.json"}:
            workspaces.append(relative)
        if path.suffix.lower() in SOURCE_EXTENSIONS:
            relative_parts = [part.lower() for part in path.relative_to(root).parts]
            source_roots.add(path.parent.relative_to(root).as_posix().split("/")[0])
            source_name = path.name.lower()
            is_test = (any(part in {"test", "tests", "__tests__", "spec", "specs", "e2e"} or
                           part.endswith((".tests", ".test", ".spec", ".specs"))
                           for part in relative_parts)
                       or source_name.endswith((".test.ts", ".test.tsx", ".test.js", ".test.jsx",
                                                ".spec.ts", ".spec.tsx", ".spec.js", ".spec.jsx")))
            is_tooling = (source_name.startswith(("eslint.config.", "vite.config.", "vitest.config.",
                                                  "playwright.config.", "tsconfig."))
                          or source_name == "vite-env.d.ts")
            is_generated = (source_name.endswith((".g.cs", ".generated.cs", ".designer.cs"))
                            or ".generated." in source_name)
            if is_test:
                source_classification["tests"] += 1
            elif is_tooling:
                source_classification["tooling"] += 1
            elif is_generated:
                source_classification["generated"] += 1
            else:
                source_classification["production"] += 1
        if any(marker in name for marker in ARCHITECTURE_MARKERS):
            architecture.append(relative)
        if relative.startswith(".github/workflows/") or relative.startswith(".azure/pipelines/"):
            ci_workflows.append(relative)
    # _walk intentionally excludes hidden directories for source discovery; inspect known CI roots
    # explicitly so workflow evidence is not silently omitted.
    for ci_root in (root / ".github" / "workflows", root / ".azure" / "pipelines"):
        if ci_root.is_dir():
            for path in ci_root.rglob("*"):
                if path.is_file():
                    ci_workflows.append(path.relative_to(root).as_posix())
    projects.sort(key=lambda item: (item["directory"], item["manifest"]))
    workspaces.sort()
    architecture.sort()
    ci_workflows.sort()
    repository_root = _find_repository_root(root)
    repository_context = _repository_context_evidence(root, repository_root)
    context_workflows = [path for path in repository_context
                         if ".github/workflows/" in path or ".azure/pipelines/" in path]
    context_architecture = [path for path in repository_context
                            if path not in context_workflows]
    return {
        "projectRoot": str(root),
        "repositoryRoot": str(repository_root) if repository_root else None,
        "projects": projects[:500],
        "projectCount": len(projects),
        "workspaces": workspaces[:100],
        "sourceTopLevelRoots": sorted(source_roots),
        "sourceClassification": source_classification,
        "architectureEvidence": architecture[:300],
        "architectureEvidenceCount": len(architecture),
        "repositoryContextEvidence": repository_context[:300],
        "repositoryContextEvidenceCount": len(repository_context),
        "repositoryArchitectureEvidence": context_architecture[:200],
        "ciWorkflows": sorted(set(ci_workflows + context_workflows))[:200],
        "ciWorkflowCount": len(set(ci_workflows + context_workflows)),
        "ownershipInference": "not_performed; project and directory boundaries are discovery evidence, not approved ACIMA modules",
    }


def _comprehensive_rule_review(catalog: dict) -> dict:
    """Expose every catalog requirement for qualitative review without claiming it was reviewed."""
    entries = []
    for rule in catalog.get("rules", []):
        entries.append({
            "rule": rule["id"],
            "level": rule.get("level"),
            "title": rule.get("title", rule["id"]),
            "requirement": rule.get("summary", ""),
            "automation": rule.get("automation"),
            "qualitativeStatus": "not_reviewed",
            "applicability": "undetermined",
            "evidence": [],
            "reviewInstruction": ("Inspect the actual implementation, ownership, dataflow, callers, consumers, "
                                  "configuration and relevant tests. Do not infer a pass from absent findings "
                                  "or from a deterministic check that did not run."),
        })
    return {
        "scope": "all_catalog_levels",
        "levels": {level: sum(1 for item in entries if item["level"] == level)
                   for level in ("L1", "L2", "L3")},
        "required": len(entries),
        "reviewed": 0,
        "pending": len(entries),
        "coverageComplete": False,
        "decisionComplete": False,
        "complete": False,
        "statusMeaning": "The CLI exposes all requirements for the adoption agent's qualitative review. "
                         "This inventory is not itself a completed architectural assessment.",
        "rules": entries,
    }

def _set_assessment_completion(report: dict, verdict: str) -> None:
    review = report.get("comprehensiveRuleReview") or {}
    review_coverage_complete = bool(review.get("coverageComplete", review.get("complete")))
    review_decision_complete = bool(review.get("decisionComplete", review.get("complete")))
    unit_map = report.get("unitMap") or {}
    unit_map_complete = bool(unit_map.get("present") and unit_map.get("count", 0) > 0)
    deterministic_complete = verdict == "ASSESSED" and unit_map_complete
    complete = deterministic_complete and review_decision_complete
    reasons = []
    if not review_coverage_complete:
        reasons.append("all catalog requirements need one valid, evidence-backed disposition")
    elif not review_decision_complete:
        reasons.append("one or more requirements remain unresolved; see their insufficient-evidence dispositions")
    if not unit_map_complete:
        reasons.append("a declared ACIMA module/unit map is required for deterministic checks")
    if verdict != "ASSESSED":
        reasons.append("deterministic assessment did not complete successfully: " + verdict)
    gate = report.get("ownershipGate") or {}
    if gate.get("status") == "blocked":
        reasons.append("ownership-dependent deterministic checks are blocked until the module map is reviewed and approved")
    report["assessmentCompletion"] = {
        "complete": complete,
        "qualitativeReviewCoverageComplete": review_coverage_complete,
        "qualitativeReviewDecisionComplete": review_decision_complete,
        "qualitativeReviewComplete": review_decision_complete,
        "deterministicAssessmentComplete": deterministic_complete,
        "unitMapComplete": unit_map_complete,
        "ownershipGate": gate.get("status", "not recorded"),
        "reasons": reasons,
    }


def assess_project(root: Path, language: str | None = None,
                   level: str | None = None,
                   review_path: Path | None = None) -> tuple[int, dict]:
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
    catalog = json.loads((ACIMA_ROOT / "tools/acima-spec/rules.json").read_text(encoding="utf-8"))
    report: dict = {
        "readOnly": True,
        "root": str(root),
        "languages": languages,
        "sourceFiles": sum(counts.values()),
        "sourceCounts": counts,
        "repositoryInventory": _repository_architecture_inventory(root),
        "comprehensiveRuleReview": _comprehensive_rule_review(catalog),
        "assessmentCompletion": {"complete": False, "qualitativeReviewComplete": False,
                                 "unitMapComplete": False, "reasons": [
                                     "all catalog rules require an evidence-backed qualitative disposition",
                                     "a declared module/unit map and deterministic assessment are required"]},
        "requestedLevel": level or "L1",
        "limitation": ("Read-only assessment. It is not a conformance claim and it computes no "
                       "health score; rules without evidence are reported as not evaluated."),
    }

    if review_path is not None:
        try:
            catalog_sha256 = hashlib.sha256((ACIMA_ROOT / "tools/acima-spec/rules.json").read_bytes()).hexdigest()
            review = load_and_validate_review(review_path.resolve(), root, catalog, catalog_sha256)
            original_rules = {item["rule"]: item
                              for item in report["comprehensiveRuleReview"]["rules"]}
            merged_rules = []
            for reviewed_rule in review["rules"]:
                base = original_rules.get(reviewed_rule["rule"], {})
                merged_rules.append({
                    **base,
                    "qualitativeStatus": reviewed_rule["status"] if reviewed_rule["valid"] else "invalid",
                    "reviewValid": reviewed_rule["valid"],
                    "rationale": reviewed_rule["rationale"],
                    "evidence": reviewed_rule["evidence"],
                    "reviewProblems": reviewed_rule["problems"],
                })
            report["comprehensiveRuleReview"] = {
                **report["comprehensiveRuleReview"],
                "reviewed": review["reviewed"], "pending": review["pending"],
                "coverageComplete": review["coverageComplete"],
                "decisionComplete": review["decisionComplete"],
                "complete": review["complete"], "status": review["status"],
                "counts": review["counts"], "unresolved": review["unresolved"],
                "evidenceBackedDispositions": review["evidenceBackedDispositions"],
                "rules": merged_rules,
                "validation": {key: value for key, value in review.items() if key != "rules"},
            }
        except ReviewValidationError as error:
            report["comprehensiveRuleReview"]["validationError"] = str(error)
            report["comprehensiveRuleReview"]["status"] = "invalid"

    if report["sourceFiles"] == 0:
        report["verdict"] = "NO_SOURCE"
        report["verdictMeaning"] = VERDICT_MEANING["NO_SOURCE"]
        _set_assessment_completion(report, report["verdict"])
        report["nextSteps"] = _next_steps(report)
        report["assessmentResult"] = build_gated_assessment_result(report, None)
        return 0, report

    try:
        config = read_config(root)
    except ConfigError as error:
        report.update({"verdict": "INVALID_CONFIG",
                       "verdictMeaning": VERDICT_MEANING["INVALID_CONFIG"],
                       "error": str(error)})
        _set_assessment_completion(report, report["verdict"])
        report["nextSteps"] = _next_steps(report)
        report["assessmentResult"] = build_gated_assessment_result(report, None)
        return 2, report

    try:
        report["moduleMap"] = discover_module_map(root, config=config)
    except (ModuleMapError, OSError) as error:
        report["moduleMap"] = {
            "status": "discovery_failed",
            "error": str(error),
            "authoritativeMap": {"present": config is not None, "status": "unknown"},
            "proposal": None,
            "nextDecision": "Complete module-map discovery manually; no ownership was inferred.",
        }
    authority = (report.get("moduleMap") or {}).get("authoritativeMap") or {}
    ownership_ready = authority.get("status") == "complete"
    report["ownershipGate"] = {
        "status": "ready" if ownership_ready else "blocked",
        "reason": ("An authoritative module map covers the discovered production source."
                   if ownership_ready else
                   "Ownership-dependent deterministic checks require an explicitly approved map. "
                   "Independent qualitative review continues for every catalog requirement."),
        "ownershipDependentRules": sorted(OWNERSHIP_DEPENDENT_RULES),
        "independentReviewContinues": True,
        "deterministicChecksBlocked": not ownership_ready,
        "proposalReviewRequired": bool((report.get("moduleMap") or {}).get("proposal")),
    }
    report["requestedLevel"] = level or (config or {}).get("level") or "L1"
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
    requested_level = level or (config or {}).get("level") or "L1"
    try:
        level_rules = required_rules(catalog, requested_level)
    except ClaimError as error:
        report.update({"verdict": "INVALID_ASSESSMENT", "verdictMeaning": str(error),
                       "error": str(error)})
        report["nextSteps"] = _next_steps(report)
        report["assessmentResult"] = build_gated_assessment_result(report, config)
        return 2, report
    manual = sorted(rule["id"] for rule in level_rules
                    if rule.get("automation") == "manual")
    report["applicable"] = {
        "catalogRules": len(catalog["rules"]),
        "requiredRules": len(level_rules),
        "portableRules": sum(1 for rule in level_rules if rule.get("automation") == "automated"),
        "automatedRules": sum(1 for rule in level_rules if rule.get("automation") == "automated"),
        "manualRules": manual,
        "manualEvidence": manual,
    }

    def finish(verdict: str, code: int = 0, **extra) -> tuple[int, dict]:
        report["verdict"] = verdict
        report["verdictMeaning"] = VERDICT_MEANING[verdict]
        report.update(extra)
        if verdict != "ASSESSED":
            reason = str(extra.get("error") or extra.get("detail") or
                         VERDICT_MEANING[verdict])
            report["coverage"] = _assessment_rule_coverage(
                root, catalog, requested_level, {}, default_reason=reason)
        _set_assessment_completion(report, verdict)
        report["nextSteps"] = _next_steps(report)
        report["assessmentResult"] = build_gated_assessment_result(report, config)
        return code, report

    mode = (config or {}).get("mode") or "base"
    if mode != "base" or (root / "acima.topology.json").is_file():
        return finish("UNSUPPORTED_PROFILE",
                      detail="architecture mode %r is not supported by this revision" % mode)

    if config is None:
        return finish("NEEDS_UNIT_MAP")
    spec = enforcer_spec(selected or "")
    if spec is None:
        return finish("UNSUPPORTED_LANGUAGE")
    if shutil.which(spec["run"][0]) is None:
        return finish("TOOLCHAIN_MISSING", detail="%s is not installed" % spec["run"][0])

    code, payload, error = run_enforcer(root, selected, None, level)
    if payload is None:
        return finish("INVALID_ASSESSMENT", 2, error=error)
    execution = payload.get("execution") or {}
    measured_level = payload.get("level") or requested_level
    if measured_level != requested_level:
        return finish("INVALID_ASSESSMENT", 2,
                      error=(f"enforcer measured level {measured_level!r}, but the assessment "
                             f"requested {requested_level!r}"))
    try:
        rule_coverage = _assessment_rule_coverage(root, catalog, requested_level, execution)
    except ClaimError as error:
        return finish("INVALID_ASSESSMENT", 2, error=str(error))
    executed = sorted(item["rule"] for item in rule_coverage["rules"]
                      if item["status"] == "deterministically_checked")
    not_executed = {item["rule"]: item["reason"]
                    for item in rule_coverage["automated"]["notExecuted"]}
    findings = payload.get("findings", [])
    by_rule: dict[str, int] = defaultdict(int)
    for finding in findings:
        by_rule[finding["rule"]] += 1
    report["coverage"] = {
        **rule_coverage,
        "executed": len(executed),
        "notExecuted": sorted(not_executed),
        "notExecutedReasons": not_executed,
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
    module_map = report.get("moduleMap") or {}
    if module_map:
        authority = module_map.get("authoritativeMap") or {}
        lines.append("  map quality %s - %s" % (authority.get("status", "unknown"),
                                                 authority.get("summary", "not recorded")))
        proposal = module_map.get("proposal") or {}
        if proposal:
            lines.append("  proposal    %s candidate module(s), %s recommendation(s), %s unassigned path(s)"
                         % (len(proposal.get("modules", [])), len(proposal.get("recommendations", [])),
                            len(proposal.get("unassigned", []))))
            lines.append("  ownership   review required; inferred boundaries are not authoritative")
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
    inventory = report.get("repositoryInventory") or {}
    review = report.get("comprehensiveRuleReview") or {}
    if inventory:
        lines.append("  projects    %s manifests; %s architecture artifacts; %s CI workflows" %
                     (inventory.get("projectCount", 0), inventory.get("architectureEvidenceCount", 0),
                      inventory.get("ciWorkflowCount", 0)))
    if review:
        lines.append("  all rules   %s catalog requirements; %s evidence-backed dispositions; %s not dispositioned" %
                     (review.get("required", 0), review.get("reviewed", 0), review.get("pending", 0)))
        lines.append("  review      coverage %s; unresolved decisions %s" %
                     ("complete" if review.get("coverageComplete") else "incomplete",
                      review.get("unresolved", 0)))
    completion = report.get("assessmentCompletion") or {}
    if completion:
        lines.append("  qualitative %s; deterministic %s; overall %s" %
                     ("complete" if completion.get("qualitativeReviewDecisionComplete") else
                      "coverage complete, unresolved" if completion.get("qualitativeReviewCoverageComplete") else "incomplete",
                      "complete" if completion.get("deterministicAssessmentComplete") else "incomplete",
                      "complete" if completion.get("complete") else "incomplete"))
        for reason in completion.get("reasons", []):
            lines.append("              - " + reason)
    coverage = report.get("coverage")
    if coverage:
        lines.append("  coverage    %s/%s required rules accounted for (%s%%)"
                     % (coverage["accountedFor"], coverage["required"],
                        coverage["coveragePercent"]))
        lines.append("              %s/%s automated checks ran; %s/%s manual reviews evidenced"
                     % (coverage["automated"]["checked"], coverage["automated"]["required"],
                        coverage["manual"]["acceptedEvidence"], coverage["manual"]["required"]))
        lines.append("              %s automated checks not run; %s manual reviews still needed"
                     % (len(coverage["automated"]["notExecuted"]),
                        len(coverage["manual"]["missingEvidence"])))
        lines.append("              Coverage completeness is not a conformance claim.")
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
    manual = [item["rule"] for item in (coverage or {}).get("manual", {}).get(
        "missingEvidence", [])] if coverage else []
    if manual:
        lines.append("  human       %s required manual review(s) still need evidence: %s"
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
    inventory = report.get("repositoryInventory") or {}
    lines += ["## Repository discovery", "",
              f"- Project manifests discovered: **{inventory.get('projectCount', 0)}**",
              f"- Architecture/enforcement artifacts discovered: **{inventory.get('architectureEvidenceCount', 0)}**",
              f"- CI workflows discovered: **{inventory.get('ciWorkflowCount', 0)}**",
              f"- Top-level source roots: {', '.join(inventory.get('sourceTopLevelRoots', [])) or 'none'}",
              f"- Source classification: {inventory.get('sourceClassification', {})}",
              "- Discovered projects and architecture files are evidence for review, not approved ACIMA modules.", ""]
    if inventory.get("projects"):
        lines += ["### Project manifests", ""]
        lines += [f"- `{item['manifest']}` ({item['language']})" for item in inventory["projects"]]
    if inventory.get("architectureEvidence") or inventory.get("repositoryArchitectureEvidence"):
        lines += ["", "### Existing architecture evidence", ""]
        lines += [f"- `{item}`" for item in inventory.get("architectureEvidence", [])]
        lines += [f"- Repository context: `{item}`" for item in inventory.get("repositoryArchitectureEvidence", [])]
    completion = report.get("assessmentCompletion") or {}
    lines += ["", "## Assessment completion", "",
              "- Overall assessment: **%s**" % ("complete" if completion.get("complete") else "incomplete"),
              "- Qualitative disposition coverage: **%s**" % ("55/55 complete" if completion.get("qualitativeReviewCoverageComplete") else "incomplete"),
              "- Qualitative decisions resolved: **%s**" % ("yes" if completion.get("qualitativeReviewDecisionComplete") else "no"),
              "- Deterministic assessment: **%s**" % ("complete" if completion.get("deterministicAssessmentComplete") else "incomplete"),
              "- Declared unit map: **%s**" % ("present" if completion.get("unitMapComplete") else "missing"),
              *["- Remaining: " + reason for reason in completion.get("reasons", [])], ""]
    review = report.get("comprehensiveRuleReview") or {}
    if review:
        lines += ["", "## Comprehensive ACIMA requirement review", "",
                  f"- Catalog requirements: **{review.get('required', 0)}** across L1, L2 and L3",
                  f"- Qualitatively reviewed by an adoption agent: **{review.get('reviewed', 0)}**",
                  f"- Pending qualitative review: **{review.get('pending', 0)}**",
                  f"- Unresolved insufficient-evidence dispositions: **{review.get('unresolved', 0)}**",
                  "- The CLI does not perform semantic code review. Each requirement must be traced through actual code and evidence before its status can change.", "",
                  "| Level | Requirement | Automation | Status |",
                  "|---|---|---|---|"]
        for item in review.get("rules", []):
            lines.append(f"| {item['level']} | {item['title']} (`{item['rule']}`) | {item['automation']} | {item['qualitativeStatus']} |")
    coverage = report.get("coverage")
    if coverage:
        lines += ["", "## Verification coverage", "",
                  "- Required at `%s`: **%s**" % (coverage["level"], coverage["required"]),
                  "- Accounted for: **%s/%s (%s%%)**" %
                  (coverage["accountedFor"], coverage["required"], coverage["coveragePercent"]),
                  "- Automated checks: **%s/%s ran**" %
                  (coverage["automated"]["checked"], coverage["automated"]["required"]),
                  "- Manual evidence: **%s/%s accepted**" %
                  (coverage["manual"]["acceptedEvidence"], coverage["manual"]["required"]),
                  "- Automated checks not run: **%s**" % len(coverage["automated"]["notExecuted"]),
                  "- Manual evidence still required: **%s**" %
                  len(coverage["manual"]["missingEvidence"]),
                  "- Coverage complete: **%s**" % ("yes" if coverage["complete"] else "no"),
                  "",
                  "Coverage means every required rule was checked or has accepted manual evidence; "
                  "it does not mean the repository has no findings or is fully conformant."]
        if coverage["automated"]["notExecuted"]:
            lines += ["", "### Automated checks not run", ""]
            lines += ["- `%s`: %s" % (item["rule"], item["reason"])
                      for item in coverage["automated"]["notExecuted"]]
        if coverage["manual"]["missingEvidence"]:
            lines += ["", "### Manual evidence required", ""]
            lines += ["- `%s`: %s" % (item["rule"], item["reason"])
                      for item in coverage["manual"]["missingEvidence"]]
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
    manual = [item["rule"] for item in (coverage or {}).get("manual", {}).get(
        "missingEvidence", [])] if coverage else []
    if manual:
        lines += ["", "## Requires human evidence", "",
                  "These required reviews do not yet have accepted, current, repository-scoped "
                  "evidence: " + ", ".join("`%s`" % rule for rule in manual) + "."]
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


def _sha256_file(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _git_dirty(root: Path) -> list[str] | None:
    """Tracked changes in the working tree, or None when Git cannot answer."""
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=no"],
            capture_output=True, text=True)
    except OSError:
        return None
    if result.returncode != 0:
        return None
    paths: list[str] = []
    for line in result.stdout.splitlines():
        if len(line) < 4:
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if path:
            paths.append(path)
    return paths


def _relevant_change(path: str) -> bool:
    normalized = path.replace("\\", "/")
    if normalized in (CONFIG_NAME, ".acima/baseline.json", EVIDENCE_FILE):
        return True
    if normalized.startswith((".acima/", ".github/workflows/")):
        return True
    return Path(normalized).suffix.lower() in SOURCE_EXTENSIONS


def _source_inventory_digest(inventory: dict[str, int]) -> str:
    encoded = json.dumps(inventory, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _currentness_result(state: str, evidence: str, checks: dict[str, str],
                        head: str | None = None, repository: str | None = None) -> dict:
    return {
        "state": state,
        "current": state == "current",
        "evidence": evidence,
        "head": head,
        "repository": repository,
        "checks": checks,
    }


def _claim_currentness(root: Path, payload: dict, config: dict | None, level: str | None,
                       catalog_version: str | None, catalog_sha: str | None,
                       inventory: dict[str, int] | None = None) -> dict:
    """Establish whether a run describes this repository, commit and configuration now.

    Missing fields are not treated as a match. An older commit is historical evidence, not a
    current claim. A dirty source tree or a changed catalogue/config requires fresh measurement.
    """
    checks: dict[str, str] = {}
    head = _git_head(root)
    remote = _git_remote(root)
    dirty = _git_dirty(root)
    if not head:
        return _currentness_result("git-unavailable",
                                   "Git HEAD is unavailable; currentness cannot be established.",
                                   checks)
    if not remote:
        return _currentness_result("git-unavailable",
                                   "the origin remote is unavailable; repository identity "
                                   "cannot be established.", checks, head)
    repository = str(payload.get("repository") or "").strip()
    current_repository = _repository_identity(remote)
    checks["repository"] = repository or "missing"
    if not repository:
        return _currentness_result("missing-provenance", "the run has no repository identity.",
                                   checks, head, current_repository)
    if _repository_identity(repository) != current_repository:
        return _currentness_result(
            "repository-mismatch",
            f"the run belongs to {repository!r}, not the current repository "
            f"{current_repository!r}.", checks, head, current_repository)
    if dirty is None:
        return _currentness_result("git-unavailable",
                                   "the working-tree state cannot be established.", checks, head,
                                   current_repository)
    changed = [path for path in dirty if _relevant_change(path)]
    if changed:
        checks["workingTree"] = ", ".join(changed[:5])
        return _currentness_result(
            "uncommitted",
            "source, configuration or governance files are modified in the working tree; a "
            "committed report cannot represent that tree.", checks, head, current_repository)
    commit = str(payload.get("commit") or "").strip().lower()
    checks["commit"] = commit or "missing"
    if not commit or not re.fullmatch(r"[0-9a-f]{7,40}", commit):
        return _currentness_result("missing-provenance",
                                   "the run has no valid commit identity.", checks, head,
                                   current_repository)
    if not head.lower().startswith(commit):
        return _currentness_result(
            "historical",
            f"the run was measured at {commit[:12]}, not current HEAD {head[:12]}.",
            checks, head, current_repository)
    declared_standard = str((config or {}).get("standard") or "").strip()
    run_standard = str(payload.get("standard") or "").strip()
    checks["standard"] = run_standard or "missing"
    if not declared_standard:
        return _currentness_result("missing-provenance",
                                   "the configuration declares no standard version.", checks,
                                   head, current_repository)
    if not run_standard:
        return _currentness_result("missing-provenance",
                                   "the run records no standard version.", checks, head,
                                   current_repository)
    if run_standard != declared_standard:
        return _currentness_result(
            "standard-mismatch",
            f"the run records standard {run_standard or 'missing'}, not the declared "
            f"{declared_standard}.", checks, head, current_repository)
    if not catalog_sha:
        return _currentness_result("missing-provenance",
                                   "the current catalog hash is unavailable.", checks, head,
                                   current_repository)
    run_catalog = str(payload.get("catalogSha256") or "").strip().lower()
    checks["catalogSha256"] = run_catalog or "missing"
    if not run_catalog:
        return _currentness_result("missing-provenance",
                                   "the run records no rule-catalog hash.", checks, head,
                                   current_repository)
    if run_catalog != catalog_sha:
        return _currentness_result(
            "catalog-mismatch", "the run used a different rule catalog; recalibrate and measure "
            "again.", checks, head, current_repository)
    config_sha = _sha256_file(root / CONFIG_NAME)
    run_config = str(payload.get("configurationSha256") or "").strip().lower()
    checks["configurationSha256"] = run_config or "missing"
    if not config_sha:
        return _currentness_result("missing-provenance",
                                   "the current configuration cannot be read.", checks, head,
                                   current_repository)
    if not run_config:
        return _currentness_result("missing-provenance",
                                   "the run records no configuration hash.", checks, head,
                                   current_repository)
    if run_config != config_sha:
        return _currentness_result(
            "configuration-mismatch", "the run used a different configuration; measure again.",
            checks, head, current_repository)
    run_enforcer = str(payload.get("enforcerVersion") or "").strip()
    checks["enforcerVersion"] = run_enforcer or "missing"
    if not run_enforcer:
        return _currentness_result("missing-provenance",
                                   "the run records no enforcer version.", checks, head,
                                   current_repository)
    if run_enforcer != ENFORCER_VERSION:
        return _currentness_result(
            "enforcer-mismatch", "the run was produced by a different enforcer version.",
            checks, head, current_repository)
    expected_level = level or (config or {}).get("level") or payload.get("level")
    if payload.get("level") != expected_level:
        return _currentness_result(
            "level-mismatch", f"the run is {payload.get('level')!r}, not the declared "
            f"{expected_level!r}.", checks, head, current_repository)
    current_inventory = inventory if inventory is not None else _source_inventory(root)
    inventory_digest = _source_inventory_digest(current_inventory)
    run_inventory = payload.get("sourceInventorySha256")
    if not run_inventory and isinstance(payload.get("sourceInventory"), dict):
        run_inventory = _source_inventory_digest(payload["sourceInventory"])
    checks["sourceInventorySha256"] = str(run_inventory or "missing")
    if not run_inventory:
        return _currentness_result("missing-provenance",
                                   "the run has no source inventory digest.", checks, head,
                                   current_repository)
    if run_inventory != inventory_digest:
        return _currentness_result(
            "source-mismatch", "the source inventory has changed since measurement.", checks,
            head, current_repository)
    sources = payload.get("sourceFiles")
    if isinstance(sources, bool) or not isinstance(sources, int) or sources <= 0:
        return _currentness_result("missing-provenance",
                                   "the run has no positive source-file count.", checks, head,
                                   current_repository)
    baseline_sha = _sha256_file(root / ".acima/baseline.json")
    run_baseline = str(payload.get("baselineSha256") or "").strip().lower()
    if baseline_sha:
        checks["baselineSha256"] = run_baseline or "missing"
        if not run_baseline:
            return _currentness_result("missing-provenance",
                                       "the run records no baseline identity.", checks, head,
                                       current_repository)
        if run_baseline != baseline_sha:
            return _currentness_result(
                "baseline-mismatch", "the fingerprint baseline changed after measurement.",
                checks, head, current_repository)
    elif run_baseline:
        return _currentness_result(
            "baseline-mismatch", "the run records a baseline that is no longer present.",
            checks, head, current_repository)
    checks["head"] = head
    return _currentness_result(
        "current", f"run, repository, HEAD {head[:12]}, catalog and configuration match.",
        checks, head, current_repository)


def _attach_run_provenance(root: Path, payload: dict) -> dict:
    """Add current evidence to a freshly produced run without rewriting old reports."""
    if not isinstance(payload, dict):
        return payload
    updated = dict(payload)
    remote = _git_remote(root)
    head = _git_head(root)
    catalog_version, catalog_sha = _catalog_version_and_hash()
    config_sha = _sha256_file(root / CONFIG_NAME)
    inventory = _source_inventory(root)
    if remote:
        updated.setdefault("repository", _repository_identity(remote))
    if head:
        updated.setdefault("commit", head)
    if catalog_version:
        updated.setdefault("catalogVersion", catalog_version)
    if catalog_sha:
        updated.setdefault("catalogSha256", catalog_sha)
    if config_sha:
        updated.setdefault("configurationSha256", config_sha)
    updated.setdefault("sourceInventory", inventory)
    updated.setdefault("sourceInventorySha256", _source_inventory_digest(inventory))
    updated.setdefault("enforcerVersion", ENFORCER_VERSION)
    updated.setdefault("provenanceVersion", PROVENANCE_VERSION)
    baseline_sha = _sha256_file(root / ".acima/baseline.json")
    if baseline_sha:
        updated.setdefault("baselineSha256", baseline_sha)
    return updated


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


def _claim_step(root: Path, runs: list[dict], level: str | None, config: dict | None,
                catalog_version: str | None, catalog_sha: str | None) -> dict:
    if not runs:
        step = _step(10, "claim", STEP_NOT_STARTED, "no measured run to base a claim on",
                     "measure a run, then record manual evidence where a rule is manual")
        step["claimState"] = "no-claim"
        return step
    newest = runs[-1]
    evidence_path = root / EVIDENCE_FILE
    try:
        evidence = load_evidence(evidence_path) if evidence_path.is_file() else {}
        claim = assess_claim(
            newest["payload"], load_catalog(ACIMA_ROOT),
            level=level or newest["payload"].get("level") or "L1",
            evidence=evidence, evidence_path=EVIDENCE_FILE, root=root,
        )
        currentness = _claim_currentness(
            root, newest["payload"], config, level, catalog_version, catalog_sha)
        claim.update({"currentness": currentness["state"],
                      "current": currentness["current"], "provenance": currentness})
    except (ClaimError, OSError, json.JSONDecodeError, ValueError) as error:
        step = _step(10, "claim", STEP_BLOCKED, f"{newest['path']}: {error}",
                     "fix or replace the manual evidence, then recompute the claim")
        step["claimState"] = "invalid"
        return step

    def result(state: str, claim_state: str, evidence: str, remedy: str = "") -> dict:
        step = _step(10, "claim", state, evidence, remedy)
        step["claimState"] = claim_state
        step["claim"] = claim
        step["provenance"] = currentness
        return step

    invalid = claim.get("invalidEvidence") or []
    if invalid:
        return result(
            STEP_BLOCKED, "invalid",
            f"{len(invalid)} evidence entr(y/ies) are invalid; the claim is {claim['claim']}",
            "correct the evidence fields or expiry, then recompute")
    if claim["claim"] == FULL:
        if currentness["current"]:
            return result(
                STEP_COMPLETE, "current",
                f"FULL CONFORMANCE at {claim.get('level')} from {newest['path']}; "
                f"current HEAD {str(currentness.get('head'))[:12]}")
        if currentness["state"] == "historical":
            return result(
                STEP_IN_PROGRESS, "historical",
                f"historical FULL CONFORMANCE at {claim.get('level')} from {newest['path']}; "
                f"{currentness['evidence']}",
                "measure the current HEAD and record a fresh claim")
        if currentness["state"] in ("missing-provenance", "git-unavailable"):
            return result(
                STEP_IN_PROGRESS, "incomplete",
                f"FULL CONFORMANCE rule coverage from {newest['path']}, but currentness is "
                f"not established: {currentness['evidence']}",
                "record repository, commit, catalog, configuration and source provenance")
        return result(
            STEP_IN_PROGRESS, "stale",
            f"FULL CONFORMANCE rule coverage from {newest['path']} is stale: "
            f"{currentness['evidence']}",
            "re-measure after the repository, configuration or catalog changed")
    missing = claim.get("missing") or []
    claim_state = "incomplete"
    if currentness["state"] == "historical":
        claim_state = "historical"
    elif currentness["state"] in ("uncommitted", "repository-mismatch",
                                  "catalog-mismatch", "standard-mismatch",
                                  "configuration-mismatch", "level-mismatch",
                                  "source-mismatch", "baseline-mismatch",
                                  "enforcer-mismatch"):
        claim_state = "stale"
    return result(
        STEP_IN_PROGRESS, claim_state,
        f"PARTIAL ASSESSMENT at {claim.get('level')}: "
        f"{len(missing)} required rule(s) have no accepted evidence; "
        f"currentness {currentness['state']}: {currentness['evidence']}",
        "record repository-scoped manual evidence for the named rules, then measure again")


ADOPTION_SCOPE_FILE = ".acima/adoption-scope.json"
ADOPTION_SCOPE_ALT = "docs/acima/adoption-scope.json"
ASSESSMENT_EVIDENCE = "docs/acima/assessment.json"
SCOPE_DISPOSITIONS = ("required", "approved", "declined", "deferred", "optional",
                      "not-applicable")
OBJECTIVE_DEFS = (
    {"id": "assessment", "title": "Architecture assessment", "dependsOn": ()},
    {"id": "local-enforcement", "title": "Local enforcement", "dependsOn": ()},
    {"id": "baseline-waivers", "title": "Baseline and waiver management",
     "dependsOn": ("local-enforcement",)},
    {"id": "ci-enforcement", "title": "CI enforcement",
     "dependsOn": ("local-enforcement",)},
    {"id": "full-conformance", "title": "Full conformance evidence",
     "dependsOn": ("local-enforcement",)},
    {"id": "developer-handoff", "title": "Developer guidance and handoff",
     "dependsOn": (), "optionalByDefault": True},
    {"id": "communication-governance", "title": "Communication and governance materials",
     "dependsOn": (), "optionalByDefault": True},
)
OBJECTIVE_BY_ID = {entry["id"]: entry for entry in OBJECTIVE_DEFS}
OBJECTIVE_IDS = tuple(entry["id"] for entry in OBJECTIVE_DEFS)
OBJECTIVE_ALIASES = {
    "assessment-only": "assessment", "assessment_only": "assessment",
    "local": "local-enforcement", "local-only": "local-enforcement",
    "local_only": "local-enforcement",
    "baseline": "baseline-waivers", "waivers": "baseline-waivers",
    "baseline-and-waivers": "baseline-waivers",
    "ci": "ci-enforcement", "ci-gate": "ci-enforcement",
    "conformance": "full-conformance", "full": "full-conformance",
    "handoff": "developer-handoff", "developer-guidance": "developer-handoff",
    "communication": "communication-governance", "governance": "communication-governance",
}
OBJECTIVE_LABEL = dict(STATE_LABEL, DECLINED="declined", DEFERRED="deferred",
                       OPTIONAL="optional, not required", UNSUPPORTED="unsupported")
HANDOFF_DOCUMENTS = ("docs/acima/handoff.md", "docs/acima/developer-guide.md")
COMMUNICATION_DOCUMENTS = ("docs/acima/communication-plan.md", "docs/acima/governance.md")


def _next_action(action: str = "", *, why: str = "", command: str = "", done: str = "",
                 approval: bool = False, writes: bool = False, effect: str = "") -> dict:
    return {"action": action, "why": why, "command": command, "doneWhen": done,
            "approvalRequired": approval, "writes": writes, "effect": effect}


def _scope_placeholder(problem: str = "") -> dict:
    return {
        "present": False, "source": None, "state": STEP_UNKNOWN, "approvedBy": None,
        "approvedOn": None, "proposal": None, "objectives": [], "dispositions": {},
        "required": [], "approved": [], "declined": [], "deferred": [], "optional": [],
        "notApplicable": [], "unsupported": [], "autoRequired": [], "problems":
        ([problem] if problem else []), "conflicts": [], "raw": {},
    }


def _scope_entries(raw: object, problems: list[str]) -> list[dict]:
    entries: list[dict] = []

    def add(identifier: object, disposition: object, reason: object = "",
            revisit: object = "") -> None:
        if not isinstance(identifier, str) or not identifier.strip():
            problems.append("every objective needs a non-empty id")
            return
        name = identifier.strip()
        name = OBJECTIVE_ALIASES.get(name, name)
        if isinstance(disposition, str):
            disposition = disposition.strip().lower().replace("_", "-")
            if disposition in ("notapplicable", "n/a"):
                disposition = "not-applicable"
        if not isinstance(disposition, str) or disposition not in SCOPE_DISPOSITIONS:
            problems.append("objective %r has disposition %r; expected one of %s"
                            % (name, disposition, ", ".join(SCOPE_DISPOSITIONS)))
            return
        if any(entry["id"] == name for entry in entries):
            problems.append("objective %r is listed more than once" % name)
            return
        entry = {"id": name, "disposition": disposition,
                 "reason": str(reason).strip() if reason else ""}
        if revisit:
            try:
                revisit_date = date.fromisoformat(str(revisit))
            except ValueError:
                problems.append("objective %r has an invalid revisitOn date %r" % (name, revisit))
            else:
                entry["revisitOn"] = revisit_date.isoformat()
        entries.append(entry)

    if isinstance(raw, dict):
        for identifier, value in raw.items():
            if isinstance(value, dict):
                add(identifier, value.get("disposition", value.get("status", value.get("state"))),
                    value.get("reason", ""), value.get("revisitOn", ""))
            else:
                add(identifier, value)
    elif isinstance(raw, list):
        for item in raw:
            if isinstance(item, str):
                add(item, "approved")
            elif isinstance(item, dict):
                add(item.get("id"), item.get("disposition", item.get("status", item.get("state"))),
                    item.get("reason", ""), item.get("revisitOn", ""))
            else:
                problems.append("every objective must be an id or an object")
    elif raw is not None:
        problems.append("objectives must be a list or an id-to-disposition object")
    return entries


def _normalise_scope(document: dict, source: str) -> dict:
    problems: list[str] = []
    conflicts: list[str] = []
    if not isinstance(document, dict):
        return dict(_scope_placeholder("the scope record must be a JSON object"),
                    present=True, source=source, state=STEP_BLOCKED)
    version = document.get("version", 1)
    if version != 1:
        problems.append("unsupported scope version %r; expected 1" % (version,))
    approved_by = document.get("approvedBy")
    if not isinstance(approved_by, str) or not approved_by.strip() or approved_by.strip().lower() in (
            "unassigned", "unknown", "tbd", "none"):
        problems.append("approvedBy must name the owner who approved this scope")
        approved_by = approved_by.strip() if isinstance(approved_by, str) else None
    else:
        approved_by = approved_by.strip()
    approved_on = document.get("approvedOn")
    approved_date = None
    if not isinstance(approved_on, str) or not approved_on.strip():
        problems.append("approvedOn must be an ISO date")
        approved_on = None
    else:
        try:
            approved_date = date.fromisoformat(approved_on.strip())
        except ValueError:
            problems.append("approvedOn must be an ISO date, not %r" % approved_on)
            approved_on = None
        else:
            approved_on = approved_date.isoformat()
            if approved_date > date.today():
                problems.append("approvedOn cannot be in the future")
    proposal = document.get("proposal")
    if proposal is not None and not isinstance(proposal, str):
        problems.append("proposal must be a path string when present")
        proposal = None
    entries = _scope_entries(document.get("objectives"), problems)
    if not entries and document.get("objectives") is None:
        for key, disposition in (("required", "required"), ("approved", "approved"),
                                 ("declined", "declined"), ("deferred", "deferred"),
                                 ("optional", "optional"),
                                 ("notApplicable", "not-applicable"),
                                 ("not-applicable", "not-applicable")):
            values = document.get(key)
            if values is None:
                continue
            if not isinstance(values, list):
                problems.append("%s must be a list of objective ids" % key)
                continue
            for identifier in values:
                entries.append({"id": str(identifier), "disposition": disposition, "reason": ""})
        deduped = []
        seen = set()
        for entry in entries:
            if entry["id"] in seen:
                problems.append("objective %r is listed more than once" % entry["id"])
                continue
            seen.add(entry["id"])
            deduped.append(entry)
        entries = deduped
    if not entries and not problems:
        problems.append("objectives must approve at least one objective")
    unsupported: list[str] = []
    dispositions: dict[str, str] = {}
    explicit: dict[str, dict] = {}
    for entry in entries:
        identifier = entry["id"]
        if identifier not in OBJECTIVE_BY_ID:
            unsupported.append(identifier)
            continue
        if entry["disposition"] not in SCOPE_DISPOSITIONS:
            continue
        explicit[identifier] = entry
        dispositions[identifier] = entry["disposition"]
    if unsupported:
        problems.append("unsupported objective(s): %s" % ", ".join(sorted(unsupported)))
    if not any(value in ("required", "approved") for value in dispositions.values()):
        problems.append("at least one objective must be required or approved")

    origin: dict[str, str] = {}
    auto_required: list[str] = []
    for definition in OBJECTIVE_DEFS:
        identifier = definition["id"]
        if identifier in dispositions:
            origin[identifier] = "declared"
        elif definition.get("optionalByDefault"):
            dispositions[identifier] = "optional"
            origin[identifier] = "optional-by-default"
        else:
            dispositions[identifier] = "not-applicable"
            origin[identifier] = "not-in-scope"

    def require_dependencies(identifier: str, chain: tuple[str, ...]) -> None:
        for dependency in OBJECTIVE_BY_ID[identifier]["dependsOn"]:
            disposition = dispositions.get(dependency)
            if disposition not in ("required", "approved"):
                if dependency not in explicit:
                    dispositions[dependency] = "required"
                    origin[dependency] = "prerequisite for %s" % identifier
                    if dependency not in auto_required:
                        auto_required.append(dependency)
                else:
                    conflicts.append("%s is %s but %s needs it as a prerequisite"
                                     % (dependency, disposition, identifier))
                    continue
            if dependency not in chain:
                require_dependencies(dependency, chain + (dependency,))

    for identifier, disposition in list(dispositions.items()):
        if disposition in ("required", "approved"):
            require_dependencies(identifier, (identifier,))

    if conflicts:
        problems.extend(conflicts)
    scope = {
        "present": True, "source": source,
        "state": STEP_BLOCKED if problems else STEP_IN_PROGRESS,
        "approvedBy": approved_by, "approvedOn": approved_on, "proposal": proposal,
        "objectives": entries, "dispositions": dispositions, "origin": origin,
        "required": [key for key in OBJECTIVE_IDS if dispositions.get(key) == "required"],
        "approved": [key for key in OBJECTIVE_IDS if dispositions.get(key) == "approved"],
        "declined": [key for key in OBJECTIVE_IDS if dispositions.get(key) == "declined"],
        "deferred": [key for key in OBJECTIVE_IDS if dispositions.get(key) == "deferred"],
        "optional": [key for key in OBJECTIVE_IDS if dispositions.get(key) == "optional"],
        "notApplicable": [key for key in OBJECTIVE_IDS
                          if dispositions.get(key) == "not-applicable"],
        "unsupported": unsupported, "autoRequired": auto_required,
        "problems": problems, "conflicts": conflicts, "raw": document,
    }
    return scope


def _load_adoption_scope(root: Path, config: dict | None) -> dict:
    found: list[tuple[str, object]] = []
    for relative in (ADOPTION_SCOPE_FILE, ADOPTION_SCOPE_ALT):
        path = root / relative
        if not path.is_file():
            continue
        try:
            found.append((relative, json.loads(path.read_text(encoding="utf-8"))))
        except (OSError, json.JSONDecodeError) as error:
            return dict(_scope_placeholder("cannot read %s: %s" % (relative, error)),
                        present=True, source=relative, state=STEP_BLOCKED)
    if isinstance(config, dict) and "adoption" in config:
        inline = config.get("adoption")
        if not isinstance(inline, dict):
            return dict(_scope_placeholder("acima.config.json adoption must be an object"),
                        present=True, source="acima.config.json#adoption",
                        state=STEP_BLOCKED)
        found.append(("acima.config.json#adoption", inline))
    if not found:
        return _scope_placeholder()
    if len(found) > 1:
        return dict(_scope_placeholder("multiple scope records found: %s; keep one"
                                        % ", ".join(item[0] for item in found)),
                    present=True, source=found[0][0], state=STEP_BLOCKED)
    source, document = found[0]
    return _normalise_scope(document, source)


def _assessment_evidence(root: Path, scope: dict) -> dict:
    if not scope.get("present") or scope.get("state") == STEP_BLOCKED:
        return {"state": STEP_NOT_STARTED, "path": None, "verdict": None,
                "evidence": "no usable assessment evidence"}
    raw = scope.get("raw") if isinstance(scope.get("raw"), dict) else {}
    configured = raw.get("assessment")
    candidates: list[str] = []
    if isinstance(configured, dict) and isinstance(configured.get("artifact"), str) \
            and configured["artifact"].strip():
        candidates.append(configured["artifact"].strip())
    else:
        candidates.extend((ASSESSMENT_EVIDENCE, ".acima/assessment.json"))
    for relative in candidates:
        path = root / relative
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            return {"state": STEP_BLOCKED, "path": relative, "verdict": None,
                    "evidence": "%s does not parse: %s" % (relative, error)}
        if not isinstance(payload, dict):
            return {"state": STEP_BLOCKED, "path": relative, "verdict": None,
                    "evidence": "%s is not a JSON object" % relative}
        verdict = payload.get("verdict")
        if verdict not in VERDICT_MEANING:
            return {"state": STEP_BLOCKED, "path": relative, "verdict": verdict,
                    "evidence": "%s has no recognized assessment verdict" % relative}
        if payload.get("readOnly") is False:
            return {"state": STEP_BLOCKED, "path": relative, "verdict": verdict,
                    "evidence": "%s is not marked read-only" % relative}
        recorded_root = payload.get("root")
        if isinstance(recorded_root, str) and recorded_root.strip():
            try:
                recorded = Path(recorded_root)
                if not recorded.is_absolute():
                    recorded = root / recorded
                if recorded.resolve() != root.resolve():
                    return {"state": STEP_BLOCKED, "path": relative, "verdict": verdict,
                            "evidence": "%s belongs to a different repository" % relative}
            except OSError:
                pass
        if verdict in ("INVALID_ROOT", "INVALID_CONFIG", "INVALID_ASSESSMENT",
                       "TOOLCHAIN_MISSING"):
            return {"state": STEP_BLOCKED, "path": relative, "verdict": verdict,
                    "evidence": "%s records %s: %s" % (relative, verdict,
                                                         VERDICT_MEANING[verdict])}
        if verdict == "ASSESSED" and not isinstance(payload.get("sourceFiles"), int):
            return {"state": STEP_BLOCKED, "path": relative, "verdict": verdict,
                    "evidence": "%s does not record a source count" % relative}
        return {"state": STEP_COMPLETE, "path": relative, "verdict": verdict,
                "evidence": "%s records %s (%s)" % (relative, verdict,
                                                      VERDICT_MEANING[verdict])}
    return {"state": STEP_NOT_STARTED, "path": candidates[0], "verdict": None,
            "evidence": "no assessment evidence at %s" % candidates[0]}


def _document_evidence(root: Path, candidates: tuple[str, ...]) -> dict:
    for relative in candidates:
        path = root / relative
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if text.strip():
            return {"present": True, "path": relative,
                    "evidence": "%s has %s word(s)" % (relative, len(text.split()))}
    return {"present": False, "path": candidates[0],
            "evidence": "no non-empty document at %s" % " or ".join(candidates)}


def _scope_remedy(scope: dict) -> dict:
    problem_text = "; ".join(scope.get("problems") or ["the scope record is invalid"])
    return _next_action(
        "Correct the adoption scope record before acting on it",
        why="The owner's approved scope is the only basis for completion and next actions.",
        command="edit .acima/adoption-scope.json: fix approvedBy, approvedOn and objective dispositions",
        done="status accepts the scope and names every required, declined and deferred objective.",
        approval=True, writes=True,
        effect="Only the scope record changes; no architecture, evidence or CI is modified. "
               "Current problem: " + problem_text)


def _objective_record(definition: dict, disposition: str, state: str, evidence: str,
                      *, blockers: list[str] | None = None, next_action: dict | None = None,
                      reason: str = "") -> dict:
    action = next_action or _next_action()
    return {
        "id": definition["id"], "title": definition["title"],
        "disposition": disposition, "state": state,
        "label": OBJECTIVE_LABEL.get(state, state.lower()),
        "evidence": evidence, "prerequisites": list(definition.get("dependsOn", ())),
        "blocking": blockers or [], "reason": reason,
        "approvalRequired": bool(action.get("approvalRequired")),
        "writes": bool(action.get("writes")),
        "next": action,
        "completion": _objective_completion(definition["id"]),
    }


def _objective_completion(identifier: str) -> str:
    return {
        "assessment": "a read-only assessment artefact for this repository records a valid verdict",
        "local-enforcement": "the config declares reviewed units and a validated run measures them",
        "baseline-waivers": "a validated baseline exists and every pre-existing error is owned or none remain",
        "ci-enforcement": "a real pull-request gate is configured and independently observed at HEAD",
        "full-conformance": "a current FULL CONFORMANCE claim accounts for every required rule",
        "developer-handoff": "an approved, non-empty handoff or developer guide exists",
        "communication-governance": "an approved, non-empty communication or governance document exists",
    }[identifier]


def _build_objectives(root: Path, scope: dict, assessment: dict, steps: list[dict],
                      config: dict | None, config_problem: str, units: list[dict],
                      runs: list[dict], newest: dict | None, errors: int,
                      waiver_report: dict, language: str | None) -> tuple[list[dict], dict]:
    by_name = {step["name"]: step for step in steps}
    objectives: list[dict] = []
    if not scope.get("present"):
        for definition in OBJECTIVE_DEFS:
            objectives.append(_objective_record(
                definition, "undetermined", STEP_UNKNOWN,
                "scope has not been declared, so this objective is not required or declined"))
        return objectives, {
            "state": STEP_UNKNOWN, "complete": False, "scopeDefined": False,
            "completed": [], "inProgress": [], "remaining": [], "blocked": [],
            "declined": [], "deferred": [], "optional": [], "notApplicable": [],
            "unsupported": [], "required": [], "approved": [], "next": None,
            "problems": scope.get("problems", []),
        }
    if scope.get("state") == STEP_BLOCKED:
        for definition in OBJECTIVE_DEFS:
            disposition = scope["dispositions"].get(definition["id"], "not-applicable")
            if disposition in ("required", "approved"):
                state = STEP_BLOCKED
            elif disposition == "declined":
                state = "DECLINED"
            elif disposition == "deferred":
                state = "DEFERRED"
            elif disposition == "optional":
                state = "OPTIONAL"
            else:
                state = STEP_NOT_APPLICABLE
            objectives.append(_objective_record(
                definition, disposition, state,
                "scope record is invalid: " + "; ".join(scope.get("problems") or []),
                blockers=scope.get("problems") or []))
        for name in scope.get("unsupported", []):
            objectives.append({
                "id": name, "title": name, "disposition": "unsupported",
                "state": "UNSUPPORTED", "label": OBJECTIVE_LABEL["UNSUPPORTED"],
                "evidence": "not a supported objective id", "prerequisites": [],
                "blocking": scope.get("problems") or [], "reason": "",
                "approvalRequired": True, "writes": True, "next": _scope_remedy(scope),
                "completion": "remove the unsupported id or replace it with a supported objective",
            })
        return objectives, {
            "state": STEP_BLOCKED, "complete": False, "scopeDefined": True,
            "completed": [], "inProgress": [], "remaining": [],
            "blocked": [definition["id"] for definition in OBJECTIVE_DEFS
                        if scope["dispositions"].get(definition["id"]) in ("required", "approved")]
                       + list(scope.get("unsupported", [])),
            "declined": scope["declined"], "deferred": scope["deferred"],
            "optional": scope["optional"], "notApplicable": scope["notApplicable"],
            "unsupported": scope.get("unsupported", []),
            "required": scope["required"], "approved": scope["approved"], "next": None,
            "problems": scope.get("problems", []),
            "scopeProblems": scope.get("problems", []),
        }

    disposition = scope["dispositions"]
    local = by_name["freeze"]
    own = by_name["own"]
    gate = by_name["gate"]
    claim = by_name["claim"]
    handoff = _document_evidence(root, HANDOFF_DOCUMENTS)
    communication = _document_evidence(root, COMMUNICATION_DOCUMENTS)
    preflight = execution_context()["commands"]["preflight"] + " --project . --format text"
    enforcer = _enforcer_command(language) + " --root . --format json"
    local_complete = (config is not None and bool(units) and not config_problem
                      and local["state"] == STEP_COMPLETE)
    baseline_complete = local_complete and own["state"] in (STEP_COMPLETE,
                                                             STEP_NOT_APPLICABLE)

    def terminal(identifier: str) -> dict:
        definition = OBJECTIVE_BY_ID[identifier]
        disp = disposition[identifier]
        reason = next((entry.get("reason", "") for entry in scope["objectives"]
                       if entry["id"] == identifier), "")
        if disp == "declined":
            state = "DECLINED"
            evidence = "declined in the approved scope" + (": " + reason if reason else "")
        elif disp == "deferred":
            state = "DEFERRED"
            entry = next((item for item in scope["objectives"] if item["id"] == identifier), {})
            when = entry.get("revisitOn")
            evidence = "deferred in the approved scope" + (" until " + when if when else "")
            if reason:
                evidence += ": " + reason
        elif disp == "optional":
            state = "OPTIONAL"
            evidence = "optional and not part of the approved completion condition"
        else:
            state = STEP_NOT_APPLICABLE
            evidence = "not included in the approved scope"
        return _objective_record(definition, disp, state, evidence)

    for definition in OBJECTIVE_DEFS:
        identifier = definition["id"]
        disp = disposition[identifier]
        if disp not in ("required", "approved"):
            objectives.append(terminal(identifier))
            continue
        blockers: list[str] = []
        state = STEP_NOT_STARTED
        evidence = ""
        action = _next_action()
        if identifier == "assessment":
            audit = assessment
            if audit["state"] == STEP_COMPLETE:
                state = STEP_COMPLETE
                evidence = str(audit["evidence"])
            elif audit["state"] == STEP_BLOCKED:
                state = STEP_BLOCKED
                evidence = str(audit["evidence"])
                blockers.append(evidence)
                action = _next_action(
                    "Correct the assessment evidence",
                    why="The existing assessment artefact cannot support a verified assessment.",
                    command="python3 tools/acima.py assess --root . --format json > "
                            + ASSESSMENT_EVIDENCE,
                    done="the artefact parses, belongs to this repository and records a valid verdict.",
                    approval=True, writes=True,
                    effect="Replaces only the assessment evidence; no config, source or CI changes.")
            else:
                state = STEP_READY
                evidence = str(audit["evidence"])
                action = _next_action(
                    "Complete the read-only assessment and save its evidence",
                    why="An assessment-only scope is complete only when the assessment is verified.",
                    command="python3 tools/acima.py assess --root . --format json > "
                            + ASSESSMENT_EVIDENCE,
                    done="the artefact parses, belongs to this repository and records a valid verdict.",
                    approval=True, writes=True,
                    effect="Creates the assessment evidence; it does not change architecture, config or CI.")
        elif identifier == "local-enforcement":
            if config_problem:
                state = STEP_BLOCKED
                evidence = config_problem
                blockers.append(config_problem)
                action = _next_action(
                    "Repair the unit map", why="No valid unit map means nothing can be measured.",
                    command="edit acima.config.json: add units with roles and paths",
                    done="units parse and cover every source file.", approval=True, writes=True,
                    effect="Changes only the declaration; approval is required for the exact unit map.")
            elif not config or not units:
                state = STEP_READY
                evidence = "no reviewed unit map" if not config else "the config declares no units"
                action = _next_action(
                    "Approve the unit map and create acima.config.json",
                    why="Local enforcement needs a reviewed declaration of units and paths.",
                    command=preflight + " --write-draft",
                    done="every unit covers real source and the owner approves the map.",
                    approval=True, writes=True,
                    effect="Creates the declaration only; no source, CI or baseline changes.")
            elif local["state"] == STEP_BLOCKED:
                state = STEP_BLOCKED
                evidence = local["evidence"]
                blockers.append(local["evidence"])
                action = _next_action(
                    "Produce a valid local measurement", why=local["evidence"],
                    command=enforcer, done="the JSON parses, sourceFiles > 0 and the execution map is complete.",
                    effect="Prints a measurement; save its unmodified JSON under docs/acima/.")
            elif local["state"] != STEP_COMPLETE:
                state = STEP_READY
                evidence = "units declared; no validated run" if not runs else local["evidence"]
                action = _next_action(
                    "Measure the declared architecture locally",
                    why="Without a validated run, findings and local enforcement are guesses.",
                    command=enforcer,
                    done="the JSON parses, sourceFiles > 0 and the execution map is complete.",
                    effect="Prints a measurement; save it under docs/acima/ so status can verify it.")
            else:
                state = STEP_COMPLETE
                evidence = local["evidence"]
        elif identifier == "baseline-waivers":
            if not local_complete:
                blockers.append("local enforcement is %s" % ("complete" if local_complete else "incomplete"))
                evidence = "waiting for a validated local measurement"
            elif own["state"] == STEP_COMPLETE:
                state = STEP_COMPLETE
                evidence = own["evidence"]
            elif own["state"] == STEP_NOT_APPLICABLE:
                state = STEP_COMPLETE
                evidence = "baseline measured with no error findings; no waivers are required"
            elif own["state"] == STEP_BLOCKED:
                state = STEP_BLOCKED
                evidence = own["evidence"]
                blockers.append(own["evidence"])
                action = _next_action(
                    "Repair waiver governance before relying on the baseline",
                    why="An invalid, expired or unowned exception hides new findings.",
                    command="edit .acima/waivers.json: complete every field, scope and expiry",
                    done="every waiver validates and none is expired.", approval=True, writes=True,
                    effect="Changes only exception records; it does not hide or rewrite findings.")
            else:
                state = STEP_IN_PROGRESS
                evidence = own["evidence"]
                action = _next_action(
                    "Ask the owner to approve owned exceptions for existing findings",
                    why="The baseline has errors but no accepted exception; the baseline is not owned yet.",
                    command="propose scoped waivers, then write .acima/waivers.json only with approval",
                    done="each pre-existing finding has an owner, scope, fingerprint and expiry.",
                    approval=True, writes=True,
                    effect="Adds scoped exceptions only for named pre-existing findings; never suppresses new errors.")
        elif identifier == "ci-enforcement":
            if not local_complete:
                blockers.append("local enforcement is incomplete")
                evidence = "waiting for local enforcement"
            elif not baseline_complete:
                blockers.append("baseline and waiver management is incomplete")
                evidence = "waiting for a complete baseline and waiver record"
            elif gate["state"] == STEP_COMPLETE:
                state = STEP_COMPLETE
                evidence = gate["evidence"]
            elif gate["state"] == STEP_BLOCKED:
                state = STEP_BLOCKED
                evidence = gate["evidence"]
                blockers.append(gate["evidence"])
                gate_state = gate.get("gateState")
                if gate_state == "mention-only":
                    action = _next_action(
                        "Make the CI workflow run a real gate",
                        why="A workflow that mentions ACIMA without invoking it proves nothing.",
                        command="edit the workflow to run the enforcer with --root and the declared level",
                        done="the workflow invokes the gate and a failing pull request blocks.",
                        approval=True, writes=True,
                        effect="Changes CI configuration only within the approved CI objective.")
                elif gate_state == "not-pull-request":
                    action = _next_action(
                        "Make the CI gate run on pull requests",
                        why="A command that runs only on push or manually does not protect merges.",
                        command="add a pull_request or merge_group trigger to the gate workflow",
                        done="the workflow runs the enforcer for pull requests and merge groups.",
                        approval=True, writes=True,
                        effect="Changes the workflow trigger, not application source.")
                elif gate_state in ("observation-stale", "observation-mismatch"):
                    action = _next_action(
                        "Re-record the gate observation from the actual workflow",
                        why="The recorded run is stale or does not match this workflow and commit.",
                        command="open a fresh pull request run and record its provider, run id, workflow and HEAD",
                        done="the observation references this workflow and its commit is HEAD.",
                        approval=True, writes=True,
                        effect="Replaces only the observation record; it does not change the workflow.")
                else:
                    action = _next_action(
                        "Fix the CI gate before trusting it",
                        why="The enforcer invocation is disabled, advisory, conditional or unsupported.",
                        command="remove if: false and continue-on-error; use --root . and the declared level",
                        done="one unconditional step invokes the enforcer at the declared level.",
                        approval=True, writes=True,
                        effect="Changes CI configuration only; application source remains untouched.")
            elif gate["state"] == STEP_IN_PROGRESS:
                state = STEP_IN_PROGRESS
                evidence = gate["evidence"]
                if gate.get("gateState") == "observation-failed":
                    action = _next_action(
                        "Fix the failure the gate observed",
                        why="The gate ran and rejected the commit; that is not a passing milestone.",
                        command="fix the reported finding, then record a fresh passing run",
                        done="a provider-sourced observation at HEAD exits 0.")
                else:
                    action = _next_action(
                        "Confirm the gate runs on a pull request and record provider provenance",
                        why="Configured or manually recorded is not independently observed.",
                        command="open a pull request, then record commit, workflow and run id",
                        done="a provider-sourced observation matches HEAD and the declared level.",
                        effect="Adds gate provenance only; it does not claim the gate passed until the provider says so.")
            else:
                state = STEP_READY
                evidence = gate["evidence"]
                action = _next_action(
                    "Ask the owner to approve a CI gate",
                    why="The gate is what stops new violations; it is a write and needs consent.",
                    command="propose .github/workflows/acima.yml running the enforcer for the declared level",
                    done="an approved workflow invokes the gate on pull requests.",
                    approval=True, writes=True,
                    effect="Adds CI enforcement for the declared level; no application source changes.")
        elif identifier == "full-conformance":
            if not local_complete:
                blockers.append("local enforcement is incomplete")
                evidence = "waiting for a validated local measurement"
            elif claim["state"] == STEP_COMPLETE:
                state = STEP_COMPLETE
                evidence = claim["evidence"]
            elif claim["state"] == STEP_BLOCKED:
                state = STEP_BLOCKED
                evidence = claim["evidence"]
                blockers.append(claim["evidence"])
                action = _next_action(
                    "Correct the claim evidence",
                    why="The current claim record is invalid; it cannot be promoted to conformance.",
                    command="repair .acima/manual-evidence.json and recompute the claim",
                    done="the claim has valid, current repository and manual evidence.",
                    approval=True, writes=True,
                    effect="Changes only evidence for named manual rules; the claim itself is unchanged.")
            else:
                state = STEP_IN_PROGRESS if claim["state"] == STEP_IN_PROGRESS else STEP_READY
                evidence = claim["evidence"]
                claim_state = claim.get("claimState")
                if (claim.get("claim") or {}).get("missingManual"):
                    action = _next_action(
                        "Record the evidence the claim still needs",
                        why="A partial assessment is honest; accepted evidence is what can make it full.",
                        command="fill .acima/manual-evidence.json for the named manual rules",
                        done="acima.py claim --require full exits 0 at the declared level.",
                        approval=True, writes=True,
                        effect="Adds accepted evidence for named manual rules; it does not waive automated findings.")
                elif claim_state in ("historical", "stale", "uncommitted", "incomplete"):
                    action = _next_action(
                        "Measure the current repository state again",
                        why="The existing claim is historical or incomplete; freshness is the limitation.",
                        command=enforcer,
                        done="a new run records the current HEAD, catalog, configuration and source "
                             "inventory, then the claim matches it.")
                else:
                    action = _next_action(
                        "Establish a current conformance claim",
                        why="Full conformance requires a run and accepted evidence for every manual rule.",
                        command=enforcer,
                        done="the run is current and acima.py claim --require full exits 0.")
        elif identifier in ("developer-handoff", "communication-governance"):
            document = handoff if identifier == "developer-handoff" else communication
            candidates = HANDOFF_DOCUMENTS if identifier == "developer-handoff" \
                else COMMUNICATION_DOCUMENTS
            if document["present"]:
                state = STEP_COMPLETE
                evidence = document["evidence"]
            else:
                state = STEP_READY
                evidence = document["evidence"]
                label = "developer handoff" if identifier == "developer-handoff" \
                    else "communication or governance plan"
                action = _next_action(
                    "Write the approved " + label,
                    why="This objective is approved but its document does not exist or is empty.",
                    command="create " + candidates[0],
                    done="the document is non-empty, approved and names what changed and what remains.",
                    approval=True, writes=True,
                    effect="Adds the approved document only; no source or enforcement changes.")
        objectives.append(_objective_record(
            definition, disp, state, evidence, blockers=blockers, next_action=action))

    blocking = [obj for obj in objectives if obj["disposition"] in ("required", "approved")]
    completed = [obj["id"] for obj in blocking if obj["state"] == STEP_COMPLETE]
    blocked = [obj["id"] for obj in blocking if obj["state"] == STEP_BLOCKED]
    remaining = [obj["id"] for obj in blocking
                 if obj["state"] not in (STEP_COMPLETE, STEP_BLOCKED)]
    in_progress = [obj["id"] for obj in blocking
                   if obj["state"] in (STEP_READY, STEP_IN_PROGRESS, STEP_NOT_STARTED)]
    selected = next((obj for obj in blocking if obj["state"] != STEP_COMPLETE), None)
    if selected is None:
        next_action = _next_action(
            "No further action in the approved scope",
            why="Every required and approved objective is complete; declined, deferred, optional "
                "and not-applicable work does not block.",
            done="The scope stays unchanged; a new objective needs a new owner approval.",
            effect="Nothing changes. Adoption completion is separate from architectural conformance; "
                   "only full-conformance asserts a conformance claim.")
        state = STEP_COMPLETE
    else:
        next_action = selected["next"]
        state = STEP_BLOCKED if blocked else STEP_IN_PROGRESS
    engagement = {
        "state": state, "complete": selected is None, "scopeDefined": True,
        "completed": completed, "inProgress": in_progress, "remaining": remaining,
        "blocked": blocked,
        "declined": [obj["id"] for obj in objectives if obj["state"] == "DECLINED"],
        "deferred": [obj["id"] for obj in objectives if obj["state"] == "DEFERRED"],
        "optional": [obj["id"] for obj in objectives if obj["state"] == "OPTIONAL"],
        "notApplicable": [obj["id"] for obj in objectives if obj["state"] == STEP_NOT_APPLICABLE],
        "unsupported": scope.get("unsupported", []),
        "required": scope["required"], "approved": scope["approved"],
        "next": next_action, "problems": scope.get("problems", []),
        "scopeProblems": scope.get("problems", []),
    }
    return objectives, engagement


def _scope_aware_next(scope: dict, engagement: dict, config: dict | None,
                      runs: list[dict]) -> dict | None:
    if not scope.get("present"):
        if not config and not runs:
            return None
        return _next_action(
            "Record the owner-approved adoption scope",
            why="Configuration and evidence exist, but no artefact records what the owner approved.",
            command="create .acima/adoption-scope.json with approvedBy, approvedOn and objective dispositions",
            done="status accepts the scope and separates approved, declined, deferred and optional work.",
            approval=True, writes=True,
            effect="Adds the scope record only; it does not approve or perform any other objective.")
    if scope.get("state") == STEP_BLOCKED:
        return _scope_remedy(scope)
    return engagement.get("next")


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
    scope = _load_adoption_scope(root, config)
    assessment = _assessment_evidence(root, scope)

    steps = [_step(1, "recon", STEP_READY,
                   f"{sources} source file(s), {language or 'unknown language'}")]
    if scope.get("present") and scope.get("state") != STEP_BLOCKED \
            and assessment["state"] == STEP_COMPLETE:
        fit = _step(2, "fit", STEP_COMPLETE,
                    "%s; scope approved by %s on %s"
                    % (assessment["evidence"], scope.get("approvedBy"),
                       scope.get("approvedOn")))
    elif scope.get("present") and scope.get("state") != STEP_BLOCKED:
        fit = _step(2, "fit", STEP_IN_PROGRESS,
                    "approved scope recorded, but no verified assessment artefact",
                    "record the read-only assessment evidence")
    else:
        fit = _step(2, "fit", STEP_UNKNOWN,
                    "the fit decision is conversational; no artefact proves assessment or "
                    "unit-map approval",
                    "record the approved proposal path if the owner keeps one")
    steps.append(fit)
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
    steps.append(_claim_step(root, runs, level, config, catalog_version, catalog_sha))
    steps.append(_step(11, "maintain", STEP_NOT_APPLICABLE,
                       "maintaining the standard is not part of adopting it"))

    objectives, engagement = _build_objectives(
        root, scope, assessment, steps, config, config_problem, units, runs, newest,
        errors, waiver_report, language)

    optional = [{"name": name, "path": f"docs/acima/{name}",
                 "present": (root / "docs/acima" / name).is_file(),
                 "disposition": "optional"}
                for name in ("adoption-plan.md", "communication-plan.md", "STATUS.md")]

    scope_next = _scope_aware_next(scope, engagement, config, runs)

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
    elif steps[9].get("claimState") in ("historical", "stale", "uncommitted", "incomplete"):
        claim_step = steps[9]
        claim = claim_step.get("claim") or {}
        if claim.get("missingManual"):
            next_step.update(action="Record the evidence the claim still needs",
                             why="A partial assessment is honest; accepted evidence is what can "
                                 "make it full.",
                             command="fill .acima/manual-evidence.json for the named manual rules",
                             doneWhen="acima.py claim --require full exits 0 at the declared level.",
                             approvalRequired=True, writes=True)
        else:
            next_step.update(
                action="Measure the current repository state again",
                why="The existing claim is historical or incomplete; freshness, not an architecture "
                    "defect, is the limitation.",
                command=f"{_enforcer_command(language)} --root . --format json",
                doneWhen="a new run records the current HEAD, catalog, configuration and source "
                         "inventory, then the claim matches it.")
    elif steps[9].get("claimState") == "invalid":
        next_step.update(action="Correct the claim evidence",
                         why="The current claim record is invalid; a partial or stale record cannot "
                             "be promoted to conformance.",
                         command="repair .acima/manual-evidence.json and recompute the claim",
                         doneWhen="the claim has valid, current repository and manual evidence.",
                         approvalRequired=True, writes=True)
    else:
        next_step.update(action="Keep the count falling and the gate green",
                         why="The ratchet is the programme: flat or falling, never rising.",
                         command=f"{_enforcer_command(language)} --root . --format json",
                         doneWhen="the next run has no unwaived errors and the claim still holds.")

    if scope_next is not None:
        next_step = scope_next
    engagement["next"] = next_step
    if scope.get("present") and scope.get("state") != STEP_BLOCKED:
        scope["state"] = STEP_COMPLETE if engagement["complete"] else STEP_IN_PROGRESS
        verified = engagement["completed"]
        remaining = engagement["remaining"]
        blocked = ["%s: %s" % (obj["id"], obj["evidence"])
                   for obj in objectives if obj["id"] in engagement["blocked"]]
    elif scope.get("present") and scope.get("state") == STEP_BLOCKED:
        verified = []
        remaining = []
        blocked = ["scope: " + problem for problem in scope.get("problems", [])]
    else:
        verified = [step["name"] for step in steps if step["state"] == STEP_COMPLETE]
        blocked = [f"{step['name']}: {step['evidence']}" for step in steps
                   if step["state"] == STEP_BLOCKED]
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
        "scope": scope,
        "assessmentEvidence": assessment,
        "objectives": objectives,
        "engagement": engagement,
        "verified": verified,
        "remaining": remaining,
        "blocked": blocked,
        "optional": optional,
        "next": next_step,
        "limitation": ("Completion is relative to the explicitly approved scope. A missing, "
                       "invalid or stale artefact is reported, never assumed complete. Declined, "
                       "deferred, optional and not-applicable work never blocks. Adoption "
                       "completion is separate from architectural conformance."),
    }


def status_text(report: dict) -> str:
    config = report["config"]
    engagement = report.get("engagement") or {}
    scope = report.get("scope") or {}
    objectives = {entry["id"]: entry for entry in report.get("objectives", [])}

    def titles(identifiers: list[str]) -> str:
        return ", ".join(objectives.get(name, {}).get("title", name) for name in identifiers)

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
    if scope.get("present"):
        lines.append("  scope       %s - approved by %s on %s (%s)"
                     % (STATE_LABEL.get(scope.get("state"), str(scope.get("state")).lower()),
                        scope.get("approvedBy") or "unknown owner",
                        scope.get("approvedOn") or "unknown date", scope.get("source")))
    else:
        lines.append("  scope       not recorded (completion cannot be inferred from files)")
    if scope.get("present"):
        completed_text = titles(engagement.get("completed", [])) or "nothing yet"
        in_progress_text = titles(engagement.get("inProgress", [])) or "nothing"
        remaining_text = titles(engagement.get("remaining", [])) or "nothing"
    else:
        completed_text = ", ".join(report.get("verified", [])) or "nothing yet"
        in_progress_text = ", ".join(step["name"] for step in report["steps"]
                                      if step["state"] == STEP_IN_PROGRESS) or "nothing"
        remaining_text = ", ".join(report.get("remaining", [])) or "nothing"
    lines.append("  completed   " + completed_text)
    lines.append("  in progress " + in_progress_text)
    lines.append("  remaining   " + remaining_text)
    lines.append("  blocked     " + ("; ".join(report["blocked"]) or "nothing"))
    lines.append("  declined    " + (titles(engagement.get("declined", [])) or "nothing"))
    lines.append("  deferred    " + (titles(engagement.get("deferred", [])) or "nothing"))
    lines.append("  optional    " + (titles(engagement.get("optional", [])) or "nothing"))
    lines.append("  not appl.   " + (titles(engagement.get("notApplicable", [])) or "nothing"))
    if engagement.get("complete"):
        lines.append("  outcome     complete within the approved scope; this is not a conformance claim")
    lines += ["", "  steps (evidence diagnostics)"]
    for step in report["steps"]:
        lines.append("    %2s  %-14s %-14s %s"
                     % (step["n"], step["name"], step["label"], step["evidence"]))
    next_step = report["next"]
    lines += ["", "  next",
              "    " + next_step["action"],
              "    why: " + next_step["why"],
              "    done when: " + next_step["doneWhen"]]
    if next_step.get("command"):
        lines.append("    $ " + next_step["command"])
    lines.append("    approval %s - %s"
                 % ("required" if next_step["approvalRequired"] else "not needed",
                    "writes the target" if next_step["writes"] else "read-only"))
    if next_step.get("effect"):
        lines.append("    if approved: " + next_step["effect"])
    return chr(10).join(lines)


def status_markdown(report: dict) -> str:
    """A compact, scope-aware dashboard. Read-only, like the status itself."""
    engagement = report.get("engagement") or {}
    objectives = {entry["id"]: entry for entry in report.get("objectives", [])}

    def titles(identifiers: list[str]) -> str:
        return ", ".join(objectives.get(name, {}).get("title", name) for name in identifiers) \
            or "Nothing"

    scope = report.get("scope") or {}
    lines = ["# ACIMA adoption status", "",
             "**Repository:** `%s`" % report["root"], "",
             "**Scope:** " + (("approved by %s on %s" % (scope.get("approvedBy"),
                                                            scope.get("approvedOn")))
                               if scope.get("present") else "not recorded"), "",
             "**Completed:** " + titles(engagement.get("completed", [])), "",
             "**Remaining:** " + titles(engagement.get("remaining", [])), "",
             "**Blocked:** " + ("; ".join(report.get("blocked", [])) or "Nothing"), "",
             "**Declined:** " + titles(engagement.get("declined", [])), "",
             "**Deferred:** " + titles(engagement.get("deferred", [])), "",
             "**Optional:** " + titles(engagement.get("optional", [])), "", "## Next action", "",
             report["next"]["action"], "", report["next"]["why"], ""]
    if report["next"].get("command"):
        lines += ["```bash", report["next"]["command"], "```", ""]
    lines += ["**Done when:** " + report["next"]["doneWhen"], "",
              "**Approval:** " + ("required" if report["next"]["approvalRequired"]
                                  else "not needed"), ""]
    if report["next"].get("effect"):
        lines += ["**If approved:** " + report["next"]["effect"], ""]
    return chr(10).join(lines).rstrip()


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
    assess.add_argument("--review", default=None,
                        help="evidence-backed qualitative review JSON; required for assessment completion")
    assess.add_argument("--format", choices=("text", "json", "markdown"), default="text")

    review = sub.add_parser("validate-review", help="validate evidence-backed qualitative review of every catalog rule")
    review.add_argument("--root", default=".", help="assessed repository root")
    review.add_argument("--file", required=True, help="qualitative review JSON")
    review.add_argument("--format", choices=("json", "markdown"), default="markdown")

    status = sub.add_parser("status", help="which steps are evidenced, and the next command")
    status.add_argument("--root", default=".")
    status.add_argument("--format", choices=("text", "json", "markdown"), default="text")
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

    adoption = sub.add_parser("adoption", help="end-to-end guided or explicitly authorized adoption")
    adoption.add_argument("action", choices=("start", "status", "approve", "apply", "continue", "remediate", "guidance"))
    adoption.add_argument("--root", default=".")
    adoption.add_argument("--mode", choices=("guided", "full"), default=None,
                          help="required for start: guided or explicit full automation")
    adoption.add_argument("--authorize-full", action="store_true", dest="authorize_full",
                          help="required before full automation can start")
    adoption.add_argument("--reviewer", default=None)
    adoption.add_argument("--map-decisions", default=None)
    adoption.add_argument("--scope", default=None)
    adoption.add_argument("--choice", choices=("none", "selected", "all"), default=None)
    adoption.add_argument("--maturity-choice", choices=("greenfield", "brownfield"), default=None)
    adoption.add_argument("--approve", action="store_true")
    adoption.add_argument("--selected", action="append", default=[])
    adoption.add_argument("--approved-by", default="Repository owner")
    adoption.add_argument("--confirm", action="store_true")
    adoption.add_argument("--confirm-scope", action="store_true", dest="confirm_scope")
    adoption.add_argument("--confirm-implementation", action="store_true",
                          dest="confirm_implementation")
    adoption.add_argument("--format", choices=("json", "text"), default="json")

    args = parser.parse_args()
    if args.command == "adoption":
        try:
            import adoption_workflow
        except ImportError as error:
            print(f"acima: adoption workflow is unavailable: {error}", file=sys.stderr)
            return 2
        root = Path(args.root).resolve()
        try:
            if args.action == "start":
                if not args.mode:
                    print("acima: adoption start requires --mode guided or --mode full",
                          file=sys.stderr)
                    return 2
                result = adoption_workflow.start(root, args.mode,
                                                 authorize_full=args.authorize_full,
                                                 reviewer=args.reviewer)
            elif args.action == "status":
                result = adoption_workflow.status(root)
            elif args.action == "approve":
                result = adoption_workflow.approve(
                    root,
                    map_decisions=Path(args.map_decisions) if args.map_decisions else None,
                    scope=Path(args.scope) if args.scope else None,
                    reviewer=args.reviewer)
            elif args.action == "apply":
                result = adoption_workflow._apply(root, adoption_workflow._load(root))
            elif args.action == "guidance":
                result = adoption_workflow.guidance(root, approve=args.approve)
            elif args.action == "remediate":
                if not args.choice:
                    print("acima: adoption remediate requires --choice none, selected, or all",
                          file=sys.stderr)
                    return 2
                result = adoption_workflow.remediate(
                    root, args.choice, selected=args.selected, approved_by=args.approved_by,
                    confirm=args.confirm, confirm_scope=args.confirm_scope,
                    confirm_implementation=args.confirm_implementation,
                    maturity_choice=args.maturity_choice)
            else:
                result = adoption_workflow.continue_workflow(root)
        except (adoption_workflow.WorkflowError, adoption_workflow.ModuleMapError,
                OSError, ValueError) as error:
            print(f"acima: adoption workflow: {error}", file=sys.stderr)
            return 2
        if args.format == "json":
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            summary = adoption_workflow._summary(result) if "stages" in result else result
            print("ACIMA adoption workflow")
            print("  mode    %s" % summary.get("mode", result.get("mode", "unknown")))
            for stage in summary.get("stages", []):
                print("  %-8s %-28s %s" % (stage.get("status"), stage.get("label"),
                                            stage.get("detail")))
            nxt = summary.get("next") or result.get("next") or {}
            if nxt.get("action"):
                print("  next    %s" % nxt["action"])
        return 0 if not (result.get("blockers") or
                         (result.get("next") or {}).get("action", "").startswith("Resolve")) else 1

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
        claim = claim_for(root, payload, config)
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
            try:
                config = read_config(root)
            except ConfigError:
                config = None
            catalog_version, catalog_sha = _catalog_version_and_hash()
            currentness = _claim_currentness(
                root, payload, config, args.level, catalog_version, catalog_sha)
            claim.update({"currentness": currentness["state"],
                          "current": currentness["current"], "provenance": currentness})
        except ClaimError as error:
            print(f"acima: {error}", file=sys.stderr)
            return 2
        if args.format == "json":
            print(json.dumps(claim, indent=2, sort_keys=True))
        else:
            print(render_claim_markdown(claim))
        if args.require == "full" and (claim["claim"] != FULL or not claim.get("current")):
            return 1
        return 0

    if args.command == "validate-review":
        root = Path(args.root).resolve()
        review_path = Path(args.file).resolve()
        try:
            catalog_sha256 = hashlib.sha256((ACIMA_ROOT / "tools/acima-spec/rules.json").read_bytes()).hexdigest()
            validation = load_and_validate_review(
                review_path, root, load_catalog(ACIMA_ROOT), catalog_sha256)
        except ReviewValidationError as error:
            print(f"acima: {error}", file=sys.stderr)
            return 2
        if args.format == "json":
            print(json.dumps(validation, indent=2))
        else:
            print("ACIMA qualitative review: %s" % validation["status"].upper())
            print("  evidence-backed rules: %s/%s" % (validation["reviewed"], validation["required"]))
            print("  pending: %s" % validation["pending"])
            for status, count in validation["counts"].items():
                print("  %-22s %s" % (status, count))
            for issue in validation["problems"]:
                print("  %s: %s" % (issue.get("rule", issue.get("scope", "document")), "; ".join(issue["problems"])))
            print("  disposition coverage: %s" % ("complete" if validation["coverageComplete"] else "incomplete"))
            print("  unresolved decisions: %s" % validation["unresolved"])
            print("  decision resolved: %s" % ("yes" if validation["decisionComplete"] else "no"))
            print("  meaning: complete disposition coverage is not a conformance result")
        # A fully dispositioned review is a successful validation even when some
        # requirements remain unresolved. Overall assessment completion stays false.
        return 0 if validation["coverageComplete"] else 1

    if args.command == "status":
        report = status_project(Path(args.root))
        if args.format == "json":
            print(json.dumps(report, indent=2))
        elif args.format == "markdown":
            print(status_markdown(report))
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
        code, report = assess_project(Path(args.root), args.language, args.level,
                                      Path(args.review) if args.review else None)
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
