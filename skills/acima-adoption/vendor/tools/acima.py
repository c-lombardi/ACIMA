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
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ACIMA_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ACIMA_ROOT / "conformance"))
from acima_claim import (  # noqa: E402 - path is set above deliberately
    EVIDENCE_FILE, FULL, INVALID, ClaimError, assess as assess_claim,
    load_catalog, load_evidence, render_markdown as render_claim_markdown,
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
        return 0, report

    try:
        config = read_config(root)
    except ConfigError as error:
        report.update({"verdict": "INVALID_CONFIG",
                       "verdictMeaning": VERDICT_MEANING["INVALID_CONFIG"],
                       "error": str(error)})
        report["nextSteps"] = _next_steps(report)
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
        return code, report

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
        "## Unit map",
        "",
    ]
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
GATE_TOKENS = ("acima_arch.py", "acima-arch.mjs", "./tools/archtest",
               "Acima.ArchTests", "acima.py analyze", "preflight.py")
GATE_OBSERVATION = "docs/acima/gate-observed.json"
PROOF_ARTEFACT = "docs/acima/proof.json"


def _step(number: int, name: str, state: str, evidence: str, remedy: str = "") -> dict:
    return {"n": number, "name": name, "state": state, "label": STATE_LABEL[state],
            "verified": state == STEP_COMPLETE, "evidence": evidence, "remedy": remedy}


def _calibration() -> dict:
    """Compare the skill's pinned catalog against the catalog on disk.

    A config file proves nothing about calibration; this is the only artefact that does.
    """
    try:
        manifest = json.loads((ACIMA_ROOT / CALIBRATION_MANIFEST).read_text(encoding="utf-8"))
        raw = (ACIMA_ROOT / "tools/acima-spec/rules.json").read_bytes()
        catalog = json.loads(raw)
    except (OSError, json.JSONDecodeError) as error:
        return _step(0, "calibration", STEP_UNKNOWN, f"cannot verify the skill pin: {error}",
                     "run preflight.py from an ACIMA checkout")
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
                 f"PIN MATCHES {len(rules)} RULES ({digest[:12]}...)")


def _run_artefacts(root: Path) -> tuple[list[dict], list[str]]:
    """Return usable measured runs, plus named reasons for files that only look like runs."""
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
        if not isinstance(payload, dict):
            rejected.append(f"{name}: not a run artefact")
            continue
        sources = payload.get("sourceFiles")
        execution = payload.get("execution")
        findings = payload.get("findings")
        if not isinstance(sources, int) or sources <= 0:
            rejected.append(f"{name}: sourceFiles is not a positive count")
            continue
        if not isinstance(execution, dict) or len(execution) < 2:
            rejected.append(f"{name}: no execution map, so the run is incomplete")
            continue
        if not isinstance(findings, list):
            rejected.append(f"{name}: no findings list")
            continue
        usable.append({"path": name, "payload": payload,
                       "mtime": path.stat().st_mtime})
    usable.sort(key=lambda entry: entry["mtime"])
    return usable, rejected


def _gate_workflows(root: Path) -> list[dict]:
    """Inspect workflows that mention ACIMA, and say whether they invoke a real gate."""
    directory = root / ".github/workflows"
    entries: list[dict] = []
    if not directory.is_dir():
        return entries
    for path in sorted(directory.glob("*.y*ml")):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "acima" not in text.lower():
            continue
        level = re.search(r"--level\s+(L[123])", text)
        entries.append({
            "path": path.relative_to(root).as_posix(),
            "invokes": [token for token in GATE_TOKENS if token in text],
            "onPullRequest": bool(re.search(r"pull_request|merge_group|pull-request", text)),
            "level": level.group(1) if level else None,
        })
    return entries


def _gate_observation(root: Path) -> dict | None:
    path = root / GATE_OBSERVATION
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("exitCode") not in (0, 1):
        return None
    return payload


def _error_count(payload: dict) -> int:
    return sum(1 for finding in payload.get("findings") or []
               if str(finding.get("severity", "")).lower() == "error")


