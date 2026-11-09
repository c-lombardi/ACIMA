"""A module whose name appears inside a NuGet package id must not claim that package.

Regression for a real false positive: in a 27-project C# solution the module `tools` matched
the third-party package `Grpc.Tools` by substring, which fabricated a contracts -> implementation
edge (D002) and seven transitive D008 findings. Matching is now by package identity prefix.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENFORCER = ROOT / "examples/dotnet/tools/Acima.ArchTests"

CONTRACTS = """<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="Grpc.Tools" Version="2.64.0" PrivateAssets="All" />
  </ItemGroup>
</Project>
"""

IMPLEMENTATION = """<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
  </PropertyGroup>
  <ItemGroup>
    <ProjectReference Include="..\\acima.test.contracts\\acima.test.contracts.csproj" />
  </ItemGroup>
</Project>
"""

CONFIG = {
    "standard": "1.0.0",
    "mode": "base",
    "language": "dotnet",
    "level": "L1",
    "units": [
        {"id": "test.contracts", "module": "tools", "role": "contracts",
         "paths": ["acima.test.contracts"], "namespaces": ["Acima.Test.Contracts"]},
        {"id": "test", "module": "tools", "role": "implementation",
         "paths": ["acima.test"], "namespaces": ["Acima.Test"]},
    ],
}


@unittest.skipUnless(shutil.which("dotnet"), "dotnet SDK is not installed")
class PackageIdentityTests(unittest.TestCase):
    def test_package_name_is_not_a_module_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contracts = root / "acima.test.contracts"
            contracts.mkdir()
            (contracts / "acima.test.contracts.csproj").write_text(CONTRACTS, encoding="utf-8")
            (contracts / "Thing.cs").write_text(
                "namespace Acima.Test.Contracts;\npublic sealed record Thing(string Id);\n",
                encoding="utf-8")
            implementation = root / "acima.test"
            implementation.mkdir()
            (implementation / "acima.test.csproj").write_text(IMPLEMENTATION, encoding="utf-8")
            (implementation / "Widget.cs").write_text(
                "namespace Acima.Test;\ninternal sealed class Widget { }\n", encoding="utf-8")
            (root / "acima.config.json").write_text(json.dumps(CONFIG, indent=2), encoding="utf-8")

            result = subprocess.run(
                ["dotnet", "run", "--project", str(ENFORCER), "--", "--root", str(root),
                 "--format", "json"],
                cwd=ROOT, capture_output=True, text=True, timeout=600,
            )
            self.assertIn(result.returncode, (0, 1), result.stderr)
            payload = json.loads(result.stdout)
            rules = {finding["rule"] for finding in payload["findings"]}

            # D004 still fires: a contract project really does carry a package. That proves the
            # enforcer read this project rather than skipping it.
            self.assertIn("ACIMA-D004", rules)
            # ... but the package must not be mistaken for a reference to the `tools` module.
            self.assertNotIn("ACIMA-D002", rules)
            for finding in payload["findings"]:
                self.assertNotIn("Grpc.Tools", finding.get("message", ""))


if __name__ == "__main__":
    unittest.main()
