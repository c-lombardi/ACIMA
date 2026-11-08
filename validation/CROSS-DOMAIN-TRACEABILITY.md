# Cross-Domain Traceability

**Status:** IN PROGRESS — internal review only
**Required chain:**
Architecture principle → normative requirement → enforcement mapping → language
implementation → regression test → skill interpretation → real-world adoption evidence.

A link is **complete** only when every element exists and is consistent. A missing automated
rule is not automatically a defect; a missing manual evidence path is.

## Master chain

| Principle | Normative requirement | Enforcement | Languages | Regression evidence | Skill interpretation | Adoption evidence | Status |
|---|---|---|---|---|---|---|---|
| P1 Service Ownership | P1.1–P1.6: no implementation dependency, no internal access, own data/config/static state, infrastructure abstractions local | D001, D008, D009, L003, A001, A002, A003 | 4 (A002 missing) | galleries; injection L001/D001 | Base ownership and no-shared-kernel guidance | No application pilot | **PARTIAL** |
| P2 Contract Isolation | P2.1–P2.5: one contracts surface, only contract kinds, no leaks, docs | D002, D006, D009, L002, C005, L003, G003 | 4 | galleries; library profile | Strong in base; service granularity missing | No application pilot | **PARTIAL** |
| P3 Zero-Dependency Contracts | P3.1–P3.5: no third-party, no contracts→contracts, no implementation, no framework, legacy kernel only | D003, D004, D008, L002, C005, D007 | 4 | galleries | Default no-kernel is taught | Libraries: 150 classified, 30 unclassified | **PARTIAL** |
| P4 Dependency Inversion | P4.1–P4.5: explicit deps, no consumer-shaped contract, consumer-owned ports, infra abstractions local, composition root | D002, L003, L004, G003, C007, D006 | 4 (L004/C007 missing) | galleries; no L004 fixture | Explained; no review procedure for P4.2/4.3 | No application pilot | **PARTIAL** |
| P5 Strict Dependency Boundaries | P5.1–P5.5: contracts-only, acyclic, no transitive leak, inward layering, no host | D001, D005, D008, L001, D006 | 4 | galleries; injection L001/D001 | Strong | Benchmark 28 defects/62 unclassified; author-adjudicated | **PARTIAL** |
| P6 Immutable by Default | P6.1–P6.7: no mutation, no mutable collections, no behaviour, no ambient state, no persistence, explicit types, one-step construction | C001–C007 | 4 (C003/C007 missing) | galleries | Taught; C003/C007 not tracked | No application pilot | **PARTIAL** |
| P7 Independent Evolution | P7.1–P7.6: own data/config, no static state, contracts versions, API baseline, independent release | A001–A004, G004 | 4 (A002/A004/G004 missing) | galleries; no release test | Taught; no manual evidence | No application pilot | **PARTIAL** |
| P8 Executable Governance | P8.1–P8.5: level rules execute, finding format, no disable, classify all, version-control artifacts | G001–G005 + harness | 4 (partial) | runner; CLI; injection | Strong safety rules; overclaims conformance | 12/12 supported benchmark; no hosted CI | **CONTRADICTORY** |
| P9 Explicit Exceptions | P9.1–P9.5: exact fingerprint, expiry, narrow, review, immutability limit | G001, G002 | 4 | waiver tests | Requires fingerprint; docs stale; P9.5 absent | No production waiver | **PARTIAL** |
| P10 Service-Aligned Topology | P10.1–P10.4: directory, naming, one responsibility, deployable independently | S001–S003, S007, S012 | S (.NET-shaped) | `test_topology` | Explicit `NOT SUPPORTED` stop | No service pilot | **PARTIAL/BLOCKED** |
| P11 Layer Contract Independence | P11.1–P11.5: per-layer contracts, no sharing, transform, no domain contracts, pure transform | S004–S006, S009; P2.1 superseded | S (.NET-shaped) | `test_topology` | Explicit `NOT SUPPORTED` stop | No service pilot | **PARTIAL/BLOCKED** |
| P12 Absolute Contract Isolation | P12.1–P12.5: zero refs, no kernel, no framework attrs, validation only, compile alone | S005 | S (partial) | `test_topology` | **No skill path** | No service pilot | **PARTIAL/BLOCKED** |
| P13 Product-Oriented Services | P13.1–P13.4: UI/API workflow, domain rules, deployment/vendor edge, product boundary | S002, S008–S012 | S (token checks) | `test_topology` | **No skill path** | No full-stack pilot | **NOT TESTED/AMBIGUOUS** |

## Rule-level chain

The complete 29-rule table is in `RULE-TRACEABILITY.md`. The important chain breaks are:

