# Comprehensive architectural assessment

A read-only ACIMA assessment has two independent outputs:

1. **Deterministic conformance measurement**: what the selected language enforcer actually executed against an approved module map.
2. **Comprehensive architectural review**: qualitative inspection of all requirements in the current catalog, including requirements above the level recommended for adoption.

A missing module map blocks the first output, not the second. Continue qualitative discovery and review. Do not call an inferred map approved, and do not invent deterministic results.

When no authoritative map exists, automatic discovery must produce a proposal before the assessment
concludes. The proposal contains candidate module names and responsibilities, observed evidence,
inferred ownership, candidate contracts, observed dependencies, unassigned production code,
architectural-quality observations, recommendations with rationale/benefit/risk/uncertainty, and
the decisions that require owner input. Project, package and directory boundaries are discovery
signals. Evaluate the proposal for meaningful ownership rather than inventory completeness: coherent
responsibility, implementation ownership, contract separation, dependency direction, cycles,
private-implementation coupling, data/configuration ownership and composition isolation. A structural
validator accepting a proposal does not make it architecturally correct.

The assessment must state separately whether an authoritative map exists, whether a proposal was
generated, whether it was reviewed or approved, which qualitative reviews were completed, and which
deterministic ownership-dependent checks remain blocked. A partial map preserves its existing units
and adds candidates only where ownership is missing. Approval is explicit and scoped per boundary
and recommendation; approved units become the existing unit-map contract, with proposal identity,
reviewer, review date and approval status retained. Do not write the map or run ownership-dependent
checks before that approval.

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

Read `tools/acima-spec/rules.json` and the normative chapter(s) for every requirement. The current catalog has 56 requirements: 28 L1, 10 additional L2 and 18 additional L3 (38 cumulative at L2 and 56 cumulative at L3). If the catalog changes, derive the counts from the catalog rather than hardcoding these values.

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

Every catalog rule must have exactly one explicit review disposition, using the validator's exact vocabulary:

- `conforms`: inspected evidence supports the requirement; cite exact files/locations and explain why the evidence satisfies its intent.
- `gap`: direct evidence demonstrates a conflict with the normative requirement; explain the actual behavior and consequence.
- `not_applicable`: explain why the assessed software genuinely does not exercise the requirement and support the scope decision with evidence.
- `insufficient_evidence`: identify what source, runtime, owner or decision evidence is missing. This is an explicit unresolved disposition, never a pass.

A concrete but ambiguous signal belongs in the rationale for `insufficient_evidence`, not in a guessed conformance or gap result. Do not infer `conforms` from zero findings, absent keyword matches, an enforcer that did not run, or a similarly named local rule. Do not count a qualitative observation as accepted formal manual evidence unless it meets the standard's evidence schema, scope, reviewer, freshness and artifact requirements. Keep deterministic execution status and qualitative review status separate.

For every material finding, include the actual behavior, requirement meaning, exact evidence location, consequence, confidence, status and a practical correction. Trace dataflow and callers when needed. Do not report an identifier without explaining its meaning in user-facing prose.

Module-map recommendations must distinguish observed repository facts, evidence-supported inferred
boundaries, recommendations and decisions requiring the owner. Every proposed assignment and
recommendation needs repository-relative evidence and line references where applicable. For an
absence claim, record the inspection scope and method; a missing keyword is not proof. Do not inflate
confidence because the proposal is internally consistent or a validator accepted it.

## 5. Separate review scope from adoption level

The comprehensive review always considers all catalog requirements. The recommended adoption level remains an incremental decision. Report separately:

- Comprehensive architectural review: all catalog requirements and their review statuses.
- Deterministic coverage: selected level, languages, checks actually executed, checks not executed and reasons.
- Formal manual evidence: accepted and missing evidence under the standard's evidence rules.
- Adoption recommendation: smallest useful level and sequence, with existing strengths preserved.

Do not claim conformance because all requirements were discussed or reviewed. Do not force L3 adoption merely because the assessment reviewed L3.

## 6. Required report

Report repository scope and exclusions; project/language/deployment inventory; provisional ownership map; existing architecture and enforcement comparison; findings grouped by L1/L2/L3; a complete 56-rule status matrix; cross-project integration contract findings; deterministic coverage by language; formal manual-evidence status; critical gaps; adoption sequence; confidence and limitations.

