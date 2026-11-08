# Simplification assessment and plan

> Follow-up applied after this plan: `benchmark-evidence/` was split into in-tree headline results plus archived raw artifacts — see `IMPLEMENTATION-LOG.md` §8.

Method: every significant component was read, its consumers found with a repository-wide search, and its relationship to R1–R5 (`audit/CORE-ARCHITECTURE.md`) judged. Classification uses the mission's five categories.

## 1. Component classification

| Component | Purpose | Consumers | Class | Disposition |
|---|---|---|---|---|
| `tools/acima-spec/rules.json` | 29-rule catalog, finding schema, claim model | every enforcer, `acima.py`, `coverage.json`, skill preflight (hash) | **CORE** | keep; unchanged |
| `docs/standard/00`–`10` | normative specification | humans, reviewers, tool authors | **CORE** | keep |
| `docs/rules/*` | human rule catalog with examples | developers, reviewers | **SUPPORTING** | keep; add sync test |
| `docs/standard/11` service topology, `conformance/topology.py` | optional profile for multi-service products | `.NET` fixture, `run.py topology` | **OPTIONAL** | keep, keep visibly optional |
| `docs/standard/12` library profile | published-artifact classification | TypeScript/.NET enforcers | **OPTIONAL** | keep |
| `examples/<lang>` implementations + enforcers | the only executable proof a rule can fire | `run.py`, `acima.py`, adoption skill | **CORE** (reference) | keep |
| `conformance/run.py`, `coverage.json`, `test_*.py` | verify enforcers against the catalog | CI, contributors | **CORE** | keep; add link test |
| `conformance/acima_claim.py`, `.acima/manual-evidence.json` | stop "full conformance" claims without evidence | `acima.py claim`, skill | **SUPPORTING** | keep |
| `skills/acima-adoption/SKILL.md` + references + scripts | adoption capability | developers, coding agents | **CORE** (product) | keep; fix pin; add README |
| `skills/acima-adoption/references/30,40,50` | onboarding, communication, metrics | skill workflow steps 2 and 6 | **OPTIONAL** | keep; labelled optional in plan |
| `tools/acima.py` | developer CLI (`inspect/analyze/report/claim/verify`) | status docs, CI, skill | **SUPPORTING** | keep |
| `tools/acima_walkthrough.py` | executable D001 walkthrough | `test_walkthrough` | **SUPPORTING** | keep |
| `validation/` (20 files, 3,633 lines) | dated release-readiness reports, traceability matrices, backlog | **nothing outside itself** (verified) | **REDUNDANT** | **remove** |
| `docs/audit/continuous-improvement-ledger.md` | dated remediation log | nothing (verified) | **REDUNDANT** | **remove**; superseded by `audit/` |
| `docs/index.md` | second documentation index | internal links only | **REDUNDANT** | **remove**; superseded by `docs/README.md` |
| `benchmark-evidence/` (459 files, 17k lines) | immutable evidence for portfolio claims | `docs/product-contract.md`, `docs/status.md` | **OPTIONAL** | keep (evidence), document; flag as largest remaining weight |
| `.github/workflows/*` | CI equivalent | none automatically | **SUPPORTING** | keep; unobserved |
| `.freebuff/` | tool metadata | agent host | out of scope | untouched |

### Why `validation/` is redundant, not merely stale

Each file restates something that already has an authoritative home:

- `ARCHITECTURE-ENFORCEMENT-MATRIX.md`, `RULE-TRACEABILITY.md`, `CROSS-DOMAIN-TRACEABILITY.md`, `LANGUAGE-SUPPORT-MATRIX.md` restate `rules.json` + `coverage.json` + `docs/languages/index.md`.
- `ARCHITECTURE-CONSISTENCY-REPORT.md`, `ENFORCEMENT-CONFORMANCE-REPORT.md`, `PRODUCT-READINESS-REPORT.md`, `RELEASE-READINESS.md`, `SKILL-*-REPORT.md`, `ARCHITECTURE-VALIDATION-REPORT.md` restate `docs/status.md` and `docs/product-contract.md` as of a date.
- `ARCHITECTURE-MODEL.md`, `ARCHITECTURE-GLOSSARY.md`, `ARCHITECTURE-DECISIONS.md`, `ARCHITECTURE-APPLICABILITY-MATRIX.md` restate chapters 0–2 and 8.
- `MASTER-BACKLOG.md` is the only file with unique content (open work items).

