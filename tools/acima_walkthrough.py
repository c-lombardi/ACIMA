#!/usr/bin/env python3
"""Executable before/after walkthrough.

Copies the clean Python reference application to a temporary directory, introduces a
real cross-module implementation import, shows the finding, corrects the code, and
proves the tree is clean again. The source repository is never modified.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/python"
BAD = (
    "from acima.catalog.impl.repository import InMemoryProductStore\n"
    "\n"
    "def leaked_store() -> InMemoryProductStore:\n"
    "    return InMemoryProductStore()\n"
)
FIXED = (
    "from acima.catalog.contracts import CatalogReader\n"
    "\n"
    "def catalog_reader(catalog: CatalogReader) -> CatalogReader:\n"
    "    return catalog\n"
)


def run(root: Path) -> tuple[int, dict]:
    result = subprocess.run(
        [sys.executable, "tools/acima_arch.py", "--root", str(root), "--format", "json"],
        cwd=root, capture_output=True, text=True,
    )
    try:
        return result.returncode, json.loads(result.stdout)
    except json.JSONDecodeError:
        raise SystemExit(f"enforcer produced no JSON:\n{result.stderr or result.stdout}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="acima-walkthrough-") as temporary:
        work = Path(temporary)
        shutil.copytree(EXAMPLE, work, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__", "tests", "violations"))
        target = work / "src/acima/orders/impl/reach_into_catalog.py"

        code, clean = run(work)
        before = len(clean.get("findings", []))
        if code != 0 or before:
            print(f"before: expected a clean tree, got {before} finding(s)")
            return 1
        print("before: clean ordering application — 0 findings")

        target.write_text(BAD, encoding="utf-8")
        print("introduced: Orders imports Catalog's implementation "
              "(src/acima/orders/impl/reach_into_catalog.py)")
        code, broken = run(work)
        finding = next((item for item in broken.get("findings", [])
                        if item["rule"] == "ACIMA-D001"), None)
        if finding is None:
            print("expected ACIMA-D001, got no D001 finding")
            return 1
        print(f"finding: {finding['rule']} — {finding['message']}")
        print(f"  {finding['path']}:{finding['line']}  {finding['evidence']}")

        target.write_text(FIXED, encoding="utf-8")
        print("fixed: depend on Catalog's contract instead of its implementation")
        code, repaired = run(work)
        after = len(repaired.get("findings", []))
        if code != 0 or after:
            print(f"after: expected a clean tree, got {after} finding(s)")
            for item in repaired.get("findings", []):
                print(f"  {item['rule']} {item['path']}:{item['line']}")
            return 1
        print("after: 0 findings")
        print("result: violation detected, corrected, and verified")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
