# Architecture Decisions

**Status:** ACCEPTED — AD-01/AD-02/AD-03/AD-05/AD-06/AD-11 implemented on 2026-11-08; the rest remain proposed
**Purpose:** Record the significant architecture-level choices exposed by the audit, with
evidence, alternatives, tradeoffs, compatibility impact and recommended approach. These
decisions are deliberately separated from enforcement fixes. Implementing a decision
requires an explicit change to the standard and its evidence.

No decision changes P1–P13 by itself. Accepted decisions are implemented explicitly with
tests; the rest remain proposals and do not alter the architecture by implication.

## Decision register

| ID | Decision | Status | Blocking? |
|---|---|---|---|
| AD-01 | Define “full conformance” versus “partial assessment” | ACCEPTED — executable claim gate and tests | Yes |
| AD-02 | Make base mode vs service mode explicit | ACCEPTED — `mode` selector, precedence, tests | Yes |
| AD-03 | Define contract granularity and module/service ownership | ACCEPTED — selector + P2.1/P3.5 supersession | Yes |
| AD-04 | Make the shared-kernel allowance explicitly legacy and mode-bound | PROPOSED | No |
| AD-05 | Make finding fingerprints mandatory in the normative waiver/finding schema | ACCEPTED — fingerprint in §7.2 and rules.json | Yes |
| AD-06 | Resolve the P9.5 version-bounded immutability waiver | ACCEPTED — advisory in Draft 1 | No |
| AD-07 | State the scope limits for multi-tenant, full-stack and platform systems | PROPOSED | No |
| AD-08 | Define evidence for independent release (P7.6) | PROPOSED | No |
| AD-09 | Require runtime persistence evidence for L3 autonomy | PROPOSED | No |
| AD-10 | Define the service profile independently of .NET project mechanics | PROPOSED | Yes |
| AD-11 | Decide the disposition of the six non-executed catalog rules | ACCEPTED — manual evidence path | Yes |
| AD-12 | Align the human catalog and skill guidance with the executable contract | PROPOSED | No |

---

## AD-01 — Define conformance claim classes

**Evidence.** Preface §0.1 and P8.1 promise machine-checkable execution for every MUST;
`08` §8.6 permits `executed: false`; `conformance/coverage.json` and all four enforcers
report six rules as not executed. No level is fully executed by the reference tooling.

**Options.**

1. **Strong conformance.** A level claim requires every rule in that level to execute and
   pass. Until the six rules exist, no full L1/L2/L3 claim is available from the reference
   tooling. Honest, but makes the current product unable to certify anything.
2. **Two claim classes.** `FULL CONFORMANCE` = all level rules executed with evidence;
   `PARTIAL ASSESSMENT` = executed subset, with every non-executed required rule listed and
   no use of the word "conformant". This preserves usefulness without overclaiming.
3. **Narrow the levels.** Remove the six rules from the level sets until implemented.
   Simple, but weakens the architecture to match the tools — the wrong direction.

**Recommendation.** Option 2. Add the claim classes to chapter 8 and the skill. A partial
assessment may be useful, but it is not a conformance claim and cannot be reported as one.
Make the JSON artifact carry `claim: "full" | "partial"` and the list of unexecuted required
rules.

**Compatibility.** Existing repositories that say "L2" must re-label as full, partial, or
unverified. This is a documentation/claim change, not a rule change. It is compatible with
all existing configs.

**Acceptance criteria.** The standard, CLI report, and skill all use the same two terms;
a run with any `executed: false` at the declared level cannot produce `claim: "full"`; tests
pin the behavior.

**Resolution (2026-11-08).** Implemented as option 2. `conformance/acima_claim.py` and
`tools/acima.py claim` compute `FULL CONFORMANCE` only when every required rule executed or
has accepted repository-scoped manual evidence, with zero unwaived errors. Missing evidence
returns `PARTIAL ASSESSMENT`; malformed input exits `2`. `conformance/test_claim_model.py`
pins L1/L2/L3 counts, evidence expiry/scope, error blocking and CLI exit codes.

