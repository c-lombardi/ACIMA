"""End-to-end controller runs against a local pinned repository."""
from __future__ import annotations

import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from support import (
    GOOD_OUTPUT, approval, execution_stub, make_repository, scenario_stub, script, write_json,
)

from adapters.fake import FakeAdapter
from adapters.freebuff import FreebuffAdapter
from runner.controller import BenchmarkController
from runner.lifecycle import RunState
from runner.reporting import compare, load_results
from runner.schema import SchemaError, validate
from support import HARNESS_ROOT


@unittest.skipUnless(shutil.which("git"), "git is required")
class EndToEndTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.origin, self.commit = make_repository(self.root / "origin")
        self.scenario = scenario_stub(self.origin, self.commit)
        self.controller = BenchmarkController(HARNESS_ROOT, results_root=self.root / "results")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _run(self, payload: dict, **kwargs):
        return self.controller.run(
            self.scenario["id"], FakeAdapter(script=payload), scenario=self.scenario, **kwargs
        )

    def _metric(self, result, identifier):
        return next(metric for metric in result["metrics"] if metric["id"] == identifier)

    def test_successful_read_only_assessment(self) -> None:
        result = self._run(script(copy.deepcopy(GOOD_OUTPUT)))
        self.assertEqual(result["outcome"], "agent-assessed")
        self.assertTrue(result["success"], result["errors"])
        self.assertEqual(result["execution"]["status"], RunState.COMPLETED.value)
        self.assertEqual(self._metric(result, "boundary-accuracy")["status"], "indeterminate")
        self.assertTrue(result["evaluation"]["humanReview"]["required"])
        self.assertEqual(self._metric(result, "finding-precision")["value"], 1.0)
        self.assertEqual(self._metric(result, "finding-recall")["value"], 1.0)
        self.assertEqual(self._metric(result, "scope-adherence")["value"], 1.0)
        self.assertTrue(result["evaluation"]["deterministic"]["passed"])
        # An in-process adapter is not sandboxed, and the record must not imply that it was.
        self.assertFalse(result["execution"]["sandbox"]["agentIsolated"])
        self.assertTrue(any("controller process" in item for item in result["limitations"]))

        directory = self.root / "results" / result["runId"]
        for name in ("state.json", "execution.json", "evaluation.json", "result.json", "report.md"):
            self.assertTrue((directory / name).is_file(), name)
        for name in ("instructions.md", "events.jsonl", "agent-output.json",
                     "files-before.json", "files-after.json", "changes.json", "repository.json"):
            self.assertTrue((directory / "evidence" / name).is_file(), name)
        self.assertFalse((directory / "workspace").exists(), "the disposable workspace is cleaned up")

        schema = json.loads((HARNESS_ROOT / "harness" / "schemas" / "result.schema.json").read_text(encoding="utf-8"))
        validate({key: value for key, value in result.items() if key != "_directory"}, schema)
        execution_schema = json.loads(
            (HARNESS_ROOT / "harness" / "schemas" / "execution.schema.json").read_text(encoding="utf-8"))
        validate(result["execution"], execution_schema)
        evaluation_schema = json.loads(
            (HARNESS_ROOT / "harness" / "schemas" / "evaluation.schema.json").read_text(encoding="utf-8"))
        validate(result["evaluation"], evaluation_schema)

    def test_scope_violation_makes_the_run_unsuccessful(self) -> None:
        output = copy.deepcopy(GOOD_OUTPUT)
        output["profiles"] = ["base", "library"]
        output["findings"][0]["rule"] = "ACIMA-Z999"
        result = self._run(script(output, writeFiles={"acima.config.json": "{}"}))
        self.assertEqual(result["outcome"], "agent-scope-violation")
        self.assertFalse(result["success"])
        checks = {check["id"]: check for check in result["evaluation"]["deterministic"]["checks"]}
        self.assertEqual(checks["D07"]["status"], "fail")
        self.assertEqual(checks["D08"]["status"], "fail")
        self.assertEqual(self._metric(result, "profile-selection")["value"], 0.0)
        self.assertEqual(self._metric(result, "scope-adherence")["value"], 0.0)

    def test_failed_agent_execution_is_not_successful(self) -> None:
        result = self._run(script(behavior="partial"))
        self.assertEqual(result["outcome"], "failed")
        self.assertFalse(result["success"])
        self.assertEqual(result["execution"]["status"], RunState.FAILED.value)
        checks = {check["id"]: check for check in result["evaluation"]["deterministic"]["checks"]}
        self.assertEqual(checks["D05"]["status"], "fail")
        self.assertTrue(result["evaluation"]["humanReview"]["required"])
        self.assertTrue(all(metric["status"] != "measured"
                            for metric in result["metrics"] if metric["id"] == "boundary-accuracy"))

    def test_timed_out_execution_is_terminal_and_unsuccessful(self) -> None:
        from dataclasses import replace
        from runner.provenance import load_config

        _config, limits = load_config(HARNESS_ROOT)
        controller = BenchmarkController(
            HARNESS_ROOT, results_root=self.root / "results-timeout",
            limits=replace(limits, execution_timeout_seconds=1),
        )
        result = controller.run(self.scenario["id"], FakeAdapter(script=script(sleepSeconds=10)),
                                scenario=self.scenario)
        self.assertEqual(result["outcome"], "timed-out")
        self.assertEqual(result["execution"]["status"], RunState.TIMED_OUT.value)
        self.assertFalse(result["success"])
        self.assertEqual(result["execution"]["agent"]["status"], "timed_out")
        directory = self.root / "results-timeout" / result["runId"]
        self.assertTrue((directory / "result.json").is_file())
        self.assertIn("timed-out", (directory / "report.md").read_text(encoding="utf-8"))

    def test_unsupported_adapter_is_recorded_and_not_successful(self) -> None:
        result = self.controller.run(self.scenario["id"], FreebuffAdapter(), scenario=self.scenario)
        self.assertFalse(result["success"])
        self.assertIn(result["outcome"],
                      ("unsupported-execution", "invalid-configuration"))
        directory = self.root / "results" / result["runId"]
        state = json.loads((directory / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["state"], RunState.INVALID_CONFIGURATION.value)
        self.assertIsNotNone(state["finishedAt"])

    def test_authorized_adoption_inside_scope(self) -> None:
        scenario = scenario_stub(
            self.origin, self.commit,
            authorizedChanges={
                "approvedPaths": ["acima.config.json"],
                "level": "L1",
                "verificationCommands": [{
                    "name": "noop", "argv": [sys.executable, "-c", "print('ok')"],
                    "regression": True,
                }],
            },
        )
        approval_path = approval(self.root / "approval.json", ["acima.config.json"])
        output = copy.deepcopy(GOOD_OUTPUT)
        output["mode"] = "authorized-adoption"
        output["changesMade"] = [{"path": "acima.config.json", "kind": "config", "approved": True}]
        output["testsRun"] = [{"name": "noop-verification", "command": "noop", "passed": True}]
        result = self.controller.run(
            scenario["id"], FakeAdapter(script=script(
                output,
                writeFiles={"acima.config.json": "{\"units\": []}\n"},
                tests=[{"name": "noop-verification", "passed": True}],
            )),
            scenario=scenario, mode="authorized-adoption", approval_path=approval_path,
        )
        self.assertTrue(result["success"], result["errors"])
        self.assertIn("acima.config.json", result["execution"]["changes"]["added"])
        self.assertEqual(result["execution"]["changes"]["unauthorized"], [])
        self.assertEqual(self._metric(result, "scope-adherence")["value"], 1.0)
        self.assertEqual(self._metric(result, "adoption-effectiveness")["value"], 1.0)
        self.assertEqual(self._metric(result, "regression-rate")["value"], 0.0)
        self.assertEqual(len(result["execution"]["verification"]["commands"]), 1)

    def test_authorized_adoption_outside_scope_is_rejected(self) -> None:
        scenario = scenario_stub(self.origin, self.commit)
        approval_path = approval(self.root / "approval.json", ["acima.config.json"])
        output = copy.deepcopy(GOOD_OUTPUT)
        output["mode"] = "authorized-adoption"
        result = self.controller.run(
            scenario["id"], FakeAdapter(script=script(output, writeFiles={"src/hack.py": "x = 1\n"})),
            scenario=scenario, mode="authorized-adoption", approval_path=approval_path,
        )
        self.assertEqual(result["outcome"], "agent-scope-violation")
        self.assertFalse(result["success"])
        self.assertEqual(result["execution"]["changes"]["unauthorized"], ["src/hack.py"])

    def test_authorized_adoption_without_approval_is_invalid(self) -> None:
        scenario = scenario_stub(self.origin, self.commit)
        result = self.controller.run(
            scenario["id"], FakeAdapter(script=script(copy.deepcopy(GOOD_OUTPUT))),
            scenario=scenario, mode="authorized-adoption",
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["outcome"], "invalid-configuration")

    def test_repeated_runs_are_comparable(self) -> None:
        for _index in range(2):
            self._run(script(copy.deepcopy(GOOD_OUTPUT)))
        results = load_results(self.root / "results")
        comparison = compare(results)
        self.assertEqual(len(comparison["groups"]), 1)
        self.assertEqual(comparison["groups"][0]["runs"], 2)
        self.assertTrue(comparison["groups"][0]["repeatable"])

    def test_wrong_commit_is_an_infrastructure_or_configuration_outcome(self) -> None:
        scenario = scenario_stub(self.origin, "0" * 40)
        result = self.controller.run(
            scenario["id"], FakeAdapter(script=script(copy.deepcopy(GOOD_OUTPUT))),
            scenario=scenario,
        )
        self.assertFalse(result["success"])
        self.assertIn(result["outcome"], ("infrastructure-failure", "invalid-configuration"))
        self.assertFalse(result["evaluation"]["deterministic"]["passed"])

    def test_scenario_schema_rejects_an_invalid_scenario(self) -> None:
        scenario = scenario_stub(self.origin, self.commit)
        scenario["repository"]["commit"] = "HEAD"
        with self.assertRaises(SchemaError):
            self.controller.run(scenario["id"], FakeAdapter(script=script(None)), scenario=scenario)


if __name__ == "__main__":
    unittest.main()
