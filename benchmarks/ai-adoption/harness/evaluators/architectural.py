"""Structured ground-truth evaluation of an agent's assessment.

The evaluator compares what the agent reported with evidence established independently of it. It
never reads the agent's self-assessment of success, and it never turns a missing comparison into a
pass. Precision and recall are reported only where the scenario records violation-level ground
truth; everywhere else they are ``unavailable`` with the reason.
"""
from __future__ import annotations

from pathlib import PurePosixPath

EVALUATOR_VERSION = "1.2.0"

QUALITATIVE_RUBRIC_CRITERIA = {
    "D1.1": "Actual ACIMA module ownership boundaries are supported by ownership evidence.",
    "D1.2": "Modules are distinguished from packages, projects, services, applications, and deployment units.",
    "D1.3": "The assessment does not invent an architecture or deployment model.",
    "D2.1": "Normative claims are consistent with the actual meaning of the pinned ACIMA standard and catalog.",
    "D2.2": "The assessment does not invent normative requirements, rules, or thresholds.",
    "D2.3": "Normative requirements are distinguished from optional profiles, guidance, and enforcer limitations.",
    "D3.2": "Profile requirements are applied only where the corresponding architectural context exists.",
    "D4.1": "Reported violations are genuine under the repository evidence and ACIMA standard.",
    "D4.2": "Findings do not contradict legitimate preserved architectural choices.",
    "D4.3": "Material adjudicated violations are not missed.",
    "D5.2": "Evidence explains why the cited code or configuration supports each finding.",
    "D5.3": "Confirmed findings, potential findings, and insufficient evidence are distinguished.",
    "D6.1": "Legitimate architectural decisions are preserved.",
    "D6.2": "Recommendations do not impose restructuring unsupported by repository evidence.",
    "D6.3": "Packages, projects, services, and deployment units are not converted into modules without ownership evidence.",
    "D7.3": "The assessment respects the approval boundary and does not imply implementation occurred.",
    "D8.1": "Meaningful values are identified by semantic purpose and ownership, not by literal equality or identifier matching alone.",
    "D8.2": "Meaningful values are declared immutably using the strongest appropriate language construct; incidental literals remain inline.",
    "D8.3": "Repeated values with the same meaning are consolidated at the highest genuine common owner and passed explicitly through the call chain.",
    "D8.4": "Equal primitive values with different meanings, units, domains, or owners remain independently declared.",
    "D8.5": "The assessment traces receiving identifiers, assignments, transformations, parameters, and consumers before claiming semantic equivalence.",
    "D8.6": "Constants are distinguished from deployment, runtime-adjustable, environment-specific, and secret configuration; configuration is resolved at the appropriate composition boundary.",
    "D8.7": "The assessment avoids over-centralization, global constants/configuration dumping grounds, and consolidation across independently owned or deployed boundaries without an explicit shared owner."
}

METRIC_NAMES = {
    "boundary-accuracy": "Architectural boundary accuracy",
    "requirement-interpretation": "Requirement interpretation accuracy",
    "finding-precision": "Finding precision",
    "finding-recall": "Finding recall",
    "evidence-completeness": "Evidence completeness",
    "profile-selection": "Profile selection accuracy",
    "scope-adherence": "Scope adherence",
    "unnecessary-restructuring": "Unnecessary restructuring",
    "adoption-effectiveness": "Adoption effectiveness",
    "regression-rate": "Regression rate",
    "repeatability": "Repeatability",
    "execution-cost": "Execution cost",
    "recommendation": "Qualitative review of recommendation rationale, proportionality, and evidence against the defensible reference set.",
    "compatibility": "Qualitative review of compatibility rationale and repository evidence against the defensible reference set.",
}

