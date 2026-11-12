"""Contract tests for D015/D016: closures and partial application stay visible."""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = [sys.executable, str(ROOT / "examples/python/tools/acima_arch.py")]
TYPESCRIPT = ["node", str(ROOT / "examples/typescript/tools/acima-arch.mjs")]
FIXTURES = ROOT / "conformance/fixtures/functional-composition"


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


class FunctionalCaptureTests(unittest.TestCase):
    def test_catalog_declares_both_rules_with_the_ratchet(self) -> None:
        catalog = json.loads((ROOT / "tools/acima-spec/rules.json").read_text(encoding="utf-8"))
        rules = {rule["id"]: rule for rule in catalog["rules"]}
        for rule_id in ("ACIMA-D015", "ACIMA-D016"):
            rule = rules[rule_id]
            self.assertEqual(rule["level"], "L1")
            self.assertEqual(rule["severity"], "warning")
            self.assertEqual(rule["severityRatchet"], {"to": "error", "at": "2.0.0"})
            self.assertEqual(rule["automation"], "automated")
        self.assertEqual(len(catalog["rules"]), 56)

    def test_python_gallery_fires_both_rules(self) -> None:
        result, report = run(PYTHON, ROOT / "examples/python", "acima.gallery.config.json")
        self.assertEqual(result.returncode, 1)
        fired = paths_by_rule(report)
        self.assertEqual(fired["ACIMA-D015"], {"violations/d015_closure_capture.py"})
        self.assertEqual(fired["ACIMA-D016"], {"violations/d016_partial_dependency.py"})

    def test_typescript_gallery_fires_both_rules(self) -> None:
        result, report = run(TYPESCRIPT, ROOT / "examples/typescript", "acima.gallery.config.json")
        self.assertEqual(result.returncode, 1)
        fired = paths_by_rule(report)
        self.assertEqual(fired["ACIMA-D015"], {"violations/d015_closure_capture.ts"})
        self.assertEqual(fired["ACIMA-D016"], {"violations/d016_partial_dependency.ts"})

    def test_positive_fixtures_are_clean(self) -> None:
        for language, command in (("python", PYTHON), ("typescript", TYPESCRIPT)):
            result, report = run(command, FIXTURES / language)
            self.assertEqual(result.returncode, 0, report["findings"])
            self.assertEqual(report["findings"], [])
            self.assertTrue(report["execution"]["ACIMA-D015"]["executed"])
            self.assertTrue(report["execution"]["ACIMA-D016"]["executed"])

    def test_chapter_allows_pure_hofs_and_explicit_currying(self) -> None:
        chapter = (ROOT / "docs/standard/16-functional-composition.md").read_text(encoding="utf-8")
        for phrase in ("currying", "partial application", "pure", "closure", "composition boundary"):
            self.assertIn(phrase.lower(), chapter.lower())


if __name__ == "__main__":
    unittest.main()
