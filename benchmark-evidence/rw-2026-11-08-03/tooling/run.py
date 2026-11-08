#!/usr/bin/env python3
"""Mechanical rerun of the pinned ACIMA benchmark over retained source copies.

This runner does not re-clone, edit, build or test upstream sources. It executes the
current reference enforcer against the already-pinned adoption copies and records the
raw result. Adjudication is deliberately not performed here: a clean result is not
injection-proven by this script and a finding is not a confirmed defect.

    python3 benchmark-evidence/rw-2026-11-08-03/tooling/run.py \
        --languages python,typescript
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

RUN_DIR = Path(__file__).resolve().parents[1]
PROJECT = RUN_DIR.parents[1]
BENCH = Path("/tmp/acima-real-world-benchmark")
RUN02_CONFIGS = PROJECT / "benchmark-evidence/rw-2026-11-08-02/configs"
REPOS = [
    ("httpx", "python", "encode/httpx"),
    ("flask", "python", "pallets/flask"),
    ("fastapi", "python", "fastapi/fastapi"),
    ("hono", "typescript", "honojs/hono"),
    ("drizzle-orm", "typescript", "drizzle-team/drizzle-orm"),
    ("trpc", "typescript", "trpc/trpc"),
    ("cobra", "go", "spf13/cobra"),
    ("bubbletea", "go", "charmbracelet/bubbletea"),
    ("gin", "go", "gin-gonic/gin"),
    ("fluentvalidation", "dotnet", "FluentValidation/FluentValidation"),
    ("serilog", "dotnet", "serilog/serilog"),
    ("spectre-console", "dotnet", "spectreconsole/spectre.console"),
    ("jsoup", "java", "jhy/jsoup"),
    ("gson", "java", "google/gson"),
    ("mall", "java", "macrozheng/mall"),
]
ENV = os.environ.copy()
ENV["PATH"] = "/tmp/toolchains/go/bin:/tmp/toolchains/dotnet:" + ENV.get("PATH", "")
ENV["DOTNET_ROOT"] = "/tmp/toolchains/dotnet"
ENV["DOTNET_CLI_TELEMETRY_OPTOUT"] = "1"


def command_for(language: str, target: Path) -> tuple[list[str], Path]:
    if language == "python":
        return ([sys.executable, str(PROJECT / "examples/python/tools/acima_arch.py")],
                PROJECT)
    if language == "typescript":
        return (["node", str(PROJECT / "examples/typescript/tools/acima-arch.mjs")],
                PROJECT)
    if language == "go":
        return (["go", "run", "./tools/archtest"], PROJECT / "examples/go")
    if language == "dotnet":
        return (["dotnet", "run", "--project",
                 str(PROJECT / "examples/dotnet/tools/Acima.ArchTests"), "--"], PROJECT)
    raise ValueError(language)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def install_reviewed_config(repo_id: str, target: Path) -> Path | None:
    """Use the exact run-02 reviewed config, not the uncorrected run-01 copy."""
    source = RUN02_CONFIGS / f"{repo_id}.acima.config.json"
    if not source.is_file():
        return None
    destination = target / "acima.config.json"
    if destination.is_file():
        backup = RUN_DIR / "configs" / f"{repo_id}.run01.acima.config.json"
        backup.parent.mkdir(parents=True, exist_ok=True)
        if not backup.exists():
            shutil.copyfile(destination, backup)
    shutil.copyfile(source, destination)
    return source


def run_one(repo_id: str, language: str, repo_name: str) -> dict:
    target = BENCH / "repositories" / language / repo_id / "adoption"
    out = RUN_DIR / "runs" / language / repo_id
    out.mkdir(parents=True, exist_ok=True)
    record = {"id": repo_id, "repo": repo_name, "language": language,
              "target": str(target), "executed": language != "java"}
    reviewed = install_reviewed_config(repo_id, target)
    if reviewed is not None:
        record["reviewedConfig"] = str(reviewed.relative_to(PROJECT))
    if language == "java":
        reason = "no Java reference enforcer in this revision"
        (out / "blocked.json").write_text(
            json.dumps({"reason": reason}, indent=2) + "\n", encoding="utf-8")
        record.update({"validJson": False, "exit": None, "findings": None,
                       "status": "blocked", "reason": reason})
        return record

    command, cwd = command_for(language, target)
    command += ["--root", str(target), "--format", "json"]
    result = subprocess.run(command, cwd=cwd, env=ENV, capture_output=True,
                            text=True, timeout=300)
    (out / "enforcer.stderr").write_text(result.stderr, encoding="utf-8")
    (out / "enforcer.exit").write_text(f"{result.returncode}\n", encoding="utf-8")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        (out / "enforcer.stdout").write_text(result.stdout, encoding="utf-8")
        record.update({"validJson": False, "exit": result.returncode,
                       "findings": None, "status": "invalid-json",
                       "reason": (result.stderr or result.stdout)[-500:]})
        return record

    (out / "enforcer.json").write_text(json.dumps(payload, indent=2) + "\n",
                                       encoding="utf-8")
    findings = payload.get("findings", [])
    by_rule: dict[str, int] = {}
    for finding in findings:
        by_rule[finding.get("rule", "?")] = by_rule.get(finding.get("rule", "?"), 0) + 1
    execution = payload.get("execution", {})
    record.update({
        "validJson": True,
        "exit": result.returncode,
        "findings": len(findings),
        "errors": sum(1 for finding in findings
                      if finding.get("severity") == "error"),
        "byRule": dict(sorted(by_rule.items())),
        "classified": len(payload.get("classified", [])),
        "sourceFiles": payload.get("sourceFiles"),
        "level": payload.get("level"),
        "executedRules": sum(1 for value in execution.values()
                             if isinstance(value, dict) and value.get("executed") is True),
        "notExecutedRules": sum(1 for value in execution.values()
                                if isinstance(value, dict) and value.get("executed") is False),
        "configSha256": sha256(target / "acima.config.json"),
        "status": "clean" if not findings else "findings",
    })
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--languages", default="python,typescript,go,dotnet,java")
    args = parser.parse_args()
    selected = {item.strip() for item in args.languages.split(",") if item.strip()}
    unknown = selected - {"python", "typescript", "go", "dotnet", "java"}
    if unknown:
        print(f"unknown languages: {', '.join(sorted(unknown))}", file=sys.stderr)
        return 2
    if "dotnet" in selected:
        prepared = subprocess.run(
            ["dotnet", "build", "examples/dotnet/tools/Acima.ArchTests",
             "-v", "q", "--nologo"], cwd=PROJECT, env=ENV, capture_output=True, text=True)
        if prepared.returncode != 0:
            print((prepared.stdout + prepared.stderr)[-2000:], file=sys.stderr)
            return 2

    rows = []
    for repo_id, language, repo_name in REPOS:
        if language not in selected:
            continue
        try:
            row = run_one(repo_id, language, repo_name)
        except subprocess.TimeoutExpired:
            row = {"id": repo_id, "repo": repo_name, "language": language,
                   "executed": True, "validJson": False, "exit": None,
                   "findings": None, "status": "timeout"}
        rows.append(row)
        print(f"{language:10} {repo_id:18} {row['status']:12} "
              f"findings={row.get('findings')} exit={row.get('exit')}")

    aggregate = RUN_DIR / "aggregate"
    aggregate.mkdir(parents=True, exist_ok=True)
    existing_path = aggregate / "portfolio.json"
    existing = json.loads(existing_path.read_text(encoding="utf-8")) if existing_path.is_file() else []
    merged = {row["id"]: row for row in existing}
    merged.update({row["id"]: row for row in rows})
    ordered = [merged[key] for key, _language, _repo in REPOS if key in merged]
    (existing_path).write_text(json.dumps(ordered, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {existing_path} ({len(ordered)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