| Break | Architecture requirement | Enforcement | Skill | Adoption consequence |
|---|---|---|---|---|
| B-01 | P8.1 requires every level rule to execute | Six rules `executed:false` | Skill says zero unwaived errors = conformant | False full-conformance claim |
| B-02 | P9.1 requires exact fingerprint | §7.5 now requires rule+scope+fingerprint; §7.2 finding schema omits it | Skill and references corrected | §7.2 profile/format gap remains |
| B-03 | P2.1 one contracts unit | `mode` selects base vs service; P2.1 superseded in service mode | Skill reads mode and stops for service | Layer contracts are no longer judged as base modules |
| B-04 | P11/P12 per-layer, absolute isolation | S rules only .NET fixture; mode gate now rejects mismatches | Explicit `NOT SUPPORTED` stop; no workflow | Profile cannot yet be adopted by the skill |
| B-05 | P4.1 no service locator | L004 not executed | Skill doesn't mention | Runtime coupling invisible |
| B-06 | P4.2/P4.3 consumer-owned adaptation | No rule / C007 missing | Conceptual explanation only | Provider contracts can be consumer-shaped |
| B-07 | P6.3/C003 no behaviour in contracts | Not executed | Skill says contracts data-only, but cannot measure | Business logic passes |
| B-08 | P6.7/C007 one-step construction | Not executed | No manual evidence | Half-valid contracts pass |
| B-09 | P7.2/A002 config ownership | Not executed | No manual evidence | Cross-module secrets/config pass |
| B-10 | P7.4/A004 version coupling | Not executed | No manual evidence | Implementation version pinning passes |
| B-11 | P7.5/G004 API baseline | Not executed | No baseline artifact | Breaking changes pass |
| B-12 | P7.6 release independence | No rule | No manual evidence | L3 claim includes unproven release |
| B-13 | P9.5 waiver version limit | No rule/field | No guidance | Waiver can outlive limit |
| B-14 | P1.3/P7.1 runtime data ownership | A001 static only | Skill cites A001; no grant evidence | Shared runtime DB passes |
| B-15 | P12.5 compile alone | S005 zero refs only | No service path | Project may still not compile alone |
| B-16 | P13.1 UI/API equality | S011 token presence | No service path | Different workflows pass |
| B-17 | Library public API | TS/.NET only | One hard rule | Python/Go valid API flagged |

## Language chain

| Language | Architecture coverage | Enforcement | Skill | Adoption evidence |
|---|---|---|---|---|
| Python | Base P1–P9 | 23 automated, 6 manual; no library profile | Base workflow | Benchmark libraries; no app pilot |
| TypeScript | Base P1–P9 | 23 automated, 6 manual; library profile | Base workflow; profile only as warning | Benchmark libraries; no app pilot |
| Go | Base P1–P9 | 23 automated, 6 manual; no library profile | Base workflow | Benchmark libraries; no app pilot |
| .NET | Base P1–P9; service profile | 23 automated, 6 manual; library profile; ST fixture | Base workflow; no service path | Benchmark libraries; no app pilot |
| Java | Base documented only | 0 automated | Stop; don't fake | 3 benchmark repos blocked |

## Skill chain

| Principle | Skill behavior | Validation | Status |
|---|---|---|---|
| P1/P2/P3/P5 | Explain ownership, contracts, no-kernel, dependency directions; run preflight/enforcer | Base text/tests | PARTIAL |
| P4 | Explain provided/consumer-owned ports; no review procedure | Text only | PARTIAL |
| P6 | Explain immutable contracts; no C003/C007 evidence | Text only | PARTIAL |
| P7 | Explain own data/config, API evolution; no manual evidence | Text only | PARTIAL |
| P8 | Require run, zero source check, injection proof; define partial assessment | Tests exist | PARTIAL |
| P9 | Require exact waiver; references corrected; no P9.5 | Tests exist | PARTIAL |
| P10–P13 | Explicit `NOT SUPPORTED` stop; no workflow | Mode tests | NOT SUPPORTED |

## Adoption evidence chain

| Evidence | Supports | Does not support |
|---|---|---|
| `rw-2026-11-08-02` | Enforcement precision/reliability on 12 libraries | Architecture validity, application adoption, productivity |
| Gallery fixtures | Rule detection on controlled examples | General semantic completeness |
| Injection proofs | L001/D001 detection; zero-finding not vacuous | Other 21 rules |
| Library profile tests | TS/.NET public API/adapter classification | Python/Go/Java, service profile |
| Topology tests | 12 ST checks on .NET-shaped fixture | Language-neutral service adoption |
| Preflight tests | Fail-closed assessment, exact waivers, zero-unit blocker, 18-module completeness | Real repository mapping or implementation |
| No pilot | — | All C7 adoption measurements |

## Broken or incomplete traceability to fix

1. **Architecture → claim:** define full vs partial (AD-01/AD-11).
2. **Architecture → mode:** add mode field/precedence (AD-02/AD-03).
3. **Waiver identity:** §7.5 and preflight now require the fingerprint; add it to the §7.2 finding schema (AD-05).
4. **P9.5:** implement metadata or downgrade (AD-06).
5. **Manual rules:** define evidence and claim status for six rules.
6. **Runtime data:** require grant evidence at L3 or relabel L3.
7. **Skill:** add service/library workflows or explicit stops (AD-10).
8. **Adoption:** run one real application pilot with independent verification.

Every item is assigned in `MASTER-BACKLOG.md`; none is resolved by editing this matrix.

## 2026-11-08 implementation update

- **B-01 / P8:** resolved by the executable claim gate. `FULL CONFORMANCE` requires
  every required rule to execute or have accepted repository-scoped manual evidence;
  otherwise the result is `PARTIAL ASSESSMENT`. The six rules remain normative and are
  marked `automation: manual`, not silently removed.
- **B-02 / P9:** resolved in the normative schema. `fingerprint` is now required in
  §7.2, `rules.json` and G001; §7.5 already required it.
- **B-13 / P9.5:** resolved by making P9.5 explicitly advisory in Draft 1. No document
  claims it is machine-enforced.
- **B-03/B-04:** unchanged; service mode remains explicitly unsupported by the skill.
- **Adoption evidence:** the benchmark rerun is mechanical, not a pilot; no application
  adoption or independent review exists.
