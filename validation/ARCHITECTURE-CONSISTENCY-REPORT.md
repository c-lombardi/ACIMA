# Architecture Consistency Report

**Status:** IN PROGRESS — internal review only
**Subject:** ACIMA abstract architecture, independent of analyzer behaviour
**Sources:** `docs/standard/00-preface.md`–`12-library-profile.md`, `docs/rules/*`, `tools/acima-spec/rules.json`
**Method:** Obligation-by-obligation reading; cross-check against the catalog's level and
execution contract; no source changes were made during this audit. Corrections applied
afterwards are marked in the findings.

## Summary

The base model is understandable and unusually explicit about ownership. It is not
internally consistent enough to support unconditional conformance claims. The most serious
issues are:

1. The standard says every MUST maps to a machine-checkable rule and that a rule not
   executed is not a rule, while six normative rules are explicitly `executed: false` at
   every conformance level.
2. The waiver definition required an exact finding fingerprint while the governance chapter
   matched on rule + scope; §7.5 was corrected to require the fingerprint, so this
   contradiction is closed (the finding schema still omits `fingerprint`, C-14).
3. Base mode and service mode had different contract granularity and different kernel
   rules with no machine-readable selector; `acima.config.json.mode` and the §11.12
   precedence now select and constrain them, so this issue is closed.
4. P9.5 imposes a version-bounded limit on immutability waivers without any schema field,
   catalog rule or review procedure that can evaluate it.

These are architecture-level issues. They must not be "fixed" only by changing analyzers.

## Findings

| ID | Classification | Principle / section | Finding | Consequence |
|---|---|---|---|---|
| C-01 | CONTRADICTORY | Preface 0.1; P8/P8.1; `08` §8.1, §8.6 | "Every MUST maps to at least one machine-checkable rule" and "a rule that is not executed is not a rule" coexist with six MUST-level rules that every reference enforcer reports as `executed: false`. | No repository using the reference enforcers can truthfully claim full L1/L2/L3 execution. The standard's central promise is false as written. |
| C-02 | CONTRADICTORY | P8.1 vs `08` §8.6 | P8.1 requires every rule at the declared level to execute in CI on every change; §8.6 permits an enforcer to report a rule as `info` with `executed: false` and still be part of a claim that lists it. | "Partial conformance" is honest reporting but is not a level conformance claim. The documents do not say which label wins. |
| C-03 | VALIDATED | P2.1 vs P11.1, P11.4 | Base mode: exactly one contracts unit per module. Service mode: one contracts project per outward-facing layer, none for the domain. `acima.config.json.mode` now selects the mode; service mode supersedes P2.1. | The granularity conflict is resolved by declaration and tested; a reader can no longer apply both rules at once. |
| C-04 | VALIDATED | P3.5 vs P12.1–P12.2; `11` §11.12 | Base mode permits a legacy shared kernel in contracts; service mode forbids it and calls absolute isolation the default for new systems. `mode` selects which applies, and the profile runner rejects a mismatch. | The same contract is no longer judged under two incompatible modes; the declaration is explicit and tested. |
| C-05 | PARTIALLY VALIDATED | P9.1, P9.3; G001; `07` §7.5 | P9.1 requires the exact finding fingerprint. §7.5 previously matched only rule + scope; it now requires `rule`, `scope` and `fingerprint`. G001's one-line catalog summary still lists only owner, reason, scope and expiry. | Closed in the governance chapter and preflight; the catalog summary and §7.2 finding schema remain incomplete. |
| C-06 | UNDERSPECIFIED / UNSUPPORTED | P9.5 | A waiver must not permit a C001–C006 violation for longer than one minor version; the waiver schema has no contract/standard version, and no rule computes this limit. | The requirement is unenforceable and cannot be audited from a waiver file. "One minor version" is also ambiguous: standard version or contract version? |
| C-07 | UNDERSPECIFIED | P4.2, P4.3; G003; C007 | "Consumer-shaped" is defined by a question ("would the provider's contract change if the consumer disappeared?"), not by a decidable property. G003 only checks documentation; C007 is not executed. | The requirement relies entirely on human judgment, but the specification presents it alongside machine-enforced rules without a review procedure or evidence format. |
| C-08 | UNSUPPORTED / NOT MACHINE-CHECKABLE | P7.6 | A contracts unit must be independently releasable: publishing X.Contracts must not require publishing X. | No catalog rule, baseline, or CI check evaluates release independence. A repository can be L3 and violate this. |
| C-09 | AMBIGUOUS | P8.1, `08` §8.1; P8.4 | "Every rule required by the declared level" is category-based (`D*`, `L*`, `G*`, etc.), but warnings are included in the level even though they are not merge-blocking. | "Required" can mean executed, reported, or blocking. The conformance claim is unclear about warnings and unexecuted rules. |
| C-10 | AMBIGUOUS | `00` §0.3 vs P13.1 | Scope excludes front-end framework choice, but P13.1 imposes a UI/API workflow-equivalence obligation. | Full-stack applicability is asserted without a front-end model, evidence format, or enforcement boundary. |
| C-11 | UNDERSPECIFIED | `11` §11.1–§11.2, §11.10; `conformance/topology.py` | The profile claims to be domain- and language-agnostic, but its manifest and fixtures are .NET-shaped (`csproj`, namespace tokens), and "project" is not defined for TypeScript/Go/Python packages. | The profile's applicability outside .NET is not established. A TypeScript service can satisfy the prose but fail or evade the runner. |
| C-12 | AMBIGUOUS | `02` §2.12, P10–P13, `11` §11.1 | "Service" contains "one primary module and its layers"; the base module still has one contracts unit, while the service has several. The relationship between module contracts and layer contracts is not defined. | Ownership of a contract can be attributed to both a module and a layer. It is unclear which rule applies when they conflict. |
| C-13 | UNDERSPECIFIED | P1.3, A001; `06` §6.5 | Persistence ownership is a MUST, but A001's automated detection is limited to static SQL/ORM names; runtime database grants are "recommended", not required evidence. | A repository can pass A001 while sharing a database at runtime. The architecture's autonomy claim is stronger than its evidence model. |
| C-14 | PARTIALLY VALIDATED | P8.2, `07` §7.2 | The finding schema is normative, but `fingerprint` (required by P9.1/G001) is not in the normative finding schema; profile findings (`S` rules) use the same object without saying whether they carry fingerprints. | Waiver matching now requires the fingerprint (§7.5), but the finding object still omits it; profile reporting remains underspecified. |

