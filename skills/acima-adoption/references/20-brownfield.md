# Brownfield playbook

> **Consent gate.** Phase 1 measures read-only. Phase 2 presents the exact config, baseline, waiver,
> gate and CI paths, with their status and dependencies. Phase 3 creates only what the owner
> approved. A request to assess is not a request to write `acima.config.json`, and a config is not
> permission to add a baseline gate or CI.


Brownfield adoption is a **measurement programme with a code-change habit attached**, not a
rewrite. The goal of the first month is a number that cannot go up. The goal of the first quarter
is that the number goes down without anyone heroically carving out a module.

## The ratchet

```
Step 1  Declare units in acima.config.json, even if they are imperfect.
Step 2  Run at L1. Record every existing finding as a waiver with an owner and an expiry.
Step 3  Gate CI on "no NEW findings". Put the count on a dashboard.
Step 4  Every change either reduces the count or leaves it unchanged.
Step 5  As waivers expire, fix or renew deliberately. Never bulk-renew.
Step 6  At zero, delete the waivers, raise the level, repeat.
```

The question changes from *"is our architecture good?"* — unanswerable, therefore ignored — to
*"did this pull request add a violation?"* — answerable, therefore enforced.

## Step 1 — inventory before config (only if approved)

After the owner approves the configuration path and the proposed unit map, you cannot declare units from the directory tree alone. Spend one session with someone who knows
the domain and answer:

1. What are the business capabilities? (Orders, Catalog, Payments, Billing, Identity…)
2. Which capability owns which data? A table written by two capabilities is an `A001` finding
   *and* an org question.
3. Who is on call for each capability? Ownership that does not exist in the org chart will not
   survive in the code.
4. Which two capabilities change together most often? Those are the first contract to extract.

Write the answers as ADR-0001 in the adoption plan. The config follows the ADR, not the folders.

Then draft, if that path is approved:

```bash
python3 skills/acima-adoption/scripts/preflight.py --project . --write-draft acima.config.json
```

Review the draft. Rename units to domain words (`orders`, not `orders-service-v2`). Merge units
that are not real boundaries. Delete units that are folders rather than capabilities.

## Step 2 — baseline honestly (only if approved)

Baseline and waivers are conditional. A local-only trial can use the measured run without
committing a baseline; a gate without owned waivers is not ready to merge. Create only the approved
subset.

```bash
python3 skills/acima-adoption/scripts/preflight.py --project . --format json > acima-baseline.json
python3 skills/acima-adoption/scripts/preflight.py --project . --write-waivers .acima/waivers.json
```

The waiver writer emits one waiver per exact finding fingerprint and marks owners `unassigned`.
That is structurally valid and socially useless: replace **every** owner with a person before the
gate merges.

Rules for the baseline:

- Waive **errors**, not warnings. Warnings are information and should stay visible.
- One waiver per exact finding fingerprint, scoped to the owning unit/path. Do not group findings by unit; that suppresses future findings you have not measured.
- Expiry is 90 days by default. Anything longer is a decision to keep the violation.
- Exception: findings in code scheduled for deletion get a 30-day expiry and a deletion ticket.

Commit the baseline artefact next to the plan. It is the "before" photograph; without it nobody
can tell whether the programme is working.

## Step 3 — the gate (only if approved)

CI is a separate commitment; configuration and local enforcement do not authorize a workflow
change. When approved, CI runs the enforcer at the declared level and fails when a **new** finding appears. Two
implementation details decide whether this survives contact with a team:

1. **Compare against the committed baseline**, not against zero. A gate that fails on day one is
   disabled by day three.
2. **Print the remedy, not just the rule.** `D001: implementation references another
   implementation — depend on Catalog.Contracts and call ICatalog` is actionable.
   `D001 violation` is not.

The gate must also fail when the enforcer discovers nothing (`G005`). Otherwise a bad config
silently turns the gate into a green light.

## Step 4 — choose the first slice

Migration order from `docs/standard/09-adoption.md` §9.2, with the reasoning:

| Order | Target | Why | Typical PR size |
|---|---|---|---|
| 1 | contracts extraction for the two most-coupled modules | unlocks every later move | days |
| 2 | cycle breaking (`D005`) | cycles make every other migration harder | days |
| 3 | immutability (`C001`, `C002`) | mechanical, low risk, visible | hours |
| 4 | persistence ownership (`A001`) | needs schema work and a migration | weeks |
| 5 | config keys and statics (`A002`, `A003`) | small, few hot spots | hours |
| 6 | lifecycle and state ownership (`A007`–`A009`) | usually a registry change, but only after the state owner is decided | hours to days |
| 7 | naming clarity (`N001`–`N003`) | targeted renames where a name misleads; never a bulk rename | hours |

