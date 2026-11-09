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
| `SKL-003` | 55 rules, all 41 automated ids and all 14 manual ids still exist | a rule was renamed or removed; update references that cite it |
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
| `TGT-006` | the architecture mode is valid and matches the tree: `base` (or absent) with no manifest, or `service-topology` with `acima.topology.json` | repair `mode` and the manifest; service mode is `NOT SUPPORTED` by this skill and must not be assessed as base |

Classification rules, stated plainly:

- **adopting** — `acima.config.json` exists.
- **greenfield** — no config and no source files.
- **brownfield** — no config and at least one existing source file.
- **architecture mode** — `acima.config.json.mode` is `base` (default) or `service-topology`.
  A `service-topology` declaration requires `acima.topology.json`; the manifest without the mode is
  a configuration error. The preflight reports the mode as `TGT-006` and blocks a service target
  because this skill has no service workflow.

There is no numeric threshold. A 400-line prototype with one source file is still brownfield by
the classification the tool uses; the plan can say it is early-stage, but it must not call the
same repository greenfield. The classification changes the adoption path, not the quality of the
code.

## Governance checks (`GOV`)

Only run when `acima.config.json` exists.

| ID | Asserts | If it fails |
|---|---|---|
| `GOV-001` | units are declared and the level is `L1`, `L2` or `L3` | repair the config; an empty config classifies nothing |
| `GOV-002` | the enforcer runs, and reports the baseline; a profile with no runner blocks | exit `2` is a tool failure — stop; exit `1` is a baseline, expected on day one; no reference runner is `fail` (unsupported, not clean) |
| `GOV-003` | waivers have the required fields — including the exact finding fingerprint — and none are expired | `G001`/`G002`: complete them or renew deliberately |
| `GOV-004` | no waiver is still owned by `unassigned` | replace with real names before merging the gate |

`GOV-002` deliberately distinguishes four outcomes: clean (`pass`), baseline findings (`warn`),
enforcer failure (`fail`), and unsupported language profile (`fail`). Collapsing the first two
teaches teams to ignore the gate; collapsing tool failure hides a broken tool; collapsing
"unsupported" into pass turns "we could not check" into a false conformance claim. A Java target
must report `BLOCKED` with `GOV-002` until a native analyzer result is supplied and reviewed.

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

The waiver writer emits one waiver per **exact finding fingerprint**, scoped to the unit that owns
the path, with owner `unassigned`, a 90-day expiry and today's review date. The scope is a filter,
not permission to suppress every future finding in the unit. The file is structurally valid but
**not acceptable**: `GOV-004` warns until a human replaces every owner. That is intentional. An
automatically generated exception file that passes review is how governance dies.

## Reading the report

Text output groups by check and ends with `READY`, `READY with N warning(s)` or `BLOCKED`.
JSON output is stable and safe to attach to a ticket:

```json
{
  "skill": { "name": "acima-adoption", "version": "1.17.0", "standard": "1.9.0-draft.1" },
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
