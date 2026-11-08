# 9. Adoption

ACIMA is designed to be adopted while a system is running, by teams that cannot stop to rewrite it.
This chapter is the practical path.

## 9.1 Greenfield

Adopt the full shape from the first commit. It costs almost nothing when there is no legacy:

1. create the shared kernel (usually one file: `Money`, plus ids);
2. create the first two modules … *and the contract between them before either implementation*;
3. write `acima.config.json` and the first waiver file (empty) at the same time as the solution file;
4. add the enforcer to CI **before** the second module exists, so the rules are never optional;
5. declare L3 and stay there. There is no reason to start lower when nothing is fighting you.

The most common greenfield mistake is deferring the contract split "until there are two teams". By
then the modules have already referenced each other's internals, and the split is a refactor.

## 9.2 Brownfield: the ratchet

Never start by fixing the architecture. Start by *measuring* it, then freeze the measurement.

```
Step 1  Declare units in acima.config.json, even if they are wrong.
Step 2  Run at L1. Record every existing finding as a waiver with owner + expiry.
Step 3  Gate CI on "no NEW findings". The number becomes a number on a dashboard.
Step 4  Turn the ratchet: every change reduces the count, and the gate stops the count rising.
Step 5  As waivers expire, fix or renew deliberately. Never bulk-renew.
Step 6  When the count reaches zero, delete the waivers, raise the level, repeat.
```

This works because it changes the question from "is our architecture good?" (unanswerable, therefore
ignored) to "did this pull request add a violation?" (answerable, therefore enforced).

### What to migrate first

| Order | Target | Why first |
|---|---|---|
| 1 | **Contracts extraction** for the two most-coupled modules | it is the change that unlocks everything else |
| 2 | **Cycle breaking** (`D005`) | cycles make every other migration harder |
| 3 | **Contract immutability** (`C001`, `C002`) | the cheapest high-value rule; it is mechanical |
| 4 | **Persistence ownership** (`A001`) | the expensive one: it needs schema work and a migration |
| 5 | **Configuration and statics** (`A002`, `A003`) | small, usually a handful of hot spots |

Do not start with `A001`. Teams try, discover it needs a data migration, and abandon the programme.
Start with the rules where the fix is a code change within one pull request.

## 9.3 The extraction recipe

Given a `BigModule` that everything references, and a `Common` project that everything needs:

1. **Inventory the surface.** List every public type `Common` exposes and who uses it. Group by
   concept, not by type.
2. **Move by concept, not by folder.** For each concept, decide the owner module. If no module owns it,
   that is the design question, not a file move.
3. **Create `<Owner>.Contracts`** and move only the types other modules actually need. Leave the rest
   internal to the owner.
4. **Leave compatibility shims temporarily**: `Common` becomes `[Obsolete]` forwarding types, so the
   change lands in small PRs. Shims get an expiry waiver — this is what `G001` is for.
5. **Delete `Common`** when the waiver expires. A `Common` project that no longer compiles is the only
   successful outcome.

## 9.4 Team topology

ACIMA's module boundaries should match ownership, or they will be renegotiated by force:

- one module, one owning team (or one team owning several modules — but never one module owned by
  several);
- contracts changes are reviewed by the owner, and by consumers only when breaking;
- the shared kernel is owned by an architecture group or by whoever is willing to be its bottleneck —
  this is intentional friction;
- the waiver file has named owners, which means it doubles as a map of who owes what.

If two teams cannot agree on a boundary, the boundary is wrong, and no rule will fix it. Fix the
organisation, then the code.

## 9.5 Cost, honestly

| Activity | One-off cost | Recurring cost |
|---|---|---|
| Contract extraction | days to weeks per module | low: new types go in contracts by default |
| Cycle breaking | days, sometimes a redesign | low |
| Immutability | hours per contract type | near zero; it is the default shape afterwards |
| Persistence ownership | weeks per module, includes a data migration | low, but schema changes get harder at first |
| Waiver discipline | minutes every PR | minutes monthly; the expiry does the nagging |
| Enforcer maintenance | days | low if it stays a rule runner, high if it becomes a framework |

The recurring cost of *not* doing it is the one that compounds: every change to a shared `Common`
project, every "just this once" reference, every schema join across modules is paid again on the next
change.

## 9.6 Failure modes of adoption

| Symptom | Real cause | Fix |
|---|---|---|
| Rules pass but the architecture is still bad | units are declared too coarsely, so most references are "internal" | split the units; `G005` only catches undeclared files, not undeclared concepts |
| Everyone hates the enforcer | findings say what is wrong but not what to do | rewrite messages as instructions (`4.8`) |
| Waivers grow faster than findings fall | waivers are bulk-renewed | expire them, and require the owner to renew individually |
| Contracts became a dumping ground | consumers request types directly | enforce `P4.3`; consumers adapt instead |
| One module is 80% of the code | the boundary follows the org chart, not the domain | split by concept, not by team |
| The kernel keeps growing | `D007` is not enforced, or every convenience type is "shared" | apply the four-part admission test in `4.5` |
| Enforcer is slow / flaky | it compiles the product instead of reading the source | read source or compiled metadata; do not execute the application |

## 9.7 When to stop

ACIMA is a means, not a goal. Stop adding discipline when:

- the remaining findings are all in code that is scheduled for deletion;
- a rule repeatedly produces waivers for legitimate designs — that is evidence the rule is wrong, and
  the standard should be amended rather than the code bent;
- the enforcer has become a product with its own roadmap. Rules are cheap to write and expensive to
  maintain; a rule that costs more than the defect it prevents should be withdrawn in the next major
  version.
