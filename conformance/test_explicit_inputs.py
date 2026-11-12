"""Contract tests for D011/D012: required inputs stay visible at construction and invocation."""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = [sys.executable, str(ROOT / "examples/python/tools/acima_arch.py")]
TYPESCRIPT = ["node", str(ROOT / "examples/typescript/tools/acima-arch.mjs")]
FIXTURES = ROOT / "conformance/fixtures/explicit-inputs"


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


class ExplicitInputTests(unittest.TestCase):
    def test_catalog_prohibits_optional_parameters_on_module_owned_inputs(self) -> None:
        catalog = json.loads((ROOT / "tools/acima-spec/rules.json").read_text(encoding="utf-8"))
        rules = {rule["id"]: rule for rule in catalog["rules"]}
        for rule_id in ("ACIMA-D011", "ACIMA-D012"):
            rule = rules[rule_id]
            self.assertEqual(rule["level"], "L1")
            self.assertEqual(rule["severity"], "error")
            self.assertNotIn("severityRatchet", rule)
            self.assertEqual(rule["automation"], "automated")
        named_call = rules["ACIMA-D017"]
        self.assertEqual(named_call["severity"], "warning")
        self.assertEqual(named_call["severityRatchet"], {"to": "error", "at": "2.0.0"})
        self.assertEqual(len(catalog["rules"]), 56)

    def test_python_gallery_fires_both_rules_on_the_optional_fixtures(self) -> None:
        result, report = run(PYTHON, ROOT / "examples/python", "acima.gallery.config.json")
        self.assertEqual(result.returncode, 1)
        fired = paths_by_rule(report)
        self.assertEqual(fired["ACIMA-D011"],
                         {"violations/d011_optional_constructor_dependency.py"})
        self.assertEqual(fired["ACIMA-D012"], {"violations/d012_hidden_default.py",
                                                    "violations/l001_identifier_only.py"})
        self.assertTrue(report["execution"]["ACIMA-D011"]["executed"])
        self.assertTrue(report["execution"]["ACIMA-D012"]["executed"])
        self.assertTrue(report["execution"]["ACIMA-D017"]["executed"])
        self.assertEqual(
            fired["ACIMA-D017"],
            {"violations/d015_closure_capture.py", "violations/d017_unlabeled_arguments.py"},
        )

    def test_typescript_gallery_fires_both_rules_on_the_optional_fixtures(self) -> None:
        result, report = run(TYPESCRIPT, ROOT / "examples/typescript", "acima.gallery.config.json")
        self.assertEqual(result.returncode, 1)
        fired = paths_by_rule(report)
        self.assertEqual(fired["ACIMA-D011"], {"violations/d011_optional_constructor_dependency.ts"})
        self.assertEqual(fired["ACIMA-D012"], {"violations/d012_hidden_default.ts"})
        self.assertTrue(report["execution"]["ACIMA-D011"]["executed"])
        self.assertTrue(report["execution"]["ACIMA-D012"]["executed"])
        self.assertFalse(report["execution"]["ACIMA-D017"]["executed"])
        self.assertIn("native named-argument", report["execution"]["ACIMA-D017"]["reason"])

    def test_positive_fixtures_are_clean_and_required_nullable_is_not_a_finding(self) -> None:
        for language, command in (("python", PYTHON), ("typescript", TYPESCRIPT)):
            root = FIXTURES / language
            result, report = run(command, root)
            self.assertEqual(result.returncode, 0, report["findings"])
            self.assertEqual(report["findings"], [])
            self.assertTrue(report["execution"]["ACIMA-D011"]["executed"])
            self.assertTrue(report["execution"]["ACIMA-D012"]["executed"])
            self.assertTrue(report["execution"]["ACIMA-D017"]["executed"] if language == "python" else
                            not report["execution"]["ACIMA-D017"]["executed"])
            self.assertFalse(any(item["rule"] == "ACIMA-D017" for item in report["findings"]))

    def test_contracts_are_out_of_scope_and_say_so(self) -> None:
        catalog = json.loads((ROOT / "tools/acima-spec/rules.json").read_text(encoding="utf-8"))
        rule = next(item for item in catalog["rules"] if item["id"] == "ACIMA-D011")
        self.assertIn("constructor", rule["summary"].lower())
        chapter = (ROOT / "docs/standard/13-explicit-inputs.md").read_text(encoding="utf-8")
        self.assertIn("Contract types are data", chapter)
        self.assertIn("required nullable", chapter.lower())


if __name__ == "__main__":
    unittest.main()
