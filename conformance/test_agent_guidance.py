#!/usr/bin/env python3
"""Adoption-generated AI instruction discovery, preservation and validation."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "conformance"))
import adoption_workflow as workflow  # noqa: E402
import agent_guidance as guidance  # noqa: E402


def write(root: Path, relative: str, text: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def fixture(root: Path) -> None:
    write(root, "src/orders/service.py", "def place():\n    return 1\n")
    write(root, "src/billing/service.py", "def charge():\n    return 1\n")
    write(root, "src/orders/pyproject.toml", "[project]\nname = 'orders'\n")
    write(root, "src/billing/pyproject.toml", "[project]\nname = 'billing'\n")
    from test_adoption_workflow import write_review
    write_review(root)


def run_full(root: Path) -> dict:
    from test_adoption_workflow import full_start
    full_start(root)
    state = workflow.remediate(root, "none", approved_by="Repository owner")
    if state["stages"].get("agent_guidance", {}).get("status") == workflow.AWAITING:
        # This fixture models the owner's separate review and approval of the exact
        # generated instruction proposal; the production workflow still waits.
        state = workflow.guidance(root, approve=True)
    return state


def map_review(root: Path) -> Path:
    proposal = json.loads((root / "acima/evidence/module-map.proposal.json").read_text(encoding="utf-8"))
    review = {
        "schemaVersion": "1.0", "proposalId": proposal["proposalId"],
        "reviewer": "Repository owner", "reviewedOn": workflow._today(),
        "mapDecision": "accept",
        "moduleDecisions": [{"id": item["id"], "decision": "accept"}
                            for item in proposal["modules"]],
        "recommendationDecisions": [{"id": item["id"], "decision": "accept"}
                                    for item in proposal.get("recommendations", [])],
    }
    path = root.parent / (root.name + "-agent-map-review.json")
    path.write_text(json.dumps(review), encoding="utf-8")
    return path


def scope_without_guidance(root: Path) -> Path:
    path = root.parent / (root.name + "-agent-scope.json")
    path.write_text(json.dumps({
        "version": 1, "approvedBy": "Repository owner", "approvedOn": workflow._today(),
        "objectives": [
            {"id": "assessment", "disposition": "required"},
            {"id": "local-enforcement", "disposition": "approved"},
            {"id": "baseline-waivers", "disposition": "approved"},
            {"id": "ci-enforcement", "disposition": "deferred"},
            {"id": "developer-handoff", "disposition": "approved"},
            {"id": "adoption-notifications", "disposition": "deferred"},
        ],
        "approvedPaths": [],
    }), encoding="utf-8")
    document = json.loads(path.read_text(encoding="utf-8"))
    document["approvedPaths"] = workflow._implementation_paths(root, document)
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


class AgentGuidanceTests(unittest.TestCase):
    def test_existing_agents_is_updated_and_user_content_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            original = "# Existing instructions\n\nUse the existing logging convention.\n"
            write(root, "AGENTS.md", original)
            state = run_full(root)
            assert (root / "AGENTS.md").is_file()
            text = (root / "AGENTS.md").read_text(encoding="utf-8")
            self.assertIn("Use the existing logging convention.", text)
            self.assertIn(guidance.START, text)
            self.assertFalse((root / "CLAUDE.md").exists())
            self.assertTrue(state["agentGuidance"]["preservedExisting"])
            self.assertEqual(state["stages"]["agent_guidance"]["status"], "complete")

    def test_existing_claude_is_respected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            write(root, "CLAUDE.md", "# Team rules\n\nPreserve this text.\n")
            state = run_full(root)
            text = (root / "CLAUDE.md").read_text(encoding="utf-8")
            self.assertIn("Preserve this text.", text)
            self.assertIn(guidance.START, text)
            self.assertFalse((root / "AGENTS.md").exists())
            self.assertEqual(state["agentGuidance"]["primaryFile"], "CLAUDE.md")

    def test_no_convention_creates_agents_md(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            state = run_full(root)
            self.assertTrue((root / "AGENTS.md").is_file())
            self.assertFalse((root / "CLAUDE.md").exists())
            self.assertEqual(state["agentGuidance"]["convention"]["convention"], "default-root-agents")

    def test_multiple_conventions_get_one_full_instruction_and_references(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            write(root, "AGENTS.md", "# Agents\n\nOriginal agent rule.\n")
            write(root, "CLAUDE.md", "# Claude\n\nOriginal Claude rule.\n")
            state = run_full(root)
            agents = (root / "AGENTS.md").read_text(encoding="utf-8")
            claude = (root / "CLAUDE.md").read_text(encoding="utf-8")
            self.assertIn("Original agent rule.", agents)
            self.assertIn("Original Claude rule.", claude)
            self.assertIn(guidance.START, agents)
            self.assertIn(guidance.REF_START, claude)
            self.assertNotIn("## Category D", claude)
            self.assertEqual(state["agentGuidance"]["primaryFile"], "AGENTS.md")

    def test_guidance_references_authoritative_map_and_actual_checks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            state = run_full(root)
            primary = (root / "AGENTS.md").read_text(encoding="utf-8")
            enforcement = (root / guidance.ENFORCEMENT_FILE).read_text(encoding="utf-8")
            self.assertIn("acima.config.json", primary)
            self.assertIn("acima/handoff/agent-guidance/judgment-guidance.md", primary)
            command = state["agentGuidance"]["checks"]["command"]
            self.assertTrue(command)
            self.assertIn(command, enforcement)
            self.assertIn(state["agentGuidance"]["checks"]["ciStatus"], enforcement)

    def test_every_catalog_rule_is_represented(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            result = run_full(root)
            text = (root / guidance.JUDGMENT_FILE).read_text(encoding="utf-8")
            rules = guidance._rules()
            validation = result["agentGuidance"]["validation"]
            self.assertEqual(validation["rulesCovered"], len(rules))
            self.assertEqual(validation["rulesRequired"], len(rules))
            for rule in rules:
                self.assertIn(rule["id"], text)
            automated = next(rule for rule in rules if rule.get("automation") == "automated")
            self.assertIn("### %s" % automated["id"], text)
            self.assertIn("Judgment prompt:", text)

    def test_progressive_disclosure_is_shorter_and_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            run_full(root)
            primary = (root / "AGENTS.md").read_text(encoding="utf-8")
            judgment = (root / guidance.JUDGMENT_FILE).read_text(encoding="utf-8")
            self.assertLess(len(primary), len(judgment))
            for path in (guidance.ARCH_FILE, guidance.ENFORCEMENT_FILE,
                         guidance.JUDGMENT_FILE, guidance.WORKFLOW_FILE):
                self.assertIn(path, primary)
                self.assertTrue((root / path).is_file())

    def test_unresolved_decisions_are_visible(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            workflow.start(root, "guided")
            state = workflow._load(root)
            state["blockers"] = ["Owner must confirm the inventory ownership."]
            result = guidance.proposal(root, state)
            text = (root / guidance.PROPOSAL_FILE).read_text(encoding="utf-8")
            self.assertIn("Owner must confirm the inventory ownership.", text)
            self.assertIn("Owner must confirm the inventory ownership.", result["unresolved"])

    def test_changed_sources_are_detected_as_stale(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            run_full(root)
            result = json.loads((root / guidance.RESULT_FILE).read_text(encoding="utf-8"))
            stale, changed = guidance.stale(root, result)
            self.assertFalse(stale)
            config = json.loads((root / "acima.config.json").read_text(encoding="utf-8"))
            config["level"] = "L2"
            (root / "acima.config.json").write_text(json.dumps(config), encoding="utf-8")
            stale, changed = guidance.stale(root, result)
            self.assertTrue(stale)
            self.assertIn("acima.config.json", changed)

    def test_missing_enforcement_is_not_claimed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            from test_adoption_workflow import full_start
            full_start(root)
            state = workflow._load(root)
            (root / "acima/evidence/enforcement.json").unlink()
            guidance.apply(root, state)
            text = (root / "AGENTS.md").read_text(encoding="utf-8")
            self.assertIn("No verified local architectural command", text)
            self.assertNotIn("Run the local architectural command", text)

    def test_refresh_after_map_change_clears_staleness(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            run_full(root)
            result = json.loads((root / guidance.RESULT_FILE).read_text(encoding="utf-8"))
            config = json.loads((root / "acima.config.json").read_text(encoding="utf-8"))
            config["level"] = "L2"
            (root / "acima.config.json").write_text(json.dumps(config), encoding="utf-8")
            state = workflow._load(root)
            refreshed = guidance.proposal(root, state)
            applied = guidance.apply(root, state)
            self.assertEqual(applied["validation"]["status"], "valid")
            self.assertFalse(guidance.stale(root, applied)[0])
            self.assertNotEqual(refreshed["sourceHashes"], result["sourceHashes"])

    def test_guided_scope_without_guidance_waits_for_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            workflow.start(root, "guided")
            workflow.approve(root, map_decisions=map_review(root))
            from test_adoption_workflow import approve_scope
            state_before = workflow._load(root)
            report = state_before["artifacts"]["proposalReport"]
            workflow.approve(
                root, scope=scope_without_guidance(root),
                reviewed_report_sha256=report["sha256"],
                reviewed_by="Repository owner",
            )
            state = workflow.remediate(root, "none", approved_by="Repository owner")
            self.assertEqual(state["stages"]["agent_guidance"]["status"], workflow.DEFERRED)
            self.assertFalse((root / "AGENTS.md").exists())
            with self.assertRaisesRegex(workflow.WorkflowError, "was not selected"):
                workflow.guidance(root, approve=True)

    def test_guidance_does_not_modify_application_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            before = {path.relative_to(root).as_posix(): path.read_bytes()
                      for path in (root / "src").rglob("*") if path.is_file()}
            run_full(root)
            after = {path.relative_to(root).as_posix(): path.read_bytes()
                     for path in (root / "src").rglob("*") if path.is_file()}
            self.assertEqual(before, after)

    def test_final_report_renders_guidance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            state = run_full(root)
            model = {
                "schemaVersion": "1.0", "generatedAt": "2026-11-11T00:00:00Z",
                "repository": {"name": "target", "path": str(root)},
                "recommendation": {"status": "INSUFFICIENT_EVIDENCE", "summary": "Review needed."},
                "overview": {"plainLanguage": "Guidance was generated."},
                "agentGuidance": state["agentGuidance"],
            }
            source = root / "model.json"
            source.write_text(json.dumps(model), encoding="utf-8")
            target = root / "report"
            result = subprocess.run(
                [sys.executable, str(ROOT / "skills/acima-adoption/scripts/render_report.py"),
                 "--input", str(source), "--out-dir", str(target)],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            plan = (target / "plan.html").read_text(encoding="utf-8")
            self.assertIn("AI AGENT GUIDANCE", plan)
            self.assertIn("AGENTS.md", plan)
            self.assertIn("Valid", plan)


if __name__ == "__main__":
    unittest.main()
