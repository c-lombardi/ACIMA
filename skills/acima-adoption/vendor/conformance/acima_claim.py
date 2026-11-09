"""Executable ACIMA conformance claim model.

The standard distinguishes two claim classes:

* ``FULL CONFORMANCE`` -- every rule required by the declared level was either
  executed by the run through its designated enforcement mechanism or covered
  by an accepted, current, repository-scoped manual evidence entry, and the run
  has no unwaived error findings.  A run that reports a catalog-manual rule as
  ``executed: true`` does not satisfy the rule: manual rules are only ever
  satisfied by evidence.
* ``PARTIAL ASSESSMENT`` -- the run is useful, but at least one required rule
  was not executed and has no accepted manual evidence.  It is not a
  conformance claim and must never be labelled as one.

This module is deliberately deterministic and dependency-free.  It consumes the
JSON run produced by an enforcer, the catalog, and an optional manual evidence
document.  It does not re-run analysis.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

FULL = "FULL CONFORMANCE"
PARTIAL = "PARTIAL ASSESSMENT"
INVALID = "INVALID ASSESSMENT"
LEVELS = ("L1", "L2", "L3")
LEVEL_INDEX = {"L1": 1, "L2": 2, "L3": 3}
EVIDENCE_FILE = ".acima/manual-evidence.json"
EVIDENCE_FIELDS = (
    "rule",
    "scope",
    "owner",
    "reviewer",
    "method",
    "artifact",
    "reviewedOn",
    "expires",
    "result",
)
FULL_SCOPE = "repository"
PASS_RESULT = "pass"


class ClaimError(Exception):
    """The run or the evidence document cannot support any claim."""


def load_catalog(root: Path) -> dict:
    path = root / "tools/acima-spec/rules.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ClaimError(f"cannot read catalog {path}: {error}") from error


def required_rules(catalog: dict, level: str) -> list[dict]:
    """Return every rule required at ``level``, including lower levels."""
    if level not in LEVELS:
        raise ClaimError(f"unknown level {level!r}; expected L1, L2 or L3")
    ceiling = LEVEL_INDEX[level]
    return [
        rule for rule in catalog.get("rules", [])
        if LEVEL_INDEX.get(rule.get("level"), 99) <= ceiling
    ]


def load_evidence(path: Path) -> list[dict]:
    """Read a manual evidence document.

    A missing file is an empty evidence set, not an error: it simply makes the
    claim partial.  A malformed file is an error because the reviewer intended
    evidence and the tool cannot trust it.
    """
    if not path.is_file():
        return []
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ClaimError(f"cannot read manual evidence {path}: {error}") from error
    if isinstance(document, list):
        return document
    if not isinstance(document, dict):
        raise ClaimError("manual evidence must be an object or an array")
    evidence = document.get("evidence", [])
    if not isinstance(evidence, list):
        raise ClaimError("manual evidence 'evidence' must be an array")
    return evidence


def _parse_date(value: Any, field: str, errors: list[str]) -> date | None:
    text = str(value or "").strip()
    if not text:
        errors.append(f"{field} is missing")
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        errors.append(f"{field} is not an ISO date: {text!r}")
        return None


def validate_evidence(entry: Any, rule_id: str, root: Path | None,
                      today: date) -> list[str]:
    """Validate one manual evidence entry against the normative contract."""
    errors: list[str] = []
    if not isinstance(entry, dict):
        return ["entry is not an object"]
    for field in EVIDENCE_FIELDS:
        if not str(entry.get(field, "")).strip():
            errors.append(f"missing {field}")
    if errors:
        return errors
    if entry["rule"] != rule_id:
        errors.append(f"rule is {entry['rule']!r}, expected {rule_id!r}")
    if entry["result"] != PASS_RESULT:
        errors.append(f"result is {entry['result']!r}; a full claim requires 'pass'")
    if entry["scope"] != FULL_SCOPE:
        errors.append(
            f"scope is {entry['scope']!r}; a full claim requires repository-scoped evidence")
    reviewed = _parse_date(entry["reviewedOn"], "reviewedOn", errors)
    expires = _parse_date(entry["expires"], "expires", errors)
    if reviewed and expires and expires < reviewed:
        errors.append("expires precedes reviewedOn")
    if reviewed and reviewed > today:
        errors.append("reviewedOn is in the future")
    if expires and expires < today:
        errors.append("evidence has expired")
    if root is not None:
        artifact = Path(str(entry["artifact"]))
        if not (root / artifact).is_file():
            errors.append(f"artifact does not exist: {entry['artifact']}")
    return errors


def assess(payload: Any, catalog: dict, level: str | None = None,
           evidence: list[dict] | None = None, evidence_path: str = EVIDENCE_FILE,
           root: Path | None = None, today: date | None = None) -> dict:
    """Compute the claim class for a run.

    Structural problems in the run or evidence raise ``ClaimError`` (exit 2 in
    the CLI).  A well-formed run with missing or invalid manual evidence is a
    ``PARTIAL ASSESSMENT`` (exit 1 only when a full claim was requested).
    """
    if not isinstance(payload, dict):
        raise ClaimError("run is not a JSON object")
    run_level = payload.get("level")
    if run_level not in LEVELS:
        raise ClaimError(f"run level is {run_level!r}; expected L1, L2 or L3")
    if level is not None and level != run_level:
        raise ClaimError(f"requested level {level!r} does not match the run level {run_level!r}")
    level = run_level

    rules = required_rules(catalog, level)
    required_ids = [rule["id"] for rule in rules]
    execution = payload.get("execution")
    if not isinstance(execution, dict):
        raise ClaimError("run has no execution map; this is an invalid assessment")
    missing_from_map = [rule_id for rule_id in required_ids if rule_id not in execution]
    if missing_from_map:
        raise ClaimError(
            "execution map does not cover every rule required by the level: "
            + ", ".join(missing_from_map))

    findings = payload.get("findings")
    if not isinstance(findings, list):
        raise ClaimError("run findings is not an array")
    blocking_findings = [
        finding for finding in findings
        if isinstance(finding, dict) and finding.get("severity") == "error"
    ]

    today = today or date.today()
    entries = evidence or []
    accepted: list[dict] = []
    invalid: list[dict] = []
    by_rule: dict[str, list[dict]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            invalid.append({"rule": None, "errors": ["entry is not an object"]})
            continue
        rule_id = str(entry.get("rule", "")).strip()
        if rule_id not in required_ids:
            # Evidence for a rule outside this level is not an error; it simply
            # cannot support this claim.
            continue
        by_rule.setdefault(rule_id, []).append(entry)

    missing: list[str] = []
    executed_ids: list[str] = []
    manual_ids: list[str] = []
    unsupported: list[str] = []
    reasons: list[str] = []
    for rule in rules:
        rule_id = rule["id"]
        automation = rule.get("automation")
        if automation not in ("automated", "manual"):
            raise ClaimError(
                f"catalog rule {rule_id} has unknown automation {automation!r}")
        value = execution.get(rule_id)
        if not isinstance(value, dict) or type(value.get("executed")) is not bool:
            raise ClaimError(f"execution entry for {rule_id} has no boolean executed flag")
        if value["executed"] is True and automation == "automated":
            executed_ids.append(rule_id)
            continue
        if value["executed"] is True:
            # A rule the catalog marks manual is not decidable by a portable
            # enforcer.  Trusting this flag would let an unsupported check pass
            # as evaluated, so the claim still requires repository-scoped
            # evidence and the run is reported as a misstated execution map.
            unsupported.append(rule_id)
        elif not str(value.get("reason", "")).strip():
            raise ClaimError(f"execution entry for {rule_id} is unexecuted without a reason")

        valid_entry = None
        for entry in by_rule.get(rule_id, []):
            entry_errors = validate_evidence(entry, rule_id, root, today)
            if entry_errors:
                invalid.append({"rule": rule_id, "errors": entry_errors})
            elif valid_entry is None:
                valid_entry = entry
        if valid_entry is not None:
            accepted.append(valid_entry)
            manual_ids.append(rule_id)
            continue

        missing.append(rule_id)
        if rule_id in unsupported:
            reasons.append(
                f"{rule_id} is manual in the catalog; an execution claim cannot substitute "
                "for repository-scoped manual evidence")
        elif automation == "manual":
            requirement = rule.get("manualEvidence") or "record a repository-scoped manual review"
            reasons.append(f"{rule_id} needs manual evidence: {requirement}")
        else:
            reasons.append(f"{rule_id} was marked automated but did not execute")

    if blocking_findings:
        reasons.append(
            f"{len(blocking_findings)} unwaived error finding(s) block a full claim")
    eligible = not missing and not blocking_findings
    claim_class = FULL if eligible else PARTIAL
    return {
        "claim": claim_class,
        "eligible": eligible,
        "standard": payload.get("standard") or catalog.get("version"),
        "level": level,
        "required": len(rules),
        "executed": len(executed_ids),
        "manualEvidence": len(manual_ids),
        "manualRulesRequired": sum(1 for rule in rules if rule.get("automation") == "manual"),
        "missing": missing,
        "missingManual": [rule_id for rule_id in missing
                          if next((rule for rule in rules if rule["id"] == rule_id),
                                  {}).get("automation") == "manual"],
        "missingAutomated": [rule_id for rule_id in missing
                             if next((rule for rule in rules if rule["id"] == rule_id),
                                     {}).get("automation") != "manual"],
        "executedIds": executed_ids,
        "manualEvidenceIds": manual_ids,
        "unsupportedExecution": unsupported,
        "invalidEvidence": invalid,
        "blockingFindings": len(blocking_findings),
        "reasons": reasons,
        "evidencePath": evidence_path,
        "rules": {
            "required": required_ids,
            "manual": [rule["id"] for rule in rules if rule.get("automation") == "manual"],
        },
    }


def render_markdown(claim: dict) -> str:
    lines = [
        "## ACIMA conformance claim",
        "",
        f"- Level: `{claim.get('level')}`",
        f"- Claim: **{claim.get('claim')}**",
        f"- Required rules: {claim.get('required')} "
        f"({claim.get('executed')} executed, {claim.get('manualEvidence')} manual evidence)",
        f"- Unwaived error findings: {claim.get('blockingFindings')}",
        f"- Manual evidence: `{claim.get('evidencePath')}`",
        "",
    ]
    if claim.get("missing"):
        lines.append("### Missing required evidence")
        lines.append("")
        lines.extend(f"- `{rule}`" for rule in claim["missing"])
        lines.append("")
    if claim.get("invalidEvidence"):
        lines.append("### Rejected manual evidence")
        lines.append("")
        for entry in claim["invalidEvidence"]:
            lines.append(f"- `{entry.get('rule')}`: {'; '.join(entry.get('errors', []))}")
        lines.append("")
    if claim.get("reasons"):
        lines.append("### Why this is not full conformance")
        lines.append("")
        lines.extend(f"- {reason}" for reason in claim["reasons"])
        lines.append("")
    lines.append(
        "A partial assessment is not a conformance claim. See "
        "`docs/standard/08-conformance.md` and `docs/standard/07-executable-governance.md`.")
    lines.append("")
    return "\n".join(lines)
