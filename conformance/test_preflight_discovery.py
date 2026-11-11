"""Regression tests for discovery completeness in the adoption preflight.

These exist because two controlled repositories exposed unsafe behavior:

* a source-bearing tree with no discoverable boundary exited 0 with only warnings;
* a tree with eighteen candidate modules was silently truncated to sixteen.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = ROOT / "skills/acima-adoption/scripts/preflight.py"


def run_preflight(directory: Path) -> tuple[int, dict]:
    result = subprocess.run(
        [sys.executable, str(PREFLIGHT), "--project", str(directory), "--format", "json"],
        cwd=ROOT, capture_output=True, text=True,
    )
    payload = json.loads(result.stdout) if result.stdout.strip() else {}
    return result.returncode, payload


class PreflightDiscoveryTests(unittest.TestCase):
    def test_source_without_discoverable_units_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory(prefix="acima-no-units-") as temp:
            directory = Path(temp)
            (directory / "main.py").write_text('print("hello")\n', encoding="utf-8")
            code, payload = run_preflight(directory)
            self.assertEqual(code, 1)
            checks = {check["id"]: check for check in payload["checks"]}
            self.assertEqual(checks["TGT-004"]["status"], "fail")
            self.assertIn("TGT-004", payload["blockers"])

    def test_dotnet_contract_projects_are_recognized_case_insensitively(self) -> None:
        with tempfile.TemporaryDirectory(prefix="acima-contract-suffix-") as temp:
            directory = Path(temp)
            contracts = directory / "src" / "ailib.tools.domain.contracts"
            contracts.mkdir(parents=True)
            (contracts / "ailib.tools.domain.contracts.csproj").write_text(
                "<Project />", encoding="utf-8")
            (contracts / "Contract.cs").write_text("public sealed record Contract;", encoding="utf-8")
            code, payload = run_preflight(directory)
            self.assertEqual(code, 0)
            unit = next(item for item in payload["proposedUnits"]
                        if item["paths"] == ["src/ailib.tools.domain.contracts"])
            self.assertEqual(unit["role"], "contracts")
            self.assertEqual(unit["module"], "ailib.tools.domain")

    def test_test_projects_are_not_proposed_as_production_modules(self) -> None:
        with tempfile.TemporaryDirectory(prefix="acima-test-projects-") as temp:
            directory = Path(temp)
            production = directory / "src" / "Catalog"
            tests = directory / "src" / "Catalog.Tests"
            production.mkdir(parents=True)
            tests.mkdir(parents=True)
            (production / "Catalog.csproj").write_text("<Project />", encoding="utf-8")
            (production / "Catalog.cs").write_text("public class Catalog;", encoding="utf-8")
            (tests / "Catalog.Tests.csproj").write_text("<Project />", encoding="utf-8")
            (tests / "CatalogTests.cs").write_text("public class CatalogTests;", encoding="utf-8")
            code, payload = run_preflight(directory)
            self.assertEqual(code, 0)
            self.assertEqual(len(payload["proposedUnits"]), 1)
            self.assertEqual(payload["proposedUnits"][0]["id"], "catalog")
            self.assertEqual(payload["sourceCoverage"]["productionCovered"], 1)
            self.assertEqual(payload["sourceCoverage"]["testsExcluded"], 1)
            self.assertEqual(payload["sourceCoverage"]["productionUncovered"], [])

    def test_frontend_tooling_and_e2e_tests_are_not_reported_as_unowned_production(self) -> None:
        with tempfile.TemporaryDirectory(prefix="acima-frontend-source-scope-") as temp:
            directory = Path(temp)
            for name in ("api", "app", "features"):
                path = directory / "src" / name
                path.mkdir(parents=True)
                (path / "index.ts").write_text("export {};", encoding="utf-8")
            (directory / "src" / "main.tsx").write_text("export {};", encoding="utf-8")
            (directory / "src" / "vite-env.d.ts").write_text("declare const x: string;", encoding="utf-8")
            (directory / "e2e" / "specs").mkdir(parents=True)
            (directory / "e2e" / "specs" / "home.spec.ts").write_text("test();", encoding="utf-8")
            (directory / "vite.config.ts").write_text("export {};", encoding="utf-8")
            code, payload = run_preflight(directory)
            self.assertEqual(code, 0)
            self.assertEqual(payload["sourceCoverage"]["testsExcluded"], 1)
            self.assertEqual(payload["sourceCoverage"]["toolingExcluded"], 2)
            self.assertEqual(payload["sourceCoverage"]["productionCovered"], 3)
            self.assertEqual(payload["sourceCoverage"]["productionUncovered"], ["src/main.tsx"])
            checks = {check["id"]: check for check in payload["checks"]}
            self.assertEqual(checks["TGT-005"]["status"], "warn")
            self.assertIn("1 production source file", checks["TGT-005"]["detail"])

    def test_more_than_sixteen_candidates_are_all_proposed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="acima-many-units-") as temp:
            directory = Path(temp)
            source = directory / "src"
            source.mkdir()
            for index in range(18):
                module = source / f"mod{index:02d}"
                module.mkdir()
                (module / "file.py").write_text("VALUE = 1\n", encoding="utf-8")
            code, payload = run_preflight(directory)
            self.assertEqual(code, 0)
            self.assertEqual(len(payload["proposedUnits"]), 18)
            checks = {check["id"]: check for check in payload["checks"]}
            self.assertEqual(checks["TGT-004"]["status"], "pass")
            self.assertEqual(checks["TGT-005"]["status"], "pass")

    def test_preflight_units_match_the_module_map_proposal(self) -> None:
        with tempfile.TemporaryDirectory(prefix="acima-consistent-") as temp:
            directory = Path(temp)
            for name in ("orders", "billing"):
                source = directory / "src" / name
                source.mkdir(parents=True)
                (source / "service.py").write_text("VALUE = 1\n", encoding="utf-8")
            (directory / "tests").mkdir()
            (directory / "tests" / "test_service.py").write_text("def test(): pass\n",
                                                                    encoding="utf-8")
            (directory / "tools").mkdir()
            (directory / "tools" / "build.py").write_text("VALUE = 2\n", encoding="utf-8")
            code, payload = run_preflight(directory)
            self.assertEqual(code, 0)
            proposal = json.loads(
                subprocess.run(
                    [sys.executable, "-c",
                     "import json,sys; sys.path.insert(0,'conformance'); "
                     "import module_map; print(json.dumps(module_map.discover("
                     "__import__('pathlib').Path(sys.argv[1]))['proposal']))",
                     str(directory)], cwd=ROOT, capture_output=True, text=True,
                    check=True).stdout)
            proposed_ids = {item["id"] for item in payload["proposedUnits"]}
            proposed_ids.update(item["id"] for item in payload["proposedUnits"]
                                if item.get("role") == "contracts")
            proposal_ids = {item["id"] for item in proposal["modules"]}
            self.assertEqual(proposed_ids, proposal_ids)
            checks = {check["id"]: check for check in payload["checks"]}
            self.assertEqual(checks["TGT-005"]["status"], "pass")


if __name__ == "__main__":
    unittest.main()
