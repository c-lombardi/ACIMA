# Communication reference

Architecture adoption is a change to how people are allowed to work. Most failures are
communication failures wearing technical clothes: the gate arrives unannounced, a finding feels
like a reprimand, a waiver negotiation turns into a status contest.

This reference gives audiences, messages and cadence. Adapt the words; keep the structure.

## Audiences

| Audience | Cares about | Give them | Do not give them |
|---|---|---|---|
| Engineers in the module | "what do I do differently on Monday?" | imports, ownership, the exact remedy text | levels, rule taxonomy, the spec |
| Tech lead / module owner | "who reviews what, what breaks" | contract-change review rule, waiver ownership | programme metrics |
| Engineering manager | delivery risk, capacity, dependencies on other teams | phase plan, dates, cost, cross-team blockers | rule IDs |
| Skeptic senior engineer | "is this another framework?" | the smallest rule that catches a real bug they know | enthusiasm |
| Leadership | cost, risk, trend | finding count, unowned exceptions, lead-time effect | architecture diagrams |
| New joiners | "how does this place work?" | first-week curriculum, one real example | history of the programme |

## Message 1 — kickoff (before the gate exists)

> We are making module boundaries enforceable instead of conventional.
>
> What changes: you may import another module's **contracts**, never its implementation. CI will
> start failing on **new** boundary violations. Existing ones are recorded and owned; they will not
> block you.
>
> What does not change: your stack, your tests, your delivery process.
>
> Why: today a change can break a module we did not know depended on us. The gate turns that into
> a build error on the pull request that caused it, with the replacement named.
>
> First step: a 45-minute session on <date> to walk through one real finding. Bring a boundary you
> have personally been burned by.

Say the date, the owner and the support channel in the same message. A kickoff without a named
owner reads as a reorg.

## Message 2 — the first finding (pull request comment)

> **ACIMA-D001** — implementation references another implementation
>
> `Orders` is importing `CatalogRepository` from `catalog/impl`. It works today, but it means a
> change to Catalog's storage can break Orders at compile time without Catalog knowing.
>
> Fix: depend on `Catalog.Contracts` (`ICatalog`) and call `GetProduct`. If the data you need
> isn't on the contract, add it to the contracts unit in this PR — that's the intended path, not a
> workaround.
>
> If this can't land this sprint, add a waiver with your name and a 30-day expiry and link the
> ticket. I'll approve that.

Three properties: it explains the consequence, it names the fix, and it makes the exception
cheap but visible. Criticism of code without a path to green is how gates get disabled.

## Message 3 — waivers

Waivers are where architecture meets politics. Rules:

- The **owner** is the person who will fix it, not the person who noticed it.
- The **reason** states the constraint, not the feeling: "schema migration scheduled for Q1" beats
  "legacy".
- The **expiry** is a date someone will actually be in the code. 30–90 days.
- Renewal is a conversation, not a formality: *"the waiver on Orders/Catalog expires Friday. Is the
  migration still on? If yes, renew to <date>; if no, let's delete it."*

Never say "we'll clean it up later". Say the date and the ticket.

## Message 4 — monthly update (one page)

```
ACIMA — <month>
Declared level: L1     Units: 7     Gate: required since <date>

Findings: 214 → 198  (-16, -7%)
  by rule: D001 41→33, C001 22→12, D005 3→3
Waivers: 31 active, 3 expired, 4 expire within 30 days
Owners: 31 named, 0 unassigned

Merged this month: Catalog contracts extraction (#412), immutability sweep in Billing (#418)
Next: break Orders↔Payments cycle; A001 discovery for Billing
Risk: two teams disagree on ownership of "pricing"; escalated to <name>
```

Trend plus owners plus next plus risk. No adjectives. If the number went up, say so and say why;
a metric that only moves one way is a metric people stop trusting.

## Message 5 — saying no to a shortcut

When someone asks to import an implementation "just this once":

> That's the exact reference the gate exists to stop, and it would put the count up after six
> weeks of it going down. Two options: (a) I'll pair with you for 20 minutes to add what you need
> to the contracts unit; (b) a 30-day waiver with your name. I'd rather do (a) — which is it?

Offer the legitimate path, make the exception possible, make the cost visible. A blanket "no"
produces shadow imports outside the gate's reach.

## Talking to skeptics

Skeptics are usually right about something. Find it first.

| They say | Respond with |
|---|---|
| "This is just DDD with extra steps." | "The boundary thinking is DDD's. The difference is the gate: this one fails a build." |
| "We'll spend all our time on architecture." | "Day one is a baseline, not a rewrite. After that it's the build telling you, once." |
| "It can't work with our legacy." | "Agreed — that's why we start with contracts for the two most-coupled modules and waive the rest." |
| "The rules are too strict." | "Which rule produced a finding you think is wrong? That's a standard amendment, and I'll take it." |
| "This will slow delivery." | "It slows the change that would have broken three services. Measure lead time for a quarter and we'll both look at the number." |

Do not defend the whole standard. Defend the next slice.

## The review argument (use this first)

Engineers adopt architecture work when it makes their afternoon better. Lead with the pull request,
not the principles:

> The gate answers the structural questions before anyone reads the diff — may this depend on that,
> did the blast radius grow, is this a published-surface change, is the exception owned. Review
> time goes to whether the product behaviour is right. Contracts and implementations can be
> separate PRs, so a surface change cannot hide in a refactor.

Three sentences that land with reviewers:

- **"The graph is the blast radius."** No cycles, no implementation references, no shared statics,
  so the affected units are derivable instead of discovered in staging.
- **"The finding is the review comment, before the review."** Rule id, path, line, evidence and
  remedy, in JSON, on every PR.
- **"The agent cites the same rubric you do."** Findings are machine-readable and the skill pins
  the catalog hash; the agent proposes, the owner decides, and no agent can author a waiver.

For the full reviewer checklist, AI review protocol and anti-patterns, link
[Review and decisions](../../../docs/guides/review-and-decisions.md).

## Cadence

| When | What | Who |
|---|---|---|
| Before the gate | kickoff + unit-map workshop | all engineers, tech leads |
| Weekly | 30-minute office hours; count + blockers | volunteers, owners |
| Every PR | remedy-shaped comment on new findings | reviewer |
| Monthly | one-page update; waiver review | manager, owners |
| Quarterly | level review: raise, hold, or amend a rule | architecture owner |

## Language rules

- Name the **consequence**, then the rule ID. Nobody remembers IDs; everybody remembers "Orders
  can break when Catalog changes its schema".
- Say "pre-existing" for baselined findings, every time. Otherwise the first baseline read feels
  like an accusation.
- Never present a level as a maturity badge. L1 on a hard legacy estate is an achievement.
- Put the remedy in the failure message. Communication that lives only in a document is not
  communication; it is a hope.

## When adoption stalls

Ask three questions in this order, and believe the first honest answer:

1. **Is the gate failing for reasons people cannot fix?** Then the unit map or the rule is wrong.
2. **Are waivers owned by nobody?** Then nobody has been given the work.
3. **Is the count invisible?** Then it is not a programme, it is a build step.

The fix is almost never more documentation. It is a smaller slice, a named owner, or a visible
number.
