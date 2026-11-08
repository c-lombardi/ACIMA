"""Tests for the thin `acima` developer entry point."""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("acima_cli", ROOT / "tools/acima.py")
acima = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(acima)


class CliTests(unittest.TestCase):
    def test_inspect_detects_declared_python_example(self) -> None:
        payload = acima.inspect_project(ROOT / "examples/python")
        self.assertEqual(payload["language"], "python")
        self.assertEqual(payload["mode"], "adopting")
        self.assertEqual(payload["declaredLevel"], "L3")
        self.assertEqual(len(payload["units"]), 11)
        self.assertTrue(payload["enforcerAvailable"])

    def test_analyze_clean_example(self) -> None:
        code, payload, error, language = acima.analyze_project(ROOT / "examples/python")
        self.assertEqual(code, 0, error)
        self.assertEqual(language, "python")
        self.assertEqual(payload["findings"], [])

    def test_analyze_gallery_is_structured(self) -> None:
        code, payload, error, _language = acima.analyze_project(
            ROOT / "examples/python", config_name="acima.gallery.config.json")
        self.assertEqual(code, 1, error)
        self.assertGreater(len(payload["findings"]), 0)
        for finding in payload["findings"]:
            for key in ("rule", "severity", "message", "path", "line"):
                self.assertIn(key, finding)

    def test_report_is_explicit_about_unevaluated_rules(self) -> None:
        config = acima.read_config(ROOT / "examples/python")
        _code, payload, error, language = acima.analyze_project(
            ROOT / "examples/python", config_name="acima.gallery.config.json")
        self.assertIsNotNone(payload, error)
        markdown = acima.report_markdown(ROOT / "examples/python", payload, language, config)
        self.assertIn("not a single health score", markdown)
        self.assertIn("Not evaluated by this run", markdown)
        self.assertIn("ACIMA-C003", markdown)
        self.assertIn("ACIMA-G004", markdown)

    def test_malformed_config_is_a_tool_failure_not_a_traceback(self) -> None:
        import subprocess

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "acima.config.json").write_text("{", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(ROOT / "tools/acima.py"), "inspect", "--root", str(root)],
                cwd=ROOT, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("cannot read config", result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_unknown_language_is_a_tool_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "notes.txt").write_text("no source", encoding="utf-8")
            code, payload, error, _language = acima.analyze_project(root)
            self.assertEqual(code, 2)
            self.assertIsNone(payload)
            self.assertIn("language", error)

    def test_json_report_has_no_invented_score(self) -> None:
        _code, payload, error, _language = acima.analyze_project(ROOT / "examples/python")
        self.assertIsNotNone(payload, error)
        report = {
            "summary": acima.summarize(payload),
            "limitation": "Evidence only; no productivity or health score is inferred.",
        }
        self.assertNotIn("score", report["summary"])
        self.assertIn("no productivity", report["limitation"])


if __name__ == "__main__":
    unittest.main()
