"""Portfolio experiment: rubric, references, freezing and pinned preparation."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
HARNESS_ROOT = TESTS_DIR.parents[1]
if str(HARNESS_ROOT / "harness") not in sys.path:
    sys.path.insert(0, str(HARNESS_ROOT / "harness"))

from runner import portfolio  # noqa: E402
from runner.lifecycle import InvalidConfiguration  # noqa: E402

EXPERIMENT = "portfolio-2026-11-10"
ACIMA_ROOT = HARNESS_ROOT.parents[1]


class PortfolioExperimentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.loaded = portfolio.load_experiment(HARNESS_ROOT, EXPERIMENT)
        self.manifest = self.loaded["manifest"]
        self.rubric = self.loaded["rubric"]

    def test_v2_targets_acima_module_ownership_and_resolves_httpx_reference(self) -> None:
        loaded = portfolio.load_experiment(HARNESS_ROOT, "portfolio-2026-11-10-v2")
        manifest = loaded["manifest"]
        rubric = loaded["rubric"]
        self.assertEqual(manifest["boundaryMeasurement"]["target"], "ACIMA module ownership")
        self.assertEqual(rubric["version"], "1.1.0")
        httpx = json.loads((loaded["directory"] / "references" / "httpx.json").read_text(encoding="utf-8"))
        self.assertEqual([item["module"] for item in httpx["expectedBoundaries"]], ["httpx"])
        self.assertEqual(len(httpx["componentCandidates"]), 6)
        self.assertEqual(httpx["boundaryGroundTruth"]["status"], "author-adjudicated-module-map")
        self.assertTrue(httpx["boundaryGroundTruth"]["independentReviewRequired"])

    def test_v2_freeze_records_evaluator_and_scenario_hashes(self) -> None:
        loaded = portfolio.load_experiment(HARNESS_ROOT, "portfolio-2026-11-10-v2")
        frozen = json.loads((loaded["directory"] / "frozen.json").read_text(encoding="utf-8"))
        self.assertEqual(frozen["evaluator"]["version"], "1.1.0")
        self.assertTrue(frozen["evaluator"]["sha256"])
        self.assertIn("library-python-httpx", frozen["scenarioReferences"])
        self.assertEqual(len(frozen["references"]), 15)
        self.assertEqual(frozen["preparation"]["verified"], 15)
        self.assertEqual(frozen["humanReview"]["minimumIndependentReviewers"], 2)

    def test_manifest_pins_fifteen_repositories_across_five_languages(self) -> None:
        entries = self.manifest["repositories"]
        self.assertEqual(len(entries), 15)
        self.assertEqual(len({entry["id"] for entry in entries}), 15)
        self.assertEqual(len({entry["commit"] for entry in entries}), 15)
        for entry in entries:
            self.assertRegex(entry["commit"], r"^[0-9a-f]{40}$")
            self.assertTrue(entry["url"].startswith("https://github.com/"))
        self.assertEqual(
            {entry["language"] for entry in entries},
            {"python", "typescript", "go", "dotnet", "java"},
        )

    def test_manifest_pins_match_the_adjudicated_evidence(self) -> None:
        references = portfolio.build_references(HARNESS_ROOT, EXPERIMENT)
        self.assertEqual(set(references), {entry["id"] for entry in self.manifest["repositories"]})
        for entry in self.manifest["repositories"]:
            self.assertEqual(references[entry["id"]]["repository"]["commit"], entry["commit"])

    def test_rubric_covers_every_dimension_and_keeps_consent_a_hard_failure(self) -> None:
        self.assertEqual(len(self.rubric["dimensions"]), 7)
        ids = {dimension["id"] for dimension in self.rubric["dimensions"]}
        self.assertEqual(ids, {"D1", "D2", "D3", "D4", "D5", "D6", "D7"})
        for dimension in self.rubric["dimensions"]:
            self.assertTrue(dimension["criteria"])
            for criterion in dimension["criteria"]:
                self.assertIn(criterion["judgement"], {"deterministic", "qualitative", "mixed"})
        hard = {failure["id"] for failure in self.rubric["hardFailures"]}
        self.assertEqual(hard, {"HF1", "HF2", "HF3"})
        consent = next(d for d in self.rubric["dimensions"] if d["id"] == "D7")
        self.assertIn("Never", consent["unavailableWhen"])
        self.assertEqual(self.rubric["measurement"]["aggregation"], "none")
        self.assertTrue(self.rubric["provenance"]["establishedBeforeModelExecution"])

    def test_references_come_from_adjudicated_unit_maps_only(self) -> None:
        references = portfolio.build_references(HARNESS_ROOT, EXPERIMENT)
        httpx = references["httpx"]
        self.assertTrue(httpx["expectedBoundaries"])
        for boundary in httpx["expectedBoundaries"]:
            self.assertTrue(boundary["evidencePaths"])
            self.assertIn("author-reviewed", boundary["source"])
        self.assertEqual(httpx["boundaryGroundTruth"]["status"], "adjudicated-unit-map")
        self.assertEqual(httpx["findingGroundTruth"]["precisionRecall"], "unavailable")

        for repository_id in ("jsoup", "gson", "mall"):
            java = references[repository_id]
            self.assertEqual(java["expectedBoundaries"], [])
            self.assertEqual(java["boundaryGroundTruth"]["status"], "unavailable")
            self.assertEqual(java["dimensionAvailability"]["boundaryAccuracy"], "unavailable")

    def test_preserved_choices_and_artefacts_stay_separate(self) -> None:
        references = portfolio.build_references(HARNESS_ROOT, EXPERIMENT)
        drizzle = references["drizzle-orm"]
        self.assertEqual(drizzle["knownViolations"], [])
        self.assertTrue(drizzle["preservedChoices"])
        self.assertTrue(any(item["classification"] == "false_positive"
                            for item in drizzle["enforcerArtefacts"]))
        spectre = references["spectre-console"]
        self.assertTrue(spectre["knownViolations"])
        self.assertTrue(spectre["preservedChoices"])

    def test_reference_derivation_rejects_an_unpinned_repository(self) -> None:
        loaded = portfolio.load_experiment(HARNESS_ROOT, EXPERIMENT)
        manifest = json.loads(json.dumps(loaded["manifest"]))
        manifest["repositories"][0]["repo"] = "example/not-in-evidence"
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / EXPERIMENT
            directory.mkdir(parents=True)
            (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            shutil.copy(HARNESS_ROOT / "experiments" / EXPERIMENT / "rubric.v1.json", directory)
            harness = Path(temporary) / "benchmarks" / "ai-adoption"
            harness.mkdir(parents=True)
            with self.assertRaises(InvalidConfiguration):
                portfolio.build_references(harness, EXPERIMENT, acima_root=ACIMA_ROOT)

    def test_freeze_hashes_references_and_refuses_a_second_freeze(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            harness = Path(temporary) / "benchmarks" / "ai-adoption"
            harness.mkdir(parents=True)
            destination = harness / "experiments" / EXPERIMENT
            destination.mkdir(parents=True)
            shutil.copy(HARNESS_ROOT / "experiments" / EXPERIMENT / "manifest.json", destination)
            shutil.copy(HARNESS_ROOT / "experiments" / EXPERIMENT / "rubric.v1.json", destination)
            (destination / "references").mkdir()
            for repository_id, reference in portfolio.build_references(HARNESS_ROOT, EXPERIMENT).items():
                (destination / "references" / f"{repository_id}.json").write_text(
                    json.dumps(reference, indent=2), encoding="utf-8"
                )
            frozen = portfolio.freeze(harness, EXPERIMENT, acima_root=ACIMA_ROOT)
            self.assertEqual(len(frozen["references"]), 15)
            self.assertEqual(frozen["rubric"]["version"], self.rubric["version"])
            self.assertTrue(frozen["collection"]["skill"]["contentSha256"])
            stored = json.loads((destination / "frozen.json").read_text(encoding="utf-8"))
            self.assertEqual(stored["referencesCombinedSha256"], frozen["referencesCombinedSha256"])
            with self.assertRaises(InvalidConfiguration):
                portfolio.freeze(harness, EXPERIMENT, acima_root=ACIMA_ROOT)

    def test_preparation_records_failures_without_aborting_the_portfolio(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            harness = Path(temporary) / "benchmarks" / "ai-adoption"
            harness.mkdir(parents=True)
            shutil.copy(HARNESS_ROOT / "config.json", harness / "config.json")
            destination = harness / "experiments" / EXPERIMENT
            destination.mkdir(parents=True)
            manifest = json.loads(json.dumps(self.manifest))
            manifest["repositories"] = [dict(manifest["repositories"][0],
                                             url="https://example.invalid/acima/nope")]
            (destination / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            shutil.copy(HARNESS_ROOT / "experiments" / EXPERIMENT / "rubric.v1.json", destination)
            summary = portfolio.prepare(harness, EXPERIMENT)
            self.assertEqual(summary["verified"], 0)
            self.assertEqual(summary["failed"], 1)
            self.assertIn(summary["repositories"][0]["status"],
                          {"acquisition_failed", "snapshot_mismatch"})

    def test_report_states_the_execution_blocker_and_lists_every_repository(self) -> None:
        report = portfolio.render_report(HARNESS_ROOT, EXPERIMENT)
        self.assertIn("Phase 4 (model execution) is blocked", report)
        self.assertIn("no agent ran", report.lower())
        for entry in self.manifest["repositories"]:
            self.assertIn(entry["repo"], report)


if __name__ == "__main__":
    unittest.main()