---

## AD-02 — Make base mode vs service mode explicit

**Evidence.** P2.1 vs P11.1/P11.4; P3.5 vs P12.1–P12.2. Chapter 11.12 describes the
relationship, but no configuration field or normative precedence rule selects a mode.
`acima.config.json` has no `mode`; the service profile uses a separate
`acima.topology.json`.

**Options.**

1. **Mode field.** Add `"mode": "base" | "service-topology"` to `acima.config.json` (and
   require the topology manifest when the mode is service). Clear and machine-readable.
2. **Profile field.** Add a `"profile"` object parallel to `units`; leave the base mode as
   the default. More extensible, but two sources of truth for the same decision.
3. **Documentation-only precedence.** State that P11/P12 supersede P2.1/P3.5 when a
   topology manifest is present. Minimal change, but still not machine-checked.

**Recommendation.** Option 1 with a small profile object if needed later. Define precedence
explicitly: the service profile supersedes P2.1's one-contract-unit granularity, P3.5's
kernel allowance, and the base module-to-module crossing model; all other base principles
continue to apply. A repository cannot mix modes silently.

**Compatibility.** New optional field; existing configs default to `base`. A repository
with a topology manifest but no mode should fail configuration validation rather than
guess. This is a minor-version change.

**Acceptance criteria.** Config schema has the field; enforcers reject unknown modes;
topology runner requires service mode; tests cover base/service and mixed attempts.

**Resolution (2026-11-08).** Implemented as option 1. `acima.config.json.mode` is the only
selector; absent means `base`. `service-topology` applies P1–P9 plus P10–P13 and supersedes
exactly P2.1 and P3.5. The topology runner exits `2` on a missing/mismatched mode or profile,
and `conformance/test_mode_precedence.py` plus `test_topology.py` pin the behavior. Base
enforcers remain mode-agnostic because they execute the unchanged P1–P9 rule set.

---

## AD-03 — Define contract granularity and module/service ownership

**Evidence.** P2.1 says one contracts unit per module. P11.1 says one per outward-facing
layer; P11.4 says the domain has none. Chapter 11 calls the service an envelope containing
“one primary module and its layers” but does not define how the service's layer contracts
relate to the module's contracts unit.

**Options.**

1. **Service is the module.** In service mode, the service is the ownership unit and the
   layer contracts are its public surfaces. P2.1 is read as “one contracts surface per
   outward-facing boundary”, not one project per service.
2. **Module is nested.** A service contains one module per layer group, each with its own
   contracts; the service is only a naming/deployment envelope. This multiplies modules and
   makes P1/P7 ownership ambiguous.
3. **Keep both, with a mapping table.** Define module-level contracts (base) and
   layer-level contracts (service), and state that service mode replaces the base
   granularity. This is the status quo, made explicit.

**Recommendation.** Option 1 plus an explicit mapping: in service mode the service is the
module for P1/P7 ownership; each outward-facing layer has one contracts project; the domain
has none. Replace “one primary module and its layers” with a definition that does not imply
two ownership levels. Add a table mapping each base obligation to its service-mode
expression.

**Compatibility.** Tightens terminology, not behavior. Existing service repositories are
already shaped this way; base repositories are unaffected.

**Acceptance criteria.** `02-vocabulary.md` and chapter 11 use one definition of module and
service; the base/P11 conflict is resolved in a precedence note; no text says a service has
one contracts unit.

**Resolution (2026-11-08).** Implemented as option 1 plus the mapping table: in service mode
the service is the ownership unit for P1/P7, each outward-facing layer has one contracts
project, and the domain has none. §11.12 states that P2.1 is superseded, not reinterpreted;
`02-vocabulary.md` now carries the same mapping. `mode` selects the reading, so the same
repository cannot be judged under both.

