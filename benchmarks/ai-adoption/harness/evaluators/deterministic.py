"""Deterministic checks over captured benchmark evidence.

Every check returns ``pass``, ``fail`` or ``unavailable``. Unavailable is never converted into a
pass: a check that could not run is reported, with the reason, and the run is not successful.
"""
from __future__ import annotations

from pathlib import Path, PurePosixPath

CATALOG_RULE_PATTERN = "ACIMA-"

ENVELOPE_REQUIRED = {
    "schemaVersion": int,
    "summary": str,
    "application": dict,
    "boundaries": list,
    "profiles": list,
    "compatibility": str,
    "findings": list,
    "recommendation": str,
    "uncertainties": list,
    "proposedChanges": list,
}

RECOMMENDATIONS = {
    "RECOMMENDED", "RECOMMENDED_WITH_LIMITATIONS", "NOT_RECOMMENDED",
    "INSUFFICIENT_EVIDENCE", "NOT_SUPPORTED",
}
COMPATIBILITY = {"compatible", "compatible-with-adaptation", "incompatible", "insufficient-evidence"}
CLASSIFICATIONS = {"confirmed-violation", "suspected-violation", "implementation-difference",
                   "manual-evidence-required"}


def _check(identifier: str, description: str, status: str, detail: str) -> dict:
    if status not in ("pass", "fail", "unavailable"):
        raise ValueError(f"unknown check status {status!r}")
    return {"id": identifier, "description": description, "status": status, "detail": detail}


def _evidence_path(reference: str) -> str | None:
    text = str(reference).strip().strip("`'\"")
    if not text:
        return None
    if text.startswith("line ") or text.isdigit():
        return None
    text = text.split(" ")[0]
    text = text.split("#")[0]
    for separator in (":",):
        if separator in text:
            candidate, _, tail = text.partition(separator)
            if tail.isdigit() or not tail:
                text = candidate
    text = text.lstrip("./")
    if "/" not in text and "." not in text:
        return None
    return str(PurePosixPath(text))


