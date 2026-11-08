# Rule Traceability

**Status:** IN PROGRESS — internal review only
**Source of truth:** `tools/acima-spec/rules.json` (29 rules) and `docs/rules/*`
**Coverage source:** `conformance/coverage.json`
**Evidence:** four galleries (`examples/*/violations/expected.json`), `conformance/run.py`,
targeted tests named below.

## How to read

- **Automated** means the reference enforcer executes the rule and the gallery contains a
  fixture that fires it. It does **not** mean every semantic form is detected.
- **Not executed** means the rule is in the catalog but the enforcer reports
  `"executed": false` with a reason. It is a normative requirement, not a pass.
- **Manual** means no automated rule currently exists; the obligation needs review,
  native analysis, or release evidence.
- **Java** has no reference enforcer. All Java cells are `NONE`, regardless of the
  profile's prose.

## Base catalog

| Rule | Principle | Level / severity | Normative requirement | Auto status | Languages | Regression evidence | Human judgment |
|---|---|---|---|---|---|---|---|
| D001 | P5, P1 | L1 / error | Implementation must not reference/import/link another implementation | Automated | P/T/G/N | gallery; `test_injected_violation`; `test_exclusions` | No for static direct edge |
| D002 | P3, P4 | L1 / error | Contracts must not reference any implementation, including own | Automated | P/T/G/N | gallery | No |
| D003 | P3, P7 | L1 / error | Contracts must not reference another contracts unit | Automated | P/T/G/N | gallery | No |
| D004 | P3 | L1 / error | Contracts only language core; no third-party packages/framework types | Automated | P/T/G/N | gallery | Some language/package classification |
| D005 | P5 | L1 / error | Module graph must be acyclic | Automated | P/T/G/N | gallery; cycle fixtures | No |
| D006 | P2, P4, P5 | L1 / error | Contracts must not reference host/composition root | Automated | P/T/G/N | gallery | No for declared host |
| D007 | P3, P1 | L1 / error | Kernel is dependency-free, no modules/behaviour | Automated | P/T/G/N | gallery | Some kernel admission judgment |
| D008 | P5, P1 | L1 / error | No transitive implementation leak | Automated | P/T/G/N | gallery; graph closure | No for static graph |
| D009 | P1, P2, P4 | L1 / error | Non-contract types unreachable outside module | Automated | P/T/G/N | gallery; library profile tests | Yes for public API declarations |
| L001 | P5 | L1 / error | Domain/application must not depend on infrastructure/delivery | Automated | P/T/G/N | gallery; library profile `intentionalAdapters` | Yes for unlisted edges |
| L002 | P2, P3 | L1 / error | Contracts must not expose framework types | Automated | P/T/G/N | gallery | Yes for framework list |
| L003 | P1, P2, P4 | L1 / error | Only contracts types public outside module | Automated | P/T/G/N | gallery; library profile `publicApi` | Yes for intended public surface |
| L004 | P4 | L1 / warning | No service-locator/runtime peer resolution | **Not executed** | — | none; manifest lists notPortableIds | **Yes** |
| C001 | P6 | L2 / error | Contract state set at construction, never mutated | Automated | P/T/G/N | gallery | Some language-specific field semantics |
| C002 | P6 | L2 / error | No mutable collection exposure | Automated | P/T/G/N | gallery | Yes for aliasing |
| C003 | P6 | L2 / error | No business behaviour, IO, orchestration, lifecycle hooks | **Not executed** | — | none | **Yes**; semantic |
| C004 | P6 | L2 / error | No ambient/non-deterministic state (clocks, ids, caches) | Automated | P/T/G/N | gallery; denylist | Yes for unlisted APIs |
| C005 | P3, P6 | L2 / error | No persistence types/query abstractions | Automated | P/T/G/N | gallery | Yes for custom ORMs |
| C006 | P6 | L2 / error | Explicitly typed; no object/dynamic/any/bare maps | Automated | P/T/G/N | gallery | Some alias/type forms |
| C007 | P6 | L2 / warning | Constructible in one step; required state obvious | **Not executed** | — | none | **Yes** |
| A001 | P1, P7 | L3 / error | Module owns persistence; no cross-module schema read/write | Automated (static) | P/T/G/N | gallery | **Yes** for runtime grants/actual DB access |
| A002 | P1, P7 | L3 / warning | No cross-module configuration keys/secrets | **Not executed** | — | none | **Yes** |
| A003 | P1, P7 | L3 / error | No cross-module mutable static/global state | Automated | P/T/G/N | gallery | Yes for hidden globals |
| A004 | P7 | L3 / warning | Consumers depend on contracts version, never implementation version | **Not executed** | — | none | **Yes** |
| G001 | P8, P9 | L1 / error | Waiver has owner, reason, scope, fingerprint, expiry; known rule id | Automated | P/T/G/N | `test_waiver_fingerprints`; gallery | Yes for reason quality/scope |
| G002 | P9 | L1 / error | Expired waiver fails; finding returns | Automated | P/T/G/N | gallery/waiver tests | No |
| G003 | P2, P4 | L2 / warning | Public contract types documented with invariants | Automated | P/T/G/N | gallery | **Yes** to write/review docs |
| G004 | P7, P8 | L2 / error | Contract change captured in reviewed API baseline | **Not executed** | — | none | **Yes**; baseline review |
| G005 | P8, P1 | L1 / error | Every production file belongs to a declared unit | Automated | P/T/G/N | gallery; `test_rule_catalog`; `test_library_profile` | No |

