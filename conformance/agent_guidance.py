#!/usr/bin/env python3
"""Generate, update, validate and report repository-level ACIMA agent guidance.

The generator never guesses ownership or enforcement. It reads the approved map and the
implementation/verification records produced by the adoption workflow, then writes a concise
root instruction plus progressive-disclosure support documents. Existing user-authored content
is preserved; generated sections are replaceable by marker.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "tools/acima-spec/rules.json"
PROPOSAL_FILE = "docs/acima/agent-guidance-proposal.md"
RESULT_FILE = ".acima/agent-guidance.json"
SUPPORT_ROOT = "docs/architecture/acima"
ARCH_FILE = SUPPORT_ROOT + "/agent-architecture-guidance.md"
ENFORCEMENT_FILE = SUPPORT_ROOT + "/enforcement.md"
JUDGMENT_FILE = SUPPORT_ROOT + "/judgment-guidance.md"
WORKFLOW_FILE = SUPPORT_ROOT + "/architectural-workflow.md"
CONFIG_FILE = "acima.config.json"
APPROVAL_FILE = ".acima/module-map.approval.json"
ADOPTION_PROPOSAL = "docs/acima/adoption-proposal.md"
ENFORCEMENT_RECORD = "docs/acima/enforcement.json"
VERIFICATION_RECORD = "docs/acima/verification.json"
CI_RECORD = "docs/acima/ci-integration.json"
START = "<!-- acima-agent-guidance:start -->"
END = "<!-- acima-agent-guidance:end -->"
REF_START = "<!-- acima-agent-guidance-reference:start -->"
REF_END = "<!-- acima-agent-guidance-reference:end -->"
SOURCE_NAMES = (CONFIG_FILE, APPROVAL_FILE, ADOPTION_PROPOSAL, ENFORCEMENT_RECORD,
                VERIFICATION_RECORD, CI_RECORD)


class GuidanceError(ValueError):
    """The generated guidance cannot be trusted or safely updated."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> str:
    return date.today().isoformat()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise GuidanceError("cannot read %s: %s" % (path, error)) from error
    if not isinstance(value, dict):
        raise GuidanceError("%s must contain a JSON object" % path)
    return value


def catalog() -> dict:
    return _read_json(CATALOG_PATH)


def _rules() -> list[dict]:
    return [item for item in catalog().get("rules", []) if isinstance(item, dict)]


def _relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _safe_target(root: Path, relative: str) -> Path:
    value = Path(relative)
    if value.is_absolute() or ".." in value.parts:
        raise GuidanceError("guidance path escapes the repository: %s" % relative)
    return root / value


def _root_instruction_files(root: Path) -> list[str]:
    candidates = []
    for name in ("AGENTS.md", "CLAUDE.md", "GEMINI.md", "COPILOT_INSTRUCTIONS.md"):
        if (root / name).is_file():
            candidates.append(name)
    for name in (".github/copilot-instructions.md",):
        if (root / name).is_file():
            candidates.append(name)
    # Cursor's current project-rule convention; keep it as a recognized secondary mechanism.
    if (root / ".cursor/rules").is_dir():
        for path in sorted((root / ".cursor/rules").glob("*")):
            if path.is_file() and path.suffix.lower() in (".md", ".mdc", ".txt"):
                candidates.append(_relative(root, path))
    if (root / ".github/instructions").is_dir():
        for path in sorted((root / ".github/instructions").glob("*")):
            if path.is_file() and path.suffix.lower() in (".md", ".instructions.md", ".mdc"):
                candidates.append(_relative(root, path))
    return candidates


