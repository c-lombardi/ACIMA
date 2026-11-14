"""The .NET enforcer executes all 42 automated rules and keeps the clean tree clean."""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENFORCER = ROOT / "examples/dotnet/tools/Acima.ArchTests"
EXAMPLE = ROOT / "examples/dotnet"
MANUAL = {
    "ACIMA-A002", "ACIMA-A004", "ACIMA-A010", "ACIMA-A011", "ACIMA-A012",
    "ACIMA-A013", "ACIMA-A014", "ACIMA-A015", "ACIMA-C003", "ACIMA-C007",
    "ACIMA-C008", "ACIMA-G004", "ACIMA-L004", "ACIMA-N003",
}
EXPECTED = {
    "ACIMA-A005": {"violations/values_impl.cs"},
    "ACIMA-A006": {"violations/values_impl.cs"},
    "ACIMA-A007": {"violations/lifecycle_host.cs"},
    "ACIMA-A008": {"violations/lifecycle_host.cs"},
    "ACIMA-A009": {"violations/lifecycle_host.cs"},
    "ACIMA-D013": {"violations/composition_host.cs"},
    "ACIMA-D014": {"violations/composition_impl.cs"},
    "ACIMA-D015": {"violations/composition_impl.cs"},
    "ACIMA-D016": {"violations/composition_impl.cs"},
    "ACIMA-N001": {"violations/naming_impl.cs"},
    "ACIMA-N002": {"violations/naming_impl.cs"},
}


def run(config: str = "acima.config.json") -> tuple[int, dict, str]:
    result = subprocess.run(
        ["dotnet", "run", "--project", str(ENFORCER), "--no-build", "--",
         "--root", str(EXAMPLE), "--config", config, "--format", "json"],
        cwd=ROOT, capture_output=True, text=True,
    )
    payload = json.loads(result.stdout) if result.stdout.strip() else {}
    return result.returncode, payload, result.stderr


