# Architecture Validation Report

**Status:** IN PROGRESS — internal review only
**Subject:** ACIMA abstract architecture, independent of analyzer behaviour and skill
**Commit:** `25ed9f8c672c4e8031af7b50cc6b60b8635a0a2b`
**Review date:** 2026-11-08
**Disclosure:** This is an internal, same-assistant review. It is **not** independent
architectural review. No external reviewer, customer, or production team participated.

## 1. Verdict

**PARTIALLY VALIDATED — not ready for a full conformance claim.**

ACIMA has a coherent and distinctive core: contracts as a structural public surface,
consumer-owned integration ports, compile-time acyclicity, immutable messages, owned
persistence/configuration, and explicit expiring exceptions. The dependency model and
module anatomy are unusually precise, and the service profile is a serious attempt to make
ownership readable at scale.

The architecture is not yet internally consistent enough to support its strongest claims:

- its central promise that every MUST is machine-checkable is contradicted by six
  non-executed normative rules;
- its waiver identity rule was contradicted by its own governance chapter (corrected in §7.5 after this audit);
- its base and service modes have different contract granularity and kernel rules without a
  machine-readable mode or precedence at the point of use;
- its immutability-waiver limit is unenforceable;
- its applicability to multi-tenant, full-stack, and shared-platform systems is not
  established.

These are architecture-level findings, not merely documentation defects. The correct next
step is to resolve the claim vocabulary and mode semantics, then validate on real
applications. Do not optimize benchmark scores first.

## 2. Method

1. Read the complete normative specification, chapters 0–12, and the 29-rule catalog.
2. Reconstructed the architecture model and glossary without treating analyzer behavior as
   definition.
3. Checked every numbered obligation against the catalog and conformance level mapping.
4. Compared the standard's own claims to the implementation evidence and benchmark
   evidence.
5. Evaluated the model against the required architectural scenarios using ten criteria.
6. Classified findings using the mandated statuses.

No source was modified during this initial audit. The benchmark evidence
`benchmark-evidence/rw-2026-11-08-02` was used only as evidence, not as proof of
architecture validity.

## 3. Findings by classification

### VALIDATED

| ID | Finding | Evidence |
|---|---|---|
| A-V01 | The dependency matrix is explicit, exception-aware and internally coherent for the base module model. | `04` §4.1; P1–P5; D/L rules |
| A-V02 | The module anatomy (contracts / implementation / host / composition root) is clear and implementable in multiple languages. | `03`; `04`; examples |
| A-V03 | The contract-type catalogue and immutability rationale are coherent and give a defensible mechanism for retry/replay/comparison. | `05`; P6 |
| A-V04 | The service profile's naming, layer, inter-service and vendor-seam model is coherent on its own terms. | `11` §11.1–§11.7 |
| A-V05 | The library profile identifies the real public-API/adapter problem and classifies rather than deletes findings, which is the right architecture for a library boundary. | `12` |
| A-V06 | The conformance evidence model (config, run artefact, waiver report, PR gate) is directionally sound. | `08` §8.4 |

"Validated" here means **internally coherent and traceable to normative text**, not
"proven in production." Every empirical claim is separately marked.

### PARTIALLY VALIDATED

| ID | Finding | Why partial |
|---|---|---|
| A-P01 | P1 service ownership | A002 is unexecuted; A001 is static-only; runtime data isolation is not proven. |
| A-P02 | P2 contract isolation | Base one-contract-unit rule conflicts with service per-layer contracts; public-surface enforcement is language-dependent. |
| A-P03 | P3 zero-dependency contracts | Clear default, but the kernel allowance and service-mode absolute isolation are not selected by a config field. |
| A-P04 | P4 dependency inversion | Provided/consumer-owned port distinction is strong; consumer-shaped contract review and L004 are not executed. |
| A-P05 | P5 strict dependency boundaries | D/L rules execute; no application-scale evidence; L001 covers only four edges. |
| A-P06 | P6 immutable by default | C001/C002/C004/C005/C006 execute; C003 and C007 do not, so the principle is not fully evaluated. |
| A-P07 | P7 independent evolution | A001/A003 execute; A002/A004/G004 do not; P7.6 has no evidence path. |
| A-P08 | P10 service-aligned topology | Naming/topology model is coherent; the runner is .NET-shaped and no non-.NET fixture exists. |
| A-P09 | P11 layer contract independence | Model is coherent; no non-.NET proof; transform purity is not checked. |
| A-P10 | P12 absolute contract isolation | Default is clear and ST-5 is implemented in the profile; base compatibility mode is not machine-selected. |