INTERPRETATIONS = {
    "boundary-accuracy": "Qualitative adjudication of actual ACIMA module ownership; name/path matches are not scored.",
    "requirement-interpretation": "Qualitative semantic adjudication against the pinned standard/catalog and repository evidence; lexical coverage is not scored.",
    "finding-precision": "Share of reported confirmed violations that match recorded ground truth.",
    "finding-recall": "Share of recorded ground-truth violations the agent reported.",
    "evidence-completeness": "Share of reported findings whose evidence references resolve in the pinned checkout.",
    "profile-selection": "1 when the reported profiles equal the applicable profiles, 0 when an inapplicable profile is claimed, fractional for a missing one.",
    "scope-adherence": "Whether an assessment left the repository untouched and an authorized adoption stayed inside its approval.",
    "unnecessary-restructuring": "Qualitative judgement of whether proposed restructuring is justified by demonstrated ownership problems.",
    "adoption-effectiveness": "Whether an authorized change achieved its named requirement; unavailable for read-only runs.",
    "regression-rate": "Share of baseline verification commands that passed before an authorized change and failed after it.",
    "repeatability": "Consistency across repeated runs of the same scenario, model and skill; computed when a comparison is made.",
    "execution-cost": "Wall-clock duration and, when the adapter reports it, token usage. Provider cost is not inferred.",
    "recommendation": "Qualitative review of recommendation rationale, proportionality, and evidence against the defensible reference set.",
    "compatibility": "Qualitative review of compatibility rationale and repository evidence against the defensible reference set.",
}


def _metric(identifier: str, value: float | None, status: str, detail: str,
            unit: str = "ratio") -> dict:
    if status not in ("measured", "unavailable", "indeterminate"):
        raise ValueError(f"unknown metric status {status!r}")
    return {
        "id": identifier,
        "name": METRIC_NAMES[identifier],
        "value": None if value is None else round(float(value), 3),
        "status": status,
        "unit": unit,
        "detail": detail,
        "interpretation": INTERPRETATIONS[identifier],
    }


def _criterion(identifier: str, description: str, status: str, detail: str,
               evidence: list[str] | None = None) -> dict:
    return {
        "id": identifier,
        "description": description,
        "status": status,
        "detail": detail,
        "evidence": evidence or [],
    }


def _path_matches(reported: str, expected: str) -> bool:
    left = str(PurePosixPath(reported.lstrip("./")))
    right = str(PurePosixPath(expected.lstrip("./")))
    return left == right or left.startswith(right + "/") or right.startswith(left + "/")


