#!/usr/bin/env python3
"""User-facing communication must explain ACIMA's meaning, not its identifiers.

These tests exercise the generated adoption summary and the skill's worked examples. They
check for the presence of the architectural meaning, consequence, evidence, action and
confidence, not merely for the absence of rule-id strings.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/acima-adoption/scripts/summarize.py"
CATALOG = ROOT / "tools/acima-spec/rules.json"
SKILL = ROOT / "skills/acima-adoption/SKILL.md"
REPORTING = ROOT / "skills/acima-adoption/references/80-reporting.md"


def catalog() -> dict:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def execution_map() -> dict:
    return {rule["id"]: {"executed": True} for rule in catalog()["rules"]}


def finding(rule: str, fingerprint: str, path: str = "src/orders/service.py",
            classification: str | None = None) -> dict:
    entry = next((rule_entry for rule_entry in catalog()["rules"]
                  if rule_entry["id"] == rule), None)
    result = {
        "rule": rule,
        "severity": entry["severity"] if entry else "error",
        "message": "candidate pattern",
        "path": path,
        "line": 12,
        "evidence": "retry_limit = 3",
        "fingerprint": fingerprint,
    }
    if classification:
        result["classification"] = classification
    return result


def summary(findings: list[dict]) -> tuple[dict, str, str]:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "src/orders").mkdir(parents=True)
        (root / "src/catalog").mkdir(parents=True)
        (root / "acima.config.json").write_text(json.dumps({
            "standard": catalog()["version"], "level": "L1", "language": "python",
            "units": [
                {"id": "orders", "module": "orders", "role": "implementation",
                 "paths": ["src/orders"]},
                {"id": "catalog", "module": "catalog", "role": "implementation",
                 "paths": ["src/catalog"]},
            ],
        }), encoding="utf-8")
        report = {
            "standard": catalog()["version"], "level": "L1", "sourceFiles": 4,
            "newFindings": 0, "execution": execution_map(), "findings": findings,
        }
        report_path = root / "gate.json"
        report_path.write_text(json.dumps(report), encoding="utf-8")
        common = [sys.executable, str(SCRIPT), "--root", str(root),
                  "--report", str(report_path), "--catalog", str(CATALOG)]
        json_run = subprocess.run(common + ["--format", "json"],
                                  capture_output=True, text=True)
        markdown_run = subprocess.run(common + ["--format", "markdown"],
                                      capture_output=True, text=True)
        assert json_run.returncode == 0, json_run.stderr
        assert markdown_run.returncode == 0, markdown_run.stderr
        return json.loads(json_run.stdout), markdown_run.stdout, root.as_posix()


def reporting_section(start: str, end: str) -> str:
    text = REPORTING.read_text(encoding="utf-8")
    assert start in text, start
    section = text.split(start, 1)[1]
    if end:
        assert end in section, end
        section = section.split(end, 1)[0]
    lines = [line.strip().lstrip(">").strip() for line in section.splitlines()]
    return " ".join(" ".join(lines).split())


def table_section(markdown: str) -> str:
    assert "## 3. Key findings" in markdown
    return markdown.split("## 3. Key findings", 1)[1].split("## 4.", 1)[0]


class HumanCommunicationTests(unittest.TestCase):
    def test_a006_is_explained_as_value_ownership_not_a_code(self) -> None:
        data, markdown, _ = summary([
            finding("ACIMA-A006", "sha256:a", classification="candidate"),
            finding("ACIMA-A006", "sha256:b", "src/orders/other.py",
                    classification="candidate"),
            finding("ACIMA-A006", "sha256:c", "src/catalog/policy.py",
                    classification="candidate"),
        ])
        group = next(item for item in data["groups"] if item["rule"] == "ACIMA-A006")
        self.assertEqual(group["count"], 3)
        self.assertEqual(group["confidence"].split(" —", 1)[0],
                         "Candidate requiring review")
        section = table_section(markdown)
        self.assertIn("meaningful primitive value", section)
        self.assertIn("immutable declaration", section)
        self.assertIn("semantic identity", section)
        self.assertIn("configuration", section)
        self.assertIn("Candidate requiring review", section)
        self.assertIn("Example: `src/", section)
        self.assertIn("+2 more paths", section)
        self.assertNotIn("ACIMA-A006", section)
        self.assertEqual(section.count("Meaningful value without one immutable owner"), 1)

    def test_l001_explains_the_module_boundary_problem(self) -> None:
        data, markdown, _ = summary([
            finding("ACIMA-L001", "sha256:l001"),
        ])
        group = next(item for item in data["groups"] if item["rule"] == "ACIMA-L001")
        self.assertIn("infrastructure", group["summary"].lower())
        section = table_section(markdown)
        self.assertIn("domain and application logic", section)
        self.assertIn("infrastructure", section)
        self.assertIn("Declare the port", section)
        self.assertIn("dependencies point inward", section)
        self.assertIn("layer boundary", section.lower())
        self.assertNotIn("ACIMA-L001", section)

    def test_r3_guidance_resolves_scope_instead_of_guessing(self) -> None:
        section = reporting_section("### A repository requirement labelled `R3`",
                                    "### Equal values")
        self.assertIn("dependency isolation", section)
        self.assertIn("private implementation", section)
        self.assertIn("published contract", section)
        self.assertIn("separate behaviour from mutable state", section)
        self.assertIn("request-specific data", section)
        self.assertIn("Name which source applies", section)

    def test_d84_explains_equal_values_with_different_meanings(self) -> None:
        section = reporting_section("### Equal values with different meanings (`D8.4`)",
                                    "### An approval request")
        self.assertIn("request timeout", section)
        self.assertIn("cache lifetime", section)
        self.assertIn("different behaviours and different owners", section)
        self.assertIn("numeric equality does not make them the same value", section)
        self.assertIn("Keep them separate", section)
        self.assertIn("units, domain meaning and owner", section)
        self.assertIn("review criterion", section)

    def test_approval_explains_the_actual_changes(self) -> None:
        section = reporting_section("### An approval request", "### An unresolved identifier")
        self.assertIn("`acima.config.json`", section)
        self.assertIn("`.acima/baseline.json`", section)
        self.assertIn("five discovered modules and their roles", section)
        self.assertIn("It does not add CI, change source code or suppress any finding", section)
        self.assertIn("May I create those two files", section)
        for identifier in ("ACIMA-", "A006", "D8.4", "R3"):
            self.assertNotIn(identifier, section)

    def test_unknown_identifier_is_not_invented(self) -> None:
        data, markdown, _ = summary([finding("ACIMA-Z999", "sha256:unknown")])
        group = next(item for item in data["groups"] if item["rule"] == "ACIMA-Z999")
        self.assertTrue(group["unresolved"])
        self.assertEqual(group["title"], "Unresolved architectural check")
        self.assertIn("does not define", group["summary"])
        self.assertIn("reporting defect", group["confidence"])
        self.assertEqual(data["status"], "Assessment incomplete")
        self.assertIn("Unresolved architectural check", markdown)
        self.assertIn("reporting defect", markdown)
        self.assertNotIn("Unauthorised", markdown)

    def test_repeated_findings_are_grouped_with_one_explanation(self) -> None:
        data, markdown, _ = summary([
            finding("ACIMA-A006", "sha256:a", classification="candidate"),
            finding("ACIMA-A006", "sha256:b", "src/orders/other.py",
                    classification="candidate"),
        ])
        group = next(item for item in data["groups"] if item["rule"] == "ACIMA-A006")
        self.assertEqual(group["count"], 2)
        self.assertEqual(len(group["paths"]), 2)
        self.assertEqual(table_section(markdown).count("semantic identity"), 1)

    def test_traceability_survives_behind_the_explanation(self) -> None:
        data, markdown, _ = summary([
            finding("ACIMA-A006", "sha256:a", classification="candidate"),
        ])
        group = data["groups"][0]
        self.assertEqual(group["rule"], "ACIMA-A006")
        self.assertEqual(group["fingerprints"], ["sha256:a"])
        self.assertIn("Internal check identifiers", markdown)
        self.assertIn("technical report", markdown)

    def test_precise_and_accessible_examples_are_both_present(self) -> None:
        section = reporting_section("### Two readers, same finding", "")
        self.assertIn("CatalogRepository", section)
        self.assertIn("Catalog.Contracts", section)
        self.assertIn("Orders team", section)
        self.assertIn("private code", section)
        self.assertIn("published interface", section)

    def test_voice_output_does_not_read_identifiers_aloud(self) -> None:
        section = reporting_section("### Spoken output", "### Two readers")
        spoken = section.split("Say:", 1)[1]
        self.assertIn("operational values", spoken)
        self.assertIn("named declarations", spoken)
        self.assertIn("configuration", spoken)
        self.assertNotIn("A006", spoken)

    def test_skill_requires_the_policy_across_all_interactions(self) -> None:
        text = " ".join((SKILL.parent / "references/42-communication-and-interaction.md").read_text(encoding="utf-8").lower().split())
        self.assertIn("all user-facing communication must express the actual meaning", text)
        self.assertIn("internal identifiers must not be presented", text)
        for surface in ("initial assessment", "findings", "recommendations",
                        "implementation plans", "approval requests", "progress updates",
                        "final reports", "spoken or conversational output"):
            self.assertIn(surface, text)
        self.assertIn("reporting defect", text)
        self.assertIn("normally omit identifiers", text)
        self.assertIn("never ask to “resolve a006”", text)


if __name__ == "__main__":
    unittest.main()