def discover(root: Path) -> dict:
    """Discover conventions without claiming that mere existence proves consumption."""
    root = root.resolve()
    root_files = _root_instruction_files(root)
    nested = []
    for path in root.rglob("*"):
        if not path.is_file() or path.name not in ("AGENTS.md", "CLAUDE.md", "GEMINI.md"):
            continue
        if any(part in {".git", "node_modules", "dist", "build", "target", ".venv"} for part in path.parts):
            continue
        relative = _relative(root, path)
        if relative not in root_files:
            nested.append(relative)
    preference = ["AGENTS.md", "CLAUDE.md", "GEMINI.md", "COPILOT_INSTRUCTIONS.md",
                  ".github/copilot-instructions.md"]
    primary = next((name for name in preference if name in root_files), None)
    convention = "root-agents" if primary == "AGENTS.md" else (
        "root-claude" if primary == "CLAUDE.md" else
        "root-gemini" if primary == "GEMINI.md" else
        "root-copilot" if primary and "copilot" in primary.lower() else
        "root-instructions" if primary else "default-root-agents")
    if not root_files and not nested:
        primary = "AGENTS.md"
        convention = "default-root-agents"
    return {
        "convention": convention,
        "primary": primary or "AGENTS.md",
        "recognized": root_files + nested,
        "rootFiles": root_files,
        "nestedFiles": nested,
        "secondary": [item for item in root_files if item != primary],
        "selectionBasis": ("Existing root-level recognized instruction file(s) were found."
                           if root_files else
                           "No root-level recognized convention was found; create AGENTS.md by default."),
        "consumptionCaveat": ("A recognized file is not proof of automatic consumption. "
                              "The repository may load it explicitly, by directory scope, or not at all."),
    }


def _module_rows(rows: list[dict]) -> list[tuple[str, str, str, str]]:
    grouped: dict[str, dict] = {}
    for unit in rows:
        module = str(unit.get("module") or unit.get("id") or "Unassigned")
        item = grouped.setdefault(module, {"contracts": [], "implementation": [], "roles": set()})
        role = str(unit.get("role") or "implementation")
        item["roles"].add(role)
        key = "contracts" if role in ("contracts", "port") else "implementation"
        item[key].extend(unit.get("paths") or [])
    return [(module, ", ".join(sorted(item["roles"])),
             ", ".join(sorted(set(item["contracts"]))) or "No contract path recorded",
             ", ".join(sorted(set(item["implementation"]))) or "No implementation path recorded")
            for module, item in sorted(grouped.items())]


def _judgment_markdown(rules: list[dict]) -> str:
    lines = [
        "# ACIMA judgment-dependent architectural guidance",
        "",
        "This file covers every requirement in the pinned catalog. Automated checks are evidence,",
        "not a replacement for the judgment below. A partly automated requirement still requires",
        "the agent to examine the code and the design decision.",
        "",
        "If evidence is missing, record the uncertainty and ask the owner. Do not invent ownership,",
        "a contract, a data owner, a lifetime or a consistency guarantee.",
        "",
    ]
    categories: dict[str, list[dict]] = {}
    for rule in rules:
        categories.setdefault(str(rule.get("id", ""))[6:7] or "?", []).append(rule)
    for category in sorted(categories):
        lines += ["## Category %s" % category, ""]
        for rule in categories[category]:
            lines += [
                "### %s — %s" % (rule.get("id"), rule.get("title", "Requirement")),
                "",
                "**Requirement:** %s" % rule.get("summary", "No summary supplied."),
                "",
                "**Automation:** %s. %s" % (
                    rule.get("automation", "not recorded"),
                    "The deterministic check must be run, but it cannot decide intent, ownership or tradeoffs."
                    if rule.get("automation") == "automated" else
                    "No complete deterministic check is recorded; use the evidence and reasoning below."),
                "",
                "**Judgment prompt:** %s" % (
                    rule.get("manualEvidence") or
                    "Decide whether the proposed change preserves this requirement in context; "
                    "inspect the affected ownership, contract, dependency and data boundaries."),
                "",
                "**Sound response:** %s" % rule.get("fix", "Explain the decision and its evidence."),
                "",
                "**Human escalation:** Ask before changing module ownership, a materially incompatible "
                "contract, a shared data owner, a composition boundary, or a consequential tradeoff.",
                "",
            ]
    return "\n".join(lines)


