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


def config(units: list[dict], level: str = "L1") -> dict:
    return {
        "standard": "1.0.0",
        "mode": "base",
        "language": "dotnet",
        "level": level,
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

    def run_fixture(self, units: list[dict], files: dict[str, str],
                    level: str = "L1") -> tuple[int, dict]:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        target = Path(temporary.name) / "repo"
        for relative, text in files.items():
            path = target / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        (target / "acima.config.json").write_text(
            json.dumps(config(units, level)), encoding="utf-8")
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

    def test_self_contained_partial_and_generated_declaration_are_not_defects(self) -> None:
        units = [
            {"id": "app", "module": "app", "role": "implementation",
             "paths": ["src/App"], "namespaces": ["App"]},
            {"id": "catalog", "module": "catalog", "role": "implementation",
             "paths": ["src/Catalog"], "namespaces": ["Catalog.Internals"]},
        ]
        files = {
            "src/App/OrderPolicy.Part1.cs": (
                "namespace App;\n"
                "internal sealed partial class OrderPolicy\n"
                "{\n"
                "    public bool Accepts(int quantity) => quantity > 0;\n"
                "}\n"
            ),
            "src/App/OrderPolicy.Part2.cs": (
                "namespace App;\n"
                "internal sealed partial class OrderPolicy\n"
                "{\n"
                "    public bool Rejects(int quantity) => !Accepts(quantity: quantity);\n"
                "}\n"
            ),
            "src/App/App.csproj": (
                "<Project Sdk=\"Microsoft.NET.Sdk\">\n"
                "  <PropertyGroup><TargetFramework>net8.0</TargetFramework></PropertyGroup>\n"
                "</Project>\n"
            ),
            "src/Catalog/Catalog.csproj": (
                "<Project Sdk=\"Microsoft.NET.Sdk\">\n"
                "  <PropertyGroup><TargetFramework>net8.0</TargetFramework></PropertyGroup>\n"
                "</Project>\n"
            ),
            "src/App/Generated.g.cs": (
                "using Catalog.Internals;\n"
                "namespace App;\n"
                "internal sealed class generated_order_projection\n"
                "{\n"
                "    public bool IsGenerated() => true;\n"
                "}\n"
            ),
            "src/Catalog/CatalogWriter.cs": (
                "namespace Catalog.Internals;\n"
                "internal sealed class CatalogWriter { }\n"
            ),
        }
        code, payload = self.run_fixture(units, files, level="L3")
        self.assertIn(code, (0, 1), payload)
        generated = "src/App/Generated.g.cs"
        partial_paths = {"src/App/OrderPolicy.Part1.cs", "src/App/OrderPolicy.Part2.cs"}
        self.assertEqual(
            {finding["path"] for finding in self.findings(payload, "ACIMA-D001")},
            {generated},
            payload,
        )
        self.assertEqual(
            {finding["rule"] for finding in payload["findings"] if finding["path"] == generated},
            {"ACIMA-D001"},
            payload,
        )
        self.assertEqual(self.findings(payload, "ACIMA-N001"), [], payload)
        self.assertEqual(
            [finding for finding in payload["findings"] if finding["path"] in partial_paths],
            [],
            payload,
        )

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

    def test_optional_inputs_are_scoped_to_behavior_units(self) -> None:
        units = [
            {"id": "app", "module": "app", "role": "implementation",
             "paths": ["src/App"], "namespaces": ["App"]},
            {"id": "app.contracts", "module": "app", "role": "contracts",
             "paths": ["src/App.Contracts"], "namespaces": ["App.Contracts"]},
        ]
        files = {
            "src/App/Module.cs": (
                "namespace App;\n"
                "internal sealed class Module\n"
                "{\n"
                "    public Module(string name, TimeProvider? clock = null) { }\n"
                "    public void Run(string name, bool notify = true) { }\n"
                "}\n"
            ),
            "src/App/Required.cs": (
                "namespace App;\n"
                "internal sealed class Required\n"
                "{\n"
                "    public Required(TimeProvider? clock) { }\n"
                "}\n"
            ),
            "src/App.Contracts/View.cs": (
                "namespace App.Contracts;\n"
                "public sealed record View(string Name, int Version = 1);\n"
            ),
        }
        code, payload = self.run_fixture(units, files)
        self.assertIn(code, (0, 1), payload)
        self.assertEqual(
            {finding["path"] for finding in self.findings(payload, "ACIMA-D011")},
            {"src/App/Module.cs"},
            payload,
        )
        self.assertEqual(
            {finding["path"] for finding in self.findings(payload, "ACIMA-D012")},
            {"src/App/Module.cs"},
            payload,
        )

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