def evaluate(*, scenario: dict, agent_output: dict | None, execution: dict,
             deterministic: dict, changes: dict, file_manifest: dict | None = None) -> dict:
    metrics: list[dict] = []
    criteria: list[dict] = []
    indeterminate: list[str] = []
    limitations: list[str] = []

    if agent_output is None:
        reason = "no agent output was captured; the agent produced nothing to evaluate"
        for identifier in ("boundary-accuracy", "requirement-interpretation", "finding-precision",
                           "finding-recall", "evidence-completeness", "profile-selection",
                           "unnecessary-restructuring"):
            metrics.append(_metric(identifier, None, "unavailable", reason))
        criteria.append(_criterion("assessment-produced", "The agent produced an assessment", "fail", reason))
        indeterminate.append(reason)
    else:
        required = [boundary for boundary in scenario["expectedBoundaries"] if boundary.get("required")]
        if required:
            reference_names = [boundary["module"] for boundary in required]
            reported_names = [str(item.get("module", "")) for item in (agent_output.get("boundaries") or []) if isinstance(item, dict)]
            detail = (
                f"Reference records {len(required)} ACIMA module-ownership boundary/boundaries "
                f"({', '.join(reference_names)}); agent reported {len(reported_names)} candidate(s) "
                f"({', '.join(reported_names) or 'none'}). Names, folders, package manifests, and "
                "path overlap cannot establish module ownership. Review explicit contracts, "
                "implementation ownership, dependency isolation, data/configuration ownership, "
                "and controlled composition."
            )
            metrics.append(_metric("boundary-accuracy", None, "indeterminate",
                                   detail + " Requires independent qualitative adjudication."))
            criteria.append(_criterion("boundaries", "Identifies actual ACIMA module-ownership boundaries",
                                       "review", detail,
                                       [str(path) for item in required for path in item.get("evidencePaths", [])]))
            indeterminate.append("boundary accuracy requires qualitative adjudication of ACIMA module ownership")
        else:
            metrics.append(_metric("boundary-accuracy", None, "unavailable",
                                   "No adjudicated ACIMA module-ownership reference exists for this repository."))
            indeterminate.append("boundary accuracy: no module-ownership reference")

        metrics.append(_metric("requirement-interpretation", None, "indeterminate",
                               "Semantic interpretation cannot be established by keyword presence or lexical coverage. "
                               "Compare normative claims with the pinned standard/catalog and repository evidence "
                               "through independent qualitative review."))
        criteria.append(_criterion("requirements", "Applicable ACIMA requirements were interpreted correctly",
                                   "review", "Requires independent semantic review of normative claims, applicability, "
                                   "profiles, enforcement limitations, and uncertainty. No lexical-coverage score is produced."))
        indeterminate.append("requirement interpretation requires independent semantic review")

        reported_findings = [finding for finding in agent_output.get("findings") or []
                             if isinstance(finding, dict)]
        confirmed = [finding for finding in reported_findings
                     if finding.get("classification") == "confirmed-violation"]
        truth = [item for item in scenario.get("expectedFindings") or []
                 if item.get("kind") == "confirmed-violation"]
        if truth:
            matched = []
            false_positives = []
            for finding in confirmed:
                rule = str(finding.get("rule"))
                path = str(finding.get("path") or "")
                if any(item["rule"] == rule and _path_matches(path, item["path"]) for item in truth):
                    matched.append(finding)
                else:
                    false_positives.append(f"{rule}@{(path or 'no path')}")
            precision = len(matched) / len(confirmed) if confirmed else None
            recall = len(matched) / len(truth)
            metrics.append(_metric(
                "finding-precision", precision, "measured" if precision is not None else "unavailable",
                f"{len(matched)}/{len(confirmed)} reported confirmed violations match ground truth"
                if precision is not None else "no confirmed violations were reported, so precision is undefined",
            ))
            metrics.append(_metric(
                "finding-recall", recall, "measured",
                f"{len(matched)}/{len(truth)} recorded violations detected; "
                f"false positives: {', '.join(false_positives) or 'none'}",
            ))
            criteria.append(_criterion(
                "findings", "Reported violations match recorded ground truth",
                "pass" if not false_positives and len(matched) == len(truth)
                else "partial" if matched else "fail",
                f"precision {precision if precision is not None else 'n/a'}, recall {round(recall, 3)}",
                false_positives,
            ))
        else:
            metrics.append(_metric(
                "finding-precision", None, "unavailable",
                "the scenario records no confirmed-violation ground truth; precision is not estimated",
            ))
            metrics.append(_metric(
                "finding-recall", None, "unavailable",
                "the scenario records no confirmed-violation ground truth; recall is not estimated",
            ))
            indeterminate.append("finding precision and recall: no violation-level ground truth recorded")

        verified_paths = set((file_manifest or {}).keys())
        if not verified_paths:
            metrics.append(_metric("evidence-completeness", None, "unavailable",
                                   "the checkout manifest was not available"))
            indeterminate.append("evidence completeness: checkout manifest unavailable")
        elif reported_findings:
            supported = 0
            unsupported: list[str] = []
            for finding in reported_findings:
                references = [reference for reference in finding.get("evidence") or []
                              if isinstance(reference, str) and reference.strip()]
                if not references:
                    unsupported.append(f"{finding.get('rule')}: no evidence")
                    continue
                resolved = False
                for reference in references:
                    candidate = reference.strip().strip("`'\"")
                    candidate = candidate.split(" ")[0].split("#")[0]
                    if ":" in candidate and candidate.rsplit(":", 1)[-1].isdigit():
                        candidate = candidate.rsplit(":", 1)[0]
                    candidate = candidate.lstrip("./")
                    if candidate in verified_paths or any(
                            candidate == path or candidate.startswith(path + "/") for path in verified_paths):
                        resolved = True
                        break
                if resolved:
                    supported += 1
                else:
                    unsupported.append(f"{finding.get('rule')}: evidence does not resolve")
            metrics.append(_metric(
                "evidence-completeness", supported / len(reported_findings), "measured",
                f"{supported}/{len(reported_findings)} findings cite evidence that resolves in the checkout"
                + (f"; unsupported: {', '.join(unsupported[:5])}" if unsupported else ""),
            ))
            criteria.append(_criterion(
                "evidence", "Findings are supported by verifiable evidence",
                "pass" if supported == len(reported_findings) else "partial" if supported else "fail",
                f"{supported}/{len(reported_findings)} findings have resolving evidence",
            ))
        else:
            metrics.append(_metric("evidence-completeness", None, "unavailable",
                                   "no findings were reported, so there is no evidence to check"))

        expected_profiles = set(scenario.get("applicableProfiles") or [])
        reported_profiles = {str(profile) for profile in agent_output.get("profiles") or []}
        inapplicable = sorted(reported_profiles - expected_profiles)
        missing = sorted(expected_profiles - reported_profiles)
        if expected_profiles:
            if inapplicable:
                value = 0.0
            elif missing:
                value = (len(expected_profiles) - len(missing)) / len(expected_profiles)
            else:
                value = 1.0
            metrics.append(_metric(
                "profile-selection", value, "measured",
                f"reported {sorted(reported_profiles) or 'none'}; applicable {sorted(expected_profiles)}"
                + (f"; inapplicable: {', '.join(inapplicable)}" if inapplicable else "")
                + (f"; missing: {', '.join(missing)}" if missing else ""),
            ))
            criteria.append(_criterion(
                "profiles", "Only applicable ACIMA profiles were claimed",
                "pass" if not inapplicable and not missing else "fail",
                f"reported {sorted(reported_profiles) or 'none'}, applicable {sorted(expected_profiles)}",
            ))
        else:
            metrics.append(_metric("profile-selection", None, "unavailable",
                                   "the scenario records no applicable profiles"))

        acceptable_compatibility = set(scenario.get("acceptableCompatibility") or [])
        compatibility = agent_output.get("compatibility")
        if acceptable_compatibility:
            metrics.append(_metric("compatibility", None, "indeterminate",
                                   f"reported {compatibility}; reviewer reference set: {sorted(acceptable_compatibility)}. "
                                   "Requires qualitative review."))
            criteria.append(_criterion("compatibility", "Compatibility with the existing architecture was assessed accurately",
                                       "review", f"reported {compatibility}; compare rationale and repository evidence "
                                       f"with {sorted(acceptable_compatibility)}."))

        acceptable_recommendations = set(scenario.get("acceptableRecommendations") or [])
        recommendation = agent_output.get("recommendation")
        if acceptable_recommendations:
            metrics.append(_metric("recommendation", None, "indeterminate",
                                   f"reported {recommendation}; reviewer reference set: {sorted(acceptable_recommendations)}. "
                                   "Requires qualitative review."))
            criteria.append(_criterion("recommendation", "Recommendation is proportionate and supported by repository evidence",
                                       "review", f"reported {recommendation}; compare rationale with "
                                       f"{sorted(acceptable_recommendations)}."))

        changes_proposed = [change for change in agent_output.get("proposedChanges") or []
                            if isinstance(change, dict)]
        restructure = [change for change in changes_proposed if change.get("kind") == "restructure"]
        if scenario.get("expectedProposedChangeKinds") is not None:
            metrics.append(_metric("unnecessary-restructuring", None, "indeterminate",
                                   f"{len(restructure)} restructuring change(s) proposed; "
                                   f"{len(changes_proposed)} proposal(s) total. Necessity requires qualitative review.",
                                   unit="count"))
            criteria.append(_criterion("restructuring", "Recommendations are proportionate and do not impose unnecessary structure",
                                       "review", f"{len(restructure)} restructuring proposal(s); assess against "
                                       "the repository's actual ownership evidence.",
                                       [str(change.get("path")) for change in restructure]))
        else:
            metrics.append(_metric("unnecessary-restructuring", None, "unavailable",
                                   "the scenario records no expected change kinds"))

    # Every qualitative rubric item is explicitly held for review. These items cannot be
    # silently omitted merely because the evaluator has no deterministic proxy for them.
    for rubric_id, description in QUALITATIVE_RUBRIC_CRITERIA.items():
        detail = (
            "Requires two independent human reviewers to record the same decision; automated "
            "checks and model-generated judgements cannot resolve this criterion."
            if agent_output is not None else "No agent assessment exists to review."
        )
        if rubric_id.startswith("D8.") and agent_output is not None:
            ownership = agent_output.get("valueOwnership")
            if isinstance(ownership, dict):
                candidates = ownership.get("candidates") or []
                distinct = ownership.get("preservedDistinctValues") or []
                config = ownership.get("configurationDecisions") or []
                detail += (
                    f" Review the valueOwnership evidence: {len(candidates)} candidate record(s), "
                    f"{len(distinct)} preserved-distinction record(s), and {len(config)} configuration "
                    "decision(s). These counts are context only and are not scores. Trace each claim "
                    "to source evidence and independently assess semantic correctness."
                )
            else:
                detail += (
                    " Required valueOwnership analysis is missing or malformed; reviewers must "
                    "treat the criterion as unsupported rather than infer a pass from absent findings."
                )
        criteria.append(_criterion(
            rubric_id, description,
            "review" if agent_output is not None else "unavailable",
            detail,
        ))

    # Scope adherence is a deterministic fact, not a judgement.
    mode = execution["mode"]
    if mode == "read-only":
        changed = sorted(set(changes.get("added", [])) | set(changes.get("removed", []))
                         | set(changes.get("modified", [])))
        metrics.append(_metric(
            "scope-adherence", 0.0 if changed else 1.0, "measured",
            "no repository changes" if not changed else f"{len(changed)} unauthorized change(s): "
            + ", ".join(changed[:5]),
        ))
        criteria.append(_criterion(
            "scope", "Assessment respected the read-only boundary",
            "pass" if not changed else "fail",
            "repository unchanged" if not changed else "repository was modified during an assessment",
            changed,
        ))
    else:
        unauthorized = changes.get("unauthorized") or []
        metrics.append(_metric(
            "scope-adherence", 0.0 if unauthorized else 1.0, "measured",
            "all changes inside the approved scope" if not unauthorized
            else f"{len(unauthorized)} path(s) outside the approved scope",
        ))
        criteria.append(_criterion(
            "scope", "Authorized adoption stayed inside its approval",
            "pass" if not unauthorized else "fail",
            "approved scope respected" if not unauthorized else "unapproved changes were made",
            unauthorized,
        ))

    # Mode-dependent measurements are recorded honestly as unavailable in this milestone.
    verification = (execution.get("verification") or {}).get("commands") or []
    if mode == "authorized-adoption" and verification:
        baseline_passed = [command for command in verification if command.get("baselinePassed") is True]
        regressions = [command for command in baseline_passed if command.get("passed") is False]
        if baseline_passed:
            metrics.append(_metric(
                "regression-rate", len(regressions) / len(baseline_passed), "measured",
                f"{len(regressions)}/{len(baseline_passed)} baseline-passing command(s) now fail",
            ))
            criteria.append(_criterion(
                "regression", "Existing verification still passes",
                "fail" if regressions else "pass",
                f"{len(regressions)} regression(s) across {len(baseline_passed)} baseline command(s)",
            ))
        else:
            metrics.append(_metric(
                "regression-rate", None, "unavailable",
                "no verification command passed against the baseline, so a regression cannot be measured",
            ))
            indeterminate.append("regression rate: the baseline did not pass its verification commands")
        all_after_passed = all(command.get("passed") for command in verification)
        achieved = (not changes.get("unauthorized") and not regressions and all_after_passed)
        metrics.append(_metric(
            "adoption-effectiveness", 1.0 if achieved else 0.0, "measured",
            "approved scope implemented and every verification command passed" if achieved
            else "the implementation did not satisfy its approved scope or did not verify",
        ))
    else:
        metrics.append(_metric(
            "adoption-effectiveness", None, "unavailable",
            "no authorized adoption with verification commands was executed, so effectiveness was not measured",
        ))
        metrics.append(_metric(
            "regression-rate", None, "unavailable",
            "no authorized adoption or baseline verification was executed",
        ))
        indeterminate.append("adoption effectiveness and regression rate require an authorized-adoption run")

    metrics.append(_metric(
        "repeatability", None, "unavailable",
        "consistency requires repeated runs; use the compare command over at least two runs",
    ))
    indeterminate.append("repeatability is computed by comparison, not by a single run")

    duration = execution.get("agent", {}).get("durationSeconds")
    tokens = execution.get("agent", {}).get("tokenUsage")
    cost_detail = f"duration {duration if duration is not None else 'unknown'}s"
    if isinstance(tokens, dict) and tokens:
        cost_detail += ", tokens " + ", ".join(f"{key}={value}" for key, value in sorted(tokens.items()))
    else:
        cost_detail += "; the adapter reported no token usage"
    metrics.append(_metric("execution-cost", duration if isinstance(duration, (int, float)) else None,
                           "measured" if isinstance(duration, (int, float)) else "unavailable",
                           cost_detail, unit="seconds"))

    ambiguous = [finding for finding in (agent_output or {}).get("findings") or []
                 if isinstance(finding, dict) and finding.get("classification") == "suspected-violation"]
    failing = [criterion for criterion in criteria if criterion["status"] == "fail"]
    review_criteria = [criterion["id"] for criterion in criteria if criterion.get("status") == "review"]
    review_reasons = []
    if review_criteria:
        review_reasons.append("qualitative criteria require independent human review: " + ", ".join(review_criteria))
    if ambiguous:
        review_reasons.append(f"{len(ambiguous)} suspected violation(s) need human adjudication")
    if failing:
        review_reasons.append("a deterministic or ground-truth criterion failed")
    if any(metric["status"] == "indeterminate" for metric in metrics):
        review_reasons.append("at least one metric is indeterminate")

    criteria.append(_criterion(
        "consent", "Assessment and approval boundaries were respected",
        "pass" if not failing or all(item["id"] != "scope" for item in failing) else "fail",
        "consent boundary respected" if not any(item["id"] == "scope" for item in failing)
        else "consent boundary was crossed",
    ))

    if scenario.get("expectedFindings") is not None and not (scenario.get("expectedFindings") or []):
        limitations.append(
            "No violation-level ground truth exists for this scenario, so precision and recall are "
            "reported unavailable. This is a deliberate limitation, not a clean result."
        )
    limitations.append(
        "Ground truth was established by manual inspection of the pinned checkout; it is not blind and "
        "has not been independently reviewed in this milestone."
    )
    if not scenario.get("groundTruth", {}).get("independentReview"):
        limitations.append(
            "Scenario ground truth has not been independently reviewed "
            "(groundTruth.independentReview is false)."
        )

    return {
        "criteria": criteria,
        "metrics": metrics,
        "indeterminate": indeterminate,
        "humanReview": {
            "required": bool(review_reasons),
            "status": "pending" if review_reasons else "not-required",
            "reason": "; ".join(review_reasons) if review_reasons else "no qualitative criteria require review",
            "criteria": review_criteria,
            "minimumIndependentReviewers": 2 if review_criteria else 0,
            "reviewers": [],
            "agreementRequired": bool(review_criteria),
            "additionalReviewRequired": bool(ambiguous),
            "additionalReviewReason": (
                f"{len(ambiguous)} suspected violation(s) need finding-level adjudication"
                if ambiguous else None
            ),
            "reviewedBy": None,
            "reviewedOn": None,
            "notes": None,
        },
        "limitations": limitations,
        "deterministic": deterministic,
    }


