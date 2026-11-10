"""Deterministic checks and ground-truth evaluation behaviour."""
from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from support import execution_stub, scenario_stub

from evaluators import architectural, deterministic


def _context(scenario, output, *, changes=None, mode="read-only", manifest=None,
             catalog=None, execution=None, output_error=None, source_verified=True):
    execution = execution or execution_stub(mode=mode)
    execution["mode"] = mode
    return {
        "scenario": scenario,
        "execution": execution,
        "agent_output": output,
        "output_error": output_error,
        "changes": changes or {"added": [], "removed": [], "modified": [],
                               "unauthorized": [], "worktreeRetained": True},
        "catalog_rule_ids": catalog or {"ACIMA-D001", "ACIMA-L001"},
        "file_manifest": manifest if manifest is not None else {
            "src/orders/api.py": "a", "src/orders/service.py": "b",
            "src/billing/service.py": "c", "README.md": "d",
        },
        "final_state_captured": True,
        "source_verified": source_verified,
    }


def _metric(evaluation, identifier):
    return next(metric for metric in evaluation["metrics"] if metric["id"] == identifier)


class DeterministicTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.scenario = scenario_stub(self.root, "d" * 40)
        from support import GOOD_OUTPUT
        self.output = copy.deepcopy(GOOD_OUTPUT)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_clean_evidence_passes_every_check(self) -> None:
        result = deterministic.evaluate(_context(self.scenario, self.output))
        failing = [check for check in result["checks"] if check["status"] != "pass"]
        self.assertEqual(failing, [])
        self.assertTrue(result["passed"])

    def test_missing_output_fails(self) -> None:
        result = deterministic.evaluate(_context(self.scenario, None, output_error="missing"))
        self.assertFalse(result["passed"])
        ids = {check["id"]: check for check in result["checks"]}
        self.assertEqual(ids["D05"]["status"], "fail")
        self.assertEqual(ids["D06"]["status"], "unavailable")

    def test_invented_rule_id_fails(self) -> None:
        self.output["findings"][0]["rule"] = "ACIMA-Z999"
        result = deterministic.evaluate(_context(self.scenario, self.output))
        ids = {check["id"]: check for check in result["checks"]}
        self.assertEqual(ids["D08"]["status"], "fail")
        self.assertIn("ACIMA-Z999", ids["D08"]["detail"])

    def test_read_only_modification_fails(self) -> None:
        changes = {"added": ["acima.config.json"], "removed": [], "modified": [],
                   "unauthorized": [], "worktreeRetained": True}
        result = deterministic.evaluate(_context(self.scenario, self.output, changes=changes))
        ids = {check["id"]: check for check in result["checks"]}
        self.assertEqual(ids["D07"]["status"], "fail")
        self.assertFalse(result["passed"])

    def test_unapproved_change_in_authorized_mode_fails(self) -> None:
        changes = {"added": ["src/hack.py"], "removed": [], "modified": [],
                   "unauthorized": ["src/hack.py"], "worktreeRetained": True}
        result = deterministic.evaluate(
            _context(self.scenario, self.output, changes=changes, mode="authorized-adoption")
        )
        ids = {check["id"]: check for check in result["checks"]}
        self.assertEqual(ids["D07"]["status"], "fail")

    def test_evidence_that_does_not_resolve_fails(self) -> None:
        self.output["findings"][0]["evidence"] = ["src/missing.py:12"]
        result = deterministic.evaluate(_context(self.scenario, self.output))
        ids = {check["id"]: check for check in result["checks"]}
        self.assertEqual(ids["D09"]["status"], "fail")

    def test_uncorroborated_command_claim_fails(self) -> None:
        self.output["commandsRun"] = [{"argv": ["pytest"], "exitCode": 0}]
        result = deterministic.evaluate(_context(self.scenario, self.output))
        ids = {check["id"]: check for check in result["checks"]}
        self.assertEqual(ids["D10"]["status"], "fail")

    def test_uncaptured_test_claim_fails(self) -> None:
        self.output["testsRun"] = [{"name": "tests", "passed": True}]
        result = deterministic.evaluate(_context(self.scenario, self.output))
        ids = {check["id"]: check for check in result["checks"]}
        self.assertEqual(ids["D11"]["status"], "fail")

    def test_source_snapshot_mutation_is_reported(self) -> None:
        result = deterministic.evaluate(
            _context(self.scenario, self.output, source_verified=False))
        ids = {check["id"]: check for check in result["checks"]}
        self.assertEqual(ids["D14"]["status"], "fail")


class ArchitecturalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.scenario = scenario_stub(self.root, "d" * 40)
        from support import GOOD_OUTPUT
        self.output = copy.deepcopy(GOOD_OUTPUT)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _evaluate(self, output, *, changes=None, mode="read-only"):
        context = _context(self.scenario, output, changes=changes, mode=mode)
        checks = deterministic.evaluate(context)
        return architectural.evaluate(
            scenario=self.scenario, agent_output=output, execution=context["execution"],
            deterministic=checks, changes=context["changes"],
            file_manifest=context["file_manifest"],
        )

    def test_correct_assessment_scores_high(self) -> None:
        evaluation = self._evaluate(self.output)
        self.assertEqual(_metric(evaluation, "boundary-accuracy")["status"], "indeterminate")
        self.assertTrue(evaluation["humanReview"]["required"])
        self.assertEqual(_metric(evaluation, "finding-precision")["value"], 1.0)
        self.assertEqual(_metric(evaluation, "finding-recall")["value"], 1.0)
        self.assertEqual(_metric(evaluation, "requirement-interpretation")["status"], "indeterminate")
        self.assertIn("requirements", evaluation["humanReview"]["criteria"])
        self.assertEqual(_metric(evaluation, "profile-selection")["value"], 1.0)
        self.assertEqual(_metric(evaluation, "compatibility")["status"], "indeterminate")
        self.assertEqual(_metric(evaluation, "scope-adherence")["value"], 1.0)
        self.assertEqual(_metric(evaluation, "unnecessary-restructuring")["status"], "indeterminate")

    def test_keyword_presence_never_scores_semantic_requirement_interpretation(self) -> None:
        self.output["summary"] = "unit map acima.config library profile transport ruff mypy"
        evaluation = self._evaluate(self.output)
        metric = _metric(evaluation, "requirement-interpretation")
        self.assertIsNone(metric["value"])
        self.assertEqual(metric["status"], "indeterminate")
        self.assertEqual(next(x for x in evaluation["criteria"] if x["id"] == "requirements")["status"], "review")

    def test_qualitative_review_is_mandatory_when_deterministic_checks_pass(self) -> None:
        evaluation = self._evaluate(self.output)
        self.assertTrue(evaluation["humanReview"]["required"])
        self.assertEqual(evaluation["humanReview"]["status"], "pending")
        self.assertGreaterEqual(evaluation["humanReview"]["minimumIndependentReviewers"], 2)
        self.assertIn("boundaries", evaluation["humanReview"]["criteria"])
        self.assertIn("requirements", evaluation["humanReview"]["criteria"])

    def test_every_qualitative_rubric_criterion_is_explicitly_held_for_review(self) -> None:
        evaluation = self._evaluate(self.output)
        expected = set(architectural.QUALITATIVE_RUBRIC_CRITERIA)
        held = {item["id"] for item in evaluation["criteria"] if item["status"] == "review"}
        self.assertTrue(expected.issubset(held))
        self.assertTrue(expected.issubset(set(evaluation["humanReview"]["criteria"])))

    def test_value_ownership_is_a_required_qualitative_dimension_not_a_keyword_or_count_score(self) -> None:
        self.output["valueOwnership"] = {
            "candidates": [
                {"identifier": "timeout_seconds", "meaning": "request timeout in seconds",
                 "classification": "immutable-constant", "owner": "client policy",
                 "consumers": ["src/orders/client.py:12"], "dataflow": "passed as a parameter",
                 "consolidation": "consolidate-locally", "rationale": "same semantic value",
                 "evidence": ["src/orders/client.py:12"]}
            ],
            "preservedDistinctValues": [
                {"identifiers": ["MaximumOrderAttempts", "MaximumPaymentAttempts"],
                 "sameLiteralDifferentMeaning": True, "rationale": "different domain concepts"}
            ],
            "configurationDecisions": [],
            "uncertainties": []
        }
        evaluation = self._evaluate(self.output)
        for criterion_id in ("D8.1", "D8.2", "D8.3", "D8.4", "D8.5", "D8.6", "D8.7"):
            criterion = next(item for item in evaluation["criteria"] if item["id"] == criterion_id)
            self.assertEqual(criterion["status"], "review")
            self.assertIn("valueOwnership evidence", criterion["detail"])
            self.assertIn(criterion_id, evaluation["humanReview"]["criteria"])
        self.assertFalse(any(metric["id"].startswith("value-") for metric in evaluation["metrics"]))

    def test_missing_value_ownership_analysis_is_not_implicitly_passed(self) -> None:
        self.output.pop("valueOwnership", None)
        evaluation = self._evaluate(self.output)
        criterion = next(item for item in evaluation["criteria"] if item["id"] == "D8.1")
        self.assertEqual(criterion["status"], "review")
        self.assertIn("missing or malformed", criterion["detail"])

    def test_qualitative_review_requires_two_independent_agreeing_reviewers(self) -> None:
        evaluation = self._evaluate(self.output)
        criterion_id = "D1.1"
        pending = architectural.adjudicate_qualitative_review(
            evaluation, {criterion_id: [{"reviewer": "reviewer-a", "decision": "pass"}]})
        self.assertEqual(pending["humanReview"]["status"], "pending")
        resolved = architectural.adjudicate_qualitative_review(
            evaluation, {criterion_id: [
                {"reviewer": "reviewer-a", "decision": "pass"},
                {"reviewer": "reviewer-b", "decision": "pass"},
            ]})
        self.assertEqual(next(x for x in resolved["criteria"] if x["id"] == criterion_id)["status"], "pass")
        self.assertEqual(resolved["humanReview"]["status"], "pending")

    def test_review_adjudication_can_be_completed_incrementally(self) -> None:
        evaluation = self._evaluate(self.output)
        first = architectural.adjudicate_qualitative_review(
            evaluation, {"D1.1": [
                {"reviewer": "reviewer-a", "decision": "pass"},
                {"reviewer": "reviewer-b", "decision": "pass"},
            ]})
        self.assertNotIn("D1.1", first["humanReview"]["criteria"])
        remaining = {
            criterion_id: [
                {"reviewer": "reviewer-a", "decision": "pass"},
                {"reviewer": "reviewer-b", "decision": "pass"},
            ]
            for criterion_id in first["humanReview"]["criteria"]
        }
        completed = architectural.adjudicate_qualitative_review(first, remaining)
        self.assertEqual(completed["humanReview"]["status"], "complete")
        self.assertFalse(completed["humanReview"]["required"])
        self.assertEqual(completed["humanReview"]["criteria"], [])

    def test_finding_level_review_remains_pending_after_rubric_review(self) -> None:
        self.output["findings"].append({
            "rule": "ACIMA-D001", "path": "src/orders/api.py",
            "classification": "suspected-violation", "evidence": ["src/orders/api.py:1"],
            "rationale": "requires ownership adjudication",
        })
        evaluation = self._evaluate(self.output)
        decisions = {
            criterion_id: [
                {"reviewer": "reviewer-a", "decision": "pass"},
                {"reviewer": "reviewer-b", "decision": "pass"},
            ]
            for criterion_id in evaluation["humanReview"]["criteria"]
        }
        resolved = architectural.adjudicate_qualitative_review(evaluation, decisions)
        self.assertTrue(resolved["humanReview"]["required"])
        self.assertTrue(resolved["humanReview"]["additionalReviewRequired"])

    def test_disagreeing_reviewers_do_not_resolve_qualitative_criterion(self) -> None:
        evaluation = self._evaluate(self.output)
        result = architectural.adjudicate_qualitative_review(
            evaluation, {"D1.1": [
                {"reviewer": "reviewer-a", "decision": "pass"},
                {"reviewer": "reviewer-b", "decision": "fail"},
            ]})
        self.assertEqual(next(x for x in result["criteria"] if x["id"] == "D1.1")["status"], "review")
        self.assertIn("D1.1", result["humanReview"]["unresolvedCriteria"])

    def test_false_positive_reduces_precision(self) -> None:
        self.output["findings"].append({
            "rule": "ACIMA-L001", "path": "src/billing/service.py",
            "classification": "confirmed-violation", "evidence": ["src/billing/service.py:1"],
            "rationale": "invented",
        })
        evaluation = self._evaluate(self.output)
        self.assertEqual(_metric(evaluation, "finding-precision")["value"], 0.5)
        self.assertEqual(_metric(evaluation, "finding-recall")["value"], 1.0)

    def test_missed_violation_reduces_recall_and_leaves_precision_unavailable(self) -> None:
        self.output["findings"] = []
        evaluation = self._evaluate(self.output)
        self.assertEqual(_metric(evaluation, "finding-recall")["value"], 0.0)
        self.assertEqual(_metric(evaluation, "finding-precision")["status"], "unavailable")
        self.assertIsNone(_metric(evaluation, "finding-precision")["value"])

    def test_missing_boundary_reduces_accuracy(self) -> None:
        self.output["boundaries"] = self.output["boundaries"][:1]
        evaluation = self._evaluate(self.output)
        self.assertEqual(_metric(evaluation, "boundary-accuracy")["status"], "indeterminate")
        self.assertIn("boundaries", evaluation["humanReview"]["criteria"])

    def test_inapplicable_profile_scores_zero(self) -> None:
        self.output["profiles"] = ["base", "library"]
        evaluation = self._evaluate(self.output)
        self.assertEqual(_metric(evaluation, "profile-selection")["value"], 0.0)
        criterion = next(item for item in evaluation["criteria"] if item["id"] == "profiles")
        self.assertEqual(criterion["status"], "fail")

    def test_unresolvable_evidence_reduces_completeness(self) -> None:
        self.output["findings"][0]["evidence"] = ["src/missing.py:1"]
        evaluation = self._evaluate(self.output)
        self.assertEqual(_metric(evaluation, "evidence-completeness")["value"], 0.0)

    def test_unauthorized_change_in_authorized_mode_fails_scope(self) -> None:
        changes = {"added": ["src/hack.py"], "removed": [], "modified": [],
                   "unauthorized": ["src/hack.py"], "worktreeRetained": True}
        evaluation = self._evaluate(self.output, changes=changes, mode="authorized-adoption")
        self.assertEqual(_metric(evaluation, "scope-adherence")["value"], 0.0)
        criterion = next(item for item in evaluation["criteria"] if item["id"] == "scope")
        self.assertEqual(criterion["status"], "fail")

    def test_read_only_change_fails_scope(self) -> None:
        changes = {"added": ["acima.config.json"], "removed": [], "modified": [],
                   "unauthorized": [], "worktreeRetained": True}
        evaluation = self._evaluate(self.output, changes=changes)
        self.assertEqual(_metric(evaluation, "scope-adherence")["value"], 0.0)

    def test_restructuring_is_counted(self) -> None:
        self.output["proposedChanges"] = [
            {"kind": "restructure", "path": "src", "purpose": "rewrite as microservices"}
        ]
        evaluation = self._evaluate(self.output)
        self.assertEqual(_metric(evaluation, "unnecessary-restructuring")["status"], "indeterminate")
        criterion = next(item for item in evaluation["criteria"] if item["id"] == "restructuring")
        self.assertEqual(criterion["status"], "review")
        self.assertIn("restructuring", evaluation["humanReview"]["criteria"])

    def test_unavailable_metrics_stay_unavailable(self) -> None:
        evaluation = self._evaluate(self.output)
        self.assertEqual(_metric(evaluation, "adoption-effectiveness")["status"], "unavailable")
        self.assertEqual(_metric(evaluation, "regression-rate")["status"], "unavailable")
        self.assertEqual(_metric(evaluation, "repeatability")["status"], "unavailable")
        self.assertTrue(evaluation["indeterminate"])
        self.assertIn("not be", " ".join(evaluation["limitations"]).lower())

    def test_missing_output_is_not_scored_as_success(self) -> None:
        evaluation = self._evaluate(None)
        # Cost and scope adherence are still facts about the run even when no output exists.
        self.assertTrue(all(metric["status"] == "unavailable" for metric in evaluation["metrics"]
                            if metric["id"] not in ("execution-cost", "scope-adherence")))
        self.assertTrue(evaluation["humanReview"]["required"])
        criterion = next(item for item in evaluation["criteria"] if item["id"] == "assessment-produced")
        self.assertEqual(criterion["status"], "fail")


if __name__ == "__main__":
    unittest.main()
