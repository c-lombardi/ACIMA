"""Reporting: one machine-readable record and one human-readable report.

No dashboard, no aggregate score. The report states what was tested, what the agent found, what was
correct, what was missed, what remains uncertain, and which metrics are unavailable and why.
"""
from __future__ import annotations

import json
from pathlib import Path

from .lifecycle import is_terminal


def _fmt(value: float | None, unit: str) -> str:
    if value is None:
        return "—"
    if unit == "seconds":
        return f"{value:.2f}s"
    if unit == "count":
        return f"{value:g}"
    return f"{value:.2f}"


def metrics_table(metrics: list[dict]) -> list[str]:
    lines = [
        "| Metric | Value | Status | Basis |",
        "|---|---|---|---|",
    ]
    for metric in metrics:
        lines.append(
            f"| {metric['name']} | {_fmt(metric['value'], metric['unit'])} | {metric['status']} "
            f"| {metric['detail'].replace('|', '/')} |"
        )
    return lines


def _isolation_label(sandbox: dict) -> str:
    value = sandbox.get("agentIsolated")
    if value is None:
        return "not applicable (no agent process executed)"
    return "yes" if value else "no (adapter ran in the controller process)"


def render_markdown(result: dict, scenario: dict, directory: Path | None = None) -> str:
    execution = result["execution"]
    evaluation = result["evaluation"]
    repository = execution.get("repository", {})
    adapter = execution.get("adapter", {})
    provenance = execution.get("provenance", {})
    checks = evaluation.get("deterministic", {}).get("checks", [])
    metrics = result.get("metrics") or []
    failing = [check for check in checks if check["status"] == "fail"]
    criteria = evaluation.get("criteria", [])

    lines = [
        f"# AI adoption benchmark — {scenario.get('name', result['scenarioId'])}",
        "",
        f"- Run: `{result['runId']}`",
        f"- Scenario: `{result['scenarioId']}` ({scenario.get('category')})",
        f"- Outcome: **{result['outcome']}** — pipeline success: **{str(result['success']).lower()}**",
        f"- Mode: `{execution.get('mode')}`",
        f"- Agent provider / model: `{adapter.get('provider')}` / `{adapter.get('model')}`",
        f"- Skill: `{provenance.get('skill', {}).get('version')}` "
        f"(`{str(provenance.get('skill', {}).get('contentSha256'))[:16]}…`)",
        f"- Standard: `{provenance.get('standard', {}).get('version')}` · "
        f"catalog `{provenance.get('catalog', {}).get('version')}` "
        f"(`{str(provenance.get('catalog', {}).get('sha256'))[:16]}…`)",
        f"- Repository: {repository.get('url')} @ `{repository.get('commit')}`",
        f"- Started / finished: {execution.get('startedAt')} / {execution.get('finishedAt')}",
        "",
    ]

    if adapter.get("provider") == "fake":
        lines += [
            "> **This run used the deterministic scripted adapter.** It demonstrates the harness and is",
            "> not evidence of any model's capability. No model, provider or paid call was involved.",
            "",
        ]

    lines += ["## 1. What was tested", ""]
    lines.append(scenario.get("description", ""))
    lines += [
        "",
        f"- Software category: {scenario.get('softwareCategory')}",
        f"- Architecture family: {scenario.get('architectureFamily')}",
        f"- Applicable profiles (ground truth): {', '.join(scenario.get('applicableProfiles') or [])}",
        f"- Repository files at the pinned commit: {repository.get('fileCount')} "
        f"({repository.get('bytes')} bytes)",
        f"- Sandbox: `{execution.get('sandbox', {}).get('backend')}` "
        f"(agent process isolated: {_isolation_label(execution.get('sandbox', {}))})",
        f"- Instructions supplied: `{provenance.get('instructions', {}).get('id')}` "
        f"(`{str(provenance.get('instructions', {}).get('sha256'))[:16]}…`)",
        "",
    ]
    limitations = list(scenario.get("knownLimitations") or []) + list(result.get("limitations") or [])
    if limitations:
        lines += ["Known limitations recorded before and after the run:", ""]
        lines += [f"- {item}" for item in limitations]
        lines.append("")

    lines += ["## 2. Model and skill version", ""]
    lines += [
        f"Provider `{adapter.get('provider')}`, model `{adapter.get('model')}`, "
        f"configuration `{json.dumps(adapter.get('modelConfig'))}`.",
        f"Skill `{provenance.get('skill', {}).get('name')}` version "
        f"`{provenance.get('skill', {}).get('version')}`, content hash "
        f"`{provenance.get('skill', {}).get('contentSha256')}`.",
        f"Catalog `{provenance.get('catalog', {}).get('version')}` with "
        f"{provenance.get('catalog', {}).get('rules')} rules "
        f"({provenance.get('catalog', {}).get('portable')} portable).",
        "",
    ]
    capabilities = adapter.get("capabilities") or {}
    if capabilities.get("notes"):
        lines += ["Adapter capabilities and limits:", ""]
        lines += [f"- {note}" for note in capabilities["notes"]]
        lines.append("")

    lines += ["## 3. What the agent discovered", ""]
    output_path = (execution.get("artifacts") or {}).get("agentOutput")
    if output_path:
        lines.append(f"Captured verbatim at `{output_path}`. Structured summary:")
        lines.append("")
        agent_output = _load_artifact(directory, output_path)
        if agent_output:
            lines.append(f"- Summary: {agent_output.get('summary', '(none)')}")
            boundaries = agent_output.get("boundaries") or []
            if boundaries:
                lines.append("- Boundaries reported:")
                for boundary in boundaries[:12]:
                    units = ", ".join(str(unit) for unit in (boundary.get("units") or [])[:4])
                    lines.append(f"  - `{boundary.get('module')}` — {units}")
            lines.append(f"- Profiles claimed: {', '.join(agent_output.get('profiles') or []) or 'none'}")
            lines.append(f"- Compatibility: {agent_output.get('compatibility') or 'not stated'}")
            lines.append(f"- Recommendation: {agent_output.get('recommendation') or 'not stated'}")
            uncertainties = agent_output.get("uncertainties") or []
            if uncertainties:
                lines.append("- Stated uncertainties:")
                lines += [f"  - {item}" for item in uncertainties[:8]]
    else:
        lines.append("No assessment artifact was produced.")
    lines.append("")

    lines += ["## 4. Findings: correct and incorrect", ""]
    if criteria:
        lines += ["| Criterion | Status | Basis |", "|---|---|---|"]
        for criterion in criteria:
            detail = str(criterion.get("detail", "")).replace("|", "/")
            lines.append(f"| {criterion['description']} | {criterion['status']} | {detail} |")
        lines.append("")
    else:
        lines.append("No criteria were evaluated.")
        lines.append("")

    lines += ["## 5. What the agent missed", ""]
    missed = [item for item in evaluation.get("criteria", []) if item["status"] in ("fail", "partial")]
    if missed:
        for item in missed:
            detail = item.get("detail", "")
            evidence = ", ".join(item.get("evidence") or [])
            lines.append(f"- **{item['description']}** ({item['status']}): {detail}"
                         + (f" — {evidence}" if evidence else ""))
    else:
        lines.append("No required observation, boundary or criterion was missed under the recorded ground truth.")
    lines.append("")

    lines += ["## 6. Were the recommendations appropriate?", ""]
    recommendation = next((metric for metric in metrics if metric["id"] == "recommendation"), None)
    restructuring = next((metric for metric in metrics if metric["id"] == "unnecessary-restructuring"), None)
    if recommendation:
        lines.append(f"- Recommendation check: {recommendation['detail']} ({recommendation['status']}).")
    if restructuring:
        lines.append(f"- Restructuring: {restructuring['value']} proposal(s) of kind `restructure`; "
                     f"{restructuring['detail']}.")
    lines.append("")

    lines += ["## 7. Consent and scope", ""]
    scope_criteria = [item for item in criteria if item["id"] in ("scope", "consent")]
    for item in scope_criteria:
        lines.append(f"- {item['description']}: **{item['status']}** — {item['detail']}")
    changes = execution.get("changes") or {}
    changed = sorted(set(changes.get("added", [])) | set(changes.get("removed", []))
                     | set(changes.get("modified", [])))
    lines.append(f"- Files added/removed/modified: {len(changed)}")
    if changed:
        lines += [f"  - `{path}`" for path in changed[:20]]
    if changes.get("unauthorized"):
        lines += [f"- Outside the approved scope: `{path}`" for path in changes["unauthorized"][:20]]
    lines.append("")

    lines += ["## 8. Changes, if authorized", ""]
    if execution.get("mode") == "authorized-adoption":
        lines.append(f"- Approval: {provenance.get('approval') or 'missing'}")
        for command in (execution.get("verification") or {}).get("commands", []):
            lines.append(f"- Verification `{command['name']}`: exit {command['exitCode']} "
                         f"({command['phase']})")
    else:
        lines.append("Read-only mode: the agent was not authorized to change any file.")
    lines.append("")

    lines += ["## 9. Tests and verification", ""]
    tests = (execution.get("agent") or {}).get("tests") or []
    if tests:
        for test in tests:
            lines.append(f"- Agent-reported test `{test.get('name')}`: passed={test.get('passed')}")
    else:
        lines.append("- The agent ran no tests (read-only assessment does not require them).")
    lines += ["", "Deterministic checks:", "", "| Check | Status | Detail |", "|---|---|---|"]
    for check in checks:
        detail = str(check["detail"]).replace("|", "/")
        lines.append(f"| {check['id']} — {check['description']} | {check['status']} | {detail} |")
    if failing:
        lines += ["", f"**{len(failing)} deterministic check(s) failed.**"]
    lines.append("")

    lines += ["## 10. What remains uncertain", ""]
    indeterminate = evaluation.get("indeterminate") or []
    if indeterminate:
        lines += [f"- {item}" for item in indeterminate]
    unavailable = [metric for metric in metrics if metric["status"] != "measured"]
    if unavailable:
        lines += [f"- `{metric['id']}` is {metric['status']}: {metric['detail']}" for metric in unavailable]
    review = evaluation.get("humanReview") or {}
    if review.get("required"):
        lines.append(f"- Human review required: {review.get('reason')}")
    lines += [f"- {item}" for item in evaluation.get("limitations") or []]
    lines += [
        "",
        "A metric reported `unavailable` or `indeterminate` is not a pass. The absence of a finding is",
        "not evidence that a rule holds.",
        "",
        "## Metrics",
        "",
    ]
    lines += metrics_table(metrics)
    lines += [
        "",
        "## Evidence",
        "",
        f"Raw evidence is preserved under `{result['runId']}/evidence/`: instructions, event log,",
        "agent output, file manifests before and after, change set and the acquired repository identity.",
        "The result record embeds the execution account and this evaluation; neither is a substitute",
        "for the raw evidence.",
        "",
    ]
    return "\n".join(lines)


