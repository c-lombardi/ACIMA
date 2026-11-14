# 9. Adoption

ACIMA is designed to be adopted while a system is running, by teams that cannot stop to rewrite it.
This chapter is the practical path.

Adoption is a consent-based sequence, not an instruction to implement. §9.9 defines the five phases
and the approval boundary; the authoritative agent workflow is the
[adoption skill](../../skills/acima-adoption/SKILL.md).

## 9.1 Greenfield

Adopt the full shape from the first commit. It costs almost nothing when there is no legacy:

1. declare value types inside each contract project (or use primitives); do not add a shared kernel
   to new contracts — the kernel is a legacy compatibility allowance;
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
| 5 | **Configuration, values and statics** (`A002`, `A005`, `A006`, `A003`) | small, usually a handful of hot spots |

Do not start with `A001`. Teams try, discover it needs a data migration, and abandon the programme.
Start with the rules where the fix is a code change within one pull request.

Once a composition boundary exists, add explicit composition as the next slice. Replace scans and
convention registration that choose module-owned components (`D013`), then move module-owned
dependencies out of properties and fields into constructors (`D014`). Do not force a container-free
style on framework infrastructure: the test is whether the module-owned graph and its registrations
are visible, not whether every object is written with `new`. A library may have no host; its public
factory or consumer construction is the boundary. Then review closures, callbacks and partial
module graph: a dependency captured from a module or enclosing local is `D015`, and a dependency
pre-bound inside a component is `D016`. Pure HOFs and explicit currying stay legal (chapter 16).

Then review lifetimes and state ownership before changing registrations in bulk. Identify which
module-owned components are stateless, which carry request or tenant state, which own resources and
which depend on a scoped component. A stateless service registered transient is `A007`; a shared
component directly capturing a scoped dependency is `A008`; a shared component owning a mutable
container without a stated owner, isolation key and concurrency policy is `A009` (chapter 17). Do
not convert transient registrations to singletons as a migration shortcut: decide the state
owner first, then choose the lifetime. Go and Java report these rules `executed: false` in this
revision, so their lifecycle decisions need recorded manual evidence. The .NET enforcer executes the
three rules from direct host registrations, with the conservative limits in chapter 17.

Then review effects before adding retries, transactions or background consumers. For each effect,
name the owning module, the execution boundary and the truthful outcome; say whether a retry is
possible, whether a duplicate can harm, what partial completion looks like and who recovers it. This
is a design review, not a code scan (`A010`–`A013`, `C008`). Do not add an idempotency key, a
transaction or a cancellation parameter merely to make a checklist look complete. Start with the
effects that can lose money, duplicate a commitment, corrupt data or lose a required audit record,
and record the evidence that covers their failure paths. The P15 rules are manual in every profile,
so a clean portable run says nothing about them.

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
- a legacy shared kernel, where one still exists during migration, is owned by an architecture group
  or by whoever is willing to be its bottleneck — this is intentional friction;
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
| Effect review | hours per critical workflow | low; retries and recovery have a named owner before they are added |
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
| Enforcer is slow / flaky | it compiles the product instead of reading the source | read source or compiled metadata; do not execute the product |

## 9.7 When to stop

ACIMA is a means, not a goal. Stop adding discipline when:

- the remaining findings are all in code that is scheduled for deletion;
- a rule repeatedly produces waivers for legitimate designs — that is evidence the rule is wrong, and
  the standard should be amended rather than the code bent;
- the enforcer has become a product with its own roadmap. Rules are cheap to write and expensive to
  maintain; a rule that costs more than the defect it prevents should be withdrawn in the next major
  version.

## 9.8 Adopting the service topology profile

The service topology profile in chapter 11 is optional and applies only when explicitly selected. It
matters most when the product has, or is about to have, more than one service and more than one
layer. A single-module repository, package or library can use the base module shape; absolute
contract isolation is a profile requirement, not a base requirement.

### Greenfield

1. create `services/<Service>/` with the service name, and write its one-sentence responsibility;
2. create the domain first, with its tests, before any contract exists;
3. add `Api.Contracts` and `Application.Contracts` as zero-reference projects;
4. add the transform at the Api → Application boundary before the first endpoint;
5. isolate the first vendor behind `<Service>.<Vendor>.Contracts` + `<Service>.<Vendor>` before the
   first call is written;
6. add the composition boundary last, and let it be the only project in its scope that references everything.

Do not start with the composition boundary or the database. Starting there produces a service shaped by its
infrastructure, which is the thing the profile exists to prevent.

### Brownfield

Map before you rename. List every existing project, assign it a layer and a service, and only then
apply the naming. The first slice is usually one boundary transform: replace a shared DTO with two
layer contracts and a mapper. That change is visible, testable and reversible, and it proves the
pattern before the rest of the tree moves.

Do not bulk-rename projects in one PR. A rename campaign touches every build file, obscures the
semantic changes, and makes review impossible. Rename the project you are already changing.

### What it costs

| Activity | One-off | Recurring |
|---|---|---|
| Splitting layer contracts | days per boundary | low; new types go to the owning layer |
| Writing transforms | hours per boundary | low; mappers are simple and tested |
| Absolute isolation | days, mostly removing kernel references | near zero; contracts start empty |
| Vendor seams | days per vendor | low until the vendor changes, then a swap instead of a rewrite |
| Domain coverage to 100% | weeks on a legacy domain | low if tests are written with the rule |
| Manual ST checklist | an afternoon per service | an hour per quarter |

### When not to adopt it

- the product has one service and one layer, and no plan to change that;
- the team cannot name a single product outcome the service owns;
- the existing deployment is the product (a script, a batch job) and has no UI/API workflow to keep
  in parity.

A profile adopted without the product shape it assumes becomes ceremony. Base ACIMA still applies.

## 9.9 Consent, authorization and artifacts

A repository's owner decides whether, how much and when to adopt. Analysis is never authorization.
The workflow has five phases; the skill implements them and this section defines the boundary.

| Phase | Purpose | May write to the target? | Ends with |
|---|---|---|---|
| 1. Assessment | establish fit, boundaries, findings and limits | no | a verdict and named gaps |
| 2. Proposal | make the change reviewable | no | exact paths, statuses, decisions and risks |
| 3. Explicit authorization | the owner accepts a named scope | no | an affirmative answer to the approval question |
| 4. Approved implementation | implement only the approved scope | approved paths only | the approved artifacts and slices |
| 5. Verification and handoff | prove what exists and state what does not | no new scope | a report of changes, checks and gaps |

Approval is **scope-specific**. A proposal lists every path, what it contains, why it is needed and
whether it is required, conditional or optional. An approval covers that list and nothing else; a
new requirement discovered during implementation stops work until the owner approves the addition.
Partial approval is normal: a repository may adopt a unit map and a local check without a CI gate, a
baseline or any programme document.

Organizational artifacts are **optional unless the owner asks for them or coordination genuinely
requires them**. An adoption plan, a communication plan and a status dashboard are useful for a
multi-team programme; they are not conditions of technical adoption and MUST NOT be created by
default. A summary is an interpretation of a run, not evidence, and may live outside the target.

Merging, releasing, publishing and organizational decisions always remain with the human owner. No
agent approval, tool result or passing gate substitutes for them. A limited adoption is legitimate;
calling it complete is not.
