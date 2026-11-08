#!/usr/bin/env python3
"""ACIMA reference enforcer for Python.

Implements the portable rule set (23 rules) against the units declared in acima.config.json.
Reads source with `ast`; never imports the product code.

    python3 tools/acima_arch.py --root . --config acima.config.json --format json

Exit codes: 0 clean, 1 unwaived errors, 2 tool failure.
"""
from __future__ import annotations

import argparse
import ast
import fnmatch
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
    "ACIMA-L001": ("error", "L1"), "ACIMA-L002": ("error", "L1"), "ACIMA-L003": ("error", "L1"),
    "ACIMA-C001": ("error", "L2"), "ACIMA-C002": ("error", "L2"), "ACIMA-C004": ("error", "L2"),
    "ACIMA-C005": ("error", "L2"), "ACIMA-C006": ("error", "L2"),
    "ACIMA-A001": ("error", "L3"), "ACIMA-A003": ("error", "L3"),
    "ACIMA-G001": ("error", "L1"), "ACIMA-G002": ("error", "L1"),
    "ACIMA-G003": ("warning", "L2"), "ACIMA-G005": ("error", "L1"),
}
RANK = {"L1": 1, "L2": 2, "L3": 3}

PERSISTENCE = ("sqlalchemy", "QuerySet", "psycopg", "sqlite3", "db.execute", "IQueryable",
               "DbContext", "EntityManager", "django.db", "asyncpg", "pymongo")
FRAMEWORK = ("flask", "fastapi", "starlette", "django", "http.server", "werkzeug", "celery",
             "requests", "httpx", "aiohttp")
AMBIENT = (r"datetime\.now\b", r"datetime\.utcnow\b", r"date\.today\b", r"time\.time\b",
           r"uuid4\b", r"uuid\.uuid1\b", r"\brandom\.")
SQL = re.compile(r"(?is)\b(?:from|into|update|join)\s+([a-z][a-z0-9_]*)")
WRITE_SQL = re.compile(r"(?is)\b(?:insert\s+into|update|delete\s+from|join)\s+([a-z][a-z0-9_]*)")

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

    def as_dict(self) -> dict:
        return {"rule": self.rule, "severity": self.severity, "message": self.message,
                "path": self.path, "line": self.line, "evidence": self.evidence}


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
        self.edges: list[tuple[str, str, int, str]] = []
        self.module_names = {u.module for u in self.units if u.module}

    # -- discovery ---------------------------------------------------------
    def rel(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()

    def excluded(self, rel: str) -> bool:
        parts = rel.split("/")
        return any(fnmatch.fnmatch(rel, p) or any(fnmatch.fnmatch(x, p) for x in parts)
                   for p in self.excludes)

    def unit_for(self, rel: str, source: str) -> Unit | None:
        head = "\n".join(source.splitlines()[:3])
        override = re.search(r"acima-unit:\s*([\w.\-]+)", head)
        if override:
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
        best: Unit | None = None
        best_len = -1
        for u in self.units:
            for p in u.paths:
                if (rel == p or rel.startswith(p.rstrip("/") + "/")) and len(p) > best_len:
                    best, best_len = u, len(p)
        return best

    def add(self, rule: str, message: str, rel: str, line: int, evidence: str = "") -> None:
        severity, required = CATALOG[rule]
        if RANK[required] > RANK[self.level]:
            return
        self.findings.append(Finding(rule, severity, message, rel, max(line, 1), evidence.strip()[:200]))

    # -- parsing -----------------------------------------------------------
    def collect(self) -> None:
        for path in sorted(self.root.rglob("*.py")):
            rel = self.rel(path)
            if self.excluded(rel):
                continue
            source = path.read_text(encoding="utf-8", errors="replace")
            unit = self.unit_for(rel, source)
            if unit is None:
                self.add("ACIMA-G005", f"Source file is not part of any declared unit: {rel}", rel, 1)
                continue
            self.units_of[rel] = unit
            try:
                self.files[rel] = ast.parse(source)
            except SyntaxError:
                self.add("ACIMA-G005", f"File could not be parsed: {rel}", rel, 1)

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
                if u_from.role == "contracts":
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
                forbidden = (module != a.module and a.role in ("contracts", "implementation")
                             and not (a.role == "implementation" and module == a.module))
                if forbidden and (a.id, module) not in seen:
                    seen.add((a.id, module))
                    self.add("ACIMA-D008",
                             f"{a.id} reaches the implementation unit {module} transitively "
                             f"through {b.id}.", rel, line, evidence)

    def check_contracts(self) -> None:
        for rel, tree in self.files.items():
            unit = self.units_of[rel]
            if unit.role != "contracts":
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

    def check_contract_class(self, rel: str, node: ast.ClassDef) -> None:
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
            if annotated or assigns:
                self.add("ACIMA-C001",
                         f"Contract type {node.name} exposes mutable state "
                         f"(not an immutable dataclass).", rel, node.lineno)
        elif not frozen:
            self.add("ACIMA-C001",
                     f"Contract type {node.name} is a dataclass without frozen=True.",
                     rel, node.lineno)
        for item in node.body:
            if isinstance(item, ast.AnnAssign):
                annotation = ast.unparse(item.annotation)
                if re.search(r"\b(list|dict|set|List|Dict|Set|OrderedDict|defaultdict)\b", annotation):
                    self.add("ACIMA-C002",
                             f"Contract type {node.name} exposes a mutable collection "
                             f"({annotation}).", rel, item.lineno, annotation)
                if re.search(r"\b(Any|object)\b", annotation) or annotation in ("dict", "list"):
                    self.add("ACIMA-C006",
                             f"Contract type {node.name} has an untyped member ({annotation}).",
                             rel, item.lineno, annotation)
        if not documented:
            self.add("ACIMA-G003", f"Contract type {node.name} has no documentation.", rel, node.lineno)

    def check_layering(self) -> None:
        for rel in self.files:
            unit = self.units_of[rel]
            if unit.role != "implementation" or "/infrastructure/" in rel:
                continue
            source = (self.root / rel).read_text(encoding="utf-8", errors="replace")
            for token in PERSISTENCE:
                if token in source:
                    self.add("ACIMA-L001",
                             f"{unit.id} references infrastructure ({token}) outside infrastructure/.",
                             rel, self.line_of(source, token), token)

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
            else:
                waivers.append(waiver)
        return waivers

    def apply_waivers(self, waivers: list[dict]) -> None:
        kept: list[Finding] = []
        for finding in self.findings:
            unit = self.units_of.get(finding.path)
            waived = any(
                w["rule"] == finding.rule and (
                    (unit is not None and w["scope"] == f"unit:{unit.id}")
                    or (w["scope"].startswith("path:") and fnmatch.fnmatch(finding.path, w["scope"][5:]))
                    or (unit is not None and w["scope"] == f"module:{unit.module}")
                )
                for w in waivers
            )
            if not waived:
                kept.append(finding)
        self.findings = kept

    # -- run ---------------------------------------------------------------
    def run(self) -> list[Finding]:
        self.collect()
        self.check_edges()
        self.check_contracts()
        self.check_layering()
        self.check_sql()
        self.check_statics()
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

    level = args.level or config.get("level", "L1")
    findings = Enforcer(root, config, level).run()
    errors = [f for f in findings if f.severity == "error"]

    if args.format == "json":
        print(json.dumps({"standard": config.get("standard", "1.0.0"),
                          "level": level.upper(),
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
