# Troubleshooting

Each entry is a symptom the agent will actually meet, the likely cause, and the action. Prefer the
first action; escalate only if it fails.

## The enforcer reports zero findings on a large repository

**Cause:** the config's `units` do not match the layout, so nothing is classified. This is the
false pass `G005` exists to catch.

**Action:** run the preflight and read `TGT-004`/`TGT-005`. If coverage is low, regenerate the
draft (`--write-draft`), fix unit paths, re-run. Never accept "0 findings" without checking that
the unit count is what you expect. Add an assertion to CI that the enforcer discovered at least N
units.

## The enforcer reports hundreds of findings on day one

**Cause:** correct behaviour. That is the baseline, not a failure.

**Action:** do not fix them. Write waivers per `(rule, unit)`, name owners, set 90-day expiries,
gate on new findings only. If the count is in the thousands, the unit map is too coarse — split
by bounded context first (`20-brownfield.md`, "Large / monorepo").

## A rule fires on a design the team considers correct

**Cause:** either the rule is wrong, or the unit map hides the real boundary. Both are legitimate.

**Action:** capture the finding, the design rationale and the affected unit in a short note.
If the design is genuinely outside the rule's intent, propose a standard amendment — do not add a
permanent waiver and call it resolved. If the boundary is wrong, fix the map; a rule cannot
separate two concepts the config merged.

## Waivers are growing faster than findings fall

**Cause:** waivers are being used as a queue for work nobody owns, and they are being renewed in
bulk.

**Action:** require individual renewal by the named owner; refuse bulk edits; set the default
expiry to 30 days for new waivers; review the file monthly. If a team has more than ~10 active
waivers, the slice they were given was too large.

## The gate is disabled "temporarily"

**Cause:** it failed for a reason the team could not fix, usually a false positive or a config
error.

**Action:** treat a disabled gate as an incident. Reproduce the failure, fix the enforcer or the
config, add a fixture that covers it, re-enable, and note the date it was off. A gate that has been
off for a quarter is not a gate; report it as absent in the conformance claim.

## Contracts have become a dumping ground

**Cause:** consumers request types directly instead of adapting to the published surface, and
nobody enforces the admission test.

**Action:** apply the four-part admission test in `docs/standard/04-dependency-model.md` §4.5.
Types that exist only to serve one consumer belong in that consumer's adapter. Adding a type to
contracts is a reviewed decision, not a convenience.

## A monorepo produces one giant unit map

**Cause:** one config at the repository root over hundreds of packages.

**Action:** adopt per bounded context. Each context gets its own root, config, gate and owners.
Cross-context references are then ordinary contracts dependencies. The preflight can be run once
per context; the conformance claim names the contexts it covers.

## Generated code is flagged

**Cause:** the generator's output is inside a declared unit path.

**Action:** exclude generated directories in the config (`exclude`), and assert that the unit
coverage check still explains where the generated code comes from. Do not waive individual
findings in generated files; a regeneration will move them.

## The Java profile is requested

**Cause:** `docs/languages/java.md` exists, but this revision ships no Java enforcer or example.

**Action:** say so plainly. Do not invent rule IDs or claim conformance. ArchUnit can implement
most of the portable set; the profile document maps the rules. A Java implementation is a
contribution to this repository, not something to fake in the target.

## Toolchain missing in CI

**Cause:** the enforcer runs in a job that does not install the language.

**Action:** match the job's setup to `conformance/run.py` (see the dotted paths in `.github` or
the runner's `PROFILES` map). A gate that cannot start must fail closed, not skip silently.

## The skill's preflight fails calibration

**Cause:** `rules.json`, the version or an enforcer path changed after the skill was written.

**Action:** that is the design. Read the diff, update the manifest and the references, bump
`skillVersion`, re-run `--deep`. Never edit the pinned hash without reading the change; the hash
is the only thing preventing confident, stale advice.

## `preflight.py` exits 2

**Cause:** the tool itself failed — missing Python, unreadable manifest, a crash.

**Action:** read stderr. Exit 2 is never an architecture result; do not report it as "the
repository is non-conformant". Fix the tool or the environment first.

## The team agrees with the goal and ignores the gate

**Cause:** the findings do not name a remedy, or the count is invisible, or waivers have no owner.

**Action:** in that order — rewrite the top finding messages as instructions, publish the monthly
one-pager, replace unassigned owners. More documentation does not fix this; a smaller first slice
and a named owner usually do.

## A contract change breaks three consumers at once

**Cause:** contracts changed without the additive-first discipline.

**Action:** add the new shape alongside the old, mark the old deprecated with a removal date,
migrate consumers, then remove. A contract change that requires all consumers to land in the same
hour is a deployment coupling you have just discovered; record it.
