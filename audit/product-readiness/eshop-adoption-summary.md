# ACIMA Repository Assessment

**Repository:** eShop
**Assessment date:** 2026-11-09
**Architecture:** microservices — one deployable per service, Aspire as the composition and deployment root, per-service data stores (Catalog and Ordering on PostgreSQL, Basket on Redis, Identity on PostgreSQL), integration events over RabbitMQ. What ACIMA adds: the boundaries the Aspire model declares are now checked as code — a service may consume another capability only through a contracts unit, never by referencing another service's implementation project, and the shared libraries stop being everyone's implicit kernel.
**Assessment status:** **Baseline established** — The measured findings are recorded against a frozen baseline and the gate reports no new findings. A passing baseline is not architectural conformance.

**How to read this:** a *module* is a declared unit in `acima.config.json`; a *contract* is the interface other modules are allowed to use; the *baseline* is the frozen snapshot of existing findings; a *waiver* is an owned, expiring exception. Rule ids are for traceability, not for decoding the sentence.

## 1. Overall result

122 findings in the current run, none new, 122 produced by the detector rather than by the code.

The frozen baseline contains **220** fingerprints measured over 498 source files. 98 findings carry owned waivers. This run contains **122** findings, of which 122 are detector artefacts.

This is a summary of evidence, not a score. A clean gate means no new findings at the declared level; it does not mean the architecture is good.

## 2. What this means

eshop contains 499 source files organised into 19 declared modules. The declared level is **L1**, and the architecture recorded for it is **microservices — one deployable per service, Aspire as the composition and deployment root, per-service data stores (Catalog and Ordering on PostgreSQL, Basket on Redis, Identity on PostgreSQL), integration events over RabbitMQ. What ACIMA adds: the boundaries the Aspire model declares are now checked as code — a service may consume another capability only through a contracts unit, never by referencing another service's implementation project, and the shared libraries stop being everyone's implicit kernel**.
The most consequential issue is **Shared kernel violation** — 3 occurrences across 1 module. Modules can reach across a boundary that was meant to contain them, so an internal change can break a consumer that never agreed to depend on it.
The gate reports 0 new findings, but 2 required rules did not execute. The repository is therefore not verified at **L1**, whatever the finding count says; a passing baseline only shows that no new findings appeared among the rules that did run.

## 3. Key findings

| Finding | Impact | Affected areas | Recommended action |
|---|---|---|---|
| Shared kernel violation (`ACIMA-D007`, 3 occurrences, baseline, waived) | Modules can reach across a boundary that was meant to contain them, so an internal change can break a consumer that never agreed to depend on it. | 1 module: messaging.contracts | Move the type to the owning module or to the contract project that needs it, and keep only dependency-free values in the kernel. |
| Implementation references another implementation (`ACIMA-D001`, 22 occurrences, baseline, waived) | Modules can reach across a boundary that was meant to contain them, so an internal change can break a consumer that never agreed to depend on it. | 10 modules: basket, catalog, hybridapp, identity +6 more | Import the provider's contracts port; if it lacks the operation you need, request an additive contract change from its owner instead of referencing the implementation. |
| Implementation type published outside the module (`ACIMA-L003`, 73 occurrences, baseline, waived) | A layer boundary inside a module is crossed, so persistence or framework detail can surface where only the module's own rules belong. | 10 modules: clientapp, hybridapp, identity, ordering +6 more | Make the type internal, unexported or package-private, and move anything that genuinely crosses the boundary into the contracts unit. |
| Access to another module's internals (`ACIMA-D009`, 48 occurrences, detector artifact) | The detector matched this pattern, but the match does not describe a defect in the code. Treat it as a tooling problem, not architecture debt. | 13 modules: basket, catalog, clientapp, hybridapp +9 more | Report the detector problem to the ACIMA maintainers with a minimal fixture; do not rename or restructure working code to satisfy the match. |
| Domain references infrastructure (`ACIMA-L001`, 74 occurrences, detector artifact) | The detector matched this pattern, but the match does not describe a defect in the code. Treat it as a tooling problem, not architecture debt. | 5 modules: catalog, identity, ordering, orderprocessor +1 more | Report the detector problem to the ACIMA maintainers with a minimal fixture; do not rename or restructure working code to satisfy the match. |

