# ACIMA adoption skill

A coding-agent skill for applying ACIMA to a real repository: understand the existing architecture, propose module boundaries, measure a baseline, introduce enforcement, and leave a named owner for every exception.

## Who it is for

- **Developers and tech leads** adopting contract-isolated modules in an existing codebase.
- **Agents** acting on their behalf — Claude Code, Codex, Cursor, or any tool that reads `SKILL.md`.
- **Reviewers** who want the assessment to state what was not checked.

## Install and invoke

```bash
mkdir -p .claude/skills && cp -R ACIMA/skills/acima-adoption .claude/skills/
```

Then, with the target repository open:

```text
Use the ACIMA adoption skill to assess this repository.
Start with the required preflight and compatibility checks.
Do not modify the codebase until I have reviewed and approved the adoption plan.
```

For agents without skill discovery, point them at [`SKILL.md`](SKILL.md).

## What the workflow produces

| Step | Output |
|---|---|
| Preflight | pass/block report, calibration against the pinned catalog |
| Classification | `greenfield`, `brownfield` or `adopting`, with evidence |
| Plan | `adoption-plan.md` and `communication-plan.md`, with owners and dates |
| Baseline | a run artefact plus fingerprinted waivers for existing findings |
| First slice | one merged boundary change, gate green |
| Gate | CI failing on new `error` findings at the declared level |
| Hand-off | the team can run the gate without the agent |

## Layout

| Path | What it is |
|---|---|
| [`SKILL.md`](SKILL.md) | **authoritative** agent instructions, hard rules, workflow, stop conditions |
| `references/` | detail loaded on demand: preflight checks, greenfield, brownfield, onboarding, communication, outcomes, troubleshooting, glossary |
| `assets/` | templates: config, waiver, manual evidence, adoption plan, communication plan |
| `scripts/` | deterministic, read-only helpers: `preflight.py`, `inject_violation.py` |
| `manifest.json` | calibrated catalog hash, portable rule ids, enforcer paths, skill version |

## Boundaries worth knowing before you start

- **No service-topology workflow.** If `mode` is `service-topology` or `acima.topology.json` exists, the skill stops rather than forcing the base unit model.
- **Java is not supported.** The profile exists; the enforcer does not.
- **The skill cannot certify conformance.** It produces evidence; `python3 tools/acima.py claim` decides the class, and six rules always need human evidence.
- **It will not edit your code without approval** — the workflow plans first, then asks.

A run that finds no files is the most common false pass. The preflight and the prover exist to make that failure loud; see [`references/00-preflight.md`](references/00-preflight.md).