**Automated count:** 23 / 29. **Not executed:** 6 / 29 (`C003`, `C007`, `L004`, `A002`,
`A004`, `G004`). **Java:** 0 / 29.

## Service-topology profile rules

These are not in the base catalog and do not change L1–L3. They are profile requirements
from chapter 11, implemented by `conformance/topology.py` as `ACIMA-S001`–`S012`.

| Profile rule | Principle | Requirement | Implementation | Evidence | Human judgment |
|---|---|---|---|---|---|
| S001 (ST-1) | P10.1 | One directory per service under `services/<Service>/` | `topology.py` | `test_topology` good/bad | Service boundary naming |
| S002 (ST-2) | P10.3 | One responsibility, one sentence in README | `topology.py` | `test_topology` | **Yes**; sentence semantics |
| S003 (ST-3) | P10.1 | Every project named `<Service>.<Layer>` and under its service | `topology.py` | `test_topology` | Layer naming |
| S004 (ST-4) | P11.1, P11.2, P11.4 | One contracts project per outward-facing layer; none for domain; no sharing | `topology.py` | `test_topology` | Layer ownership |
| S005 (ST-5) | P12.1, P12.2, P3.5 | Zero project/package/module/kernel/framework references | `topology.py` | `test_topology` | Actual compile-alone proof |
| S006 (ST-6) | P11.3, P11.5 | Explicit transform; no re-export of another layer's DTO | `topology.py` | `test_topology` | **Yes**; transform purity |
| S007 (ST-7) | P10.2, P11.3 | Inter-service contract `<Source>.<Target>`; exactly two names; only named services reference | `topology.py` | `test_topology` | Ownership/review |
| S008 (ST-8) | P13.3 | Vendor SDK isolated behind contracts and adapter | `topology.py` | `test_topology` | Vendor classification |
| S009 (ST-9) | P11.4, P13.2 | Domain owns rules; no persistence/transport/vendor code | `topology.py` (token scan) | `test_topology` | **Yes**; semantic rule ownership |
| S010 (ST-10) | P11 / chapter 11 | 100% line/branch domain coverage; named rule tests | `topology.py` | `test_topology` | Coverage quality |
| S011 (ST-11) | P13.1, P13.2 | UI/API share states, transitions, errors; API enforces core | `topology.py` (token presence) | `test_topology` | **Yes**; semantic equivalence |
| S012 (ST-12) | P10.4, P13.3 | No deployment/vendor SDK outside adapter/host; deployment-agnostic service | `topology.py` | `test_topology` | **Yes**; actual deployability |

**Profile coverage:** 12 / 12 in the .NET-shaped fixture. No non-.NET fixture. The runner
reads `.csproj`, `package.json`, `pyproject.toml`, and `go.mod` where present, but the
manifest's project/layer model and the tests are .NET-first.

## Broken or weak mappings