Rule identifiers are in parentheses for traceability; the grouping and every affected path are in §7 and the technical report.

## 4. What should happen next?

**Shared kernel violation.** Move the type to the owning module or to the contract project that needs it, and keep only dependency-free values in the kernel.

- **Why:** Modules can reach across a boundary that was meant to contain them, so an internal change can break a consumer that never agreed to depend on it.
- **Where:** messaging.contracts
- **Done when:** `ACIMA-D007` no longer appears in the enforcer report.
- **Verified by:** Run the enforcer again and confirm this rule is gone and the gate reports no new findings.
- **Needs human judgement:** no

Then, in order:

2. **Implementation references another implementation** — Import the provider's contracts port; if it lacks the operation you need, request an additive contract change from its owner instead of referencing the implementation.
3. **Implementation type published outside the module** — Make the type internal, unexported or package-private, and move anything that genuinely crosses the boundary into the contracts unit.
4. **Correct 122 detector artefact(s), not the code** — File the detector defect upstream with a minimal reproduction; leave the working code as it is.
5. **Complete the evidence the level requires** — Record native or human evidence for the rules this environment cannot execute, or run them where the toolchain exists.

## 5. What has already been completed?

- Repository structure inspected — 499 source files were in scope for this run.
- Architecture units identified — 19 units are declared in `acima.config.json`.
- Existing findings measured — 220 at adoption; this run contains 122.
- Baseline established — 220 fingerprints were frozen on 2026-11-09.
- Exceptions recorded — 98 waivers, owned.
- Enforcement configuration exists — `acima.yml` (a configured gate is not an observed gate).
- Finding triage recorded — 2 decisions separate defects from detector and review items.

## 6. What has not been verified?

- 6 rules did not run: `ACIMA-A002` (Cross-module configuration key), `ACIMA-A004` (Version-lock coupling), `ACIMA-C003` (Behaviour in contracts), `ACIMA-C007` (Contract cannot be constructed in one step), `ACIMA-G004` (Unreviewed contract change), `ACIMA-L004` (Module resolved through a service locator). A rule that did not run is not a rule that passed.
- At the declared level, `ACIMA-G004` (Unreviewed contract change), `ACIMA-L004` (Module resolved through a service locator) still need executed evidence or a recorded manual review. Without them the assessment cannot be full.
- 98 waivers are in force; the earliest expiry is 2027-02-07. Renewal is an individual decision, never a bulk action.
- The CI gate has not been observed running in this summary; a workflow file proves configuration, not enforcement.
- No full-conformance claim was supplied, so this summary does not assert conformance at any level.
- 122 findings are detector artefacts, not architectural defects. They remain in the gate so the detector problem stays visible; they are not evidence that the code is wrong.
- The current run has 122 findings; the baseline records 220. A passing gate means no new findings, not the same set of findings.
- Source scope changed: the baseline was measured over 498 files, this run over 499. Compare counts only after reconciling scope.
- The first measurement reported **221** findings; the frozen baseline contains **220** fingerprints.
- The difference is 1 finding(s) present in the first run and not in the frozen baseline: `ACIMA-G001` ×1 (Undocumented exception). The baseline is the frozen measurement; the first run is the before photograph.

## 7. Supporting technical details

- Full run: `../eShop/docs/acima/gate-L1-latest.json` — every finding with rule, path, line, fingerprint and new/pre-existing status.
- First measurement: `../eShop/docs/acima/gate-L1-baseline.json` — the before photograph used to reconcile the baseline count.
- Frozen baseline: `../eShop/.acima/baseline.json`.
- Waivers: `../eShop/.acima/waivers.json` — ownership, reason, expiry.
- Triage: `audit/product-readiness/eshop-triage.json` — which matches are defects, detector artefacts, or awaiting review.
- Adoption plan: `../eShop/docs/acima/adoption-plan.md`.
- Status dashboard: `../eShop/docs/acima/STATUS.md`.

Rule meanings and remedies: `../tools/acima-spec/rules.json` and the rule pages in the standard repository.

