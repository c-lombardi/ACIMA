"""Provider-independent agent execution interface.

An adapter executes a task; it never decides whether the benchmark succeeded. Success is computed
by the controller's deterministic checks and the independent evaluator.
"""
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Protocol

from runner.lifecycle import utcnow
from runner.provenance import Limits

READ_ONLY = "read-only"
AUTHORIZED_ADOPTION = "authorized-adoption"
EXECUTION_MODES = (READ_ONLY, AUTHORIZED_ADOPTION)

AGENT_STATUSES = ("completed", "failed", "timed_out", "cancelled", "unsupported", "unauthenticated", "not_run")


class AdapterFailure(RuntimeError):
    """The adapter could not execute the task."""


class UnsupportedHeadlessExecution(AdapterFailure):
    """The provider has no supported unattended invocation. Never worked around heuristically."""

    code = "unsupported-headless-execution"


class AuthenticationFailure(AdapterFailure):
    code = "authentication-failure"


@dataclass(frozen=True)
class AdapterCapabilities:
    provider: str
    headless: bool
    models: tuple[str, ...]
    notes: tuple[str, ...] = ()
    evidence: Mapping[str, Any] = field(default_factory=dict)
    # An in-process adapter runs inside the controller. The sandbox then governs only commands the
    # controller runs (verification), never the agent itself, and the run record must say so.
    in_process: bool = False

    def as_dict(self) -> dict:
        return {
            "provider": self.provider,
            "headless": self.headless,
            "models": list(self.models),
            "notes": list(self.notes),
            "evidence": dict(self.evidence),
            "inProcess": self.in_process,
        }


@dataclass(frozen=True)
class AgentInvocation:
    run_id: str
    scenario_id: str
    mode: str
    model: str
    model_config: Mapping[str, Any] | None
    repository_dir: Path
    output_dir: Path
    skill_dir: Path
    instructions: str
    limits: Limits
    approved_paths: tuple[str, ...]
    deadline: float

    def __post_init__(self) -> None:
        if self.mode not in EXECUTION_MODES:
            raise ValueError(f"unknown execution mode {self.mode!r}")


@dataclass
class AgentExecution:
    status: str = "not_run"
    exit_code: int | None = None
    duration_seconds: float | None = None
    messages: list[dict] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)
    commands: list[dict] = field(default_factory=list)
    files_read: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    tests: list[dict] = field(default_factory=list)
    token_usage: dict | None = None
    errors: list[str] = field(default_factory=list)
    termination_reason: str | None = None
    raw_evidence: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in AGENT_STATUSES:
            raise ValueError(f"unknown agent status {self.status!r}")

    def as_record(self) -> dict:
        return {
            "status": self.status,
            "exitCode": self.exit_code,
            "durationSeconds": None if self.duration_seconds is None else round(self.duration_seconds, 3),
            "messages": list(self.messages),
            "toolCalls": list(self.tool_calls),
            "commands": list(self.commands),
            "filesRead": list(self.files_read),
            "filesModified": list(self.files_modified),
            "tests": list(self.tests),
            "tokenUsage": self.token_usage,
            "errors": list(self.errors),
            "terminationReason": self.termination_reason,
            "rawEvidence": dict(self.raw_evidence),
        }


class Control:
    """Cancellation, deadline and event capture handed to an adapter."""

    def __init__(self, invocation: AgentInvocation, events_path: Path, max_event_bytes: int) -> None:
        self.invocation = invocation
        self.events_path = Path(events_path)
        self.max_event_bytes = max_event_bytes
        self._cancelled = threading.Event()
        self._lock = threading.Lock()
        self._written = 0
        self.truncated = False
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        self.events_path.write_text("", encoding="utf-8")

    def cancel(self) -> None:
        self._cancelled.set()

    @property
    def cancelled(self) -> bool:
        return self._cancelled.is_set()

    def remaining(self) -> float:
        return self.invocation.deadline - time.monotonic()

    @property
    def expired(self) -> bool:
        return self.remaining() <= 0

    def event(self, kind: str, **payload: Any) -> None:
        record = {"at": utcnow(), "kind": kind, **payload}
        line = json.dumps(record, sort_keys=True) + "\n"
        encoded = len(line.encode("utf-8"))
        with self._lock:
            if self._written + encoded > self.max_event_bytes:
                if not self.truncated:
                    self.truncated = True
                    marker = json.dumps({"at": utcnow(), "kind": "evidence-truncated",
                                         "limitBytes": self.max_event_bytes}) + "\n"
                    with self.events_path.open("a", encoding="utf-8") as stream:
                        stream.write(marker)
                return
            with self.events_path.open("a", encoding="utf-8") as stream:
                stream.write(line)
            self._written += encoded


class AgentAdapter(Protocol):
    name: str

    def capabilities(self) -> AdapterCapabilities:
        ...

    def execute(self, invocation: AgentInvocation, control: Control) -> AgentExecution:
        ...