### CONTRADICTORY

| ID | Finding | Evidence | Why it matters |
|---|---|---|---|
| A-C01 | The standard promises every MUST is machine-checkable, but six normative rules are `executed: false` at every level. | Preface §0.1; P8; `coverage.json`; four enforcers | A green run can be described as conformance even though required rules were not evaluated. |
| A-C02 | A waiver must carry an exact fingerprint, but the governance chapter says rule + scope is sufficient and omits the fingerprint. | P9.1, P9.3, G001, `07` §7.5 | Broad waivers can hide new findings, defeating the exception model. |
| A-C03 | P8.1 requires every level rule to execute in CI; §8.6 permits `executed: false` in a claim. | P8.1, `08` §8.1/§8.6 | "Partial conformance" is undefined; the claim label is ambiguous. |
| A-C04 | P9.5 imposes a version-bounded immutability waiver limit with no version field or rule. | P9.5, `07` §7.5, G002 | An unenforceable MUST cannot be audited. |

### AMBIGUOUS

| ID | Finding | Evidence | Missing definition |
|---|---|---|---|
| A-A01 | Base mode and service mode have different contract granularity and kernel rules. | P2.1 vs P11.1/P11.4; P3.5 vs P12 | Mode selection and precedence. |
| A-A02 | "Service contains one primary module and its layers" does not say which unit owns a contract. | `02` §2.12; `11` §11.1 | Module/service relationship. |
| A-A03 | "Consumer-shaped" is a question, not a decidable property. | P4.2 | Review evidence and decision criteria. |
| A-A04 | "Every rule required by the level" includes warnings, but warnings are not blocking. | P8.1; `08` §8.1 | Executed vs reported vs blocking. |
| A-A05 | Full-stack scope excludes front-end frameworks but P13.1 requires UI/API workflow equality. | `00` §0.3; P13.1; ST-11 | UI model and evidence. |
| A-A06 | The service profile claims language neutrality but its runner is .NET-shaped. | `11`; `conformance/topology.py` | Definition of "project" outside .NET. |
| A-A07 | The finding schema is normative but omits the fingerprint required for waivers. | `07` §7.2; P9.1 | Whether fingerprint is a required field or a tool extension. |

### UNSUPPORTED

| ID | Finding | Evidence | Consequence |
|---|---|---|---|
| A-U01 | Multi-tenant SaaS isolation is not represented. | No tenancy term in chapters 0–12; applicability matrix | A modular but tenant-leaking system can pass all rules. |
| A-U02 | Full-stack UI semantics are not represented. | `00` §0.3; ST-11 token check | The profile cannot prove UI/API workflow equivalence. |
| A-U03 | P7.6 independent release has no automated or defined manual evidence. | P7.6; no rule | An L3 claim can include an unverified release property. |
| A-U04 | P9.5 is unenforceable. | P9.5; waiver schema | The requirement is normative text only. |
| A-U05 | Runtime persistence isolation is not proven by A001. | A001 detection; §4.5 recommendation | L3 autonomy is a static claim, not runtime proof. |

### NOT TESTED

