"""The adoption skill must declare and pass its own Python tooling boundary.

The skill is not an application module: its scripts are analyzers, report renderers and
test helpers. ACIMA's `tooling` role is the correct classification, but only when it is
explicit. This test fails if a script is added without a unit, if the vendor snapshot is
mistaken for product source, or if the Python enforcer regresses the clean baseline.
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/acima-adoption"
CONFIG = SKILL / "acima.config.json"
ENFORCER = ROOT / "examples/python/tools/acima_arch.py"


class SkillArchitectureTests(unittest.TestCase):
    def test_skill_declares_only_tooling_units_and_excludes_vendor(self) -> None:
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        self.assertEqual(config["language"], "python")
        self.assertEqual(config["mode"], "base")
        self.assertEqual(
            {unit["role"] for unit in config["units"]},
            {"tooling"},
        )
        self.assertIn("vendor", config["exclude"])
        declared = {
            path
            for unit in config["units"]
            for path in unit["paths"]
        }
        scripts = {
            path.relative_to(SKILL).as_posix()
            for path in (SKILL / "scripts").glob("*.py")
            if path.name != "__init__.py"
        }
        self.assertEqual(declared, scripts)

    def test_python_enforcer_reports_the_skill_clean(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ENFORCER),
             "--root", str(SKILL), "--config", CONFIG.name, "--format", "json"],
            cwd=ROOT, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        declared = sum(len(unit["paths"]) for unit in config["units"])
        self.assertEqual(payload["sourceFiles"], declared)
        self.assertEqual(payload["findings"], [])
        self.assertEqual(payload["level"], "L1")
        self.assertEqual(len(payload["execution"]), 56)

    def test_self_preflight_excludes_generated_vendor_from_source_ownership(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SKILL / "scripts/preflight.py"),
             "--project", str(SKILL), "--format", "json",
             "--manifest", str(SKILL / "manifest.json")],
            cwd=ROOT, capture_output=True, text=True,
        )
        self.assertIn(result.returncode, (0, 1), result.stderr)
        report = json.loads(result.stdout)
        checks = {check["id"]: check for check in report["checks"]}
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        declared = sum(len(unit["paths"]) for unit in config["units"])
        self.assertEqual(checks["TGT-002"]["status"], "pass")
        self.assertIn(f"{declared} source files", checks["TGT-002"]["detail"])
        self.assertEqual(checks["GOV-002"]["status"], "pass")
        self.assertEqual(report["moduleMap"]["status"], "authoritative")


if __name__ == "__main__":
    unittest.main()