## Detailed analysis

### C-01/C-02 — The execution contradiction

**Exact issue.** `00-preface.md` §0.1 says every MUST maps to at least one
machine-checkable rule. P8 says "A rule that is not executed is not a rule." P8.1 requires
every rule at the declared level to execute in CI. But `conformance/coverage.json` and all
four reference enforcers report exactly six catalog rules as not executed:
`C003`, `C007`, `L004`, `A002`, `A004`, `G004`. These are not obscure rules: `L004` is in
L1, `C003`/`C007`/`G004` are in L2, and `A002`/`A004` are in L3.

**Scenario.** A team declares L2, runs the TypeScript enforcer, and receives exit 0 with
zero unwaived errors. `C003`, `C007` and `G004` are listed as not evaluated. The skill's
current definition says the repository is "conformant at a level only when the run artefact
shows zero unwaived errors at that level." That sentence would call the run conformant.
P8.1 says the level's rules must execute. Both cannot be true.

**Why it matters.** This is not a tooling detail. It determines whether an ACIMA
conformance claim means "all required rules passed" or "the implemented subset passed."
Customers, auditors and AI agents will interpret a green gate as the former.

**Interpretations.**

1. **Strong reading:** six rules are normative, so no level claim is available until they
   execute. This is consistent with P8 but means the shipped reference enforcers cannot
   certify any level.
2. **Subset reading:** the catalog has "portable" and "native/manual" rules; a level claim
   covers only executed portable rules, and the rest are explicitly listed. This is
   consistent with §8.6 but contradicts P8.1 and the preface.
3. **Profile reading:** L1–L3 are base-mode labels; the service profile has its own 12
   checks; "conformance" should be profile-specific. This does not resolve the six base
   rules.