| Mapping issue | Requirement | Current enforcement | Consequence |
|---|---|---|---|
| No one-contracts-unit rule | P2.1 | None; `G005` only classification | A module can have zero or two contracts units and pass |
| Profile granularity not selected | P2.1 vs P11.1/P11.4 | Two config formats; no mode | Same shape can be a violation or correct |
| Service-locator rule missing | P4.1 | L004 not executed | Runtime peer resolution is not detected |
| Consumer-shaped contract rule missing | P4.2 | G003 docs; C007 not executed | Provider can be consumer-shaped and pass |
| Consumer-owned port rule missing | P4.3 | None | A consumer can demand a provider contract change undetected |
| Contract behaviour judgment missing | P6.3 | C003 not executed | Business logic/IO can live in contracts |
| One-step construction missing | P6.7 | C007 not executed | Half-valid contracts can pass |
| Config ownership missing | P1.4/P7.2 | A002 not executed | Cross-module config/secret reads undetected |
| Version coupling missing | P7.4 | A004 not executed | Consumers can pin implementation versions |
| API baseline missing | P7.5 | G004 not executed | Breaking contract changes can pass |
| Independent release missing | P7.6 | None | L3 claim includes unverified release property |
| Immutability waiver limit missing | P9.5 | None | Waiver can outlive a minor version |
| Runtime data isolation missing | P1.3/P7.1 | A001 static only | Shared DB at runtime can pass |
| Compile-alone missing | P12.5 | S005 zero refs only | A project could still fail to compile alone |
| Transform purity missing | P11.5 | S006 existence only | A business-logic transform can pass |
| UI/API semantic equality missing | P13.1 | S011 token presence | Different workflows can pass |
| Profile language portability missing | P10–P13 | .NET-shaped runner | Non-.NET services can evade or fail incorrectly |

## Rules without an architectural requirement?

None in the catalog. Every rule traces to at least one principle. The weakest direct
mapping is `G005`: it is a governance/classification rule (P8.4) rather than a
domain-architecture rule, and `G001`/`G002` are about the exception mechanism itself. That
is intentional, not a defect.

## Rules that enforce a narrower interpretation

- **L001** checks four layer edges, not a complete Clean/Hexagonal dependency model.
- **A001** checks static SQL/ORM identifiers, not runtime database grants.
- **G003** checks documentation presence, not whether the documentation is correct.
- **C004** uses a denylist; unlisted clock/random APIs escape.
- **C005** uses known persistence type names; custom ORMs can escape.
- **C006** checks listed untyped forms; aliases can escape.
- **S011** checks tokens, not workflow semantics.
- **S005** checks declared references, not actual `compile-alone`.

## Rules that enforce a broader interpretation

- **C004** can flag legitimate pure use of a time type if it appears in a contract body;
  the rule should distinguish a field/parameter from a clock read.
- **L003** can flag an intentional public library surface; the library profile exists to
  classify it, but only for TypeScript/.NET.
- **D001/D009** can flag intentional adapter edges; the library profile classifies them
  only when declared and supported.
- **D008** may report the same transitive path multiple times; the benchmark records
  duplicate D008 findings. This is a precision issue, not a broader architecture claim.

## Duplicate / overlapping rules

| Rules | Relationship | Disposition |
|---|---|---|
| D001, D008, D009 | Direct implementation edge, transitive closure, internal type access | Keep all; they catch different graph shapes, but deduplicate findings |
| D002, P4.4 | Contracts→implementation also catches a misplaced infrastructure abstraction | Keep; document the indirect mapping |
| D006, P5.5 | Contracts→host and implementation→host share a concept | Keep separate; different from-unit roles |
| D003, L002 | Contracts→contracts vs contracts→framework type | Different causes; not duplicates |
| G001, G002 | Malformed/unknown waiver vs expired waiver | Keep; different lifecycle states |
| S004, S005 | Layer ownership vs zero references | Keep; a zero-reference contract can still be the wrong layer's contract |

## 2026-11-08 update

The six rules are no longer described as an unresolved execution gap. They remain
normative and are now marked `automation: manual` in `rules.json`. A full claim requires
one accepted repository-scoped entry per required manual rule in
`.acima/manual-evidence.json`; otherwise the claim is `PARTIAL ASSESSMENT`. The portable
enforcers still execute 23 of 29 rules. Java still has no enforcer.
