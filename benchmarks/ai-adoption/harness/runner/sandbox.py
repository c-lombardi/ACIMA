"""Sandbox execution boundary and resource limits.

Container execution is the intended isolation. When no container runtime is available the
controller may fall back to a local process sandbox, but only when configuration allows it, and the
run record then states plainly which guarantees were not enforced. The agent cannot change either.
"""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from .lifecycle import InvalidConfiguration
from .provenance import Limits

SANDBOX_BACKENDS = ("auto", "docker", "local")
DOCKER_IMAGE_DEFAULT = "python:3.12-slim"


@dataclass
class CommandResult:
    argv: list[str]
    returncode: int | None
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool = False
    cancelled: bool = False
    truncated: bool = False

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out and not self.cancelled


_DOCKER_STATUS: bool | None = None


def _docker_daemon_available() -> bool:
    """A docker CLI without a reachable daemon provides no isolation, so it is not 'available'."""
    global _DOCKER_STATUS
    if _DOCKER_STATUS is not None:
        return _DOCKER_STATUS
    executable = shutil.which("docker")
    if executable is None:
        _DOCKER_STATUS = False
        return False
    try:
        result = subprocess.run([executable, "info", "--format", "{{.ServerVersion}}"],
                                capture_output=True, text=True, timeout=10)
        _DOCKER_STATUS = result.returncode == 0 and bool(result.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        _DOCKER_STATUS = False
    return _DOCKER_STATUS


def _kill_tree(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)],
                       capture_output=True, text=True)
    else:
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            process.kill()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass


