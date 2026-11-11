"""Evidence-backed module-map discovery, proposal and approval.

The proposal is an assessment artefact. It never becomes authoritative merely because
discovery succeeded: a reviewer must accept, modify, reject or defer the proposal (or
individual boundaries and recommendations). An approved map is then converted to the
existing ``acima.config.json`` unit contract, which the enforcers already understand.

This module is deliberately shared by the adoption skill and the developer CLI so a
proposal cannot drift between the two entry points.
"""
from __future__ import annotations

import hashlib
import json
import re
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
}
BASES = ("src", "internal", "packages", "app", "apps", "services", "lib", "modules")
CONTRACT_NAMES = {"contracts", "contract", "api", "ports", "port", "public"}
IGNORED_LAYOUT = {
    "test", "tests", "__tests__", "spec", "specs", "e2e", "docs", "doc",
    "examples", "example", "tools", "scripts", "migrations", "benchmarks",
}
DECISIONS = {"accept", "modify", "reject", "defer"}
ESSENTIAL_RECOMMENDATION_CLASSES = {"required", "owner-decision"}
OWNERSHIP_DEPENDENT_RULES = {
    "ACIMA-D001", "ACIMA-D002", "ACIMA-D003", "ACIMA-D004", "ACIMA-D005",
    "ACIMA-D008", "ACIMA-D009", "ACIMA-D010", "ACIMA-D013", "ACIMA-D014",
    "ACIMA-D015", "ACIMA-D016", "ACIMA-L001", "ACIMA-L002", "ACIMA-L003",
    "ACIMA-A007", "ACIMA-A008", "ACIMA-A009",
}


class ModuleMapError(ValueError):
    """A proposal or review cannot be trusted."""


def _walk(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in PRUNE or (part.startswith(".") and part not in {".acima"})
               for part in relative.parts):
            continue
        yield path


def _is_test(path: Path) -> bool:
    parts = [part.lower() for part in path.parts]
    name = path.name.lower()
    return (any(part in {"test", "tests", "__tests__", "spec", "specs", "e2e"} or
                part.endswith((".test", ".tests", ".spec", ".specs")) for part in parts)
            or any(name.endswith(suffix) for suffix in
                   (".test.ts", ".test.tsx", ".test.js", ".test.jsx",
                    ".spec.ts", ".spec.tsx", ".spec.js", ".spec.jsx")))


def _is_tooling(path: Path) -> bool:
    name = path.name.lower()
    return (name.startswith(("eslint.config.", "vite.config.", "vitest.config.",
                             "playwright.config.", "tsconfig."))
            or name == "vite-env.d.ts")


def _is_generated(path: Path) -> bool:
    name = path.name.lower()
    return name.endswith((".g.cs", ".generated.cs", ".designer.cs")) or ".generated." in name


def _production_files(root: Path) -> list[Path]:
    return [path for path in _walk(root)
            if path.suffix.lower() in SOURCE_EXTENSIONS
            and not _is_test(path.relative_to(root))
            and not _is_tooling(path.relative_to(root))
            and not _is_generated(path.relative_to(root))]


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


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
    for path in sorted(directory.rglob("*")):
        if path.is_file() and path.suffix.lower() in SOURCE_EXTENSIONS:
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
    words = re.sub(r"[^A-Za-z0-9]+", " ", stem).strip().split()
    return " ".join(word[:1].upper() + word[1:] for word in words) or stem


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug or "module"


