"""Deterministic scripted adapter for tests and for demonstrating the pipeline.

A script describes what the simulated agent does: events, files read, commands, tests, the output
envelope and — deliberately allowed — files it writes. It never has access to scenario ground
truth. Every behaviour is reproducible and requires no model, network or credentials.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .base import (
    AdapterCapabilities,
    AgentExecution,
    AgentInvocation,
    AuthenticationFailure,
    Control,
    UnsupportedHeadlessExecution,
)

SCRIPT_VERSION = 1
DEFAULT_MODEL = "fake-scripted-1"


class FakeAdapter:
    name = "fake"

    def __init__(self, script: dict | None = None, *, script_path: Path | None = None,
                 model: str | None = None) -> None:
        if script is None and script_path is not None:
            script = json.loads(Path(script_path).read_text(encoding="utf-8"))
        self.script = script or {}
        if not isinstance(self.script, dict):
            raise ValueError("fake adapter script must be a JSON object")
        self.model = model or self.script.get("model") or DEFAULT_MODEL

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            provider="fake",
            headless=True,
            models=(DEFAULT_MODEL,),
            notes=(
                "Deterministic scripted adapter. It exercises the harness; it is not a model and "
                "its results are not evidence of model capability.",
            ),
            evidence={"scriptVersion": SCRIPT_VERSION, "behaviour": self.script.get("behavior", "complete")},
            in_process=True,
        )

    def execute(self, invocation: AgentInvocation, control: Control) -> AgentExecution:
        started = time.monotonic()
        execution = AgentExecution()
        behavior = str(self.script.get("behavior", "complete"))
        control.event("adapter-start", provider=self.name, model=self.model, behavior=behavior)

        for event in self.script.get("events") or []:
            control.event("agent-event", **event)

        sleep_seconds = float(self.script.get("sleepSeconds") or 0)
        while sleep_seconds > 0:
            if control.cancelled:
                execution.status = "cancelled"
                execution.termination_reason = "cancelled by controller"
                break
            if control.expired:
                execution.status = "timed_out"
                execution.termination_reason = "execution deadline reached"
                break
            step = min(0.05, sleep_seconds, max(0.0, control.remaining()))
            if step <= 0:
                execution.status = "timed_out"
                execution.termination_reason = "execution deadline reached"
                break
            time.sleep(step)
            sleep_seconds -= step

        if behavior == "unsupported":
            raise UnsupportedHeadlessExecution(
                "the scripted adapter was configured to report an unsupported unattended invocation"
            )
        if behavior == "auth-failure":
            raise AuthenticationFailure("the scripted adapter was configured to fail authentication")
        if behavior == "partial":
            execution.status = "failed"
            execution.errors.append("simulated partial execution: the agent stopped before writing output")
            execution.duration_seconds = time.monotonic() - started
            return execution
        if execution.status in ("timed_out", "cancelled"):
            execution.duration_seconds = time.monotonic() - started
            return execution

        for index, entry in enumerate(self.script.get("toolCalls") or []):
            control.event("tool-call", index=index, **entry)
            execution.tool_calls.append(dict(entry))

        for relative in self.script.get("filesRead") or []:
            path = invocation.repository_dir / relative
            control.event("file-read", path=relative, exists=path.exists())
            execution.files_read.append(relative)

        for command in self.script.get("commands") or []:
            record = dict(command)
            control.event("command", **record)
            execution.commands.append(record)

        for test in self.script.get("tests") or []:
            record = dict(test)
            control.event("test-result", **record)
            execution.tests.append(record)

        for relative, content in (self.script.get("writeFiles") or {}).items():
            target = invocation.repository_dir / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            control.event("file-write", path=relative)
            execution.files_modified.append(relative)

        output = self.script.get("output")
        if output is not None:
            invocation.output_dir.mkdir(parents=True, exist_ok=True)
            target = invocation.output_dir / "agent-output.json"
            target.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            control.event("output-written", path=str(target.name))

        execution.messages = list(self.script.get("messages") or [])
        execution.token_usage = self.script.get("tokenUsage")
        execution.exit_code = int(self.script.get("exitCode", 0))
        execution.status = "completed"
        execution.duration_seconds = time.monotonic() - started
        control.event("adapter-complete", status=execution.status)
        return execution
