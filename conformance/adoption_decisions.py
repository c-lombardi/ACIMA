"""Owner-authored adoption decisions, produced by the HTML report or by conversation.

A decisions file records intent. It is bound to exactly one generated report by identity, and
ingestion may only record it: the workflow's existing approval command remains the only way to
authorize implementation. Nothing here writes to the target.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

KIND = "acima-adoption-decisions"
SCHEMA_VERSION = "1.0"

PACKAGES = ("recommended", "custom")
CHOICES = ("accept", "modify", "defer", "reject")
ANSWER_KINDS = (
    "report-review", "module", "module-path", "recommendation",
    "scope-objective", "scope-path", "remediation",
)
MAP_ANSWER_KINDS = ("module", "module-path", "recommendation")
SCOPE_ANSWER_KINDS = ("scope-objective", "scope-path")
IDENTITY_FIELDS = ("reportId", "reportSha256", "decisionSha256", "proposalSha256")


class DecisionError(ValueError):
    """The decisions file is not usable owner input."""


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _hex(value, length: int) -> bool:
    return isinstance(value, str) and len(value) == length and all(
        character in "0123456789abcdef" for character in value.lower()
    )


def load(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DecisionError("cannot read decisions file %s: %s" % (path, error)) from error
    return validate(value)


def validate(document: dict) -> dict:
    """Validate the decisions contract. Identity against a specific report is checked on ingest."""
    if not isinstance(document, dict):
        raise DecisionError("a decisions file must contain a JSON object")
    if document.get("kind") != KIND:
        raise DecisionError("decisions.kind must be %s" % KIND)
    if document.get("schemaVersion") != SCHEMA_VERSION:
        raise DecisionError("decisions.schemaVersion must be %s" % SCHEMA_VERSION)
    if not _hex(document.get("reportId"), 20):
        raise DecisionError("decisions.reportId must be a 20-hex identity")
    # The page cannot hash its own bytes, so these bindings may be supplied by the workflow. A value
    # that is present is still validated and compared on ingest; it is never silently trusted.
    for field, length in (("reportSha256", 64), ("decisionSha256", 64), ("proposalSha256", 64)):
        value = document.get(field)
        if value is not None and not _hex(value, length):
            raise DecisionError("decisions.%s must be a %s-hex identity when supplied" % (field, length))
    if document.get("package") not in PACKAGES:
        raise DecisionError("decisions.package must be one of %s" % ", ".join(PACKAGES))
    supersedes = document.get("supersedes")
    if supersedes is not None and not _hex(supersedes, 64):
        raise DecisionError("decisions.supersedes must be null or the sha256 of the file it replaces")
    if not str(document.get("reviewer") or "").strip():
        raise DecisionError("decisions.reviewer is required")
    try:
        decided_on = str(document.get("decidedOn"))
        parsed = date.fromisoformat(decided_on)
        if parsed.isoformat() != decided_on or parsed > date.today():
            raise ValueError
    except (TypeError, ValueError) as error:
        raise DecisionError("decisions.decidedOn must be a valid, non-future YYYY-MM-DD date") from error
    entries = document.get("answers")
    if not isinstance(entries, list) or not entries:
        raise DecisionError("decisions.answers must list at least one answer")
    seen: set[tuple[str, str]] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise DecisionError("decisions.answers[%s] must be an object" % index)
        kind, identifier = entry.get("kind"), entry.get("id")
        if kind not in ANSWER_KINDS:
            raise DecisionError("decisions.answers[%s].kind is unknown" % index)
        if not str(identifier or "").strip():
            raise DecisionError("decisions.answers[%s].id is required" % index)
        if entry.get("decision") not in CHOICES:
            raise DecisionError("decisions.answers[%s].decision must be one of %s"
                                % (index, ", ".join(CHOICES)))
        if entry.get("decision") == "modify" and not str(entry.get("note") or "").strip():
            raise DecisionError("decisions.answers[%s] is a modification and needs a note" % index)
        if kind == "report-review" and identifier != "all-pages":
            raise DecisionError("the report-review answer must use id all-pages")
        key = (kind, identifier)
        if key in seen:
            raise DecisionError("decisions.answers repeats %s %s" % key)
        seen.add(key)
    return document


def answers(document: dict) -> list[dict]:
    return [dict(entry) for entry in document.get("answers") or []]


def prior_answers(sources: list[dict]) -> dict[tuple[str, str], dict]:
    """Collapse recorded decision sources into the answer currently in force."""
    current: dict[tuple[str, str], dict] = {}
    for source in sources or []:
        if not isinstance(source, dict) or source.get("status") == "superseded":
            continue
        for entry in source.get("answers") or []:
            if isinstance(entry, dict) and entry.get("kind") and entry.get("id"):
                current[(entry["kind"], entry["id"])] = {
                    **entry,
                    "sourceSha256": source.get("fileSha256"),
                    "reviewer": source.get("reviewer"),
                    "decidedOn": source.get("decidedOn"),
                }
    return current


def conflicts(document: dict, sources: list[dict],
              supersedes: str | None = None) -> list[dict]:
    """List answers that contradict a decision in force in a file that is not being replaced.

    A file may name one earlier file in `supersedes`; only that file's answers may change. Answers
    recorded by any other file still conflict, so one supersede cannot silently rewrite them.
    """
    prior = prior_answers(sources)
    result = []
    for entry in answers(document):
        previous = prior.get((entry["kind"], entry["id"]))
        if not previous or previous.get("decision") == entry.get("decision"):
            continue
        if supersedes and previous.get("sourceSha256") == supersedes:
            continue
        result.append({
            "kind": entry["kind"], "id": entry["id"],
            "recorded": previous.get("decision"), "recordedBy": previous.get("reviewer"),
            "recordedOn": previous.get("decidedOn"),
            "recordedIn": previous.get("sourceSha256"),
            "proposed": entry["decision"],
        })
    return result


def source_entry(document: dict, path: Path) -> dict:
    """The provenance record for one ingested file."""
    return {
        "status": "in force",
        "file": path.name,
        "fileSha256": _sha(path),
        "reportId": document["reportId"],
        "reportSha256": document["reportSha256"],
        "decisionSha256": document["decisionSha256"],
        "proposalSha256": document["proposalSha256"],
        "reviewer": document["reviewer"],
        "decidedOn": document["decidedOn"],
        "source": document.get("source") or "decisions-file",
        "package": document.get("package"),
        "supersedes": document.get("supersedes"),
        "answers": answers(document),
    }
