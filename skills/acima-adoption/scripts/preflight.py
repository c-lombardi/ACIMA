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
# Inside the standard repository the authority is the tree itself. Copied into ~/.agents or similar
# there is no repository root, so the skill falls back to the snapshot tools/bundle_skill.py writes.
_REPOSITORY = SKILL_DIR.parents[1]
STANDARD_ROOT = (_REPOSITORY if (_REPOSITORY / "tools/acima-spec/rules.json").is_file()
                 else SKILL_DIR / "vendor")
sys.path.insert(0, str(STANDARD_ROOT / "conformance"))
from acima_claim import validate_waivers  # noqa: E402 - shared governance validation
from module_map import (  # noqa: E402
    ModuleMapError, classify_path, discover as discover_module_map, proposed_units,
)

PRUNE = {
    ".git", "node_modules", "bin", "obj", "dist", "build", "target", "out",
    ".venv", "venv", "__pycache__", ".next", ".nuxt", "coverage", ".idea", ".vs",
}
SOURCE_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".mjs", ".cjs", ".cs", ".go", ".java",
    ".kt", ".rs", ".rb", ".php", ".scala", ".swift",
}
LEVELS = {"L1", "L2", "L3"}
ARCHITECTURE_MODES = ("base", "service-topology")
PROFILE_MANIFEST = "acima.topology.json"
WAIVER_FIELDS = ("rule", "scope", "fingerprint", "owner", "reason", "expires", "reviewedOn")


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
    architecture_mode: str = "base"
    profile: str = "none"
    language: str = "unknown"
    detected_languages: list[str] = field(default_factory=list)
    source_coverage: dict = field(default_factory=dict)
    module_map: dict = field(default_factory=dict)
    automation: dict = field(default_factory=dict)
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


def is_test_source(path: Path) -> bool:
    parts = [part.lower() for part in path.parts]
    name = path.name.lower()
    return (any(part in {"test", "tests", "__tests__", "spec", "specs", "e2e"} or
                part.endswith((".test", ".tests", ".spec", ".specs")) for part in parts)
            or any(name.endswith(suffix) for suffix in
                   (".test.ts", ".test.tsx", ".test.js", ".test.jsx",
                    ".spec.ts", ".spec.tsx", ".spec.js", ".spec.jsx")))


def is_tooling_source(path: Path) -> bool:
    name = path.name.lower()
    return (name.startswith(("eslint.config.", "vite.config.", "vitest.config.",
                             "playwright.config.", "tsconfig."))
            or name == "vite-env.d.ts")


def is_generated_source(path: Path) -> bool:
    name = path.name.lower()
    return name.endswith((".g.cs", ".generated.cs", ".designer.cs")) or ".generated." in name


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
    """Use the shared discovery model so preflight and adoption cannot disagree.

    The old language-specific helpers remain as a fallback for old or malformed trees, but
    they are not a second source of truth when discovery succeeds.
    """
    try:
        discovered = discover_module_map(project)
        if discovered.get("proposal"):
            units = proposed_units(discovered)
            if units:
                return units
    except (ModuleMapError, OSError):
        pass
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
        if is_test_source(directory):
            continue
        if name.lower().endswith(".contracts"):
            module = name[: -len(".contracts")].lower()
            units.append({"id": f"{module}.contracts", "module": module,
                          "role": "contracts", "paths": [relative]})
        else:
            module = name.lower()
            units.append({"id": module, "module": module,
                          "role": "implementation", "paths": [relative]})
    return units


def has_direct_sources(directory: Path) -> bool:
    return any(path.is_file() and path.suffix.lower() in SOURCE_EXTENSIONS
               for path in directory.iterdir())


def propose_directory_units(project: Path) -> list[dict]:
    bases = [base for base in (project / "src", project / "internal", project / "packages",
                              project / "app", project / "apps", project / "services",
                              project / "lib", project / "modules")
             if base.is_dir()]
    if not bases:
        bases = [project]
    units: list[dict] = []
    seen_paths: set[str] = set()
    for base in bases:
        # A source root often contains one namespace directory (for example
        # src/acima/catalog, src/acima/orders). Descend through that wrapper so the
        # modules, not the namespace, become the proposed units.
        while base.is_dir() and not has_direct_sources(base):
            children = [child for child in sorted(base.iterdir())
                        if child.is_dir() and child.name not in PRUNE and not child.name.startswith(".")]
            if len(children) != 1:
                break
            base = children[0]
        if not base.is_dir():
            continue
        for child in sorted(base.iterdir()):
            if (not child.is_dir() or child.name in PRUNE or child.name.startswith(".")
                    or is_test_source(child)):
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
    return units