@unittest.skipUnless(shutil.which("dotnet"), "dotnet SDK is not installed")
class DotnetFullCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        built = subprocess.run(
            ["dotnet", "build", str(ENFORCER), "-v", "q", "--nologo"],
            cwd=ROOT, capture_output=True, text=True,
        )
        if built.returncode != 0:
            raise AssertionError(built.stdout + built.stderr)

    def test_clean_tree_executes_every_automated_rule(self) -> None:
        code, payload, stderr = run()
        self.assertEqual(code, 0, stderr)
        self.assertEqual(payload["findings"], [])
        execution = payload["execution"]
        self.assertEqual(
            {rule for rule, value in execution.items() if value["executed"]},
            set(execution) - MANUAL,
        )
        self.assertEqual(len(execution) - len(MANUAL), 42)

    def test_gallery_fires_the_new_rules_and_all_42_execute(self) -> None:
        code, payload, stderr = run("acima.gallery.config.json")
        self.assertEqual(code, 1, stderr)
        paths: dict[str, set[str]] = {}
        for finding in payload["findings"]:
            paths.setdefault(finding["rule"], set()).add(finding["path"])
        for rule, expected in EXPECTED.items():
            self.assertEqual(paths.get(rule), expected, rule)
            self.assertTrue(payload["execution"][rule]["executed"], rule)
        self.assertFalse(
            [rule for rule in EXPECTED if not payload["execution"][rule]["executed"]]
        )
        self.assertEqual(
            [rule for rule, value in payload["execution"].items() if not value["executed"]],
            sorted(MANUAL),
        )

    def test_d016_names_the_dependency_not_the_helper_type(self) -> None:
        _, payload, _ = run("acima.gallery.config.json")
        finding = next(item for item in payload["findings"] if item["rule"] == "ACIMA-D016")
        self.assertIn("Repository", finding["message"])
        self.assertNotIn("CapturingService", finding["message"])

    def test_explicit_empty_allowlist_executes_d016(self) -> None:
        config = json.loads((EXAMPLE / "acima.config.json").read_text(encoding="utf-8"))
        config["partialHelpers"] = []
        with tempfile.TemporaryDirectory(prefix="acima-dotnet-d016-") as temporary:
            path = Path(temporary) / "acima.config.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            result = subprocess.run(
                ["dotnet", "run", "--project", str(ENFORCER), "--no-build", "--",
                 "--root", str(EXAMPLE), "--config", str(path), "--format", "json"],
                cwd=ROOT, capture_output=True, text=True,
            )
        payload = json.loads(result.stdout) if result.stdout.strip() else {}
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertTrue(payload["execution"]["ACIMA-D016"]["executed"])
        self.assertEqual(
            {rule for rule, value in payload["execution"].items() if value["executed"]},
            set(payload["execution"]) - MANUAL,
        )

    def test_absent_allowlist_leaves_d016_unexecuted(self) -> None:
        config = json.loads((EXAMPLE / "acima.config.json").read_text(encoding="utf-8"))
        config.pop("partialHelpers", None)
        with tempfile.TemporaryDirectory(prefix="acima-dotnet-d016-absent-") as temporary:
            path = Path(temporary) / "acima.config.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            result = subprocess.run(
                ["dotnet", "run", "--project", str(ENFORCER), "--no-build", "--",
                 "--root", str(EXAMPLE), "--config", str(path), "--format", "json"],
                cwd=ROOT, capture_output=True, text=True,
            )
        payload = json.loads(result.stdout) if result.stdout.strip() else {}
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertFalse(payload["execution"]["ACIMA-D016"]["executed"])
        self.assertIn("partial helper allowlist", payload["execution"]["ACIMA-D016"].get("reason", ""))

    def test_a007_allows_readonly_dependencies_but_requires_one_required_constructor(self) -> None:
        with tempfile.TemporaryDirectory(prefix="acima-dotnet-a007-") as temporary:
            root = Path(temporary)
            (root / "src/app").mkdir(parents=True)
            (root / "src/host").mkdir(parents=True)
            (root / "Fixture.csproj").write_text(
                "<Project Sdk=\"Microsoft.NET.Sdk\">\n"
                "  <PropertyGroup><TargetFramework>net8.0</TargetFramework><Nullable>enable</Nullable></PropertyGroup>\n"
                "</Project>\n", encoding="utf-8")
            (root / "src/app/App.cs").write_text(
                "namespace App;\n"
                "internal sealed class Clock {}\n"
                "internal sealed class Injected\n"
                "{\n"
                "    private readonly Clock _clock;\n"
                "    public Injected(Clock clock) { _clock = clock; }\n"
                "    public bool IsReady() => _clock is not null;\n"
                "}\n"
                "internal sealed class Defaulted\n"
                "{\n"
                "    private readonly Clock _clock;\n"
                "    public Defaulted(Clock clock = null!) { _clock = clock; }\n"
                "}\n"
                "internal sealed class Mutated\n"
                "{\n"
                "    private Clock _clock;\n"
                "    public Mutated(Clock clock) { _clock = clock; }\n"
                "    public void Reset() { _clock = null!; }\n"
                "}\n"
                "internal sealed class Multiple\n"
                "{\n"
                "    public Multiple(Clock clock) { _ = clock; }\n"
                "    public Multiple(Clock clock, bool other) { _ = clock; _ = other; }\n"
                "}\n", encoding="utf-8")
            (root / "src/host/Host.cs").write_text(
                "namespace App;\n"
                "internal static class Host\n"
                "{\n"
                "    public static void Configure(dynamic services)\n"
                "    {\n"
                "        services.AddTransient<Injected>();\n"
                "        services.AddTransient<Defaulted>();\n"
                "        services.AddTransient<Mutated>();\n"
                "        services.AddTransient<Multiple>();\n"
                "    }\n"
                "}\n", encoding="utf-8")
            (root / "acima.config.json").write_text(json.dumps({
                "language": "dotnet", "root": ".", "level": "L3", "exclude": ["bin", "obj"],
                "units": [
                    {"id": "app", "role": "implementation", "paths": ["src/app"]},
                    {"id": "host", "role": "host", "paths": ["src/host"]},
                ],
            }), encoding="utf-8")
            result = subprocess.run(
                ["dotnet", "run", "--project", str(ENFORCER), "--no-build", "--",
                 "--root", str(root), "--config", "acima.config.json", "--format", "json"],
                cwd=ROOT, capture_output=True, text=True,
            )
        payload = json.loads(result.stdout) if result.stdout.strip() else {}
        self.assertIn(result.returncode, (0, 1), result.stderr + result.stdout)
        a007 = [finding for finding in payload["findings"] if finding["rule"] == "ACIMA-A007"]
        self.assertEqual(len(a007), 1, a007)
        self.assertIn("Injected", a007[0]["message"], a007)

    def test_project_level_model_resolves_a_partial_class_across_files(self) -> None:
        with tempfile.TemporaryDirectory(prefix="acima-dotnet-project-") as temporary:
            root = Path(temporary)
            (root / "src").mkdir()
            (root / "Fixture.csproj").write_text(
                "<Project Sdk=\"Microsoft.NET.Sdk\">\n"
                "  <PropertyGroup><TargetFramework>net8.0</TargetFramework></PropertyGroup>\n"
                "</Project>\n", encoding="utf-8")
            (root / "src/Captured.cs").write_text(
                "using System;\n"
                "namespace App;\n"
                "internal sealed partial class Captured\n"
                "{\n"
                "    public Func<string, string> Handler() => request => Repository(request);\n"
                "}\n", encoding="utf-8")
            (root / "src/CapturedField.cs").write_text(
                "using System;\n"
                "namespace App;\n"
                "internal sealed partial class Captured\n"
                "{\n"
                "    internal static readonly Func<string, string> Repository = text => text;\n"
                "}\n", encoding="utf-8")
            (root / "acima.config.json").write_text(json.dumps({
                "language": "dotnet", "root": ".", "exclude": ["bin", "obj"],
                "units": [{"id": "app", "module": "app", "role": "implementation",
                           "paths": ["src"]}],
            }), encoding="utf-8")
            result = subprocess.run(
                ["dotnet", "run", "--project", str(ENFORCER), "--no-build", "--",
                 "--root", str(root), "--config", "acima.config.json", "--format", "json"],
                cwd=ROOT, capture_output=True, text=True,
            )
        payload = json.loads(result.stdout) if result.stdout.strip() else {}
        self.assertIn(result.returncode, (0, 1), result.stderr + result.stdout)
        d015 = [finding for finding in payload["findings"] if finding["rule"] == "ACIMA-D015"]
        self.assertEqual({finding["path"] for finding in d015}, {"src/Captured.cs"}, payload)
        self.assertTrue(all("Repository" in finding["message"] for finding in d015), d015)


if __name__ == "__main__":
    unittest.main()
