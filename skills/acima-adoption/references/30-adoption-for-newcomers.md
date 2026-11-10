# Adoption for people with no background

Most engineers have never worked in a codebase with enforced module boundaries. They have worked
in codebases where "don't touch that" is folklore, where `Common` is a folder, and where the
architecture diagram is three years old. Assume zero background. Do not hand them the
specification and hope.

This reference is written to be reused: read it aloud in a kickoff, paste sections into onboarding
docs, or link it from the first pull request.

## The problem they already recognise

Start with pain they have felt, not with ACIMA's vocabulary:

- "Changing a shared helper breaks three services we didn't know existed."
- "Nobody can tell what depends on what, so every change is a gamble."
- "Two teams edit the same table and blame each other for the data."
- "We can't extract a service because everything imports everything."

Then the one-sentence claim: **ACIMA makes the boundary a compile-time and CI-time fact instead of
a convention**. That is all it is. Everything else is detail.

## Five ideas, in plain language

| Term | Plain language | What it replaces |
|---|---|---|
| **Module** | A business capability that owns its data and its code | A folder named after a team |
| **Contracts unit** | The small, stable set of types a module shows to the outside | Public classes, DTOs scattered everywhere |
| **Implementation unit** | Everything the module keeps to itself | Anything someone imported "just this once" |
| **Contract-owned value types** | `Money` and ids declared by the contract that publishes them | A shared kernel or `Common` project |
| **Enforcer** | A test that fails the build when a boundary is crossed | An architecture diagram in Confluence |

Analogy that works for mixed audiences: contracts are a **published API**, implementations are
**private offices**. You may walk into the lobby; you may not walk into someone's desk drawers.

## What changes for them on Monday

Be concrete. People need to know what is different in their day, not what is different in the
diagram.

1. **Imports.** You may import another module's contracts, never its implementation. The build
   will tell you immediately, with the replacement to use.
2. **Types you own.** If a type is not in your contracts unit, other modules cannot see it. That
   is the point; make it `internal`/unexported/underscore-prefixed and move on.
3. **Contract changes.** Adding a field is cheap. Removing or changing one is a reviewed event.
   The reviewer is the module owner.
4. **Exceptions.** If you need to cross a boundary temporarily, you add a waiver with your name,
   a reason and a date. It is not a favour; it is a debt with a due date.
5. **The gate.** CI will fail on new violations. It will not fail because of old ones. You are not
   expected to fix the estate; you are expected not to add to it.

## The first week curriculum

Do not front-load theory. Sequence: pain → boundary → tool → practice.

| Session | Duration | Content | Artefact |
|---|---|---|---|
| 1 | 45 min | the pain, the five ideas, one real finding explained | nothing; questions only |
| 2 | 60 min | walk one module: contracts vs implementation, live in the IDE | a one-page map of their own module |
| 3 | 60 min | read the config together; which unit owns what | corrections to the unit map |
| 4 | 90 min | pairing: fix one waived finding end to end | a merged PR |
| 5 | 30 min | read a failing gate together, decide fix vs waiver | the decision recorded in the waiver |

Session 4 is the one that converts people. Watching a boundary change compile, test and merge in
90 minutes does more than any document.

## Reading order (and what to skip)

Give them this list, not the full table of contents:

1. `README.md` — what this repository is, ten minutes.
2. `docs/standard/03-module-anatomy.md` — what a module looks like.
3. `docs/standard/04-dependency-model.md` §4.2 — the allowed edges table. Skip the rationale on
   first read.
4. `examples/<their language>/` — read the contracts of one module, then its implementation.
5. `docs/guides/violation-walkthrough.md` — one rule at a time, only the rules their team hit.

Skip the FAQ, governance, and conformance chapters on day one. They answer questions the reader
does not have yet.

## Misconceptions to correct early

| They will think | Say instead |
|---|---|
| "This is microservices." | It is a modular monolith with enforceable seams. Services are an option later, not a requirement. |
| "Contracts are DTOs for the API layer." | Contracts are the module's published surface for *all* consumers: HTTP, jobs, other modules. |
| "We need a shared kernel for `Money` and ids." | No: each contracts unit owns the value types it publishes. A shared kernel is a legacy compatibility allowance, not the default. |
| "The enforcer is a lint rule; I can suppress it." | A waiver is a reviewed, expiring exception with your name on it. Suppression without a waiver fails CI. |
| "We need to fix everything before turning it on." | No: baseline, waive, gate, ratchet. Fixing everything first is how this fails. |
| "Contracts should have validation and business rules." | Contracts carry data and shape validation; business decisions and orchestration live in the implementation. |

## Teaching the enforcer output

Show one real finding and annotate it:

```
Orders depends on Catalog's private implementation
  where:     src/orders/impl/module.ts:14
  evidence:  import { CatalogRepository } from '../../catalog/impl/repository'
  why:       a Catalog storage change can break Orders without Catalog knowing
  confidence: confirmed by the automated check
  remedy:    use Catalog's published interface; if it lacks the operation, request it
             from the Catalog owner instead of reaching into the implementation
```

Five useful sentences: what happened, where, why it matters, how certain the observation is, and
what to do instead. The internal check reference belongs in the technical record, not in the
headline. If your enforcer's output does not explain the problem this way, fix the message before
onboarding anyone; the message *is* the training.

## Pairing guide for the first fix

- Pick a finding the learner's team owns. Never a stranger's module.
- Do the smallest correct change: usually replace an implementation import with a contracts call.
- If the contract is missing something, stop and add it to the contracts unit together. That
  teaches the most important lesson: contracts evolve because consumers need them.
- Merge it. Do not leave it as a draft "for review"; the merge is the reward.

## Office hours and escalation

- **Weekly 30 minutes**, same slot, open agenda, first ten minutes on the current finding count.
- **A named architecture owner** (one person, not a committee) for contract-breaking decisions.
- **A rule-change channel**: if a rule feels wrong, the path is a proposal to amend the standard,
  not a quiet waiver. Say this out loud; otherwise the waiver file becomes the complaint department.

## Language for people who feel accused

Adoption fails when it sounds like a verdict on past work. Use:

- "the boundary was never written down" — not "the code is a mess";
- "this is a pre-existing finding, it is baselined" — not "you introduced 42 violations";
- "the contract is incomplete" — not "you reached through the boundary";
- "the waiver expires in 90 days, who owns it?" — not "who is going to fix this?".

The architecture is being made explicit. The people who wrote the old code were solving the
problem they had, without a seam to lean on.
