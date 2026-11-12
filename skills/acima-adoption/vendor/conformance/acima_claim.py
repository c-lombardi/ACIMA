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
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

FULL = "FULL CONFORMANCE"
PARTIAL = "PARTIAL ASSESSMENT"
INVALID = "INVALID ASSESSMENT"
LEVELS = ("L1", "L2", "L3")
LEVEL_INDEX = {"L1": 1, "L2": 2, "L3": 3}
EVIDENCE_FILE = "acima/evidence/manual-evidence.json"
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
WAIVER_FIELDS = ("rule", "scope", "fingerprint", "owner", "reason", "expires", "reviewedOn")
FINGERPRINT_PATTERN = re.compile(r"sha256:[0-9a-f]{64}$")
ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _waiver_glob_problem(pattern: str) -> str | None:
    """Return why ``pattern`` is not a valid waiver path glob.

    The contract is deliberately small and shared by every enforcer: ``*`` and ``?``
    match within one path segment, and ``**`` is a whole segment matching zero or more
    segments. Character classes and brace expansion are literals, not syntax.
    """
    if not pattern:
        return "the pattern is empty"
    if pattern != pattern.strip():
        return "the pattern has leading or trailing whitespace"
    if "\\" in pattern:
        return "use forward slashes"
    if pattern.startswith("/") or pattern.endswith("/"):
        return "the pattern must be relative and must not end with a slash"
    if "//" in pattern:
        return "the pattern contains an empty segment"
    if any(part in ("", ".", "..") for part in pattern.split("/")):
        return "the pattern must not contain empty, '.' or '..' segments"
    index = 0
    while index < len(pattern):
        if pattern[index] == "*" and index + 1 < len(pattern) and pattern[index + 1] == "*":
            before = index == 0 or pattern[index - 1] == "/"
            after = index + 2 == len(pattern) or pattern[index + 2] == "/"
            if not (before and after):
                return "'**' must be a whole path segment"
            index += 2
            continue
        index += 1
    return None


def _waiver_glob_regex(pattern: str) -> re.Pattern[str] | None:
    if _waiver_glob_problem(pattern) is not None:
        return None
    parts = ["^"]
    index = 0
    while index < len(pattern):
        if pattern[index] == "*" and index + 1 < len(pattern) and pattern[index + 1] == "*":
            if index + 2 < len(pattern) and pattern[index + 2] == "/":
                parts.append("(?:[^/]+/)*")
                index += 3
            else:
                parts.append(".*")
                index += 2
        elif pattern[index] == "*":
            parts.append("[^/]*")
            index += 1
        elif pattern[index] == "?":
            parts.append("[^/]")
            index += 1
        else:
            parts.append(re.escape(pattern[index]))
            index += 1
    parts.append("$")
    return re.compile("".join(parts))


def waiver_glob_match(pattern: str, value: str) -> bool:
    """Match one repository-relative path using the shared waiver glob contract."""
    expression = _waiver_glob_regex(pattern)
    return expression is not None and expression.match(value) is not None


def _waiver_scope_is_known(scope: str, scopes: set[str]) -> bool:
    """Match the enforcers' waiver scope vocabulary exactly.

    Enforcers apply ``unit:<id>`` and ``module:<name>`` against declared units, and
    ``path:<glob>`` against finding paths. ``repository`` is manual-evidence scope, not a
    waiver scope, so accepting it here would approve an exception the gate never applies.
    """
    return scope in scopes or (scope.startswith("path:")
                               and _waiver_glob_problem(scope[5:]) is None)