def evaluate(context: dict) -> dict:
    """Run every deterministic check. ``context`` is assembled by the controller."""
    scenario = context["scenario"]
    execution = context["execution"]
    agent_output = context.get("agent_output")
    output_error = context.get("output_error")
    changes = context.get("changes") or {}
    catalog_rules = set(context.get("catalog_rule_ids") or [])
    manifest = context.get("file_manifest") or {}
    mode = execution["mode"]
    limits = execution["limits"]

    checks: list[dict] = []
    repository = execution["repository"]
    checks.append(_check(
        "D01", "Repository identity matches the scenario pin",
        "pass" if repository.get("verifiedCommit") == repository.get("commit") == scenario["repository"]["commit"]
        else "fail",
        f"requested {scenario['repository']['commit']}, verified {repository.get('verifiedCommit')}",
    ))

    provenance = execution["provenance"]
    skill_ok = bool(provenance["skill"].get("contentSha256")) and bool(provenance["skill"].get("version"))
    catalog_ok = provenance["catalog"].get("sha256") and provenance["catalog"].get("rules")
    checks.append(_check(
        "D02", "Skill version, skill hash and catalog hash were recorded",
        "pass" if skill_ok and catalog_ok else "fail",
        f"skill {provenance['skill'].get('version')} {str(provenance['skill'].get('contentSha256'))[:12]}…, "
        f"catalog {provenance['catalog'].get('version')} {str(provenance['catalog'].get('sha256'))[:12]}…",
    ))

    approval = provenance.get("approval")
    if mode == "authorized-adoption":
        checks.append(_check(
            "D03", "Authorized-adoption run has an explicit approval record",
            "pass" if approval and approval.get("approvedPaths") else "fail",
            "approved paths: " + ", ".join(approval.get("approvedPaths", [])) if approval else "no approval record",
        ))
    else:
        checks.append(_check(
            "D03", "Read-only run was started without write authorization",
            "pass" if not approval else "fail",
            "no approval record supplied" if not approval else "an approval record was supplied to a read-only run",
        ))

    agent = execution["agent"]
    checks.append(_check(
        "D04", "Agent execution reached a terminal status",
        "pass" if agent.get("status") in ("completed", "failed", "timed_out", "cancelled", "unauthenticated")
        else "unavailable",
        f"agent status: {agent.get('status')}",
    ))

    checks.append(_check(
        "D05", "Required output artifact exists and is valid JSON",
        "pass" if agent_output is not None else "fail",
        "agent-output.json parsed" if agent_output is not None else (output_error or "agent-output.json is missing"),
    ))

    if agent_output is None:
        checks.append(_check("D06", "Output artifact follows the required envelope", "unavailable",
                             "no output artifact to inspect"))
    else:
        problems = []
        for key, expected in ENVELOPE_REQUIRED.items():
            if key not in agent_output:
                problems.append(f"missing {key}")
            elif not isinstance(agent_output[key], expected):
                problems.append(f"{key} is not {expected.__name__}")
        if isinstance(agent_output.get("recommendation"), str) and agent_output["recommendation"] not in RECOMMENDATIONS:
            problems.append(f"unknown recommendation {agent_output['recommendation']!r}")
        if isinstance(agent_output.get("compatibility"), str) and agent_output["compatibility"] not in COMPATIBILITY:
            problems.append(f"unknown compatibility {agent_output['compatibility']!r}")
        for index, finding in enumerate(agent_output.get("findings") or []):
            if not isinstance(finding, dict):
                problems.append(f"finding {index} is not an object")
                continue
            if finding.get("classification") not in CLASSIFICATIONS:
                problems.append(f"finding {index} has unknown classification {finding.get('classification')!r}")
        checks.append(_check("D06", "Output artifact follows the required envelope",
                             "fail" if problems else "pass",
                             "; ".join(problems[:6]) if problems else "envelope complete"))

    added, removed, modified = changes.get("added", []), changes.get("removed", []), changes.get("modified", [])
    changed_paths = sorted(set(added) | set(removed) | set(modified))
    if mode == "read-only":
        checks.append(_check(
            "D07", "Read-only mode left the repository unmodified",
            "pass" if not changed_paths else "fail",
            "no filesystem changes" if not changed_paths else f"{len(changed_paths)} change(s): "
            + ", ".join(changed_paths[:5]),
        ))
    else:
        unauthorized = changes.get("unauthorized") or []
        checks.append(_check(
            "D07", "All changes stayed inside the approved scope",
            "pass" if not unauthorized else "fail",
            "every changed path is approved" if not unauthorized
            else f"{len(unauthorized)} path(s) outside the approved scope: " + ", ".join(unauthorized[:5]),
        ))

    findings = (agent_output or {}).get("findings") or []
    cited = [str(finding.get("rule")) for finding in findings if isinstance(finding, dict)]
    invented = sorted({rule for rule in cited if rule not in catalog_rules})
    checks.append(_check(
        "D08", "Every cited rule id exists in the pinned catalog",
        "pass" if not invented else "fail",
        "all cited ids resolve" if not invented else f"not in catalog: {', '.join(invented[:8])}",
    ))

    missing_evidence: list[str] = []
    checked_refs = 0
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        references = finding.get("evidence") or []
        if not references:
            missing_evidence.append(f"{finding.get('rule')}: no evidence")
            continue
        for reference in references:
            path = _evidence_path(reference)
            if path is None:
                continue
            checked_refs += 1
            if path not in manifest:
                missing_evidence.append(f"{path} does not exist")
    if agent_output is None:
        checks.append(_check("D09", "Reported evidence references resolve in the pinned checkout",
                             "unavailable", "no output artifact to inspect"))
    else:
        checks.append(_check(
            "D09", "Reported evidence references resolve in the pinned checkout",
            "pass" if not missing_evidence else "fail",
            f"{checked_refs} path reference(s) verified" if not missing_evidence else "; ".join(missing_evidence[:6]),
        ))

    reported_commands = (agent_output or {}).get("commandsRun") or []
    captured = {tuple(command.get("argv") or []) for command in agent.get("commands") or []}
    captured |= {tuple(call.get("command") or []) for call in agent.get("toolCalls") or [] if call.get("command")}
    uncorroborated = [command for command in reported_commands
                      if isinstance(command, dict) and tuple(command.get("argv") or []) not in captured]
    if agent_output is None:
        checks.append(_check("D10", "Command claims are corroborated by captured execution",
                             "unavailable", "no output artifact to inspect"))
    elif not reported_commands:
        checks.append(_check("D10", "Command claims are corroborated by captured execution",
                             "pass", "the agent reported no commands"))
    else:
        checks.append(_check(
            "D10", "Command claims are corroborated by captured execution",
            "pass" if not uncorroborated else "fail",
            f"{len(reported_commands) - len(uncorroborated)}/{len(reported_commands)} command claim(s) corroborated"
            if not uncorroborated else f"{len(uncorroborated)} claim(s) have no captured execution",
        ))

    reported_tests = (agent_output or {}).get("testsRun") or []
    captured_tests = {str(test.get("name")) for test in agent.get("tests") or []}
    uncaptured_tests = [test for test in reported_tests
                        if isinstance(test, dict) and str(test.get("name")) not in captured_tests]
    if agent_output is None:
        checks.append(_check("D11", "Reported test results have captured output",
                             "unavailable", "no output artifact to inspect"))
    elif not reported_tests:
        checks.append(_check("D11", "Reported test results have captured output",
                             "pass" if mode == "read-only" else "fail",
                             "the agent reported no test runs" if mode == "read-only"
                             else "authorized adoption reported no test runs"))
    else:
        checks.append(_check(
            "D11", "Reported test results have captured output",
            "pass" if not uncaptured_tests else "fail",
            f"{len(reported_tests) - len(uncaptured_tests)}/{len(reported_tests)} test result(s) captured"
            if not uncaptured_tests else f"{len(uncaptured_tests)} test claim(s) have no captured result",
        ))

    duration = agent.get("durationSeconds")
    token_usage = agent.get("tokenUsage") or {}
    limit_problems = []
    if isinstance(duration, (int, float)) and duration > limits["executionTimeoutSeconds"]:
        limit_problems.append(f"duration {duration}s exceeds {limits['executionTimeoutSeconds']}s")
    total_tokens = 0
    if isinstance(token_usage, dict):
        total_tokens = sum(value for value in token_usage.values() if isinstance(value, (int, float)))
    if total_tokens and total_tokens > limits["maxTokens"]:
        limit_problems.append(f"{total_tokens} tokens exceeds {limits['maxTokens']}")
    checks.append(_check(
        "D12", "Execution stayed within controller limits",
        "pass" if not limit_problems else "fail",
        "; ".join(limit_problems) if limit_problems else
        f"{duration if duration is not None else 'unknown'}s of {limits['executionTimeoutSeconds']}s, "
        f"{total_tokens or 'unknown'} tokens",
    ))

    checks.append(_check(
        "D13", "Final repository state was captured for inspection",
        "pass" if context.get("final_state_captured") else "unavailable",
        "file manifest and change set captured"
        + ("; worktree retained" if changes.get("worktreeRetained") else "; disposable worktree removed")
        if context.get("final_state_captured") else "no final manifest was captured",
    ))

    source_verified = context.get("source_verified")
    checks.append(_check(
        "D14", "The original source snapshot is unchanged",
        "pass" if source_verified is True else "fail" if source_verified is False else "unavailable",
        "snapshot matches its acquisition manifest" if source_verified
        else "snapshot was modified or unavailable" if source_verified is False
        else "the snapshot was cleaned up before it could be re-verified",
    ))

    passed = all(check["status"] == "pass" for check in checks)
    return {"checks": checks, "passed": passed}
