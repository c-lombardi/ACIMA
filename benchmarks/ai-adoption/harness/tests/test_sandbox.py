"""Sandbox command execution, limits and container arguments."""
from __future__ import annotations

import shutil
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from support import HARNESS_ROOT

from runner.lifecycle import InvalidConfiguration
from runner.provenance import load_config
from runner.sandbox import (
    DockerSandbox,
    LocalSandbox,
    allowlisted_environment,
    docker_argv,
    run_command,
    select_sandbox,
)


class CommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_successful_command(self) -> None:
        result = run_command([sys.executable, "-c", "print('ok')"], cwd=self.directory,
                             env=allowlisted_environment(), timeout=10)
        self.assertTrue(result.ok)
        self.assertEqual(result.returncode, 0)
        self.assertIn("ok", result.stdout)

    def test_missing_command_is_reported(self) -> None:
        result = run_command(["definitely-not-a-command-xyz"], cwd=self.directory,
                             env=allowlisted_environment(), timeout=10)
        self.assertFalse(result.ok)
        self.assertIn("not found", result.stderr)

    def test_timeout_terminates_the_process(self) -> None:
        started = time.monotonic()
        result = run_command([sys.executable, "-c", "import time; time.sleep(30)"],
                             cwd=self.directory, env=allowlisted_environment(), timeout=0.4)
        self.assertTrue(result.timed_out)
        self.assertFalse(result.ok)
        self.assertLess(time.monotonic() - started, 15)

    def test_cancellation_terminates_the_process(self) -> None:
        cancel = threading.Event()
        timer = threading.Timer(0.3, cancel.set)
        timer.start()
        try:
            result = run_command([sys.executable, "-c", "import time; time.sleep(30)"],
                                 cwd=self.directory, env=allowlisted_environment(),
                                 timeout=30, cancel_event=cancel)
        finally:
            timer.cancel()
        self.assertTrue(result.cancelled)

    def test_output_is_truncated_at_the_limit(self) -> None:
        result = run_command([sys.executable, "-c", "print('x' * 5000)"], cwd=self.directory,
                             env=allowlisted_environment(), timeout=10, max_output_bytes=500)
        self.assertTrue(result.truncated)
        self.assertIn("truncated", result.stderr)


class SandboxSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        for name in ("source", "working", "out"):
            (self.root / name).mkdir()
        self.config, self.limits = load_config(HARNESS_ROOT)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_docker_argv_is_isolated(self) -> None:
        argv = docker_argv(image="python:3.12-slim", working_dir=self.root / "working",
                           source_dir=self.root / "source", output_dir=self.root / "out",
                           mode="read-only", limits=self.limits, user="65534:65534",
                           argv=["python", "-V"])
        joined = " ".join(argv)
        self.assertIn("--network none", joined)
        self.assertIn("--cap-drop ALL", joined)
        self.assertIn("no-new-privileges", joined)
        self.assertIn(":/benchmark/workspace:ro", joined)
        self.assertIn(":/benchmark/source:ro", joined)
        self.assertIn(":/benchmark/out:rw", joined)
        self.assertNotIn("docker.sock", joined)
        self.assertIn(f"--memory {self.limits.max_container_memory_mb}m", joined)
        self.assertIn(f"--pids-limit {self.limits.max_processes}", joined)
        self.assertEqual(argv[-2:], ["python", "-V"])

    def test_docker_argv_is_writable_only_when_authorized(self) -> None:
        argv = docker_argv(image="image", working_dir=self.root / "working",
                           source_dir=self.root / "source", output_dir=self.root / "out",
                           mode="authorized-adoption", limits=self.limits)
        self.assertIn(":/benchmark/workspace:rw", " ".join(argv))

    def test_local_fallback_is_recorded_as_a_limitation(self) -> None:
        sandbox, limitations = select_sandbox(
            self.config, self.limits, mode="read-only", source_dir=self.root / "source",
            working_dir=self.root / "working", output_dir=self.root / "out",
        )
        if DockerSandbox.available():
            self.assertEqual(sandbox.backend, "docker")
            self.assertEqual(limitations, [])
        else:
            self.assertEqual(sandbox.backend, "local-process")
            self.assertTrue(limitations)
            described = sandbox.describe()
            self.assertIn("network isolation", described["notEnforced"])

    def test_docker_is_required_when_requested(self) -> None:
        if DockerSandbox.available():
            self.skipTest("docker is installed on this host")
        config = dict(self.config)
        config["sandbox"] = {**self.config["sandbox"], "backend": "docker"}
        with self.assertRaises(InvalidConfiguration):
            select_sandbox(config, self.limits, mode="read-only",
                           source_dir=self.root / "source", working_dir=self.root / "working",
                           output_dir=self.root / "out")

    def test_local_isolation_can_be_disabled(self) -> None:
        if DockerSandbox.available():
            self.skipTest("docker is installed on this host")
        config = dict(self.config)
        config["sandbox"] = {**self.config["sandbox"], "backend": "auto",
                             "allowLocalIsolation": False}
        with self.assertRaises(InvalidConfiguration):
            select_sandbox(config, self.limits, mode="read-only",
                           source_dir=self.root / "source", working_dir=self.root / "working",
                           output_dir=self.root / "out")


if __name__ == "__main__":
    unittest.main()
