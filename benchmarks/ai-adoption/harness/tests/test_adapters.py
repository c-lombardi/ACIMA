"""Adapter contract: success, unsupported, authentication, timeout, capture."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from support import HARNESS_ROOT, invocation, script

from adapters.base import (
    AgentExecution,
    AuthenticationFailure,
    Control,
    UnsupportedHeadlessExecution,
)
from adapters.fake import FakeAdapter
from adapters.freebuff import FreebuffAdapter
from runner.provenance import load_config


class FakeAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.events = self.root / "events.jsonl"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _run(self, payload: dict, *, timeout: float = 10.0, mode: str = "read-only"):
        inv = invocation(self.root, mode=mode, timeout=timeout)
        control = Control(inv, self.events, 1_000_000)
        return FakeAdapter(script=payload).execute(inv, control), inv

    def test_completed_execution_captures_output_and_events(self) -> None:
        execution, inv = self._run(script({"summary": "ok"}))
        self.assertEqual(execution.status, "completed")
        self.assertTrue((inv.output_dir / "agent-output.json").is_file())
        self.assertEqual(json.loads((inv.output_dir / "agent-output.json").read_text())["summary"], "ok")
        self.assertEqual(len(execution.tool_calls), 1)
        self.assertEqual(execution.files_read, ["src/orders/api.py"])
        self.assertEqual(execution.token_usage, {"input": 100, "output": 50})
        self.assertIn("adapter-start", self.events.read_text(encoding="utf-8"))

    def test_unsupported_execution_is_explicit(self) -> None:
        with self.assertRaises(UnsupportedHeadlessExecution):
            self._run(script(behavior="unsupported"))

    def test_authentication_failure_is_explicit(self) -> None:
        with self.assertRaises(AuthenticationFailure):
            self._run(script(behavior="auth-failure"))

    def test_partial_execution_reports_failure(self) -> None:
        execution, _inv = self._run(script(behavior="partial"))
        self.assertEqual(execution.status, "failed")
        self.assertTrue(execution.errors)

    def test_timeout_is_reported_not_raised(self) -> None:
        execution, _inv = self._run(script(sleepSeconds=3), timeout=0.3)
        self.assertEqual(execution.status, "timed_out")
        self.assertEqual(execution.termination_reason, "execution deadline reached")

    def test_writes_are_visible_to_the_controller(self) -> None:
        execution, inv = self._run(script(writeFiles={"acima.config.json": "{}"}))
        self.assertTrue((inv.repository_dir / "acima.config.json").is_file())
        self.assertIn("acima.config.json", execution.files_modified)

    def test_declared_capabilities(self) -> None:
        capabilities = FakeAdapter(script={}).capabilities()
        self.assertEqual(capabilities.provider, "fake")
        self.assertTrue(capabilities.headless)
        self.assertIn("not a model", " ".join(capabilities.notes))


class FreebuffAdapterTests(unittest.TestCase):
    def test_capabilities_never_claim_headless_execution(self) -> None:
        capabilities = FreebuffAdapter().capabilities()
        self.assertEqual(capabilities.provider, "freebuff")
        self.assertFalse(capabilities.headless)
        self.assertIn("helpSha256", capabilities.evidence)
        self.assertTrue(capabilities.notes)

    def test_execute_refuses_unsupported_invocation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inv = invocation(root)
            control = Control(inv, root / "events.jsonl", 10_000)
            with self.assertRaises(UnsupportedHeadlessExecution):
                FreebuffAdapter().execute(inv, control)


class ExecutionRecordTests(unittest.TestCase):
    def test_unknown_status_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            AgentExecution(status="maybe")

    def test_record_shape_is_provider_neutral(self) -> None:
        record = AgentExecution(status="completed", duration_seconds=1.23456).as_record()
        for key in ("status", "exitCode", "durationSeconds", "messages", "toolCalls", "commands",
                    "filesRead", "filesModified", "tests", "tokenUsage", "errors",
                    "terminationReason"):
            self.assertIn(key, record)
        self.assertEqual(record["durationSeconds"], 1.235)

    def test_limits_are_frozen(self) -> None:
        _config, limits = load_config(HARNESS_ROOT)
        with self.assertRaises(Exception):
            limits.execution_timeout_seconds = 1  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
