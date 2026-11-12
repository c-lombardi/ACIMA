#!/usr/bin/env python3
"""Render the user-facing ACIMA adoption summary from an enforcement report.

The summary is a presentation of evidence, never a new judgement. It reads the run
artefact, the frozen baseline, the waiver file and an optional triage file, and groups the
findings by the architectural problem behind them. Every group keeps its rule id and
fingerprints, so the technical report stays the record of what was found.

    python3 skills/acima-adoption/scripts/summarize.py \
        --root /path/to/repo \
        --report /path/to/repo/docs/acima/gate-L1-latest.json \
        --out /path/to/repo/docs/acima/adoption-summary.md

It does not edit the target, reclassify a finding, or turn a passing baseline into a
conformance claim. Exit 0 when a summary was produced, 2 when the input cannot be read.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

CLASSIFICATIONS = ("defect", "review", "detector-artifact", "tooling-limitation")
PRIORITIES = ("High", "Medium", "Low", "Review")

# Rules that remove or protect an essential boundary. Priority is a recommendation about
# what to do first, not a change to the rule's severity or to its normative meaning.
HIGH_IMPACT = {
    "ACIMA-D001",  # implementation -> implementation
    "ACIMA-D002",  # contracts -> implementation
    "ACIMA-D005",  # circular modules
    "ACIMA-D006",  # contracts -> host
    "ACIMA-D007",  # shared kernel is not a leaf
    "ACIMA-L003",  # implementation type published outside the module
    "ACIMA-C001",  # mutable contract state
    "ACIMA-A001",  # shared database
    "ACIMA-A003",  # cross-module mutable static
    "ACIMA-G001",  # undocumented exception
    "ACIMA-G002",  # expired waiver
}

CATEGORY_IMPACT = {
    "D": ("Modules can reach across a boundary that was meant to contain them, so an "
          "internal change can break a consumer that never agreed to depend on it."),
    "L": ("A layer boundary inside a module is crossed, so persistence or framework detail "
          "can surface where only the module's own rules belong."),
    "C": ("A contract can change, or be mutated, in a way its consumers cannot rely on."),
    "A": ("Modules are not independent at runtime, so they cannot be deployed, configured "
          "or scaled separately."),
    "G": ("The exception record does not prove who owns a finding, why it exists, or when "
          "it ends, so the gate cannot be trusted to stay honest."),
}

ARTIFACT_IMPACT = ("The detector matched this pattern, but the match does not describe a "
                   "defect in the code. Treat it as a tooling problem, not architecture debt.")
REVIEW_IMPACT = ("This needs a person to decide whether the match is a real boundary "
                 "violation, a legitimate design, or a detector limitation.")

STATUS_DETAIL = {
    "Not assessed": ("No usable enforcement report was supplied, so nothing here is a "
                     "judgement about the repository."),
    "Assessment incomplete": ("Part of the required evidence is missing. What is reported "
                              "below is real, but it is not the whole picture."),
    "Significant issues found": ("The run found problems that are not in the frozen "
                                 "baseline. They need attention before anything else."),
    "Partially aligned": ("The repository follows some ACIMA boundaries, but unwaived real "
                          "defects remain. This is not conformance."),
    "Baseline established": ("The measured findings are recorded against a frozen baseline "
                             "and the gate reports no new findings. A passing baseline is "
                             "not architectural conformance."),
    "Verified": ("A current full conformance claim was supplied and matches this run. That "
                 "is the only status that asserts conformance."),
}


class InputError(Exception):
    """A report, catalog or metadata file cannot be used."""


def load_json(path: Path, what: str) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise InputError(f"{what} cannot be read: {path} ({error})") from error
    except json.JSONDecodeError as error:
        raise InputError(f"{what} is not valid JSON: {path} ({error})") from error
    if not isinstance(data, dict):
        raise InputError(f"{what} must be a JSON object: {path}")
    return data


def resolve_catalog(explicit: str | None) -> Path:
    here = Path(__file__).resolve()
    skill = here.parents[1] if len(here.parents) > 1 else here.parent
    candidates = [Path(explicit)] if explicit else []
    candidates += [parent / "tools/acima-spec/rules.json" for parent in here.parents]
    candidates.append(skill / "vendor/tools/acima-spec/rules.json")
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise InputError("rule catalog not found; pass --catalog or run inside the ACIMA "
                     "repository")


def category_of(rule: str) -> str:
    parts = rule.split("-")
    return parts[1][:1] if len(parts) > 1 and parts[1] else "?"


def human_title(rule: str, catalog: dict) -> str:
    entry = catalog.get(rule)
    if not entry:
        return "Unresolved architectural check"
    return entry.get("title") or "Architectural check without a catalog description"


def human_summary(rule: str, catalog: dict) -> str:
    entry = catalog.get(rule)
    if not entry:
        return ("The installed rule catalog does not define the check that produced "
                "this finding. The code cannot be judged from this result; treat it as "
                "a reporting defect and keep the original evidence.")
    return entry.get("summary") or "The catalog does not describe what this check means."


def human_fix(rule: str, catalog: dict) -> str:
    entry = catalog.get(rule)
    if not entry:
        return ("Do not change code from this finding. Correct the catalog or tool "
                "version, restore the authoritative definition, and run the check again.")
    return entry.get("fix") or "The catalog does not provide a remedy for this check."


def plural(count: int, word: str) -> str:
    return f"{count} {word}{'' if count == 1 else 's'}"


def expand_required(catalog: dict, level: str) -> set[str]:
    levels = catalog.get("levels") or {}
    rules = catalog.get("rules") or []

    def expand(requirement: str, seen: set[str]) -> set[str]:
        if requirement in levels and requirement not in seen:
            seen.add(requirement)
            found: set[str] = set()
            for child in levels[requirement].get("requires") or []:
                found |= expand(child, seen)
            return found
        if requirement.endswith("*"):
            prefix = requirement[:-1]
            return {r["id"] for r in rules
                    if category_of(r["id"]) == prefix
                    or r["id"].split("-")[-1].startswith(prefix)}
        return {requirement}

    return expand(level, set())


def load_triage(path: Path | None) -> tuple[dict, dict, list[str]]:
    if path is None or not path.is_file():
        return {}, {}, []
    data = load_json(path, "triage file")
    by_rule: dict[str, dict] = {}
    by_fingerprint: dict[str, dict] = {}
    notes: list[str] = []
    for entry in data.get("triage") or []:
        if not isinstance(entry, dict):
            raise InputError("triage entries must be objects")
        rule = entry.get("rule")
        classification = entry.get("classification")
        if not rule or classification not in CLASSIFICATIONS:
            raise InputError(f"triage entry invalid: {entry!r}; classification must be one "
                             f"of {', '.join(CLASSIFICATIONS)}")
        if classification != "defect" and not entry.get("reason"):
            raise InputError(f"triage entry for {rule} needs a reason")
        by_rule[rule] = entry
        if entry.get("note"):
            notes.append(f"{rule}: {entry['note']}")
    for entry in data.get("findings") or []:
        if not isinstance(entry, dict) or not entry.get("fingerprint"):
            raise InputError("triage finding entries need a fingerprint")
        classification = entry.get("classification")
        if classification not in CLASSIFICATIONS:
            raise InputError(f"triage finding {entry['fingerprint']} has invalid "
                             f"classification")
        by_fingerprint[entry["fingerprint"]] = entry
    return by_rule, by_fingerprint, notes


def load_manual_evidence(root: Path, path: str | None) -> dict[str, dict]:
    candidate = Path(path) if path else root / ".acima/manual-evidence.json"
    if not candidate.is_file():
        return {}
    data = load_json(candidate, "manual evidence")
    today = date.today().isoformat()
    accepted: dict[str, dict] = {}
    for entry in data.get("evidence") or []:
        rule = entry.get("rule")
        if not rule:
            continue
        expiry = entry.get("expires")
        if expiry and expiry < today:
            continue
        accepted[rule] = entry
    return accepted


def module_for(path: str, units: list[dict]) -> str:
    normalised = path.replace("\\", "/")
    best = None
    best_length = -1
    for unit in units:
        for declared in unit.get("paths") or []:
            prefix = declared.replace("\\", "/").rstrip("/")
            if (normalised == prefix or normalised.startswith(prefix + "/")) \
                    and len(prefix) > best_length:
                best = unit.get("id") or unit.get("module")
                best_length = len(prefix)
    if best:
        return str(best)
    parts = [part for part in normalised.split("/") if part]
    if len(parts) >= 2 and parts[0] in ("src", "lib", "apps", "packages", "services"):
        return parts[1]
    return parts[0] if parts else "unknown"


def prepare(root: Path, report: dict, catalog_rules: dict, config: dict | None,
            triage_rules: dict, triage_fingerprints: dict, waivers: dict[str, dict],
            baseline_fingerprints: set[str], scope: str = "current",
            findings_override: list[dict] | None = None) -> dict:
    units = (config or {}).get("units") or []
    findings = findings_override if findings_override is not None \
        else report.get("findings") or []
    statuses_present = any("status" in finding for finding in findings)
    groups: dict[tuple[str, str], dict] = {}
    for finding in findings:
        rule = finding.get("rule") or "unknown"
        fingerprint = finding.get("fingerprint") or ""
        override = triage_fingerprints.get(fingerprint) or triage_rules.get(rule) or {}
        classification = override.get("classification") or "defect"
        cluster = str(override.get("cluster") or "")
        severity = finding.get("severity") or "error"
        key = (rule, classification, cluster, severity, scope)
        group = groups.setdefault(key, {
            "rule": rule,
            "classification": classification,
            "scope": scope,
            "title": override.get("label") or human_title(rule, catalog_rules),
            "summary": human_summary(rule, catalog_rules),
            "fix": human_fix(rule, catalog_rules),
            "count": 0,
            "paths": [],
            "modules": Counter(),
            "fingerprints": [],
            "waived": 0,
            "new": 0,
            "severity": severity,
            "reason": override.get("reason") or "",
            "owner": override.get("owner") or "",
            "known": rule in catalog_rules,
            "unresolved": rule not in catalog_rules,
            "candidate": False,
        })
        if finding.get("classification") == "candidate":
            group["candidate"] = True
        group["count"] += 1
        group["paths"].append(finding.get("path") or "")
        group["modules"][module_for(finding.get("path") or "", units)] += 1
        group["fingerprints"].append(fingerprint)
        if fingerprint in waivers:
            group["waived"] += 1
        if finding.get("status") == "new":
            group["new"] += 1

    catalog_entry = lambda rule: catalog_rules.get(rule) or {}
    for group in groups.values():
        rule = group["rule"]
        entry = catalog_entry(rule)
        new_count = group["new"]
        if not new_count and not statuses_present and group["classification"] == "defect":
            # Reports without per-finding status only expose the aggregate count. Treat it
            # as new for defect groups; that is the conservative reading.
            new_count = report.get("newFindings") or 0
        if group["unresolved"] or group["candidate"]:
            group["priority"] = "Review"
        elif group["classification"] != "defect":
            group["priority"] = "Review"
        elif new_count:
            group["priority"] = "High"
        elif entry.get("automation") == "manual":
            group["priority"] = "Review"
        elif rule in HIGH_IMPACT:
            group["priority"] = "High"
        elif group["severity"] in ("warning", "info"):
            group["priority"] = "Low"
        else:
            group["priority"] = "Medium"
        if group["unresolved"]:
            group["impact"] = ("The meaning of this result is unknown, so it cannot support "
                               "a claim about the code or a recommendation to change it.")
        else:
            group["impact"] = (
                ARTIFACT_IMPACT if group["classification"] == "detector-artifact"
                else REVIEW_IMPACT if group["classification"] in
                ("review", "tooling-limitation")
                else CATEGORY_IMPACT.get(category_of(rule), ""))
        if group["unresolved"]:
            group["action"] = group["fix"]
        elif group["classification"] == "defect":
            group["action"] = group["fix"] or (
                "Correct the dependency or ownership problem at the named paths.")
        elif group["classification"] == "detector-artifact":
            group["action"] = ("Report the detector problem to the ACIMA maintainers with a "
                               "minimal fixture; do not rename or restructure working code "
                               "to satisfy the match.")
        else:
            group["action"] = ("Review the listed occurrences with the module owner and "
                               "classify each one before changing code.")
        if group["unresolved"]:
            group["confidence"] = ("Unresolved — the installed catalog does not define this "
                                    "check; this is a reporting defect, not an architectural "
                                    "conclusion.")
        elif group["classification"] == "detector-artifact":
            group["confidence"] = ("Confirmed detector artefact — the match does not describe "
                                    "a defect in the code.")
        elif group["classification"] in ("review", "tooling-limitation"):
            group["confidence"] = ("Requires human review — the available evidence cannot "
                                    "settle whether this is a defect.")
        elif group["candidate"]:
            group["confidence"] = ("Candidate requiring review — the automated check found a "
                                    "pattern, but semantic meaning and ownership still need "
                                    "confirmation.")
        elif entry.get("automation") == "manual":
            group["confidence"] = ("Manual review required — this check needs evidence the "
                                    "automated analysis cannot provide.")
        else:
            group["confidence"] = ("Confirmed by the automated check at the recorded "
                                    "locations.")
        group["modules"] = dict(group["modules"])
        group["paths"] = sorted(set(path for path in group["paths"] if path))

    ordered = sorted(groups.values(), key=lambda g: (
        PRIORITIES.index(g["priority"]),
        0 if g["classification"] == "defect" else 1,
        g["count"]))
    return {"groups": ordered, "all": groups}


def overall_status(report: dict, groups: list[dict], missing_required: list[str],
                   claim: dict | None, new_findings: int) -> str:
    if not report:
        return "Not assessed"
    if not report.get("sourceFiles") or not report.get("execution"):
        return "Assessment incomplete"
    if any(group.get("unresolved") for group in groups):
        return "Assessment incomplete"
    if new_findings:
        return "Significant issues found"
    unwaived_defects = sum(g["count"] - g["waived"] for g in groups
                           if g["classification"] == "defect"
                           and g.get("scope") == "current")
    if unwaived_defects:
        return "Partially aligned"
    if report.get("findings"):
        return "Baseline established"
    if missing_required:
        return "Assessment incomplete"
    if claim and claim.get("current") is True \
            and str(claim.get("claim", "")).upper().startswith("FULL") \
            and claim.get("level") in (None, report.get("level")) \
            and not claim.get("blockingFindings"):
        return "Verified"
    return "Assessment incomplete"


def reason_summary(report: dict, waived_total: int, artifacts: int, new: int) -> str:
    total = len(report.get("findings") or [])
    if not total:
        return "no findings from the rules that executed"
    parts = [f"{plural(total, 'finding')} in the current run"]
    parts.append(f"{new} new" if new else "none new")
    if artifacts:
        parts.append(f"{artifacts} produced by the detector rather than by the code")
    return ", ".join(parts)


def reconciliation(initial: dict | None, baseline: dict | None,
                   catalog_rules: dict) -> list[str]:
    if not initial or not baseline:
        return []
    initial_findings = initial.get("findings") or []
    initial_fps = {f.get("fingerprint") for f in initial_findings}
    frozen = set(baseline.get("fingerprints") or [])
    only_initial = [f for f in initial_findings
                    if f.get("fingerprint") not in frozen]
    only_baseline = sorted(frozen - initial_fps)
    lines = [
        f"The first measurement reported **{len(initial_findings)}** findings; the frozen "
        f"baseline contains **{len(frozen)}** fingerprints.",
    ]
    if only_initial:
        counts = Counter(f.get("rule") or "unknown" for f in only_initial)
        detail = ", ".join(
            f"{human_title(rule, catalog_rules)} ×{count}"
            for rule, count in sorted(counts.items()))
        lines.append(f"The difference is {len(only_initial)} finding(s) present in the "
                     f"first run and not in the frozen baseline: {detail}. The baseline is "
                     f"the frozen measurement; the first run is the before photograph.")
    elif only_baseline:
        lines.append(f"{len(only_baseline)} baseline fingerprint(s) are absent from the "
                     f"first report; the baseline is still the authority for what was "
                     f"frozen, and the difference is reported rather than hidden.")
    else:
        lines.append("The two runs agree on the frozen set; only counts and source scope "
                     "may differ.")
    if initial.get("sourceFiles") and baseline.get("sourceFiles") \
            and initial["sourceFiles"] != baseline["sourceFiles"]:
        lines.append(f"Source scope differs: the first run saw "
                     f"{initial['sourceFiles']} files, the baseline records "
                     f"{baseline['sourceFiles']}. Reconcile the scope before comparing "
                     f"counts across time.")
    return lines


def completed_evidence(root: Path, config: dict | None, report: dict, baseline: dict | None,
                       waivers: dict[str, dict], triage_notes: list[str],
                       ci_files: list[Path]) -> list[str]:
    items: list[str] = []
    if report.get("sourceFiles"):
        items.append(f"Repository structure inspected — {report['sourceFiles']} source files "
                     f"were in scope for this run.")
    units = (config or {}).get("units") or []
    if units:
        items.append(f"Architecture units identified — {len(units)} units are declared in "
                     f"`acima.config.json`.")
    if report.get("findings") is not None:
        measured = (f"{len(baseline.get('fingerprints') or [])} at adoption"
                    if baseline else "in this run")
        items.append(f"Existing findings measured — {measured}; this run contains "
                     f"{len(report.get('findings') or [])}.")
    if baseline:
        frozen = len(baseline.get("fingerprints") or [])
        stamp = baseline.get("generatedOn") or "an unrecorded date"
        items.append(f"Baseline established — {frozen} fingerprints were frozen on {stamp}.")
    if waivers:
        owners = {w.get("owner") for w in waivers.values()}
        items.append(f"Exceptions recorded — {len(waivers)} waivers, "
                     f"{'owned' if owners - {'unassigned', '', None} else 'not yet owned'}.")
    if ci_files:
        items.append("Enforcement configuration exists — "
                     + ", ".join(f"`{path.name}`" for path in ci_files)
                     + " (a configured gate is not an observed gate).")
    if triage_notes:
        items.append(f"Finding triage recorded — {plural(len(triage_notes), 'decision')} separate "
                     f"defects from detector and review items.")
    return items


def limitations(report: dict, groups: list[dict], required: set[str],
                missing_required: list[str], manual_evidence: dict[str, dict],
                waivers: dict[str, dict], catalog_rules: dict, claim: dict | None,
                ci_files: list[Path], ci_observed: str | None,
                baseline: dict | None, artifacts: int) -> list[str]:
    items: list[str] = []
    unexecuted = sorted(rule for rule, value in (report.get("execution") or {}).items()
                        if value.get("executed") is False)
    if unexecuted:
        names = ", ".join(human_title(rule, catalog_rules) for rule in unexecuted)
        items.append(f"{plural(len(unexecuted), 'check')} did not run: {names}. A check that "
                     f"did not run is not a check that passed.")
    if missing_required:
        names = ", ".join(human_title(rule, catalog_rules) for rule in missing_required)
        items.append(f"At the declared level, these checks still need executed evidence or a "
                     f"recorded manual review: {names}. Without them the assessment cannot be "
                     f"full.")
    if manual_evidence:
        items.append(f"Manual evidence is recorded for {len(manual_evidence)} rule(s); its "
                     f"review date and expiry still apply.")
    today = date.today()
    expired = [w for w in waivers.values()
               if w.get("expires") and w["expires"] < today.isoformat()]
    horizon = (today + timedelta(days=30)).isoformat()
    soon = [w for w in waivers.values()
            if w.get("expires") and today.isoformat() <= w["expires"] <= horizon]
    later = sorted(w["expires"] for w in waivers.values()
                   if w.get("expires") and w["expires"] > horizon)
    if expired:
        items.append(f"{plural(len(expired), 'waiver')} have expired and should already be "
                     f"unresolved exceptions. They no longer justify leaving the related "
                     f"architecture problem unaddressed.")
    if soon:
        items.append(f"{plural(len(soon), 'waiver')} expire within 30 days; renewal is an "
                     f"individual decision, never a bulk action.")
    if later:
        items.append(f"{plural(len(waivers), 'waiver')} are in force; the earliest expiry is "
                     f"{later[0]}. Renewal is an individual decision, never a bulk action.")
    if ci_files and not ci_observed:
        items.append("The CI gate has not been observed running in this summary; a workflow "
                     "file proves configuration, not enforcement.")
    if ci_observed:
        items.append(f"CI observation supplied: {ci_observed}.")
    if not claim:
        items.append("No full-conformance claim was supplied, so this summary does not "
                     "assert conformance at any level.")
    elif not str(claim.get("claim", "")).upper().startswith("FULL"):
        items.append(f"The supplied claim is **{claim.get('claim')}**, not full "
                     f"conformance.")
    elif claim.get("current") is not True:
        state = claim.get("currentness") or "currentness not recorded"
        items.append(f"The supplied full-conformance claim is not current (**{state}**). "
                     f"Historical or stale evidence explains how the repository evolved; "
                     f"it does not establish current conformance. Take a fresh measurement "
                     f"at the current commit and recompute the claim before repeating it.")
    if artifacts:
        items.append(f"{plural(artifacts, 'finding')} are detector artefacts, not architectural "
                     f"defects. They remain in the gate so the detector problem stays "
                     f"visible; they are not evidence that the code is wrong.")
    review_groups = [g for g in groups if g["classification"] == "review"]
    if review_groups:
        items.append(f"{plural(len(review_groups), 'group')} still need human classification; they "
                     f"are reported as **Review**, not counted as confirmed defects.")
    if baseline and report.get("findings") is not None \
            and len(baseline.get("fingerprints") or []) != len(report.get("findings") or []):
        items.append(f"The current run has {len(report.get('findings') or [])} findings; the "
                     f"baseline records {len(baseline.get('fingerprints') or [])}. A passing "
                     f"gate means no new findings, not the same set of findings.")
    if baseline and report.get("sourceFiles") and baseline.get("sourceFiles") \
            and report["sourceFiles"] != baseline["sourceFiles"]:
        items.append(f"Source scope changed: the baseline was measured over "
                     f"{baseline['sourceFiles']} files, this run over "
                     f"{report['sourceFiles']}. Compare counts only after reconciling scope.")
    if not report.get("sourceFiles"):
        items.append("The run discovered no source files; zero findings from zero files is "
                     "not a pass.")
    return items


def next_actions(groups: list[dict], missing_required: list[str], required: set[str],
                 catalog_rules: dict, manual_evidence: dict[str, dict],
                 ci_files: list[Path], ci_observed: str | None) -> list[dict]:
    actions: list[dict] = []

    def defect_action(group: dict) -> dict:
        modules = sorted(group["modules"])
        where = ", ".join(modules[:4]) + (f" (+{len(modules) - 4} more)" if len(modules) > 4
                                         else "")
        return {
            "kind": "defect",
            "rule": group["rule"],
            "title": group["title"],
            "action": group["action"],
            "reason": group["impact"],
            "where": where or "the paths in the technical report",
            "done": "The report no longer contains this finding.",
            "verification": ("Run the same check again and confirm the finding is gone and "
                             "the gate reports no new findings."),
            "judgement": len(modules) > 3,
            "count": group["count"],
        }

    new_groups = [g for g in groups if g["classification"] == "defect" and g["new"]]
    high = [g for g in groups if g["classification"] == "defect"
            and g["priority"] == "High"]
    first_pool = new_groups or high
    # Among equally important boundary defects, take the smallest slice first: it is the
    # cheapest change that proves the remedy and keeps the gate green.
    if first_pool:
        actions.append(defect_action(sorted(first_pool, key=lambda g: g["count"])[0]))
    seen = {actions[0]["rule"]} if actions else set()
    for group in groups:
        if group["classification"] != "defect" or group["rule"] in seen:
            continue
        seen.add(group["rule"])
        actions.append(defect_action(group))
        if len(actions) >= 5:
            break
    artifact_groups = [g for g in groups if g["classification"] == "detector-artifact"]
    if artifact_groups:
        total = sum(g["count"] for g in artifact_groups)
        actions.append({
            "kind": "tooling",
            "rule": ", ".join(g["rule"] for g in artifact_groups),
            "title": f"Correct {total} detector artefact(s), not the code",
            "action": ("File the detector defect upstream with a minimal reproduction; "
                       "leave the working code as it is."),
            "reason": ("These matches come from how the detector resolves names or paths, "
                       "not from a boundary the code actually crosses."),
            "where": "the ACIMA enforcer that produced this report",
            "done": "The corrected detector no longer reports these matches, and its fixture "
                    "proves both the detection and the correction.",
            "verification": "Run the same report after the detector fix; the artefact count "
                            "falls without any application change.",
            "judgement": True,
            "count": total,
        })
    if missing_required:
        actions.append({
            "kind": "verification",
            "rule": ", ".join(missing_required),
            "title": "Complete the evidence the level requires",
            "action": ("Record native or human evidence for the rules this environment "
                       "cannot execute, or run them where the toolchain exists."),
            "reason": ("Until every required rule has executed evidence, no conformance "
                       "claim can be more than partial."),
            "where": "`.acima/manual-evidence.json` or the matching CI runner",
            "done": "Every required rule at the declared level is executed or has accepted "
                    "evidence.",
            "verification": "`acima.py claim --report <run> --level <L> --require full` "
                            "exits 0.",
            "judgement": True,
            "count": len(missing_required),
        })
    if ci_files and not ci_observed:
        actions.append({
            "kind": "verification",
            "rule": "gate",
            "title": "Observe the gate on a real change",
            "action": ("Open a throwaway change with one forbidden dependency and confirm "
                       "the workflow fails, then revert it."),
            "reason": ("A workflow file is configuration; only an observed failing run "
                       "proves the gate is enforcing."),
            "where": "the repository's CI provider",
            "done": "A red run names the expected rule, and the reverted change is green.",
            "verification": "Link the run in `docs/acima/STATUS.md`.",
            "judgement": True,
            "count": 1,
        })
    return actions


def render_markdown(context: dict) -> str:
    report = context["report"]
    groups = context["groups"]
    status = context["status"]
    lines: list[str] = [
        "# ACIMA Repository Assessment",
        "",
        f"**Repository:** {context['repository']}",
        f"**Assessment date:** {context['date']}",
        f"**Architecture:** {context['architecture']}",
        f"**Assessment status:** **{status}** — {STATUS_DETAIL[status]}",
        "",
        "**How to read this:** a *module* is a declared unit in `acima.config.json`; a *contract* "
        "is the interface other modules are allowed to use; the *baseline* is the frozen snapshot "
        "of existing findings; a *waiver* is an owned, expiring exception. The explanation comes "
        "first. Internal check identifiers and fingerprints remain in the technical report; you "
        "do not need them to understand a finding or decide what to do.",
        "",
        "## 1. Overall result",
        "",
    ]
    lines.append(f"{context['reason']}.")
    if context["new"]:
        lines.append(f"\nThe gate reports **{context['new']}** new finding(s) outside the "
                     f"frozen baseline.")
    if context["baseline"]:
        lines.append("")
        lines.append(f"The frozen baseline contains **{context['baseline_count']}** "
                     f"fingerprints measured over {context['baseline_scope']} source files. "
                     f"{plural(context['waived'], 'finding')} carry owned waivers. This run contains "
                     f"**{context['current_total']}** findings"
                     + (f", of which {context['artifacts']} are detector artefacts"
                        if context["artifacts"] else "") + ".")
    lines.append("")
    lines.append("This is a summary of evidence, not a score. A clean gate means no new "
                 "findings at the declared level; it does not mean the architecture is "
                 "good.")
    lines += ["", "## 2. What this means", ""]
    lines.extend(context["meaning"])
    lines += ["", "## 3. Key findings", ""]
    if not groups:
        lines.append("The rules that executed produced no findings. That is only meaningful "
                     "because the run discovered source files; see the verification limits "
                     "below.")
    else:
        lines += ["| What was found | Why it matters | Evidence | Recommended improvement | Confidence |",
                  "|---|---|---|---|---|"]
        for group in groups[:8]:
            count_word = "occurrences" if group["count"] != 1 else "occurrence"
            found = f"**{group['title']}.** {group['summary']} ({group['count']} {count_word})"
            if group.get("scope") == "baseline":
                found += " Retained from the baseline for context."
            modules = sorted(group["modules"])
            areas = f"{plural(len(modules), 'module')}: " + ", ".join(modules[:4])
            if len(modules) > 4:
                areas += f" +{len(modules) - 4} more"
            paths = group.get("paths") or []
            if paths:
                areas += f". Example: `{paths[0]}`"
                if len(paths) > 1:
                    areas += f" (+{len(paths) - 1} more paths)"
            action = group["action"]
            confidence = group["confidence"]
            lines.append(f"| {found} | {group['impact']} | {areas} | {action} | "
                         f"{confidence} |")
        lines += ["", "Internal check identifiers, execution evidence and every affected "
                      "path are retained in §7 and the technical report. They are not needed "
                      "to read the findings above."]
    lines += ["", "## 4. What should happen next?", ""]
    actions = context["actions"]
    if actions:
        first = actions[0]
        lines += [f"**{first['title']}.** {first['action']}", "",
                  f"- **Why:** {first['reason']}",
                  f"- **Where:** {first['where']}",
                  f"- **Done when:** {first['done']}",
                  f"- **Verified by:** {first['verification']}",
                  f"- **Needs human judgement:** {'yes' if first['judgement'] else 'no'}"]
        if len(actions) > 1:
            lines += ["", "Then, in order:", ""]
            for index, action in enumerate(actions[1:5], start=2):
                lines.append(f"{index}. **{action['title']}** — {action['action']}")
    else:
        lines.append("No corrective action is supported by this run. Keep the gate running "
                     "on every change and complete the missing evidence below before making "
                     "a conformance claim.")
    lines += ["", "## 5. What has already been completed?", ""]
    lines.extend(f"- {item}" for item in context["completed"]) if context["completed"] \
        else lines.append("- Nothing is evidenced yet.")
    lines += ["", "## 6. What has not been verified?", ""]
    lines.extend(f"- {item}" for item in context["limitations"])
    lines += ["", "## 7. Supporting technical details", ""]
    lines.append(f"- Full run: `{context['report_path']}` — every finding with rule, path, "
                 f"line, fingerprint and new/pre-existing status.")
    if context["initial_path"]:
        lines.append(f"- First measurement: `{context['initial_path']}` — the before "
                     f"photograph used to reconcile the baseline count.")
    if context["baseline_path"]:
        lines.append(f"- Frozen baseline: `{context['baseline_path']}`.")
    if context["waiver_path"]:
        lines.append(f"- Waivers: `{context['waiver_path']}` — ownership, reason, expiry.")
    if context["triage_path"]:
        lines.append(f"- Triage: `{context['triage_path']}` — which matches are defects, "
                     f"detector artefacts, or awaiting review.")
    if context["plan_path"]:
        lines.append(f"- Adoption plan: `{context['plan_path']}`.")
    if context["status_path"]:
        lines.append(f"- Status dashboard: `{context['status_path']}`.")
    lines += ["", f"Rule meanings and remedies: `{context['catalog_path']}` and the rule "
                  f"pages in the standard repository.", ""]
    return "\n".join(lines)


def build(args: argparse.Namespace) -> dict:
    root = Path(args.root)
    report_path = Path(args.report)
    if not root.is_dir():
        raise InputError(f"target is not a directory: {root}")
    report = load_json(report_path, "enforcement report")
    catalog_path = resolve_catalog(args.catalog)
    catalog = load_json(catalog_path, "rule catalog")
    catalog_rules = {rule["id"]: rule for rule in catalog.get("rules") or []}
    try:
        config = load_json(root / "acima.config.json", "unit map")
    except InputError:
        config = None

    baseline_path = root / ".acima/baseline.json"
    baseline = load_json(baseline_path, "baseline") if baseline_path.is_file() else None
    waiver_path = root / ((config or {}).get("waivers") or ".acima/waivers.json")
    waivers: dict[str, dict] = {}
    if waiver_path.is_file():
        waiver_data = load_json(waiver_path, "waiver file")
        for entry in waiver_data.get("waivers") or []:
            if entry.get("fingerprint"):
                waivers[entry["fingerprint"]] = entry
    baseline_fingerprints = set((baseline or {}).get("fingerprints") or [])

    triage_path = Path(args.triage) if args.triage else root / ".acima/triage.json"
    triage_rules, triage_fingerprints, triage_notes = load_triage(
        triage_path if triage_path.is_file() else None)
    manual = load_manual_evidence(root, args.manual_evidence)

    level = report.get("level") or (config or {}).get("level") or "L1"
    required = expand_required(catalog, level)
    executed = {rule for rule, value in (report.get("execution") or {}).items()
                if value.get("executed") is True}
    missing_required = sorted(rule for rule in required
                              if rule not in executed and rule not in manual)

    current_fingerprints = {f.get("fingerprint") for f in report.get("findings") or []}
    initial_report = (load_json(Path(args.initial_report), "initial report")
                      if args.initial_report else None)
    baseline_findings = [f for f in (initial_report or {}).get("findings") or []
                         if f.get("fingerprint") in baseline_fingerprints
                         and f.get("fingerprint") not in current_fingerprints]
    groups = prepare(root, report, catalog_rules, config, triage_rules,
                     triage_fingerprints, waivers, baseline_fingerprints,
                     scope="current")["groups"]
    if baseline_findings:
        groups += prepare(root, report, catalog_rules, config, triage_rules,
                          triage_fingerprints, waivers, baseline_fingerprints,
                          scope="baseline", findings_override=baseline_findings)["groups"]
        groups.sort(key=lambda g: (PRIORITIES.index(g["priority"]),
                                   0 if g["classification"] == "defect" else 1,
                                   g["count"]))
    artifacts = sum(group["count"] for group in groups
                    if group["classification"] == "detector-artifact")
    waived_total = len(waivers)
    current_total = len(report.get("findings") or [])
    new_findings = report.get("newFindings")
    if new_findings is None:
        new_findings = sum(1 for f in report.get("findings") or []
                           if f.get("status") == "new")
    status = overall_status(report, groups, missing_required, None, new_findings)

    ci_files = []
    workflows = root / ".github/workflows"
    if workflows.is_dir():
        ci_files = sorted(path for path in workflows.iterdir()
                          if path.suffix in (".yml", ".yaml")
                          and "acima" in path.name.lower())

    architecture = args.architecture
    plan_path = root / "docs/acima/adoption-plan.md"
    if not architecture and plan_path.is_file():
        lines = plan_path.read_text(encoding="utf-8", errors="replace").splitlines()
        for index, line in enumerate(lines):
            if "Architecture family in use:" not in line:
                continue
            architecture = line.split(":", 1)[1].strip()
            for continuation in lines[index + 1:]:
                if not continuation.strip() or continuation.lstrip().startswith("-"):
                    break
                architecture += " " + continuation.strip()
            break
    architecture = architecture or "not recorded"

    actions = next_actions(groups, missing_required, required, catalog_rules, manual,
                           ci_files, args.ci_observed)
    baseline_count = len((baseline or {}).get("fingerprints") or [])
    meaning: list[str] = []
    units = (config or {}).get("units") or []
    meaning.append(
        f"{root.name} contains {report.get('sourceFiles') or 0} source files organised "
        f"into {plural(len(units), 'declared module')}. The declared level is **{level}**, and the "
        f"architecture recorded for it is **{architecture.rstrip('.')}**.")
    defects = [group for group in groups if group["classification"] == "defect"]
    if defects:
        top = defects[0]
        meaning.append(
            f"The most consequential issue is **{top['title']}** — "
            f"{plural(top['count'], 'occurrence')} across "
            f"{plural(len(top['modules']), 'module')}. {top['impact']}")
    elif groups:
        meaning.append(
            "The remaining findings are not reported as architectural defects: they are "
            "detector or review items, and they are kept visible so the tooling problem "
            "is not mistaken for a code problem.")
    else:
        meaning.append("The executed rules found no boundary violations. The limits in §6 "
                       "still decide what that result proves.")
    if missing_required:
        meaning.append(
            f"The gate reports {plural(new_findings, 'new finding')}, but "
            f"{plural(len(missing_required), 'required rule')} did not execute. The repository is therefore not verified at "
            f"**{level}**, whatever the finding count says; a passing baseline only shows "
            f"that no new findings appeared among the rules that did run.")
    else:
        meaning.append(
            f"The gate reports {new_findings} new finding(s) against a baseline of "
            f"{baseline_count}. A passing baseline shows that the recorded set did not "
            f"grow; it is not a statement that the architecture is compliant.")

    claim = None
    if args.claim:
        claim = load_json(Path(args.claim), "claim")
        status = overall_status(report, groups, missing_required, claim, new_findings)

    repository = report.get("repository") or root.name
    context = {
        "repository": repository,
        "root": root,
        "report": report,
        "date": args.date or date.today().isoformat(),
        "architecture": architecture,
        "status": status,
        "reason": reason_summary(report, waived_total, artifacts, new_findings),
        "current_total": current_total,
        "new": new_findings,
        "waived": waived_total,
        "artifacts": artifacts,
        "baseline": baseline,
        "baseline_count": baseline_count,
        "baseline_scope": (baseline or {}).get("sourceFiles") or "unrecorded",
        "meaning": meaning,
        "groups": groups,
        "actions": actions,
        "completed": completed_evidence(root, config, report, baseline, waivers,
                                        triage_notes, ci_files),
        "limitations": limitations(report, groups, required, missing_required, manual,
                                    waivers, catalog_rules, claim, ci_files,
                                    args.ci_observed, baseline, artifacts),
        "report_path": report_path,
        "initial_path": args.initial_report,
        "baseline_path": baseline_path if baseline else None,
        "waiver_path": waiver_path if waivers else None,
        "triage_path": triage_path if triage_rules or triage_fingerprints else None,
        "plan_path": plan_path if plan_path.is_file() else None,
        "status_path": (root / "docs/acima/STATUS.md")
        if (root / "docs/acima/STATUS.md").is_file() else None,
        "catalog_path": catalog_path,
        "level": level,
        "required": sorted(required),
        "missingRequired": missing_required,
        "claim": claim,
        "reconciliation": reconciliation(initial_report, baseline, catalog_rules),
    }
    if args.initial_report:
        context["limitations"].extend(context["reconciliation"])
    return context


def to_json(context: dict) -> dict:
    return {
        "repository": context["repository"],
        "assessmentDate": context["date"],
        "architecture": context["architecture"],
        "status": context["status"],
        "level": context["level"],
        "sourceFiles": context["report"].get("sourceFiles"),
        "newFindings": context["new"],
        "baselineFingerprints": context["baseline_count"],
        "waivedFindings": context["waived"],
        "detectorArtifacts": context["artifacts"],
        "missingRequired": context["missingRequired"],
        "groups": [
            {key: group[key] for key in (
                "rule", "classification", "scope", "title", "count", "priority", "waived",
                "new", "modules", "paths", "fingerprints", "impact", "action",
                "summary", "confidence", "unresolved", "candidate", "reason", "owner")}
            for group in context["groups"]
        ],
        "nextActions": context["actions"],
        "completed": context["completed"],
        "limitations": context["limitations"],
        "claim": context["claim"],
        "claimState": (context["claim"] or {}).get("currentness"),
        "claimCurrent": (context["claim"] or {}).get("current"),
        "reconciliation": context["reconciliation"],
        "evidence": {
            "report": str(context["report_path"]),
            "initialReport": str(context["initial_path"]) if context["initial_path"] else None,
            "baseline": str(context["baseline_path"]) if context["baseline_path"] else None,
            "waivers": str(context["waiver_path"]) if context["waiver_path"] else None,
            "triage": str(context["triage_path"]) if context["triage_path"] else None,
            "plan": str(context["plan_path"]) if context["plan_path"] else None,
            "catalog": str(context["catalog_path"]),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render the two-level ACIMA adoption report from an enforcement report")
    parser.add_argument("--root", default=".", help="target repository root")
    parser.add_argument("--report", required=True,
                        help="enforcer JSON report (the run artefact)")
    parser.add_argument("--initial-report",
                        help="the first measurement, for baseline-count reconciliation")
    parser.add_argument("--catalog", help="rule catalog (defaults to the pinned catalog)")
    parser.add_argument("--triage", help="triage file (default: <root>/.acima/triage.json)")
    parser.add_argument("--manual-evidence", help="manual evidence file")
    parser.add_argument("--claim", help="claim JSON produced by `acima.py claim --format json`")
    parser.add_argument("--architecture", help="architecture family, when no plan records it")
    parser.add_argument("--ci-observed", help="evidence that the gate ran, e.g. a run URL")
    parser.add_argument("--date", help="assessment date (default: today)")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--out", help="write to this path instead of stdout")
    args = parser.parse_args()

    try:
        context = build(args)
    except InputError as error:
        print(f"acima: summarize: {error}", file=sys.stderr)
        return 2

    text = (json.dumps(to_json(context), indent=2, sort_keys=False)
            if args.format == "json" else render_markdown(context))
    if args.out:
        output = Path(args.out)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
        print(f"acima: wrote {output}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(2)
    except Exception as error:  # noqa: BLE001 - a crash must be distinguishable from a report
        print(f"acima: summarize failed: {error}", file=sys.stderr)
        raise SystemExit(2)
