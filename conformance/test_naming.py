"""Contract tests for N001-N003: intent-revealing naming."""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = [sys.executable, str(ROOT / "examples/python/tools/acima_arch.py")]
TYPESCRIPT = ["node", str(ROOT / "examples/typescript/tools/acima-arch.mjs")]
FIXTURES = ROOT / "conformance/fixtures/naming"


def run(command: list[str], root: Path, config: str = "acima.config.json"):
    result = subprocess.run(command + ["--root", str(root), "--config", config,
                                       "--format", "json"],
                            capture_output=True, text=True)
    if not result.stdout.strip():
        raise AssertionError(result.stderr or "the enforcer printed nothing")
    return result, json.loads(result.stdout)


def paths_by_rule(report: dict) -> dict[str, set[str]]:
    fired: dict[str, set[str]] = {}
    for finding in report["findings"]:
        fired.setdefault(finding["rule"], set()).add(finding["path"])
    return fired


class NamingTests(unittest.TestCase):
    def test_catalog_declares_two_automated_rules_and_one_manual(self) -> None:
        catalog = json.loads((ROOT / "tools/acima-spec/rules.json").read_text(encoding="utf-8"))
        rules = {rule["id"]: rule for rule in catalog["rules"]}
        for rule_id in ("ACIMA-N001", "ACIMA-N002"):
            self.assertEqual(rules[rule_id]["level"], "L3")
            self.assertEqual(rules[rule_id]["severity"], "warning")
            self.assertEqual(rules[rule_id]["automation"], "automated")
            self.assertNotIn("severityRatchet", rules[rule_id])
        self.assertEqual(rules["ACIMA-N003"]["automation"], "manual")
        self.assertTrue(rules["ACIMA-N003"]["manualEvidence"])
        self.assertEqual(len(catalog["rules"]), 56)

    def test_python_gallery_fires_naming_rules(self) -> None:
        result, report = run(PYTHON, ROOT / "examples/python", "acima.gallery.config.json")
        self.assertEqual(result.returncode, 1)
        fired = paths_by_rule(report)
        for rule in ("ACIMA-N001", "ACIMA-N002"):
            self.assertEqual(fired[rule], {"violations/naming_conventions.py"})

    def test_typescript_gallery_fires_naming_rules(self) -> None:
        result, report = run(TYPESCRIPT, ROOT / "examples/typescript", "acima.gallery.config.json")
        self.assertEqual(result.returncode, 1)
        fired = paths_by_rule(report)
        for rule in ("ACIMA-N001", "ACIMA-N002"):
            self.assertEqual(fired[rule], {"violations/naming_conventions.ts"})

    def test_positive_fixtures_are_clean(self) -> None:
        for language, command in (("python", PYTHON), ("typescript", TYPESCRIPT)):
            result, report = run(command, FIXTURES / language)
            self.assertEqual(result.returncode, 0, report["findings"])
            self.assertEqual(report["findings"], [])
            self.assertTrue(report["execution"]["ACIMA-N001"]["executed"])
            self.assertTrue(report["execution"]["ACIMA-N002"]["executed"])
            self.assertFalse(report["execution"]["ACIMA-N003"]["executed"])

    def test_chapter_states_semantics_and_limits(self) -> None:
        chapter = (ROOT / "docs/standard/18-intent-revealing-naming.md").read_text(encoding="utf-8")
        for phrase in ("responsibility", "side effect", "boolean", "unit", "domain", "manual"):
            self.assertIn(phrase.lower(), chapter.lower())


if __name__ == "__main__":
    unittest.main()
