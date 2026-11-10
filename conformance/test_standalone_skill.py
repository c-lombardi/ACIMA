"""Standalone integration test: a copied skill, no ACIMA checkout, a separate target.

The test copies only the skill directory (with its bundled vendor snapshot) into a temporary
location, runs the supported read-only workflow from there, and verifies that the generated
commands point at files that exist in that context and that the target is untouched.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/acima-adoption"


def snapshot(root: Path) -> dict:
    return {path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob("*") if path.is_file()}


class StandaloneSkillTests(unittest.TestCase):
    def test_copied_skill_runs_the_read_only_workflow_without_the_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            skill = workspace / "installed/acima-adoption"
            shutil.copytree(SKILL, skill)
            self.assertTrue((skill / "vendor/tools/acima.py").is_file())
            self.assertFalse((workspace / "tools/acima.py").exists())

            target = workspace / "application"
            (target / "src").mkdir(parents=True)
            (target / "src" / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
            before = snapshot(target)

            status = subprocess.run(
                [sys.executable, str(skill / "vendor/tools/acima.py"),
                 "status", "--root", str(target), "--format", "json"],
                cwd=target, capture_output=True, text=True)
            self.assertEqual(status.returncode, 0, status.stderr)
            report = json.loads(status.stdout)
            self.assertEqual(report["context"]["context"], "vendor")
            command = report["next"]["command"]
            self.assertIn("vendor/tools/acima.py", command)
            for quoted in re.findall(r'"([^"]+)"', command):
                self.assertTrue(Path(quoted).is_file(), quoted)
            self.assertFalse(report["next"]["approvalRequired"])
            self.assertFalse(report["next"]["writes"])

            assessed = subprocess.run(
                [sys.executable, str(skill / "vendor/tools/acima.py"),
                 "assess", "--root", str(target), "--format", "json"],
                cwd=target, capture_output=True, text=True)
            self.assertEqual(assessed.returncode, 0, assessed.stderr)
            assessment = json.loads(assessed.stdout)
            self.assertEqual(assessment["verdict"], "NEEDS_UNIT_MAP")
            self.assertTrue(assessment["readOnly"])

            preflight = subprocess.run(
                [sys.executable, str(skill / "scripts/preflight.py"),
                 "--project", str(target), "--format", "json"],
                cwd=target, capture_output=True, text=True)
            self.assertIn(preflight.returncode, (0, 1), preflight.stderr)
            checks = json.loads(preflight.stdout)["checks"]
            self.assertTrue(checks)
            skill_checks = [check for check in checks if check["id"].startswith("SKL-")]
            self.assertTrue(skill_checks)
            self.assertTrue(all(check["status"] == "pass" for check in skill_checks),
                            [check for check in skill_checks if check["status"] != "pass"])

            self.assertEqual(snapshot(target), before,
                             "the standalone read-only workflow changed the target")


if __name__ == "__main__":
    unittest.main()
