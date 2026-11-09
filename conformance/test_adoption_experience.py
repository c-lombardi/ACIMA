"""Scenario tests for the guided adoption experience.

These exercise the workflow's observable behaviour: read-only defaults, evidence-based status,
optional artifacts, gate configuration versus observation, and claim honesty.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("acima_experience", ROOT / "tools/acima.py")
acima = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(acima)

CATALOG = json.loads((ROOT / "tools/acima-spec/rules.json").read_text(encoding="utf-8"))


def snapshot(root: Path) -> dict:
    return {path.relative_to(root).as_posix(): (path.stat().st_mtime_ns, path.read_bytes())
            for path in root.rglob("*") if path.is_file()}


def write_json(root: Path, relative: str, payload: dict) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def config(root: Path, level: str = "L2", units: int = 1) -> None:
    write_json(root, "acima.config.json", {
        "language": "python", "level": level, "mode": "base",
        "units": [{"id": f"u{index}", "role": "implementation", "paths": [f"src/u{index}"]}
                  for index in range(units)],
    })


def run_payload(findings: list[dict] | None = None, sources: int = 4,
                level: str = "L2") -> dict:
    execution = {}
    for rule in CATALOG["rules"]:
        if rule.get("automation") == "manual":
            execution[rule["id"]] = {"executed": False, "reason": "manual rule"}
        else:
            execution[rule["id"]] = {"executed": True}
    return {"standard": CATALOG["version"], "level": level, "sourceFiles": sources,
            "execution": execution, "findings": findings or []}


def baseline(root: Path, name: str = "baseline-2026-01-01.json", **kwargs) -> None:
    write_json(root, f"docs/acima/{name}", run_payload(**kwargs))


def step(report: dict, name: str) -> dict:
    return {entry["name"]: entry for entry in report["steps"]}[name]


class AdoptionExperienceTests(unittest.TestCase):
    def test_unadopted_status_is_read_only_and_starts_with_calibration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
            before = snapshot(root)
            report = acima.status_project(root)
            self.assertEqual(snapshot(root), before)
            self.assertEqual(len(report["steps"]), 11)
            self.assertEqual(report["steps"][0]["state"], "READY")
            self.assertFalse(report["next"]["approvalRequired"])
            self.assertFalse(report["next"]["writes"])
            command = report["next"]["command"]
            self.assertIn("preflight.py", command)
            self.assertLess(command.index("preflight.py"), command.index("assess"))

    def test_optional_documents_never_appear_in_next(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config(root)
            (root / "src").mkdir()
            (root / "src" / "a.py").write_text("VALUE = 1\n", encoding="utf-8")
            baseline(root)
            report = acima.status_project(root)
            self.assertTrue(all(not item["present"] for item in report["optional"]))
            self.assertNotIn("plan", report["next"]["action"].lower())
            self.assertIn("approve", report["next"]["action"].lower())
            self.assertTrue(report["next"]["approvalRequired"])
            self.assertNotIn("Write the adoption plan", acima.status_text(report))

    def test_workflow_that_only_mentions_acima_is_not_a_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config(root)
            baseline(root)
            workflow = root / ".github/workflows/ci.yml"
            workflow.parent.mkdir(parents=True)
            workflow.write_text("name: acima notes\non: [push]\njobs: {}\n", encoding="utf-8")
            report = acima.status_project(root)
            gate = step(report, "gate")
            self.assertEqual(gate["state"], "BLOCKED")
            self.assertIn("mentions ACIMA", gate["evidence"])
            self.assertIn("real gate", report["next"]["action"])

    def test_configured_gate_is_in_progress_not_complete(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config(root)
            baseline(root)
            workflow = root / ".github/workflows/acima.yml"
            workflow.parent.mkdir(parents=True)
            workflow.write_text(
                "on: pull_request\njobs:\n  gate:\n    steps:\n"
                "      - run: python3 examples/python/tools/acima_arch.py --root . --level L2\n",
                encoding="utf-8",
            )
            report = acima.status_project(root)
            gate = step(report, "gate")
            self.assertEqual(gate["state"], "IN_PROGRESS")
            self.assertFalse(gate["verified"])
            self.assertIn("configured, not observed", gate["evidence"])
            self.assertIn("pull request", report["next"]["action"].lower())
            self.assertIn("in progress", acima.status_text(report))

    def test_observed_gate_completes_the_step(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config(root)
            baseline(root)
            write_json(root, "docs/acima/gate-observed.json", {
                "exitCode": 1, "command": "acima_arch.py --root . --level L2",
                "observedOn": date.today().isoformat()})
            gate = step(acima.status_project(root), "gate")
            self.assertEqual(gate["state"], "COMPLETE")
            self.assertIn("observed exit 1", gate["evidence"])

    def test_zero_source_run_is_rejected_as_a_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config(root)
            baseline(root, sources=0)
            report = acima.status_project(root)
            freeze = step(report, "freeze")
            self.assertEqual(freeze["state"], "BLOCKED")
            self.assertIn("sourceFiles", freeze["evidence"])
            self.assertTrue(report["next"]["writes"] is False)

    def test_manual_evidence_file_is_not_a_claim(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config(root)
            baseline(root)
            write_json(root, ".acima/manual-evidence.json",
                       {"standard": CATALOG["version"], "evidence": []})
            report = acima.status_project(root)
            claim_step = step(report, "claim")
            self.assertNotEqual(claim_step["state"], "COMPLETE")
            self.assertIn("PARTIAL ASSESSMENT", claim_step["evidence"])
            self.assertNotIn("FULL CONFORMANCE", acima.status_text(report))

    def test_expired_evidence_blocks_the_claim(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config(root, level="L2")
            baseline(root, level="L2")
            artifact = root / "docs/reviews/C003.md"
            artifact.parent.mkdir(parents=True)
            artifact.write_text("reviewed\n", encoding="utf-8")
            write_json(root, ".acima/manual-evidence.json", {
                "standard": CATALOG["version"],
                "evidence": [{
                    "rule": "ACIMA-C003", "scope": "repository", "owner": "team",
                    "reviewer": "architecture-review", "method": "review",
                    "artifact": "docs/reviews/C003.md",
                    "reviewedOn": "2020-01-01", "expires": "2020-06-01", "result": "pass",
                }],
            })
            claim_step = step(acima.status_project(root), "claim")
            self.assertEqual(claim_step["state"], "BLOCKED")
            self.assertIn("invalid", claim_step["evidence"].lower())

    def test_fix_is_a_plan_and_never_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src").mkdir()
            (root / "src" / "a.py").write_text("VALUE = 1\n", encoding="utf-8")
            before = snapshot(root)
            plan = acima.fix_plan({"findings": [{
                "rule": "ACIMA-D001", "severity": "error", "message": "crosses a boundary",
                "path": "src/a.py", "line": 1}]}, ["ACIMA-D001"])
            self.assertEqual(snapshot(root), before)
            self.assertEqual(plan["selected"], 1)
            self.assertIn("plan", plan["limitation"].lower())
            self.assertIn("never edits", plan["limitation"])

    def test_assessment_leaves_the_target_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src").mkdir()
            (root / "src" / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
            before = snapshot(root)
            acima.assess_project(root)
            acima.status_project(root)
            self.assertEqual(snapshot(root), before)

    def test_returning_user_gets_exactly_one_next_action(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config(root)
            baseline(root)
            next_step = acima.status_project(root)["next"]
            self.assertTrue(next_step["action"])
            self.assertTrue(next_step["command"])
            self.assertTrue(next_step["doneWhen"])
            self.assertIsInstance(next_step["approvalRequired"], bool)

    def test_unsupported_language_is_reported_without_a_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pom.xml").write_text("<project/>\n", encoding="utf-8")
            (root / "App.java").write_text("class App {}\n", encoding="utf-8")
            before = snapshot(root)
            report = acima.status_project(root)
            self.assertEqual(snapshot(root), before)
            self.assertFalse(report["config"]["present"])
            self.assertFalse(report["next"]["writes"])
            self.assertFalse(report["next"]["approvalRequired"])

    def test_copied_skill_has_a_runnable_vendor_snapshot(self) -> None:
        vendor = ROOT / "skills/acima-adoption/vendor"
        for relative in ("tools/acima.py", "examples/python/tools/acima_arch.py",
                         "docs/commands.md", "MANIFEST.json"):
            self.assertTrue((vendor / relative).is_file(), relative)
        skill = (ROOT / "skills/acima-adoption/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("<skill>/vendor/tools/acima.py", skill)

    def test_skill_is_compact_and_teaches_the_contract(self) -> None:
        text = (ROOT / "skills/acima-adoption/SKILL.md").read_text(encoding="utf-8")
        self.assertLess(len(text.splitlines()), 500)
        for phrase in ("Current state", "What happened", "What it means",
                       "What happens next", "User involvement", "Next action"):
            self.assertIn(phrase, text)
        for phrase in ("source checkout", "Copied or installed skill",
                       "different target repository"):
            self.assertIn(phrase, text)
        intro = text.split("## Positioning", 1)[0]
        self.assertNotIn("ACIMA-D0", intro)


if __name__ == "__main__":
    unittest.main()