---

## AD-04 — Make the shared-kernel allowance explicitly legacy and mode-bound

**Evidence.** P3's headline says contracts reference “not the shared kernel”; P3.5 allows
existing repositories to retain it. P12 removes it for new systems. The allowance is clear
in prose but not in the config or the rule's level mapping.

**Options.**

1. **Keep as legacy only.** Require a `legacyKernel: true` declaration to allow kernel
   edges; default is absolute isolation. New repositories cannot set it without a review
   record.
2. **Remove the kernel entirely.** Cleanest, but breaks the stated migration path and the
   existing examples/fixtures.
3. **Leave as prose.** Current state; readers must infer mode. Not recommended.

**Recommendation.** Option 1. It preserves the migration path while making the exception
visible and reviewable. The kernel is not a general shared library; its admission test
remains the four-part test in §4.5.

**Compatibility.** Existing base repos with a kernel add one declaration; service repos
must not. This is a minor-version, opt-in migration.

**Acceptance criteria.** Config schema, enforcers, and docs agree; a kernel edge in default
mode fails; a declared legacy kernel gets the existing D007 constraints; no new contracts
may reference it.

---

## AD-05 — Make finding fingerprints mandatory

**Evidence.** P9.1, P9.3, G001 and the reference enforcers require a fingerprint. `07` §7.5
says a waiver matches on rule + scope and omits fingerprint from its mandatory fields. This
is a direct contradiction, and it permits broad waivers that hide new findings.

**Options.**

1. **Fingerprint required, scope secondary.** Add `fingerprint` to the normative finding
   and waiver schema; define a stable algorithm; a waiver with no fingerprint is invalid
   (`G001`). This matches P9.1 and the implementation.
2. **Rule + scope remains sufficient.** Remove the fingerprint requirement and accept
   broad waivers. This weakens the exception model and contradicts P9.1/G001.
3. **Fingerprint required only for baselines.** Allow policy waivers for whole units with
   a separate, stronger review. Adds complexity without evidence of need.

**Recommendation.** Option 1. Define the fingerprint as a hash over rule id, normalized
path, and a stable evidence discriminator; specify path normalization and line-number
policy. Add it to `07` §7.2/§7.5 and to the waiver template. A scope-only waiver is a
`G001` error, not a valid broad exception.

**Compatibility.** Existing valid waivers already have fingerprints; malformed ones become
errors, which is the intended behavior. This is a patch/clarification if the algorithm is
already implemented; a minor if the schema changes.

**Acceptance criteria.** Schema, standard, enforcers, preflight, and skill all require the
same fields; a scope-only waiver fails G001; the fingerprint is stable across line moves
where the evidence identity is unchanged.

**Resolution (2026-11-08).** `fingerprint` is now in the normative finding schema in §7.2, the
`rules.json` `findingSchema` and G001's summary, and the waiver contract in §7.5. The existing
enforcers and preflight already enforced it; the documentation/schema gap is closed and pinned
by `test_documentation_contract.py` and `test_claim_model.py`.

---

## AD-06 — Resolve P9.5

**Evidence.** P9.5 limits a C001–C006 waiver to one minor version. The waiver schema has no
version field; G002 checks only dates; no rule computes the limit. “Minor version” could
mean standard version or contract version.

**Options.**

1. **Make it a policy, not a MUST.** State that immutability waivers should be short and
   reviewed at every contract release; remove the unenforceable MUST. Honest but weaker.
2. **Add metadata.** Add `contractVersion`/`standardVersion` and a `G00x` check that rejects
   an immutability waiver spanning more than one minor version. Requires a version source
   and release history.
3. **Replace with a fixed maximum.** Forbid C001–C006 waivers longer than, say, 90 days.
   Simple and checkable, but arbitrary and still not tied to versions.

**Recommendation.** Option 1 for the draft, with a note that a future contract-release
profile may add Option 2. Do not keep an unenforceable MUST. If the project wants the
stronger rule, implement Option 2 before claiming P9.5.

