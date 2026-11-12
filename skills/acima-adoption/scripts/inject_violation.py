#!/usr/bin/env python3
"""Prove that an assessment can detect known violations.

A zero-finding report is not evidence of conformance: the enforcer may be pointed at
the wrong tree, the unit map may cover nothing, or a rule may silently not execute.
This script runs two independent proofs against the target's real enforcer:

* ``ACIMA-L001`` copies the target into a disposable directory, injects one
  language-appropriate forbidden-dependency violation into an implementation unit,
  and requires that rule at that exact path.
* ``ACIMA-D001`` builds a disposable two-unit fixture where one implementation unit
  imports another, and requires the cross-module D001 finding. This proof does not
  depend on the target's unit map, so a single-module repository can still prove
  that D-rule evaluation actually runs.

The target is never written to. Injection details are withheld from the JSON report
unless ``--reveal`` is passed, so an assessment agent can run the proof before it is
told what was injected.

    python3 inject_violation.py --project <target> [--rule L001|D001|both]
        [--format json|text] [--reveal] [--keep]
        [--out acima/evidence/proof.json]

Exit codes: 0 all requested proofs passed, 1 not proven, 2 the tool could not run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
# Same resolution as preflight: search ancestors rather than assuming a fixed depth. An installed
# skill can be exposed as a mount root, where a fixed parents[index] does not exist.
_REPOSITORY = next(
    (candidate for candidate in (SKILL_DIR, *SKILL_DIR.parents)
     if (candidate / "tools/acima-spec/rules.json").is_file()),
    None,
)
STANDARD_ROOT = _REPOSITORY or (SKILL_DIR / "vendor")
sys.path.insert(0, str(STANDARD_ROOT / "conformance"))
from executables import resolve_executable  # noqa: E402 - shared environment lookup

L001 = "ACIMA-L001"
D001 = "ACIMA-D001"
RULES = {L001: "L001", D001: "D001"}
IGNORE = shutil.ignore_patterns(
    ".git", "node_modules", "bin", "obj", "dist", "build", "target", "out",
    "coverage", ".venv", "venv", "__pycache__", ".next", ".nuxt",
)

RECIPES = {
    "python": {
        "filename": "_acima_injected_violation.py",
        "content": "import sqlalchemy\n",
        "specifier": "sqlalchemy",
    },
    "typescript": {
        "filename": "_acima_injected_violation.ts",
        "content": "import { Pool } from 'pg';\n\nexport const injectedPool = (): Pool | null => null;\n",
        "specifier": "pg",
    },
    "dotnet": {
        "filename": "AcimaInjectedViolation.cs",
        "content": "using Microsoft.EntityFrameworkCore;\n\nnamespace Acima.Injected;\n\ninternal static class InjectedViolation\n{\n}\n",
        "specifier": "Microsoft.EntityFrameworkCore",
    },
}
GO_IMPORT = 'import _ "gorm.io/gorm"'

# Each fixture has exactly two implementation units. The alpha unit imports the beta
# unit, which must produce ACIMA-D001 at the expected path. The fixtures are derived
# from the reference enforcers, not from the target repository, so they also work for
# single-module targets.
D001_FIXTURES = {
    "python": {
        "expected": "alpha/a.py",
        "config": {
            "standard": "1.0.0",
            "language": "python",
            "level": "L1",
            "root": ".",
            "units": [
                {"id": "alpha", "module": "alpha", "role": "implementation",
                 "paths": ["alpha"]},
                {"id": "beta", "module": "beta", "role": "implementation",
                 "paths": ["beta"]},
            ],
            "exclude": ["tests"],
        },
        "files": {
            "alpha/a.py": "from beta.impl.b import value\n\n\ndef read() -> int:\n    return value\n",
            "beta/impl/b.py": "value = 1\n",
        },
    },
    "typescript": {
        "expected": "src/alpha/a.ts",
        "config": {
            "standard": "1.0.0",
            "language": "typescript",
            "level": "L1",
            "root": ".",
            "units": [
                {"id": "alpha", "module": "alpha", "role": "implementation",
                 "paths": ["src/alpha"]},
                {"id": "beta", "module": "beta", "role": "implementation",
                 "paths": ["src/beta"]},
            ],
            "exclude": ["node_modules"],
        },
        "files": {
            "src/alpha/a.ts": "import { value } from '../beta/impl/b';\n\nexport const read = (): number => value;\n",
            "src/beta/impl/b.ts": "export const value = 1;\n",
        },
    },
    "go": {
        "expected": "alpha/alpha.go",
        "config": {
            "standard": "1.0.0",
            "language": "go",
            "level": "L1",
            "root": ".",
            "units": [
                {"id": "alpha", "module": "alpha", "role": "implementation",
                 "paths": ["alpha/alpha.go"]},
                {"id": "beta", "module": "beta", "role": "implementation",
                 "paths": ["beta/impl/b.go"]},
            ],
            "exclude": ["vendor"],
            "modulePath": "fixture",
        },
        "files": {
            "go.mod": "module fixture\n\ngo 1.21\n",
            "alpha/alpha.go": "package alpha\n\nimport \"fixture/beta/impl\"\n\nvar Value = impl.Value\n",
            "beta/impl/b.go": "package impl\n\nvar Value = 1\n",
        },
    },
    "dotnet": {
        "expected": "alpha/Alpha.csproj",
        "config": {
            "standard": "1.0.0",
            "language": "dotnet",
            "level": "L1",
            "root": ".",
            "units": [
                {"id": "alpha", "module": "alpha", "role": "implementation",
                 "paths": ["alpha"], "namespaces": ["Alpha"]},
                {"id": "beta", "module": "beta", "role": "implementation",
                 "paths": ["beta"], "namespaces": ["Beta"]},
            ],
            "exclude": ["bin", "obj"],
        },
        "files": {
            "alpha/Alpha.csproj": "<Project Sdk=\"Microsoft.NET.Sdk\"><PropertyGroup><TargetFramework>net8.0</TargetFramework></PropertyGroup><ItemGroup><ProjectReference Include=\"../beta/Beta.csproj\" /></ItemGroup></Project>\n",
            "alpha/A.cs": "namespace Alpha;\n\npublic class A\n{\n}\n",
            "beta/Beta.csproj": "<Project Sdk=\"Microsoft.NET.Sdk\"><PropertyGroup><TargetFramework>net8.0</TargetFramework></PropertyGroup></Project>\n",
            "beta/B.cs": "namespace Beta;\n\npublic class B\n{\n}\n",
        },
    },
}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(command: list[str], cwd: Path, timeout: int = 600) -> tuple[int, str, str]:
    try:
        result = subprocess.run(command, cwd=str(cwd), capture_output=True,
                                text=True, timeout=timeout)
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        return 127, "", f"{command[0]} is not installed"
    except subprocess.TimeoutExpired:
        return 124, "", "enforcer timed out"
    except Exception as error:  # noqa: BLE001 - the proof tool must never crash
        return 126, "", str(error)


def implementation_unit(config: dict) -> dict | None:
    return next((unit for unit in config.get("units", [])
                 if unit.get("role") == "implementation"), None)


def inject_go(copy: Path, config: dict) -> tuple[str, dict] | None:
    unit = implementation_unit(config)
    if unit is None:
        return None
    for relative in unit.get("paths", []):
        if not relative.endswith(".go") or relative.endswith("_test.go"):
            continue
        path = copy / relative
        if not path.is_file():
            continue
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        package = next((index for index, line in enumerate(lines)
                        if line.startswith("package ")), None)
        if package is None:
            continue
        lines.insert(package + 1, GO_IMPORT + "\n\n")
        path.write_text("".join(lines), encoding="utf-8")
        return relative, {"filename": relative, "content": GO_IMPORT,
                          "specifier": "gorm.io/gorm", "existingFile": True}
    return None


def inject(copy: Path, language: str, config: dict) -> tuple[str, dict] | None:
    if language == "go":
        return inject_go(copy, config)
    recipe = RECIPES.get(language)
    unit = implementation_unit(config)
    if recipe is None or unit is None:
        return None
    for relative in unit.get("paths", []):
        directory = copy / relative
        if not directory.is_dir():
            continue
        injected = directory / recipe["filename"]
        injected.write_text(recipe["content"], encoding="utf-8")
        return injected.relative_to(copy).as_posix(), dict(recipe)
    return None


def enforcer_invocation(manifest: dict, language: str, root: Path):
    enforcer = manifest.get("enforcers", {}).get(language, {})
    if not enforcer.get("run"):
        return None, None, enforcer
    command = list(enforcer["run"])
    # The manifest names the portable ``python`` command. On Windows the App
    # Execution Alias can shadow it, so run the interpreter that is running
    # this tool instead of depending on PATH resolution.
    if command and Path(command[0]).stem.lower() in {"python", "python3"}:
        command[0] = sys.executable
    elif command and command[0].lower() == "dotnet":
        resolved = resolve_executable("dotnet")
        if resolved:
            command[0] = resolved
    command += ["--root", str(root), "--config", "acima.config.json",
                "--format", "json"]
    cwd = STANDARD_ROOT / enforcer["cwd"] if enforcer.get("cwd") else STANDARD_ROOT
    return command, cwd, enforcer


def prepare(manifest: dict, language: str) -> str:
    enforcer = manifest.get("enforcers", {}).get(language, {})
    if language != "dotnet" or not enforcer.get("buildProject"):
        return ""
    executable = resolve_executable("dotnet")
    if executable is None:
        return "dotnet was not found on PATH or in DOTNET_ROOT"
    code, out, err = run([executable, "build", str(STANDARD_ROOT / enforcer["buildProject"]),
                          "-v", "q", "--nologo"], STANDARD_ROOT, timeout=300)
    if code != 0:
        return f"enforcer build failed: {(err or out).strip()[:300]}"
    return ""


def invoke(manifest: dict, language: str, root: Path) -> dict | None:
    command, cwd, enforcer = enforcer_invocation(manifest, language, root)
    if command is None:
        return None
    started = time.time()
    code, out, err = run(command, cwd)
    try:
        payload = json.loads(out)
    except json.JSONDecodeError:
        payload = None
    findings = payload.get("findings", []) if isinstance(payload, dict) else []
    return {
        "exitCode": code,
        "findings": findings,
        "sourceFiles": (payload or {}).get("sourceFiles"),
        "enforcer": enforcer.get("path"),
        "durationMs": int((time.time() - started) * 1000),
        "parseError": (err or out).strip()[:300] if payload is None else "",
    }


def select_finding(result: dict, rule: str, path: str) -> dict | None:
    return next((finding for finding in result["findings"]
                 if finding.get("rule") == rule and finding.get("path") == path), None)


def withheld_injection() -> dict:
    return {"withheld": True}


def redact(finding: dict | None) -> dict | None:
    return ({"rule": finding.get("rule"), "severity": finding.get("severity")}
            if finding else None)


def make_proof(rule: str, proven: bool, reason: str, injection: dict,
               result: dict | None = None, **extra) -> dict:
    proof = {"rule": rule, "proven": proven, "reason": reason,
             "injection": injection}
    if result is not None:
        proof.update({
            "exitCode": result["exitCode"],
            "findings": len(result["findings"]),
            "sourceFiles": result["sourceFiles"],
            "enforcer": result["enforcer"],
            "durationMs": result["durationMs"],
        })
    proof.update(extra)
    return proof


def write_d001_fixture(root: Path, fixture: dict) -> str:
    (root / "acima.config.json").write_text(
        json.dumps(fixture["config"], indent=2) + "\n", encoding="utf-8")
    for relative, content in fixture["files"].items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return fixture["expected"]


def prove_l001(project: Path, config: dict, language: str, manifest: dict,
               reveal: bool, keep: bool) -> dict:
    unit = implementation_unit(config)
    if unit is None:
        return make_proof(
            L001, False,
            "config declares no implementation unit; L001 cannot be proven",
            withheld_injection())

    copy = Path(tempfile.mkdtemp(prefix="acima-injection-"))
    try:
        shutil.copytree(project, copy, ignore=IGNORE, dirs_exist_ok=True)
        injection = inject(copy, language, config)
        if injection is None:
            return make_proof(L001, False, "no injectable implementation file was found",
                              withheld_injection())
        relative, recipe = injection
        original_hash = (sha256_file(project / relative)
                         if recipe.get("existingFile") else None)

        result = invoke(manifest, language, copy)
        if result is None:
            return make_proof(L001, False, "no reference enforcer for language",
                              withheld_injection())
        match = select_finding(result, L001, relative)
        detected = bool(match) and result["exitCode"] == 1
        untouched = (not (project / relative).exists()
                     if not recipe.get("existingFile")
                     else sha256_file(project / relative) == original_hash)
        proven = detected and untouched
        if detected and untouched:
            reason = "detected the injected violation"
        elif detected:
            reason = "the original tree changed during the proof"
        else:
            reason = "the injected violation was not detected at the expected path"
        if result["parseError"]:
            reason += f"; enforcer output was not JSON: {result['parseError']}"

        detail = ({"path": relative, "content": recipe["content"],
                   "specifier": recipe["specifier"]}
                  if reveal else withheld_injection())
        if keep:
            print(f"acima: kept L001 copy at {copy}", file=sys.stderr)
        return make_proof(
            L001, proven, reason, detail, result,
            detected=detected,
            finding=match if reveal else redact(match),
            originalUntouched=untouched,
        )
    finally:
        if not keep:
            shutil.rmtree(copy, ignore_errors=True)


def prove_d001(language: str, manifest: dict, reveal: bool, keep: bool) -> dict:
    fixture = D001_FIXTURES.get(language)
    if fixture is None:
        return make_proof(
            D001, False,
            f"no disposable D001 fixture for language {language!r}",
            withheld_injection())

    root = Path(tempfile.mkdtemp(prefix="acima-d001-"))
    try:
        expected = write_d001_fixture(root, fixture)
        result = invoke(manifest, language, root)
        if result is None:
            return make_proof(D001, False, "no reference enforcer for language",
                              withheld_injection(), fixture="disposable-two-unit")
        match = select_finding(result, D001, expected)
        detected = bool(match) and result["exitCode"] == 1
        reason = ("detected the injected cross-module violation" if detected else
                  "the cross-module D001 violation was not detected at the expected path")
        if result["parseError"]:
            reason += f"; enforcer output was not JSON: {result['parseError']}"

        detail = ({"kind": "disposable-two-unit", "expectedPath": expected,
                   "config": fixture["config"], "files": fixture["files"]}
                  if reveal else withheld_injection())
        if keep:
            print(f"acima: kept D001 fixture at {root}", file=sys.stderr)
        return make_proof(
            D001, detected, reason, detail, result,
            detected=detected,
            finding=match if reveal else redact(match),
            fixture="disposable-two-unit",
            targetUntouched=True,
        )
    finally:
        if not keep:
            shutil.rmtree(root, ignore_errors=True)


SOURCE_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".mjs", ".cjs", ".cs", ".go", ".java"}
PRUNE = {".git", "node_modules", "bin", "obj", "dist", "build", "target", "out",
         "coverage", ".venv", "venv", "__pycache__"}


def _walk_files(root: Path):
    for current, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(name for name in dirnames
                             if name not in PRUNE and not name.startswith("."))
        for name in sorted(filenames):
            if name.startswith("."):
                continue
            path = Path(current) / name
            if path.is_file():
                yield path


def _source_count(project: Path) -> int:
    return sum(1 for path in _walk_files(project)
               if path.suffix.lower() in SOURCE_EXTENSIONS)


def proof_record(project: Path, requested: list[str], proofs: dict) -> dict:
    """A portable record that status can validate, not just a transcript of this run."""
    catalog_path = STANDARD_ROOT / "tools/acima-spec/rules.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    return {
        "tool": "acima-inject-violation",
        "standard": catalog.get("version"),
        "catalogSha256": hashlib.sha256(catalog_path.read_bytes()).hexdigest(),
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "repository": project.name,
        "sourceFiles": _source_count(project),
        "results": [
            {"rule": rule, "detected": proofs[rule]["proven"],
             "exitCode": proofs[rule].get("exitCode")}
            for rule in requested
        ],
    }


def report(project: Path, language: str, requested: list[str], proofs: dict) -> dict:
    return {
        "tool": "acima-inject-violation",
        "repository": project.name,
        "language": language,
        "rules": requested,
        "proven": all(proofs[rule]["proven"] for rule in requested),
        "proofs": proofs,
        "note": ("L001 copies the target; D001 builds a synthetic two-unit fixture. "
                 "Neither writes to the target."),
    }


def print_text(payload: dict) -> None:
    requested = payload["rules"]
    passed = sum(1 for rule in requested if payload["proofs"][rule]["proven"])
    status = "PROVEN" if payload["proven"] else "NOT PROVEN"
    print(f"{status}  {payload['repository']} ({payload['language']}): "
          f"{passed}/{len(requested)} proofs")
    for rule in requested:
        proof = payload["proofs"][rule]
        state = "PROVEN" if proof["proven"] else "NOT PROVEN"
        line = f"  {rule:<11} {state}"
        if "exitCode" in proof:
            line += f"  exit={proof['exitCode']}"
        if "sourceFiles" in proof:
            line += f"  files={proof['sourceFiles']}"
        injection = proof.get("injection", {})
        if injection.get("path"):
            line += f"  path={injection['path']}"
        elif injection.get("expectedPath"):
            line += f"  fixture={injection['expectedPath']}"
        elif injection.get("withheld"):
            line += "  path=<withheld>"
        print(line)
        if not proof["proven"]:
            print(f"    reason  {proof['reason']}")
        if proof.get("originalUntouched") is False:
            print("    WARNING  the original tree changed during the proof")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prove an ACIMA assessment detects known violations")
    parser.add_argument("--project", default=".", help="target repository root (never modified)")
    parser.add_argument("--manifest", default=str(SKILL_DIR / "manifest.json"))
    parser.add_argument("--rule", choices=["L001", "D001", "both"], default="both",
                        help="which proof to run (default: both)")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--reveal", action="store_true",
                        help="include injected paths and fixture contents in the report")
    parser.add_argument("--keep", action="store_true", help="keep the disposable directories")
    parser.add_argument("--out", default=None,
                        help="write a validated proof record (for example acima/evidence/proof.json)")
    args = parser.parse_args()

    requested = [L001, D001] if args.rule == "both" else (
        [L001] if args.rule == "L001" else [D001])

    project = Path(args.project).resolve()
    manifest_path = Path(args.manifest).resolve()
    try:
        manifest = load(manifest_path)
    except FileNotFoundError:
        print(f"acima: manifest not found: {manifest_path}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as error:
        print(f"acima: manifest is not valid JSON: {error}", file=sys.stderr)
        return 2

    config_path = project / "acima.config.json"
    if not project.is_dir() or not config_path.is_file():
        print(f"acima: {project} has no acima.config.json", file=sys.stderr)
        return 2
    try:
        config = load(config_path)
    except json.JSONDecodeError as error:
        print(f"acima: config is not valid JSON: {error}", file=sys.stderr)
        return 2

    language = str(config.get("language") or "").strip()
    if language not in D001_FIXTURES:
        proofs = {}
        for rule in requested:
            reason = (f"no injection recipe for language {language!r}"
                      if rule == L001 else
                      f"no disposable D001 fixture for language {language!r}")
            proofs[rule] = make_proof(rule, False, reason, withheld_injection())
        payload = report(project, language or "unknown", requested, proofs)
        print(json.dumps(payload, indent=2) if args.format == "json" else "")
        if args.format == "text":
            print_text(payload)
        return 1

    build_error = prepare(manifest, language)
    if build_error:
        print(f"acima: {build_error}", file=sys.stderr)
        return 2
    if not manifest.get("enforcers", {}).get(language, {}).get("run"):
        print(f"acima: no reference enforcer for {language}", file=sys.stderr)
        return 2

    proofs = {}
    if L001 in requested:
        proofs[L001] = prove_l001(project, config, language, manifest,
                                  args.reveal, args.keep)
    if D001 in requested:
        proofs[D001] = prove_d001(language, manifest, args.reveal, args.keep)
    payload = report(project, language, requested, proofs)
    if args.out:
        out_path = Path(args.out)
        if not out_path.is_absolute():
            out_path = Path.cwd() / out_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(proof_record(project, requested, proofs), indent=2) + "\n",
                            encoding="utf-8")
    if args.format == "json":
        print(json.dumps(payload, indent=2))
    else:
        print_text(payload)
    return 0 if payload["proven"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
