"""Evidence-backed module-map discovery, proposal and approval.

The proposal is an assessment artefact. It never becomes authoritative merely because
discovery succeeded: a reviewer must accept, modify, reject or defer the proposal (or
individual boundaries, repository-path dispositions and recommendations). An approved map
is then converted to the existing ``acima.config.json`` unit contract, which the enforcers
already understand.

This module is deliberately shared by the adoption skill and the developer CLI so a
proposal cannot drift between the two entry points.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

CONFIG_NAME = "acima.config.json"
APPROVAL_FILE = ".acima/module-map.approval.json"
SCHEMA_VERSION = "1.0"
SOURCE_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".mjs", ".cjs", ".cs", ".go", ".java",
    ".kt", ".rs", ".rb", ".php", ".scala", ".swift",
}
PRUNE = {
    ".git", "node_modules", "bin", "obj", "dist", "build", "target", "out",
    ".venv", "venv", "__pycache__", ".next", ".nuxt", "coverage", ".idea", ".vs",
    ".acima",
    # Generated vendor content is not product source. A copied skill carries its
    # dependency snapshot here; assigning it an application module would be false ownership.
    "vendor",
}
BASES = ("src", "internal", "packages", "app", "apps", "services", "lib", "modules")
CONTRACT_NAMES = {"contracts", "contract", "api", "ports", "port", "public"}
IGNORED_LAYOUT = {
    "test", "tests", "__tests__", "spec", "specs", "e2e", "docs", "doc",
    "examples", "example", "tools", "scripts", "migrations", "benchmarks",
    "fixtures", "fixture", "testdata", "test-data", "spikes", "spike",
    "experimental", "experiments", "generated", "vendor", "vendored",
    "third_party", "third-party",
}
DECISIONS = {"accept", "modify", "reject", "defer"}
PATH_DECISIONS = {"accept", "modify", "reject", "defer"}
ESSENTIAL_RECOMMENDATION_CLASSES = {"required", "owner-decision"}
OWNERSHIP_DEPENDENT_RULES = {
    "ACIMA-D001", "ACIMA-D002", "ACIMA-D003", "ACIMA-D004", "ACIMA-D005",
    "ACIMA-D008", "ACIMA-D009", "ACIMA-D010", "ACIMA-D013", "ACIMA-D014",
    "ACIMA-D015", "ACIMA-D016", "ACIMA-L001", "ACIMA-L002", "ACIMA-L003",
    "ACIMA-A007", "ACIMA-A008", "ACIMA-A009",
}

# These are discovery classifications, not automatically ACIMA modules.
CLASSIFICATIONS = {
    "owned-implementation": "Production implementation owned by an identified module.",
    "public-contract": "Public contract owned by an identified module.",
    "shared-infrastructure": "Shared infrastructure with an explicit ownership model.",
    "composition": "Composition host or composition-specific wiring.",
    "build-tooling": "Build, packaging or development tooling.",
    "architecture-tooling": "Architecture enforcement, gate or analysis tooling.",
    "tests": "Tests and test infrastructure.",
    "fixtures": "Fixtures and deliberately invalid examples.",
    "experimental": "Experimental or spike code not in the production architecture.",
    "generated": "Generated source that should not be hand-edited.",
    "vendored": "Vendored or third-party source.",
    "documentation-configuration": "Documentation and non-architecture configuration.",
    "unresolved-production": "Production implementation whose ownership is not established.",
}
MODULE_CLASSIFICATIONS = {"owned-implementation", "public-contract"}
NON_MODULE_CLASSIFICATIONS = set(CLASSIFICATIONS) - MODULE_CLASSIFICATIONS - {"unresolved-production"}
RESOLVED_NON_MODULE = NON_MODULE_CLASSIFICATIONS
UNIT_ROLES = {"implementation", "contracts", "shared", "port", "adapter", "host", "tooling"}


class ModuleMapError(ValueError):
    """A proposal or review cannot be trusted."""


def _walk(root: Path):
    """Yield files under root without descending into pruned directories.

    ``Path.rglob`` cannot prune: it descends into ``.git``, ``node_modules`` and build output
    before the caller can reject the result. A top-down walk lets us remove those directories
    from ``dirnames`` before descent, which keeps discovery bounded on real repositories.
    """
    for current, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            name for name in dirnames
            if name not in PRUNE and (not name.startswith(".") or name == ".acima")
        )
        for name in sorted(filenames):
            if name.startswith("."):
                continue
            path = Path(current) / name
            if path.is_file():
                yield path


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _is_test(path: Path) -> bool:
    parts = [part.lower() for part in path.parts]
    name = path.name.lower()
    return (any(part in {"test", "tests", "__tests__", "spec", "specs", "e2e"} or
                part.endswith((".test", ".tests", ".spec", ".specs")) for part in parts)
            or any(name.endswith(suffix) for suffix in
                   (".test.ts", ".test.tsx", ".test.js", ".test.jsx",
                    ".spec.ts", ".spec.tsx", ".spec.js", ".spec.jsx")))


def _is_fixture(path: Path) -> bool:
    parts = [part.lower() for part in path.parts]
    return any(part in {"fixture", "fixtures", "testdata", "test-data", "testcases",
                        "test-cases", "violations", "gallery"} for part in parts)


def _is_experimental(path: Path) -> bool:
    parts = [part.lower() for part in path.parts]
    return any(part in {"spike", "spikes", "experimental", "experiments", "prototype",
                        "prototypes", "playground", "sandbox"} for part in parts)


def _is_generated(path: Path) -> bool:
    name = path.name.lower()
    parts = [part.lower() for part in path.parts]
    return (name.endswith((".g.cs", ".generated.cs", ".designer.cs"))
            or ".generated." in name or "generated" in parts)


def _is_vendored(path: Path) -> bool:
    parts = [part.lower() for part in path.parts]
    return any(part in {"vendor", "vendored", "third_party", "third-party",
                        "external", "extern"} for part in parts)


def _is_architecture_tooling(path: Path) -> bool:
    name = path.name.lower()
    parts = [part.lower() for part in path.parts]
    return (any(part in {"arch", "architecture", "architecturetests", "archtests"} for part in parts)
            and any(part in {"tools", "scripts", "tests"} for part in parts)) or \
        name in {"architecture-gate.mjs", "architecture-map.mjs", "architecture-analyzers.mjs"}


def _is_tooling(path: Path) -> bool:
    name = path.name.lower()
    parts = [part.lower() for part in path.parts]
    return (any(part in {"tools", "scripts", "build-tools", "coverage-tools",
                         "license-tools", "devtools"} for part in parts)
            or name.startswith(("eslint.config.", "vite.config.", "vitest.config.",
                                "playwright.config.", "tsconfig."))
            or name in {"vite-env.d.ts", "setup.py", "setup.cfg"})


def _is_documentation(path: Path) -> bool:
    parts = [part.lower() for part in path.parts]
    return any(part in {"docs", "doc", "documentation"} for part in parts)


def _is_composition(path: Path) -> bool:
    parts = [part.lower() for part in path.parts]
    return any(part in {"host", "hosts", "composition", "bootstrap"} for part in parts)


def classify_path(relative: str) -> dict:
    """Classify a repository-relative path without making it a module."""
    path = Path(relative)
    if _is_generated(path):
        return {"classification": "generated", "confidence": "high",
                "reason": "The file name or containing path identifies generated source."}
    if _is_vendored(path):
        return {"classification": "vendored", "confidence": "high",
                "reason": "The containing path identifies vendored or third-party source."}
    if _is_fixture(path):
        return {"classification": "fixtures", "confidence": "high",
                "reason": "The containing path identifies fixtures or deliberately invalid examples."}
    if _is_test(path):
        return {"classification": "tests", "confidence": "high",
                "reason": "The file or containing project is test infrastructure."}
    if _is_experimental(path):
        return {"classification": "experimental", "confidence": "high",
                "reason": "The containing path identifies experimental or spike code."}
    if _is_architecture_tooling(path):
        return {"classification": "architecture-tooling", "confidence": "high",
                "reason": "The path contains architecture analysis, tests or gate tooling."}
    if _is_tooling(path):
        return {"classification": "build-tooling", "confidence": "high",
                "reason": "The path is build, packaging or development tooling."}
    if _is_documentation(path):
        return {"classification": "documentation-configuration", "confidence": "high",
                "reason": "The path is documentation or non-architecture configuration."}
    if _is_composition(path):
        return {"classification": "composition", "confidence": "medium",
                "reason": "The path is a conventional composition or process entry point; "
                          "the owner should confirm the host boundary."}
    return {"classification": "unresolved-production", "confidence": "low",
            "reason": "No architectural ownership or non-module role is established by the "
                      "available repository evidence."}


def _disposition_group(relative: str, classification: str) -> str:
    """Group routine non-module files into a coherent path decision."""
    if classification == "unresolved-production":
        return relative
    parts = list(PurePosixPath(relative).parts)
    markers = {
        "tests": {"test", "tests", "__tests__", "spec", "specs", "e2e"},
        "fixtures": {"fixture", "fixtures", "testdata", "test-data", "testcases",
                     "test-cases", "violations", "gallery"},
        "experimental": {"spike", "spikes", "experimental", "experiments", "prototype",
                         "prototypes", "playground", "sandbox"},
        "build-tooling": {"tools", "scripts", "build-tools", "coverage-tools",
                          "license-tools", "devtools"},
        "architecture-tooling": {"arch", "architecture", "architecturetests", "archtests"},
        "documentation-configuration": {"docs", "doc", "documentation"},
        "generated": {"generated", "obj", "bin"},
        "vendored": {"vendor", "vendored", "third_party", "third-party", "external", "extern"},
    }.get(classification, set())
    cut = None
    for index, part in enumerate(parts[:-1]):
        lowered = part.lower()
        if lowered in markers or lowered.endswith((".tests", ".test", ".spec", ".specs")):
            cut = index + 1
            break
    if cut is None:
        cut = max(1, len(parts) - 1)
    return PurePosixPath(*parts[:cut]).as_posix()


def _source_files(root: Path) -> list[Path]:
    return [path for path in _walk(root) if path.suffix.lower() in SOURCE_EXTENSIONS]


def _production_files(root: Path) -> list[Path]:
    """Source that is not already identified as non-production by path evidence."""
    return [path for path in _source_files(root)
            if classify_path(_relative(path, root))["classification"] == "unresolved-production"]


def _read_config(root: Path) -> tuple[dict | None, str | None]:
    path = root / CONFIG_NAME
    if not path.is_file():
        return None, None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return None, f"{CONFIG_NAME} cannot be read: {error}"
    if not isinstance(value, dict):
        return None, f"{CONFIG_NAME} is not a JSON object"
    return value, None


def _line_evidence(root: Path, relative: str, line: int, observation: str,
                   kind: str = "source") -> dict:
    path = root / relative
    quote = ""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        if lines:
            line = max(1, min(line, len(lines)))
            quote = lines[line - 1].strip()
    except (OSError, UnicodeError):
        pass
    item = {"kind": kind, "path": relative, "startLine": line, "endLine": line,
            "observation": observation, "classification": "observed"}
    if quote:
        item["quote"] = quote[:240]
    return item


def _first_source_evidence(root: Path, directory: Path,
                           observation: str) -> dict | None:
    for path in sorted(_walk(directory)):
        if path.suffix.lower() in SOURCE_EXTENSIONS:
            relative = _relative(path, root)
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeError):
                continue
            for number, line in enumerate(lines, start=1):
                if line.strip():
                    return _line_evidence(root, relative, number, observation)
    return None


def _module_name(path: Path) -> str:
    stem = path.name
    if stem.lower().endswith(".contracts"):
        stem = stem[:-len(".contracts")]
    if stem.lower().endswith(".contract"):
        stem = stem[:-len(".contract")]
    words = re.sub(r"[^A-Za-z0-9]+", " ", stem).strip().split()
    return " ".join(word[:1].upper() + word[1:] for word in words) or stem


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug or "module"


def _module_id(relative: str) -> str:
    name = Path(relative).name
    if name.lower().endswith(".contracts"):
        name = name[:-len(".contracts")]
    elif name.lower().endswith(".contract"):
        name = name[:-len(".contract")]
    return _slug(name)


def _unique_modules(modules: list[dict]) -> list[dict]:
    """Make IDs stable and unique, even when the repository repeats a leaf name."""
    used: dict[str, int] = {}
    for module in sorted(modules, key=lambda item: item.get("id", "")):
        base = _slug(str(module.get("id") or module.get("name") or "module"))
        used[base] = used.get(base, 0) + 1
        if used[base] > 1:
            suffix = _slug(module.get("implementation", {}).get("paths", ["module"])[0]
                           if module.get("implementation", {}).get("paths") else str(used[base]))
            candidate = f"{base}-{suffix}"
            counter = 2
            while candidate in used:
                candidate = f"{base}-{suffix}-{counter}"
                counter += 1
            used[candidate] = 1
            module["id"] = candidate
        else:
            module["id"] = base
    return modules


def _candidate_paths(root: Path) -> dict[str, dict]:
    """Return layout candidates. These are signals, never approved ownership."""
    candidates: dict[str, dict] = {}

    def add(directory: Path, *, manifest: str | None = None) -> None:
        try:
            relative = _relative(directory, root)
        except ValueError:
            return
        if not relative or relative == "." or any(
                part in PRUNE or part.startswith(".") for part in PurePosixPath(relative).parts):
            return
        classification = classify_path(relative)
        if classification["classification"] != "unresolved-production":
            return
        # A container that groups projects is not itself a module. Its children have
        # their own manifests and must be discovered independently.
        if manifest is None and any(
                candidate.parent != directory
                for candidate in _walk(directory)
                if any(candidate.match(pattern) for pattern in
                       ("*.csproj", "package.json", "pyproject.toml", "go.mod"))):
            return
        if not any(path.suffix.lower() in SOURCE_EXTENSIONS for path in _walk(directory)):
            return
        item = candidates.setdefault(relative, {"paths": [relative], "manifests": []})
        if manifest and manifest not in item["manifests"]:
            item["manifests"].append(manifest)

    # Project/package manifests are strong layout signals, but still not ownership proof.
    manifest_patterns = ("*.csproj", "package.json", "pyproject.toml", "setup.py",
                         "setup.cfg", "go.mod")
    for manifest in sorted(_walk(root)):
        if not any(manifest.match(pattern) for pattern in manifest_patterns):
            continue
        directory = manifest.parent
        if _is_test(directory.relative_to(root)):
            continue
        add(directory, manifest=_relative(manifest, root))

    for base_name in BASES:
        base = root / base_name
        if not base.is_dir():
            continue
        # Descend a single namespace wrapper such as src/acme/orders.
        while base.is_dir() and not any(path.is_file() and path.suffix.lower() in SOURCE_EXTENSIONS
                                        for path in base.iterdir()):
            children = [child for child in sorted(base.iterdir())
                        if child.is_dir() and child.name not in PRUNE
                        and not child.name.startswith(".")
                        and child.name.lower() not in IGNORED_LAYOUT]
            if len(children) != 1:
                break
            base = children[0]
        for child in sorted(base.iterdir()):
            if (not child.is_dir() or child.name in PRUNE or child.name.startswith(".")
                    or child.name.lower() in IGNORED_LAYOUT):
                continue
            add(child)

    # Merge implementation and sibling contracts projects into one candidate module.
    for relative in list(candidates):
        path = root / relative
        if path.name.lower().endswith(".contracts"):
            parent = relative.rsplit("/", 1)[0] if "/" in relative else ""
            stem = path.name[:-len(".contracts")]
            nested = f"{parent}/{stem}" if parent else stem
            implementation = next((item for item in (nested, parent)
                                   if item in candidates and (root / item).is_dir()), None)
            if implementation:
                target = candidates[implementation]
                if relative not in target["paths"]:
                    target["paths"].append(relative)
                target["manifests"].extend(candidates[relative].get("manifests", []))
                target["manifests"] = sorted(set(target["manifests"]))
                del candidates[relative]
    return dict(sorted(candidates.items()))


def _contract_paths(root: Path, directory: Path) -> list[str]:
    found = []
    for child in sorted(directory.iterdir()):
        if child.is_dir() and child.name.lower() in CONTRACT_NAMES:
            if any(item.suffix.lower() in SOURCE_EXTENSIONS for item in _walk(child)):
                found.append(_relative(child, root))
    return sorted(set(found))


def _module_for(path: str, modules: list[dict]) -> dict | None:
    best, best_length = None, -1
    for module in modules:
        for prefix in module["implementation"]["paths"] + module["contracts"]["paths"]:
            clean = prefix.rstrip("/")
            if (path == clean or path.startswith(clean + "/")) and len(clean) > best_length:
                best, best_length = module, len(clean)
    return best


def _import_evidence(root: Path, module: dict, modules: list[dict]) -> list[dict]:
    dependencies: dict[str, dict] = {}
    for prefix in module["implementation"]["paths"] + module["contracts"]["paths"]:
        directory = root / prefix
        files = [directory] if directory.is_file() else sorted(_walk(directory))
        for path in files:
            if not path.is_file() or path.suffix.lower() not in SOURCE_EXTENSIONS:
                continue
            relative = _relative(path, root)
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeError):
                continue
            for number, line in enumerate(lines, start=1):
                stripped = line.strip()
                if not re.match(r"^(import|from|using|require|export .* from)\b", stripped):
                    continue
                for other in modules:
                    if other["id"] == module["id"]:
                        continue
                    names = {other["name"], _slug(other["name"]), other["id"]}
                    if not any(re.search(rf"(?<![A-Za-z0-9_-]){re.escape(name)}(?![A-Za-z0-9_-])",
                                         stripped, re.I) for name in names if name):
                        continue
                    leak = bool(re.search(r"(^|[./\\])(impl|internal|private)([./\\]|$)",
                                          stripped, re.I))
                    item = dependencies.setdefault(other["id"], {
                        "module": other["name"], "moduleId": other["id"], "imports": [],
                        "leaksImplementation": False, "evidence": [],
                    })
                    item["leaksImplementation"] = item["leaksImplementation"] or leak
                    item["imports"].append({"path": relative, "line": number,
                                            "text": stripped[:240]})
                    item["evidence"].append(_line_evidence(
                        root, relative, number,
                        "The candidate imports a name associated with "
                        f"{other['name']}; this is dependency evidence, not an ownership decision."))
    return sorted(dependencies.values(), key=lambda item: item["module"])


def _cycle_nodes(graph: dict[str, set[str]]) -> list[list[str]]:
    cycles: set[tuple[str, ...]] = set()
    visiting: list[str] = []
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            start = visiting.index(node)
            cycle = visiting[start:]
            if len(cycle) > 1:
                rotations = [tuple(cycle[i:] + cycle[:i]) for i in range(len(cycle))]
                cycles.add(min(rotations))
            return
        if node in visited:
            return
        visiting.append(node)
        for child in sorted(graph.get(node, set())):
            visit(child)
        visiting.pop()
        visited.add(node)

    for node in sorted(graph):
        visit(node)
    return [list(cycle) for cycle in sorted(cycles)]


def _unit_issue(unit: dict, root: Path, seen_ids: set[str]) -> str | None:
    unit_id = unit.get("id")
    if not isinstance(unit_id, str) or not unit_id.strip():
        return "A declared unit has no id."
    if unit_id in seen_ids:
        return f"Unit id {unit_id!r} is declared more than once."
    if unit.get("role") not in UNIT_ROLES:
        return f"Unit {unit_id!r} has unsupported role {unit.get('role')!r}."
    paths = unit.get("paths")
    if not isinstance(paths, list) or not paths:
        return f"Unit {unit_id!r} declares no paths."
    for raw in paths:
        if not isinstance(raw, str) or not raw.strip():
            return f"Unit {unit_id!r} has an empty path."
        candidate = PurePosixPath(raw.replace("\\", "/"))
        if candidate.is_absolute() or ".." in candidate.parts:
            return f"Unit {unit_id!r} path {raw!r} escapes the repository."
        if not (root / Path(*candidate.parts)).exists():
            return f"Unit {unit_id!r} path {raw!r} does not exist."
    return None


def _path_matches(relative: str, prefix: str) -> bool:
    clean = prefix.rstrip("/")
    return relative == clean or relative.startswith(clean + "/")


def _config_dispositions(config: dict | None) -> list[dict]:
    raw = (config or {}).get("repositoryDispositions")
    if not isinstance(raw, list):
        return []
    result = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        paths = item.get("paths")
        if not isinstance(paths, list):
            paths = [item.get("path")] if item.get("path") else []
        paths = [path for path in paths if isinstance(path, str) and path]
        classification = item.get("classification")
        if not paths or classification not in NON_MODULE_CLASSIFICATIONS:
            continue
        result.append({"paths": paths, "classification": classification,
                       "reason": item.get("reason") or "Declared by the existing map.",
                       "confidence": item.get("confidence") or "high",
                       "owner": item.get("owner") or ""})
    return result


def _authoritative_review(root: Path, config: dict | None, source: list[Path]) -> dict:
    units = (config or {}).get("units") or []
    dispositions = _config_dispositions(config)
    issues: list[dict] = []
    seen_ids: set[str] = set()
    paths: list[tuple[str, str, str]] = []
    for index, unit in enumerate(units if isinstance(units, list) else []):
        if not isinstance(unit, dict):
            issues.append({"code": "invalid-unit", "detail": f"Unit {index} is not an object."})
            continue
        problem = _unit_issue(unit, root, seen_ids)
        if problem:
            issues.append({"code": "invalid-unit", "detail": problem})
        if isinstance(unit.get("id"), str):
            seen_ids.add(unit["id"])
        for raw in unit.get("paths", []) if isinstance(unit.get("paths"), list) else []:
            if isinstance(raw, str):
                paths.append((str(unit.get("module") or unit.get("id", "?")),
                              str(unit.get("id", "?")), raw.rstrip("/")))
    for i, (left_module, left_id, left) in enumerate(paths):
        for right_module, right_id, right in paths[i + 1:]:
            if left_id == right_id or left_module == right_module:
                continue
            if left == right or left.startswith(right + "/") or right.startswith(left + "/"):
                issues.append({"code": "overlap",
                               "detail": f"Units {left_id!r} and {right_id!r} claim overlapping paths "
                                         f"({left!r}, {right!r})."})
    covered = []
    classified = []
    unowned = []
    for path in source:
        relative = _relative(path, root)
        if any(_path_matches(relative, prefix) for _, _, prefix in paths):
            covered.append(relative)
        elif any(_path_matches(relative, prefix) for item in dispositions for prefix in item["paths"]):
            classified.append(relative)
        else:
            unowned.append(relative)
    if config is None:
        status = "absent"
        summary = "No authoritative module map is declared."
    elif issues:
        status = "inconsistent"
        summary = "The declared module map has structural inconsistencies."
    elif not paths:
        status = "incomplete"
        summary = "The declared map contains no usable unit paths."
    elif len(covered) == 0 and source:
        status = "stale"
        summary = "The declared unit paths do not cover any current production source."
    elif unowned:
        status = "incomplete"
        summary = f"{len(unowned)} source file(s) are not covered by a module or an explicit disposition."
    else:
        status = "complete"
        summary = ("The declared module map covers all relevant source with module ownership or "
                   "an explicit non-module disposition and is structurally consistent.")
    if status != "complete" and unowned:
        issues.append({"code": "unowned-source",
                       "detail": f"{len(unowned)} source file(s) are outside declared units and dispositions."})
    return {
        "present": config is not None,
        "path": CONFIG_NAME if config is not None else None,
        "status": status,
        "summary": summary,
        "unitCount": len(units) if isinstance(units, list) else 0,
        "modules": sorted({str(unit.get("module")) for unit in units
                           if isinstance(unit, dict) and unit.get("module")}),
        "coveredProduction": len(covered),
        "classifiedNonModule": len(classified),
        "productionFiles": len(source),
        "issues": issues,
        "unownedPaths": unowned,
        "units": units if isinstance(units, list) else [],
        "dispositions": dispositions,
        "classification": "observed" if config is not None else "absence",
        "approvalProvenance": (
            (config or {}).get("_moduleMapApproval")
            if isinstance((config or {}).get("_moduleMapApproval"), dict) else None
        ),
    }


def _recommendation(identifier: str, title: str, observed: str, evidence: list[dict],
                    why: str, change: str, benefit: str, risk: str,
                    classification: str = "required", affected: list[str] | None = None,
                    requires_user: bool = True) -> dict:
    return {
        "id": identifier,
        "title": title,
        "observed": observed,
        "evidence": evidence,
        "whyItMatters": why,
        "recommendation": change,
        "benefit": benefit,
        "risk": risk,
        "uncertainty": ("The recommendation is based on static repository evidence; the owner "
                        "must confirm the intended responsibility and any runtime ownership."),
        "classification": classification,
        "essential": classification in ESSENTIAL_RECOMMENDATION_CLASSES,
        "requiresUserInput": requires_user,
        "affectedModules": affected or [],
        "affectedFiles": [],
        "changes": [],
        "decision": "pending",
    }


def _build_modules(root: Path, candidates: dict[str, dict]) -> list[dict]:
    modules: list[dict] = []
    for relative, candidate in candidates.items():
        directory = root / relative
        contract_only = directory.name.lower().endswith((".contracts", ".contract"))
        name = _module_name(directory)
        candidate_paths = [path for path in candidate.get("paths", []) if path]
        contracts = [path for path in candidate_paths
                     if Path(path).name.lower().endswith((".contracts", ".contract"))]
        if contract_only:
            contracts = [relative]
        elif not contracts:
            contracts = _contract_paths(root, directory)
        implementation_paths = [] if contract_only else [
            path for path in candidate_paths if path not in contracts]
        evidence = []
        first = _first_source_evidence(
            root, directory,
            "Production source was observed under this candidate area; it supports a layout "
            "boundary, not an approved ownership decision.")
        if first:
            evidence.append(first)
        for manifest in candidate.get("manifests", []):
            if (root / manifest).is_file():
                evidence.append(_line_evidence(
                    root, manifest, 1,
                    "A project or package manifest locates this candidate; the manifest is not "
                    "proof that the project is an ACIMA module.", kind="configuration"))
        if not evidence and contracts:
            evidence.append(_line_evidence(root, contracts[0], 1,
                                           "A contract-shaped area was observed."))
        module_id = _module_id(relative)
        modules.append({
            "id": module_id,
            "name": name,
            "status": "candidate",
            "ownership": "inferred",
            "confidence": "medium" if candidate.get("manifests") else "low",
            "responsibility": (f"Observed production code under `{relative}`. Its responsibility "
                               "is inferred only from repository structure and requires owner "
                               "confirmation."),
            "implementation": {"paths": implementation_paths,
                               "classification": "observed-layout"},
            "contracts": {"paths": contracts,
                          "classification": "observed" if contracts else "not-identified"},
            "dependencies": [],
            "dataAndConfiguration": [],
            "entryPoints": [],
            "compositionResponsibilities": [],
            "evidence": evidence,
            "limitations": ("The boundary is a discovery candidate. It does not establish ownership, "
                            "deployment independence or a public contract."),
        })
    return _unique_modules(modules)


def _module_paths(modules: list[dict]) -> list[str]:
    return [prefix for module in modules
            for prefix in module.get("implementation", {}).get("paths", []) +
            module.get("contracts", {}).get("paths", [])]


def _quality_and_recommendations(root: Path, modules: list[dict], unresolved: list[str],
                                 authoritative: dict, dispositions: list[dict]) -> tuple[dict, list[dict]]:
    graph = {module["id"]: set() for module in modules}
    for module in modules:
        for dependency in module.get("dependencies", []):
            graph[module["id"]].add(dependency["moduleId"])
    cycles = _cycle_nodes(graph)
    observations = []
    if modules:
        observations.append({
            "topic": "responsibility coherence",
            "observation": "Each candidate has one observed production area; no semantic business "
                           "responsibility was inferred from its name.",
            "confidence": "low",
            "basis": "inference",
        })
    observations.append({
        "topic": "contract separation",
        "observation": (f"{sum(bool(module['contracts']['paths']) for module in modules)} of "
                        f"{len(modules)} candidates contain an identified contract-shaped path."),
        "confidence": "medium",
        "basis": "observed",
    })
    observations.append({
        "topic": "repository classification",
        "observation": (f"{sum(len(item['paths']) for item in dispositions)} non-module path group(s) "
                        f"and {len(unresolved)} unresolved production file(s) were identified."),
        "confidence": "medium",
        "basis": "observed",
    })
    observations.append({
        "topic": "dependency cycle",
        "observation": ("No candidate dependency cycle was found in observed import lines."
                        if not cycles else
                        "Candidate dependency cycles were found: " +
                        "; ".join(" -> ".join(cycle) for cycle in cycles) + "."),
        "confidence": "medium",
        "basis": "observed",
    })
    recommendations: list[dict] = []
    counter = 1

    def add(*args, **kwargs):
        nonlocal counter
        recommendations.append(_recommendation(f"MMR-{counter:03d}", *args, **kwargs))
        counter += 1

    if unresolved:
        add("Unassigned production code",
            f"{len(unresolved)} source file(s) have no established module or non-module role.",
            [_line_evidence(root, unresolved[0], 1,
                            "The file was inspected and no ownership classification was established.")],
            "ACIMA cannot assign a boundary it cannot identify. Leaving these files unresolved "
            "makes ownership-dependent checks incomplete or misleading.",
            "Assign each path to an accepted module, classify it as an explicit non-module role, "
            "or record why it is excluded. Do not assign it by directory proximity alone.",
            "Every production file has a deliberate owner or an explicit reviewed exclusion.",
            "Assignment may reveal a responsibility not represented by the current candidates; "
            "that may require a new boundary or consolidation.",
            classification="required", affected=[], requires_user=True)
        recommendations[-1]["affectedFiles"] = unresolved[:25]
    if authoritative["status"] in {"incomplete", "inconsistent", "stale"}:
        add("Complete the existing module map",
            authoritative["summary"],
            [], "A partial or inconsistent map cannot support deterministic ownership checks for "
            "the unrepresented source.",
            "Preserve the existing units, review the proposed additions, and resolve overlaps or "
            "stale paths before treating the map as authoritative.",
            "Checks can run over a complete, deliberate ownership model instead of silently "
            "ignoring unowned code.",
            "An existing boundary may be intentional. Do not replace it merely to make the "
            "proposal uniform.",
            classification="required", affected=authoritative["modules"], requires_user=True)
    for cycle in cycles:
        add("Resolve a candidate dependency cycle",
            "Observed imports form a cycle among " + ", ".join(cycle) + ".",
            [item for module in modules if module["id"] in cycle
             for dependency in module["dependencies"]
             if dependency["moduleId"] in cycle for item in dependency["evidence"]],
            "ACIMA modules must remain independently changeable and dependencies must follow "
            "explicit contracts, not circular implementation coupling.",
            "Decide whether these candidates own separate responsibilities, then break the cycle "
            "through a contract, an inversion of ownership, or a justified consolidation.",
            "The resulting direction is executable and the module graph is acyclic.",
            "The observed imports may be composition or test-only wiring. Confirm the runtime "
            "dependency before restructuring.",
            classification="required", affected=cycle, requires_user=True)
    for module in modules:
        affected = module.get("implementation", {}).get("paths", []) + \
            module.get("contracts", {}).get("paths", [])
        for dependency in module.get("dependencies", []):
            if dependency["leaksImplementation"]:
                add("Replace private implementation coupling",
                    f"{module['name']} imports {dependency['module']} through an implementation-shaped path.",
                    dependency["evidence"],
                    "A consumer that depends on another module's implementation makes internal "
                    "changes cross a published boundary.",
                    "Depend on the provider's explicit public contract; if the operation is missing, "
                    "request an additive contract change from its owner.",
                    "The consumer becomes stable against private refactoring inside the provider.",
                    "The import may be an intentional adapter or composition-root reference. Confirm "
                    "the path before changing it.",
                    classification="required", affected=[module["id"], dependency["moduleId"]],
                    requires_user=True)
                recommendations[-1]["affectedFiles"] = affected
        cross_dependencies = [item for item in module.get("dependencies", []) if item["moduleId"] in graph]
        if cross_dependencies and not module["contracts"]["paths"]:
            add("Decide the contract boundary",
                f"{module['name']} participates in cross-module imports but has no identified contract-shaped path.",
                [item for dependency in cross_dependencies for item in dependency["evidence"]],
                "A dependency needs a public shape that is distinguishable from private code.",
                "Confirm whether the existing entry point is the public contract, create an explicit "
                "contract area only if needed, or record why this dependency is internal composition.",
                "Consumers and providers can evolve independently without exposing implementation.",
                "Creating a new folder is not automatically an improvement. Preserve an existing "
                "public API if it already separates contract from implementation.",
                classification="owner-decision", affected=[module["id"]], requires_user=True)
            recommendations[-1]["affectedFiles"] = affected
    return ({"observations": observations, "cycles": cycles,
             "dependencyGraph": {node: sorted(children) for node, children in graph.items()},
             "contractCoverage": sum(bool(module["contracts"]["paths"]) for module in modules)},
            recommendations)


def _existing_architecture(root: Path) -> dict:
    candidates = [
        CONFIG_NAME, "arch/architecture-rules.json", "architecture-rules.json",
        "docs/architecture-map.md", "scripts/architecture-gate.mjs",
        "scripts/architecture-map.mjs", "scripts/architecture-analyzers.mjs",
        "tools/acima_arch.py", "tools/acima-arch.mjs", "tools/Acima.ArchTests/Program.cs",
    ]
    paths = [path for path in candidates if (root / path).exists()]
    solutions = sorted(_relative(path, root) for path in _walk(root)
                       if path.suffix.lower() == ".sln")
    project_manifests = sorted(_relative(path, root) for path in _walk(root)
                               if path.suffix.lower() == ".csproj")
    return {
        "paths": paths,
        "solutions": solutions[:20],
        "dotnetProjects": project_manifests[:100],
        "declarations": (["Existing ACIMA configuration is present and is preserved."]
                         if (root / CONFIG_NAME).is_file() else []),
        "note": "Existing architecture evidence is preserved and evaluated; discovery does not "
                "replace it with directory-derived modules.",
    }


def _path_decision_item(identifier: str, classification: str, paths: list[str],
                        reason: str, confidence: str, *, owner: str = "",
                        module_id: str | None = None, status: str = "pending") -> dict:
    return {
        "id": identifier,
        "kind": "path",
        "classification": classification,
        "paths": paths,
        "reason": reason,
        "confidence": confidence,
        "owner": owner,
        "moduleId": module_id,
        "status": status,
        "requiresDecision": True,
        "options": ["accept", "modify", "reject", "defer"],
    }


def _decision_statuses(proposal: dict) -> tuple[list[dict], list[dict]]:
    modules = proposal.get("modules") or []
    dispositions = proposal.get("pathDispositions") or []
    return modules, dispositions


def _assign_disposition_ids(dispositions: list[dict]) -> list[dict]:
    used = set()
    for item in dispositions:
        base = "path:" + _slug(item["classification"] + "-" + (item["paths"][0] if item["paths"] else "path"))
        identifier = base
        counter = 2
        while identifier in used:
            identifier = f"{base}-{counter}"
            counter += 1
        used.add(identifier)
        item["id"] = identifier
    return dispositions


def discover(root: Path, *, config: dict | None = None) -> dict:
    """Discover the repository and produce a non-authoritative module-map proposal."""
    root = root.resolve()
    if not root.is_dir():
        raise ModuleMapError(f"project does not exist: {root}")
    loaded, error = (config, None) if config is not None else _read_config(root)
    source = _source_files(root)
    authoritative = _authoritative_review(root, loaded, source)
    if error:
        authoritative.update({"status": "inconsistent", "summary": error})
        authoritative["issues"].append({"code": "invalid-config", "detail": error})
    existing_architecture = _existing_architecture(root)
    if authoritative["status"] == "complete":
        review = _read_review(root)
        if review is None and authoritative.get("approvalProvenance"):
            marker = authoritative["approvalProvenance"]
            if marker.get("status") == "approved":
                review = {
                    "status": "approved",
                    "reviewer": marker.get("reviewer"),
                    "reviewedOn": marker.get("reviewedOn"),
                    "approval": marker,
                    "source": "authoritative-config-approval-marker",
                }
        return {
            "schemaVersion": SCHEMA_VERSION,
            "status": "authoritative",
            "proposalId": None,
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "authoritativeMap": authoritative,
            "proposal": None,
            "review": review,
            "existingArchitecture": existing_architecture,
            "quality": {
                "observations": [
                    {"topic": "ownership declaration", "observation": authoritative["summary"],
                     "basis": "observed", "confidence": "high"},
                    {"topic": "map consistency",
                     "observation": ("No overlapping or missing declared paths were found."
                                     if authoritative["status"] == "complete" else
                                     authoritative["summary"]),
                     "basis": "observed", "confidence": "medium"},
                ]
            },
            "summary": ("An authoritative map exists and was evaluated in place; it was not "
                        "replaced by discovery."),
            "nextDecision": "Review the map's quality observations; no ownership approval is required.",
        }
    candidates = _candidate_paths(root)
    modules = _build_modules(root, candidates)
    # Preserve declared units when the existing map is partial. Discovery adds candidates for
    # uncovered source; it never relabels or replaces a declaration the owner already made.
    existing_by_name: dict[str, dict] = {}
    for unit in (loaded or {}).get("units", []) if isinstance((loaded or {}).get("units", []), list) else []:
        if not isinstance(unit, dict) or not unit.get("module"):
            continue
        group = existing_by_name.setdefault(str(unit["module"]), {
            "id": _slug(str(unit["module"])),
            "name": _module_name(Path(str(unit["module"]))),
            "status": "existing",
            "ownership": "declared",
            "confidence": "high",
            "responsibility": ("Declared by the existing authoritative map. The declaration is "
                               "preserved for review; discovery does not reinterpret it."),
            "implementation": {"paths": [], "classification": "declared"},
            "contracts": {"paths": [], "classification": "declared"},
            "dependencies": [],
            "dataAndConfiguration": [],
            "entryPoints": [],
            "compositionResponsibilities": [],
            "evidence": [_line_evidence(root, CONFIG_NAME, 1,
                                        "The existing map declares this module and its paths.",
                                        kind="configuration")],
            "limitations": "The declaration is preserved; its quality was evaluated separately.",
        })
        role = unit.get("role")
        for path in unit.get("paths", []) if isinstance(unit.get("paths"), list) else []:
            if isinstance(path, str) and path not in group["contracts" if role == "contracts" else "implementation"]["paths"]:
                group["contracts" if role == "contracts" else "implementation"]["paths"].append(path)
    merged: list[dict] = []
    seen = set()
    for module in modules:
        existing = existing_by_name.get(_slug(module["name"])) or existing_by_name.get(module["id"])
        if existing is not None:
            existing["evidence"].extend(item for item in module["evidence"]
                                        if item not in existing["evidence"])
            existing["dependencies"] = module["dependencies"]
            module = existing
        merged.append(module)
        seen.add(module["id"])
    for _key, existing in existing_by_name.items():
        if existing["id"] not in seen:
            merged.append(existing)
    modules = _unique_modules(sorted(merged, key=lambda item: item["id"]))
    module_paths = _module_paths(modules)

    # Group routine non-module content; never manufacture a module for it.
    grouped: dict[tuple[str, str], dict] = {}
    unresolved: list[str] = []
    for path in source:
        relative = _relative(path, root)
        if any(_path_matches(relative, prefix) for prefix in module_paths):
            continue
        existing_disposition = next(
            (item for item in authoritative.get("dispositions", [])
             if any(_path_matches(relative, prefix) for prefix in item["paths"])), None)
        if existing_disposition:
            classification = existing_disposition["classification"]
            reason = existing_disposition.get("reason") or "Declared by the existing map."
            confidence = existing_disposition.get("confidence") or "high"
            owner = existing_disposition.get("owner") or ""
        else:
            classified = classify_path(relative)
            classification = classified["classification"]
            reason = classified["reason"]
            confidence = classified["confidence"]
            owner = ""
        if classification == "unresolved-production":
            unresolved.append(relative)
            continue
        group = _disposition_group(relative, classification)
        item = grouped.setdefault((classification, group), {
            "classification": classification, "paths": [group], "files": [],
            "reason": reason, "confidence": confidence, "owner": owner, "existing": bool(existing_disposition),
        })
        item["files"].append(relative)
        if confidence == "high":
            item["confidence"] = "high"
        if owner:
            item["owner"] = owner
    dispositions = []
    for (classification, group), item in sorted(grouped.items()):
        status = "existing" if item["existing"] else "pending"
        dispositions.append(_path_decision_item(
            "", classification, [group], item["reason"], item["confidence"],
            owner=item["owner"], status=status))
        dispositions[-1]["affectedFiles"] = sorted(item["files"])
    for path in sorted(unresolved):
        dispositions.append(_path_decision_item(
            "", "unresolved-production", [path], classify_path(path)["reason"], "low"))
    dispositions = _assign_disposition_ids(dispositions)
    for module in modules:
        module["dependencies"] = _import_evidence(root, module, modules)
    quality, recommendations = _quality_and_recommendations(
        root, modules, sorted(unresolved), authoritative, dispositions)
    decisions = [{
        "id": f"module:{module['id']}",
        "kind": "module",
        "question": f"Should {module['name']} be an ACIMA module?",
        "context": module["responsibility"],
        "recommendation": "Accept only if this boundary reflects real ownership, not merely a folder.",
        "essential": True,
        "status": "pending",
        "options": ["accept", "modify", "reject", "defer"],
        "affectedModules": [module["id"]],
    } for module in modules]
    decisions.extend({
        "id": item["id"],
        "kind": "path",
        "question": f"Accept the {item['classification']} disposition for {', '.join(item['paths'])}?",
        "context": item["reason"],
        "recommendation": "Accept, modify into a module assignment, reject, or defer this classification.",
        "essential": True,
        "status": "existing" if item["status"] == "existing" else "pending",
        "options": ["accept", "modify", "reject", "defer"],
        "affectedPaths": item["paths"],
    } for item in dispositions)
    decisions.extend({
        "id": f"recommendation:{rec['id']}",
        "kind": "recommendation",
        "question": rec["title"],
        "context": rec["observed"],
        "recommendation": rec["recommendation"],
        "essential": rec["essential"],
        "status": "pending",
        "options": ["accept", "reject", "defer"],
        "affectedModules": rec["affectedModules"],
    } for rec in recommendations)
    basis = ("No module map was declared." if loaded is None else
             f"An existing map was found ({authoritative['status']}) and its usable units were preserved.")
    module_covered = [ _relative(path, root) for path in source
                       if any(_path_matches(_relative(path, root), prefix) for prefix in module_paths)]
    disposition_covered = [path for item in dispositions
                           if item["classification"] != "unresolved-production"
                           for path in item.get("affectedFiles", [])]
    proposal = {
        "schemaVersion": SCHEMA_VERSION,
        "status": "proposed",
        "basis": basis,
        "classification": "inference",
        "modules": modules,
        "pathDispositions": dispositions,
        "unassigned": [{
            "path": path,
            "reason": classify_path(path)["reason"],
            "classification": "unresolved-production",
        } for path in sorted(unresolved)],
        "coverage": {
            "sourceFiles": len(source),
            "moduleCovered": len(set(module_covered)),
            "classifiedNonModule": len(set(disposition_covered)),
            "unresolvedProduction": len(unresolved),
        },
        "existingArchitecture": existing_architecture,
        "quality": quality,
        "recommendations": recommendations,
        "decisions": decisions,
        "confidence": "medium" if modules else "low",
        "limitations": [
            "Discovery uses layout, manifests, source presence, existing declarations and observed "
            "import lines. It does not prove business ownership, runtime isolation, deployment "
            "independence or public API status.",
            "Project, package, folder and runtime boundaries are signals, not approved modules.",
            "Tests, fixtures, tooling, spikes, generated and vendored source are repository content, "
            "not automatically modules. Their dispositions still require review.",
            "The proposal must be reviewed before it can become an authoritative map.",
        ],
    }
    canonical = json.dumps({key: value for key, value in proposal.items()
                            if key not in {"schemaVersion"}}, sort_keys=True, ensure_ascii=False)
    proposal["proposalId"] = "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return {
        "schemaVersion": SCHEMA_VERSION,
        "status": "proposal_required" if not authoritative["present"] else "proposal_for_incomplete_map",
        "proposalId": proposal["proposalId"],
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "authoritativeMap": authoritative,
        "proposal": proposal,
        "review": _read_review(root),
        "existingArchitecture": existing_architecture,
        "summary": basis,
        "nextDecision": ("Review the proposed boundaries, path dispositions and recommendations. "
                         "Do not treat them as ownership until accepted."),
    }


def proposed_units(document: dict) -> list[dict]:
    """Return the units represented by a discovery proposal for preflight/coverage."""
    proposal = document.get("proposal") or {}
    modules = proposal.get("modules") or []
    result = []
    for module in modules:
        implementation = module.get("implementation", {}).get("paths", [])
        contracts = module.get("contracts", {}).get("paths", [])
        if implementation:
            result.append({"id": module["id"], "module": module["id"],
                           "role": "implementation", "paths": implementation})
        if contracts:
            contract_path = contracts[0]
            base = Path(contract_path).name
            module_id = Path(contract_path).name[:-len(".contracts")] \
                if Path(contract_path).name.lower().endswith(".contracts") else module["id"]
            result.append({"id": base if base.lower().endswith(".contracts")
                           else f"{module['id']}.contracts",
                           "module": module_id, "role": "contracts", "paths": contracts})
    return result


def _safe_relative(raw: Any) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise ModuleMapError("every modified ownership path must be a non-empty string")
    candidate = PurePosixPath(raw.replace("\\", "/"))
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ModuleMapError(f"ownership path escapes the repository: {raw!r}")
    return candidate.as_posix().rstrip("/")


def _decision_map(items: Any, label: str) -> dict[str, dict]:
    if items is None:
        return {}
    if not isinstance(items, list):
        raise ModuleMapError(f"review.{label} must be a list")
    result = {}
    for item in items:
        if not isinstance(item, dict) or not item.get("id"):
            raise ModuleMapError(f"every review.{label} entry needs an id")
        identifier = str(item["id"])
        if identifier in result:
            raise ModuleMapError(f"duplicate review.{label} id {identifier!r}")
        result[identifier] = item
    return result


def _apply_path_assignment(module: dict, paths: list[str], classification: str) -> None:
    key = "contracts" if classification == "public-contract" else "implementation"
    for path in paths:
        if path not in module[key]["paths"]:
            module[key]["paths"].append(path)


def apply_review(proposal: dict, review: dict, *, root: Path | None = None) -> dict:
    """Apply explicit, scoped decisions to a proposal. No file is written here."""
    if not isinstance(proposal, dict) or not isinstance(proposal.get("proposal"), dict):
        raise ModuleMapError("a proposal document with a proposal object is required")
    if not isinstance(review, dict):
        raise ModuleMapError("review must be a JSON object")
    inner = proposal["proposal"]
    if review.get("schemaVersion") not in (None, SCHEMA_VERSION):
        raise ModuleMapError(f"review schemaVersion must be {SCHEMA_VERSION}")
    if review.get("proposalId") != proposal.get("proposalId") and review.get("proposalId") != inner.get("proposalId"):
        raise ModuleMapError("review proposalId does not match the proposal")
    if not str(review.get("reviewer", "")).strip():
        raise ModuleMapError("review.reviewer is required")
    try:
        reviewed_on = str(review.get("reviewedOn"))
        parsed = date.fromisoformat(reviewed_on)
        if parsed.isoformat() != reviewed_on or parsed > date.today():
            raise ValueError
    except (TypeError, ValueError) as error:
        raise ModuleMapError("review.reviewedOn must be a valid, non-future YYYY-MM-DD date") from error
    map_decision = review.get("mapDecision", "defer")
    if map_decision not in DECISIONS:
        raise ModuleMapError("review.mapDecision must be accept, modify, reject or defer")
    module_reviews = _decision_map(review.get("moduleDecisions"), "moduleDecisions")
    path_reviews = _decision_map(review.get("pathDecisions"), "pathDecisions")
    rec_reviews = _decision_map(review.get("recommendationDecisions"), "recommendationDecisions")
    modules = []
    for module in inner.get("modules", []):
        decision = module_reviews.get(module["id"])
        # An overall accept never implies acceptance of an individual boundary.
        choice = decision.get("decision", "defer") if decision else "defer"
        if choice not in DECISIONS:
            raise ModuleMapError(f"module {module['id']} has unknown decision {choice!r}")
        updated = json.loads(json.dumps(module))
        updated["reviewDecision"] = choice
        if choice == "modify":
            for key in ("name", "responsibility"):
                if decision.get(key):
                    updated[key] = str(decision[key]).strip()
            if decision.get("paths") is not None:
                paths = [_safe_relative(path) for path in decision["paths"]]
                if not paths:
                    raise ModuleMapError(f"module {module['id']} modification has no paths")
                if root is not None:
                    for path in paths:
                        if not (root / path).exists():
                            raise ModuleMapError(f"modified ownership path does not exist: {path}")
                updated["implementation"]["paths"] = paths
            if decision.get("contracts") is not None:
                updated["contracts"]["paths"] = [_safe_relative(path) for path in decision["contracts"]]
        if choice in {"reject", "defer"}:
            updated["status"] = "rejected" if choice == "reject" else "deferred"
        else:
            updated["status"] = "accepted" if choice == "accept" else "modified"
        modules.append(updated)
    by_id = {module["id"]: module for module in modules}

    path_results = []
    for disposition in inner.get("pathDispositions", []):
        decision = path_reviews.get(disposition["id"])
        if disposition.get("status") == "existing":
            updated = json.loads(json.dumps(disposition))
            updated["reviewDecision"] = "accept"
            updated["decisionSource"] = "existing-map"
            path_results.append(updated)
            continue
        choice = decision.get("decision", "defer") if decision else "defer"
        if choice not in PATH_DECISIONS:
            raise ModuleMapError(f"path disposition {disposition['id']} has unknown decision {choice!r}")
        updated = json.loads(json.dumps(disposition))
        updated["reviewDecision"] = choice
        if choice == "modify":
            classification = str(decision.get("classification") or updated.get("classification"))
            if classification not in CLASSIFICATIONS:
                raise ModuleMapError(f"path disposition {disposition['id']} has unknown classification {classification!r}")
            paths = decision.get("paths", updated.get("paths"))
            if not isinstance(paths, list) or not paths:
                raise ModuleMapError(f"path disposition {disposition['id']} modification has no paths")
            paths = [_safe_relative(path) for path in paths]
            if root is not None:
                for path in paths:
                    if not (root / path).exists():
                        raise ModuleMapError(f"modified disposition path does not exist: {path}")
            updated["classification"] = classification
            updated["paths"] = paths
            if decision.get("owner"):
                updated["owner"] = str(decision["owner"]).strip()
            if decision.get("reason"):
                updated["reason"] = str(decision["reason"]).strip()
            if classification in MODULE_CLASSIFICATIONS:
                module_id = decision.get("moduleId")
                if not module_id or module_id not in by_id:
                    raise ModuleMapError(f"path disposition {disposition['id']} assigns to an unknown module")
                if by_id[module_id].get("reviewDecision") not in {"accept", "modify"}:
                    raise ModuleMapError(f"path disposition {disposition['id']} assigns to an unaccepted module")
                _apply_path_assignment(by_id[module_id], paths, classification)
                updated["moduleId"] = module_id
        elif choice == "reject":
            updated["classification"] = "unresolved-production"
            updated["reason"] = "The reviewer rejected this disposition; ownership remains unresolved."
        elif choice == "defer":
            updated["status"] = "deferred"
        if choice in {"accept", "modify"}:
            updated["status"] = "accepted"
        elif choice == "reject":
            updated["status"] = "rejected"
        path_results.append(updated)

    recommendation_results = []
    for recommendation in inner.get("recommendations", []):
        decision = rec_reviews.get(recommendation["id"])
        choice = decision.get("decision", "pending") if decision else "pending"
        if choice not in {"accept", "reject", "defer", "pending"}:
            raise ModuleMapError(f"recommendation {recommendation['id']} has unknown decision {choice!r}")
        updated = dict(recommendation)
        updated["decision"] = choice
        if decision and decision.get("note"):
            updated["decisionNote"] = str(decision["note"]).strip()
        recommendation_results.append(updated)

    accepted = [module for module in modules if module["reviewDecision"] in {"accept", "modify"}]
    module_pending = [module["id"] for module in modules
                      if module["reviewDecision"] not in {"accept", "modify"}]
    essential_pending = [rec["id"] for rec in recommendation_results
                         if rec["essential"] and rec["decision"] == "pending"]
    path_pending = [item["id"] for item in path_results
                    if item.get("reviewDecision") not in {"accept", "modify", "reject"}]
    if map_decision == "reject":
        status = "rejected"
        approved_modules = []
        approved_units = []
    elif map_decision == "defer":
        status = "deferred"
        approved_modules = []
        approved_units = []
    elif module_pending or path_pending or essential_pending:
        status = "partially_approved"
        approved_modules = [module["id"] for module in accepted]
        approved_units = units_from_approved(accepted)
    else:
        status = "approved"
        approved_modules = [module["id"] for module in accepted]
        approved_units = units_from_approved(accepted)

    # Recompute coverage from the decisions, never from the original unassigned list.
    source = _source_files(root) if root is not None else []
    module_paths = _module_paths([module for module in modules
                                  if module["reviewDecision"] in {"accept", "modify"}])
    accepted_dispositions = [item for item in path_results
                             if item.get("reviewDecision") in {"accept", "modify"}
                             and item.get("classification") in RESOLVED_NON_MODULE]
    module_covered = []
    classified = []
    unresolved = []
    for path in source:
        relative = _relative(path, root)
        if any(_path_matches(relative, prefix) for prefix in module_paths):
            module_covered.append(relative)
        elif any(_path_matches(relative, prefix) for item in accepted_dispositions
                 for prefix in item["paths"]):
            classified.append(relative)
        else:
            unresolved.append(relative)
    if status == "approved" and (not modules or unresolved):
        status = "partially_approved"
    approval = {
        "schemaVersion": SCHEMA_VERSION,
        "proposalId": inner.get("proposalId"),
        "reviewer": str(review["reviewer"]).strip(),
        "reviewedOn": reviewed_on,
        "mapDecision": map_decision,
        "status": status,
        "approvedModules": approved_modules,
        "undecidedModules": module_pending,
        "undecidedPathDispositions": path_pending,
        "essentialRecommendationsPending": essential_pending,
        "uncoveredProduction": unresolved,
        "classifiedNonModule": classified,
        "moduleCovered": module_covered,
        "coverage": {
            "sourceFiles": len(source),
            "moduleCovered": len(module_covered),
            "classifiedNonModule": len(classified),
            "unresolvedProduction": len(unresolved),
        },
        "canWriteConfig": status == "approved" and not unresolved,
        "approvedAt": datetime.now(timezone.utc).isoformat(),
        "meaning": ("Approval is explicit and scoped. A partial approval permits only approved "
                    "boundaries; it does not authorize deterministic checks over unowned source."),
    }
    result = {
        "schemaVersion": SCHEMA_VERSION,
        "proposalId": inner.get("proposalId"),
        "status": status,
        "modules": modules,
        "pathDispositions": path_results,
        "recommendations": recommendation_results,
        "approval": approval,
        "approvedUnits": approved_units,
    }
    if status == "approved":
        try:
            result["config"] = build_config(proposal, result)
        except ModuleMapError:
            pass
    return result


def units_from_approved(modules: list[dict]) -> list[dict]:
    units = []
    for module in modules:
        module_id = module["id"]
        paths = module.get("implementation", {}).get("paths", [])
        contracts = module.get("contracts", {}).get("paths", [])
        if paths:
            units.append({"id": module_id, "module": module_id, "role": "implementation",
                          "paths": paths, "source": "proposal-approved"})
        if contracts:
            first = Path(contracts[0]).name
            contract_module = first[:-len(".contracts")] if first.lower().endswith(".contracts") else module_id
            unit_id = first if first.lower().endswith(".contracts") else f"{module_id}.contracts"
            units.append({"id": unit_id, "module": contract_module, "role": "contracts",
                          "paths": contracts, "source": "proposal-approved"})
    return units


def _merge_approved_units(existing_units: list[dict], generated_units: list[dict]) -> list[dict]:
    """Merge generated roles while preserving all explicitly declared unit roles.

    Existing units match generated units by (module, role), not derived ids.
    Existing ids and custom metadata survive; other declared roles remain intact.
    """
    result = [json.loads(json.dumps(unit)) for unit in existing_units
              if isinstance(unit, dict)]
    indexes: dict[tuple[str, str], int] = {}
    for index, unit in enumerate(result):
        key = (str(unit.get("module") or unit.get("id") or ""),
               str(unit.get("role") or ""))
        if key in indexes:
            raise ModuleMapError(
                "existing configuration contains multiple units for module/role %r" % (key,)
            )
        indexes[key] = index
    for generated in generated_units:
        if not isinstance(generated, dict):
            raise ModuleMapError("approved unit must be an object")
        key = (str(generated.get("module") or generated.get("id") or ""),
               str(generated.get("role") or ""))
        if not key[0] or not key[1]:
            raise ModuleMapError("approved unit requires module and role")
        if key in indexes:
            current = result[indexes[key]]
            merged = dict(current)
            merged["paths"] = list(generated.get("paths") or [])
            merged["source"] = "proposal-approved"
            result[indexes[key]] = merged
        else:
            indexes[key] = len(result)
            result.append(json.loads(json.dumps(generated)))
    return result


def build_config(proposal: dict, review_result: dict, *, existing: dict | None = None,
                 language: str | None = None) -> dict:
    approval = review_result.get("approval") or {}
    if not approval.get("canWriteConfig"):
        raise ModuleMapError("the review does not authorize a complete authoritative map")
    generated_units = review_result.get("approvedUnits") or []
    if not generated_units:
        raise ModuleMapError("the approved review contains no units")
    # Refine the existing ownership contract without flattening owner-declared roles.
    units = _merge_approved_units((existing or {}).get("units") or [], generated_units)
    seen = set()
    for unit in units:
        if unit["id"] in seen:
            raise ModuleMapError(f"approved units contain duplicate id {unit['id']!r}")
        seen.add(unit["id"])
    base = dict(existing or {})
    dispositions = []
    for item in review_result.get("pathDispositions", []):
        if item.get("reviewDecision") not in {"accept", "modify"}:
            continue
        if item.get("classification") not in RESOLVED_NON_MODULE:
            continue
        dispositions.append({
            "paths": item["paths"],
            "classification": item["classification"],
            "reason": item.get("reason", ""),
            "owner": item.get("owner", ""),
            "confidence": item.get("confidence", "medium"),
        })
    base.update({
        "standard": base.get("standard") or "1.9.0-draft.1",
        "mode": base.get("mode") or "base",
        "language": base.get("language") or language or "unknown",
        "level": base.get("level") or "L1",
        "root": base.get("root") or ".",
        "units": units,
        "repositoryDispositions": dispositions,
        "exclude": base.get("exclude") or ["bin", "obj", "node_modules", "dist", "build",
                                            "target", "tests", "**/__pycache__"],
        "waivers": base.get("waivers") or ".acima/waivers.json",
        "_moduleMapApproval": {
            "proposalId": proposal.get("proposalId"),
            "reviewer": approval.get("reviewer"),
            "reviewedOn": approval.get("reviewedOn"),
            "approvedAt": approval.get("approvedAt"),
            "status": approval.get("status"),
            "coverage": approval.get("coverage"),
        },
    })
    return base


def automatic_review(proposal: dict, reviewer: str) -> dict:
    """Create a conservative review for full automation.

    It accepts only classifications and boundaries supported by medium/high confidence, and
    explicitly defers everything else. It never uses directory proximity to invent ownership.
    """
    inner = proposal.get("proposal") or {}
    modules = []
    for module in inner.get("modules", []):
        # Confidence labels derived from manifests or directory structure are discovery
        # signals, not evidence of architectural ownership. Candidate modules whose
        # responsibility explicitly remains inferred must never become authoritative
        # merely because a build unit was detected.
        responsibility = str(module.get("responsibility") or "").lower()
        implementation = module.get("implementation") or {}
        ownership = module.get("ownership")
        supported = (
            ownership == "declared"
            and module.get("confidence") == "high"
            and bool(module.get("responsibility"))
        )
        if implementation.get("classification") == "observed-layout":
            supported = False
        if "inferred only from repository structure" in responsibility or "requires owner confirmation" in responsibility:
            supported = False
        modules.append({"id": module["id"], "decision": "accept" if supported else "defer"})
    paths = []
    for item in inner.get("pathDispositions", []):
        supported = item.get("classification") in RESOLVED_NON_MODULE and item.get("confidence") in {"medium", "high"}
        paths.append({"id": item["id"], "decision": "accept" if supported else "defer"})
    recommendations = []
    for item in inner.get("recommendations", []):
        supported = bool(item.get("autoAcceptable")) and not item.get("requiresUserInput")
        recommendations.append({"id": item["id"], "decision": "accept" if supported else "defer"})
    return {
        "schemaVersion": SCHEMA_VERSION,
        "proposalId": proposal.get("proposalId"),
        "reviewer": reviewer,
        "reviewedOn": date.today().isoformat(),
        "mapDecision": "accept",
        "moduleDecisions": modules,
        "pathDecisions": paths,
        "recommendationDecisions": recommendations,
    }


def mode_can_auto_accept(proposal: dict) -> tuple[bool, str]:
    inner = proposal.get("proposal") or {}
    if not inner.get("modules"):
        return False, "no candidate module is available for automatic adoption"
    unresolved = [item for item in inner.get("pathDispositions", [])
                  if item.get("classification") == "unresolved-production"]
    if unresolved:
        return False, ("%s production path(s) remain unresolved; the owner must classify them"
                       % len(unresolved))
    unsupported = [
        module for module in inner.get("modules", [])
        if module.get("ownership") != "declared"
        or module.get("implementation", {}).get("classification") == "observed-layout"
        or "inferred only from repository structure" in str(module.get("responsibility") or "").lower()
        or "requires owner confirmation" in str(module.get("responsibility") or "").lower()
    ]
    if unsupported:
        return False, (
            "%s candidate module boundary/boundaries rely on inferred or layout-only ownership; "
            "automated mode must defer them for owner review" % len(unsupported)
        )
    return True, "all modules have previously declared, high-confidence ownership and no unresolved production path remains"


def load_proposal(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ModuleMapError(f"cannot read module-map proposal {path}: {error}") from error
    if not isinstance(value, dict):
        raise ModuleMapError("module-map proposal must be a JSON object")
    return value


def load_review(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ModuleMapError(f"cannot read module-map review {path}: {error}") from error
    if not isinstance(value, dict):
        raise ModuleMapError("module-map review must be a JSON object")
    return value


def _read_review(root: Path) -> dict | None:
    path = root / APPROVAL_FILE
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def language_for(root: Path) -> str:
    """Choose the dominant production language, ignoring incidental non-production source."""
    counts: dict[str, int] = {}
    extensions = {".py": "python", ".ts": "typescript", ".tsx": "typescript",
                  ".js": "typescript", ".mjs": "typescript", ".cjs": "typescript",
                  ".go": "go", ".cs": "dotnet"}
    for path in _source_files(root):
        relative = _relative(path, root)
        classification = classify_path(relative)
        if classification["classification"] not in {"unresolved-production", "composition"}:
            continue
        language = extensions.get(path.suffix.lower())
        if language:
            counts[language] = counts.get(language, 0) + 1
    if counts:
        return max(counts, key=lambda item: counts[item])
    # Contract-only or unusually classified repositories still have a language.
    for path in _source_files(root):
        language = extensions.get(path.suffix.lower())
        if language:
            counts[language] = counts.get(language, 0) + 1
    return max(counts, key=lambda item: counts[item]) if counts else "unknown"


def _language_for(root: Path) -> str:
    return language_for(root)


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="ACIMA module-map discovery and review")
    sub = parser.add_subparsers(dest="command", required=True)
    discover_parser = sub.add_parser("discover", help="read-only discovery and proposal")
    discover_parser.add_argument("--project", required=True)
    discover_parser.add_argument("--format", choices=["json"], default="json")
    discover_parser.add_argument("--write-proposal", default=None,
                                 help="explicitly write the proposal to this path")
    review_parser = sub.add_parser("review", help="apply explicit decisions to a proposal")
    review_parser.add_argument("--project", required=True)
    review_parser.add_argument("--proposal", required=True)
    review_parser.add_argument("--decisions", required=True)
    review_parser.add_argument("--write-approval", default=None,
                               help="write the review to this path (typically .acima/module-map.approval.json)")
    review_parser.add_argument("--write-config", default=None,
                               help="write acima.config.json only when the review approves a complete map")
    args = parser.parse_args(argv)
    root = Path(args.project).resolve()
    try:
        if args.command == "discover":
            result = discover(root)
            if args.write_proposal:
                _write_json(root / args.write_proposal, result)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0
        proposal = load_proposal(Path(args.proposal))
        decisions = load_review(Path(args.decisions))
        result = apply_review(proposal, decisions, root=root)
        existing, _error = _read_config(root)
        if args.write_approval:
            _write_json(root / args.write_approval, result)
        if args.write_config:
            config = build_config(proposal, result, existing=existing, language=language_for(root))
            _write_json(root / args.write_config, config)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except ModuleMapError as error:
        print(f"module_map: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
