"""Toolchain resolution is an environment lookup, never a machine-specific path list."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "conformance"))
import adoption_workflow as workflow  # noqa: E402
import executables  # noqa: E402


def load_script(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class ExecutableLookupTests(unittest.TestCase):
    def test_path_lookup_is_preferred(self) -> None:
        with mock.patch.object(executables.shutil, "which", return_value="/tools/dotnet"):
            self.assertEqual(executables.resolve_executable("dotnet"), "/tools/dotnet")

    def test_tool_root_is_the_only_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("dotnet", "dotnet.exe"):
                (root / name).write_text("", encoding="utf-8")
            with mock.patch.object(executables.shutil, "which", return_value=None), \
                    mock.patch.dict(os.environ, {"DOTNET_ROOT": str(root)}):
                resolved = executables.resolve_executable("dotnet")
            self.assertIn(Path(resolved or "").name, {"dotnet", "dotnet.exe"})

    def test_no_unconfigured_installation_directory_is_consulted(self) -> None:
        with mock.patch.object(executables.shutil, "which", return_value=None), \
                mock.patch.dict(os.environ, {"DOTNET_ROOT": ""}):
            self.assertIsNone(executables.resolve_executable("dotnet"))

    def test_workflow_stops_before_copying_dotnet_enforcer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with mock.patch.object(workflow, "_dotnet_executable", return_value=None):
                self.assertIsNone(workflow._enforcer(root, "dotnet"))
                copied = workflow._copy_enforcer(root, "dotnet")
                positive = workflow._positive_fixture("dotnet")
            self.assertEqual(copied["status"], "blocked")
            self.assertIn("PATH", copied["reason"])
            self.assertIn("DOTNET_ROOT", copied["reason"])
            self.assertFalse((root / "tools/Acima.ArchTests").exists())
            self.assertEqual(positive["status"], "blocked")

    def test_enforcement_stops_before_writing_waivers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state: dict = {"artifacts": {}}
            with mock.patch.object(workflow, "_dotnet_executable", return_value=None):
                result = workflow._write_enforcement(root, state, {"language": "dotnet"})
            self.assertEqual(result["status"], "blocked")
            self.assertFalse((root / ".acima/waivers.json").exists())
            self.assertFalse((root / "docs/acima/enforcement.json").exists())

    def test_verify_reports_a_blocked_dotnet_scan(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state: dict = {"artifacts": {}}
            with mock.patch.object(workflow, "_dotnet_executable", return_value=None):
                result = workflow._verify(root, state, {"language": "dotnet"})
            self.assertEqual(result["status"], "incomplete")
            self.assertEqual(result["positive"]["status"], "blocked")
            self.assertEqual(result["targetScan"]["status"], "blocked")
            self.assertEqual(result["negative"]["status"], "blocked")
            self.assertTrue(result["limitations"])


class ScriptToolchainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.preflight = load_script("acima_preflight_toolchain", "skills/acima-adoption/scripts/preflight.py")
        cls.inject = load_script("acima_inject_toolchain", "skills/acima-adoption/scripts/inject_violation.py")

    def test_preflight_uses_the_resolved_dotnet_path(self) -> None:
        manifest = {"enforcers": {"dotnet": {"run": ["dotnet", "run"], "buildProject": "x"}}}
        with mock.patch.object(self.preflight, "resolve_executable", return_value="/custom/dotnet"):
            command, _cwd = self.preflight.enforcer_invocation(manifest, "dotnet", ROOT)
        self.assertEqual(command[0], "/custom/dotnet")

    def test_preflight_build_uses_the_resolved_dotnet_path(self) -> None:
        manifest = {"enforcers": {"dotnet": {"buildProject": "examples/dotnet/tools/Acima.ArchTests"}}}
        with mock.patch.object(self.preflight, "resolve_executable", return_value="/custom/dotnet"), \
                mock.patch.object(self.preflight, "run") as run:
            self.preflight.prepare_dotnet(manifest)
        self.assertEqual(run.call_args.args[0][0], "/custom/dotnet")

    def test_inject_violation_stops_when_dotnet_is_missing(self) -> None:
        manifest = {"enforcers": {"dotnet": {"buildProject": "examples/dotnet/tools/Acima.ArchTests"}}}
        with mock.patch.object(self.inject, "resolve_executable", return_value=None):
            message = self.inject.prepare(manifest, "dotnet")
        self.assertIn("DOTNET_ROOT", message)

    def test_inject_violation_uses_the_resolved_dotnet_path(self) -> None:
        manifest = {"enforcers": {"dotnet": {"buildProject": "examples/dotnet/tools/Acima.ArchTests"}}}
        with mock.patch.object(self.inject, "resolve_executable", return_value="/custom/dotnet"), \
                mock.patch.object(self.inject, "run", return_value=(0, "", "")) as run:
            message = self.inject.prepare(manifest, "dotnet")
        self.assertEqual(message, "")
        self.assertEqual(run.call_args.args[0][0], "/custom/dotnet")


if __name__ == "__main__":
    unittest.main()
