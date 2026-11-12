"""Controlled .NET fixtures for false-positive fixes in the reference enforcer.

Each case builds a minimal repository whose only meaningful signal is the
matching behavior. The tests fail if a fix is reverted, even when the clean
examples continue to pass.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENFORCER = ROOT / "examples/dotnet/tools/Acima.ArchTests"


def config(units: list[dict]) -> dict:
    return {
        "standard": "1.0.0",
        "mode": "base",
        "language": "dotnet",
        "level": "L1",
        "root": ".",
        "units": units,
        "exclude": ["bin", "obj"],
    }


@unittest.skipUnless(shutil.which("dotnet"), "dotnet SDK is not installed")
class DotnetFalsePositiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        built = subprocess.run(
            ["dotnet", "build", str(ENFORCER), "-v", "q", "--nologo"],
            cwd=ROOT, capture_output=True, text=True,
        )
        if built.returncode != 0:
            raise AssertionError(built.stdout + built.stderr)

    def run_fixture(self, units: list[dict], files: dict[str, str]) -> tuple[int, dict]:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        target = Path(temporary.name) / "repo"
        for relative, text in files.items():
            path = target / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        (target / "acima.config.json").write_text(
            json.dumps(config(units)), encoding="utf-8")
        result = subprocess.run(
            ["dotnet", "run", "--project", str(ENFORCER), "--no-build", "--",
             "--root", str(target), "--config", "acima.config.json", "--format", "json"],
            cwd=ROOT, capture_output=True, text=True,
        )
        payload = json.loads(result.stdout) if result.stdout.strip() else {}
        return result.returncode, payload

    def findings(self, payload: dict, rule: str) -> list[dict]:
        return [finding for finding in payload.get("findings", [])
                if finding.get("rule") == rule]

    def test_infrastructure_path_match_is_case_insensitive(self) -> None:
        units = [{"id": "app", "module": "app", "role": "implementation",
                  "paths": ["src/App"], "namespaces": ["App"]}]
        files = {
            "src/App/Infrastructure/Composition.cs": (
                "using Microsoft.EntityFrameworkCore;\n"
                "namespace App.Infrastructure;\n"
                "public sealed class Composition { }\n"
            ),
        }
        code, payload = self.run_fixture(units, files)
        self.assertIn(code, (0, 1), payload)
        l001 = [finding for finding in self.findings(payload, "ACIMA-L001")
                if finding.get("path") == "src/App/Infrastructure/Composition.cs"]
        self.assertEqual(l001, [], payload)

    def test_same_internal_type_name_in_another_module_is_not_a_reference(self) -> None:
        units = [
            {"id": "alpha", "module": "alpha", "role": "implementation",
             "paths": ["src/Alpha"], "namespaces": ["Alpha"]},
            {"id": "consumer", "module": "consumer", "role": "implementation",
             "paths": ["src/Consumer"], "namespaces": ["Consumer"]},
        ]
        files = {
            "src/Alpha/Handler.cs": (
                "namespace Alpha;\n"
                "internal sealed class Handler { }\n"
            ),
            "src/Consumer/Handler.cs": (
                "namespace Consumer;\n"
                "public sealed class Handler { }\n"
                "public sealed class UsesHandler\n"
                "{\n"
                "    private readonly Handler _handler = new Handler();\n"
                "}\n"
            ),
        }
        code, payload = self.run_fixture(units, files)
        self.assertIn(code, (0, 1), payload)
        d009 = [finding for finding in self.findings(payload, "ACIMA-D009")
                if finding.get("path") == "src/Consumer/Handler.cs"]
        self.assertEqual(d009, [], payload)

    def test_namespace_declared_in_repository_is_not_third_party(self) -> None:
        units = [
            {"id": "contracts", "module": "sales", "role": "contracts",
             "paths": ["src/Contracts"], "namespaces": ["Sales.Contracts"]},
            {"id": "sales", "module": "sales", "role": "implementation",
             "paths": ["src/Sales"], "namespaces": ["Sales"]},
            {"id": "shared", "module": "shared", "role": "shared-kernel",
             "paths": ["src/Shared"]},
        ]
        files = {
            "src/Contracts/Order.cs": (
                "using Sales.Shared;\n"
                "namespace Sales.Contracts;\n"
                "public sealed record Order(int Id);\n"
            ),
            "src/Sales/OrderService.cs": (
                "namespace Sales;\n"
                "public sealed class OrderService { }\n"
            ),
            "src/Shared/SharedValue.cs": (
                "namespace Sales.Shared;\n"
                "public sealed class SharedValue { }\n"
            ),
        }
        code, payload = self.run_fixture(units, files)
        self.assertIn(code, (0, 1), payload)
        d004 = [finding for finding in self.findings(payload, "ACIMA-D004")
                if finding.get("path") == "src/Contracts/Order.cs"]
        self.assertEqual(d004, [], payload)


if __name__ == "__main__":
    unittest.main()