def _candidate_paths(root: Path) -> dict[str, dict]:
    """Return layout candidates. These are signals, never approved ownership."""
    candidates: dict[str, dict] = {}

    def add(directory: Path, *, manifest: str | None = None) -> None:
        try:
            relative = _relative(directory, root)
        except ValueError:
            return
        if not relative or relative == "." or any(part in PRUNE or part.startswith(".")
                                                  for part in PurePosixPath(relative).parts):
            return
        if not any(path.suffix.lower() in SOURCE_EXTENSIONS for path in directory.rglob("*")
                   if path.is_file()):
            return
        item = candidates.setdefault(relative, {"paths": [relative], "manifests": []})
        if manifest and manifest not in item["manifests"]:
            item["manifests"].append(manifest)

    # Project/package manifests are strong layout signals, but still not ownership proof.
    for pattern in ("*.csproj", "package.json", "pyproject.toml", "setup.py",
                    "setup.cfg", "go.mod"):
        for manifest in sorted(root.rglob(pattern)):
            if any(part in PRUNE or part.startswith(".") for part in
                   manifest.relative_to(root).parts):
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
            modules = relative.rsplit("/", 1)[0] if "/" in relative else ""
            implementation = f"{modules}/{path.name[:-len('.contracts')]}" if modules else path.name[:-len(".contracts")]
            if (root / implementation).is_dir():
                target = candidates.setdefault(implementation, {"paths": [implementation],
                                                                  "manifests": []})
                target["paths"].append(relative)
                target["manifests"].extend(candidates[relative].get("manifests", []))
                target["manifests"] = sorted(set(target["manifests"]))
                del candidates[relative]
    return dict(sorted(candidates.items()))


def _contract_paths(root: Path, directory: Path) -> list[str]:
    found = []
    for child in sorted(directory.rglob("*")):
        if child.is_dir() and child.name.lower() in CONTRACT_NAMES:
            if any(item.is_file() and item.suffix.lower() in SOURCE_EXTENSIONS
                   for item in child.rglob("*")):
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
        files = [directory] if directory.is_file() else sorted(directory.rglob("*"))
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
                    names = {other["name"], _slug(other["name"])}
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
    if unit.get("role") not in {"implementation", "contracts", "shared", "port", "adapter"}:
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


def _authoritative_review(root: Path, config: dict | None, production: list[Path]) -> dict:
    units = (config or {}).get("units") or []
    issues: list[dict] = []
    seen_ids: set[str] = set()
    paths: list[tuple[str, str]] = []
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
                paths.append((unit.get("id", "?"), raw.rstrip("/")))
    for i, (left_id, left) in enumerate(paths):
        for right_id, right in paths[i + 1:]:
            if left_id == right_id:
                continue
            if left == right or left.startswith(right + "/") or right.startswith(left + "/"):
                issues.append({"code": "overlap",
                               "detail": f"Units {left_id!r} and {right_id!r} claim overlapping paths "
                                         f"({left!r}, {right!r})."})
    covered = []
    unowned = []
    for path in production:
        relative = _relative(path, root)
        if any(relative == prefix or relative.startswith(prefix + "/") for _, prefix in paths):
            covered.append(relative)
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
    elif len(covered) == 0 and production:
        status = "stale"
        summary = "The declared unit paths do not cover any current production source."
    elif unowned:
        status = "incomplete"
        summary = f"{len(unowned)} production source file(s) are not covered by the declared map."
    else:
        status = "complete"
        summary = "The declared module map covers all discovered production source and is structurally consistent."
    if status != "complete" and unowned:
        issues.append({"code": "unowned-source",
                       "detail": f"{len(unowned)} production source file(s) are outside the declared units."})
    return {
        "present": config is not None,
        "path": CONFIG_NAME if config is not None else None,
        "status": status,
        "summary": summary,
        "unitCount": len(units) if isinstance(units, list) else 0,
        "modules": sorted({str(unit.get("module")) for unit in units
                           if isinstance(unit, dict) and unit.get("module")}),
        "coveredProduction": len(covered),
        "productionFiles": len(production),
        "issues": issues,
        "unownedPaths": unowned,
        "units": units if isinstance(units, list) else [],
        "classification": "observed" if config is not None else "absence",
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
        "decision": "pending",
    }


