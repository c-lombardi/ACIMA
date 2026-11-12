"""Keep human documentation aligned with the executable and architectural contract."""
from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def normalized(path: str) -> str:
    text = "\n".join(line.lstrip("> ") for line in read(path).lower().splitlines())
    return " ".join(text.split())


class DocumentationContractTests(unittest.TestCase):
    def test_rule_index_names_every_non_executed_rule(self) -> None:
        coverage = json.loads(read("conformance/coverage.json"))
        not_executed = set(coverage["profiles"]["python"]["notExecuted"])
        self.assertEqual(len(not_executed), 14)
        index = read("docs/rules/index.md")
        # coverage.json uses the ACIMA- prefixed ids; the human catalog table uses short ids.
        for rule in sorted(not_executed):
            short = rule.split("-", 1)[-1]
            self.assertIn(f"`{short}`", index, f"{rule} is not documented in the rule index")
        self.assertNotIn("Four rules cannot", index)
        self.assertIn("Fourteen normative rules", index)

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
        status = read("skills/acima-adoption/references/55-status-and-evidence.md")
        self.assertIn("partial assessment", skill.lower())
        self.assertIn("service-topology", skill)
        self.assertIn(json.loads(read("skills/acima-adoption/manifest.json"))["skillVersion"], skill)

    def test_l2_counts_in_the_template_match_the_catalog(self) -> None:
        catalog = json.loads(read("tools/acima-spec/rules.json"))["rules"]
        l2 = [rule for rule in catalog if rule["level"] in ("L1", "L2")]
        self.assertEqual(len(l2), 38)
        not_executed = set(json.loads(read("conformance/coverage.json"))
                           ["profiles"]["python"]["notExecuted"])
        executed = [rule for rule in l2 if rule["id"] not in not_executed]
        self.assertEqual(len(executed), 33)
        conformance = read("docs/standard/08-conformance.md")
        self.assertIn("At L2 the catalog requires 38", conformance)
        self.assertIn("execute 33 of those", conformance)

    def test_waiver_semantics_require_a_fingerprint(self) -> None:
        governance = read("docs/standard/07-executable-governance.md")
        self.assertIn("`rule`, `scope` and `fingerprint` all match", governance)
        self.assertNotIn("`rule` and `scope` both match", governance)
        self.assertIn('"fingerprint": "sha256:', governance)
        self.assertIn("not `unassigned`", governance)
        self.assertIn("64 lowercase", governance)
        self.assertIn("inclusive on the UTC date", governance)
        self.assertIn("whole path segment", governance)

    def test_preflight_documents_the_shared_waiver_contract(self) -> None:
        preflight = read("skills/acima-adoption/references/00-preflight.md")
        self.assertIn("canonical fingerprint", preflight)
        self.assertIn("strict `YYYY-MM-DD`", preflight)
        self.assertIn("`**` is a whole segment", preflight)

    def test_catalog_marks_automation_and_manual_evidence(self) -> None:
        catalog = json.loads(read("tools/acima-spec/rules.json"))
        manual = {rule["id"] for rule in catalog["rules"]
                  if rule.get("automation") == "manual"}
        self.assertEqual(manual, {"ACIMA-A002", "ACIMA-A004", "ACIMA-A010", "ACIMA-A011",
                                  "ACIMA-A012", "ACIMA-A013", "ACIMA-A014", "ACIMA-A015",
                                  "ACIMA-C003", "ACIMA-C007", "ACIMA-C008", "ACIMA-G004",
                                  "ACIMA-L004", "ACIMA-N003"})
        self.assertEqual(sum(1 for rule in catalog["rules"]
                             if rule.get("automation") == "automated"), 42)
        self.assertEqual(catalog["claimModel"]["manualEvidencePath"],
                         "acima/evidence/manual-evidence.json")
        for rule in catalog["rules"]:
            if rule["id"] in manual:
                self.assertTrue(rule.get("manualEvidence"))

    def test_finding_schema_and_governance_require_fingerprint(self) -> None:
        catalog = json.loads(read("tools/acima-spec/rules.json"))
        self.assertIn("fingerprint", catalog["findingSchema"])
        governance = read("docs/standard/07-executable-governance.md")
        self.assertIn("| `fingerprint` | string | yes |", governance)
        g001 = next(rule for rule in catalog["rules"] if rule["id"] == "ACIMA-G001")
        self.assertIn("fingerprint", g001["summary"])

    def test_claim_classes_and_manual_evidence_are_documented(self) -> None:
        conformance = read("docs/standard/08-conformance.md")
        self.assertIn("FULL CONFORMANCE", conformance)
        self.assertIn("PARTIAL ASSESSMENT", conformance)
        self.assertIn("acima/evidence/manual-evidence.json", conformance)
        self.assertIn("acima.py claim", conformance)
        self.assertIn("8.9 Manual evidence for full claims", conformance)
        self.assertTrue((ROOT / "skills/acima-adoption/assets/manual-evidence.template.json").is_file())

    def test_p9_5_is_explicitly_advisory(self) -> None:
        principles = read("docs/standard/01-principles.md")
        self.assertIn("P9.5 (advisory)", principles)
        self.assertNotIn("**P9.5** A waiver MUST NOT", principles)
        governance = read("docs/standard/07-executable-governance.md")
        self.assertIn("P9.5 is **advisory in Draft 1**", governance)

    def test_manifest_pins_the_current_catalog_and_skill_version(self) -> None:
        catalog_bytes = (ROOT / "tools/acima-spec/rules.json").read_bytes()
        digest = hashlib.sha256(catalog_bytes).hexdigest()
        manifest = json.loads(read("skills/acima-adoption/manifest.json"))
        self.assertEqual(manifest["catalog"]["sha256"], digest)
        self.assertIn(manifest["skillVersion"], read("skills/acima-adoption/SKILL.md"))
        self.assertIn(digest, read("skills/acima-adoption/SKILL.md"))

    def test_glossary_uses_current_greenfield_and_module_definitions(self) -> None:
        glossary = read("skills/acima-adoption/references/glossary.md")
        self.assertNotIn("fewer than ten source files", glossary)
        self.assertIn("no source files", glossary)
        self.assertIn("one or more implementation units", glossary)
        self.assertIn("one exact finding fingerprint", glossary)

    def test_readme_states_own_requirements_and_preserves_design_freedom(self) -> None:
        readme = normalized("README.md")
        self.assertIn("portable architectural requirements", readme)
        self.assertIn("module ownership", readme)
        self.assertIn("compatibility is evaluated against the actual requirements", readme)
        self.assertIn("complements them rather than replacing or ranking them", readme)
        self.assertIn("language-neutral", readme)
        self.assertIn("not an exemption", readme)
        self.assertNotIn("it enforces the boundaries clean architecture", readme)
        self.assertNotIn("the boundaries that choice declares", readme)
        self.assertNotIn("your architecture, enforced", readme)

    def test_service_topology_is_optional_not_a_default_architecture(self) -> None:
        profile = normalized("docs/standard/11-service-topology.md")
        self.assertIn("optional, opinionated architectural profile", profile)
        self.assertIn("not acima's default architecture", profile)
        self.assertIn("only when the profile is explicitly selected", profile)
        self.assertIn("stricter structural requirements", profile)
        self.assertNotIn("default architecture for new systems", profile)

    def test_preface_separates_requirements_from_architectural_freedom(self) -> None:
        preface = normalized("docs/standard/00-preface.md")
        self.assertIn("what acima governs", preface)
        self.assertIn("what acima deliberately leaves to the team", preface)
        self.assertIn("architectural freedom is not an exemption", preface)
        self.assertIn("`base` is the default **mode**, not a default architecture", preface)
        self.assertIn("only when explicitly selected", preface)

    def test_p13_applicability_is_scoped_to_the_service_profile(self) -> None:
        principles = normalized("docs/standard/01-principles.md")
        self.assertIn("p13 applies only in the `service-topology` profile", principles)
        self.assertIn("base acima does not require", principles)

    def test_architecture_guide_explains_compatibility_outcomes(self) -> None:
        guide = normalized("docs/guides/architecture-families.md")
        for outcome in ("**compatible**", "**compatible with adaptation**", "**incompatible**",
                        "**insufficient evidence**"):
            self.assertIn(outcome, guide)
        self.assertIn("not conformance levels", guide)
        self.assertIn("intentionally", guide)
        self.assertIn("stricter", guide)

    def test_adoption_skill_has_a_low_friction_first_turn_for_missing_or_unspecified_intent(self) -> None:
        skill = normalized("skills/acima-adoption/SKILL.md")
        for required in (
            "start here: make the first interaction effortless",
            "no command or a greeting",
            "do not ask for a path again",
            "paste its folder path or repository link",
            "no command, acima terminology, adoption level, module map or configuration is required",
            "unsupported command",
            "infer the closest supported intent",
            "do not ask users to choose l1/l2/l3 before assessment",
            "obtain explicit approval before writing",
        ):
            self.assertIn(required, skill)

    def test_adoption_skill_keeps_users_informed_of_value_scope_progress_and_outcomes(self) -> None:
        skill = normalized("skills/acima-adoption/SKILL.md")
        reference = normalized("skills/acima-adoption/references/35-user-transparency.md")
        for required in (
            "user transparency", "phase purpose", "progress", "decisions", "risks", "evidence", "outcomes",
        ):
            self.assertIn(required, skill)
        for required in (
            "the user must remain informed at every phase", "explain what the user will acquire",
            "deterministic checks and repeatable evidence", "before starting", "while working",
            "before changing anything", "after each phase", "at handoff",
            "phase-specific communication contract", "existing capabilities, proposed capabilities, implemented capabilities and verified capabilities",
            "state coverage explicitly", "assessment consent is not implementation consent", "costs, risks and tradeoffs early",
        ):
            self.assertIn(required, reference)

    def test_adoption_skill_uses_progressive_disclosure(self) -> None:
        skill = read("skills/acima-adoption/SKILL.md")
        manifest = json.loads(read("skills/acima-adoption/manifest.json"))
        self.assertLess(len(skill.splitlines()), 200)
        for reference in (
            "12-getting-started.md", "22-workflow.md", "45-discovery.md",
            "55-status-and-evidence.md", "42-communication-and-interaction.md",
            "75-proposals-and-deliverables.md", "65-commands-and-context.md",
            "72-effects-and-corrections.md",
        ):
            self.assertIn("references/" + reference, manifest["references"])
            self.assertIn(reference, skill)
        self.assertIn("Load the phase-specific reference immediately before performing that phase", read("skills/acima-adoption/references/22-workflow.md"))

    def test_adoption_skill_exposes_reader_first_html_outcome_reporting(self) -> None:
        skill = normalized("skills/acima-adoption/SKILL.md")
        reference = normalized("skills/acima-adoption/references/90-html-outcome-reports.md")
        manifest = json.loads(read("skills/acima-adoption/manifest.json"))
        for required in ("six-page html report", "report.schema.json", "render_report.py"):
            self.assertIn(required, skill)
        for required in ("proposed file", "greenfield", "brownfield", "files.html", "evidence.html", "must not invent facts", "approval"):
            self.assertIn(required, reference)
        self.assertIn("scripts/render_report.py", manifest["scripts"])
        self.assertIn("assets/report.schema.json", manifest["assets"])
        self.assertIn("assets/report-template.css", manifest["assets"])
        self.assertIn("references/90-html-outcome-reports.md", manifest["references"])

    def test_adoption_skill_requires_honest_compatibility_assessment(self) -> None:
        skill = normalized("skills/acima-adoption/SKILL.md")
        self.assertIn("defines portable architectural requirements", skill)
        self.assertIn("compatibility is evaluated against the actual requirements", skill)
        self.assertIn("compatible with adaptation", skill)
        self.assertIn("insufficient evidence", skill)
        self.assertIn("never suggest that adopting acima requires the `service-topology` profile", skill)
        self.assertIn("analysis is never authorization", skill)
        self.assertNotIn("the team's choice decides the shape", skill)
        self.assertNotIn("enforces the boundaries that shape declares", skill)

    def test_faq_assesses_compatibility_instead_of_assuming_it(self) -> None:
        faq = normalized("docs/standard/10-faq.md")
        self.assertIn("compatibility is evaluated against those requirements", faq)
        self.assertIn("architecture compatibility", faq)
        self.assertNotIn("sits beside the architecture you chose", faq)

    def test_core_defines_modules_as_ownership_boundaries_not_artifacts(self) -> None:
        vocabulary = normalized("docs/standard/02-vocabulary.md")
        self.assertIn("identifiable architectural ownership boundary", vocabulary)
        for excluded in ("programming-language construct", "package or distribution format",
                         "deployment unit, process boundary or runtime host"):
            self.assertIn(excluded, vocabulary)
        self.assertIn("there may be more than one composition boundary", vocabulary)
        self.assertIn("library factory", vocabulary)

    def test_core_does_not_require_a_host_service_or_application(self) -> None:
        preface = normalized("docs/standard/00-preface.md")
        self.assertIn("does not require a service, an application", preface)
        self.assertIn("deployment unit, a runtime host or a single global composition boundary", preface)
        composition = normalized("docs/standard/15-composition-and-injection.md")
        self.assertIn("several composition boundaries", composition)
        self.assertIn("library consumer constructing dependencies", composition)

    def test_profiles_are_not_presented_as_defaults(self) -> None:
        for path in ("docs/standard/08-conformance.md", "docs/standard/09-adoption.md"):
            text = normalized(path)
            self.assertNotIn("default for new systems", text)
        library = normalized("docs/standard/12-library-profile.md")
        self.assertIn("not required merely because a package is distributed", library)

    def test_rule_catalog_uses_module_ownership_language(self) -> None:
        catalog = json.loads(read("tools/acima-spec/rules.json"))
        for rule in catalog["rules"]:
            text = " ".join(str(rule.get(field, "")) for field in
                            ("title", "summary", "fix")).lower()
            for phrase in ("application-owned", "application component", "application dependency"):
                self.assertNotIn(phrase, text, rule["id"])

    def test_examples_cover_package_application_and_distributed_shapes(self) -> None:
        guide = normalized("docs/guides/architecture-families.md")
        for phrase in ("a library or package with internal modules",
                       "a conventional application", "a distributed system"):
            self.assertIn(phrase, guide)
        self.assertIn("the service-topology profile is optional", guide)

    def test_skill_materials_do_not_reduce_acima_to_declared_boundaries(self) -> None:
        for path in (
            "skills/acima-adoption/references/05-architecture-families.md",
            "skills/acima-adoption/references/80-reporting.md",
            "skills/acima-adoption/assets/adoption-proposal.md",
        ):
            text = normalized(path)
            self.assertIn("compatibility", text)
            self.assertNotIn("enforces the boundaries that shape declares", text)
            self.assertNotIn("enforces the boundaries your team declares", text)


if __name__ == "__main__":
    unittest.main()
