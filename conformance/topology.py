#!/usr/bin/env python3
"""ACIMA service-topology checker.

Implements the twelve `ST` requirements from chapter 11 against a repository
described by `acima.topology.json`. The checker is language-agnostic: it reads
the manifest, project files (`.csproj`, `package.json`, `pyproject.toml`,
`go.mod`) where present, and source imports for the common languages. A
manifest is required because directory names alone cannot tell a contracts
project from an implementation project, or a UI transform from a re-export.

    python3 conformance/topology.py --root . --config acima.topology.json --format json

Findings use the profile namespace `ACIMA-SNNN`, one per ST item:

    S001 ST-1   S002 ST-2   S003 ST-3   S004 ST-4
    S005 ST-5   S006 ST-6   S007 ST-7   S008 ST-8
    S009 ST-9   S010 ST-10  S011 ST-11  S012 ST-12

Exit codes: 0 clean, 1 findings, 2 the manifest or tool could not run.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

PROFILE = "service-topology"
ST_RULES = {
    "ST-1": "ACIMA-S001",
    "ST-2": "ACIMA-S002",
    "ST-3": "ACIMA-S003",
    "ST-4": "ACIMA-S004",
    "ST-5": "ACIMA-S005",
    "ST-6": "ACIMA-S006",
    "ST-7": "ACIMA-S007",
    "ST-8": "ACIMA-S008",
    "ST-9": "ACIMA-S009",
    "ST-10": "ACIMA-S010",
    "ST-11": "ACIMA-S011",
    "ST-12": "ACIMA-S012",
}
SOURCE_SUFFIXES = {".cs", ".ts", ".tsx", ".js", ".mjs", ".py", ".go", ".java"}
PROJECT_FILES = {".csproj", "package.json", "pyproject.toml", "go.mod"}
IGNORED_PARTS = {".git", "bin", "obj", "node_modules", "__pycache__", ".venv", "venv"}
DEPLOY_FILES = {"Dockerfile", "dockerfile", "serverless.yml", "serverless.yaml",
                "k8s.yaml", "k8s.yml", "helmfile.yaml"}
DOMAIN_FORBIDDEN = (
    "DbContext", "EntityFramework", "SQLAlchemy", "psycopg", "database/sql",
    "java.sql", "HttpClient", "fetch(", "express", "fastapi", "Stripe.net",
)
TRANSFORM_REEXPORT = re.compile(
    r"(?:export\s+(?:\*|\{[^}]*\})\s+from\s+['\"]([^'\"]+)['\"]"
    r"|from\s+([^\n]*[Cc]ontracts[^\n]*)\s+import\s+\*"
    r"|global\s+using\s+[^\n]*[Cc]ontracts)"
)


@dataclass(frozen=True)
class Finding:
    rule: str
    severity: str
    message: str
    path: str
    line: int
    evidence: str = ""

    def as_dict(self) -> dict:
        return {"rule": self.rule, "severity": self.severity, "message": self.message,
                "path": self.path, "line": self.line, "evidence": self.evidence}


class Topology:
    def __init__(self, root: Path, config_path: str) -> None:
        self.root = root.resolve()
        self.config_path = config_path
        self.config = json.loads((self.root / config_path).read_text(encoding="utf-8"))
        self.services = self.config.get("services", [])
        self.findings: list[Finding] = []
        self._declared: set[str] = set()

    # -- basic helpers -----------------------------------------------------
    def rel(self, path: Path) -> str:
        return path.resolve().relative_to(self.root).as_posix()

    def resolve(self, rel: str) -> Path:
        return (self.root / rel).resolve()

    def exists(self, rel: str) -> bool:
        return self.resolve(rel).exists()

    def files(self, rel: str, suffixes: set[str] | None = None) -> list[Path]:
        base = self.resolve(rel)
        if not base.exists():
            return []
        out = []
        for path in base.rglob("*"):
            if not path.is_file() or any(part in IGNORED_PARTS for part in path.parts):
                continue
            if suffixes is None or path.suffix in suffixes or path.name in suffixes:
                out.append(path)
        return sorted(out)

    def text(self, path: Path) -> str:
        return path.read_text(encoding="utf-8", errors="replace")

    def add(self, rule: str, message: str, rel: str, line: int = 0, evidence: str = "") -> None:
        self.findings.append(Finding(rule, "error", message, rel, max(line, 0), evidence.strip()[:240]))

    def service_paths(self) -> list[tuple[dict, str]]:
        return [(service, service.get("path", "")) for service in self.services]

    def service_for(self, path: Path | str) -> dict | None:
        target = self.resolve(path) if isinstance(path, str) else path.resolve()
        best: tuple[dict, int] | None = None
        for service in self.services:
            base = self.resolve(service.get("path", ""))
            try:
                target.relative_to(base)
            except ValueError:
                continue
            depth = len(base.parts)
            if best is None or depth > best[1]:
                best = (service, depth)
        return best[0] if best else None

    def declared_dirs(self) -> set[str]:
        if self._declared:
            return self._declared
        for service, _path in self.service_paths():
            for key in ("path", "domain", "domainTests"):
                if service.get(key):
                    self._declared.add(str(self.resolve(service[key])))
            for layer in service.get("layers", []):
                if layer.get("path"):
                    self._declared.add(str(self.resolve(layer["path"])))
                if layer.get("contracts"):
                    self._declared.add(str(self.resolve(layer["contracts"])))
            for vendor in service.get("vendors", []):
                for key in ("adapter", "contracts"):
                    if vendor.get(key):
                        self._declared.add(str(self.resolve(vendor[key])))
        for inter in self.config.get("interService", []):
            if inter.get("path"):
                self._declared.add(str(self.resolve(inter["path"])))
        return self._declared

    def all_source(self) -> list[Path]:
        return [path for path in self.files(".", SOURCE_SUFFIXES)
                if not any(part in {"docs", "skills", "conformance"} for part in path.parts)]

    # -- manifest checks ---------------------------------------------------
    def run(self) -> list[Finding]:
        self.check_st1()
        self.check_st2()
        self.check_st3()
        self.check_st4()
        self.check_st5()
        self.check_st6()
        self.check_st7()
        self.check_st8()
        self.check_st9()
        self.check_st10()
        self.check_st11()
        self.check_st12()
        unique: dict[tuple[str, str, int], Finding] = {}
        for finding in sorted(self.findings, key=lambda f: (f.path, f.line, f.rule)):
            unique.setdefault((finding.rule, finding.path, finding.line), finding)
        return sorted(unique.values(), key=lambda f: (f.path, f.line, f.rule))

    # -- ST-1: one directory per service ----------------------------------
    def check_st1(self) -> None:
        services_dir = self.root / "services"
        declared = {service.get("name"): service for service in self.services}
        if not services_dir.is_dir():
            self.add("ACIMA-S001", "Services must live under services/<Service>/.",
                     self.config_path, 0, "services/ is missing")
            return
        actual = {path.name for path in services_dir.iterdir() if path.is_dir()}
        for name, service in declared.items():
            path = service.get("path", "")
            expected = f"services/{name}"
            if path != expected:
                self.add("ACIMA-S001",
                         f"Service {name} must live at {expected}/, not {path}.",
                         self.config_path, 0, path)
            if not self.exists(path):
                self.add("ACIMA-S001", f"Service directory is missing: {path}.", path, 0)
        for extra in sorted(actual - set(declared)):
            self.add("ACIMA-S001", f"Undeclared service directory: services/{extra}.", f"services/{extra}", 0)

    # -- ST-2: one responsibility, one sentence ---------------------------
    def check_st2(self) -> None:
        for service, path in self.service_paths():
            readme = self.resolve(path) / "README.md"
            if not readme.is_file():
                self.add("ACIMA-S002", f"Service {service.get('name')} has no README.md responsibility.",
                         path, 0)
                continue
            body = self.text(readme)
            match = re.search(r"^##\s+Responsibility\s*$", body, re.MULTILINE)
            if not match:
                self.add("ACIMA-S002", "Add a '## Responsibility' section with one sentence.",
                         self.rel(readme), 0)
                continue
            after = body[match.end():]
            nxt = re.search(r"^##\s+", after, re.MULTILINE)
            section = (after[:nxt.start()] if nxt else after).strip()
            sentence = section.split("\n\n")[0].strip()
            sentences = [part for part in re.split(r"(?<=[.!?])\s+", sentence) if part.strip()]
            if len(sentences) != 1 or len(sentence) < 10:
                self.add("ACIMA-S002",
                         "The responsibility must be exactly one sentence naming one responsibility.",
                         self.rel(readme), body[:match.start()].count("\n") + 1, sentence[:160])

    # -- ST-3: project naming ---------------------------------------------
    def check_st3(self) -> None:
        for service, path in self.service_paths():
            name = service.get("name", "")
            self.check_project_name(service, path, f"{name}", "service directory")
            self.check_project_name(service, service.get("domain", ""), f"{name}.Domain", "domain")
            self.check_project_name(service, service.get("domainTests", ""), f"{name}.Domain.Tests",
                                    "domain tests")
            for layer in service.get("layers", []):
                expected = f"{name}.{layer.get('name', '')}"
                self.check_project_name(service, layer.get("path", ""), expected, "layer")
                if layer.get("contracts"):
                    self.check_project_name(service, layer["contracts"],
                                            f"{expected}.Contracts", "layer contracts")
            for vendor in service.get("vendors", []):
                expected = f"{name}.{vendor.get('name', '')}"
                self.check_project_name(service, vendor.get("adapter", ""), expected, "vendor adapter")
                self.check_project_name(service, vendor.get("contracts", ""),
                                        f"{expected}.Contracts", "vendor contracts")
        for inter in self.config.get("interService", []):
            self.check_project_name(None, inter.get("path", ""), str(inter.get("name", "")),
                                    "inter-service contract")

        for service, path in self.service_paths():
            base = self.resolve(path)
            if not base.is_dir():
                continue
            declared = self.declared_dirs()
            for project in self.files(path, PROJECT_FILES):
                if project.name == "go.mod" and project.parent == base:
                    continue
                if str(project.parent.resolve()) not in declared:
                    self.add("ACIMA-S003",
                             f"Project {self.rel(project)} is not declared in acima.topology.json.",
                             self.rel(project), 0)
                if project.suffix == ".csproj" and project.stem != project.parent.name:
                    self.add("ACIMA-S003",
                             f"Project file {project.name} does not match its directory "
                             f"{project.parent.name}.",
                             self.rel(project), 0)

    def check_project_name(self, service: dict | None, rel: str, expected: str, kind: str) -> None:
        if not rel:
            if service is not None:
                self.add("ACIMA-S003", f"Service {service.get('name')} has no {kind} project.",
                         service.get("path", ""), 0)
            return
        actual = self.resolve(rel).name
        if actual != expected:
            self.add("ACIMA-S003",
                     f"{kind.capitalize()} project must be named {expected}, not {actual}.", rel, 0)

    # -- ST-4: one contracts project per outward-facing layer -------------
    def check_st4(self) -> None:
        owners: dict[str, list[tuple[str, str]]] = {}
        for service in self.services:
            for layer in service.get("layers", []):
                contract = layer.get("contracts")
                if contract:
                    owners.setdefault(contract, []).append((service.get("name", ""), layer.get("name", "")))
                if layer.get("name") in {"Api", "Application"} and not contract:
                    self.add("ACIMA-S004",
                             f"{service.get('name')}.{layer.get('name')} must own its own contracts project.",
                             layer.get("path", ""), 0)
                if layer.get("name") == "Domain" and contract:
                    self.add("ACIMA-S004", "The domain must not own a contracts project.",
                             contract, 0)
        for contract, contract_owners in owners.items():
            if len(contract_owners) > 1:
                self.add("ACIMA-S004",
                         f"Contracts project {contract} is shared by "
                         f"{', '.join(f'{s}.{layer}' for s, layer in contract_owners)}.",
                         contract, 0)

    # -- ST-5: zero references -------------------------------------------
    def contracts(self) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        for service in self.services:
            for layer in service.get("layers", []):
                if layer.get("contracts"):
                    out.append((layer["contracts"], f"{service.get('name')}.{layer.get('name')}"))
            for vendor in service.get("vendors", []):
                if vendor.get("contracts"):
                    out.append((vendor["contracts"], f"{service.get('name')}.{vendor.get('name')}"))
        for inter in self.config.get("interService", []):
            if inter.get("path"):
                out.append((inter["path"], str(inter.get("name", "inter-service"))))
        return out

    def check_st5(self) -> None:
        for contract, label in self.contracts():
            path = self.resolve(contract)
            if not path.exists():
                self.add("ACIMA-S005", f"Contracts project {contract} is missing.", contract, 0)
                continue
            for line, evidence in self.project_references(path):
                self.add("ACIMA-S005",
                         f"{label} has a project or package reference; contracts must reference nothing.",
                         contract, line, evidence)
            for source in self.files(contract, SOURCE_SUFFIXES):
                for line, evidence in self.source_references(source, path):
                    self.add("ACIMA-S005",
                             f"{label} references something outside its own project; contracts must be "
                             f"standalone.", self.rel(source), line, evidence)

    def project_references(self, project: Path) -> list[tuple[int, str]]:
        out: list[tuple[int, str]] = []
        candidates = [project] if project.suffix == ".csproj" else []
        candidates += [path for path in project.glob("*.csproj")] if project.is_dir() else []
        for csproj in dict.fromkeys(candidates):
            if not csproj.is_file():
                continue
            try:
                tree = ET.parse(csproj)
            except ET.ParseError as exc:
                out.append((0, f"unreadable project file: {exc}"))
                continue
            for element in tree.getroot().iter():
                tag = element.tag.rsplit("}", 1)[-1]
                if tag in {"ProjectReference", "PackageReference", "Reference"}:
                    include = element.attrib.get("Include") or element.attrib.get("Update") or tag
                    out.append((0, f"<{tag} Include=\"{include}\">"))
        package = project / "package.json" if project.is_dir() else None
        if package and package.is_file():
            try:
                data = json.loads(self.text(package))
            except json.JSONDecodeError:
                out.append((0, "unreadable package.json"))
                data = {}
            for key in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
                for name in sorted(data.get(key, {})):
                    out.append((0, f"{key}: {name}"))
        pyproject = project / "pyproject.toml" if project.is_dir() else None
        if pyproject and pyproject.is_file():
            body = self.text(pyproject)
            for match in re.finditer(r"^\s*dependencies\s*=\s*\[(.*?)\]", body, re.MULTILINE | re.DOTALL):
                if match.group(1).strip():
                    out.append((body[:match.start()].count("\n") + 1, "pyproject dependencies"))
        gomod = project / "go.mod" if project.is_dir() else None
        if gomod and gomod.is_file():
            for line_no, line in enumerate(self.text(gomod).splitlines(), 1):
                if line.strip().startswith("require ") or (line.startswith("\t") and " v" in line):
                    out.append((line_no, line.strip()))
        return out

    def source_references(self, source: Path, project: Path) -> list[tuple[int, str]]:
        body = self.text(source)
        out: list[tuple[int, str]] = []
        suffix = source.suffix
        project_name = project.name

        if suffix == ".cs":
            for line_no, line in enumerate(body.splitlines(), 1):
                match = re.search(r"^\s*(?:global\s+)?using\s+(?:static\s+)?([\w.]+)\s*;", line)
                if not match:
                    continue
                namespace = match.group(1)
                if namespace == project_name or namespace.startswith(project_name + "."):
                    continue
                if namespace.split(".")[0] == "System":
                    continue
                out.append((line_no, line.strip()))
        elif suffix in {".ts", ".tsx", ".js", ".mjs"}:
            for line_no, line in enumerate(body.splitlines(), 1):
                for spec in re.findall(r"(?:from\s+|require\()['\"]([^'\"]+)['\"]", line):
                    if spec.startswith("node:"):
                        continue
                    if spec.startswith("."):
                        try:
                            target = (source.parent / spec).resolve()
                            target.relative_to(project.resolve())
                        except (ValueError, OSError):
                            out.append((line_no, line.strip()))
                    else:
                        out.append((line_no, line.strip()))
        elif suffix == ".py":
            for line_no, line in enumerate(body.splitlines(), 1):
                match = re.match(r"^\s*(?:from\s+([.\w]+)\s+import|import\s+([.\w]+))", line)
                if not match:
                    continue
                module = match.group(1) or match.group(2) or ""
                if module.startswith("."):
                    depth = len(module) - len(module.lstrip("."))
                    try:
                        target = source.parent
                        for _ in range(depth - 1):
                            target = target.parent
                        target = (target / module.lstrip(".").replace(".", "/")).resolve()
                        target.relative_to(project.resolve())
                    except (ValueError, OSError):
                        out.append((line_no, line.strip()))
                    continue
                top = module.split(".")[0]
                if top in sys.stdlib_module_names or top in project_name:
                    continue
                out.append((line_no, line.strip()))
        elif suffix == ".go":
            for line_no, line in enumerate(body.splitlines(), 1):
                for spec in re.findall(r"\"([^\"]+)\"", line):
                    if "." not in spec.split("/")[0]:
                        continue
                    if project_name in spec:
                        continue
                    out.append((line_no, line.strip()))
        elif suffix == ".java":
            for line_no, line in enumerate(body.splitlines(), 1):
                match = re.match(r"^\s*import\s+(?:static\s+)?([\w.]+)\s*;", line)
                if match and not match.group(1).startswith(("java.", "javax.")):
                    out.append((line_no, line.strip()))
        return out

    # -- ST-6: explicit transforms, no re-exports ------------------------
    def check_st6(self) -> None:
        layer_names: dict[str, dict] = {}
        for service in self.services:
            for layer in service.get("layers", []):
                layer_names[f"{service.get('name')}.{layer.get('name')}"] = layer
        for boundary in self.config.get("boundaries", []):
            caller = boundary.get("caller", "")
            callee = boundary.get("callee", "")
            transform = boundary.get("transform", "")
            caller_contract = boundary.get("callerContract")
            callee_contract = boundary.get("calleeContract")
            if caller not in layer_names or callee not in layer_names:
                self.add("ACIMA-S006",
                         f"Boundary {caller} -> {callee} names an undeclared layer.",
                         self.config_path, 0)
            if not transform or not self.exists(transform) or not self.resolve(transform).is_file():
                self.add("ACIMA-S006",
                         f"Boundary {caller} -> {callee} has no explicit transform file.",
                         self.config_path, 0, transform)
            elif ".Contracts" in self.resolve(transform).name or "contracts" in self.resolve(transform).parts:
                self.add("ACIMA-S006", "A transform must not live inside a contracts project.",
                         transform, 0)
            if caller_contract and caller_contract == callee_contract:
                self.add("ACIMA-S006",
                         f"Boundary {caller} -> {callee} reuses one contracts project on both sides.",
                         self.config_path, 0)

        for service in self.services:
            for layer in service.get("layers", []):
                if layer.get("name") in {"Domain", "Host"}:
                    continue
                for source in self.files(layer.get("path", ""), SOURCE_SUFFIXES):
                    for line_no, line in enumerate(self.text(source).splitlines(), 1):
                        if TRANSFORM_REEXPORT.search(line):
                            self.add("ACIMA-S006",
                                     "A layer must map across a boundary, not re-export another "
                                     "layer's contracts.", self.rel(source), line_no, line.strip())

    # -- ST-7: inter-service contracts name exactly two services ----------
    def check_st7(self) -> None:
        names = {service.get("name") for service in self.services}
        for inter in self.config.get("interService", []):
            name = str(inter.get("name", ""))
            source = inter.get("source")
            target = inter.get("target")
            parts = name.split(".")
            if len(parts) != 2:
                self.add("ACIMA-S007",
                         f"Inter-service contract {name} must name exactly two services, "
                         f"<Source>.<Target>.", self.config_path, 0)
            elif parts[0] not in names or parts[1] not in names:
                self.add("ACIMA-S007",
                         f"Inter-service contract {name} names an unknown service; declare both "
                         f"services before the contract.", self.config_path, 0)
            if source not in names or target not in names:
                self.add("ACIMA-S007", f"{name} names an unknown service.", self.config_path, 0)
            if name != f"{source}.{target}":
                self.add("ACIMA-S007", f"{name} must match its source and target: {source}.{target}.",
                         self.config_path, 0)
            if self.resolve(inter.get("path", "")).name != name:
                self.add("ACIMA-S007", f"Inter-service project directory must be named {name}.",
                         inter.get("path", ""), 0)
            source_path = next((s.get("path", "") for s in self.services
                                if s.get("name") == source), "")
            if source_path and not inter.get("path", "").startswith(source_path.rstrip("/") + "/"):
                self.add("ACIMA-S007", f"{name} must live under its source service {source}/.",
                         inter.get("path", ""), 0)

        for inter in self.config.get("interService", []):
            name = str(inter.get("name", ""))
            allowed = {inter.get("source"), inter.get("target")}
            for source in self.all_source():
                for line_no, line in enumerate(self.text(source).splitlines(), 1):
                    if re.search(rf"(?<![\w.]){re.escape(name)}(?![\w.])", line):
                        owner = self.service_for(source)
                        if owner is None or owner.get("name") not in allowed:
                            self.add("ACIMA-S007",
                                     f"{self.rel(source)} references {name}, but only "
                                     f"{inter.get('source')} and {inter.get('target')} may use it.",
                                     self.rel(source), line_no, line.strip())

    # -- ST-8: vendor isolation -------------------------------------------
    def check_st8(self) -> None:
        for service in self.services:
            for vendor in service.get("vendors", []):
                label = f"{service.get('name')}.{vendor.get('name')}"
                adapter = vendor.get("adapter", "")
                contract = vendor.get("contracts", "")
                if not self.exists(adapter) or not self.exists(contract):
                    self.add("ACIMA-S008", f"{label} needs both an adapter and a contracts project.",
                             adapter or contract, 0)
                    continue
                references = self.project_references(self.resolve(adapter))
                if not any(contract.rstrip("/").split("/")[-1] in evidence for _line, evidence in references):
                    self.add("ACIMA-S008", f"{label} adapter must reference {contract}.",
                             adapter, 0)
                packages = [str(package) for package in vendor.get("packages", [])]
                for package in packages:
                    if not any(package in evidence for _line, evidence in references):
                        self.add("ACIMA-S008", f"{label} adapter must reference the {package} package.",
                                 adapter, 0)
                for source in self.files(service.get("path", ""), SOURCE_SUFFIXES):
                    rel = self.rel(source)
                    if rel.startswith(adapter.rstrip("/") + "/") or rel.startswith(contract.rstrip("/") + "/"):
                        continue
                    body = self.text(source)
                    for package in packages:
                        if package in body:
                            self.add("ACIMA-S008",
                                     f"{package} appears outside {label}; expose a contract and keep the "
                                     f"vendor in the adapter.", rel, 1, package)

    # -- ST-9: domain owns rules, no infrastructure -----------------------
    def check_st9(self) -> None:
        for service in self.services:
            domain = service.get("domain", "")
            sources = self.files(domain, SOURCE_SUFFIXES)
            if not sources:
                self.add("ACIMA-S009", f"Service {service.get('name')} has no domain source.",
                         domain or service.get("path", ""), 0)
                continue
            body = "\n".join(self.text(path) for path in sources)
            for token in DOMAIN_FORBIDDEN:
                if token in body:
                    line = next((i for i, text in enumerate(body.splitlines(), 1) if token in text), 1)
                    self.add("ACIMA-S009",
                             f"The domain must not contain {token}; move it behind a port or adapter.",
                             self.rel(sources[0]), line, token)
            for rule in service.get("businessRules", []):
                rule_id = str(rule.get("id", ""))
                if rule_id and rule_id not in body:
                    self.add("ACIMA-S009",
                             f"Business rule {rule_id} is not traceable in the domain source.",
                             domain, 0, rule_id)

    # -- ST-10: coverage gate and named rule tests ------------------------
    def check_st10(self) -> None:
        for service in self.services:
            name = service.get("name")
            tests = service.get("domainTests", "")
            test_sources = self.files(tests, SOURCE_SUFFIXES)
            if not test_sources:
                self.add("ACIMA-S010", f"{name} has no domain tests.", tests or service.get("path", ""), 0)
            test_body = "\n".join(self.text(path) for path in test_sources)
            coverage = service.get("coverage", {})
            report = coverage.get("report", "")
            if int(coverage.get("line", 0)) < 100 or int(coverage.get("branch", 0)) < 100:
                self.add("ACIMA-S010", "The domain coverage gate must be 100% line and branch.",
                         report or service.get("path", ""), 0)
            if not report or not self.exists(report):
                self.add("ACIMA-S010", f"{name} has no coverage report at {report}.",
                         report or service.get("path", ""), 0)
            elif not self.coverage_is_full(self.resolve(report)):
                self.add("ACIMA-S010", f"{name} coverage report is below 100% line/branch.", report, 0)
            for rule in service.get("businessRules", []):
                test_name = str(rule.get("test", ""))
                if test_name and test_name not in test_body:
                    self.add("ACIMA-S010",
                             f"Business rule {rule.get('id')} has no named test {test_name}.",
                             tests, 0, test_name)

    def coverage_is_full(self, report: Path) -> bool:
        try:
            data = json.loads(self.text(report))
        except (json.JSONDecodeError, OSError):
            return False
        totals = data.get("totals", data)
        line = (totals.get("lines", {}) or {}).get("percent", totals.get("line"))
        branch = (totals.get("branches", {}) or {}).get("percent", totals.get("branch"))
        if line is None and "percent_covered" in totals:
            line = branch = totals["percent_covered"]
        try:
            return float(line) >= 100 and float(branch) >= 100
        except (TypeError, ValueError):
            return False

    # -- ST-11: UI and API share the same workflow -----------------------
    def check_st11(self) -> None:
        for service in self.services:
            workflow = service.get("workflow")
            if not workflow:
                continue
            ui = workflow.get("ui", "")
            api = workflow.get("api", "")
            if not self.exists(ui) or not self.exists(api):
                self.add("ACIMA-S011", f"{service.get('name')} workflow needs existing UI and API files.",
                         ui or api, 0)
                continue
            tokens = list(workflow.get("states", [])) + list(workflow.get("errors", []))
            tokens += [str(item.get("event", "")) for item in workflow.get("transitions", [])]
            tokens = [token for token in dict.fromkeys(tokens) if token]
            ui_body, api_body = self.text(self.resolve(ui)), self.text(self.resolve(api))
            for token in tokens:
                if token not in ui_body:
                    self.add("ACIMA-S011",
                             f"UI is missing workflow token {token}; UI and API must share the workflow.",
                             ui, 0, token)
                if token not in api_body:
                    self.add("ACIMA-S011",
                             f"API is missing workflow token {token}; the API domain enforces the workflow.",
                             api, 0, token)
            service_path = service.get("path", "").rstrip("/") + "/"
            if not api.startswith(service_path) or ".Contracts" in api:
                self.add("ACIMA-S011", "The API workflow must be enforced in the service, not in contracts.",
                         api, 0)

    # -- ST-12: no deployment or vendor SDK outside an adapter/host -------
    def check_st12(self) -> None:
        deployment = [str(package) for package in self.config.get("deploymentPackages", [])]
        for service in self.services:
            name = service.get("name")
            allowed = {layer.get("path", "").rstrip("/") for layer in service.get("layers", [])
                       if layer.get("name") in {"Host", "Infrastructure"}
                       or str(layer.get("name", "")).startswith("Integrations.")}
            allowed |= {vendor.get("adapter", "").rstrip("/") for vendor in service.get("vendors", [])}
            packages = deployment + [str(package) for vendor in service.get("vendors", [])
                                     for package in vendor.get("packages", [])]
            for source in self.files(service.get("path", "")):
                rel = self.rel(source)
                if any(rel.startswith(path + "/") for path in allowed if path):
                    continue
                body = self.text(source)
                for package in packages:
                    if package and package in body:
                        self.add("ACIMA-S012",
                                 f"{package} appears outside an adapter or host in {name}.",
                                 rel, 1, package)
                if source.name in DEPLOY_FILES or source.suffix == ".tf":
                    self.add("ACIMA-S012",
                             f"Deployment file {source.name} belongs in the host or infrastructure layer.",
                             rel, 0)


def main() -> int:
    parser = argparse.ArgumentParser(description="ACIMA service-topology checker")
    parser.add_argument("--root", default=".")
    parser.add_argument("--config", default="acima.topology.json")
    parser.add_argument("--format", choices=("json", "text"), default="text")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    try:
        topology = Topology(root, args.config)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"acima-topology: cannot read {args.config}: {exc}", file=sys.stderr)
        return 2
    if not topology.services:
        print("acima-topology: manifest declares no services", file=sys.stderr)
        return 2

    findings = topology.run()
    if args.format == "json":
        print(json.dumps({"standard": topology.config.get("standard", "1.0.0"),
                          "profile": PROFILE,
                          "findings": [finding.as_dict() for finding in findings]}, indent=2))
    else:
        for finding in findings:
            print(f"{finding.rule}  {finding.severity:<7} {finding.message}\n  {finding.path}:{finding.line}")
            if finding.evidence:
                print(f"  {finding.evidence}")
        print(f"\n{len(findings)} finding(s) in the {PROFILE} profile")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