def _iso_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not ISO_DATE_PATTERN.match(text):
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def validate_run_artefact(payload: Any, catalog_version: str | None = None) -> list[str]:
    """Return every reason a JSON object cannot be treated as a measured run.

    Shared by status and any other consumer. A file that exists is not a measurement: the run must
    carry a positive source count, a real execution map, a findings list and a declared level.
    """
    if not isinstance(payload, dict):
        return ["run artefact is not a JSON object"]
    problems: list[str] = []
    sources = payload.get("sourceFiles")
    if isinstance(sources, bool) or not isinstance(sources, int) or sources <= 0:
        problems.append("sourceFiles is not a positive count")
    execution = payload.get("execution")
    if not isinstance(execution, dict) or len(execution) < 2:
        problems.append("execution map is missing or too small to be a run")
    if not isinstance(payload.get("findings"), list):
        problems.append("findings is not a list")
    if payload.get("level") not in LEVELS:
        problems.append("level is missing or invalid")
    # ``standard`` is the target's declared standard version, not the catalog version.
    # The two differ by design (for example a 1.0.0 target and a 1.9.0-draft catalog), so
    # comparing them would reject every real enforcer run. The catalog is identified by the
    # rule set and, for a gate observation, by catalogSha256.
    standard = payload.get("standard")
    if not isinstance(standard, str) or not standard.strip():
        problems.append("standard is missing")
    return problems


def validate_waivers(document: Any, *, today: date | None = None,
                     valid_scopes: set[str] | None = None) -> dict:
    """Validate waiver governance once, for status and preflight alike.

    An invalid, expired or unowned waiver is never treated as an accepted exception. The result
    counts every waiver once and names the entries that fail each rule.
    """
    today = today or datetime.now(timezone.utc).date()
    result: dict[str, Any] = {
        "total": 0, "valid": [], "invalid": [], "expired": [], "unowned": [],
        "missing": [], "scopeMismatch": [],
    }
    waivers = document.get("waivers") if isinstance(document, dict) else None
    if not isinstance(waivers, list):
        result["invalid"].append({"index": None, "rule": None,
                                  "problems": ["waivers is not a list"]})
        return result
    result["total"] = len(waivers)
    scopes = set(valid_scopes or set())
    for index, waiver in enumerate(waivers):
        if not isinstance(waiver, dict):
            result["invalid"].append({"index": index, "rule": None,
                                      "problems": ["waiver is not an object"]})
            continue
        problems: list[str] = []
        missing = [field for field in WAIVER_FIELDS
                   if not str(waiver.get(field, "")).strip()]
        if missing:
            problems.append("missing " + ", ".join(missing))
        fingerprint = str(waiver.get("fingerprint", "")).strip()
        if fingerprint and not FINGERPRINT_PATTERN.match(fingerprint):
            problems.append("fingerprint is not sha256:<64 hex>")
        expiry = _iso_date(waiver.get("expires"))
        reviewed = _iso_date(waiver.get("reviewedOn"))
        if str(waiver.get("expires", "")).strip() and expiry is None:
            problems.append("expires is not an ISO date")
        if str(waiver.get("reviewedOn", "")).strip() and reviewed is None:
            problems.append("reviewedOn is not an ISO date")
        if reviewed and reviewed > today:
            problems.append("reviewedOn is in the future")
        if reviewed and expiry and reviewed > expiry:
            problems.append("reviewedOn is after expires")
        scope = str(waiver.get("scope", "")).strip()
        glob_problem = (_waiver_glob_problem(scope[5:])
                        if scope.startswith("path:") else None)
        if glob_problem:
            problems.append(f"path scope is invalid: {glob_problem}")
        entry = {"index": index, "rule": waiver.get("rule"), "problems": problems}
        if missing:
            result["missing"].append(entry)
        if problems:
            result["invalid"].append(entry)
        if expiry and expiry < today:
            result["expired"].append(entry)
        unowned = str(waiver.get("owner", "")).strip().lower() in ("", "unassigned")
        if unowned:
            result["unowned"].append(entry)
        scope_known = bool(scope) and _waiver_scope_is_known(scope, scopes)
        if scope and not scope_known and not glob_problem:
            result["scopeMismatch"].append(entry)
            result["invalid"].append({**entry, "problems": problems + [
                f"scope {scope!r} matches no declared unit/module or path: pattern"]})
        if not problems and not (expiry and expiry < today) and scope_known and not unowned:
            result["valid"].append(entry)
    return result


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
    if not path.is_file() and path.parent.name == "evidence" and path.parent.parent.name == "acima":
        legacy = path.parent.parent.parent / ".acima" / path.name
        if legacy.is_file():
            path = legacy
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
    ]
    if claim.get("currentness"):
        lines.append(f"- Currentness: `{claim.get('currentness')}`")
    lines.append("")
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