Prioritize material architectural risks and inconsistencies. Preserve existing good architecture. Distinguish genuine ACIMA conflicts from different but acceptable design choices. Assessment is read-only; implementation requires separate, explicit, scope-specific approval.


## Evidence-backed qualitative review: mandatory completion gate

The 56-rule inventory is not proof that the rules were reviewed. For every comprehensive assessment,
produce a structured JSON review with exactly one entry for every current catalog rule, including rules
outside the recommended adoption level. Use `tools/qualitative-review.schema.json` as the schema and
pin `catalogSha256` to the SHA-256 of `tools/acima-spec/rules.json` from the skill's bundled catalog.

Each entry must contain:

- `rule`: exact catalog identifier, exactly once.
- `status`: `conforms`, `gap`, `not_applicable`, or `insufficient_evidence`.
- `rationale`: a specific explanation of the disposition, not a keyword summary.
- `evidence`: one or more references to actual repository material. Use repository-relative paths.
  File evidence must include valid 1-based `startLine` and `endLine`, an exact `quote` found within
  those lines, an `observation` describing what was inspected, and a kind (`source`, `test`,
  `configuration`, `architecture`, or `inventory`). Use `absence` evidence only when explaining
  a searched-for absence; reference an existing repository file or directory and describe the
  search scope and method. Do not fabricate line numbers, quotes, files, or observations.

`not_applicable` requires an explicit scope rationale and evidence supporting why the requirement
is outside the assessed system. `insufficient_evidence` is an honest disposition, not a pass; it keeps
the decision unresolved even though coverage is complete. A `gap` is a completed review finding,
not a successful conformance result. Each requirement needs its own rationale and relevant evidence;
copy-pasted rationales and exact duplicate evidence records across requirements are rejected. Shared
source files may support multiple requirements only when the specific location, observation and
reasoning are independently relevant to each one. The validator checks evidence paths, line ranges,
exact quotes, rule identity/coverage, duplicate and unknown rules, reviewer/date metadata, and catalog
freshness. It validates evidence provenance and structure, not the semantic correctness of the reviewer's
interpretation. The adoption agent must still inspect and reason about the cited code; a matching
quote is not by itself proof that a requirement is satisfied.

Run the validator and require exit code zero:

```powershell
py -3 "<skill-root>\vendor\tools\acima.py" validate-review --root "<assessed-repository>" --file "<review-json>" --format json
```

Then attach the same validated review to the comprehensive assessment:

```powershell
py -3 "<skill-root>\vendor\tools\acima.py" assess --root "<assessed-repository>" --level L3 --review "<review-json>" --format json
```

The first adoption gate is **complete qualitative coverage**: all 56 current catalog requirements must
have exactly one valid, evidence-backed disposition. The validator's `coverageComplete` result means
every requirement was explicitly reviewed and accounted for; it does not mean every requirement is
resolved or conformant. An `insufficient_evidence` disposition is valid coverage, but remains an
unresolved decision and must be shown as such. Missing module ownership blocks only checks that
depend on an approved unit map. It never excuses skipping independent qualitative reviews.

Run the validator and require exit code zero for full catalog coverage. Exit code zero means all 56
dispositions and their evidence passed structural/provenance validation. It does not certify semantic
correctness. If the validator returns nonzero, do not produce a decision-ready adoption recommendation
or HTML outcome report. Continue the review or report only a clearly labelled preliminary discovery
result with no adoption recommendation.

An assessment may be called **complete** only when all 56 rule entries validate, none is
`insufficient_evidence`, the ACIMA unit map is declared, and the deterministic assessment finishes
successfully. This is assessment completeness, not `FULL CONFORMANCE`. A complete assessment may
contain gaps. Never manufacture an ACIMA unit map or a rule disposition to obtain a complete result.
If the project is not yet mapped, the 56-rule qualitative review may still be coverage-complete; report
that separately and keep deterministic and overall assessment completion false.

The HTML renderer independently revalidates the embedded original qualitative review against the
assessed repository and the pinned catalog. It rejects missing or duplicate requirements, stale
catalogs, unsupported dispositions, nonexistent evidence, invalid line ranges, fabricated quotes,
inconsistent counts, and an incomplete per-requirement disposition table. Do not bypass this gate by
hand-editing report counts or constructing a synthetic review. The renderer validates evidence
provenance and structure, not the reviewer's semantic interpretation.
