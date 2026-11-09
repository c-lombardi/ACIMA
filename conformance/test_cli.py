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


    def test_repository_under_a_hidden_directory_still_has_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / ".hidden" / "project"
            (root / "src").mkdir(parents=True)
            (root / "src" / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
            code, report = acima.assess_project(root)
            self.assertEqual(code, 0)
            self.assertEqual(report["sourceFiles"], 1)
            self.assertEqual(report["verdict"], "NEEDS_UNIT_MAP")


    def test_status_reports_pending_steps_on_an_unadopted_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
            report = acima.status_project(root)
            self.assertFalse(report["config"]["present"])
            self.assertEqual(len(report["steps"]), 11)
            self.assertEqual(report["steps"][0]["state"], "READY")
            self.assertIn("assess", report["next"]["command"])
            self.assertIn("preflight.py", report["next"]["command"])
            self.assertFalse(report["next"]["writes"])

    def test_status_marks_the_declared_example(self) -> None:
        report = acima.status_project(ROOT / "examples/python")
        self.assertTrue(report["config"]["present"])
        self.assertEqual(report["config"]["units"], 11)
        states = {step["name"]: step["state"] for step in report["steps"]}
        self.assertEqual(states["declare"], "COMPLETE")
        self.assertIn("11 unit", report["steps"][4]["evidence"])
        self.assertTrue(report["next"]["action"])
        self.assertIn(report["steps"][5]["state"],
                      {"NOT_STARTED", "IN_PROGRESS", "COMPLETE", "BLOCKED"})


    def test_fix_names_the_remedy_for_one_selector(self) -> None:
        _code, payload, error, _language = acima.analyze_project(
            ROOT / "examples/python", config_name="acima.gallery.config.json")
        self.assertIsNotNone(payload, error)
        rule = payload["findings"][0]["rule"]
        plan = acima.fix_plan(payload, [rule])
        self.assertEqual(plan["unmatched"], [])
        self.assertEqual(plan["code"], 0)
        self.assertTrue(plan["findings"])
        for entry in plan["findings"]:
            self.assertEqual(entry["rule"], rule)
            self.assertTrue(entry["fix"])
            self.assertIn(entry["shape"], acima.CORRECTION_SHAPES)

    def test_fix_fails_on_a_selector_that_matches_nothing(self) -> None:
        plan = acima.fix_plan({"findings": []}, ["ACIMA-D001"])
        self.assertEqual(plan["selected"], 0)
        self.assertEqual(plan["unmatched"], ["ACIMA-D001"])
        self.assertEqual(plan["code"], 1)

    def test_fix_all_covers_every_finding(self) -> None:
        _code, payload, error, _language = acima.analyze_project(
            ROOT / "examples/python", config_name="acima.gallery.config.json")
        self.assertIsNotNone(payload, error)
        plan = acima.fix_plan(payload, [], all_findings=True)
        self.assertEqual(plan["selected"], len(payload["findings"]))
        self.assertEqual(plan["unmatched"], [])

if __name__ == "__main__":
    unittest.main()