def _load_artifact(directory: Path | None, relative: str) -> dict | None:
    if directory is None:
        return None
    path = Path(directory) / relative
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def load_results(results_root: Path, *, scenario: str | None = None,
                 provider: str | None = None) -> list[dict]:
    results = []
    for path in sorted(Path(results_root).glob("*/result.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if scenario and payload.get("scenarioId") != scenario:
            continue
        if provider and (payload.get("execution", {}).get("adapter", {}).get("provider")) != provider:
            continue
        payload["_directory"] = str(path.parent)
        results.append(payload)
    return results


def compare(results: list[dict]) -> dict:
    """Group runs and report repeatability. Never merges metrics into one score."""
    groups: dict[tuple, list[dict]] = {}
    for result in results:
        execution = result.get("execution") or {}
        key = (
            result.get("scenarioId"),
            (execution.get("adapter") or {}).get("provider"),
            (execution.get("adapter") or {}).get("model"),
            (execution.get("provenance") or {}).get("skill", {}).get("version"),
        )
        groups.setdefault(key, []).append(result)

    comparison = {"groups": []}
    for (scenario, provider, model, skill), runs in sorted(groups.items(), key=lambda item: str(item[0])):
        runs = sorted(runs, key=lambda run: run.get("execution", {}).get("startedAt") or run.get("runId"))
        signatures = []
        for run in runs:
            output = _agent_output(run)
            findings = sorted(
                (finding.get("rule"), finding.get("path"), finding.get("classification"))
                for finding in (output or {}).get("findings") or [] if isinstance(finding, dict)
            )
            boundaries = sorted(
                str(boundary.get("module")) for boundary in (output or {}).get("boundaries") or []
                if isinstance(boundary, dict)
            )
            signatures.append((tuple(findings), tuple(boundaries)))
        consistent = len(set(signatures)) == 1 if len(runs) > 1 else None
        metrics: dict[str, list[float | None]] = {}
        for run in runs:
            for metric in run.get("metrics") or []:
                if metric.get("status") == "measured":
                    metrics.setdefault(metric["id"], []).append(metric.get("value"))
        comparison["groups"].append({
            "scenario": scenario,
            "provider": provider,
            "model": model,
            "skillVersion": skill,
            "runs": len(runs),
            "successful": sum(1 for run in runs if run.get("success")),
            "repeatable": consistent,
            "repeatabilityDetail": (
                "identical findings and boundaries across runs" if consistent
                else "runs differ" if consistent is False
                else "one run only; repeatability not established"
            ),
            "metrics": {
                key: {
                    "values": values,
                    "min": min(value for value in values if value is not None),
                    "max": max(value for value in values if value is not None),
                }
                for key, values in metrics.items() if any(value is not None for value in values)
            },
            "runIds": [run["runId"] for run in runs],
        })
    return comparison


def _agent_output(run: dict) -> dict | None:
    execution = run.get("execution") or {}
    path = (execution.get("artifacts") or {}).get("agentOutput")
    directory = run.get("_directory")
    if not path or not directory:
        return None
    try:
        return json.loads((Path(directory) / path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def render_comparison(comparison: dict) -> str:
    lines = ["# Benchmark comparison", ""]
    if not comparison["groups"]:
        return "\n".join(lines + ["No completed runs were found."])
    for group in comparison["groups"]:
        lines += [
            f"## {group['scenario']} — {group['provider']}/{group['model']}",
            "",
            f"- Runs: {group['runs']} ({group['successful']} with a verified pipeline)",
            f"- Skill version: `{group['skillVersion']}`",
            f"- Repeatability: {group['repeatabilityDetail']}",
            f"- Run ids: {', '.join(group['runIds'])}",
            "",
        ]
        if group["metrics"]:
            lines += ["| Metric | Values | Min | Max |", "|---|---|---|---|"]
            for name, values in sorted(group["metrics"].items()):
                shown = ", ".join("—" if value is None else f"{value:.3f}" for value in values["values"])
                lines.append(f"| {name} | {shown} | {values['min']:.3f} | {values['max']:.3f} |")
            lines.append("")
        lines += [
            "Metrics are shown individually; no aggregate score is computed. Runs with different models,",
            "skill versions or scenario commits are not comparable and are grouped separately.",
            "",
        ]
    return "\n".join(lines)
