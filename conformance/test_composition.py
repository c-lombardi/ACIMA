"""Contract tests for D013/D014: composition and injection are explicit."""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = [sys.executable, str(ROOT / "examples/python/tools/acima_arch.py")]
TYPESCRIPT = ["node", str(ROOT / "examples/typescript/tools/acima-arch.mjs")]
FIXTURES = ROOT / "conformance/fixtures/composition"
BASE_LIBRARY = ROOT / "conformance/fixtures/library-base"


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


class CompositionTests(unittest.TestCase):
    def test_catalog_declares_both_rules_with_the_ratchet(self) -> None:
        catalog = json.loads((ROOT / "tools/acima-spec/rules.json").read_text(encoding="utf-8"))
        rules = {rule["id"]: rule for rule in catalog["rules"]}
        for rule_id in ("ACIMA-D013", "ACIMA-D014"):
            rule = rules[rule_id]
            self.assertEqual(rule["level"], "L1")
            self.assertEqual(rule["severity"], "warning")
            self.assertEqual(rule["severityRatchet"], {"to": "error", "at": "2.0.0"})
            self.assertEqual(rule["automation"], "automated")
        self.assertEqual(len(catalog["rules"]), 56)

    def test_python_gallery_fires_both_rules_on_the_composition_fixtures(self) -> None:
        result, report = run(PYTHON, ROOT / "examples/python", "acima.gallery.config.json")
        self.assertEqual(result.returncode, 1)
        fired = paths_by_rule(report)
        self.assertEqual(fired["ACIMA-D013"], {"violations/d013_dynamic_registration.py"})
        self.assertEqual(fired["ACIMA-D014"], {"violations/d014_property_injection.py"})

    def test_typescript_gallery_fires_both_rules_on_the_composition_fixtures(self) -> None:
        result, report = run(TYPESCRIPT, ROOT / "examples/typescript", "acima.gallery.config.json")
        self.assertEqual(result.returncode, 1)
        fired = paths_by_rule(report)
        self.assertEqual(fired["ACIMA-D013"], {"violations/d013_dynamic_registration.ts"})
        self.assertEqual(fired["ACIMA-D014"], {"violations/d014_property_injection.ts"})

    def test_positive_fixtures_are_clean_and_execute_both_rules(self) -> None:
        for language, command in (("python", PYTHON), ("typescript", TYPESCRIPT)):
            root = FIXTURES / language
            result, report = run(command, root)
            self.assertEqual(result.returncode, 0, report["findings"])
            self.assertEqual(report["findings"], [])
            self.assertTrue(report["execution"]["ACIMA-D013"]["executed"])
            self.assertTrue(report["execution"]["ACIMA-D014"]["executed"])

    def test_base_library_is_assessable_without_a_host(self) -> None:
        config = json.loads((BASE_LIBRARY / "acima.config.json").read_text(encoding="utf-8"))
        self.assertFalse(any(unit.get("role") == "host" for unit in config["units"]))
        result, report = run(PYTHON, BASE_LIBRARY)
        self.assertEqual(result.returncode, 0, report["findings"])
        self.assertEqual(report["findings"], [])

    def test_multiple_composition_boundaries_are_supported(self) -> None:
        result, report = run(
            PYTHON, FIXTURES / "python", "acima.multiple-hosts.config.json"
        )
        self.assertEqual(result.returncode, 0, report["findings"])
        self.assertEqual(report["findings"], [])

    def test_chapter_states_the_boundary_and_manual_limits(self) -> None:
        chapter = (ROOT / "docs/standard/15-composition-and-injection.md").read_text(encoding="utf-8")
        for phrase in ("composition boundary", "framework-managed", "property", "service locator",
                       "manual", "explicit"):
            self.assertIn(phrase.lower(), chapter.lower())


if __name__ == "__main__":
    unittest.main()