**Compatibility.** Removes a requirement no implementation can satisfy; no repository
behavior changes. Document it as a scope reduction.

**Acceptance criteria.** P9.5 either has a field and a rule or is explicitly advisory; no
document claims it is enforced.

**Resolution (2026-11-08).** Implemented as option 1. P9.5 is explicitly advisory in Draft 1:
it says a C001–C006 waiver should not outlive one minor version and must be reviewed at every
contract release, but no standard-version or contract-version field exists. §7.5 states the
same limitation; `test_documentation_contract.py` prevents a return to an unenforceable MUST.

---

## AD-07 — State scope limits for multi-tenant, full-stack, and platform systems

**Evidence.** The applicability matrix marks multi-tenant as unsupported, full-stack as
ambiguous, and shared platform as ambiguous. Chapter 0 excludes front-end frameworks;
P13.1 asserts a UI/API workflow requirement; no tenancy term exists.

**Options.**

1. **Declare out of scope.** State that ACIMA governs back-end ownership and static
   boundaries; multi-tenancy, UI semantics, and platform operations need separate profiles.
2. **Add profiles.** Build tenancy, UI, and platform profiles. High cost; no evidence yet.
3. **Leave implicit.** Current state; invites overclaiming.

**Recommendation.** Option 1 now, with a roadmap entry for profiles only if a real pilot
requires them. This is not a failure of the architecture; it is an honest boundary.

**Compatibility.** Narrows marketing/claims, not code. Documentation updates.

**Acceptance criteria.** README/status/product contract and chapter 0 state the boundaries;
the applicability matrix is referenced from the standard; no claim of general full-stack or
multi-tenant coverage remains.

---

## AD-08 — Define evidence for independent release (P7.6)

**Evidence.** P7.6 is a MUST with no rule, no fixture, and no release artifact. It is a
legitimate property but currently unverified.

**Options.**

1. **Manual evidence.** Require a release-graph check or a signed release record in the
   conformance evidence; keep it out of the static catalog.
2. **Automated rule.** Add a package/release-graph rule that checks whether publishing the
   contracts artifact pulls in the implementation artifact. Language-specific and costly.
3. **Downgrade.** Make P7.6 advisory. Weakens the independence claim.

**Recommendation.** Option 1 for the draft: define the evidence (published package
metadata or a release pipeline assertion) and list P7.6 as a manual conformance item. If a
language profile can automate it, add a rule later.

**Acceptance criteria.** The self-certification template has a P7.6 row; the status page
does not claim it is automated.

---

## AD-09 — Require runtime persistence evidence for L3

**Evidence.** P1.3/P7.1 are data-ownership MUSTs. A001's static SQL check cannot prove
runtime isolation. The rule doc itself recommends per-module database users/grants as the
only unbypassable enforcement.

**Options.**

1. **Static-only L3.** Rename L3 “static autonomy” and require runtime evidence only for a
   higher “operational autonomy” claim.
2. **Runtime evidence at L3.** Require a grant configuration or test that proves each module
   can access only its own schema.
3. **Leave as is.** Current overclaim.

**Recommendation.** Option 1 for the draft, with Option 2 as the target for production
readiness. The architecture should distinguish compile-time isolation, static data
ownership, and runtime autonomy; they are not the same claim.

**Acceptance criteria.** L3 definition and status page name the evidence; A001 limitations
are explicit; a repository cannot claim runtime autonomy from static findings alone.

---

## AD-10 — Make the service profile language-neutral

**Evidence.** Chapter 11 calls the profile domain-agnostic, but the runner and fixtures are
.NET-shaped (`csproj`, namespaces, coverage JSON). There is no TypeScript/Go/Python
topology fixture. The profile's “project” is undefined outside .NET.

**Options.**