def draft_config(manifest: dict, language: str, units: list[dict]) -> dict:
    return {
        "_generatedBy": "acima-adoption preflight --write-draft",
        "_note": "Heuristic draft. Review module names, merge or split units, then commit.",
        "standard": manifest["standard"],
        "mode": "base",
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
    seen: set[tuple[str, str]] = set()
    waivers = []
    for finding in findings:
        rule = finding.get("rule")
        path = finding.get("path", "")
        fingerprint = finding.get("fingerprint")
        if not rule or not path or not fingerprint:
            continue
        unit = unit_for_path(path, units)
        scope = f"unit:{unit['id']}" if unit else f"path:{path}"
        key = (scope, fingerprint)
        if key in seen:
            continue
        seen.add(key)
        waivers.append({
            "rule": rule,
            "scope": scope,
            "fingerprint": fingerprint,
            "owner": "unassigned",
            "reason": f"baseline: {path}:{finding.get('line', 1)} — {finding.get('message', rule)}",
            "expires": (today + timedelta(days=days)).isoformat(),
            "reviewedOn": today.isoformat(),
        })
    waivers.sort(key=lambda waiver: (waiver["rule"], waiver["scope"], waiver["fingerprint"]))
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


def _catalog_rule_ids() -> set[str]:
    try:
        catalog = load_json(STANDARD_ROOT / "tools/acima-spec/rules.json")
        return {str(rule["id"]) for rule in catalog.get("rules", [])}
    except (OSError, KeyError, TypeError, json.JSONDecodeError):
        return set()


def validate_assessment(payload, code: int, manifest: dict) -> list[str]:
    """Reject incomplete enforcer output before it can become an architecture claim."""
    errors: list[str] = []
    if code not in (0, 1):
        errors.append(f"unexpected enforcer exit code {code}")
    if not isinstance(payload, dict):
        return errors + ["assessment is not a JSON object"]
    if not str(payload.get("standard", "")).strip():
        errors.append("assessment has no standard identity")
    if payload.get("level") not in LEVELS:
        errors.append(f"assessment level is {payload.get('level')!r}")
    source_files = payload.get("sourceFiles")
    if type(source_files) is not int or source_files <= 0:
        errors.append(f"assessment discovered {source_files!r} source files")
    findings = payload.get("findings")
    if not isinstance(findings, list):
        errors.append("assessment findings is not a list")
    else:
        for index, finding in enumerate(findings):
            if not isinstance(finding, dict):
                errors.append(f"finding {index} is not an object")
                continue
            missing = [key for key in ("rule", "severity", "message", "path", "line")
                       if key not in finding]
            if missing:
                errors.append(f"finding {index} is missing {', '.join(missing)}")
    classified = payload.get("classified", [])
    if not isinstance(classified, list):
        errors.append("assessment classified is not a list")
    else:
        for index, item in enumerate(classified):
            if not isinstance(item, dict):
                errors.append(f"classified {index} is not an object")
                continue
            missing = [key for key in ("rule", "path", "classification", "owner", "reason")
                       if not str(item.get(key, "")).strip()]
            if missing:
                errors.append(f"classified {index} is missing {', '.join(missing)}")
            elif item["classification"] not in ("intentional-adapter", "declared-public-api"):
                errors.append(f"classified {index} has unknown classification "
                              f"{item['classification']!r}")
    execution = payload.get("execution")
    expected = _catalog_rule_ids()
    if not isinstance(execution, dict):
        errors.append("assessment has no execution map")
    else:
        if expected and set(execution) != expected:
            missing = sorted(expected - set(execution))
            extra = sorted(set(execution) - expected)
            errors.append("execution map does not cover the catalog"
                          + (f" (missing {', '.join(missing)})" if missing else "")
                          + (f" (extra {', '.join(extra)})" if extra else ""))
        for rule, value in execution.items():
            if not isinstance(value, dict) or type(value.get("executed")) is not bool:
                errors.append(f"execution entry for {rule} has no boolean executed flag")
            elif value.get("executed") is False and not str(value.get("reason", "")).strip():
                errors.append(f"execution entry for {rule} is unexecuted without a reason")
    return errors


def enforcer_invocation(manifest: dict, language: str, project: Path,
                        config_name: str | None = None):
    enforcer = manifest.get("enforcers", {}).get(language, {})
    if not enforcer.get("run"):
        return None
    command = list(enforcer["run"])
    if command and Path(command[0]).stem.lower() in {"python", "python3"}:
        command[0] = sys.executable
    command += ["--root", str(project)]
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
    manual = catalog.get("notPortableIds", [])
    missing = [rule_id for rule_id in portable if rule_id not in ids]
    missing_manual = [rule_id for rule_id in manual if rule_id not in ids]
    if len(rules) != catalog.get("rules"):
        report.add("SKL-003", "fail",
                   f"catalog has {len(rules)} rules, the skill pins {catalog.get('rules')}",
                   "update the skill against the new catalog")
    elif missing or missing_manual:
        report.add("SKL-003", "fail",
                   f"catalog rule ids missing: {', '.join(missing + missing_manual)}",
                   "update the skill: a rule was renamed or removed")
    else:
        report.add("SKL-003", "pass",
                   f"{len(rules)} rules, {len(portable)} automated and {len(manual)} manual ids present")

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

    # This process is already running Python 3.9+, so its own interpreter is the
    # portable Python the enforcers can use even when `python3` is not on PATH
    # (for example behind the Windows App Execution Alias).
    available = ["python3"] + [name for name in ("node", "go", "dotnet", "java")
                               if shutil_module.which(name)]
    report.add("ENV-001", "pass", f"toolchains available: {', '.join(available)}")


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

        topology_present = (project / PROFILE_MANIFEST).is_file()
        declared_mode = config.get("mode", "base")
        report.architecture_mode = declared_mode if declared_mode in ARCHITECTURE_MODES else "unknown"
        if declared_mode not in ARCHITECTURE_MODES:
            report.add("TGT-006", "fail",
                       f"unknown architecture mode {declared_mode!r}; expected base or service-topology",
                       "use one of the two documented modes; a typo must not silently mean base")
        elif declared_mode == "service-topology":
            report.profile = "service-topology" if topology_present else "none"
            if not topology_present:
                report.add("TGT-006", "fail",
                           f"mode is service-topology but {PROFILE_MANIFEST} is missing",
                           "add the profile manifest, or declare mode base")
            else:
                report.add("TGT-006", "fail",
                           "service-topology declared; this skill revision has no supported service "
                           "workflow, so the assessment is NOT SUPPORTED, not clean",
                           "stop; use conformance/topology.py for the profile and do not apply base P2.1")
        elif topology_present:
            report.add("TGT-006", "fail",
                       f"{PROFILE_MANIFEST} is present but mode is base/absent",
                       "declare \"mode\": \"service-topology\" or remove the manifest")
        else:
            report.add("TGT-006", "pass", "architecture mode: base")

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
            # An unsupported language is not a clean baseline. Reporting READY here
            # would turn "we could not check" into "we checked and it is clean".
            report.add("GOV-002", "fail",
                       f"no reference enforcer for {language}: this assessment is unsupported, not clean",
                       "use the profile's native analyzer (for Java, ArchUnit) and report the result as "
                       "unsupported/partial; do not claim ACIMA conformance")
        else:
            command, cwd = enforcer_invocation(manifest, language, project, "acima.config.json")
            if language == "dotnet":
                prepare_dotnet(manifest)
            code, out, err = run(command, cwd)
            payload = None
            try:
                payload = json.loads(out)
            except json.JSONDecodeError:
                pass
            if code == 2:
                report.add("GOV-002", "fail",
                           f"enforcer failed to run: {(err or out).strip()[:300]}",
                           "fix the enforcer invocation before trusting any architecture claim")
            elif code == 127:
                report.add("GOV-002", "fail",
                           f"required toolchain {command[0]!r} is not installed; the "
                           "architecture was not measured",
                           "install the toolchain, then re-run the preflight; do not treat an "
                           "unmeasured repository as clean")
            elif payload is None:
                report.add("GOV-002", "fail", "enforcer returned invalid or truncated JSON",
                           "this is a tool failure, not an architecture result; keep the raw output")
            else:
                errors = validate_assessment(payload, code, manifest)
                if errors:
                    report.add("GOV-002", "fail",
                               "assessment is invalid: " + "; ".join(errors[:4]),
                               "fix or rerun the enforcer; do not count this run as a baseline")
                else:
                    findings = payload["findings"]
                    report.findings = {
                        "total": len(findings),
                        "errors": sum(1 for f in findings if f.get("severity") == "error"),
                        "byRule": _group(findings, "rule"),
                        "byPath": _group(findings, "path"),
                        "sourceFiles": payload["sourceFiles"],
                        "standard": payload["standard"],
                    }
                    if code == 1:
                        report.add("GOV-002", "warn",
                                   f"baseline is not clean: {len(findings)} finding(s), "
                                   f"{report.findings['errors']} error(s)",
                                   "this is expected on day one: waive deliberately, then ratchet")
                    else:
                        report.add("GOV-002", "pass", "baseline is clean at the declared level")
                        if not findings:
                            report.add("GOV-005", "warn",
                                       f"zero findings from {payload['sourceFiles']} source file(s); "
                                       "zero is not proof of conformance",
                                       "run scripts/inject_violation.py (L001 and D001) against this target before claiming clean")

        waiver_name = config.get("waivers")
        explicit_waivers = bool(waiver_name)
        waiver_name = waiver_name or ".acima/waivers.json"
        if waiver_name:
            waiver_path = project / waiver_name
            if not waiver_path.is_file() and explicit_waivers:
                report.add("GOV-003", "fail", f"waivers file missing: {waiver_name}",
                           "create it with an empty waivers array, or fix the path")
            elif not waiver_path.is_file():
                report.add("GOV-003", "pass", "no waiver file; no exceptions recorded")
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
                    scopes = {str(unit.get("id")) for unit in config.get("units", []) if unit.get("id")}
                    scopes |= {str(unit.get("module")) for unit in config.get("units", [])
                               if unit.get("module")}
                    validation = validate_waivers(document, valid_scopes=scopes)
                    if validation["invalid"]:
                        first = validation["invalid"][0]
                        detail = f"{len(validation['invalid'])} waiver(s) invalid"
                        if first.get("problems"):
                            detail += ": " + "; ".join(first["problems"])
                        report.add("GOV-003", "fail", detail,
                                   "G001 requires rule, scope, fingerprint, owner, reason, expires "
                                   "and reviewedOn; fingerprint is sha256:<64 hex>")
                    elif validation["expired"]:
                        report.add("GOV-003", "fail",
                                   f"{len(validation['expired'])} expired waiver(s)",
                                   "renew deliberately with the owner, or fix the violation")
                    elif validation["unowned"]:
                        report.add("GOV-003", "fail",
                                   f"{len(validation['unowned'])} waiver(s) still owned by 'unassigned'",
                                   "replace with real names before merging the gate")
                    else:
                        report.add("GOV-003", "pass",
                                   f"{len(validation['valid'])} active waiver(s), none expired")
                    if validation["scopeMismatch"]:
                        report.add("GOV-004", "warn",
                                   f"{len(validation['scopeMismatch'])} waiver(s) name a scope that "
                                   "no declared unit owns",
                                   "use 'repository' or a declared unit id/module")
    else:
        if (project / PROFILE_MANIFEST).is_file():
            report.add("TGT-006", "fail",
                       f"{PROFILE_MANIFEST} is present but acima.config.json is missing; "
                       "the mode cannot be selected",
                       "add acima.config.json with \"mode\": \"service-topology\" or remove the manifest")
        else:
            report.add("TGT-006", "pass", "architecture mode: base (no config or manifest)")
        if total == 0:
            report.mode = "greenfield"
            report.add("TGT-003", "pass",
                       "no config and no source files (mode: greenfield)")
        else:
            report.mode = "brownfield"
            report.add("TGT-003", "pass",
                       f"no config and {total} existing source file(s) (mode: brownfield)")

        report.proposed_units = propose_units(project, report.language)
        if report.proposed_units:
            report.add("TGT-004", "pass",
                       f"{len(report.proposed_units)} candidate unit(s) proposed from the layout")
        elif report.mode == "brownfield":
            report.add("TGT-004", "fail",
                       "no candidate units found for a source-bearing repository",
                       "complete the 55-requirement evidence-backed qualitative review before making an adoption recommendation. "
                       "Do not infer that ACIMA adds no value from the absence of candidate units. "
                       "If the review confirms no meaningful ownership boundaries or applicable benefit, "
                       "recommend against adoption; otherwise record owner-approved units separately.")
        else:
            report.add("TGT-004", "warn", "no candidate units found",
                       "declare units manually; ADR-0001 in the adoption plan explains the split")

        if report.mode == "brownfield":
            coverage = {"productionCovered": 0, "productionUncovered": [],
                        "testsExcluded": 0, "toolingExcluded": 0, "generatedExcluded": 0,
                        "fixturesExcluded": 0, "experimentalExcluded": 0,
                        "compositionExcluded": 0, "vendoredExcluded": 0,
                        "classifiedNonModule": 0}
            for path in walk_files(project):
                if path.suffix.lower() not in SOURCE_EXTENSIONS:
                    continue
                relative = path.relative_to(project).as_posix()
                classified = classify_path(relative)
                classification = classified["classification"]
                if classification == "tests":
                    coverage["testsExcluded"] += 1
                    continue
                if classification == "fixtures":
                    coverage["fixturesExcluded"] += 1
                    continue
                if classification == "experimental":
                    coverage["experimentalExcluded"] += 1
                    continue
                if classification in {"build-tooling", "architecture-tooling"}:
                    coverage["toolingExcluded"] += 1
                    continue
                if classification == "generated":
                    coverage["generatedExcluded"] += 1
                    continue
                if classification == "vendored":
                    coverage["vendoredExcluded"] += 1
                    continue
                if classification == "composition":
                    coverage["compositionExcluded"] += 1
                    continue
                if classification == "documentation-configuration":
                    coverage["classifiedNonModule"] += 1
                    continue
                if unit_for_path(relative, report.proposed_units) is not None:
                    coverage["productionCovered"] += 1
                else:
                    coverage["productionUncovered"].append(relative)
            report.source_coverage = coverage
            uncovered = len(coverage["productionUncovered"])
            excluded = (coverage["testsExcluded"] + coverage["toolingExcluded"] +
                        coverage["generatedExcluded"] + coverage["fixturesExcluded"] +
                        coverage["experimentalExcluded"] + coverage["compositionExcluded"] +
                        coverage["vendoredExcluded"] + coverage["classifiedNonModule"])
            if uncovered:
                report.add("TGT-005", "warn",
                           f"{uncovered} production source file(s) fall outside candidate units "
                           "and explicit repository classifications; "
                           f"{coverage['testsExcluded']} test, {coverage['toolingExcluded']} tooling, "
                           f"{coverage['fixturesExcluded']} fixture, "
                           f"{coverage['experimentalExcluded']} experimental, "
                           f"{coverage['compositionExcluded']} composition, "
                           f"{coverage['generatedExcluded']} generated, "
                           f"{coverage['vendoredExcluded']} vendored and "
                           f"{coverage['classifiedNonModule']} other non-module file(s) are "
                           "separately classified outside module ownership coverage",
                           "review the unresolved production paths and assign each to a module "
                           "or an explicit non-module disposition; do not use directory proximity")
            else:
                report.add("TGT-005", "pass",
                           f"all {coverage['productionCovered']} production source files are covered; "
                           f"{excluded} test/tooling/fixture/composition/other files are explicitly "
                           "classified outside module ownership coverage")
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
        executable = enforcer["run"][0]
        python_enforcer = Path(executable).stem.lower() in {"python", "python3"}
        if not python_enforcer and shutil_module.which(executable) is None:
            report.add(f"ENF-{language}", "skip", f"{language}: {executable} not installed")
            continue
        example = enforcer.get("example")
        if not example:
            continue
        if not (STANDARD_ROOT / example / "acima.config.json").is_file():
            report.add(f"ENF-{language}", "warn",
                       f"{language}: example tree is not bundled; run --deep from a checkout")
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
            payload = json.loads(out)
        except json.JSONDecodeError:
            report.add(f"ENF-{language}", "fail", f"{language} enforcer returned invalid JSON",
                       "tool failure: do not use it as a reference")
            continue
        errors = validate_assessment(payload, code, manifest)
        if errors:
            report.add(f"ENF-{language}", "fail",
                       f"{language} example assessment is invalid: {'; '.join(errors[:3])}",
                       "fix the enforcer and its output contract before using it as a reference")
            continue
        findings = payload["findings"]
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

    proposal = (report.module_map or {}).get("proposal") or {}
    if proposal:
        steps.insert(0, "Review the proposed module map, its evidence and recommendations; "
                        "accept, modify, reject or defer individual decisions before relying on "
                        "inferred ownership. No map was made authoritative.")
    if report.mode == "greenfield":
        steps = [
            "Review the proposed units and present the adoption proposal; do not scaffold until approved.",
            "If approved, create the first two contracts with their own value types, then implementations.",
            "If approved, write acima.config.json and an empty waiver file in the same commit.",
            "If CI is approved, wire the enforcer in before the second module exists; declare the approved level.",
            "Read references/10-greenfield.md for the exact skeleton.",
        ]
    elif report.mode == "brownfield":
        if draft_path and (project / draft_path).is_file():
            steps.append(f"Review the draft at {draft_path}: rename units to domain concepts, then commit it.")
            steps.append("If baseline and gate are approved, measure the run and write scoped waivers with owners.")
        elif not (project / "acima.config.json").is_file():
            steps.append("Review the proposed units and present the adoption proposal; no files were written.")
            steps.append("If configuration is approved: --write-draft acima.config.json, then review it.")
        if waiver_path and (project / waiver_path).is_file():
            steps.append(f"Replace every 'unassigned' owner in {waiver_path} before merging the gate.")
        steps.extend([
            "If integration blocking is approved, gate CI on 'no new findings' at the declared level.",
            "Pick the first approved slice from references/20-brownfield.md (contracts, not persistence).",
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
    parser.add_argument("--automation-mode", choices=["guided", "full"], default=None,
                        help="explicitly choose guided adoption or full automation for this engagement")
    parser.add_argument("--authorize-full-automation", action="store_true",
                        dest="authorize_full_automation",
                        help="required with --automation-mode full; authorizes routine implementation steps")
    args = parser.parse_args()
    if args.authorize_full_automation and args.automation_mode != "full":
        print("acima: --authorize-full-automation requires --automation-mode full", file=sys.stderr)
        return 2
    if args.automation_mode == "full" and not args.authorize_full_automation:
        print("acima: full automation requires --authorize-full-automation; no write was made",
              file=sys.stderr)
        return 2

    manifest_path = Path(args.manifest).resolve()
    project = Path(args.project).resolve()
    report = Report()
    report.automation = {
        "mode": args.automation_mode,
        "fullAutomationAuthorized": bool(args.authorize_full_automation),
        "meaning": ("Explicit authorization to apply routine adoption steps inside the target; "
                    "deployment, release, commit and push remain separately unauthorized."
                    if args.automation_mode == "full" else
                    "Guided adoption: generate artifacts and wait for explicit approval before consequential changes."
                    if args.automation_mode == "guided" else
                    "No automation mode selected; assessment remains read-only."),
    }

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
    try:
        report.module_map = discover_module_map(project, config=config)
    except (ModuleMapError, OSError) as error:
        report.add("MMP-001", "warn", f"module-map discovery did not complete: {error}",
                   "complete discovery manually; do not infer ownership from the failure")

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
                        "architectureMode": report.architecture_mode,
                        "profile": report.profile,
                        "language": report.language,
                        "detectedLanguages": report.detected_languages},
            "sourceCoverage": report.source_coverage,
            "checks": [check.__dict__ for check in report.checks],
            "blockers": [check.id for check in report.blockers],
            "warnings": [check.id for check in report.warnings],
            "findings": report.findings,
            "proposedUnits": units,
            "moduleMap": report.module_map,
            "automation": report.automation,
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
    print(f"  mode     {report.mode} · architecture {report.architecture_mode} · "
          f"language {report.language}")
    if report.automation.get("mode"):
        print(f"  workflow guided={report.automation['mode'] == 'guided'} · "
              f"full automation authorized={report.automation.get('fullAutomationAuthorized', False)}")
    print()
    for check in report.checks:
        print(f"  {symbols.get(check.status, '?   ')}{check.id:<8} {check.detail}")
        if check.status in ("fail", "warn") and check.remedy:
            print(f"          -> {check.remedy}")

    module_map = report.module_map or {}
    if module_map:
        print()
        authority = module_map.get("authoritativeMap") or {}
        print(f"  module map  {authority.get('status', 'not established')} · "
              f"{authority.get('summary', 'No summary recorded.')}")
        proposal = module_map.get("proposal") or {}
        if proposal:
            print(f"  proposal    {len(proposal.get('modules', []))} candidate module(s), "
                  f"{len(proposal.get('recommendations', []))} recommendation(s), "
                  f"{len(proposal.get('unassigned', []))} unassigned path(s) — review required")

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
