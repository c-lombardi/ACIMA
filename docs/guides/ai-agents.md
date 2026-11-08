# AI coding agents

ACIMA is designed to be an operational constraint for coding agents, not a prompt that
asks them to be careful. The repository provides a pinned catalog, a machine-readable unit
map, deterministic enforcers and structured findings. An agent can run the same checks a
human runs.

## Operating contract

An ACIMA-aware agent **must**:

1. Read the applicable specification and the target's `acima.config.json`.
2. Verify the rule catalog version and hash with the adoption preflight.
3. Inspect the target repository before editing.
4. Identify the authorized module boundaries and allowed dependency directions.
5. Plan the change and name any published contract it will alter.
6. Implement the smallest change that fits the declared boundaries.
7. Run the enforcer and read the structured findings.
8. Correct violations it introduced.
9. Report contract changes and compatibility implications.
10. Ask the owner before adding or changing a waiver.
11. Produce an implementation summary with the commands run and their results.

An agent **must not**:

- edit `acima.config.json`, `expected.json` or the waiver file just to make a check pass;
- suppress a finding without an owner, reason and expiry;
- invent a rule id or a finding;
- import another module's implementation;
- change a published contract without identifying the compatibility impact;
- claim conformance when a rule was skipped or not evaluated;
- use a missing tool or an empty scan as evidence of a pass.

## Commands

From an ACIMA checkout, against the target repository:

```bash
python3 skills/acima-adoption/scripts/preflight.py --project /path/to/target --format json
python3 tools/acima.py inspect  --root /path/to/target --format json
python3 tools/acima.py analyze  --root /path/to/target --format json
python3 tools/acima.py report   --root /path/to/target --format markdown
```

The preflight is read-only unless `--write-draft` or `--write-waivers` is requested. The
CLI's `inspect` and `analyze` commands do not modify the target.

The agent should run the target's own wired enforcer as the final gate. `tools/acima.py
verify` verifies this ACIMA repository, not the target.

## Portable agent prompt

```text
You are changing a repository governed by ACIMA.

Before editing:
1. Run the adoption preflight and verify the catalog hash.
2. Read acima.config.json and list the units and allowed dependencies.
3. State which module owns the change and which contracts it touches.
4. If a contract changes, identify whether the change is additive or breaking.

While editing:
- Depend on other modules only through their contracts.
- Do not edit the config, expected findings or waivers to pass a check.
- Do not add a cross-module implementation import.
- Ask before creating an exception. An exception needs owner, reason, scope, expiry and
  review date.

After editing:
- Run the enforcer and report the exact command.
- List every finding introduced and fixed.
- List every rule that was not evaluated.
- Do not say "conformant"; say "0 unwaived errors at level X, with these unevaluated rules".
```

The full portable skill, including the preflight, adoption plan and brownfield playbook,
is in [`skills/acima-adoption`](../../skills/acima-adoption/SKILL.md).

## Example: what the agent sees

When the walkthrough introduces an implementation import, the enforcer returns a finding
with a rule id, severity, message, path, line and evidence. The agent should use that
evidence to change the dependency, not to search for a suppression:

```text
ACIMA-D001  error  Module orders imports the implementation unit catalog (expected catalog.contracts).
  src/acima/orders/impl/reach_into_catalog.py:1
  from acima.catalog.impl.repository import InMemoryProductStore
```

The correction is a contract import and an explicit boundary map, as shown in
[Before and after](before-after.md).

## Limits

- The reference enforcers read source and project files; they do not prove runtime
  autonomy or deployment independence.
- Six portable rules require native analyzers or human judgement; the CLI report lists
  them as **not evaluated**.
- The Java profile has no reference enforcer in this revision.
- The agent skill is only as current as its pinned catalog hash. If preflight fails, stop;
  do not work around the pin.

A clean agent run is evidence, not a guarantee. The owner still decides whether a contract
change is acceptable.
