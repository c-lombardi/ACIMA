"""Decision-ready HTML proposal reports for guided and automated ACIMA adoption.

The report is generated from the same pinned catalog and qualitative-review evidence
as the adoption workflow. It is stored outside the target repository until the owner
explicitly approves report/document files as part of the implementation scope.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "conformance"))
from qualitative_review import validate_review  # noqa: E402


class AdoptionReportError(RuntimeError):
    """The proposal report could not be rendered and validated."""


def _skill_root() -> Path:
    if (ROOT / "skills" / "acima-adoption" / "scripts" / "render_report.py").is_file():
        return ROOT / "skills" / "acima-adoption"
    candidate = ROOT.parent
    if (candidate / "scripts" / "render_report.py").is_file() and (candidate / "assets" / "report.schema.json").is_file():
        return candidate
    raise AdoptionReportError("the adoption skill HTML renderer or report assets are missing")


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AdoptionReportError("cannot load required ACIMA module: %s" % path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def report_digest(directory: Path) -> str:
    """Hash every user-visible report file, including the CSS and source data model."""
    if not directory.is_dir():
        raise AdoptionReportError("the proposal report directory is missing")
    digest = hashlib.sha256()
    files = sorted(path for path in directory.rglob("*") if path.is_file())
    if not files:
        raise AdoptionReportError("the proposal report directory is empty")
    for path in files:
        relative = path.relative_to(directory).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _file_change(path: str, action: str, purpose: str, outcome: str,
                 classification: str = "owner-decision", approval: str = "Not approved") -> dict:
    return {
        "path": path,
        "action": action,
        "purpose": purpose,
        "expectedOutcome": outcome,
        "classification": classification,
        "approval": approval,
        "status": "proposed",
    }


def _human_review(review: dict, catalog: dict) -> list[dict]:
    rules_by_id = {item["id"]: item for item in catalog.get("rules", [])}
    disposition_map = {
        "conforms": "conforms",
        "gap": "does-not-conform",
        "not_applicable": "not-applicable",
        "insufficient_evidence": "unverified",
    }
    result = []
    for item in review.get("rules", []):
        rule = rules_by_id[item["rule"]]
        evidence_refs = []
        for evidence in item.get("evidence", []):
            path = evidence.get("path")
            if evidence.get("kind") == "absence":
                ref = path
            else:
                ref = "%s:%s-%s" % (
                    path, evidence.get("startLine"), evidence.get("endLine")
                )
            if ref not in evidence_refs:
                evidence_refs.append(ref)
        result.append({
            "rule": item["rule"],
            "requirement": rule["title"],
            "meaning": rule["summary"],
            "disposition": disposition_map[item["status"]],
            "rationale": item["rationale"],
            "evidenceRefs": evidence_refs,
        })
    return result


def _phase(name: str, purpose: str, deliverable: str, verification: str,
           approval: str, status: str, completion: str,
           affected: list[str] | None = None, prerequisites: str = "") -> dict:
    return {
        "name": name,
        "purpose": purpose,
        "deliverable": deliverable,
        "verification": verification,
        "approval": approval,
        "status": status,
        "completionCriteria": completion,
        "affectedFiles": affected or [],
        "prerequisites": prerequisites,
        "activities": [],
    }


def _finding_records(review_validation: dict, catalog: dict) -> list[dict]:
    """Project reviewed requirement gaps into human-readable findings.

    One finding is emitted per nonconforming requirement. The qualitative review
    does not claim semantic clustering across unrelated requirements.
    """
    rules_by_id = {item["id"]: item for item in catalog.get("rules", [])}
    findings = []
    for item in review_validation.get("rules", []):
        if item.get("status") != "gap":
            continue
        rule = rules_by_id.get(item.get("rule"))
        if not rule:
            raise AdoptionReportError(
                "qualitative gap references a rule missing from the current catalog: %s"
                % item.get("rule")
            )
        evidence = item.get("evidence") or []
        paths = sorted({str(ref["path"]) for ref in evidence if ref.get("path")})
        refs = []
        for ref in evidence:
            path = ref.get("path")
            if not path:
                continue
            if ref.get("kind") == "absence":
                value = str(path)
            else:
                value = "%s:%s-%s" % (
                    path, ref.get("startLine"), ref.get("endLine")
                )
            if value not in refs:
                refs.append(value)
        severity = rule.get("severity")
        classification = {
            "error": "required", "warning": "recommended", "info": "optional"
        }.get(severity, "owner-decision")
        automated = rule.get("automation") == "automated"
        verification = (
            "After the owner approves the relevant enforcement stage, run the supported "
            "language enforcer against a known-compliant fixture and a controlled violation. "
            "The qualitative review itself is not an automated test."
            if automated else
            "This requirement needs evidence-backed human review in the applicable design, "
            "runtime or operational context. A clean static scan cannot establish it."
        )
        findings.append({
            "title": rule["title"],
            "what": item.get("rationale") or "The qualitative reviewer recorded a gap.",
            "why": rule["summary"],
            "rule": rule["id"],
            "requirementRefs": [rule["id"]],
            "paths": paths,
            "status": "Reviewed gap",
            "confidence": "Evidence-backed qualitative judgement; not a deterministic proof.",
            "recommendation": rule.get("fix") or "Review the requirement and select an owner-approved correction.",
            "classification": classification,
            "disposition": "does-not-conform",
            "requirementMeaning": rule["summary"],
            "expectedOutcome": rule.get("fix") or "The implementation satisfies the stated requirement.",
            "verification": verification,
            "limitations": (
                "The finding is based on the recorded reviewer interpretation and cited evidence. "
                "The evidence validator proves provenance, not semantic correctness."
            ),
            "evidenceRefs": refs,
        })
    return findings


def _benefit_records(assessment_result: dict) -> tuple[list[dict], list[dict]]:
    """Create benefit and outcome projections without claiming future outcomes are realized."""
    details = assessment_result.get("benefitDetails") or []
    benefits = []
    outcomes = []
    class_map = {
        "available-today": ("optional", "not-established", "Available today"),
        "achievable-through-adoption": ("recommended", "implementation-dependent", "Achievable through adoption"),
        "requires-additional-work": ("required", "implementation-dependent", "Requires additional work"),
        "not-applicable": ("optional", "not-established", "Not applicable to the observed architecture"),
    }
    for index, item in enumerate(details, 1):
        if not isinstance(item, dict) or not item.get("benefit"):
            continue
        benefit = str(item["benefit"])
        classification, realization, availability = class_map.get(
            item.get("classification"), ("owner-decision", "not-established", "Not established")
        )
        basis = str(item.get("basis") or "The assessment did not record a specific basis.")
        implementation = (
            "Already available in the assessed repository or its current tooling; this is not "
            "a claim that ACIMA adoption changes it."
            if item.get("classification") == "available-today" else
            "This capability depends on the owner approving and completing the relevant adoption work."
        )
        verification = (
            "The assessment identified this capability from existing repository evidence. "
            "It has not been independently validated as a production outcome."
            if item.get("classification") == "available-today" else
            "Not yet realized or verified. After approved implementation, validate the behavior "
            "with the stated positive and negative checks and observe the relevant workflow."
        )
        benefits.append({
            "title": benefit,
            "description": benefit,
            "availability": availability,
            "whyItMatters": basis,
            "practicalChange": implementation,
            "implementation": implementation,
            "classification": classification,
            "realization": realization,
            "verification": verification,
            "limitations": "Assessment benefit classification is not evidence of a realized business outcome.",
        })
        outcomes.append({
            "title": benefit,
            "description": benefit,
            "whyItMatters": basis,
            "practicalChange": implementation,
            "classification": classification,
            "realization": realization,
            "verification": verification,
            "limitations": "No post-implementation outcome has been measured in this assessment.",
            "status": availability,
        })
    return benefits, outcomes


def build_report_model(root: Path, review_path: Path, module_map: dict,
                       proposal: dict, state: dict) -> dict:
    """Build and independently validate the schema 1.1 report model."""
    root = root.resolve()
    skill = _skill_root()
    catalog_path = ROOT / "tools" / "acima-spec" / "rules.json"
    if not catalog_path.is_file():
        raise AdoptionReportError("the pinned ACIMA rule catalog is unavailable")
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog_sha = _sha(catalog_path)
    review_document = json.loads(review_path.read_text(encoding="utf-8"))
    review_validation = validate_review(review_document, root, catalog, catalog_sha)
    required_rules = len(catalog.get("rules", []))
    if (not review_validation.get("decisionComplete")
            or review_validation.get("reviewed") != required_rules
            or review_validation.get("required") != required_rules):
        raise AdoptionReportError(
            "the proposal report requires %s valid, decision-complete qualitative reviews" % required_rules
        )

    cli = _load_module(ROOT / "tools" / "acima.py", "acima_adoption_assessment_cli")
    _code, assessment = cli.assess_project(root, review_path=review_path)
    assessment_result = assessment.get("assessmentResult") or {}
    recommendation = assessment_result.get("fit") or "INSUFFICIENT_EVIDENCE"
    if recommendation not in {
        "RECOMMENDED", "RECOMMENDED_WITH_LIMITATIONS", "NOT_RECOMMENDED",
        "INSUFFICIENT_EVIDENCE", "NOT_SUPPORTED",
    }:
        recommendation = "INSUFFICIENT_EVIDENCE"
    recommendation_summary = assessment_result.get("recommendation") or (
        "The repository-specific adoption recommendation is not established by the available assessment."
    )

    mapping = module_map or assessment.get("moduleMap") or {}
    authoritative = mapping.get("authoritativeMap") or {
        "present": False,
        "status": "absent",
        "summary": "No approved module map is available yet.",
        "unitCount": 0,
        "coveredProduction": 0,
        "productionFiles": assessment.get("sourceFiles", 0),
        "issues": [],
        "unownedPaths": [],
    }
    if "present" not in authoritative:
        authoritative = {**authoritative, "present": authoritative.get("status") == "complete"}
    if not authoritative.get("status"):
        authoritative["status"] = "unknown"
    module_proposal = mapping.get("proposal")
    existing_architecture = mapping.get("existingArchitecture") or (
        module_proposal.get("existingArchitecture") if isinstance(module_proposal, dict) else {}
    ) or {}
    map_section = {
        "status": mapping.get("status") or ("proposed" if module_proposal else authoritative.get("status")),
        "proposalId": mapping.get("proposalId"),
        "summary": mapping.get("summary") or "The module map is shown with observed evidence and unresolved ownership decisions.",
        "nextDecision": mapping.get("nextDecision") or "Review the module boundaries before approving any implementation.",
        "authoritativeMap": authoritative,
        "authoritativeUnits": authoritative.get("units") or [],
        "proposal": module_proposal,
        "review": mapping.get("review"),
        "existingArchitecture": existing_architecture,
        "quality": mapping.get("quality") or {},
    }

    conformance = _human_review(review_validation, catalog)
    counts = review_validation["counts"]
    coverage = {
        "requiredRules": review_validation["required"],
        "reviewedRules": review_validation["reviewed"],
        "pendingRules": review_validation["pending"],
        "unresolvedRules": review_validation["unresolved"],
        "automatedChecksRun": 0,
        "manualReviewsCompleted": review_validation["reviewed"],
        "skippedOrUnsupported": 0,
        "qualitativeReviewsOutstanding": review_validation["pending"],
        "dispositionCounts": {
            "conforms": counts["conforms"],
            "doesNotConform": counts["gap"],
            "partiallyConforms": 0,
            "notApplicable": counts["not_applicable"],
            "unverified": counts["insufficient_evidence"],
            "notAssessed": 0,
            "unsupported": 0,
            "blocked": 0,
        },
    }

    create_changes = []
    preserve_changes = []
    for item in (proposal.get("implementationImpact") or {}).get("create", []):
        if not isinstance(item, dict) or not item.get("path"):
            continue
        action = "no-change" if item.get("action") == "preserve" else "create"
        destination = preserve_changes if action == "no-change" else create_changes
        destination.append(_file_change(
            str(item["path"]), action, item.get("purpose") or "Create or preserve an ACIMA adoption artifact.",
            item.get("expectedOutcome") or "The approved adoption capability becomes available.",
            "required" if item.get("status") == "required" else "owner-decision",
            "Preserve" if action == "no-change" else "Not approved",
        ))
    modify_changes = []
    for item in (proposal.get("implementationImpact") or {}).get("modify", []):
        if not isinstance(item, dict) or not item.get("path"):
            continue
        modify_changes.append(_file_change(
            str(item["path"]), "modify", item.get("purpose") or "Modify a target file.",
            item.get("expectedOutcome") or "The approved behavior is established.",
            "owner-decision",
        ))

    inspect_paths = set()
    for item in review_document.get("rules", []):
        for evidence in item.get("evidence", []):
            if evidence.get("path"):
                inspect_paths.add(str(evidence["path"]))
    for module in (module_proposal or {}).get("modules", []):
        for evidence in module.get("evidence", []):
            if evidence.get("path"):
                inspect_paths.add(str(evidence["path"]))
        for collection in ("contracts", "implementation"):
            for path in ((module.get(collection) or {}).get("paths") or []):
                inspect_paths.add(str(path))
    for path in (existing_architecture.get("paths") or []):
        if path:
            inspect_paths.add(str(path))
    for path in (existing_architecture.get("solutions") or []):
        if path:
            inspect_paths.add(str(path))
    for path in (existing_architecture.get("dotnetProjects") or []):
        if path:
            inspect_paths.add(str(path))
    preserve_text = (proposal.get("implementationImpact") or {}).get("preserve") or []
    preserve_candidates = []
    if isinstance(existing_architecture, dict):
        preserve_candidates = (
            existing_architecture.get("files", [])
            or existing_architecture.get("artifacts", [])
            or existing_architecture.get("paths", [])
        )
    preserved_paths = {
        str(entry.get("path") if isinstance(entry, dict) else entry)
        for entry in preserve_candidates if (entry.get("path") if isinstance(entry, dict) else entry)
    }
    inspect_changes = [
        _file_change(path, "inspect", "Inspected as repository evidence; inspection does not propose a modification.",
                     "The assessment is traceable to the actual repository file.", "required", "Inspected")
        for path in sorted(inspect_paths - preserved_paths)
    ]
    for entry in preserve_candidates:
        path = entry.get("path") if isinstance(entry, dict) else str(entry)
        if path:
            preserve_changes.append(_file_change(
                path, "no-change", "Preserve existing architecture or enforcement that already serves this purpose.",
                "Existing repository behavior remains intact.", "required", "Preserve",
            ))

    proposed_changes = [
        {**item, "status": "proposed"}
        for item in create_changes + modify_changes
    ]
    decisions = []
    for item in (module_proposal or {}).get("decisions", []):
        if not isinstance(item, dict):
            continue
        decisions.append({
            "question": item.get("question") or "Confirm module ownership",
            "context": item.get("context") or "Repository evidence does not establish this ownership decision.",
            "recommendation": item.get("recommendation") or "Review the observed evidence and choose an owner-approved boundary.",
            "impact": item.get("impact") or item.get("blockedWork") or "Implementation depending on this decision remains blocked.",
            "whyOwner": "Only the repository owner can confirm intended responsibility and compatibility boundaries.",
            "alternatives": item.get("options") or [],
            "blockedWork": item.get("blockedWork") or "Ownership-dependent implementation and checks.",
            "requiredBeforeImplementation": bool(item.get("essential", True)),
        })

    phases = [
        _phase("Assess the repository", "Understand the actual architecture and assess every ACIMA requirement.",
               "A complete evidence-backed review of all %s catalog requirements." % len(catalog.get("rules", [])),
               "The pinned catalog validator confirms %s valid dispositions." % len(catalog.get("rules", [])),
               "No implementation approval required.", "Complete",
               "Every requirement has a valid, individually reasoned disposition.",
               [review_path.relative_to(root).as_posix()]),
        _phase("Review module ownership", "Confirm module responsibilities and contract/implementation paths.",
               "An owner-approved authoritative module map.",
               "The map review records a decision for each boundary and path disposition.",
               "Explicit owner approval required.", "Awaiting review" if authoritative.get("status") != "complete" else "Complete",
               "All material ownership decisions are resolved.",
               [".acima/module-map.proposal.json"] if module_proposal else [],
               "The qualitative assessment is complete."),
        _phase("Review the HTML adoption proposal", "Understand what ACIMA would add, preserve, and change.",
               "The six-page HTML report, including proposal, file impact, plan, and evidence.",
               "All six pages and the report data render and pass schema/evidence validation.",
               "The owner must inspect the HTML report and explicitly approve its exact digest.", "Awaiting review",
               "A report-review receipt identifies the exact report digest, reviewer, and date.",
               ["proposal.html", "files.html", "plan.html", "evidence.html"]),
        _phase("Review CI integration", "Decide whether the existing CI provider should enforce the architecture checks.",
               "A provider-specific CI integration proposal.",
               "The configured command, workflow path, triggers, and local validation are inspected.",
               "Separate CI approval required.", "Awaiting decision",
               "The owner explicitly approves, defers, or declines CI integration.",
               [".github/workflows/acima.yml"]),
        _phase("Select implementation stages", "Select exactly which proposed changes ACIMA may apply.",
               "A scope record with approved objectives and explicit target paths.",
               "The approval matches the report, proposal digest, and unchanged assessed repository revision.",
               "Separate explicit implementation approval required.", "Awaiting decision",
               "Every implementation path is listed and authorized before the first target write."),
    ]

    decisions.append({
        "question": "Which ACIMA adoption changes do you explicitly authorize?",
        "context": "Reviewing the map or HTML report only acknowledges the proposal. It does not authorize enforcement, changing future AI-agent instructions, CI integration, or modifying application source. Each change must be selected explicitly, and the exact files must be listed in the approval record.",
        "recommendation": "Select only the capabilities you want ACIMA to implement now. Defer or decline everything else; you can authorize additional stages later.",
        "impact": "ACIMA will modify only the paths listed in the approved scope. Source remediation is a later, separate decision tied to a specific remediation-plan digest and exact source files.",
        "whyOwner": "Only the repository owner can decide whether to adopt these changes now, how much disruption is acceptable, and which future agent behavior or CI policy should change.",
        "alternatives": [
            "Install or extend local architecture enforcement and its automated tests.",
            "Create the initial waiver/baseline record required by the selected enforcement setup.",
            "Integrate the existing CI provider, with the workflow and trigger reviewed separately.",
            "Update repository AI-agent instructions, preserving existing user-authored guidance; this is separate from adoption notifications.",
            "Apply selected application-source remediation recommendations after a second review of the remediation plan.",
            "Defer all implementation and retain the assessment and proposal only.",
        ],
        "blockedWork": "Any unselected stage remains unimplemented. In particular, no source file, CI workflow, or AI-agent instruction is changed merely because the user reviewed the report or chose a recovery branch.",
        "requiredBeforeImplementation": True,
    })

    decisions.append({
        "id": "adoption-notifications",
        "question": "Should ACIMA prepare a separate implementation proposal for user-facing adoption notifications?",
        "context": "This is distinct from application-domain notifications and from editing AGENTS.md/CLAUDE.md. It would cover clear user-facing notices for adoption milestones, module-map decisions, report reviews, CI decisions, implementation starts/completions, blockers, remediation decisions, and final verification. No notification provider, external channel, or product source file is assumed.",
        "recommendation": "Choose whether ACIMA should prepare a repository-grounded proposal describing events, delivery surface, affected files, user controls, privacy implications, retry/duplication behavior, and tests. Preparing the proposal is not permission to implement its recommendations.",
        "impact": "Selecting 'approved' authorizes only the proposal document. Any notification source code, external integration, UI, persistence or product configuration requires a second review and exact file-scoped approval.",
        "whyOwner": "The owner must decide whether adoption notices should exist, which audiences and channels are appropriate, and whether the feature belongs in the target product or only in the interactive agent experience.",
        "alternatives": [
            "Prepare a separate notification implementation proposal for review (proposal only).",
            "Use only the current interactive adoption messages; do not add a target-product notification feature.",
            "Defer the decision until core ACIMA adoption is verified.",
            "Decline adoption notifications."
        ],
        "blockedWork": "No notification source code, provider, webhook, email, push channel, UI component, persistence or configuration is changed by reviewing this report or approving local enforcement.",
        "requiredBeforeImplementation": True,
        "status": "awaiting_owner_decision",
    })

    repo_name = root.name or str(root)
    revision_record = (state.get("repository") or {}).get("revision") or {}
    if isinstance(revision_record, dict):
        revision = revision_record.get("head") or cli._git_head(root)
        branch = revision_record.get("branch")
        working_tree_digest = revision_record.get("workingTree")
    else:
        revision = cli._git_head(root)
        branch = None
        working_tree_digest = None
    repo_mode = (proposal.get("maturity") or {}).get("mode") or "unknown"
    if repo_mode not in {"greenfield", "brownfield", "mixed", "unknown"}:
        repo_mode = "unknown"
    inferences = assessment_result.get("inferences") or []
    architecture_family = "; ".join(str(item.get("candidate")) for item in inferences if isinstance(item, dict)) or "Not established from the available evidence"
    summary = (
        "The %s-rule qualitative review is complete. The proposed module ownership and adoption changes remain subject to the review gates shown in this report." % len(catalog.get("rules", []))
    )
    overview = {
        "summary": summary,
        "plainLanguage": summary,
        "nextAction": "Review the proposed module map and the HTML adoption proposal.",
        "nextActionWhy": "The report must be inspected and its exact version explicitly approved before ACIMA applies enforcement, CI, agent-guidance, or source changes.",
    }
    findings = _finding_records(review_validation, catalog)
    benefits, outcomes = _benefit_records(assessment_result)
    existing_enforcement = assessment_result.get("existingEnforcement") or {}
    target_capabilities = []
    level_guidance = assessment_result.get("levelGuidance") or {}
    for key, label in (
        ("establishes", "What the selected ACIMA level establishes"),
        ("checks", "What the selected ACIMA level checks"),
        ("requires", "Prerequisites for the selected ACIMA level"),
        ("doesNotProve", "What the selected ACIMA level does not prove"),
    ):
        value = level_guidance.get(key)
        if value:
            target_capabilities.append({
                "capability": label, "change": str(value),
                "outcome": "This describes the standard's intended guarantee, not an implementation result.",
            })
    for mechanism in existing_enforcement.get("mechanisms") or []:
        if isinstance(mechanism, dict):
            description = mechanism.get("path") or mechanism.get("name") or mechanism.get("kind")
            if description:
                target_capabilities.append({
                    "capability": "Existing architecture enforcement",
                    "change": str(description),
                    "outcome": mechanism.get("purpose") or mechanism.get("status") or
                               "Existing mechanism identified by read-only assessment.",
                })

    current_state_parts = []
    if existing_architecture.get("paths"):
        current_state_parts.append(
            "Existing architecture and enforcement assets: " +
            ", ".join(str(path) for path in existing_architecture.get("paths", []))
        )
    if existing_enforcement.get("summary"):
        current_state_parts.append(str(existing_enforcement["summary"]))
    if proposal.get("summary"):
        current_state_parts.append(str(proposal["summary"]))
    current_state = " ".join(current_state_parts) or (
        "Current architecture was inspected; see the ownership, findings and evidence sections."
    )
    preserved_assets = sorted({
        str(path) for path in (
            (existing_architecture.get("paths") or [])
            + (existing_architecture.get("solutions") or [])
            + (existing_architecture.get("dotnetProjects") or [])
        ) if path
    })
    preservation = list(preserve_text) if isinstance(preserve_text, list) else []
    if existing_architecture.get("note"):
        preservation.append(str(existing_architecture["note"]))
    if preserved_assets:
        preservation.append(
            "Existing architecture assets are inspected and preserved by default: " +
            ", ".join(preserved_assets) + ". They are not replaced merely to introduce ACIMA."
        )

    workflow_stages = []
    for name, stage in (state.get("stages") or {}).items():
        if isinstance(stage, dict):
            workflow_stages.append({
                "name": name, "label": stage.get("label") or name,
                "status": stage.get("status"), "detail": stage.get("detail"),
                "nextAction": stage.get("nextAction") or "",
            })

    model = {
        "schemaVersion": "1.1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "skillVersion": json.loads((skill / "manifest.json").read_text(encoding="utf-8"))["skillVersion"],
        "standardVersion": json.loads((skill / "manifest.json").read_text(encoding="utf-8"))["standard"],
        "catalogSha256": catalog_sha,
        "qualitativeReview": review_document,
        "assessmentSummary": {
            "benefitDetails": assessment_result.get("benefitDetails") or [],
            "existingEnforcement": existing_enforcement,
            "dimensions": assessment_result.get("dimensions") or {},
            "sourceFiles": assessment.get("sourceFiles", 0),
            "language": assessment.get("language"),
        },
        "assessmentStatus": "Qualitative review complete; module ownership and implementation review are pending.",
        "milestones": {
            "assessmentComplete": True,
            "reportGenerationComplete": True,
            "adoptionProposalComplete": True,
            "implementationComplete": False,
            "conformanceVerified": False,
        },
        "repository": {
            "name": repo_name, "path": str(root),
            **({"commit": revision} if revision else {}),
            **({"branch": branch} if branch else {}),
            **({"workingTreeDigest": working_tree_digest} if working_tree_digest else {}),
            "mode": repo_mode,
        },
        "recommendation": {
            "status": recommendation,
            "summary": recommendation_summary,
            "reasons": [assessment_result.get("why") or summary],
            "caveats": assessment_result.get("whatItWillNotSolve") or [
                "A complete qualitative review is not a conformance claim.",
                "No implementation has been authorized or performed.",
            ],
        },
        "overview": overview,
        "value": {
            "benefits": benefits,
            "adds": [item["capability"] for item in target_capabilities],
            "costs": ["Ongoing maintenance of the approved architecture map and checks."],
            "risks": (proposal.get("risks") or []),
        },
        "architecture": {
            "family": architecture_family,
            "currentState": current_state,
            "proposedState": "Preserve sound existing architecture and add only the missing, owner-approved ownership, enforcement, guidance and CI capabilities.",
            "targetCapabilities": target_capabilities,
            "existingEnforcement": existing_enforcement,
            "existingArchitecture": existing_architecture,
        },
        "coverage": coverage,
        "conformance": conformance,
        "strengths": list(dict.fromkeys(
            (proposal.get("existingStrengths") or [])
            + [item["benefit"] for item in (assessment_result.get("benefitDetails") or [])
               if item.get("classification") == "available-today"]
            + ([existing_enforcement.get("summary")] if existing_enforcement.get("status") not in (None, "none")
               and existing_enforcement.get("summary") else [])
        )),
        "findings": findings,
        "proposedChanges": proposed_changes,
        "outcomes": outcomes,
        "outcomesStatus": (
            "Potential outcomes are derived from the assessment's benefit analysis. They are not realized or verified until the owner approves the relevant work and post-implementation checks confirm them."
            if outcomes else
            "The assessment did not establish a distinct adoption outcome beyond the recorded requirement findings; no business benefit is inferred."
        ),
        "decisions": decisions,
        "decisionsStatus": "The report identifies decisions requiring the repository owner's review. No decision is inferred from a branch selection.",
        "fileImpact": {"inspect": inspect_changes, "create": create_changes,
                       "modify": modify_changes, "preserve": preserve_changes},
        "fileImpactStatus": "Inspection paths are evidence only. Create/modify paths remain proposed and are not authorized.",
        "roadmap": {"status": "Proposed; implementation is blocked pending explicit owner selection.",
                    "phases": phases},
        "roadmapStatus": "The implementation roadmap is a proposal, not an execution order until the owner approves its exact scope.",
        "phases": phases,
        "preservation": list(dict.fromkeys(preservation)),
        "preservationStatus": (
            "Existing architecture assets are listed from repository evidence. Preserve them unless an explicit, reviewed change is justified and approved."
            if preservation else
            "No specific preservation inventory was established; do not infer that existing architecture can be discarded."
        ),
        "outOfScope": ["No branch creation or switching is authorized by this report.",
                       "No source modification, build change, dependency change, CI change, commit, push, release, or deployment is authorized by report review alone."],
        "limitations": [
            "The assessment and proposal do not guarantee architectural conformance.",
            "The report's existence or being opened is not implementation consent.",
            "CI integration and source remediation require their own explicit decisions.",
        ],
        "approvalStatement": "To authorize implementation, approve the exact report digest, select objectives, and list every target path that may be created or modified. Branch selection is not implementation authorization.",
        "moduleMap": map_section,
        "ownershipGate": assessment.get("ownershipGate") or {
            "status": "blocked", "reason": "An approved map is required for ownership-dependent checks.",
            "ownershipDependentRules": [], "independentReviewContinues": True,
            "deterministicChecksBlocked": True, "proposalReviewRequired": True,
        },
        "adoptionWorkflow": {"mode": state.get("mode", "guided"), "authorized": False,
                             "repositoryRevision": revision_record,
                             "stages": workflow_stages, "next": state.get("next", {})},
    }

    renderer = _load_module(skill / "scripts" / "render_report.py", "acima_adoption_html_renderer")
    problems = renderer.validate(model)
    if problems:
        raise AdoptionReportError("report model rejected by the HTML renderer:\n- " + "\n- ".join(problems))
    return model


def render_proposal_report(root: Path, review_path: Path, module_map: dict,
                           proposal: dict, state: dict) -> dict:
    """Generate a six-page report outside the target and return its reviewable identity."""
    root = root.resolve()
    skill = _skill_root()
    renderer_path = skill / "scripts" / "render_report.py"
    model = build_report_model(root, review_path, module_map, proposal, state)
    report_id = hashlib.sha256(
        (str(root) + "|" + str(state.get("startedAt")) + "|" +
         str(module_map.get("proposalId")) + "|" + str(proposal.get("generatedAt"))).encode("utf-8")
    ).hexdigest()[:20]
    output = Path(tempfile.gettempdir()) / "acima-adoption-reports" / (root.name + "-" + report_id)
    if output.exists():
        raise AdoptionReportError("report output already exists; refusing to overwrite %s" % output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as stream:
        model_path = Path(stream.name)
        json.dump(model, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    try:
        result = subprocess.run(
            [sys.executable, str(renderer_path), "--input", str(model_path),
             "--out-dir", str(output)],
            capture_output=True, text=True, timeout=120,
        )
    finally:
        model_path.unlink(missing_ok=True)
    if result.returncode != 0:
        raise AdoptionReportError(result.stderr.strip() or result.stdout.strip() or "HTML renderer failed")
    expected = ["index.html", "proposal.html", "findings.html", "files.html",
                "plan.html", "evidence.html", "report-data.json", "assets/report.css"]
    missing = [name for name in expected if not (output / name).is_file()]
    if missing:
        raise AdoptionReportError("HTML renderer returned without all required pages/assets: %s" % ", ".join(missing))
    digest = report_digest(output)
    return {
        "status": "awaiting_review",
        "reportId": report_id,
        "directory": str(output),
        "indexHtml": str(output / "index.html"),
        "proposalHtml": str(output / "proposal.html"),
        "pages": {name: str(output / name) for name in expected if name.endswith(".html")},
        "sha256": digest,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "rendererOutput": result.stdout.strip(),
    }
