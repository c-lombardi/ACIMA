"""Regression tests for .NET library-profile package metadata.

The previous implementation concatenated project XML and required a literal
`<PackageId>` element. MSBuild's evaluated metadata is authoritative: PackageId
may be inherited from Directory.Build.props or default to the assembly/project
name, and IsPackable may be false. This test exercises the evaluator rather than
special-casing FluentValidation.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "conformance/fixtures/dotnet-profile"
ENFORCER = ROOT / "examples/dotnet/tools/Acima.ArchTests"


def run_enforcer(target: Path) -> tuple[int, dict, str]:
    result = subprocess.run(
        ["dotnet", "run", "--project", str(ENFORCER), "--no-build", "--",
         "--root", str(target), "--config", "acima.config.json", "--format", "json"],
        cwd=ROOT, capture_output=True, text=True,
    )
    payload = json.loads(result.stdout) if result.stdout.strip() else {}
    return result.returncode, payload, result.stderr


@unittest.skipUnless(shutil.which("dotnet"), "dotnet SDK is not installed")
class DotnetProfileMetadataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        built = subprocess.run(
            ["dotnet", "build", str(ENFORCER), "-v", "q", "--nologo"],
            cwd=ROOT, capture_output=True, text=True,
        )
        if built.returncode != 0:
            raise AssertionError(built.stdout + built.stderr)

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.target = Path(self.temporary.name) / "repo"
        shutil.copytree(FIXTURE, self.target,
                        ignore=shutil.ignore_patterns("bin", "obj"))

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def edit(self, relative: str, old: str, new: str) -> None:
        path = self.target / relative
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text)
        path.write_text(text.replace(old, new), encoding="utf-8")

    def assert_no_profile_error(self) -> None:
        code, payload, stderr = run_enforcer(self.target)
        self.assertIn(code, (0, 1), stderr)
        errors = [finding for finding in payload.get("findings", [])
                  if finding["rule"] == "ACIMA-G001"
                  and finding.get("evidence") == "profile.kind"]
        self.assertEqual(errors, [], payload)

    def test_inherited_package_id_is_publishable(self) -> None:
        self.assert_no_profile_error()

    def test_public_api_glob_matches_root_and_nested_files(self) -> None:
        code, payload, stderr = run_enforcer(self.target)
        self.assertIn(code, (0, 1), stderr)
        findings = [finding for finding in payload.get("findings", [])
                    if finding["rule"] == "ACIMA-L003"]
        self.assertEqual(findings, [], payload)
        classified = {entry["path"] for entry in payload.get("classified", [])
                      if entry["rule"] == "ACIMA-L003"}
        self.assertEqual(classified, {
            "src/Widget/Widget.cs",
            "src/Widget/Internal/Nested.cs",
        })

    def test_direct_package_id_is_publishable(self) -> None:
        (self.target / "Directory.Build.props").unlink()
        self.edit("src/Widget/Widget.csproj",
                  "<TargetFramework>net8.0</TargetFramework>",
                  "<TargetFramework>net8.0</TargetFramework>\n    <PackageId>Direct.Widgets</PackageId>")
        self.assert_no_profile_error()

    def test_default_package_id_is_publishable(self) -> None:
        (self.target / "Directory.Build.props").unlink()
        self.assert_no_profile_error()

    def test_is_packable_false_is_rejected(self) -> None:
        self.edit("Directory.Build.props",
                  "<PackageId>Acme.Widgets</PackageId>",
                  "<PackageId>Acme.Widgets</PackageId>\n    <IsPackable>false</IsPackable>")
        _code, payload, _stderr = run_enforcer(self.target)
        evidence = {finding.get("evidence") for finding in payload.get("findings", [])}
        self.assertIn("profile.kind", evidence)


if __name__ == "__main__":
    unittest.main()
