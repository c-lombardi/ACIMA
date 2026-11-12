# AI coding agents

ACIMA is designed to be an operational constraint for coding agents, not a prompt that
asks them to be careful. The repository provides a pinned catalog, a machine-readable unit
map, deterministic enforcers and structured findings. An agent can run the same checks a
human runs.

## Operating contract

An ACIMA-aware agent **must**:

0. Treat assessment as read-only. Before creating configuration, baselines, waivers, plans, CI or
   tooling, present the exact proposed paths and obtain the owner's explicit approval. “Adopt
   ACIMA” is intent, not approval of unseen files.
1. Read the applicable specification and the target's `acima.config.json` when one exists.
2. Verify the rule catalog version and hash with the adoption preflight.
3. Inspect the target repository before editing.
4. Identify the authorized module boundaries and allowed dependency directions, and name the team's architecture family (Clean, Hexagonal, DDD, modular monolith, microservices). ACIMA evaluates the applicable requirements; it does not replace the family.
5. Plan the change and name any published contract and externally visible effect it will alter.
6. If the change introduces or modifies an effect, state its owner, execution boundary, duplicate
   behaviour and truthful failure outcome before implementing it.
7. Implement the smallest change that fits the declared boundaries.
7. Run the enforcer and read the structured findings.
9. Correct violations it introduced.
10. Report contract changes and compatibility implications.
11. Ask the owner before adding or changing a waiver or recording manual effect evidence.
12. Produce an implementation summary with the commands run and their results.

An agent **must not**:

- create or modify `acima.config.json`, `.acima/`, CI, build files, plans or source during an
  assessment, or beyond an approved adoption scope;
- edit `acima.config.json`, `expected.json` or the waiver file just to make a check pass;
- suppress a finding without an owner, reason and expiry;
- invent a rule id or a finding;
- use ACIMA to argue for a different architecture; it enforces the chosen boundaries, it does not choose them;
- import another module's implementation;
- change a published contract without identifying the compatibility impact;
- hide an effect behind a read-shaped method or perform a provider's effect at a composition boundary;
- claim that a retry, transaction, idempotency key or cancellation token makes an effect correct;
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

The preflight is read-only unless `--write-draft` or `--write-waivers` is requested. Those flags
are adoption acts and require explicit approval of the named paths, as does every other write. The
CLI's `inspect` and `analyze` commands do not modify the target.

The agent should run the target's own wired enforcer as the final gate. `tools/acima.py
verify` verifies this ACIMA repository, not the target.

## Portable agent prompt

```text
You are changing a repository governed by ACIMA.

Before editing:
1. Run the adoption preflight and verify the catalog hash.
2. Read acima.config.json and list the units and allowed dependencies.
3. State which module owns the change and which contracts and effects it touches.
4. If a contract changes, identify whether the change is additive or breaking.
5. If an effect changes, name its owner and execution boundary, and state retry, duplicate,
   consistency and cancellation semantics where they apply. Do not add them where they do not.

While editing:
- Depend on other modules only through their contracts.
- Do not perform another module's effect or open a transaction across modules.
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

The full portable skill, including the consent gate, preflight, proposal template and playbooks,
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

## Reporting to a human

An agent's final message is a report, not a work log. Use the two-level model in
[the reporting reference](../../skills/acima-adoption/references/80-reporting.md): generate
the summary with `skills/acima-adoption/scripts/summarize.py`, and keep the JSON run as the evidence
it links to. For an assessment, deliver it in the response or outside the target; writing into
`docs/acima/` needs approval.

- Name the consequence before the rule id; put the id in parentheses.
- Group repeated findings by problem and remedy, never one row per file.
- Separate real defects from detector artefacts and review items; never present a tooling defect
  as architecture debt.
- Say which status the evidence supports, using the six-term vocabulary. Only a supplied full
  claim makes `Verified`; a green baseline is not conformance.
- Name one next action with its location, done-state and verification, then a short ordered list.
- List what was completed and what was not verified. Never narrate each command, and never paste
  the run JSON into the summary.

## Limits

- The reference enforcers read source and project files; they do not prove runtime
  autonomy or deployment independence.
- Fourteen rules require native analyzers or human judgement; the CLI report lists them as **not
  evaluated**. `C008` and `A010`–`A015` cover business-behaviour visibility, effect ownership,
  duplicate/retry/consistency semantics, truthful outcomes, recovery evidence, telemetry and
  consistency ownership.
- The Java profile has no reference enforcer in this revision.
- The agent skill is only as current as its pinned catalog hash. If preflight fails, stop;
  do not work around the pin.

A clean agent run is evidence, not a guarantee. The owner still decides whether a contract
change is acceptable.