def _claim_evidence(root: Path, runs: list[dict], level: str | None) -> dict:
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

    Read-only. A step is complete only when its completion criterion is verified: a config is
    checked for units, calibration is compared against the pinned catalog, a baseline is parsed
    and inspected, a workflow is read to see whether it invokes a gate, and a claim is computed
    with the authoritative claim implementation.
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

    calibration = _calibration()
    waivers = _waiver_document(root / ((config or {}).get("waivers") or ".acima/waivers.json"))
    waiver_list = waivers.get("waivers") if isinstance(waivers.get("waivers"), list) else []
    unowned = [entry for entry in waiver_list
               if not str(entry.get("owner") or "").strip()
               or str(entry.get("owner")).strip().lower() == "unassigned"]
    today = date.today().isoformat()
    expired = [entry for entry in waiver_list if str(entry.get("expires") or "") < today]
    fingerprinted = _waiver_document(root / ".acima/baseline.json").get("fingerprints")
    fingerprinted = fingerprinted if isinstance(fingerprinted, list) else []

    runs, rejected_runs = _run_artefacts(root)
    newest = runs[-1] if runs else None
    errors = _error_count(newest["payload"]) if newest else 0
    workflows = _gate_workflows(root)
    observation = _gate_observation(root)
    proof_path = root / PROOF_ARTEFACT

    steps = [_step(1, "recon", STEP_READY,
                   f"{sources} source file(s), {language or 'unknown language'}")]
    steps.append(_step(2, "fit", STEP_COMPLETE if config else STEP_NOT_STARTED,
                       "the unit map records the fit decision" if config
                       else "no unit map; the fit decision is not recorded",
                       "assess fit, then propose a unit map"))
    steps.append(_step(3, "trust the tool", STEP_COMPLETE if proof_path.is_file() else STEP_UNKNOWN,
                       proof_path.relative_to(root).as_posix() if proof_path.is_file()
                       else "no proof artefact; detection is unproven",
                       "run inject_violation.py and keep its result"))
    steps.append(_step(4, "calibrate", calibration["state"], calibration["evidence"],
                       calibration["remedy"]))
    if config_problem:
        declare = _step(5, "declare", STEP_BLOCKED, config_problem,
                        "repair acima.config.json; nothing else can be trusted until it parses")
    elif units:
        declare = _step(5, "declare", STEP_COMPLETE,
                        f"{len(units)} unit(s) at {level or 'unset level'}")
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
                 f"{len(newest['payload'].get('findings') or [])} finding(s), " \
                 f"{errors} error(s)"
        freeze = _step(6, "freeze", STEP_COMPLETE, detail)
    elif fingerprinted:
        freeze = _step(6, "freeze", STEP_IN_PROGRESS,
                       f".acima/baseline.json holds {len(fingerprinted)} fingerprint(s), but no "
                       "measured run artefact proves the measurement",
                       "keep the enforcer's JSON as docs/acima/baseline-<date>.json")
    else:
        freeze = _step(6, "freeze", STEP_NOT_STARTED, "no measured run",
                       "measure the current state")
    steps.append(freeze)

    if not newest:
        own = _step(7, "own", STEP_NOT_STARTED, "no measured findings to own",
                    "freeze a baseline first")
    elif expired:
        own = _step(7, "own", STEP_BLOCKED,
                    f"{len(expired)} waiver(s) expired; {len(unowned)} unowned",
                    "renew or remove each expired exception with its owner")
    elif unowned:
        own = _step(7, "own", STEP_IN_PROGRESS,
                    f"{len(unowned)} of {len(waiver_list)} waiver(s) have no owner")
    elif waiver_list:
        own = _step(7, "own", STEP_COMPLETE,
                    f"{len(waiver_list)} owned, unexpired waiver(s)")
    elif errors:
        own = _step(7, "own", STEP_NOT_STARTED,
                    f"{errors} unwaived error(s) and no waiver file",
                    "propose scoped, owned waivers for pre-existing findings")
    else:
        own = _step(7, "own", STEP_NOT_APPLICABLE,
                    "no error findings require an exception")
    steps.append(own)

    invoking = [entry for entry in workflows if entry["invokes"]]
    if observation:
        gate = _step(8, "gate", STEP_COMPLETE,
                     f"observed exit {observation.get('exitCode')} from "
                     f"{observation.get('command', 'the gate')}")
    elif invoking:
        gate = _step(8, "gate", STEP_IN_PROGRESS,
                     f"{invoking[0]['path']} invokes {invoking[0]['invokes'][0]}; "
                     "configured, not observed on a pull request",
                     "confirm the check runs and blocks on a real pull request")
    elif workflows:
        gate = _step(8, "gate", STEP_BLOCKED,
                     f"{workflows[0]['path']} mentions ACIMA but invokes no gate command",
                     "make the workflow run an enforcer, or remove the misleading file")
    else:
        gate = _step(8, "gate", STEP_NOT_STARTED, "no workflow invokes a gate",
                     "propose a CI gate and wait for approval")
    steps.append(gate)

    if len(runs) < 2:
        slice_step = _step(9, "slice", STEP_NOT_STARTED if not runs else STEP_IN_PROGRESS,
                           "one measurement; no boundary change is evidenced yet",
                           "pick one finding, change one boundary, re-measure")
    else:
        first, last = _error_count(runs[0]["payload"]), _error_count(runs[-1]["payload"])
        if last < first:
            slice_step = _step(9, "slice", STEP_COMPLETE,
                               f"errors fell from {first} ({runs[0]['path']}) to "
                               f"{last} ({runs[-1]['path']})")
        else:
            slice_step = _step(9, "slice", STEP_IN_PROGRESS,
                               f"errors did not fall between {runs[0]['path']} and {runs[-1]['path']}",
                               "land one boundary change and re-measure")
    steps.append(slice_step)
    steps.append(_claim_evidence(root, runs, level))
    steps.append(_step(11, "maintain", STEP_NOT_APPLICABLE,
                       "maintaining the standard is not part of adopting it"))

    optional = [{"name": name, "path": f"docs/acima/{name}", "present": (root / "docs/acima" / name).is_file()}
                for name in ("adoption-plan.md", "communication-plan.md", "STATUS.md")]

    next_step = {"action": "", "why": "", "command": "", "doneWhen": "",
                 "approvalRequired": False, "writes": False}
    preflight = "python3 skills/acima-adoption/scripts/preflight.py --project . --format text"

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
                         command=f"{preflight} && python3 tools/acima.py assess --root .",
                         doneWhen="a verdict and named gaps exist; no target file is written.")
    elif not runs:
        next_step.update(action="Measure the current architecture",
                         why="Without a measured run, findings and progress are guesses.",
                         command=f"{_enforcer_command(language)} --root . --format json",
                         doneWhen="the JSON parses, sourceFiles > 0 and the execution map is complete.")
    elif gate["state"] == STEP_NOT_STARTED:
        next_step.update(action="Ask the owner to approve a CI gate",
                         why="The gate is what stops new violations; it is a write and needs consent.",
                         command="propose .github/workflows/acima.yml running the enforcer for the declared level",
                         doneWhen="an approved workflow invokes the gate on pull requests.",
                         approvalRequired=True, writes=True)
    elif gate["state"] == STEP_BLOCKED:
        next_step.update(action="Make the CI workflow run a real gate",
                         why="A workflow that mentions ACIMA without invoking it proves nothing.",
                         command="edit the workflow to run the enforcer with --root and the declared level",
                         doneWhen="the workflow invokes the gate and a failing pull request blocks.",
                         approvalRequired=True, writes=True)
    elif own["state"] in (STEP_BLOCKED, STEP_IN_PROGRESS) or (newest and errors and not waiver_list):
        next_step.update(action="Give every exception an owner and an expiry",
                         why="Unowned or expired exceptions hide new findings.",
                         command="edit .acima/waivers.json: one owner, reason, scope, expiry and review date each",
                         doneWhen="no waiver is unassigned and none is expired.",
                         approvalRequired=True, writes=True)
    elif gate["state"] == STEP_IN_PROGRESS:
        next_step.update(action="Confirm the gate actually runs on a pull request",
                         why="A configured workflow is not evidence that the check executes or blocks.",
                         command="open a pull request and watch the ACIMA check; keep the result",
                         doneWhen="the check appears and a failing commit is rejected.")
    elif steps[9]["state"] in (STEP_NOT_STARTED, STEP_IN_PROGRESS):
        rule = ""
        if newest and newest["payload"].get("findings"):
            rule = str(newest["payload"]["findings"][0].get("rule") or "")
        next_step.update(action="Plan one boundary correction from the newest run",
                         why="One boundary per pull request keeps the gate explainable.",
                         command=f"python3 tools/acima.py fix --report {newest['path']} "
                                 f"{rule or '--all'}".replace("  ", " "),
                         doneWhen="one correction is chosen, explained and separately approved.")
    elif steps[10]["state"] == STEP_IN_PROGRESS:
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
        "config": {"present": config is not None, "level": level, "mode": mode,
                   "units": len(units), "problem": config_problem or None},
        "evidence": {
            "runArtefacts": [entry["path"] for entry in runs],
            "rejectedArtefacts": rejected_runs,
            "runErrors": errors,
            "waivers": len(waiver_list), "unownedWaivers": len(unowned),
            "expiredWaivers": len(expired), "gateWorkflows": workflows,
            "gateObserved": observation is not None,
            "manualEvidence": (root / EVIDENCE_FILE).is_file(),
            "fingerprints": len(fingerprinted),
        },
        "steps": steps,
        "verified": verified,
        "remaining": remaining,
        "blocked": blocked,
        "optional": optional,
        "next": next_step,
        "limitation": ("Derived from artefacts and verified criteria; a missing or unparsable "
                       "artefact is reported, never assumed complete. Optional documents never "
                       "block adoption."),
    }


def status_text(report: dict) -> str:
    config = report["config"]
    evidence = report["evidence"]
    lines = ["ACIMA status",
             "  repository  " + report["root"],
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