def _checks(state: dict, root: Path) -> dict:
    enforcement = _read_json(root / ENFORCEMENT_RECORD) if (root / ENFORCEMENT_RECORD).is_file() else {}
    verification = _read_json(root / VERIFICATION_RECORD) if (root / VERIFICATION_RECORD).is_file() else {}
    ci = _read_json(root / CI_RECORD) if (root / CI_RECORD).is_file() else {}
    enforcer = enforcement.get("enforcer") or {}
    command = enforcer.get("command")
    enforcer_path = enforcer.get("path")
    return {
        "command": command,
        "enforcerPath": enforcer_path,
        "enforcerStatus": enforcer.get("status") or enforcement.get("status") or "not recorded",
        "positive": (verification.get("positive") or {}).get("status") or "not recorded",
        "negative": (verification.get("negative") or {}).get("status") or "not recorded",
        "verificationStatus": verification.get("status") or "not recorded",
        "ciProvider": ci.get("provider"),
        "ciStatus": ci.get("status") or "not recorded",
        "ciWorkflow": ci.get("workflow"),
        "claim": ci.get("claim") or "No CI claim is recorded.",
    }


def _root_block(discovery: dict, state: dict, checks: dict, modules: list[tuple[str, str, str, str]],
                unresolved: list[str]) -> str:
    command = checks.get("command")
    enforcement_line = (
        "- Run the local architectural command: `%s`\n" % command
        if command and checks.get("enforcerStatus") in ("implemented", "preserved", "valid")
        else "- No verified local architectural command is recorded; follow the manual procedure in `%s`.\n" % ENFORCEMENT_FILE)
    module_lines = "\n".join("- **%s** — roles: %s; contracts: %s; implementation: %s" %
                             (name, roles, contracts, implementation)
                             for name, roles, contracts, implementation in modules)
    if not modules:
        module_lines = "- No approved module rows are recorded; consult the authoritative map before assigning ownership."
    unresolved_text = "\n".join("- " + item for item in unresolved) if unresolved else \
        "- No unresolved ownership decision is recorded by this workflow, but absence of a recorded decision is not approval."
    return f"""{START}
# ACIMA architectural constraints for AI coding agents

ACIMA is mandatory for changes in this repository. Architecture is defined by approved ownership,
explicit contracts and dependency direction, not merely by folders, packages, projects, namespaces,
services or deployment units.

## Authoritative sources

- Approved module map: `{CONFIG_FILE}` (approval provenance: `{APPROVAL_FILE}`).
- Adoption proposal: `{ADOPTION_PROPOSAL}`.
- Enforcement and verification: `{ENFORCEMENT_RECORD}` and `{VERIFICATION_RECORD}`.
- Full repository guidance: `{ARCH_FILE}`, `{ENFORCEMENT_FILE}`, `{JUDGMENT_FILE}`, `{WORKFLOW_FILE}`.
- CI record: `{CI_RECORD}`. {checks.get("claim")}

## Approved ownership snapshot

{module_lines}

Modules own their implementation and expose explicit contracts. Never depend on another module's
private implementation. Do not infer ownership from a folder or project name; use the authoritative
map and ask when the map does not cover the change.

## Before completing any architectural change

1. Identify the affected module, owner and public contract.
2. Identify every dependency and the owner of data, configuration, lifecycle and state.
3. Check whether the change crosses a module boundary or changes a contract, composition or data owner.
4. Load `{JUDGMENT_FILE}` and apply the relevant judgment-dependent requirement.
5. Run the relevant checks; do not weaken or bypass an architectural check to make a change pass.
6. Report actual command results. A configured CI file is not evidence that a remote run succeeded.
7. Ask the owner when ownership, a materially incompatible contract, a shared data owner, a
   composition boundary or a consequential tradeoff is unresolved.

{enforcement_line}
## Judgment and escalation

Passing an automated check does not establish compliance with judgment-dependent requirements.
Explain the evidence and the decision. Do not invent architecture. Routine work within established
boundaries should proceed autonomously; consequential architectural changes require human approval.

## Unresolved decisions recorded by adoption

{unresolved_text}

Load `{WORKFLOW_FILE}` for the proportionate decision process. This block is generated and may be
updated when the approved map, enforcement or CI changes; preserve user-authored content outside it.

{END}"""


