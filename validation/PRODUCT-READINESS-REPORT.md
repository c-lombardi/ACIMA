# Product Readiness Report

**Status:** IN PROGRESS — internal review only
**Scope:** ACIMA as a product for engineers, architecture leads and CTOs. This report does
not re-score the architecture or enforcement domains.

## Verdict

**PARTIAL — experimental technical preview, not self-service production infrastructure.**

The repository has an unusually strong explanatory surface: a normative standard, a rule
catalog, four reference implementations, violation galleries, a benchmark, a product
contract, a quickstart, and an adoption skill. A motivated engineer can clone it, run the
conformance suite, and see what the standard does.

The product is not ready for a broad production audience because:

- the standard has two modes without a single selector or precedence table;
- six normative rules are not executable, but the status page can read as “verified”;
- Java is documented but unsupported;
- the skill's references contradict its code;
- no real application adoption is documented;
- release/support boundaries and maintenance ownership are not explicit enough;
- hosted CI has never been observed.

## Scorecard

Rubric: 0 absent, 1 asserted, 2 specified/partial, 3 implemented and evidenced, 4
independently validated.

| Dimension | Score | Rationale |
|---|---:|---|
| Clarity of positioning | 2 | README/product contract explain contract isolation; “draft” and “default” are not consistently separated |
| Self-service usability | 2 | Quickstart/conformance suite; two modes and stale skill docs complicate first use |
| Documentation | 2 | Deep and abundant; four-vs-six, 24-of-24, brownfield/waiver drift |
| Installation | 2 | Python 3.9+ and language toolchains documented; no packaged CLI/install path? |
| Support boundaries | 2 | Java and profiles stated in places; no single support matrix |
| Operational reliability | 1 | Hosted CI unobserved; no release process/SLO; cancellation/universal output gaps |
| Maintainability | 2 | Tests/galleries; duplicated enforcers; six-rule gap; docs drift |
| Organizational applicability | 2 | Ownership/waivers/team model; no tenancy/platform/full-stack coverage |
| Evidence quality | 2 | Reproducible benchmark, raw outputs; author-adjudicated, no independent review |

No aggregate score.

## What a new user can do today

1. Clone the repository.
2. Run `python3 conformance/run.py` with the four toolchains installed.
3. Read `docs/start/quickstart.md`.
4. Inspect `examples/<language>/` and the violation galleries.
5. Run the enforcer on a repository with a hand-written `acima.config.json`.
6. Run `preflight.py` for base-mode classification and a draft unit map.

What they cannot do reliably:

- choose base vs service mode from a config field;
- adopt a service profile outside the .NET-shaped fixture;
- use a library profile in Python or Go;
- assess Java;
- get a truthful full L2/L3 conformance claim with six rules unexecuted;
- know whether a zero-unit preflight is ready or broken;
- find one current, consistent statement of brownfield/waiver rules;
- see a real application adoption or independent review.

## Positioning findings

### PR-01 — “Draft” and “default” are not distinguished at the point of use

The preface says Draft 1; chapter 11 says service topology is the default for new systems;
the skill says modular monolith and “services are an option later.” A CTO cannot tell
whether ACIMA is a modular monolith standard, a service standard, or both with a mode.

**Recommendation:** State the two modes on the README and in the quickstart; define which is
default for which starting condition; make the mode explicit in config.

### PR-02 — “Verified” is broader than the evidence

`docs/status.md` says the 29-rule catalog is “Implemented and verified,” then correctly
lists six rules not decided. The heading and the limitation conflict. A reader skimming the
table can conclude all 29 are enforced.

**Recommendation:** Rename rows to “Catalog defined” and “23/29 automated; 6 manual”;
include the claim class.

### PR-03 — Java is a first-class documentation profile with no product support

The Java profile is substantial, but there is no enforcer. Three benchmark repositories are
blocked. This is honest in the status page but easy to miss in the README.

**Recommendation:** Put Java in the support matrix as `NOT SUPPORTED` until an enforcer
exists; do not imply parity.

### PR-04 — Library and service profiles are presented as complete

The library profile is implemented for TypeScript/.NET only; the service profile is
exercised only against a .NET-shaped fixture. The docs state limitations, but the top-level
positioning treats both as parts of the standard.

**Recommendation:** Add a capability matrix with language/profile cells; link it from the
README.

## Documentation findings

| ID | Finding | Impact |
|---|---|---|
| PR-05 | Four-vs-six non-executed rules in `docs/rules/index.md` | Wrong mental model of coverage |
| PR-06 | Self-certification says “24 of 24” at L2; L2 has 25 rules | Arithmetic/credibility |
| PR-07 | Skill `00` says 10+ files brownfield; code says any source | Wrong classification |
| PR-08 | Skill `00`/`20`/`60` say per-rule/unit waivers; code per fingerprint | Broad baselines; wrong baseline size |
| PR-09 | Skill glossary says <10 sources greenfield, one implementation unit, one-unit waiver | Conflicts with standard/code |
| PR-10 | Skill has no service-topology or library-profile playbook | Default architecture inaccessible |
| PR-11 | No single support matrix | Users overestimate Java/profile support |
| PR-12 | No migration guide base→service | Users may apply wrong contract granularity |

**Disposition (2026-11-08):** PR-05–PR-09 were corrected in this iteration and are pinned by
`conformance/test_documentation_contract.py`. PR-10 is partially addressed by the `mode`
selector, an explicit `NOT SUPPORTED` stop for service topology, and Python/Go library stops;
no service workflow exists.
PR-11/PR-12 remain open.

## Installation and operation

The repository is source-first. `conformance/run.py` requires Python 3.9+, Node, Go and
.NET SDK for the full suite; Java has no enforcer. The preflight only needs Python. This is
reasonable for a standards repository, but:

- there is no packaged `acima` distribution or versioned install command documented in the
  product contract;
- hosted CI is not observed;
- there is no release cadence, support window, security policy, or maintainer list in the
  reviewed product pages;
- cancellation and tool-failure behavior are not fully tested.

**Recommendation:** Add an installation/support page with exact prerequisites, supported
platforms, CI status, versioning policy, and maintainer/contact path. Do not claim a support
level that is not tested.

## Evidence quality

The benchmark is a genuine asset: pinned commits, raw outputs, configs, adjudications,
checksums, and a preserved prior run. It is also:

- author-adjudicated;
- library-heavy, not application-adoption evidence;
- not independent;
- not a precision/recall estimate with reliable ground truth;
- not proof of architecture validity.

The product should present it as **benchmark evidence**, not a certification. The status and
release pages should state the evidence class.

## Product release disposition

| Capability | Status |
|---|---|
| Read the standard | PASS |
| Run reference enforcers | PARTIAL |
| Run conformance suite | PARTIAL (toolchains/Java) |
| Adopt base mode | PARTIAL |
| Adopt service mode | NOT SUPPORTED |
| Adopt library mode | PARTIAL (TS/.NET) |
| Self-service production adoption | NOT READY |
| Support/operational guarantees | NOT READY |

## Required next steps

1. Publish a one-page capability/support matrix.
2. Add the mode selector and precedence.
3. Correct the numeric/coverage claims.
4. Link the architecture consistency, enforcement and adoption reports from the README.
5. Add install/CI/support/maintainer information.
6. Obtain one real application pilot before using “adoption” as a product claim.
7. Preserve the experimental preview label until the release gate passes.
