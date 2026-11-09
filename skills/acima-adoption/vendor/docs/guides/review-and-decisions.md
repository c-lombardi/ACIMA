# Review and decisions

ACIMA's value is easiest to see in a pull request. The standard does not shorten review by removing
judgement; it removes the **structural questions** reviewers otherwise reconstruct from memory, so
the remaining time goes to product outcomes.

## 1. Where review time actually goes

Most review latency is not the diff. It is three things around it:

- **Reconstructing the dependency graph** — "who else uses this?", "is this import allowed?"
- **Guessing the blast radius** — "what else changes when this contract changes?"
- **Negotiating ownership** — "who reviews this?", "who owns this exception?"

Each has a mechanical answer in ACIMA. When the answer comes from the build, it does not come from
a comment thread.

## 2. What moves out of review

| Question | Mechanical answer | Evidence |
|---|---|---|
| May this unit depend on that one? | allowed-edge matrix + declared units | `acima.config.json`, `D001`–`D009` |
| Is the module graph still acyclic? | cycle detection | `D005`, `D008` |
| Is this a published-surface change? | contracts path + API baseline | `G004` |
| Can a consumer mutate this value? | contract shape | `C001`, `C002` |
| Does this reach into another module's data? | persistence ownership | `A001`, `A003` |
| Is this exception acceptable? | owner, reason, scope, expiry | `G001`, `G002` |
| Did the run actually discover the code? | unit coverage | `G005` |

What remains is the work only humans can do: whether the boundary is the right product boundary,
whether the contract models the domain, whether the change should ship at all.

## 3. Quick decisions: the reviewer's table

| Decision | Look at | Who decides |
|---|---|---|
| Accept the dependency | the unit map and the allowed-edge matrix | reviewer |
| Accept the contract change | contracts diff + API baseline + consumers | module owner |
| Accept the scope | files touched, units touched, new edges | reviewer or tech lead |
| Accept the exception | waiver fields and the ticket it cites | architecture owner |
| Accept the product behaviour | tests, contract semantics, acceptance criteria | product owner with reviewer |

The operating rule: **if a review comment argues about something the enforcer already checks, that
is a bug report against the enforcer or the unit map, not a request to the author.** Fix the
mechanical answer once; stop re-litigating it per pull request.

## 4. AI-assisted review that stays auditable

The enforcer produces deterministic JSON: `rule`, `severity`, `path`, `line`, `evidence`, and a
remedy. That is the same rubric a human reviewer uses, in a form an agent can read and cite. The
[agent skill](../../skills/acima-adoption/SKILL.md) pins the catalog hash, so its advice is written
against the rules actually in this revision rather than a remembered version.

A protocol that keeps the human in control:

1. **Preflight the repository.** `preflight.py` classifies the target and refuses to proceed when
   the skill and the catalog have drifted.
2. **Run the enforcer on the PR.** Keep the JSON as the review artefact.
3. **Group findings by rule and unit.** A list of 40 line findings is noise; "6 × `D001` in
   `orders`, all the same import" is a decision.
4. **Propose one remedy per group**, with the file and the replacement dependency named.
5. **The human decides.** The agent may propose a waiver; only the owner may own one.

Guardrails:

- No auto-merge and no agent-authored approval.
- No agent-authored waivers: a waiver is a named person accepting debt.
- No executing product code to "see what happens"; the enforcers read source.
- Quote evidence verbatim. A finding without a path and line is an opinion.
- Agents are bad at product intent, domain naming, and whether a boundary is commercially right.
  Keep those decisions human.

The point is not that AI reviews instead of people. It is that the **mechanical half of review is
reproducible**, so the human half gets the attention.

## 5. Finding problems earlier

| Defect class | Found at | Rule |
|---|---|---|
| Module reaches into another's implementation | pull request | `D001` |
| Dependency cycle | pull request | `D005` |
| Transitive implementation leak | pull request | `D008` |
| Mutable contract or exposed collection | pull request | `C001`, `C002` |
| Contract surface changed without review | pull request | `G004` |
| Shared table or cross-module static | design / pull request | `A001`, `A003` |
| Undeclared module | CI | `G005` |

The cost curve is the argument: a finding at PR time costs minutes, at integration days, and in
production an incident with a postmortem. ACIMA does not prevent every defect; it moves a specific,
mechanical class of them to the cheapest possible moment.

## 6. Responsibility focus

The unit map is an ownership map. Use it that way:

- **One unit, one owner.** Contract changes route to that owner; implementation changes do not need
  cross-team review unless they add an edge.