| ID | Finding | Reason |
|---|---|---|
| A-N01 | Real application adoption (greenfield or brownfield) | No production repository was adopted; benchmark is library-heavy and author-adjudicated. |
| A-N02 | Multi-team interpretation consistency | No independent teams or reviewers. |
| A-N03 | Evolution over multiple contract versions in a real product | No longitudinal evidence. |
| A-N04 | Service extraction cost/benefit | No extraction performed. |
| A-N05 | AI-agent adoption effectiveness | No independent agent pilot; the skill was only reviewed and exercised through fixtures. |
| A-N06 | Operational autonomy (deploy, scale, recover independently) | Static rules cannot establish it; no runtime portfolio. |

## 4. Principle-by-principle disposition

| Principle | Disposition | Basis |
|---|---|---|
| P1 Service Ownership | PARTIALLY VALIDATED | Strong ownership model; A002 unexecuted; runtime data isolation unproven. |
| P2 Contract Isolation | PARTIALLY VALIDATED | Strong base model; profile granularity conflict. |
| P3 Zero-Dependency Contracts | PARTIALLY VALIDATED | Clear mechanism; kernel/profile ambiguity. |
| P4 Dependency Inversion | PARTIALLY VALIDATED | Strong port distinction; P4.2/4.3 human-only. |
| P5 Strict Dependency Boundaries | PARTIALLY VALIDATED | Executable matrix; no application evidence. |
| P6 Immutable by Default | PARTIALLY VALIDATED | Six of seven rules execute; C003/C007 missing. |
| P7 Independent Evolution | PARTIALLY VALIDATED | A001/A003 execute; A002/A004/G004/P7.6 do not. |
| P8 Executable Governance | CONTRADICTORY | The non-execution contradiction; see A-C01/C03. |
| P9 Explicit Exceptions | CONTRADICTORY | Fingerprint and P9.5 conflicts. |
| P10 Service-Aligned Topology | PARTIALLY VALIDATED | Coherent naming; .NET-only runner. |
| P11 Layer Contract Independence | PARTIALLY VALIDATED | Coherent model; no cross-language proof. |
| P12 Absolute Contract Isolation | PARTIALLY VALIDATED | Clear default; mode not selected. |
| P13 Product-Oriented Services | NOT TESTED / AMBIGUOUS | UI/API equivalence and product-boundary choice lack evidence. |

A principle is not validated merely because a rule exists. The dispositions above separate
specification coherence from enforcement and empirical evidence.

## 5. Claimed benefits and mechanisms

| Claim | Mechanism in ACIMA | Evidence status |
|---|---|---|
| Reduce accidental coupling | Contracts are the only public surface; implementation types are unreachable; D001/D002/D008/D009. | Mechanism is coherent; no controlled application comparison. |
| Establish meaningful ownership | Module owns domain, implementation, dependencies, abstractions, data, configuration; P1/P7. | Coherent; ownership is asserted by config, not proven by org evidence. |
| Improve modularity | One contracts unit per module; acyclic graph; consumer-owned ports. | Coherent; benchmark shows library-profile noise, not application modularity. |
| Support independent development | Contracts versioning; no implementation references; composition root. | Partially plausible; A004/G004 unexecuted; no team study. |
| Control change propagation | Zero-dependency contracts; immutable messages; contract versions; API baseline. | Mechanism strong; baseline rule unexecuted; no version-history evidence. |
| Limit unintended dependencies | Dependency matrix + D rules + transitive closure. | Evidence at fixture level; benchmark found 28 defects/62 unclassified, but author-adjudicated. |
| Preserve integrity as complexity grows | Executable governance + CI gate + waivers. | Contradicted at the claim boundary by six unexecuted rules. |
| Support parallel teams | Module ownership + contracts + service profile. | Not tested with multiple teams. |
| Foundation for AI-assisted development | Explicit rules, stable finding format, skill workflow. | No independent agent pilot; skill guidance has stale contradictions. |

No quantitative business benefit is claimed or inferred. The 45.2% benchmark "actionable
yield" is an author-adjudicated benchmark-local measure, not a productivity or quality
outcome.