**Never start with 4.** It is the one that needs a data migration, and it is where programmes are
abandoned. Start where the fix fits in one pull request.

Lifecycle findings are easy to spot and easy to fix badly. Do not bulk-convert transient
registrations to singletons. First classify each component as stateless, request/tenant-scoped,
resource-owning or legitimately transient; then choose the lifetime. A stateless service can be
shared after checking concurrent safety. A shared component that captures a scoped dependency must
change its consumption path, not just its registration. A shared mutable container needs an owner,
isolation key, synchronization and eviction policy — or it belongs in a narrower scope. Record the
concurrency, tenant-isolation and cleanup claims as review evidence; the scanner does not prove
them, and Go, .NET and Java do not execute these rules at all.

Naming work begins with the mechanical casing and generic-name candidates, then stops for review.
Rename only where the current name would mislead a reader about responsibility or a side effect,
keep domain terms consistent across the modules that share a concept, and get consent before
changing consumer code. A rename changes the finding fingerprint, so move the baseline or waiver in
the same pull request. Do not bulk-rename to drive down a count; `N003` is evidence of a reviewed
judgement, not a scanner result.

A good first slice has: one boundary, fewer than ~400 changed lines, no schema change, and a
consumer that demonstrably compiles against the new contract.

## Step 5 — the extraction recipe

Given `BigModule` that everyone references and a `Common` project everyone needs:

1. **Inventory the surface.** Every public type `Common` exposes, and who uses it. Group by
   concept, not by type.
2. **Move by concept.** For each concept decide the owner. If no module owns it, that is a design
   question, not a file move.
3. **Create `<Owner>.Contracts`** and move only what other modules actually need. Everything else
   becomes internal to the owner.
4. **Leave compatibility shims.** `Common` forwards with `[Obsolete]`/`@deprecated`, so the change
   lands in small PRs. Every shim gets its own waiver with an expiry — this is what `G001` is for.
5. **Delete `Common`** when the last waiver expires. A `Common` project that no longer compiles
   is the only successful outcome.

Do not rename `Common` to `Shared`. Do not create `Common.Contracts` as a compromise; it is the
same unowned module with a stricter-sounding name.

## Step 6 — waiver discipline

| Situation | Do | Do not |
|---|---|---|
| Finding is real, fix is next sprint | waive 30 days, owner = the person fixing it | waive 12 months "to clear the board" |
| Finding is a false positive | fix the enforcer, add a fixture, note it in the plan | waive it forever |
| Finding is in dead code | 30-day waiver + deletion ticket | fix dead code |
| Waiver expired | owner decides: fix, renew with a new date, or escalate | bulk-renew the file |
| Rule keeps producing legitimate designs | propose a standard amendment | bend the code to satisfy a bad rule |

The waiver file is a map of who owes what. Read it in the monthly review; if the same name appears
eight times, that person needs help, not pressure.

## Sequencing by size

**Small (< 20k LOC, one team).** One afternoon: config, baseline, waivers, gate. First slice the
same week. Target L2 within a quarter.

**Medium (20–200k LOC, several teams).** One unit map workshop, then one module per team as the
first slice. Expect 2–3 months to L1 across the estate, longer if persistence is entangled. Do not
attempt a big-bang contracts extraction.

**Large / monorepo.** Adopt per bounded context, not per repository. Each context gets its own
config root, its own gate and its own owners. A single root config over 200 packages produces
thousands of waivers and no behaviour change. The preflight's `TGT-005` is the signal that the
map is too coarse.

## Stop conditions

Stop the programme and escalate when:

- the same rule generates waivers for designs the domain experts consider correct — the rule or
  the unit map is wrong;
- two teams cannot agree who owns a concept — fix the org boundary first (`09-adoption.md` §9.4);
- the first slice has been "almost done" for three sprints — the slice was too big;
- leadership asks for a conformance percentage before a baseline exists — there is no denominator.

## Definition of done for an approved full adoption (first 90 days)

A partial adoption uses the subset the owner approved; do not mark these boxes for capabilities that
were not approved and do not call the result conformant.

- [ ] ADR-0001 records the unit map and who owns each unit
- [ ] `acima.config.json` committed, L1 declared, units cover every source file
- [ ] baseline artefact committed and referenced from the plan
- [ ] every waiver has a real owner and an expiry no longer than 90 days
- [ ] CI fails on a new finding (proven with a throwaway branch)
- [ ] CI fails when the enforcer discovers nothing
- [ ] one boundary change merged
- [ ] the finding count is reported monthly, with owners, to the team
