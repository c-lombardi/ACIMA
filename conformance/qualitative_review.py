"""Evidence-backed qualitative review validation for the complete ACIMA catalog."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any

SCHEMA_VERSION = "1.0"
STATUSES = {"conforms", "gap", "not_applicable", "insufficient_evidence"}
EVIDENCE_KINDS = {"source", "test", "configuration", "architecture", "inventory", "absence"}


class ReviewValidationError(ValueError):
    """The qualitative review cannot support a complete assessment."""


def _safe_evidence_path(root: Path, raw: Any) -> tuple[Path | None, str | None]:
    if not isinstance(raw, str) or not raw.strip():
        return None, "evidence path must be a non-empty repository-relative path"
    path_text = raw.replace("\\", "/")
    candidate = PurePosixPath(path_text)
    if candidate.is_absolute() or ".." in candidate.parts:
        return None, "evidence path must stay inside the assessed repository"
    resolved = (root / Path(*candidate.parts)).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        return None, "evidence path resolves outside the assessed repository"
    if not resolved.exists() or not (resolved.is_file() or resolved.is_dir()):
        return None, "evidence path does not exist in the assessed repository"
    return resolved, None


def validate_review(document: Any, root: Path, catalog: dict,
                    catalog_sha256: str | None = None) -> dict:
    """Validate exact catalog coverage and repository-grounded evidence for every rule.

    A complete review is not a conformance result. It means every catalog requirement has an
    explicit, reasoned disposition backed by inspectable repository evidence.
    """
    problems: list[dict] = []
    root = root.resolve()
    rules = catalog.get("rules", [])
    expected = {rule["id"] for rule in rules}
    if not isinstance(document, dict):
        raise ReviewValidationError("review document must be a JSON object")
    if document.get("schemaVersion") != SCHEMA_VERSION:
        problems.append({"scope": "document", "problems": [f"schemaVersion must be {SCHEMA_VERSION}"]})
    if not str(document.get("reviewer", "")).strip():
        problems.append({"scope": "document", "problems": ["reviewer is required"]})
    reviewed_on = document.get("reviewedOn")
    try:
        parsed_date = date.fromisoformat(str(reviewed_on))
        if parsed_date.isoformat() != reviewed_on or parsed_date > date.today():
            raise ValueError("not canonical or is in the future")
    except (TypeError, ValueError):
        problems.append({"scope": "document", "problems": ["reviewedOn must be a valid YYYY-MM-DD date"]})
    if not catalog_sha256 or document.get("catalogSha256") != catalog_sha256:
        problems.append({"scope": "document", "problems": ["catalogSha256 is missing or does not match the current ACIMA catalog"]})
    entries = document.get("rules")
    if not isinstance(entries, list):
        entries = []
        problems.append({"scope": "document", "problems": ["rules must be an array"]})
    by_id: dict[str, list[dict]] = {}
    unknown_ids: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            problems.append({"scope": "rules", "problems": ["each rule review must be an object"]})
            continue
        rule_id = entry.get("rule")
        if not isinstance(rule_id, str) or rule_id not in expected:
            unknown_ids.append(str(rule_id))
            problems.append({"rule": rule_id, "problems": ["unknown or missing catalog rule identifier"]})
            continue
        by_id.setdefault(rule_id, []).append(entry)
    validated = []
    counts = {status: 0 for status in sorted(STATUSES)}
    for rule in rules:
        rule_id = rule["id"]
        candidates = by_id.get(rule_id, [])
        local: list[str] = []
        if len(candidates) != 1:
            local.append("rule must appear exactly once; found %d entries" % len(candidates))
            entry = candidates[0] if candidates else {}
        else:
            entry = candidates[0]
        status = entry.get("status")
        if status not in STATUSES:
            local.append("status must be one of: " + ", ".join(sorted(STATUSES)))
        rationale = entry.get("rationale")
        if not isinstance(rationale, str) or len(rationale.strip()) < 20:
            local.append("rationale must explain the disposition in at least 20 characters")
        evidence = entry.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            local.append("at least one evidence reference is required")
            evidence = []
        checked_evidence = []
        for index, item in enumerate(evidence):
            if not isinstance(item, dict):
                local.append(f"evidence[{index}] must be an object")
                continue
            kind = item.get("kind")
            if kind not in EVIDENCE_KINDS:
                local.append(f"evidence[{index}].kind must be one of: " + ", ".join(sorted(EVIDENCE_KINDS)))
            path, path_error = _safe_evidence_path(root, item.get("path"))
            if path_error:
                local.append(f"evidence[{index}]: {path_error}")
            observation = item.get("observation")
            if not isinstance(observation, str) or len(observation.strip()) < 12:
                local.append(f"evidence[{index}].observation must describe what was inspected and found")
            start, end = item.get("startLine"), item.get("endLine")
            if path is not None and path.is_file() and kind != "absence":
                try:
                    line_count = len(path.read_text(encoding="utf-8").splitlines())
                except (OSError, UnicodeError):
                    local.append(f"evidence[{index}]: referenced file cannot be read as UTF-8 text")
                else:
                    if (isinstance(start, bool) or not isinstance(start, int) or
                            isinstance(end, bool) or not isinstance(end, int) or
                            start < 1 or end < start or end > line_count):
                        local.append(f"evidence[{index}] must reference valid 1-based startLine/endLine")
                    else:
                        try:
                            cited_lines = path.read_text(encoding="utf-8").splitlines()[start - 1:end]
                        except (OSError, UnicodeError):
                            cited_lines = []
                        quote = item.get("quote")
                        if not isinstance(quote, str) or len(quote.strip()) < 3:
                            local.append(f"evidence[{index}].quote must reproduce text from the cited lines")
                        elif quote.strip() not in "\n".join(cited_lines):
                            local.append(f"evidence[{index}].quote does not appear in the cited line range")
            elif path is not None and path.is_dir() and kind != "absence":
                local.append(f"evidence[{index}]: directory evidence must use kind 'absence' or cite a file")
            elif kind == "absence" and (start is not None or end is not None):
                local.append(f"evidence[{index}]: absence evidence must omit line numbers")
            if path is not None and not path.is_dir():
                checked_evidence.append({"path": item.get("path"), "kind": kind,
                                         "startLine": start, "endLine": end,
                                         "observation": observation})
            elif path is not None:
                checked_evidence.append({"path": item.get("path"), "kind": kind,
                                         "observation": observation})
        if status == "not_applicable" and "not applicable" not in (rationale or "").lower():
            local.append("not_applicable status must explain why the requirement is not applicable")
        if status in STATUSES and checked_evidence and not local:
            counts[status] += 1
        validated.append({"rule": rule_id, "level": rule.get("level"), "title": rule.get("title"),
                          "status": status if status in STATUSES else "invalid",
                          "rationale": rationale, "evidence": checked_evidence,
                          "valid": not local, "problems": local})
        if local:
            problems.append({"rule": rule_id, "problems": local})
    missing = sorted(expected - set(by_id))
    extra = sorted(unknown_ids)
    duplicate = sorted(rule_id for rule_id, values in by_id.items() if len(values) != 1)
    reviewed = sum(1 for item in validated if item["valid"])
    unresolved = counts["insufficient_evidence"]
    complete = (not problems and reviewed == len(expected) and not missing and not extra
                and unresolved == 0)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "complete": complete,
        "status": "complete" if complete else "incomplete",
        "reviewed": reviewed,
        "required": len(expected),
        "pending": len(expected) - reviewed,
        "unresolved": unresolved,
        "counts": counts,
        "missing": missing,
        "extra": extra,
        "duplicates": duplicate,
        "problems": problems,
        "rules": validated,
        "meaning": "A complete qualitative review means every catalog rule has one structurally valid disposition anchored to repository evidence. Validation checks provenance and structure, not the semantic correctness of the reviewer's interpretation. It does not mean every rule conforms or that ACIMA conformance has been achieved.",
    }


def load_and_validate_review(path: Path, root: Path, catalog: dict,
                             catalog_sha256: str | None = None) -> dict:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReviewValidationError(f"cannot read qualitative review {path}: {error}") from error
    return validate_review(document, root, catalog, catalog_sha256)
