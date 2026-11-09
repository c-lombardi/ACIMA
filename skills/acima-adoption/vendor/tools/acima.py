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


def _gate_workflow(root: Path) -> str | None:
    directory = root / ".github/workflows"
    if not directory.is_dir():
        return None
    for path in sorted(directory.glob("*.y*ml")):
        try:
            if "acima" in path.read_text(encoding="utf-8", errors="replace").lower():
                return path.relative_to(root).as_posix()
        except OSError:
            continue
    return None


def status_project(root: Path) -> dict:
    """Report which adoption steps are evidenced, and the next command to run.

    Read-only. Completeness is inferred from artefacts on disk, never from intent, so a step
    whose evidence is missing is reported as pending rather than assumed done.
    """
    root = root.resolve()
    if not root.is_dir():
        raise ConfigError(f"not a directory: {root}")
    config = read_config(root)
    languages = detect_languages(root)
    language = (config or {}).get("language") or (languages[0] if languages else None)
    sources = sum(1 for path in _walk(root) if path.suffix.lower() in SOURCE_EXTENSIONS)
    units = list((config or {}).get("units", []))
    level = (config or {}).get("level")
    mode = (config or {}).get("mode") or "base"

    waiver_path = root / ((config or {}).get("waivers") or ".acima/waivers.json")
    waivers = _waiver_document(waiver_path).get("waivers", []) if waiver_path.is_file() else []
    unowned = [w for w in waivers
               if not str(w.get("owner") or "").strip()
               or str(w.get("owner")).strip().lower() == "unassigned"]
    today = date.today().isoformat()
    expired = [w for w in waivers if str(w.get("expires") or "") < today]

    baseline_path = root / ".acima/baseline.json"
    baseline = _waiver_document(baseline_path) if baseline_path.is_file() else {}
    fingerprints = baseline.get("fingerprints")
    fingerprints = fingerprints if isinstance(fingerprints, list) else []

    docs = root / "docs/acima"
    artefacts = sorted(docs.glob("baseline-*.json")) if docs.is_dir() else []
    documents = {name: (docs / name).is_file()
                 for name in ("adoption-plan.md", "communication-plan.md", "STATUS.md")}
    manual = (root / ".acima/manual-evidence.json").is_file()
    workflow = _gate_workflow(root)
    enforcer = _enforcer_command(language)

    def state(done: bool) -> str:
        return "done" if done else "pending"

    steps = [
        {"n": 1, "name": "recon", "state": "ready",
         "evidence": f"{sources} source file(s), {language or 'unknown'}"},
        {"n": 2, "name": "fit", "state": state(bool(config) or docs.is_dir()),
         "evidence": "config declared" if config else "no assessment artefact"},
        {"n": 3, "name": "trust the tool", "state": "not recorded",
         "evidence": "inject_violation.py proves detection"},
        {"n": 4, "name": "calibrate", "state": state(bool(config)),
         "evidence": "preflight produced the unit map" if config else "run preflight.py"},
        {"n": 5, "name": "declare", "state": state(bool(units)),
         "evidence": f"{len(units)} unit(s) at {level or 'unset'}" if units else "no units"},
        {"n": 6, "name": "freeze", "state": state(bool(artefacts)),
         "evidence": artefacts[0].relative_to(root).as_posix() if artefacts else "no baseline artefact"},
        {"n": 7, "name": "own", "state": state(bool(waivers) and not unowned),
         "evidence": f"{len(waivers)} waiver(s), {len(unowned)} unowned, {len(expired)} expired"},
        {"n": 8, "name": "gate", "state": state(bool(workflow)),
         "evidence": workflow or "no workflow mentions acima"},
        {"n": 9, "name": "slice", "state": "in progress" if workflow else "pending",
         "evidence": "one boundary per pull request"},
        {"n": 10, "name": "claim", "state": state(manual),
         "evidence": ".acima/manual-evidence.json" if manual else "no manual evidence"},
        {"n": 11, "name": "maintain", "state": "standard changes only",
         "evidence": "conformance/run.py"},
    ]

    if config is None:
        action = "Assess, then declare units"
        command = ("python3 tools/acima.py assess --root . && "
                   "python3 skills/acima-adoption/scripts/preflight.py --project . --write-draft acima.config.json")
    elif not documents["adoption-plan.md"]:
        action = "Write the adoption plan"
        command = ("copy skills/acima-adoption/assets/adoption-plan.md to docs/acima/adoption-plan.md "
                   "and fill every owner and date")
    elif not documents["communication-plan.md"]:
        action = "Write the communication plan"
        command = ("copy skills/acima-adoption/assets/communication-plan.md to "
                   "docs/acima/communication-plan.md")
    elif not artefacts:
        action = f"Measure the baseline at {level or 'L1'}"
        command = f"{enforcer} --root . --format json > docs/acima/baseline-{today}.json"
    elif not waivers:
        action = "Turn the baseline into owned waivers"
        command = ("python3 skills/acima-adoption/scripts/preflight.py --project . "
                   "--write-waivers .acima/waivers.json")
    elif unowned:
        action = f"Name an owner for {len(unowned)} waiver(s)"
        command = "edit .acima/waivers.json: replace 'unassigned', set expires and reviewedOn"
    elif not workflow:
        action = "Wire the gate into CI"
        command = f"add .github/workflows/acima.yml running: {enforcer} --root . --format json"
    elif not documents["STATUS.md"]:
        action = "Write the status dashboard"
        command = "copy skills/acima-adoption/assets/status-dashboard.md to docs/acima/STATUS.md"
    else:
        action = "Land the next slice and keep the count falling"
        command = f"{enforcer} --root . --format json"

    return {
        "root": str(root), "language": language, "sourceFiles": sources,
        "config": {"present": config is not None, "level": level, "mode": mode, "units": len(units)},
        "evidence": {
            "baselineArtefacts": [path.relative_to(root).as_posix() for path in artefacts],
            "baselineFingerprints": len(fingerprints),
            "waivers": len(waivers), "unownedWaivers": len(unowned),
            "expiredWaivers": len(expired), "gateWorkflow": workflow,
            "manualEvidence": manual, "documents": documents,
        },
        "steps": steps,
        "next": {"action": action, "command": command},
        "limitation": "Derived from artefacts on disk; a missing artefact is reported as pending, not assumed done.",
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
    lines.append("  evidence    baseline artefact %s - fingerprints %s - waivers %s (%s unowned, %s expired) - gate %s"
                 % (len(evidence["baselineArtefacts"]), evidence["baselineFingerprints"],
                    evidence["waivers"], evidence["unownedWaivers"], evidence["expiredWaivers"],
                    evidence["gateWorkflow"] or "none"))
    documents = evidence["documents"]
    lines.append("              plans " + ", ".join("%s %s" % (name, "yes" if present else "no")
                                                    for name, present in documents.items())
                 + " - manual evidence " + ("yes" if evidence["manualEvidence"] else "no"))
    lines += ["", "  steps"]
    for step in report["steps"]:
        lines.append("    %2s  %-19s %-20s %s"
                     % (step["n"], step["name"], step["state"], step["evidence"]))
    lines += ["", "  next", "    " + report["next"]["action"],
              "    $ " + report["next"]["command"]]
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