def _build_modules(root: Path, candidates: dict[str, dict]) -> tuple[list[dict], list[dict]]:
    modules: list[dict] = []
    for relative, candidate in candidates.items():
        directory = root / relative
        name = _module_name(directory)
        contracts = _contract_paths(root, directory)
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
        module_id = _slug(directory.name)
        modules.append({
            "id": module_id,
            "name": name,
            "status": "candidate",
            "ownership": "inferred",
            "confidence": "low" if not candidate.get("manifests") else "medium",
            "responsibility": ("Observed production code under "
                               f"`{relative}`. Its business responsibility is not inferred from "
                               "the directory name and requires owner confirmation."),
            "implementation": {"paths": [relative], "classification": "observed-layout"},
            "contracts": {"paths": contracts, "classification": "observed" if contracts else "not-identified"},
            "dependencies": [],
            "dataAndConfiguration": [],
            "evidence": evidence,
            "limitations": ("The boundary is a discovery candidate. It does not establish ownership, "
                            "deployment independence or a public contract."),
        })
    return modules, []


def _quality_and_recommendations(root: Path, modules: list[dict], unassigned: list[str],
                                 authoritative: dict) -> tuple[dict, list[dict]]:
    by_id = {module["id"]: module for module in modules}
    graph = {module["id"]: set() for module in modules}
    for module in modules:
        for dependency in module["dependencies"]:
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

    if unassigned:
        add("Unassigned production code",
            f"{len(unassigned)} production source file(s) are outside every candidate boundary.",
            [_line_evidence(root, unassigned[0], 1,
                            "The file was inspected and falls outside every candidate path.")],
            "ACIMA cannot assign a boundary it cannot identify. Leaving these files unowned makes "
            "ownership-dependent checks incomplete or misleading.",
            "Assign each path to an existing candidate module or explicitly declare it as a "
            "composition/entry-point area with an owner.",
            "Every production file has a deliberate owner or an explicit, reviewed exclusion.",
            "Assignment may reveal that the file belongs to a responsibility not represented by the "
            "current candidates; that may require a new boundary or consolidation.",
            classification="required", affected=[],
            requires_user=True)
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
            classification="required", affected=authoritative["modules"],
            requires_user=True)
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
        for dependency in module["dependencies"]:
            if dependency["leaksImplementation"]:
                add("Replace private implementation coupling",
                    f"{module['name']} imports {dependency['module']} through an implementation-"
                    "shaped path.",
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
    for module in modules:
        cross_dependencies = [item for item in module["dependencies"] if item["moduleId"] in by_id]
        if cross_dependencies and not module["contracts"]["paths"]:
            add("Decide the contract boundary",
                f"{module['name']} participates in cross-module imports but has no identified "
                "contract-shaped path.",
                [item for dependency in cross_dependencies for item in dependency["evidence"]],
                "A dependency needs a public shape that is distinguishable from private code.",
                "Confirm whether the existing entry point is the public contract, create an explicit "
                "contract area only if needed, or record why this dependency is internal composition.",
                "Consumers and providers can evolve independently without exposing implementation.",
                "Creating a new folder is not automatically an improvement. Preserve an existing "
                "public API if it already separates contract from implementation.",
                classification="owner-decision", affected=[module["id"]],
                requires_user=True)
    return {"observations": observations, "cycles": cycles,
            "dependencyGraph": {node: sorted(children) for node, children in graph.items()},
            "contractCoverage": sum(bool(module["contracts"]["paths"]) for module in modules)}, recommendations


def discover(root: Path, *, config: dict | None = None) -> dict:
    """Discover the repository and produce a non-authoritative module-map proposal."""
    root = root.resolve()
    if not root.is_dir():
        raise ModuleMapError(f"project does not exist: {root}")
    loaded, error = (config, None) if config is not None else _read_config(root)
    production = _production_files(root)
    authoritative = _authoritative_review(root, loaded, production)
    if error:
        authoritative.update({"status": "inconsistent", "summary": error})
        authoritative["issues"].append({"code": "invalid-config", "detail": error})
    if authoritative["status"] == "complete":
        review = _read_review(root)
        return {
            "schemaVersion": SCHEMA_VERSION,
            "status": "authoritative",
            "proposalId": None,
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "authoritativeMap": authoritative,
            "proposal": None,
            "review": review,
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
    modules, _ = _build_modules(root, candidates)
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
    for key, existing in existing_by_name.items():
        if existing["id"] not in seen:
            merged.append(existing)
    modules = sorted(merged, key=lambda item: item["id"])
    paths = [prefix for module in modules
             for prefix in module["implementation"]["paths"] + module["contracts"]["paths"]]
    unassigned = []
    for path in production:
        relative = _relative(path, root)
        if not any(relative == prefix or relative.startswith(prefix + "/") for prefix in paths):
            unassigned.append(relative)
    for module in modules:
        module["dependencies"] = _import_evidence(root, module, modules)
    quality, recommendations = _quality_and_recommendations(root, modules, unassigned, authoritative)
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
    proposal = {
        "schemaVersion": SCHEMA_VERSION,
        "status": "proposed",
        "basis": basis,
        "classification": "inference",
        "modules": modules,
        "unassigned": [{
            "path": path,
            "reason": "No candidate production boundary covers this file.",
            "classification": "observed",
        } for path in unassigned],
        "quality": quality,
        "recommendations": recommendations,
        "decisions": decisions,
        "confidence": "low" if modules else "low",
        "limitations": [
            "Discovery uses layout, manifests, source presence and observed import lines. It does "
            "not prove business ownership, runtime isolation, deployment independence or public API status.",
            "Project, package, folder and runtime boundaries are signals, not approved modules.",
            "The proposal must be reviewed before it can become an authoritative map.",
        ],
    }
    canonical = json.dumps({key: value for key, value in proposal.items()
                            if key != "schemaVersion"}, sort_keys=True, ensure_ascii=False)
    proposal["proposalId"] = "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return {
        "schemaVersion": SCHEMA_VERSION,
        "status": "proposal_required" if not authoritative["present"] else "proposal_for_incomplete_map",
        "proposalId": proposal["proposalId"],
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "authoritativeMap": authoritative,
        "proposal": proposal,
        "review": _read_review(root),
        "summary": basis,
        "nextDecision": ("Review the proposed boundaries and recommendations. Do not treat them "
                         "as ownership until accepted."),
    }


def _safe_relative(raw: Any) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise ModuleMapError("every modified ownership path must be a non-empty string")
    candidate = PurePosixPath(raw.replace("\\", "/"))
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ModuleMapError(f"ownership path escapes the repository: {raw!r}")
    return candidate.as_posix().rstrip("/")


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
    module_reviews = {str(item.get("id")): item for item in review.get("moduleDecisions", [])
                      if isinstance(item, dict)}
    rec_reviews = {str(item.get("id")): item for item in review.get("recommendationDecisions", [])
                   if isinstance(item, dict)}
    modules = []
    for module in inner.get("modules", []):
        decision = module_reviews.get(module["id"], {})
        choice = decision.get("decision", "defer" if map_decision == "defer" else "accept" if map_decision == "accept" else "defer")
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
    recommendation_results = []
    for recommendation in inner.get("recommendations", []):
        decision = rec_reviews.get(recommendation["id"], {})
        choice = decision.get("decision", "pending")
        if choice not in {"accept", "reject", "defer", "pending"}:
            raise ModuleMapError(f"recommendation {recommendation['id']} has unknown decision {choice!r}")
        updated = dict(recommendation)
        updated["decision"] = choice
        if decision.get("note"):
            updated["decisionNote"] = str(decision["note"]).strip()
        recommendation_results.append(updated)
    accepted = [module for module in modules if module["reviewDecision"] in {"accept", "modify"}]
    undecided = [module["id"] for module in modules if module["reviewDecision"] not in {"accept", "modify"}]
    essential_pending = [rec["id"] for rec in recommendation_results
                         if rec["essential"] and rec["decision"] in {"pending", "defer"}]
    if map_decision == "reject":
        status = "rejected"
    elif map_decision == "defer":
        status = "deferred"
    elif not modules or (not undecided and not essential_pending):
        status = "approved"
    else:
        status = "partially_approved"
    approved_paths = []
    for module in accepted:
        approved_paths.extend(module["implementation"]["paths"])
        approved_paths.extend(module["contracts"]["paths"])
    production = _production_files(root) if root is not None else []
    uncovered = []
    if root is not None:
        for path in production:
            relative = _relative(path, root)
            if not any(relative == prefix or relative.startswith(prefix + "/")
                       for prefix in approved_paths):
                uncovered.append(relative)
    if status == "approved" and (not modules or uncovered or inner.get("unassigned")):
        status = "partially_approved"
    approval = {
        "schemaVersion": SCHEMA_VERSION,
        "proposalId": inner.get("proposalId"),
        "reviewer": str(review["reviewer"]).strip(),
        "reviewedOn": reviewed_on,
        "mapDecision": map_decision,
        "status": status,
        "approvedModules": [module["id"] for module in accepted],
        "undecidedModules": undecided,
        "essentialRecommendationsPending": essential_pending,
        "uncoveredProduction": uncovered,
        "canWriteConfig": status == "approved" and not uncovered,
        "approvedAt": datetime.now(timezone.utc).isoformat(),
        "meaning": ("Approval is explicit and scoped. A partial approval permits only approved "
                    "boundaries; it does not authorize deterministic checks over unowned source."),
    }
    review = {
        "schemaVersion": SCHEMA_VERSION,
        "proposalId": inner.get("proposalId"),
        "status": status,
        "modules": modules,
        "recommendations": recommendation_results,
        "approval": approval,
        "approvedUnits": units_from_approved(accepted),
    }
    if status == "approved":
        try:
            review["config"] = build_config(proposal, review)
        except ModuleMapError:
            pass
    return review


def units_from_approved(modules: list[dict]) -> list[dict]:
    units = []
    for module in modules:
        slug = _slug(module["name"])
        paths = module.get("implementation", {}).get("paths", [])
        contracts = module.get("contracts", {}).get("paths", [])
        if paths:
            units.append({"id": slug, "module": slug, "role": "implementation",
                          "paths": paths, "source": "proposal-approved"})
        if contracts:
            units.append({"id": f"{slug}.contracts", "module": slug, "role": "contracts",
                          "paths": contracts, "source": "proposal-approved"})
    return units


def build_config(proposal: dict, review_result: dict, *, existing: dict | None = None) -> dict:
    approval = review_result.get("approval") or {}
    if not approval.get("canWriteConfig"):
        raise ModuleMapError("the review does not authorize a complete authoritative map")
    units = review_result.get("approvedUnits") or []
    if not units:
        raise ModuleMapError("the approved review contains no units")
    base = dict(existing or {})
    base.update({
        "standard": base.get("standard") or "1.9.0-draft.1",
        "mode": base.get("mode") or "base",
        "language": base.get("language") or "python",
        "level": base.get("level") or "L1",
        "root": base.get("root") or ".",
        "units": units,
        "exclude": base.get("exclude") or ["bin", "obj", "node_modules", "dist", "build",
                                            "target", "tests", "**/__pycache__"],
        "waivers": base.get("waivers") or ".acima/waivers.json",
        "_moduleMapApproval": {
            "proposalId": proposal.get("proposalId"),
            "reviewer": approval.get("reviewer"),
            "reviewedOn": approval.get("reviewedOn"),
            "approvedAt": approval.get("approvedAt"),
            "status": approval.get("status"),
        },
    })
    return base


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


def _language_for(root: Path) -> str:
    counts = {extension: 0 for extension in SOURCE_EXTENSIONS}
    for path in _production_files(root):
        extension = path.suffix.lower()
        if extension in counts:
            counts[extension] += 1
    if counts.get(".cs"):
        return "dotnet"
    if counts.get(".go"):
        return "go"
    if counts.get(".ts") or counts.get(".tsx") or counts.get(".js"):
        return "typescript"
    return "python"


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
            config = build_config(proposal, result, existing=existing)
            if not (existing or {}).get("language"):
                config["language"] = _language_for(root)
            _write_json(root / args.write_config, config)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except ModuleMapError as error:
        print(f"module_map: {error}", file=__import__("sys").stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