def _read_scope(root: Path) -> dict:
    path = root / ".acima/adoption-scope.json"
    return _read_json(path) if path.is_file() else {}


def _unresolved(root: Path, state: dict) -> list[str]:
    values = []
    proposal = _read_json(root / "docs/acima/adoption-proposal.json") \
        if (root / "docs/acima/adoption-proposal.json").is_file() else {}
    for decision in proposal.get("decisions") or []:
        if isinstance(decision, dict) and decision.get("status") in (None, "pending", "open", "deferred"):
            values.append(str(decision.get("question") or decision.get("id")))
    for blocker in state.get("blockers") or []:
        values.append(str(blocker))
    return sorted(set(values))


def _source_hashes(root: Path) -> dict:
    result = {}
    for relative in SOURCE_NAMES:
        path = root / relative
        if path.is_file():
            result[relative] = _sha(path)
    result["catalog"] = _sha(CATALOG_PATH)
    return result


def proposal(root: Path, state: dict) -> dict:
    root = root.resolve()
    discovery = discover(root)
    rules = _rules()
    checks = _checks(state, root)
    config = _read_json(root / CONFIG_FILE) if (root / CONFIG_FILE).is_file() else {}
    modules = _module_rows(config.get("units") or [])
    unresolved = _unresolved(root, state)
    result = {
        "schemaVersion": 1,
        "status": "proposed",
        "generatedAt": _now(),
        "convention": discovery,
        "primaryFile": discovery["primary"],
        "supportFiles": [ARCH_FILE, ENFORCEMENT_FILE, JUDGMENT_FILE, WORKFLOW_FILE],
        "checks": checks,
        "moduleCount": len(modules),
        "judgmentRuleCount": len(rules),
        "judgmentRuleIds": [rule.get("id") for rule in rules],
        "unresolved": unresolved,
        "sourceHashes": _source_hashes(root),
        "claim": "This is proposed guidance; no instruction file has been modified.",
        "validation": {},
    }
    _write_json(root, RESULT_FILE, result)
    _write_proposal(root, result, modules, rules)
    return result


