"""Tests for the architecture mode selector and its precedence.

`acima.config.json.mode` is the only selector. `base` (or absent) applies P1-P9;
`service-topology` applies P1-P9 plus P10-P13 and supersedes exactly P2.1 and P3.5.
A topology manifest without that mode, or that mode without the manifest, is a tool
failure (exit 2), never a clean run.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = ROOT / "skills/acima-adoption/scripts/preflight.py"


def config(mode: str | None = "base") -> dict:
    data = {
        "standard": "1.0.0",
        "language": "python",
        "level": "L1",
        "root": ".",
        "units": [{"id": "mod", "module": "mod", "role": "implementation",
                   "paths": ["src/mod"]}],
        "exclude": [],
    }
    if mode is not None:
        data["mode"] = mode
    return data


def build(root: Path, mode: str | None = "base", topology: bool = False) -> None:
    (root / "src" / "mod").mkdir(parents=True)
    (root / "src" / "mod" / "a.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "acima.config.json").write_text(json.dumps(config(mode)), encoding="utf-8")
    if topology:
        (root / "acima.topology.json").write_text(
            json.dumps({"standard": "1.0.0", "profile": "service-topology",
                        "services": []}), encoding="utf-8")


def preflight(root: Path) -> tuple[int, dict]:
    result = subprocess.run(
        [sys.executable, str(PREFLIGHT), "--project", str(root), "--format", "json"],
        cwd=ROOT, capture_output=True, text=True,
    )
    payload = json.loads(result.stdout) if result.stdout.strip() else {}
    return result.returncode, payload


def check(payload: dict, check_id: str) -> dict:
    return {item["id"]: item for item in payload.get("checks", [])}[check_id]


class ModeSelectorTests(unittest.TestCase):
    def test_absent_mode_defaults_to_base(self) -> None:
        with tempfile.TemporaryDirectory(prefix="acima-mode-base-") as temp:
            root = Path(temp)
            build(root, mode=None)
            code, payload = preflight(root)
            self.assertEqual(code, 0, payload)
            self.assertEqual(payload["project"]["architectureMode"], "base")
            self.assertEqual(check(payload, "TGT-006")["status"], "pass")

    def test_unknown_mode_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory(prefix="acima-mode-typo-") as temp:
            root = Path(temp)
            build(root, mode="service")
            code, payload = preflight(root)
            self.assertEqual(code, 1)
            self.assertEqual(check(payload, "TGT-006")["status"], "fail")
            self.assertIn("unknown architecture mode", check(payload, "TGT-006")["detail"])

    def test_service_mode_without_manifest_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory(prefix="acima-mode-no-manifest-") as temp:
            root = Path(temp)
            build(root, mode="service-topology")
            code, payload = preflight(root)
            self.assertEqual(code, 1)
            self.assertEqual(check(payload, "TGT-006")["status"], "fail")
            self.assertIn("acima.topology.json is missing", check(payload, "TGT-006")["detail"])

    def test_manifest_without_service_mode_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory(prefix="acima-mode-base-manifest-") as temp:
            root = Path(temp)
            build(root, mode="base", topology=True)
            code, payload = preflight(root)
            self.assertEqual(code, 1)
            self.assertIn("mode is base/absent", check(payload, "TGT-006")["detail"])

    def test_service_mode_is_not_supported_by_this_skill(self) -> None:
        with tempfile.TemporaryDirectory(prefix="acima-mode-service-") as temp:
            root = Path(temp)
            build(root, mode="service-topology", topology=True)
            code, payload = preflight(root)
            self.assertEqual(code, 1)
            detail = check(payload, "TGT-006")["detail"]
            self.assertIn("NOT SUPPORTED", detail)
            self.assertEqual(payload["project"]["architectureMode"], "service-topology")
            self.assertEqual(payload["project"]["profile"], "service-topology")

    def test_docs_state_the_selector_and_the_two_supersessions(self) -> None:
        preface = (ROOT / "docs/standard/00-preface.md").read_text(encoding="utf-8")
        topology = (ROOT / "docs/standard/11-service-topology.md").read_text(encoding="utf-8")
        governance = (ROOT / "docs/standard/07-executable-governance.md").read_text(encoding="utf-8")
        self.assertIn("it is the **only** selector", preface)
        self.assertIn("P2.1", preface)
        self.assertIn("P3.5", preface)
        self.assertIn("does **not** replace P1–P9 wholesale", preface)
        self.assertIn("Precedence is deliberately narrow", topology)
        self.assertIn('"mode": "base"', governance)


if __name__ == "__main__":
    unittest.main(verbosity=2)
