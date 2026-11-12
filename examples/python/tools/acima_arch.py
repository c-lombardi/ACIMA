#!/usr/bin/env python3
"""ACIMA reference enforcer for Python.

Implements the 42 automated rules and reports the 14 manual review requirements against the units declared in acima.config.json.
Reads source with `ast`; never imports the product code.

    python3 tools/acima_arch.py --root . --config acima.config.json --format json

Exit codes: 0 clean, 1 unwaived errors, 2 tool failure.
"""
from __future__ import annotations

import argparse
import ast
import fnmatch
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

CATALOG: dict[str, tuple[str, str]] = {
    "ACIMA-D001": ("error", "L1"), "ACIMA-D002": ("error", "L1"), "ACIMA-D003": ("error", "L1"),
    "ACIMA-D004": ("error", "L1"), "ACIMA-D005": ("error", "L1"), "ACIMA-D006": ("error", "L1"),
    "ACIMA-D007": ("error", "L1"), "ACIMA-D008": ("error", "L1"), "ACIMA-D009": ("error", "L1"),
    "ACIMA-D010": ("error", "L1"),
    "ACIMA-D011": ("error", "L1"), "ACIMA-D012": ("error", "L1"),
    "ACIMA-D013": ("warning", "L1"), "ACIMA-D014": ("warning", "L1"),
    "ACIMA-D015": ("warning", "L1"), "ACIMA-D016": ("warning", "L1"), "ACIMA-D017": ("warning", "L1"),
    "ACIMA-L001": ("error", "L1"), "ACIMA-L002": ("error", "L1"), "ACIMA-L003": ("error", "L1"),
    "ACIMA-L004": ("warning", "L1"), "ACIMA-L005": ("warning", "L1"), "ACIMA-L006": ("error", "L1"),
    "ACIMA-L007": ("warning", "L1"),
    "ACIMA-C001": ("error", "L2"), "ACIMA-C002": ("error", "L2"), "ACIMA-C003": ("error", "L2"),
    "ACIMA-C004": ("error", "L2"), "ACIMA-C005": ("error", "L2"), "ACIMA-C006": ("error", "L2"),
    "ACIMA-C007": ("warning", "L2"), "ACIMA-C008": ("error", "L2"),
    "ACIMA-A001": ("error", "L3"), "ACIMA-A002": ("warning", "L3"),
    "ACIMA-A003": ("error", "L3"), "ACIMA-A004": ("warning", "L3"),
    "ACIMA-A005": ("warning", "L3"), "ACIMA-A006": ("warning", "L3"),
    "ACIMA-A007": ("warning", "L3"), "ACIMA-A008": ("warning", "L3"),
    "ACIMA-A009": ("warning", "L3"),
    "ACIMA-A010": ("error", "L3"), "ACIMA-A011": ("error", "L3"),
    "ACIMA-A012": ("error", "L3"), "ACIMA-A013": ("warning", "L3"),
    "ACIMA-A014": ("error", "L3"), "ACIMA-A015": ("error", "L3"),
    "ACIMA-N001": ("warning", "L3"), "ACIMA-N002": ("warning", "L3"),
    "ACIMA-N003": ("warning", "L3"),
    "ACIMA-G001": ("error", "L1"), "ACIMA-G002": ("error", "L1"),
    "ACIMA-G003": ("warning", "L2"), "ACIMA-G004": ("error", "L2"),
    "ACIMA-G005": ("error", "L1"), "ACIMA-G006": ("warning", "L1"),
}
NOT_EXECUTED = {
    "ACIMA-C003": "behaviour versus validation is a semantic judgement",
    "ACIMA-C007": "constructor completeness needs symbol and API analysis",
    "ACIMA-L004": "service-locator APIs are framework-specific",
    "ACIMA-A002": "configuration APIs differ per ecosystem",
    "ACIMA-A004": "version-lock coupling is visible only across published packages",
    "ACIMA-G004": "an API baseline needs a per-language surface format",
    "ACIMA-N003": "semantic naming quality needs human review",
    "ACIMA-C008": "business behavior visibility is a semantic contract review",
    "ACIMA-A010": "effect ownership and commit boundaries require application and operational review",
    "ACIMA-A011": "effect semantics require contract and API review",
    "ACIMA-A012": "outcome truthfulness requires failure, retry and cancellation evidence",
    "ACIMA-A013": "critical-effect evidence requires audit and telemetry inspection",
    "ACIMA-A014": "whether telemetry observes or alters business behaviour needs review",
    "ACIMA-A015": "consistency ownership and guarantees need design review",
}
# Third-party governance: the tier rules only execute when externals is declared.
TIER_RULES = ("ACIMA-L005", "ACIMA-L006", "ACIMA-L007", "ACIMA-D010", "ACIMA-G006")
TIERS = ("platform", "integration", "utility")
ENTRY_FIELDS = ("tier", "owner", "reason", "reviewedOn", "expires")
RANK = {"L1": 1, "L2": 2, "L3": 3}
NAMING_ROLES = {"contracts", "implementation", "adapter", "host", "port", "shared-kernel"}
GENERIC_TYPE_NAMES = {"Helper", "Manager", "Handler", "Processor", "Utility", "Service",
                      "Provider", "Factory", "Common", "Base", "Default", "Generic"}
GENERIC_TYPE_SUFFIXES = ("Helper", "Manager", "Processor", "Utility", "Common", "Default",
                         "Generic")

PERSISTENCE = ("sqlalchemy", "QuerySet", "psycopg", "sqlite3", "db.execute", "IQueryable",
               "DbContext", "EntityManager", "django.db", "asyncpg", "pymongo")
# L001 is about dependency edges. Only importable persistence roots qualify here;
# bare names such as QuerySet or db.execute are handled by the contract rules.
PERSISTENCE_MODULES = ("sqlalchemy", "psycopg", "psycopg2", "sqlite3", "django.db",
                       "asyncpg", "pymongo")
FRAMEWORK = ("flask", "fastapi", "starlette", "django", "http.server", "werkzeug", "celery",
             "requests", "httpx", "aiohttp")
AMBIENT = (r"datetime\.now\b", r"datetime\.utcnow\b", r"date\.today\b", r"time\.time\b",
           r"uuid4\b", r"uuid\.uuid1\b", r"\brandom\.")
SQL = re.compile(r"(?is)\b(?:from|into|update|join)\s+[\"'`]?([a-z][a-z0-9_]*)")
WRITE_SQL = re.compile(r"(?is)\b(?:insert\s+into|update|delete\s+from|join)\s+[\"'`]?([a-z][a-z0-9_]*)")

EXCLUDE_DEFAULT = ["tests", "violations"]


@dataclass(frozen=True)
class Unit:
    id: str
    role: str
    module: str | None
    paths: tuple[str, ...]


@dataclass
class Finding:
    rule: str
    severity: str
    message: str
    path: str
    line: int
    evidence: str = ""
    fingerprint: str = ""
    classification: str = ""

    def as_dict(self) -> dict:
        data = {"rule": self.rule, "severity": self.severity, "message": self.message,
                "path": self.path, "line": self.line, "evidence": self.evidence,
                "fingerprint": self.fingerprint}
        if self.classification:
            data["classification"] = self.classification
        return data


def finding_fingerprint(rule: str, path: str, evidence: str) -> str:
    payload = f"{rule}\0{path}\0{evidence}".encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


