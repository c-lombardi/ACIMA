#!/usr/bin/env python3
"""ACIMA conformance runner.

Runs every reference implementation twice — once over its good tree, once over its
violation gallery — and compares the gallery output with the checked-in expected.json.

    python3 conformance/run.py            # all available languages
    python3 conformance/run.py go python  # a subset

Exit codes: 0 all profiles conform, 1 a profile drifted, 2 a profile could not run.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PROFILES = {
    "python": {
        "dir": "examples/python",
        "command": [sys.executable, "tools/acima_arch.py"],
        "config": "acima.gallery.config.json",
    },
    "typescript": {
        "dir": "examples/typescript",
        "command": ["node", "tools/acima-arch.mjs"],
        "config": "acima.gallery.config.json",
    },
    "go": {
        "dir": "examples/go",
        "command": ["go", "run", "./tools/archtest"],
        "config": "acima.gallery.config.json",
    },
    "dotnet": {
        "dir": "examples/dotnet",
        "command": ["dotnet", "run", "--project", "tools/Acima.ArchTests", "--no-build", "--"],
        "prepare": ["dotnet", "build", "tools/Acima.ArchTests", "-v", "q", "--nologo"],
        "config": "acima.gallery.config.json",
    },
    "java": {
        "dir": "examples/java",
        "command": ["java", "tools/acima/ArchTests.java"],
        "config": "acima.gallery.config.json",
    },
}

GREEN, RED, YELLOW, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[0m"


def collect(findings: list[dict]) -> dict[str, list[str]]:
    by_rule: dict[str, set[str]] = defaultdict(set)
    for finding in findings:
        by_rule[finding["rule"]].add(finding["path"])
    return {rule: sorted(paths) for rule, paths in sorted(by_rule.items())}


def run(profile: dict, args: list[str]) -> tuple[int, str]:
    result = subprocess.run(profile["command"] + args, cwd=ROOT / profile["dir"],
                            capture_output=True, text=True)
    return result.returncode, result.stdout if result.stdout.strip() else result.stderr


def check(name: str, profile: dict) -> bool:
    directory = ROOT / profile["dir"]
    expected_file = directory / "violations" / "expected.json"
    if not directory.is_dir() or not expected_file.is_file():
        print(f"{YELLOW}skip{RESET}  {name}: no reference implementation in {profile['dir']}")
        return True
    if shutil.which(profile["command"][0]) is None:
        print(f"{YELLOW}skip{RESET}  {name}: {profile['command'][0]} is not installed")
        return True

    if "prepare" in profile:
        prepared = subprocess.run(profile["prepare"], cwd=ROOT / profile["dir"],
                                  capture_output=True, text=True)
        if prepared.returncode != 0:
            print(f"{RED}fail{RESET}  {name}: prepare step failed")
            print((prepared.stdout + prepared.stderr)[:2000])
            return False

    code, output = run(profile, ["--root", ".", "--format", "json"])
    if code != 0:
        print(f"{RED}fail{RESET}  {name}: production tree is not clean (exit {code})")
        print(output[:2000])
        return False
    try:
        clean = json.loads(output)
    except json.JSONDecodeError:
        print(f"{RED}fail{RESET}  {name}: good run did not return JSON")
        print(output[:2000])
        return False
    if clean.get("findings"):
        print(f"{RED}fail{RESET}  {name}: {len(clean['findings'])} finding(s) on the production tree")
        return False

    code, output = run(profile, [f"--config", profile["config"], "--format", "json"])
    if code not in (0, 1):
        print(f"{RED}fail{RESET}  {name}: gallery run failed with exit {code}")
        print(output[:2000])
        return False
    try:
        gallery = json.loads(output)
    except json.JSONDecodeError:
        print(f"{RED}fail{RESET}  {name}: gallery run did not return JSON")
        print(output[:2000])
        return False

    actual = collect(gallery["findings"])
    expected = json.loads(expected_file.read_text())
    if actual != expected:
        print(f"{RED}fail{RESET}  {name}: gallery drifted")
        for rule in sorted(set(actual) | set(expected)):
            if actual.get(rule) != expected.get(rule):
                print(f"   {rule}: expected {expected.get(rule)}, got {actual.get(rule)}")
        return False

    rules = len(actual)
    findings = len(gallery["findings"])
    print(f"{GREEN}ok{RESET}    {name}: clean tree, {rules} rules / {findings} findings in the gallery")
    return True


def main() -> int:
    selected = sys.argv[1:] or list(PROFILES)
    unknown = [name for name in selected if name not in PROFILES]
    if unknown:
        print(f"unknown profile(s): {', '.join(unknown)}", file=sys.stderr)
        return 2
    results = [check(name, PROFILES[name]) for name in selected]
    failed = results.count(False)
    print()
    if failed:
        print(f"{failed} profile(s) did not conform")
        return 1
    print("all available profiles conform")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