def run_command(argv: list[str], *, cwd: Path, env: dict[str, str], timeout: float,
                max_output_bytes: int = 64000, cancel_event=None) -> CommandResult:
    """Run one command with a wall-clock limit, cancellation and process-tree termination."""
    started = time.monotonic()
    creationflags = 0
    popen_kwargs: dict = {"start_new_session": os.name != "nt"}
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(
            subprocess, "CREATE_NO_WINDOW", 0)
        popen_kwargs.pop("start_new_session")
    try:
        process = subprocess.Popen(
            argv, cwd=str(cwd), env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, errors="replace", creationflags=creationflags, **popen_kwargs,
        )
    except FileNotFoundError as error:
        return CommandResult(argv, None, "", f"command not found: {argv[0]}",
                             time.monotonic() - started)

    timed_out = False
    cancelled = False
    deadline = started + timeout
    stdout = stderr = ""
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            timed_out = True
            _kill_tree(process)
            break
        if cancel_event is not None and cancel_event.is_set():
            cancelled = True
            _kill_tree(process)
            break
        try:
            stdout, stderr = process.communicate(timeout=min(0.2, remaining))
            break
        except subprocess.TimeoutExpired:
            continue
    # Drain and close the pipes on every path. A killed process must not leave its stdout/stderr
    # handles (or the reporting thread) open.
    try:
        final_out, final_err = process.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        _kill_tree(process)
        final_out, final_err = process.communicate()
    stdout = stdout or final_out
    stderr = stderr or final_err

    truncated = False
    encoded = len(stdout.encode("utf-8")) + len(stderr.encode("utf-8"))
    if max_output_bytes and encoded > max_output_bytes:
        truncated = True
        keep = max(1, max_output_bytes // 2)
        stdout = stdout[:keep]
        stderr = (stderr[:keep] + "\n[output truncated by the benchmark]")
    return CommandResult(
        argv=list(argv), returncode=process.returncode, stdout=stdout, stderr=stderr,
        duration_seconds=time.monotonic() - started, timed_out=timed_out,
        cancelled=cancelled, truncated=truncated,
    )


@dataclass
class Sandbox:
    backend: str
    enforced: list[str] = field(default_factory=list)
    not_enforced: list[str] = field(default_factory=list)
    network: str = "unknown"
    details: dict = field(default_factory=dict)

    def describe(self) -> dict:
        return {
            "backend": self.backend,
            "enforced": sorted(self.enforced),
            "notEnforced": sorted(self.not_enforced),
            "network": self.network,
            "readOnlyMount": "read-only repository mount" in self.enforced,
            "details": dict(self.details),
        }


class LocalSandbox(Sandbox):
    def __init__(self) -> None:
        super().__init__(
            backend="local-process",
            enforced=[
                "disposable working copy",
                "narrow environment allowlist",
                "wall-clock timeout",
                "process-tree termination",
                "output byte limit",
            ],
            not_enforced=[
                "network isolation",
                "read-only repository mount",
                "container memory and CPU limits",
                "filesystem quota",
                "process count limit",
                "docker socket isolation (there is no container)",
            ],
            network="not-enforced",
        )

    def run(self, argv: list[str], *, cwd: Path, env: dict[str, str], timeout: float,
            max_output_bytes: int = 64000, cancel_event=None) -> CommandResult:
        return run_command(argv, cwd=cwd, env=env, timeout=timeout,
                           max_output_bytes=max_output_bytes, cancel_event=cancel_event)


def docker_argv(*, image: str, working_dir: Path, source_dir: Path, output_dir: Path,
                mode: str, limits: Limits, network: str = "none", user: str | None = None,
                argv: list[str] | None = None) -> list[str]:
    """Build a rootless, network-isolated container invocation.

    The repository is mounted read-only unless the mode explicitly authorizes adoption. There is
    never a docker socket mount, a host home mount or an inherited environment.
    """
    working_mount = "rw" if mode == "authorized-adoption" else "ro"
    # Resolve the CLI once: on Windows the executable may be a shim that a bare name cannot find.
    executable = shutil.which("docker") or "docker"
    command = [
        executable, "run", "--rm", "--init",
        "--network", network,
        "--memory", f"{limits.max_container_memory_mb}m",
        "--cpus", str(limits.max_cpus),
        "--pids-limit", str(limits.max_processes),
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--read-only",
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=256m",
        "-v", f"{Path(source_dir).resolve()}:/benchmark/source:ro",
        "-v", f"{Path(working_dir).resolve()}:/benchmark/workspace:{working_mount}",
        "-v", f"{Path(output_dir).resolve()}:/benchmark/out:rw",
        "-w", "/benchmark/workspace",
    ]
    if user:
        command += ["--user", user]
    command.append(image)
    command += list(argv or [])
    for forbidden in ("/var/run/docker.sock", "/proc", "/sys"):
        if any(forbidden in entry for entry in command):
            raise InvalidConfiguration(f"sandbox mount of {forbidden} is forbidden")
    return command


class DockerSandbox(Sandbox):
    def __init__(self, *, image: str, user: str | None, limits: Limits,
                 source_dir: Path, working_dir: Path, output_dir: Path, mode: str,
                 network: str = "none") -> None:
        super().__init__(
            backend="docker",
            enforced=[
                "network isolation",
                "read-only repository mount",
                "container memory and CPU limits",
                "filesystem quota",
                "process count limit",
                "no docker socket",
                "no inherited environment",
                "dropped capabilities",
            ],
            network=network,
            details={"image": image, "executable": shutil.which("docker")},
        )
        self.image = image
        self.user = user
        self.limits = limits
        self.source_dir = source_dir
        self.working_dir = working_dir
        self.output_dir = output_dir
        self.mode = mode

    @staticmethod
    def available() -> bool:
        return _docker_daemon_available()

    def invoke(self, argv: list[str]) -> list[str]:
        return docker_argv(image=self.image, working_dir=self.working_dir,
                           source_dir=self.source_dir, output_dir=self.output_dir,
                           mode=self.mode, limits=self.limits, network=self.network,
                           user=self.user, argv=argv)

    def run(self, argv: list[str], *, cwd: Path, env: dict[str, str], timeout: float,
            max_output_bytes: int = 64000, cancel_event=None) -> CommandResult:
        return run_command(self.invoke(argv), cwd=cwd, env=allowlisted_environment(),
                           timeout=timeout, max_output_bytes=max_output_bytes,
                           cancel_event=cancel_event)


def select_sandbox(config: dict, limits: Limits, *, mode: str, source_dir: Path,
                   working_dir: Path, output_dir: Path) -> tuple[Sandbox | DockerSandbox, list[str]]:
    sandbox_config = config.get("sandbox") or {}
    backend = sandbox_config.get("backend", "auto")
    if backend not in SANDBOX_BACKENDS:
        raise InvalidConfiguration(f"unknown sandbox backend {backend!r}")
    limitations: list[str] = []
    if backend in ("auto", "docker"):
        if DockerSandbox.available():
            return DockerSandbox(
                image=sandbox_config.get("image", DOCKER_IMAGE_DEFAULT),
                user=sandbox_config.get("user"),
                limits=limits, source_dir=source_dir, working_dir=working_dir,
                output_dir=output_dir, mode=mode,
                network=sandbox_config.get("network", "none"),
            ), limitations
        if backend == "docker":
            raise InvalidConfiguration("sandbox backend 'docker' was requested but docker is not installed")
        limitations.append(
            "no container runtime was available; the local process sandbox did not enforce network "
            "isolation, a read-only mount, memory/CPU limits or a filesystem quota"
        )
    if not sandbox_config.get("allowLocalIsolation", False):
        raise InvalidConfiguration(
            "local process isolation is disabled and no container runtime is available"
        )
    return LocalSandbox(), limitations


def allowlisted_environment(extra: dict[str, str] | None = None) -> dict[str, str]:
    """A narrow environment. Provider credentials are not inherited implicitly."""
    allowed = ("PATH", "PATHEXT", "SystemRoot", "SystemDrive", "TEMP", "TMP", "HOME",
               "USERPROFILE", "LANG", "LC_ALL", "PYTHONIOENCODING", "PYTHONPATH")
    environment = {key: os.environ[key] for key in allowed if key in os.environ}
    environment.setdefault("PYTHONIOENCODING", "utf-8")
    for key, value in (extra or {}).items():
        environment[key] = value
    return environment
