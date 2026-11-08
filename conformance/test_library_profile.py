"""Regression tests for the explicit library/framework profile.

These tests exist because the previous real-world benchmark showed two opposite
failures: Hono's adapter-to-core imports were invisible (false negative), and
Spectre/FluentValidation public API types were reported as leaks (false positive).
The profile must make declared surfaces reviewable without weakening the rules.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENFORCER = ROOT / "examples/typescript/tools/acima-arch.mjs"
FIXTURE = ROOT / "conformance/fixtures/library-profile"

SPEC = importlib.util.spec_from_file_location(
    "acima_preflight_profile", ROOT / "skills/acima-adoption/scripts/preflight.py")
preflight = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = preflight
SPEC.loader.exec_module(preflight)


def run_enforcer(directory: Path) -> tuple[int, dict, str]:
    result = subprocess.run(
        ["node", str(ENFORCER), "--root", str(directory),
         "--config", "acima.config.json", "--format", "json"],
        cwd=ROOT, capture_output=True, text=True)
    payload = json.loads(result.stdout) if result.stdout.strip() else {}
    return result.returncode, payload, result.stderr


def findings_set(payload: dict) -> set[tuple[str, str]]:
    return {(finding["rule"], finding["path"]) for finding in payload["findings"]}


class LibraryProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = Path(tempfile.mkdtemp(prefix="acima-library-profile-"))
        shutil.copytree(FIXTURE, self.directory, dirs_exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.directory, ignore_errors=True)

    def edit_config(self, change) -> None:
        path = self.directory / "acima.config.json"
        config = json.loads(path.read_text(encoding="utf-8"))
        change(config)
        path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    def test_declared_adapter_and_public_api_are_classified(self) -> None:
        code, payload, stderr = run_enforcer(self.directory)
        self.assertEqual(code, 1, stderr)
        classified = {(item["rule"], item["path"]) for item in payload["classified"]}
        self.assertIn(("ACIMA-D001", "adapters/driver/driver.ts"), classified)
        self.assertIn(("ACIMA-L001", "adapters/driver/driver.ts"), classified)
        self.assertIn(("ACIMA-L003", "src/index.ts"), classified)
        for item in payload["classified"]:
            self.assertTrue(item["owner"])
            self.assertTrue(item["reason"])
            self.assertIn(item["classification"],
                          {"intentional-adapter", "declared-public-api"})
        self.assertEqual(payload["profile"]["kind"], "library")
        self.assertEqual(payload["profile"]["publicApi"],
                         [{"unit": "core", "paths": ["src/index.ts"]}])

    def test_undeclared_edge_and_private_leak_still_fire(self) -> None:
        code, payload, _stderr = run_enforcer(self.directory)
        self.assertEqual(code, 1)
        actual = findings_set(payload)
        self.assertIn(("ACIMA-D001", "adapters/rogue/rogue.ts"), actual)
        self.assertIn(("ACIMA-L003", "src/internal/secret.ts"), actual)
        self.assertNotIn(("ACIMA-D001", "adapters/driver/driver.ts"), actual)
        self.assertNotIn(("ACIMA-L001", "adapters/driver/driver.ts"), actual)
        self.assertNotIn(("ACIMA-L003", "src/index.ts"), actual)
        self.assertEqual(len(actual), 2)

    def test_profile_without_owner_is_rejected(self) -> None:
        self.edit_config(lambda config: config["profile"].pop("owner"))
        _code, payload, _stderr = run_enforcer(self.directory)
        evidence = {finding["evidence"] for finding in payload["findings"]
                    if finding["rule"] == "ACIMA-G001"}
        self.assertIn("profile.owner", evidence)

    def test_adapter_without_paths_is_rejected(self) -> None:
        self.edit_config(lambda config: config["profile"]["intentionalAdapters"][0].pop("paths"))
        _code, payload, _stderr = run_enforcer(self.directory)
        evidence = {finding["evidence"] for finding in payload["findings"]
                    if finding["rule"] == "ACIMA-G001"}
        self.assertIn("profile.intentionalAdapters", evidence)

    def test_bare_public_api_unit_is_rejected(self) -> None:
        self.edit_config(lambda config: config["profile"].__setitem__("publicApi", ["core"]))
        _code, payload, _stderr = run_enforcer(self.directory)
        evidence = {finding["evidence"] for finding in payload["findings"]
                    if finding["rule"] == "ACIMA-G001"}
        self.assertIn("profile.publicApi", evidence)

    def test_library_profile_needs_a_publishable_manifest(self) -> None:
        manifest = json.loads((self.directory / "package.json").read_text(encoding="utf-8"))
        manifest["private"] = True
        (self.directory / "package.json").write_text(json.dumps(manifest), encoding="utf-8")
        _code, payload, _stderr = run_enforcer(self.directory)
        evidence = {finding["evidence"] for finding in payload["findings"]
                    if finding["rule"] == "ACIMA-G001"}
        self.assertIn("profile.kind", evidence)

    def test_unknown_adapter_target_is_rejected(self) -> None:
        self.edit_config(
            lambda config: config["profile"]["intentionalAdapters"][0].__setitem__("to", "ghost"))
        _code, payload, _stderr = run_enforcer(self.directory)
        evidence = {finding["evidence"] for finding in payload["findings"]
                    if finding["rule"] == "ACIMA-G001"}
        self.assertIn("profile.intentionalAdapters", evidence)


class ZeroSourceTests(unittest.TestCase):
    def test_zero_source_run_is_never_conformance(self) -> None:
        directory = Path(tempfile.mkdtemp(prefix="acima-zero-source-"))
        try:
            (directory / "acima.config.json").write_text(json.dumps({
                "standard": "1.0.0", "language": "typescript", "level": "L1", "root": ".",
                "units": [{"id": "core", "module": "core", "role": "implementation",
                           "paths": ["src"]}],
                "exclude": ["node_modules"],
            }), encoding="utf-8")
            code, payload, _stderr = run_enforcer(directory)
            self.assertEqual(code, 0)
            self.assertEqual(payload["sourceFiles"], 0)
            self.assertEqual(payload["findings"], [])
            errors = preflight.validate_assessment(payload, code, {})
            self.assertTrue(any("source files" in error for error in errors))
        finally:
            shutil.rmtree(directory, ignore_errors=True)


class LargeOutputTests(unittest.TestCase):
    """A 65,536-byte pipe must not be able to truncate an assessment silently."""

    def test_output_beyond_64k_is_complete_and_valid(self) -> None:
        directory = Path(tempfile.mkdtemp(prefix="acima-large-output-"))
        try:
            contracts = directory / "src/contracts"
            contracts.mkdir(parents=True)
            for index in range(500):
                (contracts / f"contract_{index:03d}.ts").write_text(
                    "import express from 'express';\n"
                    f"export interface Contract{index:03d} {{ readonly id: string }}\n",
                    encoding="utf-8")
            (directory / "acima.config.json").write_text(json.dumps({
                "standard": "1.0.0", "language": "typescript", "level": "L1", "root": ".",
                "units": [{"id": "catalog.contracts", "module": "catalog",
                           "role": "contracts", "paths": ["src/contracts"]}],
                "exclude": ["node_modules"],
            }), encoding="utf-8")
            code, payload, stderr = run_enforcer(directory)
            self.assertEqual(code, 1, stderr)
            self.assertEqual(payload["sourceFiles"], 500)
            self.assertGreaterEqual(len(payload["findings"]), 500)
            self.assertGreaterEqual(len(json.dumps(payload)), 65536)
            paths = {finding["path"] for finding in payload["findings"]}
            self.assertEqual(len(paths), 500)
        finally:
            shutil.rmtree(directory, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
