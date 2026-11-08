# For engineering leaders

ACIMA is an investment in making architectural boundaries visible and enforceable. It is
not a promise of faster delivery by itself, and it does not replace product or
organizational decisions. This page states what a leader can verify, what adoption costs,
and what the standard does not claim.

## The organizational problem

As systems and teams grow, coupling turns local changes into coordination events:

- a shared `Common` project becomes a dependency every team must release around;
- a module reaches into another module's implementation because the contract was missing;
- two teams own one table and discover it during an incident;
- an architecture rule exists in a document but not in the build;
- an AI agent introduces a dependency that no reviewer notices until it is in production.

The result is not one dramatic failure. It is a rising cost per change: more waiting, more
integration work, larger blast radius and slower onboarding.

## What ACIMA makes measurable

| Question | Evidence |
|---|---|
| Are modules declared and classified? | `acima inspect` and `acima.config.json` |
| Are illegal dependency edges present? | enforcer findings (`D*`) |
| Are contracts immutable? | findings (`C*`) and contract review |
| Is each module's data owned? | `A001` findings and schema review |
| Are exceptions owned and expiring? | waiver report (`G001`, `G002`) |
| Is the gate actually running? | CI job and retained JSON artefact |
| Which rules were not evaluated? | `acima report` and capability status |

These are evidence, not a productivity score. ACIMA does not measure story points,
deployment frequency, customer impact or team performance.

## What adoption looks like

1. **Discovery** — inspect the repository without changing it.
2. **Baseline** — measure the current findings at L1 and retain the JSON.
3. **Waivers** — give every existing finding an owner, a reason and an expiry.
4. **Gate** — block new errors in CI before asking anyone to fix the estate.
5. **First slice** — merge one boundary change: a contract extraction or a cycle break.
6. **Ratchet** — reduce the baseline one owned change at a time; raise the level only when
   the evidence supports it.

The first value is usually visible before the first cleanup: the team can see the dependency
graph, the exception list and the next boundary to fix.

## Investment and cost

The standard is explicit that contract extraction and persistence ownership are not free.
The cost table in [Adoption](../standard/09-adoption.md#95-cost-honestly) separates one-off
work from recurring work. It deliberately gives ranges, not fabricated delivery estimates.

Leaders should fund:

- a named architecture owner and module owners;
- the first baseline and one boundary slice;
- CI compute and the time to keep the gate green;
- data migration work for persistence ownership, when that becomes the next slice.

The recurring cost is small when the rules run in the existing pipeline. The recurring cost
of not doing it is paid as coordination and incident work, which is harder to attribute.

## Questions to ask the team

- Can we name the owner of every module and every schema?
- Can a module be built and tested without another module's implementation?
- Which rules are not evaluated by our current enforcer, and who reviews them?
- How old is the median waiver? Who owns the oldest one?
- What happens when someone adds a forbidden import: does CI fail, or does a reviewer
  have to notice?
- Does an AI agent get the same constraints as a human, and can we audit its run?

## Decision checklist

- [ ] The team has a real coupling problem it wants to reduce.
- [ ] There is a named owner for the standard and for exceptions.
- [ ] The team accepts an incremental gate, not a rewrite.
- [ ] CI can run the enforcer on every pull request.
- [ ] The first slice is one boundary, with a rollback path.
- [ ] The team will retain the run artefact and report, not just a green badge.
- [ ] Everyone understands that a clean run with unevaluated rules is not a conformance claim.

If those are true, start with [Brownfield adoption](../start/brownfield.md). If the product
has one module and no plan to change that, ACIMA’s base module rules may be more ceremony
than value; the standard says so.