class Enforcer:
    def __init__(self, root: Path, config: dict, level: str) -> None:
        self.root = root.resolve()
        self.config = config
        self.level = level.upper()
        self.units = [Unit(u["id"], u["role"], u.get("module"), tuple(u["paths"]))
                      for u in config.get("units", [])]
        self.excludes = list(config.get("exclude", EXCLUDE_DEFAULT))
        self.findings: list[Finding] = []
        self.files: dict[str, ast.Module] = {}
        self.units_of: dict[str, Unit] = {}
        self.source_files = 0
        self.edges: list[tuple[str, str, int, str]] = []
        self.module_names = {u.module for u in self.units if u.module}
        raw_externals = config.get("externals")
        self.externals = raw_externals if isinstance(raw_externals, dict) else None
        self.manifests = [str(path) for path in config.get("manifests", [])]
        self.config_name = "acima.config.json"

    # -- discovery ---------------------------------------------------------
    def rel(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()

    def excluded(self, rel: str) -> bool:
        value = rel.rstrip("/")
        # ``acima/`` is the generated adoption workspace. Its copied tooling and evidence
        # are not product source and must not be assigned to an application module.
        if value == "acima" or value.startswith("acima/"):
            return True
        parts = value.split("/")
        for raw in self.excludes:
            pattern = str(raw).strip().replace("\\", "/")
            if pattern.startswith("./"):
                pattern = pattern[2:]
            pattern = pattern.rstrip("/")
            if not pattern:
                continue
            if any(char in pattern for char in "*?["):
                if fnmatch.fnmatchcase(value, pattern):
                    return True
                continue
            if value == pattern or value.startswith(pattern + "/"):
                return True
            if pattern in parts:
                return True
        return False

    def unit_by_path(self, rel: str) -> Unit | None:
        best: Unit | None = None
        best_len = -1
        for u in self.units:
            for p in u.paths:
                if (rel == p or rel.startswith(p.rstrip("/") + "/")) and len(p) > best_len:
                    best, best_len = u, len(p)
        return best

    def override_unit(self, source: str) -> Unit | None:
        head = "\n".join(source.splitlines()[:3])
        override = re.search(r"acima-unit:\s*([\w.\-]+)", head)
        if not override:
            return None
        token = override.group(1)
        for u in self.units:
            if u.id == token:
                return u
        for u in self.units:
            if u.module == token and u.role == "implementation":
                return u
        if token.endswith(".contracts"):
            for u in self.units:
                if u.module == token.split(".")[0] and u.role == "contracts":
                    return u
        return None

    def unit_for(self, rel: str, source: str) -> Unit | None:
        return self.override_unit(source) or self.unit_by_path(rel)

    def add(self, rule: str, message: str, rel: str, line: int, evidence: str = "",
            classification: str = "") -> None:
        severity, required = CATALOG[rule]
        if RANK[required] > RANK[self.level]:
            return
        evidence = evidence.strip()[:200]
        self.findings.append(Finding(rule, severity, message, rel, max(line, 1), evidence,
                                     finding_fingerprint(rule, rel, evidence), classification))

    # -- parsing -----------------------------------------------------------
    def collect(self) -> None:
        for path in sorted(self.root.rglob("*.py")):
            rel = self.rel(path)
            if self.excluded(rel):
                declared = self.unit_by_path(rel)
                if declared is not None:
                    self.add("ACIMA-G005",
                             f"Declared unit {declared.id} excludes its own source: {rel}.",
                             rel, 1, "exclude overrides unit mapping")
                continue
            source = path.read_text(encoding="utf-8", errors="replace")
            declared = self.unit_by_path(rel)
            unit = self.unit_for(rel, source)
            if declared is not None and unit is not None and unit.id != declared.id:
                self.add("ACIMA-G005",
                         f"Role override changes {rel} from {declared.id} to {unit.id}.",
                         rel, 1, "acima-unit override")
            if unit is None:
                self.add("ACIMA-G005", f"Source file is not part of any declared unit: {rel}", rel, 1)
                continue
            self.units_of[rel] = unit
            try:
                self.files[rel] = ast.parse(source)
            except SyntaxError:
                self.add("ACIMA-G005", f"File could not be parsed: {rel}", rel, 1)
        self.source_files = len(self.files)

    def resolve(self, module: str, level: int, current: str) -> str | None:
        if level:
            base = current.split("/")[:-1]
            if level > 1:
                base = base[: -(level - 1)]
            parts = base + [p for p in module.split(".") if p]
        else:
            parts = [p for p in module.split(".") if p]
        for prefix in ("", "src"):
            rel = "/".join(([prefix] if prefix else []) + parts)
            for candidate in (f"{rel}.py", f"{rel}/__init__.py"):
                if (self.root / candidate).exists():
                    return candidate
        return None

    def imports(self, rel: str) -> list[tuple[str, int, str, list[str], int]]:
        out: list[tuple[str, int, str, list[str], int]] = []
        for node in ast.walk(self.files[rel]):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    out.append((alias.name, node.lineno, f"import {alias.name}",
                                [alias.name.split(".")[0]], 0))
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                names = [a.name for a in node.names]
                evidence = f"from {'.' * node.level}{module} import {', '.join(names)}"
                out.append((module, node.lineno, evidence, names, node.level))
            elif isinstance(node, ast.Call):
                func = node.func
                name = (func.attr if isinstance(func, ast.Attribute)
                        else func.id if isinstance(func, ast.Name) else "")
                if name not in {"import_module", "__import__"}:
                    continue
                if not node.args or not isinstance(node.args[0], ast.Constant):
                    continue
                module = node.args[0].value
                if not isinstance(module, str) or not module:
                    continue
                out.append((module, node.lineno, f'{name}("{module}")',
                            [module.split(".")[0]], 0))
        return out

    # -- rules -------------------------------------------------------------
    def check_edges(self) -> None:
        for rel in self.files:
            u_from = self.units_of[rel]
            for module, line, evidence, names, level in self.imports(rel):
                target = self.resolve(module, level, rel)
                if target is None:
                    top = module.split(".")[0]
                    if top in sys.stdlib_module_names or not top:
                        continue
                    if u_from.role == "contracts":
                        self.add("ACIMA-D004",
                                 f"contracts unit {u_from.id} depends on third-party package: {top}",
                                 rel, line, evidence)
                    elif u_from.role == "shared-kernel":
                        self.add("ACIMA-D007",
                                 f"shared kernel depends on a third-party package: {top}",
                                 rel, line, evidence)
                    continue
                if target not in self.units_of:
                    continue
                u_to = self.units_of[target]
                self.edges.append((rel, target, line, evidence))
                if u_from.role in ("host", "tooling", "test"):
                    continue
                if u_from.role == "shared-kernel":
                    if u_to.role != "shared-kernel":
                        self.add("ACIMA-D007",
                                 f"shared kernel references {u_to.id}; the kernel must be a leaf.",
                                 rel, line, evidence)
                    continue
                if u_from.role in ("contracts", "port"):
                    if u_to.role == "implementation":
                        self.add("ACIMA-D002",
                                 f"{u_from.id} references the implementation unit {u_to.id}.",
                                 rel, line, evidence)
                    elif u_to.role == "contracts" and u_to.module != u_from.module:
                        self.add("ACIMA-D003",
                                 f"{u_from.id} references {u_to.id}; contracts must be independent.",
                                 rel, line, evidence)
                    elif u_to.role == "host":
                        self.add("ACIMA-D006",
                                 f"{u_from.id} references the host unit; contracts must not know "
                                 f"how they are hosted.", rel, line, evidence)
                    continue
                if u_from.role == "implementation":
                    if u_to.role == "host":
                        self.add("ACIMA-D006", f"{u_from.id} references the host unit.",
                                 rel, line, evidence)
                    elif u_to.role == "implementation" and u_to.module != u_from.module:
                        self.add("ACIMA-D001",
                                 f"Module {u_from.module} imports the implementation unit {u_to.id} "
                                 f"(expected {u_to.module}.contracts).", rel, line, evidence)
                        if any(n.startswith("_") and not n.startswith("__") for n in names):
                            self.add("ACIMA-D009",
                                     f"{u_from.module} imports a private type from module {u_to.module}.",
                                     rel, line, evidence)
                        public = self.public_classes(target)
                        if public:
                            self.add("ACIMA-L003",
                                     f"implementation unit {u_to.id} publishes the public type "
                                     f"{', '.join(sorted(public))} outside the module", target, 1)
        self.check_cycles()
        self.check_transitive()

    def public_classes(self, rel: str) -> set[str]:
        tree = self.files.get(rel)
        if tree is None:
            return set()
        return {n.name for n in tree.body
                if isinstance(n, ast.ClassDef) and not n.name.startswith("_")}

    def module_edges(self) -> dict[str, set[str]]:
        graph: dict[str, set[str]] = {m: set() for m in self.module_names if m}
        for rel, target, _line, _ev in self.edges:
            a, b = self.units_of[rel], self.units_of[target]
            if a.module and b.module and a.module != b.module:
                graph.setdefault(a.module, set()).add(b.module)
        return graph

    def check_cycles(self) -> None:
        graph = self.module_edges()
        state: dict[str, int] = {}
        stack: list[str] = []
        reported: set[frozenset[str]] = set()

        def visit(node: str) -> None:
            state[node] = 1
            stack.append(node)
            for nxt in sorted(graph.get(node, ())):
                if state.get(nxt, 0) == 0:
                    visit(nxt)
                elif state.get(nxt) == 1:
                    cycle = stack[stack.index(nxt):] + [nxt]
                    key = frozenset(cycle)
                    if key not in reported:
                        reported.add(key)
                        rel = next((r for r, t, _l, _e in self.edges
                                    if self.units_of[r].module == node
                                    and self.units_of[t].module == nxt), sorted(self.files)[0])
                        self.add("ACIMA-D005",
                                 "Circular module dependency: " + " -> ".join(cycle), rel, 1)
            stack.pop()
            state[node] = 2

        for node in sorted(graph):
            if state.get(node, 0) == 0:
                visit(node)

    def check_transitive(self) -> None:
        graph = self.module_edges()
        seen: set[tuple[str, str]] = set()
        for rel, target, line, evidence in self.edges:
            a, b = self.units_of[rel], self.units_of[target]
            if not a.module or a.role in ("host", "tooling", "test"):
                continue
            if b.module == a.module:
                # an intra-module reference cannot create a transitive reach for that module
                continue
            reachable: set[str] = set()
            frontier = [b.module] if b.module else []
            while frontier:
                node = frontier.pop()
                for nxt in graph.get(node, ()):
                    if nxt not in reachable and nxt != a.module:
                        reachable.add(nxt)
                        frontier.append(nxt)
            for module in sorted(reachable):
                forbidden = (module != a.module and a.role in ("contracts", "port", "implementation")
                             and not (a.role == "implementation" and module == a.module))
                if forbidden and (a.id, module) not in seen:
                    seen.add((a.id, module))
                    self.add("ACIMA-D008",
                             f"{a.id} reaches the implementation unit {module} transitively "
                             f"through {b.id}.", rel, line, evidence)

    def check_contracts(self) -> None:
        for rel, tree in self.files.items():
            unit = self.units_of[rel]
            if unit.role not in ("contracts", "port"):
                continue
            source = (self.root / rel).read_text(encoding="utf-8", errors="replace")
            for token in AMBIENT:
                if re.search(token, source):
                    self.add("ACIMA-C004",
                             f"contracts unit {unit.id} reads ambient state.", rel,
                             self.line_of(source, token), token)
            for token in PERSISTENCE:
                if token in source:
                    self.add("ACIMA-C005",
                             f"contracts unit {unit.id} exposes a persistence concern ({token}).",
                             rel, self.line_of(source, token), token)
            for token in FRAMEWORK:
                if re.search(rf"(?<![\w.]){re.escape(token)}(?![\w])", source):
                    self.add("ACIMA-L002",
                             f"contracts unit {unit.id} exposes a framework type ({token}).",
                             rel, self.line_of(source, token), token)
            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    self.check_contract_class(rel, node)

    def line_of(self, source: str, token: str) -> int:
        needle = token.replace("\\", "").replace("(", "").replace(")", "").replace(".", ".")
        for i, line in enumerate(source.splitlines(), 1):
            if needle in line:
                return i
        return 1

    @staticmethod
    def annotation_text(annotation: ast.expr) -> str:
        return ast.unparse(annotation).strip("'\"")

    def check_annotation(self, rel: str, unit: Unit, name: str,
                         annotation: ast.expr, line: int) -> None:
        text = self.annotation_text(annotation)
        if re.search(r"\b(list|dict|set|List|Dict|Set|OrderedDict|defaultdict)\b", text):
            self.add("ACIMA-C002",
                     f"Contract type {name} exposes a mutable collection ({text}).",
                     rel, line, text)
        if re.search(r"\b(Any|object)\b", text) or text in ("dict", "list"):
            self.add("ACIMA-C006",
                     f"Contract type {name} has an untyped member ({text}).", rel, line, text)
        for module in sorted(self.module_names):
            if module == unit.module:
                continue
            if re.search(rf"\b{re.escape(module)}\.contracts\b", text):
                self.add("ACIMA-D003",
                         f"contracts unit {unit.id} references {module}.contracts in an annotation; "
                         "contracts must be independent.", rel, line, text)
            elif re.search(rf"\b{re.escape(module)}\.impl\b", text):
                self.add("ACIMA-D002",
                         f"contracts unit {unit.id} references the implementation {module}.impl in an "
                         "annotation.", rel, line, text)

    def check_contract_class(self, rel: str, node: ast.ClassDef) -> None:
        unit = self.units_of[rel]
        bases = {getattr(b, "id", getattr(b, "attr", "")) for b in node.bases}
        documented = bool(ast.get_docstring(node))
        if bases & {"Protocol", "Enum", "Exception"} or node.name.endswith("Error"):
            if not documented:
                self.add("ACIMA-G003", f"Contract type {node.name} has no documentation.",
                         rel, node.lineno)
            return
        decorators = " ".join(ast.unparse(d) for d in node.decorator_list)
        frozen = "frozen=True" in decorators.replace(" ", "")
        if "dataclass" not in decorators:
            annotated = any(isinstance(n, ast.AnnAssign) for n in node.body)
            assigns = any(isinstance(n, ast.Assign)
                          and not isinstance(n.value, (ast.Constant, ast.Name, ast.Attribute))
                          for n in node.body)
            init = next((n for n in node.body
                         if isinstance(n, ast.FunctionDef) and n.name == "__init__"), None)
            init_mutation = False
            if init is not None:
                for child in ast.walk(init):
                    if isinstance(child, ast.Assign):
                        if any(isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name)
                               and t.value.id == "self" for t in child.targets):
                            init_mutation = True
                            if isinstance(child.value, (ast.List, ast.Dict, ast.Set)) or (
                                    isinstance(child.value, ast.Call)
                                    and isinstance(child.value.func, ast.Name)
                                    and child.value.func.id in {"list", "dict", "set"}):
                                self.add("ACIMA-C001",
                                         f"Contract type {node.name} mutates state in __init__.",
                                         rel, child.lineno, ast.unparse(child))
                    elif isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Attribute):
                        if isinstance(child.target.value, ast.Name) and child.target.value.id == "self":
                            init_mutation = True
                            self.check_annotation(rel, unit, node.name, child.annotation, child.lineno)
            if annotated or assigns or init_mutation:
                self.add("ACIMA-C001",
                         f"Contract type {node.name} exposes mutable state "
                         f"(not an immutable dataclass).", rel, node.lineno)
        elif not frozen:
            self.add("ACIMA-C001",
                     f"Contract type {node.name} is a dataclass without frozen=True.",
                     rel, node.lineno)
        for item in node.body:
            if isinstance(item, ast.AnnAssign):
                self.check_annotation(rel, unit, node.name, item.annotation, item.lineno)
            elif isinstance(item, ast.Assign) and isinstance(item.value, (ast.List, ast.Dict, ast.Set)):
                self.add("ACIMA-C001",
                         f"Contract type {node.name} has mutable class-level state.",
                         rel, item.lineno, ast.unparse(item))
        if not documented:
            self.add("ACIMA-G003", f"Contract type {node.name} has no documentation.", rel, node.lineno)

    def check_layering(self) -> None:
        for rel in self.files:
            unit = self.units_of[rel]
            if unit.role != "implementation" or "/infrastructure/" in rel:
                continue
            if "/tests/" in rel or "/test/" in rel:
                continue
            for module, line, evidence, _names, level in self.imports(rel):
                if level:
                    continue
                # A declared integration library is governed by L005/L007, not the L001 token list.
                if self.tier_of(module) == "integration":
                    continue
                if not any(module == root or module.startswith(root + ".")
                           for root in PERSISTENCE_MODULES):
                    continue
                self.add("ACIMA-L001",
                         f"{unit.id} imports infrastructure ({module}) outside infrastructure/.",
                         rel, line, evidence)

    def check_sql(self) -> None:
        for rel, tree in self.files.items():
            unit = self.units_of[rel]
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    for table in set(SQL.findall(node.value) + WRITE_SQL.findall(node.value)):
                        prefix = table.split("_")[0]
                        if prefix in self.module_names and prefix != unit.module:
                            self.add("ACIMA-A001",
                                     f"{unit.id} queries the {prefix} schema ({table}); each module "
                                     f"owns its own tables.", rel, node.lineno, table)

    def check_statics(self) -> None:
        declarations: dict[str, tuple[str, int, Unit]] = {}
        for rel, tree in self.files.items():
            unit = self.units_of[rel]
            if unit.role not in ("implementation", "shared-kernel"):
                continue
            for node in tree.body:
                if isinstance(node, ast.Assign):
                    names = [t.id for t in node.targets if isinstance(t, ast.Name)]
                    mutable = isinstance(node.value, (ast.Dict, ast.List, ast.Set))
                elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                    names = [node.target.id]
                    mutable = isinstance(node.value, (ast.Dict, ast.List, ast.Set))
                else:
                    continue
                if mutable:
                    for name in names:
                        declarations.setdefault(name, (rel, node.lineno, unit))
        for rel in self.files:
            for _module, _line, _evidence, names, _level in self.imports(rel):
                for name in names:
                    if name in declarations:
                        decl_rel, line, owner = declarations[name]
                        if self.units_of[rel].module != owner.module:
                            self.add("ACIMA-A003",
                                     f"{self.units_of[rel].id} imports and may mutate the static "
                                     f"state {name} owned by {owner.id}.", decl_rel, line, name)

    def check_waivers(self) -> list[dict]:
        waivers: list[dict] = []
        path = self.config.get("waivers")
        if not path:
            return waivers
        file = self.root / path
        if not file.exists():
            self.add("ACIMA-G001", f"waivers file not found: {path}", path, 1)
            return waivers
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            self.add("ACIMA-G001", f"waivers file is not valid JSON: {path}", path, 1)
            return waivers
        required = ("rule", "scope", "owner", "reason", "expires", "reviewedOn")
        for i, waiver in enumerate(data.get("waivers", []), 1):
            missing = [k for k in required if not str(waiver.get(k, "")).strip()]
            if missing:
                self.add("ACIMA-G001",
                         f"Waiver for {waiver.get('rule', '?')} is missing: {', '.join(missing)}.",
                         path, i)
                continue
            if waiver["rule"] not in CATALOG:
                self.add("ACIMA-G001", f"Waiver names an unknown rule: {waiver['rule']}.", path, i)
                continue
            try:
                expired = date.fromisoformat(waiver["expires"]) < date.today()
            except ValueError:
                self.add("ACIMA-G001",
                         f"Waiver expiry is not an ISO date: {waiver['expires']}.", path, i)
                continue
            if expired:
                self.add("ACIMA-G002",
                         f"Waiver for {waiver['rule']} expired on {waiver['expires']} "
                         f"(owner: {waiver['owner']}).", path, i)
            elif not str(waiver.get("fingerprint", "")).strip():
                self.add("ACIMA-G001",
                         f"Waiver for {waiver['rule']} has no finding fingerprint; "
                         "a broad waiver can hide future findings.", path, i)
            else:
                waivers.append(waiver)
        return waivers

    def apply_waivers(self, waivers: list[dict]) -> None:
        kept: list[Finding] = []
        for finding in self.findings:
            unit = self.units_of.get(finding.path)
            waived = any(
                w["rule"] == finding.rule
                and w.get("fingerprint") == finding.fingerprint
                and (
                    (unit is not None and w["scope"] == f"unit:{unit.id}")
                    or (w["scope"].startswith("path:") and fnmatch.fnmatch(finding.path, w["scope"][5:]))
                    or (unit is not None and w["scope"] == f"module:{unit.module}")
                )
                for w in waivers
            )
            if not waived:
                kept.append(finding)
        self.findings = kept

    # -- third-party tiers -------------------------------------------------
    def external_entry(self, spec: str) -> tuple[str, dict] | None:
        """Resolve a specifier to its externals entry, by package name and declared specifiers."""
        if not isinstance(self.externals, dict) or not spec:
            return None
        candidates = {value.replace("-", "_") for value in
                      (spec, spec.split("/")[0], spec.split(".")[0]) if value}
        best: tuple[str, dict] | None = None
        for name, raw in self.externals.items():
            entry = raw if isinstance(raw, dict) else {}
            extra = entry.get("specifiers") if isinstance(entry.get("specifiers"), list) else []
            known = {str(value).replace("-", "_") for value in (name, *extra)}
            if not candidates & known:
                continue
            if best is None or len(name) > len(best[0]):
                best = (name, entry)
        return best

    def tier_of(self, spec: str) -> str | None:
        found = self.external_entry(spec)
        return str(found[1].get("tier", "")).strip() if found else None

    @staticmethod
    def vendor_tokens(name: str, entry: dict) -> set[str]:
        """The vendor type names to look for: the declared list, or a derivation from the name.

        A declared list is authoritative. Deriving from the package name is a fallback, and it is
        deliberately not combined with the declaration: a package called `monaco-editor` yields
        `MonacoEditor`, which is the adapter's own class name far more often than a vendor type.
        """
        declared = entry.get("types") if isinstance(entry.get("types"), list) else []
        tokens = {str(token) for token in declared if str(token).strip()}
        if not tokens:
            leaf = name.split("/")[-1].split(".")[-1]
            tokens = {name, leaf,
                      "".join(part.capitalize() for part in re.split(r"[^A-Za-z0-9]+", leaf) if part)}
        return {token for token in tokens if len(token) >= 3}

    def manifest_dependencies(self) -> list[tuple[str, int, str]]:
        out: list[tuple[str, int, str]] = []
        candidates = self.manifests or [
            name for name in ("package.json", "pyproject.toml", "requirements.txt")
            if (self.root / name).is_file()]
        for rel in candidates:
            path = self.root / rel
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if rel.endswith("package.json"):
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    continue
                for name in (data.get("dependencies") or {}):
                    out.append((rel, self.line_of(text, f'"{name}"'), str(name)))
            elif rel.endswith(".txt"):
                for number, line in enumerate(text.splitlines(), 1):
                    value = line.strip()
                    if not value or value.startswith(("#", "-")):
                        continue
                    name = re.split(r"[<>=!~\[\]; ]", value)[0]
                    if name:
                        out.append((rel, number, name))
            elif rel.endswith("pyproject.toml"):
                inside = False
                for number, line in enumerate(text.splitlines(), 1):
                    if re.match(r"\s*dependencies\s*=\s*\[", line):
                        inside = True
                    if inside:
                        for match in re.finditer(r"[\"']([A-Za-z0-9_.-]+)", line):
                            out.append((rel, number, match.group(1)))
                        if "]" in line.split("dependencies", 1)[-1]:
                            inside = False
        return out

    def check_externals(self) -> None:
        """L005, L006, L007, D010 and G006: the declared third-party tiers."""
        if not isinstance(self.externals, dict):
            return
        config_rel = self.config_name
        config_file = self.root / self.config_name
        config_text = (config_file.read_text(encoding="utf-8", errors="replace")
                       if config_file.is_file() else "")
        entry_line = lambda name: self.line_of(config_text, f'"{name}"') if config_text else 1
        adapter_units = {u.id: u for u in self.units if u.role == "adapter"}
        port_units = {u.id: u for u in self.units if u.role == "port"}
        declared_adapters: set[str] = set()

        for name, raw in self.externals.items():
            entry = raw if isinstance(raw, dict) else {}
            missing = [field for field in ENTRY_FIELDS
                       if not str(entry.get(field, "")).strip()]
            if missing:
                self.add("ACIMA-G001",
                         f"externals entry {name} is missing: {', '.join(missing)}.",
                         config_rel, entry_line(name), name)
                continue
            tier = str(entry.get("tier", "")).strip()
            if tier not in TIERS:
                self.add("ACIMA-G001",
                         f"externals entry {name} has unknown tier {tier!r}; expected "
                         f"{', '.join(TIERS)}.", config_rel, entry_line(name), name)
                continue
            if tier != "integration":
                continue
            adapter = str(entry.get("adapter", "")).strip()
            port = str(entry.get("port", "")).strip()
            if not adapter or not port:
                gap = "adapter" if not adapter else "port"
                self.add("ACIMA-L006",
                         f"integration entry {name} declares no {gap}; an adapter without a port "
                         "is an unguarded vendor import.", config_rel, entry_line(name), name)
                continue
            if adapter not in adapter_units:
                self.add("ACIMA-G001",
                         f"externals entry {name} names adapter {adapter}, which is not a "
                         "declared adapter unit.", config_rel, entry_line(name), name)
                continue
            if port not in port_units:
                self.add("ACIMA-G001",
                         f"externals entry {name} names port {port}, which is not a declared "
                         "port unit.", config_rel, entry_line(name), name)
                continue
            declared_adapters.add(adapter)

        for unit_id in sorted(adapter_units):
            if unit_id in declared_adapters:
                continue
            first = sorted(rel for rel, unit in self.units_of.items() if unit.id == unit_id)
            self.add("ACIMA-L006",
                     f"adapter unit {unit_id} is declared in no externals entry; it has no port "
                     "and no reviewed vendor.", first[0] if first else config_rel, 1, unit_id)

        for rel in sorted(self.files):
            unit = self.units_of[rel]
            for module, line, evidence, _names, _level in self.imports(rel):
                found = self.external_entry(module)
                if found is None:
                    continue
                name, entry = found
                if unit.role == "port":
                    self.add("ACIMA-D010",
                             f"port unit {unit.id} imports the third-party package {module}; a "
                             "port declares the capability, never the vendor.", rel, line, evidence)
                    continue
                if str(entry.get("tier", "")).strip() != "integration" or unit.role == "adapter":
                    continue
                declared = str(entry.get("adapter", "")).strip()
                self.add("ACIMA-L005",
                         f"{unit.id} imports the integration library {name}; only its adapter "
                         f"({declared or 'undeclared'}) may import it, everyone else takes the "
                         "port.", rel, line, evidence)

        # One adapter may cover a vendor and its wrapper (`monaco-editor` and
        # `@monaco-editor/react`), and both can declare the same worker type. Report one finding
        # per line, named after the shortest declaring package: the vendor, not its wrapper.
        claimed: set[tuple[str, int]] = set()
        for name, raw in sorted(self.externals.items(),
                                key=lambda item: (len(item[0]), item[0])):
            entry = raw if isinstance(raw, dict) else {}
            tier = str(entry.get("tier", "")).strip()
            if tier not in ("integration", "utility"):
                continue
            tokens = self.vendor_tokens(name, entry)
            for rel in sorted(self.files):
                unit = self.units_of[rel]
                if unit.role == "adapter":
                    continue
                source = (self.root / rel).read_text(encoding="utf-8", errors="replace")
                for number, text in enumerate(source.splitlines(), 1):
                    if (rel, number) in claimed:
                        continue
                    stripped = text.strip()
                    if not stripped or stripped.startswith(("#", "//", "*")):
                        continue
                    if stripped.startswith(("import ", "from ")):
                        continue
                    # A vendor type is usually qualified (`monaco_editor.IEditor`), so only a
                    # word character excludes a match; a dot must not.
                    hit = next((token for token in sorted(tokens)
                                if re.search(rf"(?<!\w){re.escape(token)}(?!\w)", text)),
                               None)
                    if hit is None:
                        continue
                    claimed.add((rel, number))
                    if unit.role == "port":
                        self.add("ACIMA-D010",
                                 f"port unit {unit.id} names the vendor type {hit} from {name}.",
                                 rel, number, hit)
                    elif tier == "utility" and unit.role not in ("contracts",):
                        continue
                    else:
                        self.add("ACIMA-L007",
                                 f"{unit.id} names the vendor type {hit} from {name} outside its "
                                 "adapter.", rel, number, hit)

        declared = {name.replace("-", "_").lower() for name in self.externals}
        for rel, line, package in self.manifest_dependencies():
            if package.replace("-", "_").lower() in declared:
                continue
            self.add("ACIMA-G006",
                     f"manifest dependency {package} has no externals entry: declare its tier, "
                     "owner and review date.", rel, line, package)
        for name, raw in self.externals.items():
            entry = raw if isinstance(raw, dict) else {}
            expires = str(entry.get("expires", "")).strip()
            if not expires:
                continue
            try:
                expired = date.fromisoformat(expires) < date.today()
            except ValueError:
                self.add("ACIMA-G001",
                         f"externals entry {name} has a non-ISO expiry: {expires}.",
                         config_rel, entry_line(name), name)
                continue
            if expired:
                self.add("ACIMA-G006",
                         f"externals entry {name} passed its review date on {expires}; renew or "
                         "remove the dependency.", config_rel, entry_line(name), name)

    # -- explicit inputs ---------------------------------------------------
    EXPLICIT_ROLES = ("implementation", "host", "adapter", "port")

    @staticmethod
    def _decorator_name(node: ast.expr) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        if isinstance(node, ast.Call):
            return Enforcer._decorator_name(node.func)
        return ""

    @staticmethod
    def _optional_parameters(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.arg]:
        """Parameters a caller may omit: a positional default or a keyword-only default."""
        args = node.args
        positional = [*args.posonlyargs, *args.args]
        defaults = [None] * (len(positional) - len(args.defaults)) + list(args.defaults)
        optional = [arg for arg, default in zip(positional, defaults) if default is not None]
        optional += [arg for arg, default in zip(args.kwonlyargs, args.kw_defaults)
                     if default is not None]
        return optional

    def check_explicit_inputs(self) -> None:
        """D011 and D012: required inputs must not hide behind optional parameters.

        Scope is the declared behaviour units. Contracts are data with compatibility semantics
        (C007 and the additive-evolution rules); a default there is a versioning decision, not a
        concealed dependency. A nullable parameter without a default is *required* and is not a
        finding: the caller must pass null explicitly, which is the distinction the chapter draws.
        """
        for rel in sorted(self.files):
            unit = self.units_of[rel]
            if unit.role not in self.EXPLICIT_ROLES:
                continue
            tree = self.files[rel]
            parents = {child: parent for parent in ast.walk(tree)
                       for child in ast.iter_child_nodes(parent)}
            lines = (self.root / rel).read_text(encoding="utf-8", errors="replace").splitlines()
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if any(self._decorator_name(item) == "overload" for item in node.decorator_list):
                    continue
                is_constructor = node.name == "__init__"
                if not is_constructor and node.name.startswith("__") and node.name.endswith("__"):
                    continue
                optional = self._optional_parameters(node)
                if not optional:
                    continue
                in_class = isinstance(parents.get(node), ast.ClassDef)
                for arg in optional:
                    evidence = (lines[arg.lineno - 1].strip()
                                if 0 < arg.lineno <= len(lines) else "")
                    if in_class and is_constructor:
                        self.add("ACIMA-D011",
                                 f"{unit.id} constructs with the optional input {arg.arg}; a "
                                 "dependency the component needs must be required at construction.",
                                 rel, arg.lineno, evidence)
                    else:
                        self.add("ACIMA-D012",
                                 f"{unit.id} lets a caller omit {arg.arg} in {node.name}(); if "
                                 "that omission changes behaviour, require the decision at the "
                                 "call site.", rel, arg.lineno, evidence)

    @staticmethod
    def _named_callable_parameters(node: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[list[str], int]:
        """Return keyword-capable positional parameters and the positional-only count."""
        positional_only = [item.arg for item in node.args.posonlyargs]
        positional = [item.arg for item in node.args.args]
        all_positional = positional_only + positional
        if node.name in {"__init__", "__new__"} and all_positional:
            all_positional = all_positional[1:]
            positional_only = positional_only[1:] if positional_only else []
        elif all_positional and all_positional[0] in {"self", "cls"}:
            all_positional = all_positional[1:]
            positional_only = positional_only[1:] if positional_only else []
        return all_positional, len(positional_only)

    def check_named_call_arguments(self) -> None:
        """D017: label calls only when the receiving signature can be resolved statically.

        Resolve same-file functions, classes, typed receivers, constructor-created fields,
        and module-level constructed instances. Never infer a destination from a method name
        alone: unresolved external and dynamic receivers remain outside the automated subset.
        """
        for rel in sorted(self.files):
            unit = self.units_of[rel]
            if unit.role not in self.EXPLICIT_ROLES:
                continue
            tree = self.files[rel]
            parents = {child: parent for parent in ast.walk(tree)
                       for child in ast.iter_child_nodes(parent)}
            module_functions: dict[str, tuple[list[str], int] | None] = {}
            class_methods: dict[str, dict[str, tuple[list[str], int] | None]] = {}
            class_constructors: dict[str, tuple[list[str], int] | None] = {}
            class_fields: dict[str, dict[str, str]] = {}
            module_instances: dict[str, str] = {}

            def remember(target: dict, name: str, signature: tuple[list[str], int]) -> None:
                if name in target and target[name] != signature:
                    target[name] = None
                else:
                    target[name] = signature

            def annotation_type(node: ast.expr | None) -> str | None:
                if isinstance(node, ast.Name):
                    return node.id
                if isinstance(node, ast.Subscript):
                    return annotation_type(node.value)
                if isinstance(node, ast.Attribute):
                    return node.attr
                return None

            for definition in (item for item in ast.walk(tree)
                               if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))):
                signature = self._named_callable_parameters(definition)
                parent = parents.get(definition)
                if isinstance(parent, ast.ClassDef):
                    remember(class_methods.setdefault(parent.name, {}), definition.name, signature)
                    if definition.name == "__init__":
                        class_constructors[parent.name] = signature
                        fields = class_fields.setdefault(parent.name, {})
                        for statement in ast.walk(definition):
                            if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Attribute):
                                if isinstance(statement.target.value, ast.Name) and statement.target.value.id == "self":
                                    inferred = annotation_type(statement.annotation)
                                    if inferred:
                                        fields[statement.target.attr] = inferred
                            elif isinstance(statement, ast.Assign) and isinstance(statement.value, ast.Call):
                                if isinstance(statement.value.func, ast.Name):
                                    for target in statement.targets:
                                        if (isinstance(target, ast.Attribute)
                                                and isinstance(target.value, ast.Name)
                                                and target.value.id == "self"):
                                            fields[target.attr] = statement.value.func.id
                else:
                    remember(module_functions, definition.name, signature)

            for statement in tree.body:
                if isinstance(statement, ast.Assign) and isinstance(statement.value, ast.Call):
                    if isinstance(statement.value.func, ast.Name):
                        for target in statement.targets:
                            if isinstance(target, ast.Name):
                                module_instances[target.id] = statement.value.func.id
                elif isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
                    inferred = annotation_type(statement.annotation)
                    if inferred:
                        module_instances[statement.target.id] = inferred

            lines = (self.root / rel).read_text(encoding="utf-8", errors="replace").splitlines()

            def containing_function(node: ast.AST):
                parent = parents.get(node)
                while parent is not None:
                    if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        return parent
                    parent = parents.get(parent)
                return None

            def receiver_type(receiver: ast.expr, call: ast.Call) -> str | None:
                if isinstance(receiver, ast.Name):
                    if receiver.id in module_instances:
                        return module_instances[receiver.id]
                    scope = containing_function(call)
                    if scope:
                        arguments = [*scope.args.posonlyargs, *scope.args.args, *scope.args.kwonlyargs]
                        for argument in arguments:
                            if argument.arg == receiver.id:
                                return annotation_type(argument.annotation)
                        for item in ast.walk(scope):
                            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                                if item.target.id == receiver.id:
                                    return annotation_type(item.annotation)
                            if isinstance(item, ast.Assign) and isinstance(item.value, ast.Call):
                                if isinstance(item.value.func, ast.Name) and any(
                                    isinstance(target, ast.Name) and target.id == receiver.id
                                    for target in item.targets
                                ):
                                    return item.value.func.id
                    return None
                if isinstance(receiver, ast.Attribute) and isinstance(receiver.value, ast.Name):
                    if receiver.value.id in {"self", "cls"}:
                        parent = parents.get(call)
                        while parent is not None and not isinstance(parent, ast.ClassDef):
                            parent = parents.get(parent)
                        if isinstance(parent, ast.ClassDef):
                            return class_fields.get(parent.name, {}).get(receiver.attr)
                return None

            for call in (item for item in ast.walk(tree) if isinstance(item, ast.Call)):
                expression = call.func
                if isinstance(expression, ast.Name):
                    leaf = expression.id
                    signature = module_functions.get(leaf)
                    if signature is None:
                        signature = class_constructors.get(leaf)
                elif isinstance(expression, ast.Attribute):
                    leaf = expression.attr
                    receiver = expression.value
                    if isinstance(receiver, ast.Name) and receiver.id in {"self", "cls"}:
                        parent = parents.get(call)
                        while parent is not None and not isinstance(parent, ast.ClassDef):
                            parent = parents.get(parent)
                        signature = class_methods.get(parent.name, {}).get(leaf) if isinstance(parent, ast.ClassDef) else None
                    else:
                        type_name = receiver_type(receiver, call)
                        signature = class_methods.get(type_name, {}).get(leaf) if type_name else None
                else:
                    continue
                if not signature:
                    continue
                parameters, positional_only_count = signature
                unlabeled = []
                for index, argument in enumerate(call.args):
                    if index < positional_only_count:
                        continue
                    if index >= len(parameters):
                        break
                    unlabeled.append(f"{parameters[index]}={ast.unparse(argument)}")
                if unlabeled:
                    line = getattr(call, "lineno", 1)
                    evidence = lines[line - 1].strip() if 0 < line <= len(lines) else ast.unparse(call)
                    self.add(
                        "ACIMA-D017",
                        f"{unit.id} calls {leaf}() with unlabeled arguments; label every value: "
                        + ", ".join(unlabeled) + ".",
                        rel, line, evidence,
                    )

    # -- composition and injection -----------------------------------------
    COMPOSITION_ROLES = ("implementation", "host", "adapter")
    DYNAMIC_DISCOVERY = frozenset({
        "pkgutil.walk_packages", "pkgutil.iter_modules", "importlib.import_module",
        "__import__", "autodiscover", "auto_register", "scan_packages", "register_all",
    })
    INJECTED_ANNOTATIONS = frozenset({"Provide", "Inject", "Autowired"})

    @staticmethod
    def _annotation_name(node: ast.expr) -> str:
        if isinstance(node, ast.Subscript):
            node = node.value
        if isinstance(node, ast.Attribute):
            return node.attr
        if isinstance(node, ast.Name):
            return node.id
        return ""

    def check_composition(self) -> None:
        """D013/D014: construction is explicit; dependencies arrive at construction.

        D013 is deliberately limited to the host: that is where registration and discovery
        belong, so a dynamic scan there is the mechanism that hides the graph. D014 applies to
        module-owned components (implementation and adapter) and to host-defined entry points;
        a framework may activate them, but their required dependencies must still be declared.
        Service-locator calls remain L004's review concern, not a duplicate D014 finding.
        """
        for rel in sorted(self.files):
            unit = self.units_of[rel]
            lines = (self.root / rel).read_text(encoding="utf-8", errors="replace").splitlines()
            seen: set[int] = set()
            if unit.role == "host":
                for node in ast.walk(self.files[rel]):
                    if not isinstance(node, ast.Call):
                        continue
                    name = self._call_name(node.func)
                    if name not in self.DYNAMIC_DISCOVERY:
                        continue
                    line = getattr(node, "lineno", 1)
                    if line in seen:
                        continue
                    seen.add(line)
                    evidence = lines[line - 1].strip() if 0 < line <= len(lines) else ""
                    self.add("ACIMA-D013",
                             f"composition host {unit.id} discovers components with {name}; "
                             "register and construct each module-owned component explicitly.",
                             rel, line, evidence)
            if unit.role not in self.COMPOSITION_ROLES:
                continue
            for node in ast.walk(self.files[rel]):
                if not isinstance(node, ast.ClassDef):
                    continue
                for member in node.body:
                    if not isinstance(member, ast.AnnAssign):
                        continue
                    name = self._annotation_name(member.annotation)
                    if name not in self.INJECTED_ANNOTATIONS:
                        continue
                    line = member.lineno
                    if line in seen:
                        continue
                    seen.add(line)
                    evidence = lines[line - 1].strip() if 0 < line <= len(lines) else ""
                    self.add("ACIMA-D014",
                             f"{unit.id} receives a dependency through the injected field "
                             f"{getattr(member.target, 'id', 'field')}; declare it in the "
                             "constructor and supply it from the composition boundary.",
                             rel, line, evidence)

    # -- functional capture ------------------------------------------------
    FUNCTIONAL_ROLES = ("implementation", "adapter")
    FUNCTIONAL_TOKENS = frozenset({
        "repository", "repositories", "repo", "service", "services", "client",
        "clients", "gateway", "gateways", "adapter", "adapters", "logger",
        "logging", "config", "configuration", "settings", "store", "stores",
        "database", "db", "connection", "connections", "session", "provider",
        "providers", "bus", "queue", "publisher", "producer", "consumer",
        "auth", "authorization", "security", "clock", "cache", "registry",
        "locator", "container", "resource", "resources",
    })
    PARTIAL_FUNCTIONS = frozenset({"partial", "functools.partial"})

    @staticmethod
    def _functional_name(name: str) -> bool:
        snake = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name).lower()
        return any(token in Enforcer.FUNCTIONAL_TOKENS
                   for token in re.split(r"[^a-z0-9]+", snake))

    @staticmethod
    def _scope_parts(node: ast.AST) -> tuple[set[str], set[str], list[ast.Name]]:
        """Return parameters, local bindings and direct loads for one lexical scope."""
        params: set[str] = set()
        locals_: set[str] = set()
        loads: list[ast.Name] = []
        args = getattr(node, "args", None)
        if args is not None:
            for arg in [*args.posonlyargs, *args.args, *args.kwonlyargs]:
                params.add(arg.arg)
            if args.vararg:
                params.add(args.vararg.arg)
            if args.kwarg:
                params.add(args.kwarg.arg)

        def walk(child: ast.AST) -> None:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda,
                                  ast.ClassDef)):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    locals_.add(child.name)
                return
            if isinstance(child, ast.Name):
                if isinstance(child.ctx, ast.Store):
                    locals_.add(child.id)
                elif isinstance(child.ctx, ast.Load):
                    loads.append(child)
                return
            if isinstance(child, ast.arg):
                params.add(child.arg)
                return
            if isinstance(child, (ast.Import, ast.ImportFrom)):
                for alias in child.names:
                    locals_.add(alias.asname or alias.name.split(".")[0])
                return
            for grandchild in ast.iter_child_nodes(child):
                walk(grandchild)

        body = getattr(node, "body", [])
        if isinstance(body, list):
            for statement in body:
                walk(statement)
        elif isinstance(body, ast.AST):
            walk(body)
        return params, locals_, loads

    @staticmethod
    def _dependency_exprs(node: ast.AST) -> list[str]:
        names: list[str] = []
        for child in ast.walk(node):
            if isinstance(child, ast.Name) and Enforcer._functional_name(child.id):
                names.append(child.id)
            elif isinstance(child, ast.Attribute) and Enforcer._functional_name(child.attr):
                names.append(child.attr)
        return names

    def _outer_binding(self, node: ast.AST, name: str, parents: dict[ast.AST, ast.AST],
                       module_bindings: set[str]) -> str:
        parent = parents.get(node)
        while parent is not None:
            if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                params, locals_, _ = self._scope_parts(parent)
                if name in params:
                    return "parameter"
                if name in locals_:
                    return "local"
            elif isinstance(parent, ast.Module):
                if name in module_bindings:
                    return "module"
            parent = parents.get(parent)
        return "unbound"

    def check_functional_capture(self) -> None:
        """D015: a closure must not silently capture a module-owned dependency.

        A dependency declared by an enclosing *parameter* is visible: that is the curried form.
        A module binding or an enclosing local is a capture. Pure closures over constants and
        transformations are untouched, and inline callbacks are analysed as their own scope.
        """
        for rel in sorted(self.files):
            unit = self.units_of[rel]
            if unit.role not in self.FUNCTIONAL_ROLES:
                continue
            tree = self.files[rel]
            parents = {child: parent for parent in ast.walk(tree)
                       for child in ast.iter_child_nodes(parent)}
            module_bindings = self._scope_parts(tree)[1]
            lines = (self.root / rel).read_text(encoding="utf-8", errors="replace").splitlines()
            seen: set[tuple[str, int]] = set()
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                    continue
                params, locals_, loads = self._scope_parts(node)
                for load in loads:
                    name = load.id
                    if name in params or name in locals_ or not self._functional_name(name):
                        continue
                    binding = self._outer_binding(node, name, parents, module_bindings)
                    if binding not in ("local", "module"):
                        continue
                    key = (name, load.lineno)
                    if key in seen:
                        continue
                    seen.add(key)
                    evidence = lines[load.lineno - 1].strip() if 0 < load.lineno <= len(lines) else ""
                    self.add("ACIMA-D015",
                             f"{unit.id} captures the module-owned dependency {name} from an "
                             "enclosing scope; pass it as a parameter or supply it at the "
                             "composition boundary.", rel, load.lineno, evidence)

    def check_partial_application(self) -> None:
        """D016: pre-binding a dependency belongs at the composition boundary."""
        for rel in sorted(self.files):
            unit = self.units_of[rel]
            if unit.role not in self.FUNCTIONAL_ROLES:
                continue
            lines = (self.root / rel).read_text(encoding="utf-8", errors="replace").splitlines()
            for node in ast.walk(self.files[rel]):
                if not isinstance(node, ast.Call) or self._call_name(node.func) not in self.PARTIAL_FUNCTIONS:
                    continue
                for argument in node.args[1:]:
                    names = self._dependency_exprs(argument)
                    if not names:
                        continue
                    evidence = lines[node.lineno - 1].strip() if 0 < node.lineno <= len(lines) else ""
                    self.add("ACIMA-D016",
                             f"{unit.id} partially applies the module-owned dependency "
                             f"{names[0]} inside a component; bind it at the composition "
                             "boundary or keep it as a parameter.", rel, node.lineno, evidence)
                    break

    # -- lifecycle and state ownership --------------------------------------
    LIFECYCLE_ROLES = ("host",)
    LIFETIME_ADDERS = {"add_singleton": "shared", "add_scoped": "scoped",
                       "add_transient": "transient"}
    LIFETIME_ALIASES = {
        "singleton": "shared", "shared": "shared", "application": "shared",
        "process": "shared", "scoped": "scoped", "request": "scoped",
        "operation": "transient", "transient": "transient", "prototype": "transient",
    }
    MUTABLE_CONSTRUCTORS = frozenset({"list", "dict", "set", "defaultdict", "OrderedDict"})

    @staticmethod
    def _class_stateless(node: ast.ClassDef) -> bool:
        """No instance fields at all: the conservative shared-service shape."""
        for child in ast.walk(node):
            if isinstance(child, ast.Attribute) and isinstance(child.ctx, ast.Store) \
                    and isinstance(child.value, ast.Name) and child.value.id == "self":
                return False
        return True

    @staticmethod
    def _class_mutable(node: ast.ClassDef) -> bool:
        """A class-level or instance-level mutable container is a state signal."""
        for child in ast.walk(node):
            value = None
            targets: list[ast.expr] = []
            if isinstance(child, ast.Assign):
                value = child.value
                targets = list(child.targets)
            elif isinstance(child, ast.AnnAssign) and child.value is not None:
                value = child.value
                targets = [child.target]
            if value is None:
                continue
            if isinstance(value, ast.Call):
                name = Enforcer._call_name(value.func).split(".")[-1]
                if name not in Enforcer.MUTABLE_CONSTRUCTORS:
                    continue
            elif not isinstance(value, (ast.List, ast.Dict, ast.Set)):
                continue
            for target in targets:
                if isinstance(target, ast.Attribute):
                    if isinstance(target.value, ast.Name) and target.value.id == "self":
                        return True
                elif isinstance(target, ast.Name):
                    return True
        return False

    def _class_index(self) -> dict[str, tuple[str, ast.ClassDef]]:
        found: dict[str, list[tuple[str, ast.ClassDef]]] = {}
        for rel, tree in self.files.items():
            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    found.setdefault(node.name, []).append((rel, node))
        return {name: items[0] for name, items in found.items() if len(items) == 1}

    @staticmethod
    def _constructor_dependencies(node: ast.ClassDef) -> set[str]:
        deps: set[str] = set()
        for member in node.body:
            if not isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                    or member.name != "__init__":
                continue
            for arg in [*member.args.posonlyargs, *member.args.args]:
                if arg.arg == "self" or arg.annotation is None:
                    continue
                name = Enforcer._annotation_name(arg.annotation)
                if name:
                    deps.add(name)
        return deps

    def _registration(self, node: ast.Call) -> tuple[str, str] | None:
        name = self._call_name(node.func).split(".")[-1]
        target = ""
        lifetime = self.LIFETIME_ADDERS.get(name, "")
        if name == "register" and node.args and isinstance(node.args[0], ast.Name):
            target = node.args[0].id
            for keyword in node.keywords:
                if keyword.arg in ("lifetime", "scope", "lifecycle") \
                        and isinstance(keyword.value, ast.Constant) \
                        and isinstance(keyword.value.value, str):
                    lifetime = self.LIFETIME_ALIASES.get(keyword.value.value.lower(), "")
        elif name in self.LIFETIME_ADDERS and node.args \
                and isinstance(node.args[0], ast.Name):
            target = node.args[0].id
        if not target or lifetime not in ("shared", "scoped", "transient"):
            return None
        return target, lifetime

    def check_lifecycle(self) -> None:
        """A007/A008/A009: lifecycle and shared state are deliberate.

        This reads explicit host registrations. It does not infer a container graph, and it does
        not treat a mutable field as proof of a race: A009 identifies an ownership question for a
        shared component. Resource cleanup, thread safety and tenant isolation remain review items.
        """
        classes = self._class_index()
        for rel in sorted(self.files):
            unit = self.units_of[rel]
            if unit.role not in self.LIFECYCLE_ROLES:
                continue
            lines = (self.root / rel).read_text(encoding="utf-8", errors="replace").splitlines()
            registrations: list[tuple[str, str, int]] = []
            for node in ast.walk(self.files[rel]):
                if isinstance(node, ast.Call):
                    registration = self._registration(node)
                    if registration:
                        registrations.append((*registration, node.lineno))
            lifetimes = {target: lifetime for target, lifetime, _line in registrations}
            for target, lifetime, line in registrations:
                entry = classes.get(target)
                if entry is None:
                    continue
                cls_rel, cls = entry
                evidence = lines[line - 1].strip() if 0 < line <= len(lines) else ""
                if lifetime == "transient" and self._class_stateless(cls):
                    self.add("ACIMA-A007",
                             f"{unit.id} registers the stateless shared service {target} as transient; "
                             "share it at the longest appropriate lifetime.", rel, line, evidence)
                if lifetime != "shared":
                    continue
                if self._class_mutable(cls):
                    self.add("ACIMA-A009",
                             f"{unit.id} shares {target}, which owns mutable state; give that "
                             "state an explicit owner, isolation boundary and concurrency policy.",
                             rel, line, evidence)
                for dependency in sorted(self._constructor_dependencies(cls)):
                    if lifetimes.get(dependency) == "scoped":
                        self.add("ACIMA-A008",
                                 f"{unit.id} shares {target}, which captures the scoped dependency "
                                 f"{dependency}; shorten the lifetime or resolve it at the "
                                 "correct scope boundary.", rel, line, evidence)

    # -- values and configuration ------------------------------------------
    CONFIG_READ_ROLES = ("implementation", "adapter")
    VALUE_ROLES = ("implementation", "adapter", "host")
    OPERATIONAL_TOKENS = frozenset({
        "timeout", "timeouts", "retry", "retries", "limit", "limits",
        "threshold", "thresholds", "ttl", "interval", "intervals", "batch",
        "rate", "rates", "retention", "capacity", "delay", "quota",
        "backoff", "concurrency", "attempts", "workers", "pagesize",
        "endpoint", "endpoints", "url", "urls", "uri", "host", "hostname",
        "port", "queue", "topic", "bucket", "minimum", "minimums",
        "maximum", "maximums", "duration", "durations", "expiry", "expiration",
        "deadline", "window", "windows", "grace", "heartbeat", "poll",
        "discount", "tax", "fee", "fees", "eligibility", "nonce", "salt",
        "signature", "secret", "secrets", "password", "passwords",
        "credential", "credentials",
    })
    CONFIGURATION_TOKENS = frozenset({
        "endpoint", "endpoints", "url", "urls", "uri", "host", "hostname",
        "port", "queue", "topic", "bucket", "region", "environment", "deployment",
    })
    SAFE_VALUE_CALLS = frozenset({
        "range", "enumerate", "zip", "len", "int", "float", "str", "bool",
        "list", "dict", "set", "tuple", "print", "super", "isinstance",
        "issubclass", "getattr", "setattr", "hasattr",
    })

    @staticmethod
    def _call_name(node: ast.expr) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            owner = Enforcer._call_name(node.value)
            return f"{owner}.{node.attr}" if owner else node.attr
        return ""

    @staticmethod
    def _operational_name(name: str) -> bool:
        snake = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name).lower()
        return any(token in Enforcer.OPERATIONAL_TOKENS
                   for token in re.split(r"[^a-z0-9]+", snake))

    @classmethod
    def _value_category(cls, name: str) -> str:
        snake = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name).lower()
        if re.search(r"(?:^|_)(?:secret|password|passwd|credential|credentials|nonce|salt)(?:_|$)", snake) \
                or re.search(r"(?:private|api|signing|access)_key(?:_|$)", snake) \
                or re.search(r"(?:auth|access|refresh)_token(?:_|$)", snake):
            return "secret"
        tokens = set(re.split(r"[^a-z0-9]+", snake))
        if tokens & cls.CONFIGURATION_TOKENS:
            return "configuration"
        return "value"

    @staticmethod
    def _literal(node: ast.AST) -> str | None:
        if isinstance(node, ast.Constant) and not isinstance(node.value, bool) \
                and isinstance(node.value, (int, float, str)):
            return repr(node.value)[:80]
        return None

    @staticmethod
    def _target_name(target: ast.expr) -> str:
        if isinstance(target, ast.Name):
            return target.id
        if isinstance(target, ast.Attribute):
            return target.attr
        return ""

    @staticmethod
    def _parents(tree: ast.Module) -> dict[ast.AST, ast.AST]:
        parents: dict[ast.AST, ast.AST] = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                parents[child] = parent
        return parents

    @staticmethod
    def _param_names(arguments: ast.arguments) -> list[str]:
        names = [arg.arg for arg in arguments.posonlyargs + arguments.args]
        if names and names[0] in ("self", "cls"):
            names = names[1:]
        return names

    def _callables(self, tree: ast.Module) -> dict[str, list[str] | None]:
        """Local callables whose positional parameters give a receiving name."""
        result: dict[str, list[str] | None] = {}

        def remember(name: str, params: list[str]) -> None:
            if name not in result:
                result[name] = params
            elif result[name] != params:
                result[name] = None

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                remember(node.name, self._param_names(node.args))
            elif isinstance(node, ast.ClassDef):
                init = next((item for item in node.body
                             if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                             and item.name == "__init__"), None)
                if init is not None:
                    remember(node.name, self._param_names(init.args))
        return result

    @staticmethod
    def _is_immutable_declaration(name: str, target: ast.expr, node: ast.AST) -> bool:
        if not isinstance(target, ast.Name):
            return False
        if name.isupper():
            return True
        if isinstance(node, ast.AnnAssign):
            return bool(re.search(r"\bFinal\b", Enforcer.annotation_text(node.annotation)))
        return False

    def _add_value_finding(self, unit: Unit, rel: str, lines: list[str], name: str,
                           line: int, kind: str) -> None:
        if not (0 < line <= len(lines)):
            return
        category = self._value_category(name)
        if category == "secret":
            message = (f"{unit.id} declares a secret-looking literal in {name}; resolve it through "
                       "the secret mechanism and never commit or log the value.")
        elif category == "configuration":
            message = (f"{unit.id} declares {name} as a source literal; classify it as a stable "
                       "code-owned constant or as deployment/runtime configuration resolved and "
                       "validated at a composition boundary.")
        elif kind == "mutable":
            message = (f"{unit.id} declares the meaningful value {name} mutably; use an immutable "
                       "constant, readonly field or immutable value object, or document why mutation "
                       "is genuinely required.")
        elif kind == "property":
            message = (f"{unit.id} assigns the meaningful value {name} through a mutable property; "
                       "prefer an immutable declaration or a readonly value object owned by the type.")
        else:
            message = (f"{unit.id} embeds a meaningful value in {name}; declare it once as an "
                       "immutable constant in the owning file or type, or supply it explicitly from "
                       "the appropriate configuration boundary.")
        self.add("ACIMA-A006", message, rel, line, lines[line - 1].strip(), "candidate")

    def _check_duplicate_values(self, lines_by_rel: dict[str, list[str]],
                                declarations: list[tuple[str, str, str, int, Unit]]) -> None:
        groups: dict[tuple[str, str, str], list[tuple[str, str, int, Unit]]] = {}
        for name, literal, path, line, unit in declarations:
            key = (unit.module or path, re.sub(r"[^a-z0-9]", "", name.lower()), literal)
            groups.setdefault(key, []).append((name, path, line, unit))
        for items in groups.values():
            if len(items) < 2:
                continue
            items.sort(key=lambda item: (item[1], item[2]))
            first = items[0]
            for name, path, line, unit in items[1:]:
                lines = lines_by_rel[path]
                if not (0 < line <= len(lines)):
                    continue
                if path == first[1]:
                    owner = "the owning type or file"
                else:
                    owner = f"the highest common owner in module {unit.module or 'this scope'}"
                self.add("ACIMA-A006",
                         f"{unit.id} declares {name} with the same apparent meaning and literal "
                         f"value as {first[1]}:{first[2]}; confirm semantic identity and one "
                         f"declaration at {owner} before consolidating.",
                         path, line, lines[line - 1].strip(), "candidate")

    def check_configuration(self) -> None:
        """A005: configuration is resolved at a composition boundary, not discovered."""
        for rel in sorted(self.files):
            unit = self.units_of[rel]
            if unit.role not in self.CONFIG_READ_ROLES:
                continue
            lines = (self.root / rel).read_text(encoding="utf-8", errors="replace").splitlines()
            for node in ast.walk(self.files[rel]):
                line = getattr(node, "lineno", 1)
                access = ""
                if isinstance(node, ast.Attribute) and node.attr == "environ":
                    access = "the process environment"
                elif isinstance(node, ast.Call) and self._call_name(node.func) in (
                        "getenv", "os.getenv"):
                    key = ""
                    if node.args and isinstance(node.args[0], ast.Constant) \
                            and isinstance(node.args[0].value, str):
                        key = f" {node.args[0].value}"
                    access = f"the environment key{key}"
                if not access:
                    continue
                evidence = lines[line - 1].strip() if 0 < line <= len(lines) else ""
                self.add("ACIMA-A005",
                         f"{unit.id} reads {access} directly; resolve it at the composition "
                         "root and pass the value into the component.",
                         rel, line, evidence)

    def check_operational_values(self) -> None:
        """A006: meaningful values have one immutable, reviewable owner.

        The scanner reports syntactic candidates. It does not prove semantic equivalence,
        decide the correct configuration category, or rewrite declarations.
        """
        lines_by_rel: dict[str, list[str]] = {}
        declarations: list[tuple[str, str, str, int, Unit]] = []
        for rel in sorted(self.files):
            unit = self.units_of[rel]
            if unit.role not in self.VALUE_ROLES:
                continue
            tree = self.files[rel]
            lines = (self.root / rel).read_text(encoding="utf-8", errors="replace").splitlines()
            lines_by_rel[rel] = lines
            parents = self._parents(tree)
            callables = self._callables(tree)

            for node in ast.walk(tree):
                if isinstance(node, (ast.Assign, ast.AnnAssign)):
                    value = node.value
                    literal = self._literal(value) if value is not None else None
                    if literal is None:
                        continue
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    for target in targets:
                        name = self._target_name(target)
                        if not name or not self._operational_name(name):
                            continue
                        if self._is_immutable_declaration(name, target, node):
                            category = self._value_category(name)
                            if category != "value":
                                self._add_value_finding(unit, rel, lines, name, node.lineno,
                                                        "inline")
                            else:
                                declarations.append((name, literal, rel, node.lineno, unit))
                        else:
                            kind = "property" if isinstance(target, ast.Attribute) else "mutable"
                            self._add_value_finding(unit, rel, lines, name, node.lineno, kind)
                elif isinstance(node, ast.Call):
                    call_name = self._call_name(node.func).split(".")[-1]
                    if call_name in self.SAFE_VALUE_CALLS:
                        continue
                    params = callables.get(call_name)
                    for index, argument in enumerate(node.args):
                        if isinstance(argument, ast.Starred) or params is None \
                                or index >= len(params):
                            continue
                        receiving = params[index]
                        if receiving and self._operational_name(receiving) \
                                and self._literal(argument) is not None:
                            self._add_value_finding(unit, rel, lines, receiving,
                                                    argument.lineno, "inline")
                    for keyword in node.keywords:
                        if keyword.arg and self._operational_name(keyword.arg) \
                                and self._literal(keyword.value) is not None:
                            self._add_value_finding(unit, rel, lines, keyword.arg,
                                                    keyword.lineno, "inline")
                elif isinstance(node, ast.Compare):
                    left = node.left
                    name = (left.id if isinstance(left, ast.Name)
                            else left.attr if isinstance(left, ast.Attribute) else "")
                    if name and not name.isupper() and self._operational_name(name) \
                            and any(self._literal(item) is not None for item in node.comparators):
                        self._add_value_finding(unit, rel, lines, name, node.lineno, "inline")
                elif isinstance(node, ast.Return) and node.value is not None:
                    if self._literal(node.value) is None:
                        continue
                    parent = parents.get(node)
                    while parent is not None and not isinstance(
                            parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        parent = parents.get(parent)
                    if parent is not None and self._operational_name(parent.name):
                        self._add_value_finding(unit, rel, lines, parent.name,
                                                node.lineno, "inline")

        self._check_duplicate_values(lines_by_rel, declarations)

    def check_naming(self) -> None:
        """N001/N002: language convention and generic responsibility names."""
        for rel in sorted(self.files):
            unit = self.units_of[rel]
            if unit.role not in NAMING_ROLES:
                continue
            lines = (self.root / rel).read_text(encoding="utf-8", errors="replace").splitlines()
            for node in ast.walk(self.files[rel]):
                if not isinstance(node, ast.ClassDef):
                    continue
                line = getattr(node, "lineno", 1)
                evidence = lines[line - 1].strip() if 0 < line <= len(lines) else ""
                name = node.name
                if not re.fullmatch(r"_?[A-Z][A-Za-z0-9]*", name):
                    self.add("ACIMA-N001",
                             f"{unit.id} declares the type {name} without the Python "
                             "PascalCase type-name convention.", rel, line, evidence)
                if name in GENERIC_TYPE_NAMES or name.endswith(GENERIC_TYPE_SUFFIXES):
                    self.add("ACIMA-N002",
                             f"{unit.id} names the type {name} after a generic role; name the "
                             "responsibility or domain concept instead.", rel, line, evidence)

    # -- run ---------------------------------------------------------------
    def run(self) -> list[Finding]:
        self.collect()
        self.check_edges()
        self.check_contracts()
        self.check_layering()
        self.check_sql()
        self.check_statics()
        self.check_explicit_inputs()
        self.check_named_call_arguments()
        self.check_composition()
        self.check_functional_capture()
        self.check_partial_application()
        self.check_lifecycle()
        self.check_naming()
        self.check_configuration()
        self.check_operational_values()
        self.check_externals()
        self.apply_waivers(self.check_waivers())
        unique: dict[tuple[str, str, int], Finding] = {}
        for f in sorted(self.findings, key=lambda f: (f.path, f.line, f.rule)):
            unique.setdefault((f.rule, f.path, f.line), f)
        self.findings = sorted(unique.values(), key=lambda f: (f.path, f.line, f.rule))
        return self.findings


def main() -> int:
    parser = argparse.ArgumentParser(description="ACIMA architecture enforcer (Python)")
    parser.add_argument("--root", default=".")
    parser.add_argument("--config", default="acima.config.json")
    parser.add_argument("--format", choices=("json", "text"), default="text")
    parser.add_argument("--level", default=None)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    try:
        config = json.loads((root / args.config).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"acima: cannot read config {args.config}: {exc}", file=sys.stderr)
        return 2

    level = str(args.level or config.get("level", "L1")).upper()
    if level not in RANK:
        print(f"acima: unknown level {level!r}; expected L1, L2 or L3", file=sys.stderr)
        return 2
    enforcer = Enforcer(root, config, level)
    enforcer.config_name = args.config
    findings = enforcer.run()
    errors = [f for f in findings if f.severity == "error"]
    disabled = ("externals map not declared in acima.config.json"
                if enforcer.externals is None else None)
    execution: dict[str, dict] = {}
    for rule in sorted(CATALOG):
        if rule in NOT_EXECUTED:
            execution[rule] = {"executed": False, "reason": NOT_EXECUTED[rule]}
        elif rule in TIER_RULES and disabled:
            execution[rule] = {"executed": False, "reason": disabled}
        else:
            execution[rule] = {"executed": True}

    if args.format == "json":
        print(json.dumps({"standard": config.get("standard", "1.0.0"),
                          "level": level,
                          "sourceFiles": enforcer.source_files,
                          "execution": execution,
                          "findings": [f.as_dict() for f in findings]}, indent=2))
    else:
        for f in findings:
            print(f"{f.rule}  {f.severity:<7} {f.message}\n  {f.path}:{f.line}")
            if f.evidence:
                print(f"  {f.evidence}")
        print(f"\n{len(findings)} finding(s), {len(errors)} error(s) at level {level.upper()}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