- **The waiver file is a debt ledger.** Every entry has a name and a date, so "who owes what" is a
  query, not a meeting.
- **Reviewers discuss outcomes, not boundaries.** "Does this pricing change do what the ticket
  says?" is review. "Is Orders allowed to call Catalog?" is a build error.
- **Disagreement about a boundary is an org question.** If two teams cannot agree who owns a
  concept, fix the ownership first (`../standard/09-adoption.md` §9.4); no rule will settle it.

This is what lets a reviewer discover product problems faster: attention is not spent policing
structure that a machine already polices.

## 7. Narrow scopes and fewer side effects

Two properties make scope assertable:

1. **Contracts and implementations are different kinds of change.** A contracts diff is a published
   surface change and deserves its own PR, its own reviewer, and often a version note. An
   implementation diff is private. Mixing them hides the surface change inside a refactor.
2. **The graph is explicit.** With no implementation references (`D001`), no cycles (`D005`), no
   transitive leaks (`D008`), and no shared mutable statics (`A003`), the affected units are
   derivable from the declared edges. Blast radius stops being a discovery.

Scope checklist for a reviewer:

- [ ] every changed file belongs to a declared unit
- [ ] no new edge outside the allowed-edge matrix
- [ ] the contracts diff is additive, or carries a deprecation/version note
- [ ] schema or migration changes are not hidden inside an implementation PR
- [ ] if there is a waiver, it names this change and expires
- [ ] the enforcer run is attached and discovered the expected units

Side effects to check explicitly, because they are the ones that escape tests:

| Side effect | Where it hides | Rule |
|---|---|---|
| Caller mutates a shared contract value | a mutable collection or setter added "for convenience" | `C001`, `C002` |
| One module writes another's table | a repository reached through a shared connection | `A001` |
| Modules coordinate through a static | a cache or flag declared `static` | `A003` |
| A change reaches a module through a transitive reference | a package that re-exports an implementation | `D008` |
| An undeclared module escapes the map | a new folder outside every declared path | `G005` |

## 8. Reviewer checklist

- [ ] the change is one concern; contracts and implementation are separate if both moved
- [ ] every touched unit is declared and has an owner
- [ ] no new edge contradicts the allowed-edge matrix
- [ ] contract changes are immutable, typed, framework-free, and documented
- [ ] the API baseline diff is reviewed, not regenerated blindly
- [ ] no cross-module persistence, configuration, or static state was introduced
- [ ] waivers, if any, have an owner, a reason, and a near expiry
- [ ] the enforcer ran on this commit and found the expected units
- [ ] tests cover the behaviour change, not just the structure
- [ ] the PR description states the product outcome, not only the refactor

## 9. Measuring whether it worked

Measure before and after; do not assume.

| Metric | What it tells you |
|---|---|
| Review turnaround (median hours) | whether decisions got faster |
| PR size (median changed lines) | whether scopes actually narrowed |
| Escaped boundary defects | whether earlier detection is real |
| Rework rate after review | whether findings arrive before approval |
| Waiver age and unowned waivers | whether exceptions are being managed |
| Agent suggestions accepted / corrected | whether AI assistance is calibrated |

Report the trend, not a single month. A number that only improves is a number nobody trusts.

## 10. Anti-patterns

| Anti-pattern | Why it hurts |
|---|---|
| Rule-lawyering in comments | the gate already decides; arguing adds latency and no information |
| Gate as a substitute for design review | it checks structure, not whether the product is right |
| AI rubber-stamping | an agent accepting a diff it cannot justify is worse than no agent |
| Reviewing generated code line by line | exclude it, and assert where it came from |
| A giant "architecture cleanup" PR | unreviewable; batch changes in slices that fit one decision |
| Waiving to unblock a release | converts a visible defect into invisible debt |

## 11. Language for review comments

**Dependency is allowed:**

> This adds `Orders → Catalog.Contracts`, which the matrix allows. The contract call returns
> `ProductView`; no schema or implementation is exposed. Approved from the structure side.

**Contract change:**

> This changes a published contract. It is additive, so consumers keep compiling; the API baseline
> diff is in the PR. @catalog-owner, you own this surface — please confirm the new field's meaning.

**Exception:**

> This needs a `D001` waiver to land this sprint. Add it with your name, the migration ticket, and a
> 30-day expiry, and I'll approve. If the ticket slips, we re-decide rather than auto-renew.

More messaging patterns: [`skills/acima-adoption/references/40-communication.md`](../../skills/acima-adoption/references/40-communication.md).
