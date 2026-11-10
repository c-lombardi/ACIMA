"""Freebuff adapter boundary.

Capabilities are probed from the installed CLI, not assumed. This adapter refuses unattended
execution unless the CLI exposes a documented non-interactive invocation; an interactive session
is not a headless API, and GUI automation is not a substitute.

Verified on 2026-11-10 with Freebuff CLI 0.2.36: the CLI advertises ``login`` and ``doctor``
commands plus ``--continue``, ``--cwd`` and ``--trust-agents``. There is no documented prompt mode,
JSON event stream or exit-status contract for an unattended task, so ``headless`` is ``false`` and
``execute`` raises ``UnsupportedHeadlessExecution``.
"""
from __future__ import annotations

import hashlib
import shutil
import subprocess

from .base import (
    AdapterCapabilities,
    AgentExecution,
    AgentInvocation,
    Control,
    UnsupportedHeadlessExecution,
)

PROBE_TIMEOUT_SECONDS = 20


class FreebuffAdapter:
    name = "freebuff"

    def __init__(self, command: str = "freebuff") -> None:
        self.command = command

    def _probe(self) -> tuple[bool, str, str, str | None]:
        executable = shutil.which(self.command)
        if executable is None:
            return False, "", "", None
        version = None
        try:
            version_result = subprocess.run(
                [executable, "--version"], capture_output=True, text=True,
                timeout=PROBE_TIMEOUT_SECONDS,
            )
            version = (version_result.stdout or version_result.stderr).strip().splitlines()[0:1]
            version = version[0] if version else None
        except (OSError, subprocess.SubprocessError):
            version = None
        try:
            help_result = subprocess.run(
                [executable, "--help"], capture_output=True, text=True,
                timeout=PROBE_TIMEOUT_SECONDS,
            )
            help_text = (help_result.stdout or "") + (help_result.stderr or "")
        except (OSError, subprocess.SubprocessError) as error:
            return True, executable, "", version if isinstance(version, str) else None
        return True, executable, help_text, version if isinstance(version, str) else None

    def capabilities(self) -> AdapterCapabilities:
        installed, executable, help_text, version = self._probe()
        digest = hashlib.sha256(help_text.encode("utf-8")).hexdigest() if help_text else None
        observed = [
            token for token in ("--continue", "--cwd", "--trust-agents", "login", "doctor")
            if token in help_text
        ]
        notes = [
            "No documented unattended invocation: the CLI exposes interactive startup, login and doctor.",
            "Authentication is interactive browser/device login; an unattended token path is not documented.",
            "Model selection is not exposed as a documented CLI flag.",
            "Skill and repository context cannot be supplied programmatically through a documented interface.",
            "Event, tool-call and token-usage capture is unavailable without a structured output mode.",
        ]
        return AdapterCapabilities(
            provider="freebuff",
            headless=False,
            models=(),
            notes=tuple(notes),
            evidence={
                "installed": installed,
                "executable": executable or None,
                "version": version,
                "helpSha256": digest,
                "observedTokens": observed,
                "probedOn": "2026-11-10",
            },
        )

    def execute(self, invocation: AgentInvocation, control: Control) -> AgentExecution:
        capabilities = self.capabilities()
        if not capabilities.headless:
            control.event("adapter-refused", provider=self.name, reason="unsupported-headless-execution")
            raise UnsupportedHeadlessExecution(
                "Freebuff CLI %s has no supported unattended invocation. The benchmark records the "
                "adapter boundary and does not simulate an interactive session."
                % (capabilities.evidence.get("version") or "unknown")
            )
        raise UnsupportedHeadlessExecution(
            "Freebuff adapter is registered as a capability boundary only in this milestone."
        )
