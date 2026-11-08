#!/usr/bin/env python3
"""ACIMA's developer entry point.

This is a thin, deterministic wrapper over the rules and enforcers in this repository.
It does not implement a second rule engine.

    python3 tools/acima.py inspect --root examples/python
    python3 tools/acima.py analyze --root examples/python --format text
    python3 tools/acima.py report  --root examples/python --format markdown
    python3 tools/acima.py verify
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ACIMA_ROOT = Path(__file__).resolve().parents[1]
CONFIG_NAME = "acima.config.json"
PRUNE = {".git", "node_modules", "bin", "obj", "dist", "build", "target", "out",
         ".venv", "venv", "__pycache__", ".next", ".nuxt", "coverage"}
SOURCE_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".mjs", ".cjs", ".cs", ".go", ".java"}
CATEGORY = {
    "D": "Dependency and structure",
    "L": "Layering inside a module",
    "C": "Contract shape and immutability",
    "A": "Autonomy at runtime",
    "G": "Governance and exceptions",
}
# Rules the portable reference enforcers deliberately do not decide from source text.
NON_PORTABLE = {
    "ACIMA-C003", "ACIMA-C007", "ACIMA-L004",
    "ACIMA-A002", "ACIMA-A004", "ACIMA-G004",
}
# All implemented reference enforcers cover the same 23 portable rules.
LANGUAGE_GAPS: dict[str, set[str]] = {}
LANGUAGE_MARKERS = {
    "dotnet": (".csproj", ".sln", "global.json"),
    "go": ("go.mod",),
    "typescript": ("package.json", "tsconfig.json"),
    "python": ("pyproject.toml", "setup.py", "setup.cfg", "requirements.txt"),
    "java": ("pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle"),
}


def _walk(root: Path):
    for path in root.rglob("*"):
        if any(part in PRUNE or part.startswith(".") for part in path.parts):
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


def report_markdown(root: Path, payload: dict, language: str, config: dict | None) -> str:
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
    return "\n".join(lines)


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
        config = read_config(Path(args.root), args.config or CONFIG_NAME)
        if args.format == "json":
            print(json.dumps({
                "summary": summarize(payload),
                "findings": payload.get("findings", []),
                "language": language,
                "level": payload.get("level"),
                "notEvaluated": not_evaluated(language),
                "limitation": "Evidence only; no productivity or health score is inferred.",
            }, indent=2))
        else:
            print(report_markdown(Path(args.root), payload, language, config))
        return code

    result = subprocess.run([sys.executable, str(ACIMA_ROOT / "conformance/run.py")] + args.profiles,
                            cwd=ACIMA_ROOT)
    return result.returncode


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ConfigError as error:
        print(f"acima: {error}", file=sys.stderr)
        raise SystemExit(2)
