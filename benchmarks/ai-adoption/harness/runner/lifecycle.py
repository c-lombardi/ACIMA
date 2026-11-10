"""The benchmark execution lifecycle.

The controller — never the agent — owns this state machine. Every transition is validated,
persisted before the next step runs, and recorded with a timestamp and a detail. A run that is
still in a non-terminal state when the process disappears is reported as an interrupted
infrastructure failure, never as a success.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class RunState(str, Enum):
    PENDING = "Pending"
    REPOSITORY_PREPARED = "RepositoryPrepared"
    ENVIRONMENT_PROVISIONED = "EnvironmentProvisioned"
    AGENT_EXECUTING = "AgentExecuting"
    EXECUTION_CAPTURED = "ExecutionCaptured"
    EVALUATION_PENDING = "EvaluationPending"
    EVALUATING = "Evaluating"
    COMPLETED = "Completed"
    FAILED = "Failed"
    TIMED_OUT = "TimedOut"
    CANCELLED = "Cancelled"
    INVALID_CONFIGURATION = "InvalidConfiguration"
    INFRASTRUCTURE_FAILURE = "InfrastructureFailure"
    EVALUATION_FAILURE = "EvaluationFailure"


TERMINAL_STATES = frozenset({
    RunState.COMPLETED,
    RunState.FAILED,
    RunState.TIMED_OUT,
    RunState.CANCELLED,
    RunState.INVALID_CONFIGURATION,
    RunState.INFRASTRUCTURE_FAILURE,
    RunState.EVALUATION_FAILURE,
})

# The happy path, plus every explicit terminal outcome from any non-terminal state. Anything
# else is a programming error and is rejected rather than silently repaired.
ALLOWED_TRANSITIONS: dict[RunState, frozenset[RunState]] = {
    RunState.PENDING: frozenset({
        RunState.REPOSITORY_PREPARED, RunState.FAILED, RunState.TIMED_OUT, RunState.CANCELLED,
        RunState.INVALID_CONFIGURATION, RunState.INFRASTRUCTURE_FAILURE,
    }),
    RunState.REPOSITORY_PREPARED: frozenset({
        RunState.ENVIRONMENT_PROVISIONED, RunState.FAILED, RunState.TIMED_OUT,
        RunState.CANCELLED, RunState.INFRASTRUCTURE_FAILURE,
    }),
    RunState.ENVIRONMENT_PROVISIONED: frozenset({
        RunState.AGENT_EXECUTING, RunState.FAILED, RunState.TIMED_OUT, RunState.CANCELLED,
        RunState.INFRASTRUCTURE_FAILURE,
    }),
    RunState.AGENT_EXECUTING: frozenset({
        RunState.EXECUTION_CAPTURED, RunState.FAILED, RunState.TIMED_OUT, RunState.CANCELLED,
        RunState.INFRASTRUCTURE_FAILURE,
    }),
    RunState.EXECUTION_CAPTURED: frozenset({
        RunState.EVALUATION_PENDING, RunState.FAILED, RunState.INFRASTRUCTURE_FAILURE,
    }),
    RunState.EVALUATION_PENDING: frozenset({
        RunState.EVALUATING, RunState.EVALUATION_FAILURE, RunState.INFRASTRUCTURE_FAILURE,
    }),
    # A captured execution can still end as timed out or cancelled: the lifecycle records what
    # happened, and evaluation of the captured evidence does not turn a failure into a success.
    RunState.EVALUATING: frozenset({
        RunState.COMPLETED, RunState.EVALUATION_FAILURE, RunState.FAILED,
        RunState.TIMED_OUT, RunState.CANCELLED, RunState.INFRASTRUCTURE_FAILURE,
    }),
}

RESUMABLE_STATES = frozenset({
    RunState.EXECUTION_CAPTURED,
    RunState.EVALUATION_PENDING,
    RunState.EVALUATING,
})


class LifecycleError(RuntimeError):
    """Base class for lifecycle problems."""


class InvalidTransition(LifecycleError):
    """A caller asked for a transition the lifecycle does not allow."""

    def __init__(self, current: RunState, target: RunState) -> None:
        super().__init__(f"invalid transition {current.value} -> {target.value}")
        self.current = current
        self.target = target


class InvalidConfiguration(LifecycleError):
    """The run cannot start because its configuration is invalid."""


def is_terminal(state: RunState | str) -> bool:
    return RunState(state) in TERMINAL_STATES


def write_json_atomic(path: Path, payload: dict) -> None:
    """Write JSON so a crash leaves either the old file or the new one, never half of each."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


class RunStore:
    """Persisted lifecycle state for one run directory."""

    def __init__(self, directory: Path, run_id: str) -> None:
        self.directory = Path(directory)
        self.run_id = run_id
        self.path = self.directory / "state.json"

    def create(self, *, recoverable: bool = True) -> dict:
        now = utcnow()
        record = {
            "schemaVersion": 1,
            "runId": self.run_id,
            "state": RunState.PENDING.value,
            "stateHistory": [{"state": RunState.PENDING.value, "at": now, "detail": {}}],
            "startedAt": now,
            "updatedAt": now,
            "finishedAt": None,
            "recoverable": recoverable,
            "interrupted": False,
            "reason": None,
        }
        write_json_atomic(self.path, record)
        return record

    def read(self) -> dict:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise LifecycleError(f"no persisted state at {self.path}") from error
        except json.JSONDecodeError as error:
            raise LifecycleError(f"persisted state is not valid JSON: {error}") from error

    def transition(self, target: RunState | str, detail: dict | None = None) -> dict:
        record = self.read()
        current = RunState(record["state"])
        target = RunState(target)
        if target not in ALLOWED_TRANSITIONS.get(current, frozenset()):
            raise InvalidTransition(current, target)
        now = utcnow()
        record["state"] = target.value
        record["updatedAt"] = now
        record["stateHistory"].append({"state": target.value, "at": now, "detail": detail or {}})
        if target in TERMINAL_STATES:
            record["finishedAt"] = now
        if detail and detail.get("reason"):
            record["reason"] = detail["reason"]
        write_json_atomic(self.path, record)
        return record

    def recover(self, reason: str = "the controller stopped before the run reached a terminal state") -> dict:
        """Close an interrupted run honestly. Never called for a terminal run."""
        record = self.read()
        current = RunState(record["state"])
        if current in TERMINAL_STATES:
            return record
        record["interrupted"] = True
        write_json_atomic(self.path, record)
        return self.transition(
            RunState.INFRASTRUCTURE_FAILURE,
            {"reason": reason, "interruptedFrom": current.value, "recovered": True},
        )

    def ephemeral_directory(self, name: str) -> Path:
        path = self.directory / "workspace" / name
        path.mkdir(parents=True, exist_ok=True)
        return path