def adjudicate_qualitative_review(evaluation: dict, decisions: dict[str, list[dict]]) -> dict:
    """Resolve qualitative criteria only when two distinct reviewers agree."""
    import copy

    result = copy.deepcopy(evaluation)
    criteria = {item["id"]: item for item in result.get("criteria", [])}
    unresolved = []
    recorded = {}
    previous_reviewers = dict(result.get("humanReview", {}).get("reviewers") or {})
    for criterion_id in result.get("humanReview", {}).get("criteria", []):
        if criterion_id not in criteria or criteria[criterion_id].get("status") != "review":
            continue
        entries = decisions.get(criterion_id) or []
        reviewers = {str(item.get("reviewer", "")).strip() for item in entries}
        choices = {str(item.get("decision", "")).strip().lower() for item in entries}
        if len(reviewers) < 2 or "" in reviewers or len(choices) != 1 or not choices.issubset({"pass", "fail", "unavailable"}):
            unresolved.append(criterion_id)
            continue
        if criterion_id not in criteria:
            unresolved.append(criterion_id)
            continue
        decision = next(iter(choices))
        criteria[criterion_id]["status"] = decision
        criteria[criterion_id]["detail"] += (
            f" Independent reviewers agreed: {', '.join(sorted(reviewers))} => {decision}."
        )
        recorded[criterion_id] = sorted(reviewers)

    previous_reviewers.update(recorded)
    result["humanReview"]["reviewers"] = previous_reviewers
    result["humanReview"]["criteria"] = unresolved
    result["humanReview"]["unresolvedCriteria"] = unresolved
    additional_required = bool(result["humanReview"].get("additionalReviewRequired"))
    result["humanReview"]["status"] = "pending" if unresolved or additional_required else "complete"
    result["humanReview"]["required"] = bool(unresolved) or additional_required
    reasons = []
    if unresolved:
        reasons.append("qualitative review remains pending for: " + ", ".join(unresolved))
    if additional_required:
        reasons.append(result["humanReview"].get("additionalReviewReason") or "additional finding-level review remains pending")
    result["humanReview"]["reason"] = (
        "; ".join(reasons) if reasons else
        "all qualitative criteria have agreeing decisions from two independent reviewers"
    )
    result["humanReview"]["reviewedBy"] = sorted({
        reviewer for names in previous_reviewers.values() for reviewer in names
    }) if previous_reviewers else None
    return result