def _write_json(root: Path, relative: str, value: dict) -> Path:
    path = _safe_target(root, relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def _write_proposal(root: Path, result: dict, modules: list[tuple[str, str, str, str]], rules: list[dict]) -> None:
    discovery = result["convention"]
    lines = [
        "# Proposed AI agent architectural guidance",
        "",
        "This proposal is part of ACIMA adoption. It does not modify active instructions until approved.",
        "",
        "## Discovery",
        "",
        "- Convention: `%s`." % discovery["convention"],
        "- Primary instruction file: `%s`." % discovery["primary"],
        "- Recognized files: %s." % (", ".join(discovery["recognized"]) or "none"),
        "- %s" % discovery["consumptionCaveat"],
        "",
        "## Files",
        "",
        "- Update `%s` with the concise ACIMA block." % discovery["primary"],
        "- Create or update `%s`." % "`, `".join(result["supportFiles"]),
        "",
        "## Approved module rows",
        "",
        "| Module | Roles | Contracts | Implementation |",
        "|---|---|---|---|",
    ]
    for row in modules:
        lines.append("| %s | %s | %s | %s |" % row)
    if not modules:
        lines.append("| No approved module rows | — | — | — |")
    lines += [
        "",
        "## Judgment coverage",
        "",
        "%s catalog requirements are included, including every wholly manual and every partially automated requirement." % len(rules),
        "",
        "## Checks documented",
        "",
        "- Local command: %s" % (result["checks"].get("command") or "none verified"),
        "- Enforcement: %s; positive: %s; negative: %s." %
        (result["checks"].get("enforcerStatus"), result["checks"].get("positive"), result["checks"].get("negative")),
        "- CI: %s (%s). %s" % (result["checks"].get("ciProvider") or "none",
                               result["checks"].get("ciStatus"), result["checks"].get("claim")),
        "",
        "## Progressive disclosure",
        "",
        "The root block is operational and short. Detailed architecture, judgment requirements, enforcement and workflow guidance live in the support files. The authoritative module map is referenced, not copied.",
        "",
        "## Validation",
        "",
        "- Agent instructions are generated from the approved map and actual enforcement record.",
        "- Existing user-authored instruction content must be preserved.",
        "- All catalog rule identifiers must appear in the judgment support file.",
        "- Missing or unverifiable enforcement is described as a limitation, never invented.",
        "",
        "## Unresolved decisions",
        "",
    ]
    if result["unresolved"]:
        lines += ["- " + item for item in result["unresolved"]]
    else:
        lines.append("- None recorded; this is not proof that ownership is settled.")
    lines += ["", "Approval is required before modifying an existing instruction file.", ""]
    path = _safe_target(root, PROPOSAL_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _replace_block(existing: str, block: str, start: str = START, end: str = END) -> str:
    if start in existing and end in existing:
        before, rest = existing.split(start, 1)
        _old, after = rest.split(end, 1)
        return before + block + after
    separator = "\n\n" if existing.strip() else ""
    return existing.rstrip() + separator + block + "\n"


def _preserved_existing(original: str, updated: str) -> bool:
    if not original.strip():
        return True
    if START in original and END in original:
        before, rest = original.split(START, 1)
        _old, after = rest.split(END, 1)
        return updated.startswith(before) and updated.endswith(after)
    return original.rstrip() in updated


def _support_documents(root: Path, result: dict, modules: list[tuple[str, str, str, str]], rules: list[dict]) -> None:
    config = _read_json(root / CONFIG_FILE) if (root / CONFIG_FILE).is_file() else {}
    checks = result["checks"]
    architecture = [
        "# ACIMA architecture guidance",
        "",
        "The authoritative ownership map is `acima.config.json`. Do not infer ownership from layout.",
        "",
        "| Module | Roles | Contracts | Implementation |",
        "|---|---|---|---|",
    ]
    architecture += ["| %s | %s | %s | %s |" % row for row in modules]
    if not modules:
        architecture.append("| No approved units | — | — | — |")
    architecture += [
        "",
        "## Ownership rules",
        "",
        "- A module owns its implementation and exposes an explicit contract.",
        "- Other modules must not import or link private implementation details.",
        "- Contracts are independently consumable and contain no third-party dependency.",
        "- Dependency direction must be justified by the contract, not by convenience.",
        "- Data, configuration, lifecycle, state, side effects and composition have one accountable owner.",
        "- Approved boundaries are decisions, not suggestions; changing them needs owner review.",
        "",
        "## Profiles and applicability",
        "",
        "Apply the level and profiles recorded in the approved configuration. Do not invent an optional",
        "service-topology, library or functional profile. If the map does not establish applicability,",
        "record the uncertainty instead of silently skipping it.",
        "",
        "## Sources",
        "",
        "- `%s`" % CONFIG_FILE,
        "- `%s`" % APPROVAL_FILE,
        "- `%s`" % ADOPTION_PROPOSAL,
        "",
    ]
    enforcement = [
        "# ACIMA enforcement for agents",
        "",
        "Use actual repository commands. A configured CI workflow is not evidence that a remote run occurred.",
        "",
        "## Local command",
        "",
        "```bash",
        checks.get("command") or "# No verified local command was recorded.",
        "```",
        "",
        "- Enforcer record: `%s`; status: **%s**." % (checks.get("enforcerPath") or "not recorded",
                                                     checks.get("enforcerStatus")),
        "- Positive evidence: **%s**; controlled negative evidence: **%s**; verification: **%s**." %
        (checks.get("positive"), checks.get("negative"), checks.get("verificationStatus")),
        "",
        "## CI",
        "",
        "- Provider: **%s**; status: **%s**." % (checks.get("ciProvider") or "none", checks.get("ciStatus")),
        "- Workflow: `%s`." % (checks.get("ciWorkflow") or "not recorded"),
        "- %s" % checks.get("claim"),
        "",
        "## Agent behavior",
        "",
        "1. Discover the checks before changing code.",
        "2. Run the relevant local checks while implementing.",
        "3. Run the complete relevant architectural suite before declaring work complete.",
        "4. Investigate failures; never weaken, skip or rewrite a check merely to pass.",
        "5. Report commands that could not run and do not claim remote CI success.",
        "6. Passing automated checks does not prove judgment-dependent requirements.",
        "",
    ]
    workflow = [
        "# ACIMA architectural decision workflow for agents",
        "",
        "Use this proportionately. A trivial local edit does not need a formal document, but a boundary,",
        "contract, ownership, composition or data-owner change does.",
        "",
        "1. Identify the affected module and its responsibility.",
        "2. Identify the implementation owner.",
        "3. Identify the relevant public contract.",
        "4. Identify dependencies and their owners.",
        "5. Decide whether the change respects ACIMA boundaries.",
        "6. Evaluate data, configuration, lifecycle, state and composition implications.",
        "7. Evaluate side effects and consistency where relevant.",
        "8. Identify and run the relevant enforcement.",
        "9. Decide whether human approval is required.",
        "10. Implement within the established architecture.",
        "11. Run focused and architectural tests.",
        "12. Report the architectural implications and actual verification results.",
        "",
        "Escalate changes to ownership, incompatible contracts, new boundaries, important data owners,",
        "composition boundaries and consequential tradeoffs. Do not invent approval.",
        "",
    ]
    _write(root, ARCH_FILE, "\n".join(architecture))
    _write(root, ENFORCEMENT_FILE, "\n".join(enforcement))
    _write(root, JUDGMENT_FILE, _judgment_markdown(rules))
    _write(root, WORKFLOW_FILE, "\n".join(workflow))
    result["files"] = [result["primaryFile"], ARCH_FILE, ENFORCEMENT_FILE, JUDGMENT_FILE, WORKFLOW_FILE]
    result["moduleRows"] = len(modules)
    result["rulesCovered"] = [rule.get("id") for rule in rules]
    result["configLevel"] = config.get("level")


def _write(root: Path, relative: str, content: str) -> None:
    path = _safe_target(root, relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def apply(root: Path, state: dict) -> dict:
    root = root.resolve()
    result = _read_json(root / RESULT_FILE) if (root / RESULT_FILE).is_file() else proposal(root, state)
    discovery = result["convention"]
    rules = _rules()
    config = _read_json(root / CONFIG_FILE) if (root / CONFIG_FILE).is_file() else {}
    modules = _module_rows(config.get("units") or [])
    checks = _checks(state, root)
    unresolved = _unresolved(root, state)
    _support_documents(root, result, modules, rules)
    target = _safe_target(root, discovery["primary"])
    existing = target.read_text(encoding="utf-8") if target.is_file() else ""
    block = _root_block(discovery, state, checks, modules, unresolved)
    updated = _replace_block(existing, block)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(updated, encoding="utf-8")
    preserved = _preserved_existing(existing, updated)
    # Multiple root conventions get a short reference, not a duplicated instruction set.
    for secondary in discovery.get("secondary") or []:
        path = _safe_target(root, secondary)
        old = path.read_text(encoding="utf-8") if path.is_file() else ""
        reference = f"{REF_START}\nACIMA architectural guidance: read `{discovery['primary']}` and `{ARCH_FILE}` before changing architecture.\n{REF_END}"
        updated_secondary = _replace_block(old, reference, REF_START, REF_END)
        path.write_text(updated_secondary, encoding="utf-8")
        preserved = preserved and _preserved_existing(old, updated_secondary)
    result.update({"status": "applied", "appliedAt": _now(), "files": result.get("files", []),
                   "preservedExisting": preserved,
                   "sourceHashes": _source_hashes(root), "claim": "Generated instructions were written; agent behavior is not guaranteed."})
    result["validation"] = validate(root, result)
    _write_json(root, RESULT_FILE, result)
    _write_proposal(root, result, modules, rules)
    return result


def validate(root: Path, result: dict | None = None) -> dict:
    root = root.resolve()
    result = result or (_read_json(root / RESULT_FILE) if (root / RESULT_FILE).is_file() else {})
    discovery = result.get("convention") or discover(root)
    rules = _rules()
    problems: list[str] = []
    primary = root / discovery["primary"]
    if not primary.is_file():
        problems.append("primary instruction file is missing")
    else:
        text = primary.read_text(encoding="utf-8")
        if START not in text or END not in text:
            problems.append("primary instruction file does not contain the ACIMA block")
        for reference in (CONFIG_FILE, ARCH_FILE, ENFORCEMENT_FILE, JUDGMENT_FILE, WORKFLOW_FILE):
            if reference not in text:
                problems.append("primary instruction file does not reference %s" % reference)
    for secondary in discovery.get("secondary") or []:
        secondary_path = root / secondary
        if secondary_path.is_file() and REF_START not in secondary_path.read_text(encoding="utf-8"):
            problems.append("secondary instruction file lacks the ACIMA reference: %s" % secondary)
    judgment = root / JUDGMENT_FILE
    judgment_text = judgment.read_text(encoding="utf-8") if judgment.is_file() else ""
    missing_rules = [rule.get("id") for rule in rules if rule.get("id") not in judgment_text]
    if missing_rules:
        problems.append("judgment guidance omits catalog rules: %s" % ", ".join(missing_rules))
    for relative in (ARCH_FILE, ENFORCEMENT_FILE, WORKFLOW_FILE):
        if not (root / relative).is_file():
            problems.append("support document is missing: %s" % relative)
    if (root / CONFIG_FILE).is_file() and CONFIG_FILE not in (primary.read_text(encoding="utf-8") if primary.is_file() else ""):
        problems.append("authoritative module map is not referenced")
    checks = _checks({}, root)
    if checks.get("command") and ENFORCEMENT_FILE not in (primary.read_text(encoding="utf-8") if primary.is_file() else ""):
        problems.append("enforcement guidance is not referenced")
    return {
        "status": "valid" if not problems else "invalid",
        "checkedAt": _now(),
        "problems": problems,
        "rulesCovered": len(rules) - len(missing_rules),
        "rulesRequired": len(rules),
        "primaryFile": discovery["primary"],
        "supportFiles": [ARCH_FILE, ENFORCEMENT_FILE, JUDGMENT_FILE, WORKFLOW_FILE],
        "preservesExisting": result.get("preservedExisting"),
        "agentBehaviorGuaranteed": False,
    }


def stale(root: Path, result: dict | None = None) -> tuple[bool, list[str]]:
    root = root.resolve()
    result = result or (_read_json(root / RESULT_FILE) if (root / RESULT_FILE).is_file() else {})
    old = result.get("sourceHashes") or {}
    new = _source_hashes(root)
    changed = sorted(key for key in set(old) | set(new) if old.get(key) != new.get(key))
    return bool(changed), changed


def authorize(root: Path, state: dict) -> bool:
    scope = _read_scope(root)
    if state.get("mode") == "full":
        return True
    for item in scope.get("objectives") or []:
        if isinstance(item, dict) and item.get("id") == "agent-guidance":
            return item.get("disposition") == "approved"
    return False
