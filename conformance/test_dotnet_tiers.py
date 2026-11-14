"""The .NET tier rules use Roslyn symbols, not only declared type tokens."""
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
GALLERY = EXAMPLE / "acima.gallery.config.json"
TIER_RULES = ("ACIMA-L005", "ACIMA-L006", "ACIMA-L007", "ACIMA-D010", "ACIMA-G006")


def run(config: str) -> tuple[int, dict, str]:
    result = subprocess.run(
        ["dotnet", "run", "--project", str(ENFORCER), "--no-build", "--",
         "--root", str(EXAMPLE), "--config", config, "--format", "json"],
        cwd=ROOT, capture_output=True, text=True,
    )
    payload = json.loads(result.stdout) if result.stdout.strip() else {}
    return result.returncode, payload, result.stderr


@unittest.skipUnless(shutil.which("dotnet"), "dotnet SDK is not installed")
class DotnetTierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        built = subprocess.run(
            ["dotnet", "build", str(ENFORCER), "-v", "q", "--nologo"],
            cwd=ROOT, capture_output=True, text=True,
        )
        if built.returncode != 0:
            raise AssertionError(built.stdout + built.stderr)

    def test_gallery_fires_every_tier_rule(self) -> None:
        code, payload, stderr = run(str(GALLERY))
        self.assertIn(code, (0, 1), stderr)
        paths: dict[str, set[str]] = {}
        for finding in payload["findings"]:
            paths.setdefault(finding["rule"], set()).add(finding["path"])
        self.assertEqual(paths["ACIMA-L005"], {"violations/tier_l005.cs"})
        self.assertEqual(paths["ACIMA-L006"], {"violations/tier_orphan_adapter.cs"})
        self.assertEqual(paths["ACIMA-L007"], {"violations/tier_l005.cs"})
        self.assertEqual(paths["ACIMA-D010"], {"violations/tier_port.cs"})
        self.assertEqual(paths["ACIMA-G006"], {"violations/TierFixtures.csproj"})
        for rule in TIER_RULES:
            self.assertTrue(payload["execution"][rule]["executed"], rule)

    def test_vendor_types_resolve_without_declared_type_tokens(self) -> None:
        config = json.loads(GALLERY.read_text(encoding="utf-8"))
        config["externals"]["Microsoft.CodeAnalysis.CSharp"].pop("types", None)
        with tempfile.TemporaryDirectory(prefix="acima-dotnet-tier-") as temporary:
            path = Path(temporary) / "gallery.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            code, payload, stderr = run(str(path))
        self.assertIn(code, (0, 1), stderr)
        l007 = [finding for finding in payload["findings"]
                if finding["rule"] == "ACIMA-L007"]
        self.assertEqual({finding["path"] for finding in l007},
                         {"violations/tier_l005.cs"})


if __name__ == "__main__":
    unittest.main()
