#!/usr/bin/env python3
"""ACIMA adoption preflight.

Answers three questions with evidence, and never writes to the target unless asked:

1. Is this skill still calibrated to the ACIMA catalog in this repository?
2. Is the target greenfield, brownfield, or already adopting?
3. What is the exact next step, and what blocks it?

    python3 preflight.py --project <path> [--format json|text] [--deep]
                         [--write-draft acima.config.json]
                         [--write-waivers .acima/waivers.json]
                         [--strict] [--manifest <path>]

Exit codes: 0 ready, 1 blocked, 2 the tool could not run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
STANDARD_ROOT = SKILL_DIR.parents[1]

PRUNE = {
    ".git", "node_modules", "bin", "obj", "dist", "build", "target", "out",
    ".venv", "venv", "__pycache__", ".next", ".nuxt", "coverage", ".idea", ".vs",
}
SOURCE_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".mjs", ".cjs", ".cs", ".go", ".java",
    ".kt", ".rs", ".rb", ".php", ".scala", ".swift",
}
LEVELS = {"L1", "L2", "L3"}
WAIVER_FIELDS = ("rule", "scope", "owner", "reason", "expires", "reviewedOn")


@dataclass
class Check:
    id: str
    status: str
    detail: str
    remedy: str = ""


@dataclass
class Report:
    checks: list[Check] = field(default_factory=list)
    proposed_units: list[dict] = field(default_factory=list)
    findings: dict = field(default_factory=dict)
    mode: str = "unknown"
    language: str = "unknown"
    detected_languages: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)

    def add(self, check_id: str, status: str, detail: str, remedy: str = "") -> None:
        self.checks.append(Check(check_id, status, detail, remedy))

    @property
    def blockers(self) -> list[Check]:
        return [c for c in self.checks if c.status == "fail"]

    @property
    def warnings(self) -> list[Check]:
        return [c for c in self.checks if c.status == "warn"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def walk_files(root: Path, limit: int = 50000):
    seen = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in PRUNE and not d.startswith("."))
        for name in sorted(filenames):
            if name.startswith("."):
                continue
            yield Path(dirpath) / name
            seen += 1
            if seen >= limit:
                return


def count_sources(root: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    for path in walk_files(root):
        suffix = path.suffix.lower()
        if suffix in SOURCE_EXTENSIONS:
            counts[suffix] = counts.get(suffix, 0) + 1
    return counts


def has_sources(directory: Path) -> bool:
    for path in walk_files(directory, limit=2000):
        if path.suffix.lower() in SOURCE_EXTENSIONS:
            return True
    return False


LANGUAGE_BY_EXTENSION = {
    ".cs": "dotnet", ".go": "go", ".ts": "typescript", ".tsx": "typescript",
    ".js": "typescript", ".mjs": "typescript", ".cjs": "typescript",
    ".py": "python", ".java": "java", ".kt": "java",
}
LANGUAGE_MARKERS = {
    "dotnet": ["*.sln", "*.csproj", "global.json"],
    "go": ["go.mod"],
    "typescript": ["package.json", "tsconfig.json"],
    "python": ["pyproject.toml", "setup.py", "setup.cfg", "requirements.txt"],
    "java": ["pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle"],
}


def detect_languages(project: Path, counts: dict[str, int]) -> list[str]:
    found: list[str] = []
    for language, patterns in LANGUAGE_MARKERS.items():
        for pattern in patterns:
            if list(project.glob(pattern)):
                found.append(language)
                break
    ranked = sorted(
        counts.items(), key=lambda item: item[1], reverse=True
    )
    for extension, _ in ranked:
        language = LANGUAGE_BY_EXTENSION.get(extension)
        if language and language not in found:
            found.append(language)
    return found


def propose_units(project: Path, language: str) -> list[dict]:
    if language == "dotnet":
        return propose_dotnet_units(project)
    return propose_directory_units(project)


def propose_dotnet_units(project: Path) -> list[dict]:
    units: list[dict] = []
    seen: set[str] = set()
    for project_file in sorted(project.rglob("*.csproj")):
        if any(part in PRUNE or part.startswith(".") for part in project_file.parts):
            continue
        directory = project_file.parent
        relative = directory.relative_to(project).as_posix()
        if relative in seen:
            continue
        seen.add(relative)
        name = directory.name
        if name.endswith(".Contracts"):
            module = name[: -len(".Contracts")].lower()
            units.append({"id": f"{module}.contracts", "module": module,
                          "role": "contracts", "paths": [relative]})
        else:
            module = name.lower()
            units.append({"id": module, "module": module,
                          "role": "implementation", "paths": [relative]})
    return units[:16]


def propose_directory_units(project: Path) -> list[dict]:
    bases = [base for base in (project / "src", project / "internal", project / "packages")
             if base.is_dir()]
    if not bases:
        bases = [project]
    units: list[dict] = []
    seen_paths: set[str] = set()
    for base in bases:
        if not base.is_dir():
            continue
        for child in sorted(base.iterdir()):
            if not child.is_dir() or child.name in PRUNE or child.name.startswith("."):
                continue
            relative = child.relative_to(project).as_posix()
            if relative in seen_paths or not has_sources(child):
                continue
            seen_paths.add(relative)
            module = child.name.lower()
            contracts = child / "contracts"
            implementation = child / "impl"
            if contracts.is_dir():
                units.append({"id": f"{module}.contracts", "module": module,
                              "role": "contracts", "paths": [f"{relative}/contracts"]})
            if implementation.is_dir():
                units.append({"id": module, "module": module,
                              "role": "implementation", "paths": [f"{relative}/impl"]})
            if not contracts.is_dir() and not implementation.is_dir():
                units.append({"id": module, "module": module,
                              "role": "implementation", "paths": [relative]})
    return units[:16]


def draft_config(manifest: dict, language: str, units: list[dict]) -> dict:
    return {
        "_generatedBy": "acima-adoption preflight --write-draft",
        "_note": "Heuristic draft. Review module names, merge or split units, then commit.",
        "standard": manifest["standard"],
        "language": language,
        "level": "L1",
        "root": ".",
        "units": units,
        "exclude": ["bin", "obj", "node_modules", "dist", "build", "target",
                    "tests", "**/__pycache__"],
        "waivers": ".acima/waivers.json",
    }


def unit_for_path(path: str, units: list[dict]) -> dict | None:
    best = None
    best_length = -1
    for unit in units:
        for prefix in unit.get("paths", []):
            clean = prefix.rstrip("/")
            if (path == clean or path.startswith(clean + "/")) and len(clean) > best_length:
                best = unit
                best_length = len(clean)
    return best


def waiver_stub(findings: list[dict], units: list[dict], days: int = 90) -> dict:
    today = date.today()
    grouped: dict[tuple[str, str], int] = {}
    for finding in findings:
        rule = finding.get("rule")
        unit = unit_for_path(finding.get("path", ""), units)
        if not rule or unit is None:
            continue
        key = (rule, unit["id"])
        grouped[key] = grouped.get(key, 0) + 1

    waivers = []
    for (rule, unit_id), count in sorted(grouped.items()):
        waivers.append({
            "rule": rule,
            "scope": f"unit:{unit_id}",
            "owner": "unassigned",
            "reason": f"baseline: {count} pre-existing finding(s) in {unit_id}",
            "expires": (today + timedelta(days=days)).isoformat(),
            "reviewedOn": today.isoformat(),
        })
    return {"standard": "1.0.0-draft.1", "waivers": waivers}


def run(command: list[str], cwd: Path, timeout: int = 240) -> tuple[int, str, str]:
    try:
        import subprocess

        result = subprocess.run(command, cwd=str(cwd), capture_output=True,
                                text=True, timeout=timeout)
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        return 127, "", f"{command[0]} is not installed"
    except Exception as error:  # noqa: BLE001 - preflight must never crash
        return 126, "", str(error)


def enforcer_invocation(manifest: dict, language: str, project: Path,
                        config_name: str | None = None):
    enforcer = manifest.get("enforcers", {}).get(language, {})
    if not enforcer.get("run"):
        return None
    command = list(enforcer["run"]) + ["--root", str(project)]
    if config_name:
        # Every reference enforcer resolves --config relative to --root, not to cwd.
        command += ["--config", config_name]
    command += ["--format", "json"]
    cwd = STANDARD_ROOT / enforcer["cwd"] if enforcer.get("cwd") else STANDARD_ROOT
    return command, cwd


def prepare_dotnet(manifest: dict) -> None:
    project = manifest.get("enforcers", {}).get("dotnet", {}).get("buildProject")
    if project:
        run(["dotnet", "build", str(STANDARD_ROOT / project), "-v", "q", "--nologo"],
            STANDARD_ROOT)


def check_skill(manifest: dict, manifest_path: Path, report: Report) -> None:
    report.add("SKL-001", "pass",
               f"manifest {manifest.get('skill')} {manifest.get('skillVersion')} loaded")
    catalog = manifest.get("catalog", {})
    catalog_path = STANDARD_ROOT / catalog.get("path", "")
    if not catalog_path.is_file():
        report.add("SKL-002", "fail", f"catalog not found at {catalog_path}",
                   "run the preflight from inside the ACIMA repository")
        return

    actual_hash = sha256(catalog_path)
    if actual_hash != catalog.get("sha256"):
        report.add("SKL-002", "fail",
                   f"rules.json is {actual_hash[:12]}… but the skill pins {catalog.get('sha256', '?')[:12]}…",
                   "the standard changed after this skill was written: re-read the changed rules, "
                   "update manifest.json and the references, then re-run")
    else:
        report.add("SKL-002", "pass", f"catalog hash matches the pin ({actual_hash[:12]}…)")

    try:
        rules = load_json(catalog_path).get("rules", [])
    except json.JSONDecodeError as error:
        report.add("SKL-002", "fail", f"rules.json is not valid JSON: {error}", "repair the catalog")
        return

    ids = {rule.get("id") for rule in rules}
    portable = catalog.get("portableIds", [])
    missing = [rule_id for rule_id in portable if rule_id not in ids]
    if len(rules) != catalog.get("rules"):
        report.add("SKL-003", "fail",
                   f"catalog has {len(rules)} rules, the skill pins {catalog.get('rules')}",
                   "update the skill against the new catalog")
    elif missing:
        report.add("SKL-003", "fail",
                   f"portable rule ids missing from the catalog: {', '.join(missing)}",
                   "update the skill: a rule was renamed or removed")
    else:
        report.add("SKL-003", "pass",
                   f"{len(rules)} rules, all {len(portable)} portable ids present")

    version = load_json(catalog_path).get("version")
    if version != manifest.get("standard"):
        report.add("SKL-004", "fail",
                   f"catalog version is {version}, the skill pins {manifest.get('standard')}",
                   "update manifest.standard and any version-specific guidance")
    else:
        report.add("SKL-004", "pass", f"standard version {version}")

    missing_references = [
        path for path in manifest.get("references", []) + manifest.get("assets", [])
        if not (SKILL_DIR / path).is_file()
    ]
    if missing_references:
        report.add("SKL-005", "fail",
                   f"missing skill files: {', '.join(missing_references)}",
                   "restore them; a reference map that points at nothing is worse than none")
    else:
        report.add("SKL-005", "pass",
                   f"{len(manifest.get('references', []))} references and "
                   f"{len(manifest.get('assets', []))} assets present")

    missing_enforcers = []
    for language, enforcer in manifest.get("enforcers", {}).items():
        path = enforcer.get("path")
        if not path:
            continue
        if not (STANDARD_ROOT / path).exists():
            missing_enforcers.append(f"{language}: {path}")
    if missing_enforcers:
        report.add("SKL-006", "fail",
                   f"documented enforcers are missing: {'; '.join(missing_enforcers)}",
                   "the repository layout changed: update manifest.enforcers and SKILL.md commands")
    else:
        report.add("SKL-006", "pass", "every documented enforcer path exists")

    galleries = [
        f"examples/{language}/violations/expected.json"
        for language, enforcer in manifest.get("enforcers", {}).items()
        if enforcer.get("path")
    ]
    absent = [gallery for gallery in galleries if not (STANDARD_ROOT / gallery).is_file()]
    if absent:
        report.add("SKL-007", "warn",
                   f"no violation baseline at: {', '.join(absent)}",
                   "the gallery is the executable definition of the rules; restore it")
    else:
        report.add("SKL-007", "pass", f"{len(galleries)} violation baselines present")

    if manifest_path != SKILL_DIR / "manifest.json":
        report.add("SKL-008", "warn", f"non-default manifest used: {manifest_path}",
                   "this is a test or a fork; the default manifest is the calibration")


def check_environment(report: Report) -> None:
    import shutil as shutil_module

    toolchains = {"python3": True, "node": False, "go": False, "dotnet": False, "java": False}
    available = [name for name in toolchains if shutil_module.which(name)]
    report.add("ENV-001", "pass", f"toolchains available: {', '.join(available) or 'none'}")
    if "python3" not in available:
        report.add("ENV-002", "fail", "python3 is not on PATH",
                   "the preflight itself requires Python 3.9+")


def check_target(project: Path, report: Report, manifest: dict) -> tuple[list[dict], dict | None]:
    if not project.is_dir():
        report.add("TGT-001", "fail", f"target does not exist: {project}",
                   "pass --project with the repository root")
        return [], None
    report.add("TGT-001", "pass", f"target {project}")

    counts = count_sources(project)
    total = sum(counts.values())
    languages = detect_languages(project, counts)
    report.detected_languages = languages
    primary = None
    if languages:
        primary = max(languages, key=lambda name: sum(
            count for extension, count in counts.items()
            if LANGUAGE_BY_EXTENSION.get(extension) == name
        ))
    report.language = primary or "unknown"
    if primary is None:
        report.add("TGT-002", "warn", "no recognised language manifest or sources",
                   "confirm this is the right path, or scaffold before adopting")
    else:
        report.add("TGT-002", "pass",
                   f"language {primary} ({total} source files; detected: {', '.join(languages)})")

    config_path = project / "acima.config.json"
    config = None
    if config_path.is_file():
        report.mode = "adopting"
        try:
            config = load_json(config_path)
            report.add("TGT-003", "pass", "acima.config.json present (mode: adopting)")
        except json.JSONDecodeError as error:
            report.add("TGT-003", "fail", f"acima.config.json is not valid JSON: {error}",
                       "repair the config; every enforcer will refuse to run")
            return [], None

        units = config.get("units", [])
        level = config.get("level")
        if not units:
            report.add("GOV-001", "fail", "config declares no units",
                       "declare at least one unit; an empty config classifies nothing")
        elif level not in LEVELS:
            report.add("GOV-001", "fail", f"config level is {level!r}, expected L1, L2 or L3",
                       "declare a level; conformance is level-relative")
        else:
            report.add("GOV-001", "pass", f"{len(units)} units declared at {level}")

        language = config.get("language") or report.language
        enforcer = manifest.get("enforcers", {}).get(language, {})
        if not enforcer.get("run"):
            report.add("GOV-002", "skip",
                       f"no reference enforcer for {language}",
                       "apply the profile's native analyzer; say plainly that this profile has no runner")
        else:
            command, cwd = enforcer_invocation(manifest, language, project, "acima.config.json")
            if language == "dotnet":
                prepare_dotnet(manifest)
            code, out, err = run(command, cwd)
            if code == 2:
                report.add("GOV-002", "fail",
                           f"enforcer failed to run: {(err or out).strip()[:300]}",
                           "fix the enforcer invocation before trusting any architecture claim")
            else:
                try:
                    payload = json.loads(out)
                    findings = payload.get("findings", [])
                except json.JSONDecodeError:
                    report.add("GOV-002", "fail", "enforcer returned no JSON",
                               "this is a tool failure, not an architecture result")
                    findings = []
                report.findings = {
                    "total": len(findings),
                    "errors": sum(1 for f in findings if f.get("severity") == "error"),
                    "byRule": _group(findings, "rule"),
                    "byPath": _group(findings, "path"),
                }
                if code == 1:
                    report.add("GOV-002", "warn",
                               f"baseline is not clean: {len(findings)} finding(s), "
                               f"{report.findings['errors']} error(s)",
                               "this is expected on day one: waive deliberately, then ratchet")
                else:
                    report.add("GOV-002", "pass", "baseline is clean at the declared level")

        waiver_name = config.get("waivers")
        if waiver_name:
            waiver_path = project / waiver_name
            if not waiver_path.is_file():
                report.add("GOV-003", "fail", f"waivers file missing: {waiver_name}",
                           "create it with an empty waivers array, or fix the path")
            else:
                try:
                    document = load_json(waiver_path)
                    waivers = document.get("waivers", [])
                except json.JSONDecodeError as error:
                    report.add("GOV-003", "fail", f"waivers file invalid: {error}",
                               "repair it; an unreadable waiver file disables the gate")
                    waivers = []
                    document = {}
                if document:
                    incomplete = [
                        waiver for waiver in waivers
                        if any(not str(waiver.get(field, "")).strip() for field in WAIVER_FIELDS)
                    ]
                    expired = [
                        waiver for waiver in waivers
                        if str(waiver.get("expires", ""))[:10] < date.today().isoformat()
                    ]
                    unassigned = [
                        waiver for waiver in waivers
                        if str(waiver.get("owner", "")).strip().lower() == "unassigned"
                    ]
                    if incomplete:
                        report.add("GOV-003", "fail",
                                   f"{len(incomplete)} waiver(s) missing required fields",
                                   "G001 requires rule, scope, owner, reason, expires and reviewedOn")
                    elif expired:
                        report.add("GOV-003", "fail",
                                   f"{len(expired)} expired waiver(s)",
                                   "renew deliberately with the owner, or fix the violation")
                    else:
                        report.add("GOV-003", "pass",
                                   f"{len(waivers)} active waiver(s), none expired")
                    if unassigned:
                        report.add("GOV-004", "warn",
                                   f"{len(unassigned)} waiver(s) still owned by 'unassigned'",
                                   "replace with real names before the first gate is merged")
    else:
        if total < 10:
            report.mode = "greenfield"
            report.add("TGT-003", "pass",
                       f"no config and {total} source file(s) (mode: greenfield)")
        else:
            report.mode = "brownfield"
            report.add("TGT-003", "pass",
                       f"no config and {total} source file(s) (mode: brownfield)")

        report.proposed_units = propose_units(project, report.language)
        if report.proposed_units:
            report.add("TGT-004", "pass",
                       f"{len(report.proposed_units)} candidate unit(s) proposed from the layout")
        else:
            report.add("TGT-004", "warn", "no candidate units found",
                       "declare units manually; ADR-0001 in the adoption plan explains the split")

        if report.mode == "brownfield":
            covered = sum(
                1 for path in walk_files(project)
                if path.suffix.lower() in SOURCE_EXTENSIONS
                and unit_for_path(path.relative_to(project).as_posix(),
                                  report.proposed_units) is not None
            )
            uncovered = max(total - covered, 0)
            if uncovered:
                report.add("TGT-005", "warn",
                           f"{uncovered} source file(s) fall outside the proposed units",
                           "they will be G005 findings until the map covers them")
            else:
                report.add("TGT-005", "pass", "every source file is covered by a proposed unit")
    return report.proposed_units, config


def _group(findings: list[dict], key: str) -> dict:
    grouped: dict[str, int] = {}
    for finding in findings:
        value = str(finding.get(key, "?"))
        grouped[value] = grouped.get(value, 0) + 1
    return dict(sorted(grouped.items(), key=lambda item: item[1], reverse=True))


def check_deep(manifest: dict, report: Report) -> None:
    import shutil as shutil_module

    for language, enforcer in manifest.get("enforcers", {}).items():
        if not enforcer.get("run"):
            report.add(f"ENF-{language}", "skip", f"{language}: no reference runner")
            continue
        if shutil_module.which(enforcer["run"][0]) is None:
            report.add(f"ENF-{language}", "skip", f"{language}: {enforcer['run'][0]} not installed")
            continue
        example = enforcer.get("example")
        if not example:
            continue
        command, cwd = enforcer_invocation(manifest, language, STANDARD_ROOT / example)
        if language == "dotnet":
            prepare_dotnet(manifest)
        code, out, err = run(command, cwd)
        if code != 0:
            report.add(f"ENF-{language}", "fail",
                       f"{language} example is not clean (exit {code}): {(err or out)[:200]}",
                       "fix the example before using this skill as a reference")
            continue
        try:
            findings = json.loads(out).get("findings", [])
        except json.JSONDecodeError:
            report.add(f"ENF-{language}", "fail", f"{language} enforcer returned no JSON",
                       "tool failure: do not use it as a reference")
            continue
        if findings:
            report.add(f"ENF-{language}", "fail",
                       f"{language} example has {len(findings)} finding(s)",
                       "the reference implementation must be clean")
        else:
            report.add(f"ENF-{language}", "pass", f"{language} example is clean at L3")


def build_next_steps(report: Report, project: Path, manifest: dict,
                     draft_path: str | None, waiver_path: str | None) -> list[str]:
    steps: list[str] = []
    if report.blockers:
        for blocker in report.blockers:
            steps.append(f"Resolve {blocker.id}: {blocker.remedy or blocker.detail}")
        return steps

    if report.mode == "greenfield":
        steps = [
            "Create the shared kernel, then the first two contracts, then their implementations.",
            "Write acima.config.json and an empty waiver file in the same commit.",
            "Wire the enforcer into CI before the second module exists.",
            "Declare L3 and keep it: nothing is fighting you yet.",
            "Read references/10-greenfield.md for the exact skeleton.",
        ]
    elif report.mode == "brownfield":
        if draft_path and (project / draft_path).is_file():
            steps.append(f"Review the draft at {draft_path}: rename units to domain concepts, then commit it.")
            steps.append("Run the preflight again with the config in place to measure the baseline.")
            steps.append("Write scoped waivers for the baseline, replacing 'unassigned' with owners.")
        elif not (project / "acima.config.json").is_file():
            steps.append("Generate a draft unit map: --write-draft acima.config.json, then review it.")
        if waiver_path and (project / waiver_path).is_file():
            steps.append(f"Replace every 'unassigned' owner in {waiver_path} before merging the gate.")
        steps.extend([
            "Gate CI on 'no new findings' at L1; do not fix the architecture first.",
            "Pick the first slice from references/20-brownfield.md (contracts, not persistence).",
        ])
    elif report.mode == "adopting":
        if report.findings.get("errors", 0) > 0:
            steps.append("Baseline is not clean: confirm every existing finding has an owner and an expiry.")
        else:
            steps.append("Baseline is clean: keep the gate on, and raise the level when ready.")
        steps.append("Record the run artefact with the build; conformance is a claim plus evidence.")
    else:
        steps.append("Confirm the target path and language, then re-run the preflight.")

    if report.language == "java" and not manifest.get("enforcers", {}).get("java", {}).get("run"):
        steps.append("Java has a profile but no reference enforcer in this revision: use ArchUnit and say so.")
    return steps


def main() -> int:
    parser = argparse.ArgumentParser(description="ACIMA adoption preflight")
    parser.add_argument("--project", default=".", help="target repository root")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--manifest", default=str(SKILL_DIR / "manifest.json"))
    parser.add_argument("--deep", action="store_true",
                        help="also run every reference enforcer against its example")
    parser.add_argument("--write-draft", dest="write_draft", default=None,
                        help="write a heuristic acima.config.json draft (relative to the target)")
    parser.add_argument("--write-waivers", dest="write_waivers", default=None,
                        help="write scoped waivers from the measured baseline")
    parser.add_argument("--strict", action="store_true", help="treat warnings as blockers")
    args = parser.parse_args()

    manifest_path = Path(args.manifest).resolve()
    project = Path(args.project).resolve()
    report = Report()

    try:
        manifest = load_json(manifest_path)
    except FileNotFoundError:
        print(f"acima: manifest not found: {manifest_path}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as error:
        print(f"acima: manifest is not valid JSON: {error}", file=sys.stderr)
        return 2

    check_skill(manifest, manifest_path, report)
    check_environment(report)
    units, config = check_target(project, report, manifest)

    if args.deep:
        check_deep(manifest, report)

    if args.write_draft:
        if report.mode == "adopting":
            report.add("OUT-001", "warn", "draft not written: a config already exists",
                       "edit the existing config instead of overwriting it")
        elif not units:
            report.add("OUT-001", "fail", "draft not written: no units were proposed",
                       "declare units manually")
        else:
            destination = project / args.write_draft
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(
                json.dumps(draft_config(manifest, report.language, units), indent=2) + "\n",
                encoding="utf-8",
            )
            report.add("OUT-001", "pass", f"draft written to {args.write_draft}")
            report.next_steps.insert(0, f"Review {args.write_draft} before committing it")

    if args.write_waivers:
        if not config:
            report.add("OUT-002", "fail", "waivers not written: no config to measure against",
                       "run --write-draft first, review it, then re-run")
        elif not report.findings:
            report.add("OUT-002", "skip", "waivers not written: no baseline findings")
        else:
            findings_payload = _read_findings(manifest, project, config, report)
            document = waiver_stub(findings_payload, config.get("units", []))
            destination = project / args.write_waivers
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
            report.add("OUT-002", "pass",
                       f"{len(document['waivers'])} waiver(s) written to {args.write_waivers}")

    report.next_steps = build_next_steps(report, project, manifest,
                                         args.write_draft, args.write_waivers)
    blocked = bool(report.blockers) or (args.strict and bool(report.warnings))

    if args.format == "json":
        payload = {
            "skill": {"name": manifest.get("skill"), "version": manifest.get("skillVersion"),
                      "standard": manifest.get("standard"),
                      "catalogSha256": manifest.get("catalog", {}).get("sha256")},
            "project": {"path": str(project), "mode": report.mode,
                        "language": report.language,
                        "detectedLanguages": report.detected_languages},
            "checks": [check.__dict__ for check in report.checks],
            "blockers": [check.id for check in report.blockers],
            "warnings": [check.id for check in report.warnings],
            "findings": report.findings,
            "proposedUnits": units,
            "next": report.next_steps,
        }
        print(json.dumps(payload, indent=2))
    else:
        print_text(report, manifest, project, units, strict=args.strict)

    return 1 if blocked else 0


def _read_findings(manifest: dict, project: Path, config: dict, report: Report) -> list[dict]:
    language = config.get("language") or report.language
    invocation = enforcer_invocation(manifest, language, project, "acima.config.json")
    if invocation is None:
        return []
    command, cwd = invocation
    if language == "dotnet":
        prepare_dotnet(manifest)
    _code, out, _err = run(command, cwd)
    try:
        return json.loads(out).get("findings", [])
    except json.JSONDecodeError:
        return []


def print_text(report: Report, manifest: dict, project: Path, units: list[dict],
               strict: bool = False) -> None:
    symbols = {"pass": "ok  ", "warn": "!   ", "fail": "x   ", "skip": "-   "}
    print("ACIMA adoption preflight")
    print(f"  standard {manifest.get('standard')} · skill {manifest.get('skillVersion')} · "
          f"catalog {str(manifest.get('catalog', {}).get('sha256'))[:8]}…")
    print(f"  target   {project}")
    print(f"  mode     {report.mode} · language {report.language}")
    print()
    for check in report.checks:
        print(f"  {symbols.get(check.status, '?   ')}{check.id:<8} {check.detail}")
        if check.status in ("fail", "warn") and check.remedy:
            print(f"          -> {check.remedy}")

    if units and report.mode != "adopting":
        print()
        print("  proposed units")
        for unit in units:
            print(f"    {unit['role']:<14} {unit['id']:<22} {', '.join(unit['paths'])}")

    print()
    if report.blockers:
        print(f"BLOCKED: {len(report.blockers)} blocker(s)")
    elif strict and report.warnings:
        print(f"BLOCKED (strict): {len(report.warnings)} warning(s) treated as errors")
    elif report.warnings:
        print(f"READY with {len(report.warnings)} warning(s)")
    else:
        print("READY")

    if report.next_steps:
        print()
        print("next")
        for index, step in enumerate(report.next_steps, start=1):
            print(f"  {index}. {step}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(2)
    except Exception as error:  # noqa: BLE001 - a crash must be distinguishable from a finding
        print(f"acima: preflight failed: {error}", file=sys.stderr)
        raise SystemExit(2)