**Recommendation.** Define two claim terms explicitly: **full conformance** (every rule
required by the level executed, with no unresolved manual requirement) and **partial
assessment** (executed subset; mandatory unexecuted rules listed; never called
conformance). Either implement the six rules or narrow P8.1 and the preface. Do not use
"conformant" for a run that contains `executed: false` at the declared level. This is
decision AD-01/AD-02.

### C-03/C-04/C-12 — The two-mode problem

**Exact issue.** P2.1's "exactly one contracts unit" and P3.5's kernel allowance are
base-mode statements. P11.1/P11.4 and P12 are service-mode statements. Chapter 11.12 calls
the profile a refinement and says the compatibility column is legacy; P12 calls absolute
isolation "the default for new systems." That is a coherent design intention, but the
normative text does not define:

- which mode a repository is in;
- whether a repository can mix modes;
- which document wins when a base obligation and a profile obligation conflict;
- whether a service is a module for the purpose of P1/P2/P3/P7.

**Scenario.** A new TypeScript service has `Orders.Api.Contracts`,
`Orders.Application.Contracts`, and no domain contracts. A reviewer applying P2.1 sees three
contracts units for one service and flags a violation. A reviewer applying P11 sees the
correct shape. The repository has no `mode` field to settle the question.

**Why it matters.** A standard whose central unit of ownership changes between chapters
cannot be applied consistently by multiple teams or agents. It also makes the catalog
mapping ambiguous: `D003` says contracts cannot reference contracts, but in service mode
`Api.Contracts` and `Application.Contracts` are both contracts and must not reference each
other; the transform rule adds a requirement the base catalog does not express.

**Recommendation.** Add an explicit `mode` or `profile` declaration with allowed values
(`base` and `service-topology`) and a precedence statement: profile obligations supersede
the named base obligations, not the whole base standard. Define "module" inside a service
and state which contract unit owns which layer surface. This is AD-03/AD-04.

### C-05 — Waiver identity

**Exact issue.** P9.1 says every waiver MUST name "the exact finding fingerprint." The
waiver example in P9 includes `"fingerprint": "sha256:1f0c…"`. G001's fix text says a
unit/path waiver without a fingerprint is rejected. At audit time, `07` §7.5 said "A waiver
matches a finding only when `rule` and `scope` both match" and listed mandatory fields as
owner, reason, expires and reviewedOn. Its example had no fingerprint. The catalog's G001
summary still mentions owner, reason, scope and expiry, not fingerprint.

**Scenario.** A team writes a waiver with `rule: D001`, `scope: unit:orders`, owner and
expiry, but no fingerprint. Under §7.5 it suppresses every D001 finding in `orders`
forever, including new ones. Under P9.1/G001 it is invalid. The two texts give different
answers for the same artifact.

**Why it matters.** The fingerprint is the mechanism that makes a baseline safe to commit.
If the governance chapter permits broad waivers, the architecture's exception model is
weaker than advertised. The implementation and skill choose fingerprints; §7.5 was
corrected to match them, while §7.2 and the catalog summary remain incomplete.

**Recommendation.** Make `fingerprint` mandatory in §7.5 and in the normative finding/
waiver schema; define a stable fingerprint algorithm per language; state that scope is a
secondary filter, never a substitute. This is AD-05. **Status:** §7.5, the preflight and the
skill now require it; §7.2 and the catalog summary are still open.

### C-06 — The immutability waiver limit

**Exact issue.** P9.5 says a waiver must not permit a C001–C006 violation for longer than
one minor version; those are breaking changes handled by G004. But the waiver object has
no standard version, contract version, or "first waived in" field. G002 only checks the
expiry date. Nothing computes "one minor version."

**Scenario.** A team waives C001 for 12 months and declares L2. The waiver has a valid
owner and expiry, so G001/G002 pass. Under P9.5 the waiver should be invalid after the next
minor version, but no tool can tell when that is or which contract version applies.

**Why it matters.** This is a normative MUST with no evidence path. It also confuses
standard versions with contract versions. Either the requirement is a policy that needs
manual review, or it needs metadata and a rule.

**Recommendation.** Add `standardVersion`/`contractVersion` metadata and a policy check, or
remove P9.5 from the MUST set and make it a review guideline. Do not leave it as an
unimplemented MUST. This is AD-06.

### C-07 — Consumer-shaped contracts

