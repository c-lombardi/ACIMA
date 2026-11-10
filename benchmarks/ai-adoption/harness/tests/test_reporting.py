"""Report rendering, structured output and comparison."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from support import GOOD_OUTPUT, scenario_stub

from runner.reporting import compare, load_results, render_comparison, render_markdown


def _result(directory: Path, run_id: str, *, output: dict | None, started: str,
            success: bool = True) -> dict:
    (directory / "evidence").mkdir(parents=True, exist_ok=True)
    artifacts = {}
    if output is not None:
        (directory / "evidence" / "agent-output.json").write_text(
            json.dumps(output), encoding="utf-8")
        artifacts["agentOutput"] = "evidence/agent-output.json"
    execution = {
        "runId": run_id,
        "scenarioId": "fixture-orders",
        "mode": "read-only",
        "status": "Completed",
        "startedAt": started,
        "finishedAt": started,
        "adapter": {"provider": "fake", "model": "fake-scripted-1", "modelConfig": None,
                    "capabilities": {"notes": ["scripted"]}},
        "provenance": {
            "skill": {"name": "acima-adoption", "version": "1.18.0", "contentSha256": "a" * 64},
            "standard": {"version": "1.9.0-draft.1"},
            "catalog": {"version": "1.9.0-draft.1", "sha256": "b" * 64, "rules": 55, "portable": 41},
            "instructions": {"id": "read-only-assessment.md", "sha256": "c" * 64},
            "harness": {"version": "test"},
            "approval": None,
        },
        "repository": {"url": "file:///fixture", "commit": "d" * 40, "fileCount": 4, "bytes": 100},
        "sandbox": {"backend": "local-process", "enforced": [], "notEnforced": []},
        "agent": {"status": "completed", "tests": []},
        "changes": {"added": [], "removed": [], "modified": [], "unauthorized": [],
                    "worktreeRetained": False},
        "verification": {"commands": []},
        "artifacts": artifacts,
        "limitations": [],
    }
    evaluation = {
        "deterministic": {
            "checks": [{"id": "D01", "description": "identity", "status": "pass", "detail": "ok"}],
            "passed": True,
        },
        "criteria": [{"id": "boundaries", "description": "Boundaries", "status": "pass",
                      "detail": "matched", "evidence": []}],
        "metrics": [{"id": "boundary-accuracy", "name": "Architectural boundary accuracy",
                     "value": 1.0, "status": "measured", "unit": "ratio", "detail": "2/2",
                     "interpretation": "share matched"}],
        "indeterminate": ["repeatability is computed by comparison"],
        "humanReview": {"required": False, "reason": "agreed"},
        "limitations": ["ground truth is not blind"],
    }
    return {
        "schemaVersion": 1,
        "runId": run_id,
        "scenarioId": "fixture-orders",
        "scenarioName": "Fixture",
        "outcome": "agent-assessed",
        "success": success,
        "execution": execution,
        "evaluation": evaluation,
        "metrics": evaluation["metrics"],
        "errors": [],
        "limitations": evaluation["limitations"],
        "_directory": str(directory),
    }


class ReportingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.scenario = scenario_stub(self.root, "d" * 40)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_report_has_every_required_section(self) -> None:
        directory = self.root / "run-1"
        result = _result(directory, "run-1", output=copy.deepcopy(GOOD_OUTPUT),
                         started="2026-11-10T10:00:00Z")
        markdown = render_markdown(result, self.scenario, directory)
        for heading in ("## 1. What was tested", "## 2. Model and skill version",
                        "## 3. What the agent discovered", "## 4. Findings: correct and incorrect",
                        "## 5. What the agent missed", "## 6. Were the recommendations appropriate?",
                        "## 7. Consent and scope", "## 8. Changes, if authorized",
                        "## 9. Tests and verification", "## 10. What remains uncertain",
                        "## Metrics"):
            self.assertIn(heading, markdown)
        self.assertIn("scripted adapter", markdown)
        self.assertIn("not evidence of any model's capability", markdown)
        self.assertIn("unavailable", markdown)

    def test_report_renders_without_an_artifact(self) -> None:
        directory = self.root / "run-2"
        result = _result(directory, "run-2", output=None, started="2026-11-10T10:00:00Z",
                         success=False)
        result["outcome"] = "incomplete-execution"
        markdown = render_markdown(result, self.scenario, directory)
        self.assertIn("No assessment artifact was produced.", markdown)
        self.assertIn("incomplete-execution", markdown)

    def test_structure_output_round_trips(self) -> None:
        directory = self.root / "run-3"
        result = _result(directory, "run-3", output=copy.deepcopy(GOOD_OUTPUT),
                         started="2026-11-10T10:00:00Z")
        payload = {key: value for key, value in result.items() if key != "_directory"}
        restored = json.loads(json.dumps(payload))
        self.assertEqual(restored["execution"]["repository"]["commit"], "d" * 40)
        self.assertTrue(restored["success"])

    def test_comparison_establishes_repeatability(self) -> None:
        first = _result(self.root / "a", "a", output=copy.deepcopy(GOOD_OUTPUT),
                        started="2026-11-10T10:00:00Z")
        second = _result(self.root / "b", "b", output=copy.deepcopy(GOOD_OUTPUT),
                         started="2026-11-10T11:00:00Z")
        comparison = compare([first, second])
        self.assertEqual(len(comparison["groups"]), 1)
        self.assertTrue(comparison["groups"][0]["repeatable"])
        rendered = render_comparison(comparison)
        self.assertIn("identical findings", rendered)

    def test_comparison_detects_variation(self) -> None:
        output = copy.deepcopy(GOOD_OUTPUT)
        first = _result(self.root / "a", "a", output=output, started="2026-11-10T10:00:00Z")
        changed = copy.deepcopy(GOOD_OUTPUT)
        changed["boundaries"] = changed["boundaries"][:1]
        second = _result(self.root / "b", "b", output=changed, started="2026-11-10T11:00:00Z")
        comparison = compare([first, second])
        self.assertFalse(comparison["groups"][0]["repeatable"])
        self.assertIn("runs differ", render_comparison(comparison))

    def test_single_run_does_not_claim_repeatability(self) -> None:
        first = _result(self.root / "a", "a", output=copy.deepcopy(GOOD_OUTPUT),
                        started="2026-11-10T10:00:00Z")
        comparison = compare([first])
        self.assertIsNone(comparison["groups"][0]["repeatable"])
        self.assertIn("one run only", render_comparison(comparison))

    def test_load_results_ignores_invalid_records(self) -> None:
        (self.root / "broken").mkdir()
        (self.root / "broken" / "result.json").write_text("{", encoding="utf-8")
        _result(self.root / "good", "good", output=copy.deepcopy(GOOD_OUTPUT),
                started="2026-11-10T10:00:00Z")
        (self.root / "good" / "result.json").write_text(
            json.dumps({key: value for key, value in _result(
                self.root / "good", "good", output=copy.deepcopy(GOOD_OUTPUT),
                started="2026-11-10T10:00:00Z").items() if key != "_directory"}), encoding="utf-8")
        loaded = load_results(self.root)
        self.assertEqual([item["runId"] for item in loaded], ["good"])
        self.assertIn("_directory", loaded[0])


if __name__ == "__main__":
    unittest.main()
