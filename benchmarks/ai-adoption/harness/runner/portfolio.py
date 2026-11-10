"""Portfolio experiment: pre-registered rubric, frozen references, pinned preparation.

The single-scenario controller answers "what happened in this run". This module answers the
portfolio question: which repositories are in the experiment, what evidence-backed reference exists
for each of them, is that reference frozen before any model runs, and are the pinned snapshots
actually present and verified. It deliberately does not execute an agent and does not score
anything; execution and evaluation stay with the controller and the evaluators.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .acquisition import AcquisitionError, acquire, remove_tree, verify
from .lifecycle import InvalidConfiguration
from .provenance import (
    collection_provenance,
    load_config,
    load_json,
    manifest_sha256,
    sha256_file,
)

DEFAULT_EXPERIMENT = "portfolio-2026-11-10"
CONFIRMED_CLASSIFICATIONS = ("true_positive", "probable_true_positive")
PRESERVED_CLASSIFICATIONS = ("valid_architectural_choice",)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def canonical_sha256(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    import hashlib

    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def experiment_directory(harness_root: Path, experiment: str | None = None) -> Path:
    directory = Path(harness_root) / "experiments" / (experiment or DEFAULT_EXPERIMENT)
    if not directory.is_dir():
        raise InvalidConfiguration(f"unknown experiment {directory.name!r}")
    return directory


def load_experiment(harness_root: Path, experiment: str | None = None) -> dict:
    directory = experiment_directory(harness_root, experiment)
    manifest = load_json(directory / "manifest.json")
    rubric = load_json(directory / manifest.get("rubric", "rubric.v1.json"))
    entries = manifest.get("repositories") or []
    if not entries:
        raise InvalidConfiguration("experiment lists no repositories")
    seen_ids, seen_commits = set(), set()
    for entry in entries:
        for key in ("id", "repo", "url", "commit", "language", "category"):
            if not entry.get(key):
                raise InvalidConfiguration(f"experiment repository entry is missing {key!r}")
        if entry["id"] in seen_ids:
            raise InvalidConfiguration(f"duplicate experiment repository id {entry['id']!r}")
        if entry["commit"] in seen_commits:
            raise InvalidConfiguration(f"duplicate pinned commit {entry['commit']!r}")
        seen_ids.add(entry["id"])
        seen_commits.add(entry["commit"])
    return {"directory": directory, "manifest": manifest, "rubric": rubric}


def reference_path(directory: Path, repository_id: str) -> Path:
    return Path(directory) / "references" / f"{repository_id}.json"


def _boundaries_from_config(config: dict) -> list[dict]:
    boundaries = []
    for unit in config.get("units") or []:
        paths = [str(path) for path in unit.get("paths") or []]
        if not paths:
            continue
        boundaries.append({
            "id": str(unit.get("id") or unit.get("module")),
            "module": str(unit.get("module") or unit.get("id")),
            "role": str(unit.get("role") or "implementation"),
            "evidencePaths": paths,
            "required": True,
            "confidence": "high",
            "source": "author-reviewed unit map (rw-2026-11-08-02)",
            "rationale": (
                "Unit recorded in the ACIMA unit map an operator reviewed for the 2026-11-08 "
                "enforcer run; the map is author-adjudicated, not independently reviewed."
            ),
        })
    return boundaries


def _optional_profile(config: dict) -> tuple[list[str], str]:
    profile = (config.get("profile") or {}).get("kind")
    if profile:
        return ["base", str(profile)], f"reviewed unit map declares the {profile} profile"
    return ["base"], "reviewed unit map declares no optional profile"


def build_reference(entry: dict, item: dict, classifications: dict,
                    acima_root: Path, manifest: dict) -> dict:
    """Derive one reference assessment from adjudicated evidence only."""
    reviewed = entry.get("reviewedConfig")
    config = None
    config_sha = None
    if reviewed:
        config_path = Path(acima_root) / reviewed
        if not config_path.is_file():
            raise InvalidConfiguration(f"reviewed unit map is missing: {reviewed}")
        config = load_json(config_path)
        config_sha = sha256_file(config_path)

    boundaries = _boundaries_from_config(config) if config else []
    profiles, profile_source = _optional_profile(config) if config else (
        ["base"], "no reviewed unit map exists, so only the base profile is established"
    )

    adjudicated = item.get("ground_truth") or classifications.get(entry["id"], {}) or {}
    known, preserved, artefacts = [], [], []
    for rule, record in adjudicated.items():
        entry_class = str(record.get("classification", ""))
        entry_record = {
            "rule": rule,
            "count": int(record.get("count") or 0),
            "classification": entry_class,
            "why": record.get("why", ""),
        }
        if entry_class in CONFIRMED_CLASSIFICATIONS:
            known.append(entry_record)
        elif entry_class in PRESERVED_CLASSIFICATIONS:
            preserved.append(entry_record)
        else:
            artefacts.append(entry_record)

    above = item.get("acima") or {}
    findings = above.get("findings")
    limitations = []
    if not config:
        limitations.append(
            f"No ACIMA unit map was reviewed for {entry['language']}, so boundary-level ground "
            "truth is unavailable rather than assumed."
        )
    if entry["language"] == "java":
        limitations.append(
            "Java has no ACIMA reference enforcer in this revision; no execution-level assessment "
            "exists to compare an agent against."
        )
    if above.get("executed") is False:
        limitations.append("The baseline enforcer run did not execute for this repository.")
    if isinstance(findings, int) and findings and not known:
        limitations.append(
            f"The enforcer reported {findings} finding(s) with no violation-level adjudication; "
            "precision and recall cannot be measured from a count."
        )
    if (item.get("baseline_test_state") or "") in ("blocked", "fail-upstream"):
        limitations.append(
            "Baseline verification is not clean "
            f"({item.get('baseline_test_state')}: {item.get('baseline_test_detail', '')}); "
            "regression measurement would need that recorded before any authorized change."
        )

    available = {
        "boundaryAccuracy": "available" if boundaries else "unavailable",
        "requirementInterpretation": "available",
        "profileSelection": "available" if config else "partial",
        "findingAccuracy": "unavailable",
        "evidenceQuality": "available",
        "architecturalPreservation": "available" if preserved else "unavailable",
        "scopeAndConsent": "available",
    }
    return {
        "schemaVersion": 1,
        "experimentId": manifest["experimentId"],
        "id": entry["id"],
        "repository": {
            "url": entry["url"],
            "commit": entry["commit"],
            "license": item.get("license"),
            "language": entry["language"],
        },
        "softwareCategory": entry["category"],
        "architectureFamily": item.get("architectural_style"),
        "applicableProfiles": profiles,
        "profileSource": profile_source,
        "expectedBoundaries": boundaries,
        "boundaryGroundTruth": {
            "status": "adjudicated-unit-map" if boundaries else "unavailable",
            "note": (
                "Author-adjudicated unit map, reused from the enforcer run; not independently "
                "reviewed and not given to the executing agent."
                if boundaries
                else "No unit map was adjudicated for this repository; boundary matching stays "
                     "unavailable and requires human adjudication."
            ),
        },
        "knownViolations": known,
        "preservedChoices": preserved,
        "enforcerArtefacts": artefacts,
        "findingGroundTruth": {
            "status": "adjudicated-rule-counts" if (known or preserved) else "none",
            "precisionRecall": "unavailable",
            "note": (
                "Adjudication is per rule and count, not per source location, so precision and "
                "recall are reported unavailable rather than estimated."
            ),
        },
        "enforcerRun": {
            "findings": findings,
            "executed": above.get("executed"),
            "sourceFilesReported": above.get("source_files_reported"),
            "rulesPortable": above.get("rules_portable"),
        },
        "baselineVerification": {
            "state": item.get("baseline_test_state"),
            "detail": item.get("baseline_test_detail"),
        },
        "dimensionAvailability": available,
        "limitations": limitations,
        "provenance": {
            "pinSource": manifest["pinSource"],
            "unitMapSource": reviewed,
            "unitMapSha256": config_sha,
            "classificationSource": manifest["classificationSource"],
            "method": "derived from adjudicated evidence; no repository content was re-classified",
            "derivedOn": "2026-11-10",
            "independentReview": False,
            "givenToAgent": False,
        },
    }


def build_references(harness_root: Path, experiment: str | None = None, *,
                     acima_root: Path | None = None) -> dict[str, dict]:
    loaded = load_experiment(harness_root, experiment)
    manifest = loaded["manifest"]
    acima_root = Path(acima_root) if acima_root else Path(harness_root).parents[1]
    portfolio = load_json(acima_root / manifest["pinSource"])
    items = portfolio.get("repositories") or []
    by_repo = {item["repo"]: item for item in items}
    classifications = load_json(acima_root / manifest["classificationSource"])
    references = {}
    for entry in manifest["repositories"]:
        item = by_repo.get(entry["repo"])
        if item is None:
            raise InvalidConfiguration(
                f"{entry['repo']} is not present in {manifest['pinSource']}; resolve the pin "
                "explicitly instead of substituting the default branch"
            )
        if item.get("commit") != entry["commit"]:
            raise InvalidConfiguration(
                f"{entry['repo']} pin mismatch: manifest {entry['commit']} vs evidence "
                f"{item.get('commit')}"
            )
        references[entry["id"]] = build_reference(entry, item, classifications, acima_root, manifest)
    return references


def write_references(harness_root: Path, experiment: str | None = None, *,
                     acima_root: Path | None = None) -> list[Path]:
    loaded = load_experiment(harness_root, experiment)
    directory = loaded["directory"]
    written = []
    for repository_id, reference in build_references(
            harness_root, experiment, acima_root=acima_root).items():
        path = reference_path(directory, repository_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(reference, indent=2) + "\n", encoding="utf-8")
        written.append(path)
    return written


def freeze(harness_root: Path, experiment: str | None = None, *, force: bool = False,
           acima_root: Path | None = None) -> dict:
    loaded = load_experiment(harness_root, experiment)
    directory, manifest, rubric = loaded["directory"], loaded["manifest"], loaded["rubric"]
    acima_root = Path(acima_root) if acima_root else Path(harness_root).parents[1]
    frozen_path = directory / "frozen.json"
    if frozen_path.exists() and not force:
        raise InvalidConfiguration(
            f"{frozen_path.name} already exists; a frozen experiment is immutable. "
            "Use a new experiment directory for a change."
        )
    reference_hashes = {}
    for entry in manifest["repositories"]:
        path = reference_path(directory, entry["id"])
        if not path.is_file():
            raise InvalidConfiguration(
                f"reference for {entry['id']!r} is missing; run the build action before freezing"
            )
        reference = load_json(path)
        if reference["repository"]["commit"] != entry["commit"]:
            raise InvalidConfiguration(
                f"reference for {entry['id']!r} records a different commit than the manifest"
            )
        reference_hashes[entry["id"]] = sha256_file(path)

    scenario_hashes = {}
    for scenario in manifest.get("scenarioReferences") or []:
        scenario_path = Path(harness_root) / scenario["path"]
        if not scenario_path.is_file():
            raise InvalidConfiguration(f"scenario reference {scenario.get('id')!r} is missing: {scenario_path}")
        scenario_hashes[scenario["id"]] = sha256_file(scenario_path)

    evaluator = None
    evaluator_spec = manifest.get("evaluator")
    if evaluator_spec:
        evaluator_path = Path(harness_root) / evaluator_spec["path"]
        if not evaluator_path.is_file():
            raise InvalidConfiguration(f"evaluator source is missing: {evaluator_path}")
        evaluator = {"path": evaluator_spec["path"], "version": evaluator_spec["version"],
                     "sha256": sha256_file(evaluator_path)}

    preparation_path = directory / "preparation" / "summary.json"
    preparation = load_json(preparation_path) if preparation_path.is_file() else None
    frozen = {
        "schemaVersion": 1,
        "experimentId": manifest["experimentId"],
        "frozenAt": utc_now(),
        "rubric": {
            "file": manifest.get("rubric", "rubric.v1.json"),
            "version": rubric.get("version"),
            "sha256": sha256_file(directory / manifest.get("rubric", "rubric.v1.json")),
        },
        "manifestSha256": sha256_file(directory / "manifest.json"),
        "references": reference_hashes,
        "referencesCombinedSha256": canonical_sha256(reference_hashes),
        "scenarioReferences": scenario_hashes,
        "evaluator": evaluator,
        "collection": collection_provenance(acima_root),
        "modelUnderTest": manifest.get("modelUnderTest"),
        "executionMode": manifest.get("executionMode"),
        "preparation": (
            {
                "summarySha256": sha256_file(preparation_path),
                "verified": preparation.get("verified"),
                "failed": preparation.get("failed"),
            }
            if preparation
            else {"status": "not-prepared"}
        ),
        "humanReview": {
            "rubricReviewed": False,
            "referencesReviewed": False,
            "qualitativeOutcomeReview": "required",
            "minimumIndependentReviewers": 2 if "two independent human reviewers" in
                str(rubric.get("measurement", {}).get("humanReview", "")).lower() else 0,
            "agreementRequired": "agree" in str(rubric.get("measurement", {}).get("humanReview", "")).lower(),
            "note": "Author-created rubric and references remain pending independent review.",
        },
    }
    frozen_path.write_text(json.dumps(frozen, indent=2) + "\n", encoding="utf-8")
    return frozen


def prepare(harness_root: Path, experiment: str | None = None, *,
            git_executable: str | None = None, only: list[str] | None = None) -> dict:
    """Acquire every pinned snapshot. Chunked calls merge into one summary."""
    loaded = load_experiment(harness_root, experiment)
    directory, manifest = loaded["directory"], loaded["manifest"]
    config, _limits = load_config(harness_root)
    executable = git_executable or config.get("gitExecutable")
    preparation_dir = directory / "preparation"
    preparation_dir.mkdir(parents=True, exist_ok=True)
    summary_path = preparation_dir / "summary.json"
    previous = load_json(summary_path) if summary_path.is_file() else None
    merged = {record["id"]: record for record in (previous or {}).get("repositories", [])}
    wanted = set(only) if only else {entry["id"] for entry in manifest["repositories"]}
    results = []
    for entry in manifest["repositories"]:
        if entry["id"] not in wanted:
            continue
        workspace = directory / "workspaces" / entry["id"]
        record_path = preparation_dir / f"{entry['id']}.json"
        previous = load_json(record_path) if record_path.is_file() else None
        if (previous and previous.get("status") == "verified"
                and (workspace / "source").is_dir()):
            results.append(previous)
            continue
        record = {
            "id": entry["id"],
            "repo": entry["repo"],
            "commit": entry["commit"],
            "language": entry["language"],
            "workspace": str(workspace),
            "preparedAt": utc_now(),
        }
        try:
            acquisition = acquire(entry["url"], entry["commit"], workspace,
                                  keep_git_history=False, git_executable=executable)
            verified = verify(acquisition)
            record.update({
                "status": "verified" if verified else "snapshot_mismatch",
                "verifiedCommit": acquisition.verified_commit,
                "treeSha256": acquisition.tree_sha256,
                "manifestSha256": manifest_sha256(acquisition.manifest),
                "fileCount": acquisition.file_count,
                "bytes": acquisition.bytes,
                "snapshotVerified": verified,
            })
            reference_file = reference_path(directory, entry["id"])
            if reference_file.is_file():
                reference = load_json(reference_file)
                missing = [
                    path
                    for boundary in reference.get("expectedBoundaries") or []
                    for path in boundary.get("evidencePaths") or []
                    if not (workspace / "source" / path).exists()
                ]
                record["missingEvidencePaths"] = missing
            if verified:
                # The disposable execution copy is created from the snapshot at execution time.
                remove_tree(workspace / "working")
            else:
                record["status"] = "snapshot_mismatch"
        except AcquisitionError as error:
            record["status"] = "acquisition_failed"
            record["error"] = {"code": error.code, "message": error.message}
        except OSError as error:
            record["status"] = "acquisition_failed"
            record["error"] = {"code": "os_error", "message": str(error)}
        record_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        merged[entry["id"]] = record
        results.append(record)

    ordered = [merged[entry["id"]] for entry in manifest["repositories"]
               if entry["id"] in merged]
    summary = {
        "experimentId": manifest["experimentId"],
        "preparedAt": utc_now(),
        "expected": len(manifest["repositories"]),
        "attempted": len(ordered),
        "verified": sum(1 for record in ordered if record.get("status") == "verified"),
        "failed": sum(1 for record in ordered if record.get("status") != "verified"),
        "repositories": ordered,
    }
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def status(harness_root: Path, experiment: str | None = None) -> dict:
    loaded = load_experiment(harness_root, experiment)
    directory, manifest = loaded["directory"], loaded["manifest"]
    summary_path = directory / "preparation" / "summary.json"
    summary = load_json(summary_path) if summary_path.is_file() else None
    frozen_path = directory / "frozen.json"
    references = {}
    for entry in manifest["repositories"]:
        path = reference_path(directory, entry["id"])
        references[entry["id"]] = path.is_file()
    return {
        "experimentId": manifest["experimentId"],
        "repositories": len(manifest["repositories"]),
        "referencesWritten": sum(1 for present in references.values() if present),
        "references": references,
        "frozen": load_json(frozen_path) if frozen_path.is_file() else None,
        "preparation": summary,
        "execution": "blocked: no supported unattended Freebuff invocation and no verified model identifier",
    }


def render_report(harness_root: Path, experiment: str | None = None) -> str:
    loaded = load_experiment(harness_root, experiment)
    directory, manifest, rubric = loaded["directory"], loaded["manifest"], loaded["rubric"]
    state = status(harness_root, experiment)
    summary = state["preparation"] or {}
    frozen = state["frozen"] or {}
    lines = [
        f"# Portfolio experiment — {manifest['experimentId']}",
        "",
        "**Phase 4 (model execution) is blocked.** No agent ran, so this report contains no "
        "assessment, no score and no success claim for any repository.",
        "",
        "## Measurement target",
        "",
        f"- Target: **{manifest.get('boundaryMeasurement', {}).get('target', 'ACIMA module ownership')}**.",
        f"- Not measured: {manifest.get('boundaryMeasurement', {}).get('notTarget', 'component discovery')}.",
        "- A component, folder, package, project, service, class or deployment unit is not automatically an ACIMA module.",
        "- Ownership requires evidence of contracts, implementation ownership, dependency isolation, data/configuration ownership and controlled composition.",
        "",
        "## Model under test",
        "",
        f"- Provider `{manifest['modelUnderTest']['provider']}`, requested model "
        f"`{manifest['modelUnderTest']['model']}` — {manifest['modelUnderTest']['verificationStatus']}.",
        "- Freebuff CLI 0.2.36 exposes interactive start, `login`, `doctor`, `--continue`, "
        "`--cwd`, `--trust-agents`: no unattended prompt, no model selection flag, no structured "
        "event stream and no programmatic authentication. The harness therefore refuses to run.",
        "",
        "## Frozen inputs",
        "",
        f"- Rubric `{rubric.get('rubricId')}` v{rubric.get('version')} — "
        f"{frozen.get('rubric', {}).get('sha256', 'not frozen')[:16]}…",
        f"- Manifest — {frozen.get('manifestSha256', 'not frozen')[:16]}…",
        f"- Evaluator — {frozen.get('evaluator', {}).get('version', 'not recorded')} "
        f"{frozen.get('evaluator', {}).get('sha256', '')[:12]}…",
        f"- Scenario references — {len(frozen.get('scenarioReferences', {}))} files hashed.",
        f"- References — {len(frozen.get('references', {}))} files, combined "
        f"{frozen.get('referencesCombinedSha256', 'not frozen')[:16]}…",
        f"- Skill `{frozen.get('collection', {}).get('skill', {}).get('version', '?')}` "
        f"{frozen.get('collection', {}).get('skill', {}).get('contentSha256', '')[:12]}…, "
        f"catalog `{frozen.get('collection', {}).get('catalog', {}).get('version', '?')}` "
        f"{frozen.get('collection', {}).get('catalog', {}).get('sha256', '')[:12]}…",
        "",
        "## Repository preparation",
        "",
    ]
    records = {record["id"]: record for record in summary.get("repositories", [])}
    lines += [
        "| Repository | Language | Pinned commit | Snapshot | Files | Boundaries (reference) |",
        "|---|---|---|---|---|---|",
    ]
    for entry in manifest["repositories"]:
        record = records.get(entry["id"], {})
        reference_file = reference_path(directory, entry["id"])
        boundaries = "—"
        if reference_file.is_file():
            boundaries = str(len(load_json(reference_file).get("expectedBoundaries") or []))
        verification = record.get("status", "not prepared")
        if record.get("missingEvidencePaths"):
            verification += f"; {len(record['missingEvidencePaths'])} missing path(s)"
        lines.append(
            f"| {entry['repo']} | {entry['language']} | `{entry['commit']}` | {verification} | "
            f"{record.get('fileCount', '—')} | {boundaries} |"
        )
    lines += [
        "",
        f"- Verified snapshots: {summary.get('verified', 0)} of {len(manifest['repositories'])}; "
        f"failures: {summary.get('failed', 0)}.",
        "- Each snapshot is acquired by exact SHA, checked against `rev-parse HEAD`, and hashed; "
        "the disposable working copy is created from the snapshot when an execution happens.",
        "",
        "## Reference availability",
        "",
        "| Repository | Boundary truth | Finding truth | Precision/recall | Profiles |",
        "|---|---|---|---|---|",
    ]
    for entry in manifest["repositories"]:
        reference_file = reference_path(directory, entry["id"])
        if not reference_file.is_file():
            lines.append(f"| {entry['repo']} | not built | — | — | — |")
            continue
        reference = load_json(reference_file)
        lines.append(
            f"| {entry['repo']} | {reference['boundaryGroundTruth']['status']} | "
            f"{reference['findingGroundTruth']['status']} | "
            f"{reference['findingGroundTruth']['precisionRecall']} | "
            f"{', '.join(reference['applicableProfiles'])} |"
        )
    if (manifest.get("measurementExtensions") or {}).get("valueOwnership"):
        lines += [
            "",
            "## Meaningful value ownership and semantic consolidation",
            "",
            "- Rubric dimension: D8.1-D8.7 (qualitative; two independent agreeing human reviewers required).",
            "- Required agent output: valueOwnership, including candidate values, preserved distinct meanings, configuration decisions, dataflow and uncertainty.",
            "- Review covers semantic identity, immutable declarations, same-meaning consolidation at a genuine common owner, explicit value flow, configuration classification, and avoidance of over-centralization.",
            "- Equal literals, matching identifiers, keyword presence, and extraction counts are not evidence of semantic equivalence and are never scored.",
            "- Missing or malformed valueOwnership evidence cannot pass by omission.",
        ]
    lines += [
        "",
        "## What is deliberately unavailable",
        "",
        "- Finding precision and recall for all 15 repositories: adjudication is per rule and "
        "count, not per location.",
        "- Boundary accuracy for the three Java repositories: no unit map was adjudicated.",
        "- Compatibility and recommendation accuracy: no reference establishes a defensible set "
        "for these repositories, and inventing one would grade the agent against a guess.",
        "- Every assessment dimension, because no execution occurred.",
        "",
        "## Next phase",
        "",
        "Obtain a supported unattended provider invocation that can select the model, receive the "
        "skill by path, run in an isolated workspace and emit structured events. Then run one fresh "
        "execution per repository, evaluate each against the frozen reference, and publish the "
        "consolidated result. Nothing in this directory needs to change first: the rubric and "
        "references are already frozen and hashed.",
        "",
    ]
    return "\n".join(lines)