## 6. Architecture scorecard

Rubric (0–4) applies to each dimension independently:

- **0 — Absent:** no meaningful definition or evidence.
- **1 — Asserted:** stated, but not specified or testable.
- **2 — Specified:** normative text and a coherent mechanism; no independent validation.
- **3 — Internally validated:** normative text, executable checks/fixtures, and a
  contradiction-free mapping.
- **4 — Independently validated:** 3 plus independent review and real-world evidence.

| Dimension | Score | Rationale |
|---|---:|---|
| Conceptual coherence | 3 | The core model is clear and distinctive; the two-mode tension is now resolved by an explicit selector. |
| Internal consistency | 1 | Two contradictory findings remain (six-rule claim, P9.5); mode precedence and waiver identity were corrected after the audit. |
| Precision of principles | 2 | Obligations are numbered and mostly precise; P4.2, P9.5, P13.1 are not decidable. |
| Clarity of constraints | 3 | Dependency matrix and rule catalog are unusually clear. |
| Applicability across architectures | 2 | Strong for modular monolith/hexagonal; unsupported for multi-tenant/full-stack/platform. |
| Flexibility without losing intent | 2 | Kernel/library/service profiles add flexibility; mode precedence is explicit and tested, but profile coverage remains narrow. |
| Evolution and governance | 2 | Versioning and waiver model are well designed; fingerprint/P9.5/API baseline gaps. |
| Ability to address claimed problems | 2 | Mechanisms are plausible and partly evidenced; no application-scale or independent evidence. |

**Domain disposition: PARTIAL.** Do not average these into a single architecture score.
The low consistency score is not offset by the strong conceptual score.

## 7. Strengths worth preserving

1. The contracts-as-build-boundary idea is stronger than documentation-only modularity.
2. Consumer-owned ports and provided ports are a useful, non-obvious distinction.
3. The dependency matrix is small enough to memorize and precise enough to test.
4. The profile model (library/service) is the right way to handle legitimate variation.
5. The refusal to compute a health score and the insistence on execution evidence are
   correct product instincts.
6. The waiver fingerprint concept is the right mechanism; it needs consistent definition.

## 8. Material limitations of this review

- **Internal only.** No independent architect reviewed the model.
- **No application pilot.** The benchmark is 15 repositories, mostly libraries/frameworks;
  no product team adopted ACIMA.
- **Author-adjudicated benchmark.** The 45.2% yield and 5.3/10 scores are not independent
  ground truth.
- **Analyzer evidence is not architecture evidence.** Passing fixtures do not prove the
  principle is sound; they prove the implementation matches a chosen interpretation.
- **Java unobserved.** No Java enforcer; three benchmark repositories are blocked.
- **No longitudinal evidence.** No multi-version contract evolution or team study.
- **No runtime evidence.** Static analysis cannot prove autonomy, isolation, or operational
  independence.

## 9. Required next steps

1. Accept or reject AD-01/AD-02/AD-11 before making any conformance claim.
2. Fix the waiver schema contradiction (AD-05) and remove or implement P9.5 (AD-06).
3. Select one real application for a bounded pilot; do not use another library benchmark as
   a substitute.
4. Obtain at least one independent architecture review; record disagreements.
5. Re-run this report after the decisions; do not mark it validated because documents were
   edited.

## 10. Status summary

| Area | Status |
|---|---|
| Core ownership/contract model | PARTIALLY VALIDATED |
| Dependency model | VALIDATED (internal, conceptual) |
| Contract design | PARTIALLY VALIDATED |
| Runtime model | PARTIALLY VALIDATED / mostly prose |
| Base/service profile coherence | AMBIGUOUS |
| Conformance claim integrity | CONTRADICTORY |
| Applicability breadth | PARTIAL |
| Empirical effectiveness | NOT TESTED |
| Independent review | BLOCKED |
| Overall architecture release gate | **FAIL / NOT READY** |
