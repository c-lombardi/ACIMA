# Preflight reference

The preflight is the only part of this skill that runs before the agent is allowed to change
anything. It is read-only unless you pass `--write-draft` or `--write-waivers`, and it never
reaches the network.

```bash
python3 skills/acima-adoption/scripts/preflight.py --project <target> --format text
python3 skills/acima-adoption/scripts/preflight.py --project <target> --format json
python3 skills/acima-adoption/scripts/preflight.py --project <target> --deep
```

| Exit | Meaning |
|---|---|
| `0` | Ready. Warnings may still need a human decision. |
| `1` | Blocked. At least one `fail`, or any warning under `--strict`. |
| `2` | The preflight itself could not run. Never treat this as an architecture result. |

## Calibration checks (`SKL`)

These assert that the skill matches the repository **at this commit**. They are the reason the
skill can be trusted months later.

| ID | Asserts | If it fails |
|---|---|---|
| `SKL-001` | the manifest is readable JSON | restore `manifest.json`; do not hand-edit around it |
| `SKL-002` | `tools/acima-spec/rules.json` matches the pinned SHA-256 | the catalog changed. Read the diff, update the skill deliberately, then update the pin |
| `SKL-003` | 29 rules and all 23 portable ids still exist | a rule was renamed or removed; update references that cite it |
| `SKL-004` | the catalog version equals `manifest.standard` | version-specific guidance is stale |
| `SKL-005` | every reference and asset listed in the manifest exists | restore the file or remove it from the map |
| `SKL-006` | every documented enforcer path exists | the layout moved; fix the commands in `SKILL.md` and the manifest together |
| `SKL-007` | every implemented profile still has `violations/expected.json` | the gallery is the executable definition of the rules; restore it |
| `SKL-008` | the default manifest was used | only appears with `--manifest`; expected in tests and forks |

**Never fix `SKL-002` by editing the hash.** The hash is the assertion that the advice was
written against these rules. Editing it converts a governance control into a rubber stamp.

## Environment checks (`ENV`)

| ID | Asserts | If it fails |
|---|---|---|
| `ENV-001` | reports which toolchains are on `PATH` | informational |
| `ENV-002` | `python3` is available | install Python 3.9+; the preflight is Python |

A missing `node`, `go`, `dotnet` or `java` is not a blocker unless the target needs it. The
preflight reports it so you do not promise a gate you cannot run.

## Target checks (`TGT`)

| ID | Asserts | If it fails |
|---|---|---|
| `TGT-001` | the target exists and is a directory | pass the right `--project` |
| `TGT-002` | a language is recognisable from manifests or sources | confirm the path, or scaffold first |
| `TGT-003` | classification: `greenfield`, `brownfield`, `adopting` | if ambiguous, ask the owner |
| `TGT-004` | candidate units can be proposed | declare units manually with the plan's ADR |
| `TGT-005` | every source file falls inside a proposed unit | uncovered files become `G005` findings |

Classification rules, stated plainly:

- **adopting** — `acima.config.json` exists.
- **greenfield** — no config and no source files.
- **brownfield** — no config, 10 or more source files.

The threshold is a heuristic, not a doctrine. A 400-line prototype with no users is greenfield
in spirit; a 9-file service that is already deployed is brownfield in spirit. When the number
and the situation disagree, trust the situation and say why in the plan.

## Governance checks (`GOV`)

Only run when `acima.config.json` exists.

| ID | Asserts | If it fails |
|---|---|---|
| `GOV-001` | units are declared and the level is `L1`, `L2` or `L3` | repair the config; an empty config classifies nothing |
| `GOV-002` | the enforcer runs, and reports the baseline | exit `2` is a tool failure — stop; exit `1` is a baseline, which is expected on day one |
| `GOV-003` | waivers have all six fields and none are expired | `G001`/`G002`: complete them or renew deliberately |
| `GOV-004` | no waiver is still owned by `unassigned` | replace with real names before merging the gate |

`GOV-002` deliberately distinguishes three outcomes: clean (`pass`), baseline findings (`warn`),
and enforcer failure (`fail`). Collapsing the first two teaches teams to ignore the gate;
collapsing the third hides a broken tool.

## Deep checks (`ENF`)

`--deep` runs every reference enforcer against its own example and requires a clean tree. This
is how you prove the skill's recommended commands still work. It needs the relevant toolchains
and can take a minute for .NET.

| ID | Asserts |
|---|---|
| `ENF-python` | `examples/python` is clean at L3 |
| `ENF-typescript` | `examples/typescript` is clean at L3 |
| `ENF-go` | `examples/go` is clean at L3 |
| `ENF-dotnet` | `examples/dotnet` is clean at L3 |
| `ENF-java` | skipped: no reference runner in this revision |

## Writing artefacts

```bash
# heuristic unit map for a brownfield repository
--write-draft acima.config.json

# scoped waivers derived from the measured baseline
--write-waivers .acima/waivers.json
```

The draft is a **draft**. It derives units from directory names, which is the least reliable
signal available. Review it with someone who knows the domain before committing it.

The waiver writer groups findings by the unit that owns each path and emits one waiver per
`(rule, unit)` pair, with owner `unassigned`, a 90-day expiry and today's review date. That
makes the file structurally valid but **not acceptable**: `GOV-004` warns until a human replaces
every owner. That is intentional. An automatically generated exception file that passes review
is how governance dies.

## Reading the report

Text output groups by check and ends with `READY`, `READY with N warning(s)` or `BLOCKED`.
JSON output is stable and safe to attach to a ticket:

```json
{
  "skill": { "name": "acima-adoption", "version": "1.0.0", "standard": "1.0.0-draft.1" },
  "project": { "path": "/repo", "mode": "brownfield", "language": "python" },
  "checks": [{ "id": "SKL-002", "status": "pass", "detail": "...", "remedy": "" }],
  "blockers": [],
  "warnings": ["GOV-004"],
  "findings": { "total": 42, "errors": 41, "byRule": { "ACIMA-D001": 12 } },
  "proposedUnits": [],
  "next": ["..."]
}
```

The `next` array is the path forward. Print it for the user verbatim; it is generated from the
checks, not from a template.
