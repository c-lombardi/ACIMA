"""The architecture gate. Runs the enforcer over the good tree and the violation gallery.

This is the Python expression of P8: the rules are not advice, they are a test.
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENFORCER = [sys.executable, "tools/acima_arch.py"]


def run(*args: str) -> tuple[int, dict]:
    result = subprocess.run(ENFORCER + list(args), cwd=ROOT, capture_output=True, text=True)
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:  # pragma: no cover - tool failure path
        raise AssertionError(f"enforcer produced no JSON: {result.stderr}") from None
    return result.returncode, payload


class ArchitectureTests(unittest.TestCase):
    def test_production_code_has_no_findings(self) -> None:
        code, payload = run("--root", ".", "--format", "json")
        self.assertEqual(payload["findings"], [], "the reference implementation must be clean")
        self.assertEqual(code, 0)

    def test_good_run_discovers_units(self) -> None:
        _code, payload = run("--root", ".", "--format", "json", "--level", "L3")
        self.assertEqual(payload["level"], "L3")
        self.assertEqual(payload["standard"], "1.0.0")

    def test_gallery_matches_documented_findings(self) -> None:
        _code, payload = run("--root", ".", "--config", "acima.gallery.config.json", "--format", "json")
        actual: dict[str, set[str]] = {}
        for finding in payload["findings"]:
            actual.setdefault(finding["rule"], set()).add(finding["path"])
        expected = json.loads((ROOT / "violations/expected.json").read_text())
        self.assertEqual({k: sorted(v) for k, v in actual.items()},
                         {k: sorted(v) for k, v in expected.items()})

    def test_every_finding_carries_the_required_fields(self) -> None:
        _code, payload = run("--root", ".", "--config", "acima.gallery.config.json", "--format", "json")
        self.assertGreater(len(payload["findings"]), 0, "a suite that finds nothing proves nothing")
        for finding in payload["findings"]:
            for key in ("rule", "severity", "message", "path", "line"):
                self.assertIn(key, finding)
            self.assertRegex(finding["rule"], r"^ACIMA-[A-Z]\d{3}$")
            self.assertIn(finding["severity"], ("error", "warning", "info"))

    def test_tool_failure_is_not_reported_as_architecture_debt(self) -> None:
        result = subprocess.run(
            ENFORCER + ["--root", ".", "--config", "does-not-exist.json", "--format", "json"],
            cwd=ROOT, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 2, "exit 2 distinguishes broken tooling from violations")
        self.assertIn("cannot read config", result.stderr)


if __name__ == "__main__":
    unittest.main()