P4.2 is a useful design test but not a decidable property. The specification says G003
review and C007 are the enforcement, but G003 only checks documentation and C007 is not
executed. A provider can name a consumer in a type, add consumer-specific optional
parameters, and pass all currently executed rules. The architecture should either define a
reviewable evidence format (consumer list, contract change rationale, deprecation record)
or label P4.2 as human judgment rather than implied automation.

### C-08 — Independent release

P7.6 is a release-engineering property. No current rule reads package manifests, publication
graphs, or release pipelines. This is a legitimate requirement that may be intentionally
manual, but the standard should say so and identify the evidence (published package graph,
release workflow, artifact dependency check). Otherwise an L3 claim silently includes an
unverified property.

### C-09 — "Required" and warnings

The level table includes warning-severity rules (L004, C007, A002, A004, G003) in the
required categories. P8.1 says every required rule executes. A warning does not block a
merge, but it is still part of the level. The documents should distinguish "executed",
"reported", and "blocking". Otherwise a zero-error run is described as full conformance
even when warnings were never evaluated.

### C-10 — Full-stack scope

Chapter 0 excludes the front-end framework choice, but P13.1 requires UI and API to enforce
the same workflow. `ST-11` checks token mentions in declared UI and API files, not semantic
equivalence. This is a reasonable review aid, but it is not enough to support a general
full-stack applicability claim. The standard should state that the profile governs the
API/domain side and treats the UI as an evidence source, or add a UI profile.

### C-11 — Topology language neutrality

Chapter 11 says the profile is domain-agnostic and describes projects, layers and
contracts generically. The runner and test fixtures are .NET-shaped: `csproj`, namespaces,
coverage JSON, `Amazon.CDK`, `Stripe.net`. There is no TypeScript/Go/Python topology
fixture. The profile may be conceptually portable, but its executable definition is not.
This belongs in the language support matrix, not hidden in a claim of profile
implementation.

### C-13 — Runtime persistence ownership

A001's static SQL/table checks are useful but cannot prove runtime isolation. The
architecture itself recommends database users/grants as the only unbypassable enforcement
(`docs/rules/autonomy.md` A001). That is an admission that the catalog rule is a partial
implementation of P1.3/P7.1. The conformance model should require runtime grant evidence
at L3 or explicitly narrow L3 to static evidence.

### C-14 — Finding schema and fingerprints

`07` §7.2 defines required fields without `fingerprint`. P9.1/G001 require a fingerprint
for waivers. The reference enforcers add it, and the skill relies on it. The normative
schema should include it, or state that it is a tool-added field with a required algorithm
for waiver matching. Profile `S` findings also need a clear statement on fingerprinting.

## What is consistent

The following survived the audit without a material contradiction:

- The dependency matrix, module anatomy, contract types and runtime boundary catalogue are
  mutually compatible.
- P1, P2 (base), P5, P6 and P7's ownership model reinforce one another.
- The service profile's naming rules, layer matrix, inter-service contract and vendor seam
  are internally coherent, given its own definitions.
- The library profile's classification model does not waive findings; it reports declared
  edges separately, which is consistent with P9's insistence on visible exceptions.
- The conformance evidence model (config, run, artifact, waiver report, pipeline) is sound
  in principle; its execution semantics are the problem, not its evidence categories.

## Documentation inconsistencies observed (not architecture defects)

These are recorded here because they affect how the architecture is communicated, but they
are not counted as principle contradictions:

- `docs/rules/index.md` says "Four rules cannot be fully decided" and lists `C003`, `C007`,
  `A002`, `G003`; the actual non-executed set is six and includes `L004`, `A004`, `G004`,
  not `G003`.
- The same catalog's severity paragraph says only `L004`, `C007`, `A002`, `A004`, `G003`
  are warnings; that part is correct.
- The skill reference `00-preflight.md` says brownfield starts at 10+ source files; the
  code and `SKILL.md` classify any existing source as brownfield.
- The skill reference says the waiver writer groups by `(rule, unit)`; the code emits one
  waiver per finding fingerprint.
- `docs/status.md` says the 29-rule catalog is "implemented and verified" while also
  correctly listing six unexecuted rules; "verified" needs a defined scope.

These are handled in the product/consistency follow-up, not by changing the principles.
