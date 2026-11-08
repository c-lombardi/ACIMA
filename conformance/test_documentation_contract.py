"""Keep human documentation aligned with the executable and architectural contract."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class DocumentationContractTests(unittest.TestCase):
    def test_rule_index_names_every_non_executed_rule(self) -> None:
        coverage = json.loads(read("conformance/coverage.json"))
        not_executed = set(coverage["profiles"]["python"]["notExecuted"])
        self.assertEqual(len(not_executed), 6)
        index = read("docs/rules/index.md")
        # coverage.json uses the ACIMA- prefixed ids; the human catalog table uses short ids.
        for rule in sorted(not_executed):
            short = rule.split("-", 1)[-1]
            self.assertIn(f"`{short}`", index, f"{rule} is not documented in the rule index")
        self.assertNotIn("Four rules cannot", index)
        self.assertIn("Six normative rules", index)

    def test_preflight_reference_matches_any_source_classification(self) -> None:
        preflight = read("skills/acima-adoption/references/00-preflight.md")
        self.assertIn("at least one existing source file", preflight)
        self.assertNotIn("10 or more source files", preflight)

    def test_skill_waiver_guidance_is_fingerprint_scoped(self) -> None:
        for path in (
            "skills/acima-adoption/references/00-preflight.md",
            "skills/acima-adoption/references/20-brownfield.md",
            "skills/acima-adoption/references/60-troubleshooting.md",
        ):
            text = read(path)
            self.assertNotIn("(rule, unit)", text)
            self.assertIn("fingerprint", text.lower())

    def test_conformance_template_does_not_hardcode_the_wrong_count(self) -> None:
        conformance = read("docs/standard/08-conformance.md")
        self.assertNotIn("24 of 24", conformance)
        self.assertIn("<executed> of <required>", conformance)
        self.assertIn("PARTIAL ASSESSMENT", conformance)

    def test_skill_carries_the_partial_assessment_and_service_stops(self) -> None:
        skill = read("skills/acima-adoption/SKILL.md")
        self.assertIn("PARTIAL ASSESSMENT", skill)
        self.assertIn("service-topology", skill)
        self.assertIn("1.2.3", skill)

    def test_l2_counts_in_the_template_match_the_catalog(self) -> None:
        catalog = json.loads(read("tools/acima-spec/rules.json"))["rules"]
        l2 = [rule for rule in catalog if rule["level"] in ("L1", "L2")]
        self.assertEqual(len(l2), 25)
        not_executed = set(json.loads(read("conformance/coverage.json"))
                           ["profiles"]["python"]["notExecuted"])
        executed = [rule for rule in l2 if rule["id"] not in not_executed]
        self.assertEqual(len(executed), 21)
        conformance = read("docs/standard/08-conformance.md")
        self.assertIn("At L2 the catalog requires 25", conformance)
        self.assertIn("execute 21 of those", conformance)

    def test_waiver_semantics_require_a_fingerprint(self) -> None:
        governance = read("docs/standard/07-executable-governance.md")
        self.assertIn("`rule`, `scope` and `fingerprint` all match", governance)
        self.assertNotIn("`rule` and `scope` both match", governance)
        self.assertIn('"fingerprint": "sha256:', governance)

    def test_glossary_uses_current_greenfield_and_module_definitions(self) -> None:
        glossary = read("skills/acima-adoption/references/glossary.md")
        self.assertNotIn("fewer than ten source files", glossary)
        self.assertIn("no source files", glossary)
        self.assertIn("one or more implementation units", glossary)
        self.assertIn("one exact finding fingerprint", glossary)


if __name__ == "__main__":
    unittest.main()