Two competing copies of the rule mapping are exactly the failure mode the mission targets: they drift, and a reader cannot tell which is current. No code, test, workflow or document outside `validation/` links to it.

## 2. Planned changes

| # | Change | Why | Dependents | Risk |
|---|---|---|---|---|
| S1 | Re-pin the skill: `manifest.json` sha256 → current catalog, `skillVersion` 1.2.5, `SKILL.md` metadata | unblocks `SKL-002`; restores 3 tests | preflight, 3 tests | low; hashes are derived |
| S2 | Stop hardcoding the skill version in tests; read it from the manifest | single source of truth | `test_documentation_contract` | low |
| S3 | Remove `validation/` (20 files) | removes a parallel rule catalog | none | **high visibility, low technical risk** (git history retains it) |
| S4 | Remove `docs/audit/continuous-improvement-ledger.md` | superseded by `audit/` | none | low |
| S5 | Replace `docs/index.md` with `docs/README.md` | one documentation index | none | low |
| S6 | Add directory READMEs: `docs/`, `docs/rules/`, `skills/`, `skills/acima-adoption/`, `examples/`, `conformance/`, `tools/`, `benchmark-evidence/` | navigation and ownership | root README links | none |
| S7 | Correct root README links (`docs/` → `docs/README.md`, `principles and rules` → `docs/rules/`, `examples/` → `examples/README.md`, `conformance/` → `conformance/README.md`, `language profiles` → `docs/languages/index.md`) | two links pointed at the same directory; none reached the rule catalog | readers | none (link-only) |
| S8 | Add `conformance/test_documentation_integrity.py`: internal links resolve + `docs/rules/index.md` matches `rules.json` | converts a manual sync risk into a deterministic check; prevents the link class of bug | `run.py tools` | low |
| S9 | Wire the new test into `conformance/run.py` | makes it part of the gate | CI | low |

Deliberately **not** done, with reasons:

- **Merging principles.** P1–P9 each map to a distinct requirement; immutability (P6) is separately checkable and §3 of the core model explains why folding it into R2 would weaken enforcement. Fewer principles would mean less precision, not less complexity.
- **Moving P10–P13 out of chapter 1.** Chapter 1 already states that they are profile obligations checked as `S001`–`S012`; moving 160 lines would create a large, low-value diff.
- **Rewriting `tools/acima.py` to derive its category labels and manual-rule set from `rules.json`.** The duplication is guarded by `test_documentation_contract` (which pins the six manual ids) and rewriting it adds risk without reducing what a reader must hold in mind. Recorded as an accepted, guarded duplication.
- **Deleting or rewriting `benchmark-evidence/`.** It is cited evidence and its `SHA256SUMS` covers the logs; deleting part of it would invalidate the rest. Documented instead.
- **Cutting the skill's communication/outcomes references.** They support workflow step 6 and are adoption IP, not architecture duplication.
- **Consolidating `docs/guides/`.** Each guide answers a different audience question (leaders, reviewers, agents, before/after, tests, analyzers, walkthrough); merging would produce one long document with no owner.

## 3. Expected benefits

- One rule catalog, one documentation index, one change log: a reader cannot land on a stale copy.
- ~3,900 lines of dated report prose removed from the reading path, without losing a capability.
- Every major directory answers "what is this, what belongs here, where next" in under 100 lines.
- Two new deterministic checks (links, catalog/docs sync) replace manual vigilance.
- The adoption preflight works again on the current commit.

## 4. Risks

- Removing `validation/` loses the dated release narrative. Mitigation: it remains in git history; `audit/` records this decision, and open backlog items are captured in `audit/FINAL-REVIEW.md`.
- New link check may surface pre-existing broken links. Mitigation: fix them as part of S8; the test is the evidence.
- Skill version bump touches the manifest hash pin; if the catalog changes again the preflight blocks, which is the intended behaviour.