1. **Define a language-neutral manifest.** Projects are logical units with a language and a
   path; the runner consumes a normalized manifest; language adapters extract project
   references and package dependencies.
2. **Declare the profile .NET-only for now.** Honest, but narrows P10–P13 substantially.
3. **Leave prose-general, runner-specific.** Current state; not acceptable for a portable
   standard.

**Recommendation.** Option 1, starting with a normalized manifest and a .NET adapter. Add a
TypeScript fixture before claiming profile support there. Until then, the language support
matrix must say “service topology: .NET reference only.”

**Acceptance criteria.** A non-.NET fixture exercises ST-1–ST-12; the manifest schema is
documented; the profile claim names the implemented language adapters.

---

## AD-11 — Decide the six non-executed rules

**Evidence.** `C003`, `C007`, `L004`, `A002`, `A004`, `G004` are normative but
`executed: false` in all four profiles. They span every level.

**Options.**

1. **Implement them** with native analyzers or portable heuristics plus human review.
   Highest cost; restores full conformance potential.
2. **Reclassify them as manual evidence requirements.** Keep them normative, but define a
   review artifact and remove them from the “machine-checkable” claim. Honest, but changes
   what L1–L3 mean.
3. **Remove them from the catalog/levels** until implemented. Simplest, but loses important
   obligations (configuration isolation, API baseline, service locator, contract behaviour).
4. **Leave as is.** Unacceptable; it is the central contradiction.

**Recommendation.** Option 2 for a draft release: split the catalog into **automated** and
**manual-evidence** requirements, make the claim class explicit (AD-01), and require a
named reviewer/artifact for each manual rule. Then implement the highest-value rules
(A002, G004, L004) as the next enforcement milestone. Do not remove C003/C007; they are
core contract properties that need human review at minimum.

**Acceptance criteria.** Every rule has an `automation` field (`automated`, `manual`,
`unsupported`); levels list both; the claim artifact includes manual evidence; no run calls
itself full conformance when a required manual item is missing.

**Resolution (2026-11-08).** Implemented as option 2 with option 1 as the next enforcement
milestone. All 29 rules now carry `automation`; the six are `manual` with a
`manualEvidence` requirement. A full claim requires repository-scoped entries in
`.acima/manual-evidence.json`; the reference enforcers continue to report all six as
`executed: false`. The highest-value next implementations remain A002, G004 and L004.

---

## AD-12 — Align human documentation and skill guidance

**Evidence.** `docs/rules/index.md` says four rules need judgment and lists a set that
includes `G003` and excludes `L004`, `A004`, `G004`. The skill's `00-preflight.md` says
brownfield starts at 10+ files. `20-brownfield.md` says one waiver per rule/unit. These
contradict the executable contract and the skill's own hard rules.

**Recommendation.** Fix these as documentation/product corrections, not architecture
changes. Do not use them to justify analyzer behavior. Add a doc-consistency test that
compares the “not executed” set to `coverage.json` and the brownfield/waiver claims to
preflight tests.

**Acceptance criteria.** The docs name the actual six; the skill reference uses “any
existing source”; the waiver text uses “one per finding fingerprint”; a test prevents
regression.

---

## Decision sequencing

1. AD-01 and AD-11 first: without an honest claim vocabulary, every other status is
   misleading.
2. AD-02/AD-03/AD-04 next: they remove the mode and granularity ambiguity.
3. AD-05/AD-06: they make the exception model internally consistent.
4. AD-07–AD-10: scope and portability; can proceed in parallel with enforcement work.
5. AD-12: product correction; do it immediately after the audit, without waiting for the
   architecture decisions.

## What must not happen

- Do not change the analyzers to make C-01 disappear; the architecture claim is the
  problem.
- Do not remove the six rules merely to make a green scorecard.
- Do not add a tenancy or UI profile without a real pilot and evidence.
- Do not call the architecture “validated” because the reports exist. Validation requires
  external review and application evidence that this repository does not yet have.
