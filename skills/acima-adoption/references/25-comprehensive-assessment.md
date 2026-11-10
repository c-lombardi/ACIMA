# Comprehensive architectural assessment

A read-only ACIMA assessment has two independent outputs:

1. **Deterministic conformance measurement**: what the selected language enforcer actually executed against an approved module map.
2. **Comprehensive architectural review**: qualitative inspection of all requirements in the current catalog, including requirements above the level recommended for adoption.

A missing module map blocks the first output, not the second. Continue qualitative discovery and review. Do not call an inferred map approved, and do not invent deterministic results.

## 1. Establish the complete repository scope

Inspect the entire requested repository, not just the first detected project or language. If the requested project is nested in a Git repository, discover the repository root and inspect its architecture standards, rule files, CI workflows, build orchestration and architecture documentation as repository context, while keeping production source analysis scoped to the requested project(s). Do not scan unrelated sibling source projects as if they were part of the requested project. Inventory:

- languages, source roots, project/package manifests and project references;
- logical modules, contracts, implementations, adapters and shared code;
- application entry points and composition roots;
- deployment units and independently released packages;
- frontend/backend API contracts and generated clients;
- tests, architecture tests, static analyzers, custom rule engines and dependency restrictions;
- CI workflows, build gates and architecture documentation;
- generated, vendored, fixture, test and build-output exclusions.

Project, directory, assembly, package and deployment boundaries are discovery evidence, not automatically ACIMA modules. Create a provisional ownership hypothesis where necessary, identify its evidence and confidence, and leave unresolved boundaries uncertain. Never write a config or approve inferred ownership during assessment.

For every language, identify whether a reference enforcer exists and whether its toolchain is available. Do not run only the first language and imply repository-wide coverage. Where one approved module map spans multiple languages, run each supported language enforcer with the same map only if the enforcer can correctly interpret its source scope. Otherwise state the limitation and keep each result separate.

## 2. Compare existing architecture enforcement

Inspect existing rule catalogs, architecture tests, custom analyzers, import restrictions, package/project-reference checks, CI commands and observed CI runs. Map each mechanism to ACIMA requirements using one of:

- Equivalent coverage
- Partial coverage
- Stronger local constraint
- Narrower local constraint
- Different architectural opinion
- Conflicting requirement
- No corresponding coverage

Explain what is actually enforced, where, and whether it has been observed running. A local layer rule is not automatically an ACIMA module-ownership rule. Do not recommend replacing existing checks simply because they are not ACIMA-branded. Identify redundancy and genuine gaps.

## 3. Review every catalog requirement

Read `tools/acima-spec/rules.json` and the normative chapter(s) for every requirement. The current catalog has 55 requirements: 27 L1, 10 additional L2 and 18 additional L3 (37 cumulative at L2 and 55 cumulative at L3). If the catalog changes, derive the counts from the catalog rather than hardcoding these values.

The review must trace each requirement through actual source, project metadata, contracts, tests, configuration, call chains and deployment evidence as applicable. Use the rule's summary as its normative meaning and its fix as guidance, not as proof of a violation.

Review all requirement families, including:

- Module ownership, explicit contracts, dependency direction, cycles, transitive leaks, internal visibility, shared-kernel boundaries and data ownership.
- Domain/infrastructure/delivery separation and contract independence from frameworks, vendors, persistence and composition.
- Contract mutability, collection aliasing, ambient state, typed payloads, atomic construction, business behavior and visible outcomes.
- Explicit constructor/function inputs, optional defaults, service locators, automatic registration, property/field injection, closures, currying and partial application.
- Configuration ownership, ambient configuration access, cross-module configuration keys, secrets and deployment/runtime variation.
- Meaningful primitive ownership, immutability, semantic identity, dataflow and consolidation at the highest genuine common owner. Equal values or matching names alone never establish semantic equivalence.
- Lifecycle choices, singleton/shared/transient/scoped services, captive dependencies, mutable state, concurrency, tenant isolation and resource disposal.
- Naming conventions and semantic clarity, including domain meaning, units, side effects, abbreviations and generic responsibility names.
- Effect ownership, triggers, commit boundaries, retry/idempotency/compensation, truthful outcomes, critical-effect evidence, telemetry and consistency guarantees.
- Governance, exceptions, contract versioning and review.

Also inspect physical and logical file organization. Determine whether projects, folders and packages reflect actual ownership, contracts, implementations, adapters, composition, persistence and tests. Do not prescribe a universal folder layout.

## 4. Rule status and evidence

Every catalog rule must have exactly one explicit review status:

- `satisfied`: inspected evidence supports the requirement; cite exact files/locations and reasoning.
- `confirmed_violation`: direct evidence demonstrates a conflict with the normative requirement.
- `candidate_for_review`: a concrete signal exists but semantic or ownership judgment is unresolved.
- `not_applicable`: explain why the software shape genuinely does not exercise the requirement.
- `insufficient_evidence`: identify the missing source, runtime, owner or decision evidence.
- `unsupported`: explain the language/tooling limitation.
- `not_assessed`: explain why the review could not be performed.

Never infer `satisfied` from zero findings, absent keyword matches, an enforcer that did not run, or a similarly named local rule. Do not count a qualitative observation as accepted formal manual evidence unless it meets the standard's evidence schema, scope, reviewer, freshness and artifact requirements. Keep deterministic execution status and qualitative review status separate.

For every material finding, include the actual behavior, requirement meaning, exact evidence location, consequence, confidence, status and a practical correction. Trace dataflow and callers when needed. Do not report an identifier without explaining its meaning in user-facing prose.

## 5. Separate review scope from adoption level

The comprehensive review always considers all catalog requirements. The recommended adoption level remains an incremental decision. Report separately:

- Comprehensive architectural review: all catalog requirements and their review statuses.
- Deterministic coverage: selected level, languages, checks actually executed, checks not executed and reasons.
- Formal manual evidence: accepted and missing evidence under the standard's evidence rules.
- Adoption recommendation: smallest useful level and sequence, with existing strengths preserved.

Do not claim conformance because all requirements were discussed or reviewed. Do not force L3 adoption merely because the assessment reviewed L3.

## 6. Required report

Report repository scope and exclusions; project/language/deployment inventory; provisional ownership map; existing architecture and enforcement comparison; findings grouped by L1/L2/L3; a complete 55-rule status matrix; cross-project integration contract findings; deterministic coverage by language; formal manual-evidence status; critical gaps; adoption sequence; confidence and limitations.

Prioritize material architectural risks and inconsistencies. Preserve existing good architecture. Distinguish genuine ACIMA conflicts from different but acceptable design choices. Assessment is read-only; implementation requires separate, explicit, scope-specific approval.
