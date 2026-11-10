#!/usr/bin/env python3
"""Bundle the files the adoption skill reads into skills/acima-adoption/vendor/.

The skill is copied into ~/.agents or an equivalent directory, so a copied skill cannot reach
`tools/`, `docs/` or `examples/`. This copies exactly the files it reads, preserving the repository
layout, so the scripts' existing root-relative paths keep working.

    python3 tools/bundle_skill.py           # regenerate vendor/ and its MANIFEST.json
    python3 tools/bundle_skill.py --check   # exit 1 if vendor/ is missing, stale or has extra files

Generated content is committed. The drift check is also run from conformance/test_skill_bundle.py,
so a rule or enforcer change cannot silently leave a copied skill giving stale advice.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/acima-adoption"
VENDOR = SKILL / "vendor"

SOURCES = [
    # the machine catalog, and the CLI that reads it
    "tools/acima-spec/rules.json",
    "tools/acima.py",
    "tools/qualitative-review.schema.json",
    "conformance/acima_claim.py",
    "conformance/qualitative_review.py",
    # reference enforcers, with the minimum build context each needs
    "examples/python/tools/acima_arch.py",
    "examples/typescript/tools/acima-arch.mjs",
    "examples/go/go.mod",
    "examples/go/tools/archtest/main.go",
    "examples/dotnet/Directory.Build.props",
    "examples/dotnet/tools/Acima.ArchTests/Program.cs",
    "examples/dotnet/tools/Acima.ArchTests/Acima.ArchTests.csproj",
    # the gallery baselines SKL-007 checks for
    "examples/python/violations/expected.json",
    "examples/typescript/violations/expected.json",
    "examples/go/violations/expected.json",
    "examples/dotnet/violations/expected.json",
    # the normative text the skill cites
    "docs/rules/README.md",
    "docs/rules/index.md",
    "docs/rules/dependency.md",
    "docs/rules/contracts.md",
    "docs/rules/autonomy.md",
    "docs/rules/naming.md",
    "docs/languages/index.md",
    "docs/languages/python.md",
    "docs/languages/typescript.md",
    "docs/languages/go.md",
    "docs/languages/dotnet.md",
    "docs/standard/04-dependency-model.md",
    "docs/standard/05-contract-design.md",
    "docs/standard/06-runtime-boundaries.md",
    "docs/standard/07-executable-governance.md",
    "docs/standard/08-conformance.md",
    "docs/standard/09-adoption.md",
    "docs/standard/11-service-topology.md",
    "docs/standard/12-library-profile.md",
    "docs/standard/13-explicit-inputs.md",
    "docs/standard/14-values-and-configuration.md",
    "docs/standard/15-composition-and-injection.md",
    "docs/standard/16-functional-composition.md",
    "docs/standard/17-lifecycle-and-state-ownership.md",
    "docs/standard/18-intent-revealing-naming.md",
    "docs/guides/architecture-tests.md",
    "docs/guides/architecture-families.md",
    "docs/guides/review-and-decisions.md",
    "docs/commands.md",
]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> int:
    if VENDOR.exists():
        shutil.rmtree(VENDOR)
    files = {}
    for relative in SOURCES:
        source = ROOT / relative
        if not source.is_file():
            print(f"bundle_skill: missing source {relative}", file=sys.stderr)
            return 2
        target = VENDOR / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        files[relative] = {"sha256": digest(source), "bytes": source.stat().st_size}
    manifest = {
        "purpose": "files the adoption skill reads when it is copied out of the standard repository",
        "layout": "paths mirror the repository root, so STANDARD_ROOT can point at vendor/ unchanged",
        "catalogSha256": files["tools/acima-spec/rules.json"]["sha256"],
        "files": dict(sorted(files.items())),
    }
    (VENDOR / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"bundle_skill: wrote {len(files)} files and MANIFEST.json")
    return 0


def check() -> int:
    manifest_path = VENDOR / "MANIFEST.json"
    if not manifest_path.is_file():
        print("bundle_skill: vendor/MANIFEST.json missing; run without --check", file=sys.stderr)
        return 1
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    problems = []
    for relative, recorded in manifest["files"].items():
        source = ROOT / relative
        vendored = VENDOR / relative
        if not source.is_file():
            problems.append(f"source gone: {relative}")
        elif not vendored.is_file():
            problems.append(f"not vendored: {relative}")
        elif digest(source) != recorded["sha256"]:
            problems.append(f"stale vendored copy: {relative}")
        elif digest(vendored) != recorded["sha256"]:
            problems.append(f"vendored file edited by hand: {relative}")
    expected = set(manifest["files"]) | {"MANIFEST.json"}
    for extra in sorted(p.relative_to(VENDOR).as_posix() for p in VENDOR.rglob("*")
                        if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"):
        if extra not in expected:
            problems.append(f"unexpected file: {extra}")
    catalog = manifest["catalogSha256"]
    if digest(VENDOR / "tools/acima-spec/rules.json") != catalog:
        problems.append("vendored catalog does not match the manifest")
    skill_manifest = json.loads((SKILL / "manifest.json").read_text(encoding="utf-8"))
    if skill_manifest["catalog"]["sha256"] != catalog:
        problems.append("skill manifest pins a different catalog than vendor/ carries")
    if problems:
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        print(f"bundle_skill: {len(problems)} drift problem(s); run without --check", file=sys.stderr)
        return 1
    print(f"bundle_skill: {len(manifest['files'])} files match their sources")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="bundle the skill's references for copying")
    parser.add_argument("--check", action="store_true", help="fail when vendor/ has drifted")
    args = parser.parse_args()
    return check() if args.check else build()


if __name__ == "__main__":
    raise SystemExit(main())
