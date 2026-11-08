"""Tests for the zero-findings proof: inject known violations into disposable fixtures.

The prover exists because several real repositories report zero findings. Without a
controlled violation, that result could mean "clean" or "the enforcer saw nothing".
These tests pin both proofs: a target-copy L001 injection and a synthetic two-unit
D001 fixture. They also pin fail-closed behavior and withholding.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/acima-adoption/scripts/inject_violation.py"
MANIFEST = ROOT / "skills/acima-adoption/manifest.json"


def _go_ready() -> tuple[bool, str]:
    executable = shutil.which("go")
    if executable is None:
        return False, "go toolchain is not installed"
    try:
        result = subprocess.run([executable, "version"], capture_output=True,
                                text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as error:
        return False, f"go toolchain cannot run: {error}"
    if result.returncode != 0:
        return False, "go version failed"
    match = re.search(r"go(\d+)\.(\d+)", result.stdout)
    if match is None or (int(match.group(1)), int(match.group(2))) < (1, 21):
        return False, "Go 1.21+ is required for the D001 fixture"
    return True, ""


def _dotnet_ready() -> tuple[bool, str]:
    executable = shutil.which("dotnet")
    if executable is None:
        return False, "dotnet toolchain is not installed"
    try:
        result = subprocess.run([executable, "--list-sdks"], capture_output=True,
                                text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as error:
        return False, f"dotnet toolchain cannot run: {error}"
    if result.returncode != 0:
        return False, "dotnet --list-sdks failed"
    majors = [int(major) for major in re.findall(r"(?m)^(\d+)\.\d+\.\d+", result.stdout)]
    if not any(major >= 8 for major in majors):
        return False, ".NET 8+ SDK is not installed"
    return True, ""


GO_READY, GO_REASON = _go_ready()
DOTNET_READY, DOTNET_REASON = _dotnet_ready()
REQUIRE_TOOLCHAINS = os.environ.get("ACIMA_REQUIRE_TOOLCHAINS", "").lower() in {
    "1", "true", "yes"
}


def write_config(directory: Path, language: str, units: list[dict]) -> None:
    (directory / "acima.config.json").write_text(json.dumps({
        "standard": "1.0.0",
        "language": language,
        "level": "L1",
        "root": ".",
        "units": units,
        "exclude": ["node_modules", "tests"],
    }), encoding="utf-8")


def prove(directory: Path, *extra: str,
          env: dict | None = None) -> tuple[int, dict, str]:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--project", str(directory),
         "--format", "json", *extra],
        cwd=ROOT, capture_output=True, text=True, env=env)
    payload = json.loads(result.stdout) if result.stdout.strip() else {}
    return result.returncode, payload, result.stderr


class InjectionProofTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = Path(tempfile.mkdtemp(prefix="acima-injection-test-"))

    def tearDown(self) -> None:
        shutil.rmtree(self.directory, ignore_errors=True)

    def _require_toolchain(self, ready: bool, reason: str) -> None:
        if ready:
            return
        if REQUIRE_TOOLCHAINS:
            self.fail(f"{reason} (ACIMA_REQUIRE_TOOLCHAINS requires both D001 fixtures to run)")
        self.skipTest(reason)

    def test_python_proves_l001_and_d001_and_target_is_untouched(self) -> None:
        (self.directory / "pkg").mkdir()
        (self.directory / "pkg/mod.py").write_text("VALUE = 1\n", encoding="utf-8")
        write_config(self.directory, "python",
                     [{"id": "pkg", "module": "pkg", "role": "implementation",
                       "paths": ["pkg"]}])
        code, payload, stderr = prove(self.directory, "--reveal")
        self.assertEqual(code, 0, stderr or payload)
        self.assertTrue(payload["proven"])
        self.assertEqual(payload["rules"], ["ACIMA-L001", "ACIMA-D001"])

        l001 = payload["proofs"]["ACIMA-L001"]
        self.assertTrue(l001["proven"])
        self.assertTrue(l001["detected"])
        self.assertEqual(l001["injection"]["path"], "pkg/_acima_injected_violation.py")
        self.assertTrue(l001["originalUntouched"])
        self.assertEqual(l001["finding"]["path"], "pkg/_acima_injected_violation.py")

        d001 = payload["proofs"]["ACIMA-D001"]
        self.assertTrue(d001["proven"])
        self.assertTrue(d001["detected"])
        self.assertEqual(d001["injection"]["expectedPath"], "alpha/a.py")
        self.assertEqual(d001["finding"]["path"], "alpha/a.py")
        self.assertTrue(d001["targetUntouched"])
        self.assertFalse((self.directory / "pkg/_acima_injected_violation.py").exists())

    def test_typescript_proves_l001_and_d001(self) -> None:
        (self.directory / "src").mkdir()
        (self.directory / "src/mod.ts").write_text("export const value = 1;\n",
                                                   encoding="utf-8")
        write_config(self.directory, "typescript",
                     [{"id": "core", "module": "core", "role": "implementation",
                       "paths": ["src"]}])
        code, payload, stderr = prove(self.directory, "--reveal")
        self.assertEqual(code, 0, stderr or payload)
        self.assertTrue(payload["proofs"]["ACIMA-L001"]["proven"])
        self.assertEqual(payload["proofs"]["ACIMA-L001"]["injection"]["path"],
                         "src/_acima_injected_violation.ts")
        self.assertTrue(payload["proofs"]["ACIMA-D001"]["proven"])
        self.assertEqual(payload["proofs"]["ACIMA-D001"]["injection"]["expectedPath"],
                         "src/alpha/a.ts")
        self.assertFalse((self.directory / "src/_acima_injected_violation.ts").exists())

    def test_go_d001_fixture_is_detected(self) -> None:
        self._require_toolchain(GO_READY, GO_REASON)
        write_config(self.directory, "go",
                     [{"id": "host", "role": "host", "paths": ["."]}])
        code, payload, stderr = prove(self.directory, "--rule", "D001", "--reveal")
        self.assertEqual(code, 0, stderr or payload)
        self.assertEqual(payload["rules"], ["ACIMA-D001"])
        d001 = payload["proofs"]["ACIMA-D001"]
        self.assertTrue(d001["proven"])
        self.assertEqual(d001["injection"]["expectedPath"], "alpha/alpha.go")
        self.assertEqual(d001["finding"]["path"], "alpha/alpha.go")
        self.assertTrue(d001["targetUntouched"])

    def test_dotnet_d001_fixture_is_detected(self) -> None:
        self._require_toolchain(DOTNET_READY, DOTNET_REASON)
        write_config(self.directory, "dotnet",
                     [{"id": "host", "role": "host", "paths": ["."]}])
        dotnet = shutil.which("dotnet")
        env = os.environ.copy()
        env.setdefault("DOTNET_ROOT", str(Path(dotnet).resolve().parent))
        env.setdefault("DOTNET_CLI_TELEMETRY_OPTOUT", "1")
        code, payload, stderr = prove(self.directory, "--rule", "D001", "--reveal",
                                      env=env)
        self.assertEqual(code, 0, stderr or payload)
        self.assertEqual(payload["rules"], ["ACIMA-D001"])
        d001 = payload["proofs"]["ACIMA-D001"]
        self.assertTrue(d001["proven"])
        self.assertEqual(d001["injection"]["expectedPath"], "alpha/Alpha.csproj")
        self.assertEqual(d001["finding"]["path"], "alpha/Alpha.csproj")
        self.assertTrue(d001["targetUntouched"])

    def test_injection_details_are_withheld_by_default(self) -> None:
        (self.directory / "pkg").mkdir()
        (self.directory / "pkg/mod.py").write_text("VALUE = 1\n", encoding="utf-8")
        write_config(self.directory, "python",
                     [{"id": "pkg", "module": "pkg", "role": "implementation",
                       "paths": ["pkg"]}])
        code, payload, stderr = prove(self.directory)
        self.assertEqual(code, 0, stderr or payload)
        self.assertEqual(payload["proofs"]["ACIMA-L001"]["injection"],
                         {"withheld": True})
        self.assertEqual(payload["proofs"]["ACIMA-D001"]["injection"],
                         {"withheld": True})
        serialized = json.dumps(payload)
        self.assertNotIn("_acima_injected_violation", serialized)
        self.assertNotIn("alpha/a.py", serialized)
        self.assertNotIn("fixture/beta/impl", serialized)

    def test_d001_only_does_not_need_an_implementation_unit(self) -> None:
        (self.directory / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
        write_config(self.directory, "python",
                     [{"id": "host", "role": "host", "paths": ["."]}])
        code, payload, stderr = prove(self.directory, "--rule", "D001")
        self.assertEqual(code, 0, stderr or payload)
        self.assertEqual(payload["rules"], ["ACIMA-D001"])
        self.assertNotIn("ACIMA-L001", payload["proofs"])
        self.assertTrue(payload["proofs"]["ACIMA-D001"]["proven"])

    def test_no_implementation_unit_fails_closed_for_l001(self) -> None:
        (self.directory / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
        write_config(self.directory, "python",
                     [{"id": "host", "role": "host", "paths": ["."]}])
        code, payload, _stderr = prove(self.directory)
        self.assertEqual(code, 1)
        self.assertFalse(payload["proven"])
        self.assertFalse(payload["proofs"]["ACIMA-L001"]["proven"])
        self.assertIn("no implementation unit",
                      payload["proofs"]["ACIMA-L001"]["reason"])
        self.assertTrue(payload["proofs"]["ACIMA-D001"]["proven"])

    def test_unsupported_language_fails_closed(self) -> None:
        (self.directory / "Main.java").write_text("class Main {}\n", encoding="utf-8")
        write_config(self.directory, "java",
                     [{"id": "main", "module": "main", "role": "implementation",
                       "paths": ["."]}])
        code, payload, _stderr = prove(self.directory)
        self.assertEqual(code, 1)
        self.assertFalse(payload["proven"])
        self.assertIn("no injection recipe",
                      payload["proofs"]["ACIMA-L001"]["reason"])
        self.assertIn("no disposable D001 fixture",
                      payload["proofs"]["ACIMA-D001"]["reason"])

    def test_d001_fails_closed_when_the_enforcer_sees_nothing(self) -> None:
        (self.directory / "pkg").mkdir()
        (self.directory / "pkg/mod.py").write_text("VALUE = 1\n", encoding="utf-8")
        write_config(self.directory, "python",
                     [{"id": "pkg", "module": "pkg", "role": "implementation",
                       "paths": ["pkg"]}])
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        manifest["enforcers"]["python"]["run"] = [
            sys.executable, "-c",
            "import json; print(json.dumps({'findings': [], 'sourceFiles': 0}))",
        ]
        manifest_path = self.directory / "manifest.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        code, payload, _stderr = prove(self.directory, "--rule", "D001",
                                       "--manifest", str(manifest_path))
        self.assertEqual(code, 1)
        self.assertFalse(payload["proven"])
        self.assertFalse(payload["proofs"]["ACIMA-D001"]["proven"])
        self.assertIn("not detected",
                      payload["proofs"]["ACIMA-D001"]["reason"])


if __name__ == "__main__":
    unittest.main()
