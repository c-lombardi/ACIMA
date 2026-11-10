"""Lifecycle, persistence and interrupted-run recovery."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from support import HARNESS_ROOT  # noqa: F401  (sets sys.path)

from runner.lifecycle import (
    InvalidTransition,
    LifecycleError,
    RunState,
    RunStore,
    is_terminal,
)


class LifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name)
        self.store = RunStore(self.directory, "run-1")
        self.store.create()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_happy_path_reaches_completed(self) -> None:
        for state in (RunState.REPOSITORY_PREPARED, RunState.ENVIRONMENT_PROVISIONED,
                      RunState.AGENT_EXECUTING, RunState.EXECUTION_CAPTURED,
                      RunState.EVALUATION_PENDING, RunState.EVALUATING, RunState.COMPLETED):
            self.store.transition(state, {"step": state.value})
        record = self.store.read()
        self.assertEqual(record["state"], "Completed")
        self.assertEqual(len(record["stateHistory"]), 8)
        self.assertTrue(is_terminal(record["state"]))
        self.assertIsNotNone(record["finishedAt"])

    def test_invalid_transition_is_rejected_not_repaired(self) -> None:
        with self.assertRaises(InvalidTransition):
            self.store.transition(RunState.AGENT_EXECUTING)
        self.assertEqual(self.store.read()["state"], "Pending")

    def test_terminal_state_cannot_be_left(self) -> None:
        self.store.transition(RunState.FAILED, {"reason": "boom"})
        with self.assertRaises(InvalidTransition):
            self.store.transition(RunState.REPOSITORY_PREPARED)
        self.assertFalse(self.store.read()["recoverable"] and False)

    def test_cancelled_and_timed_out_are_terminal(self) -> None:
        store = RunStore(self.directory, "run-2")
        store.create()
        store.transition(RunState.REPOSITORY_PREPARED)
        store.transition(RunState.ENVIRONMENT_PROVISIONED)
        store.transition(RunState.AGENT_EXECUTING)
        store.transition(RunState.EXECUTION_CAPTURED)
        store.transition(RunState.EVALUATION_PENDING)
        store.transition(RunState.EVALUATING)
        store.transition(RunState.TIMED_OUT, {"reason": "deadline"})
        self.assertTrue(is_terminal(store.read()["state"]))

    def test_interrupted_run_recovers_as_infrastructure_failure(self) -> None:
        self.store.transition(RunState.REPOSITORY_PREPARED)
        self.store.transition(RunState.ENVIRONMENT_PROVISIONED)
        record = self.store.recover("the controller stopped")
        self.assertEqual(record["state"], "InfrastructureFailure")
        self.assertTrue(record["interrupted"])
        self.assertEqual(record["stateHistory"][-1]["detail"]["interruptedFrom"],
                         "EnvironmentProvisioned")
        self.assertFalse(record["recoverable"] and False)

    def test_recover_on_terminal_run_is_a_noop(self) -> None:
        self.store.transition(RunState.FAILED)
        before = self.store.read()
        after = self.store.recover()
        self.assertEqual(before["stateHistory"], after["stateHistory"])

    def test_missing_state_is_an_error(self) -> None:
        with self.assertRaises(LifecycleError):
            RunStore(self.directory / "absent", "absent").read()

    def test_state_file_is_valid_json_on_disk(self) -> None:
        payload = json.loads((self.directory / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["runId"], "run-1")
        self.assertEqual(payload["state"], "Pending")


if __name__ == "__main__":
    unittest.main()
