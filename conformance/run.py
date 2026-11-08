#!/usr/bin/env python3
"""ACIMA conformance runner.

Runs every selected reference implementation twice — once over its good tree, once over
its violation gallery — and compares the gallery output with the checked-in expected.json.
The runner also enforces the canonical coverage contract in `conformance/coverage.json`:
every catalog rule must be reported as executed or explicitly not executed, every gallery
rule must have a fixture, and a run with no source files is a failure, not a pass.

    python3 conformance/run.py            # python, typescript, go, dotnet, topology, tools
    python3 conformance/run.py python ts  # a subset
    python3 conformance/run.py topology   # profile checks only
    python3 conformance/run.py tools      # CLI and walkthrough checks only

Exit codes: 0 all selected profiles conform, 1 a profile drifted or could not be verified,
2 the runner itself could not run. A missing toolchain is exit 1, never a green skip.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOPOLOGY = "topology"
TOOLS = "tools"
DEFAULT_PROFILES = ["python", "typescript", "go", "dotnet", TOPOLOGY, TOOLS]

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


def fail(message: str) -> None:
    print(f"{RED}fail{RESET}  {message}")


def load_contract() -> tuple[set[str], dict]:
    catalog = json.loads((ROOT / "tools/acima-spec/rules.json").read_text(encoding="utf-8"))
    coverage = json.loads((ROOT / "conformance/coverage.json").read_text(encoding="utf-8"))
    ids = {rule["id"] for rule in catalog["rules"]}
    for name, profile in coverage["profiles"].items():
        executed = set(profile["executed"])
        not_executed = set(profile["notExecuted"])
        gallery = set(profile["galleryRules"])
        if executed | not_executed != ids:
            raise ValueError(f"{name}: execution coverage does not partition the catalog")
        if executed & not_executed:
            raise ValueError(f"{name}: a rule is both executed and not executed")
        if gallery - executed:
            raise ValueError(f"{name}: gallery claims a rule that is not executed")
    return ids, coverage


def collect(findings: list[dict]) -> dict[str, list[str]]:
    by_rule: dict[str, set[str]] = defaultdict(set)
    for finding in findings:
        by_rule[finding["rule"]].add(finding["path"])
    return {rule: sorted(paths) for rule, paths in sorted(by_rule.items())}


def run(profile: dict, args: list[str]) -> tuple[int, str]:
    result = subprocess.run(profile["command"] + args, cwd=ROOT / profile["dir"],
                            capture_output=True, text=True)
    return result.returncode, result.stdout if result.stdout.strip() else result.stderr


def write_artifact(directory: Path | None, name: str, kind: str, payload: dict) -> None:
    if directory is None:
        return
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{name}.{kind}.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def check_topology() -> bool:
    result = subprocess.run([sys.executable, "conformance/test_topology.py"], cwd=ROOT,
                            capture_output=True, text=True)
    if result.returncode != 0:
        fail("topology: ST-1–ST-12 checks failed")
        print((result.stdout + result.stderr)[:3000])
        return False
    print(f"{GREEN}ok{RESET}    topology: ST-1–ST-12 checks pass on clean and violating fixtures")
    return True


def check_tools() -> bool:
    for test in ("conformance/test_cli.py", "conformance/test_walkthrough.py",
                 "conformance/test_waiver_fingerprints.py",
                 "conformance/test_adoption_safety.py",
                 "conformance/test_library_profile.py",
                 "conformance/test_dotnet_profile.py",
                 "conformance/test_exclusions.py",
                 "conformance/test_rule_catalog.py",
                 "conformance/test_injected_violation.py",
                 "conformance/test_preflight_discovery.py",
                 "conformance/test_mode_precedence.py",
                 "conformance/test_claim_model.py",
                 "conformance/test_documentation_contract.py",
                 "conformance/test_documentation_integrity.py"):
        result = subprocess.run([sys.executable, test], cwd=ROOT, capture_output=True, text=True)
        if result.returncode != 0:
            fail(f"tools: {test} failed")
            print((result.stdout + result.stderr)[:3000])
            return False
    print(f"{GREEN}ok{RESET}    tools: CLI and executable walkthrough pass")
    return True


def check(name: str, profile: dict, catalog_ids: set[str], coverage: dict,
          artifacts: Path | None) -> bool:
    directory = ROOT / profile["dir"]
    expected_file = directory / "violations" / "expected.json"
    if not directory.is_dir() or not expected_file.is_file():
        fail(f"{name}: no reference implementation or gallery at {profile['dir']}")
        return False
    if shutil.which(profile["command"][0]) is None:
        fail(f"{name}: required toolchain {profile['command'][0]!r} is not installed")
        return False

    if "prepare" in profile:
        prepared = subprocess.run(profile["prepare"], cwd=ROOT / profile["dir"],
                                  capture_output=True, text=True)
        if prepared.returncode != 0:
            fail(f"{name}: prepare step failed")
            print((prepared.stdout + prepared.stderr)[:2000])
            return False

    contract = coverage["profiles"][name]
    required_executed = set(contract["executed"])
    required_not_executed = set(contract["notExecuted"])
    required_gallery = set(contract["galleryRules"])

    code, output = run(profile, ["--root", ".", "--format", "json"])
    if code != 0:
        fail(f"{name}: production tree is not clean (exit {code})")
        print(output[:2000])
        return False
    try:
        clean = json.loads(output)
    except json.JSONDecodeError:
        fail(f"{name}: good run did not return JSON")
        print(output[:2000])
        return False
    if clean.get("findings"):
        fail(f"{name}: {len(clean['findings'])} finding(s) on the production tree")
        return False
    if not isinstance(clean.get("sourceFiles"), int) or clean["sourceFiles"] <= 0:
        fail(f"{name}: analysed zero source files; conformance cannot be claimed")
        return False
    execution = clean.get("execution")
    if not isinstance(execution, dict) or set(execution) != catalog_ids:
        fail(f"{name}: execution evidence does not name every catalog rule")
        return False
    actual_executed = {rule for rule, value in execution.items() if value.get("executed") is True}
    actual_not_executed = {rule for rule, value in execution.items() if value.get("executed") is False}
    if actual_executed != required_executed or actual_not_executed != required_not_executed:
        fail(f"{name}: execution coverage drifted from conformance/coverage.json")
        print(f"   executed: expected {sorted(required_executed)}, got {sorted(actual_executed)}")
        print(f"   not executed: expected {sorted(required_not_executed)}, got {sorted(actual_not_executed)}")
        return False
    for rule in actual_not_executed:
        if not str(execution[rule].get("reason", "")).strip():
            fail(f"{name}: {rule} is not executed but has no reason")
            return False
    write_artifact(artifacts, name, "clean", clean)

    code, output = run(profile, ["--config", profile["config"], "--format", "json"])
    if code not in (0, 1):
        fail(f"{name}: gallery run failed with exit {code}")
        print(output[:2000])
        return False
    try:
        gallery = json.loads(output)
    except json.JSONDecodeError:
        fail(f"{name}: gallery run did not return JSON")
        print(output[:2000])
        return False
    write_artifact(artifacts, name, "gallery", gallery)

    actual = collect(gallery["findings"])
    expected = json.loads(expected_file.read_text(encoding="utf-8"))
    expected_rules = set(expected)
    if expected_rules != required_gallery:
        missing = sorted(required_gallery - expected_rules)
        extra = sorted(expected_rules - required_gallery)
        fail(f"{name}: expected.json does not match the required gallery coverage")
        if missing:
            print(f"   missing rules: {', '.join(missing)}")
        if extra:
            print(f"   unexpected rules: {', '.join(extra)}")
        return False
    if set(actual) != required_gallery:
        missing = sorted(required_gallery - set(actual))
        fail(f"{name}: gallery did not fire every required rule")
        if missing:
            print(f"   missing: {', '.join(missing)}")
        return False
    if actual != expected:
        fail(f"{name}: gallery drifted")
        for rule in sorted(set(actual) | set(expected)):
            if actual.get(rule) != expected.get(rule):
                print(f"   {rule}: expected {expected.get(rule)}, got {actual.get(rule)}")
        return False

    rules = len(actual)
    findings = len(gallery["findings"])
    print(f"{GREEN}ok{RESET}    {name}: clean tree, {rules} rules / {findings} findings in the gallery")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="ACIMA conformance suite")
    parser.add_argument("profiles", nargs="*", help="profiles to run (default: all supported)")
    parser.add_argument("--artifacts", default=None,
                        help="write per-profile clean and gallery JSON evidence here")
    args = parser.parse_args()

    selected = args.profiles or DEFAULT_PROFILES
    unknown = [name for name in selected
               if name not in PROFILES and name not in (TOPOLOGY, TOOLS)]
    if unknown:
        print(f"unknown profile(s): {', '.join(unknown)}", file=sys.stderr)
        return 2
    try:
        catalog_ids, coverage = load_contract()
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"acima: invalid conformance contract: {error}", file=sys.stderr)
        return 2

    artifacts = Path(args.artifacts) if args.artifacts else None
    results = [check_topology()] if TOPOLOGY in selected else []
    results += [check(name, PROFILES[name], catalog_ids, coverage, artifacts)
                for name in selected if name in PROFILES]
    results += [check_tools()] if TOOLS in selected else []
    failed = results.count(False)
    print()
    if failed:
        print(f"{failed} profile(s) did not conform or could not be verified")
        return 1
    print("all selected profiles conform")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
