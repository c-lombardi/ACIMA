# ACIMA product and adoption simplification

**Purpose:** make ACIMA straightforward to understand, evaluate, adopt, operate and maintain without weakening any architectural, evidence, approval or conformance requirement.

**Product framing:** Architecture that enforces itself.

**Status:** orchestration plan and workstream contracts. These documents do not change the normative ACIMA standard or authorize changes to another repository.

## The product in one explanation

ACIMA helps a team make its software module boundaries explicit and enforceable. It checks whether modules own their implementations, publish contracts and depend on other modules only through those contracts. It explains what it found, what it could not establish, and what a team could improve.

For an existing codebase, ACIMA first assesses without changing anything. It then explains whether ACIMA fits, proposes the smallest useful adoption scope, asks the owner to approve that scope, implements only the approved work, and verifies what changed.

The user should never need to understand ACIMA's internal rule IDs, data structures, CLI commands or implementation details to make a sound decision.

## The user's mental model

The user should only need to understand five things:

1. **What ACIMA does:** makes module ownership and architectural boundaries explicit and checkable.
2. **What ACIMA found:** what is already working, what needs attention, and what remains unknown.
3. **What ACIMA recommends:** the smallest useful changes, why they help, what they cost and what they do not prove.
4. **What ACIMA needs permission to do:** the exact scope and stages the owner approves.
5. **What ACIMA verified:** what actually changed, which checks passed, and what remains incomplete.

A user-facing explanation follows this order:

**Intent → observed behaviour → consequence → recommended action → evidence and confidence → technical traceability.**

Do not lead with rule codes, filenames, internal workflow identifiers or implementation vocabulary when a plain-language explanation is available.

## The canonical adoption journey

The journey has five product phases plus a start step. The same phase names, purpose and completion rules apply in guided and automated adoption.

| Phase | What ACIMA does | What the user sees | What must be true before moving on |
|---|---|---|---|
| Start | Identify the repository and ask for guided or automated adoption when no mode has already been selected. | One simple mode choice; no ACIMA terminology quiz. | The target repository and workflow mode are known. |
| 1. Assess | Inspect read-only, complete the evidence-backed review of all 56 current requirements, inspect module ownership and run only supported checks whose prerequisites are satisfied. | What the repository does, existing architecture, findings, limits, coverage and map status. | Every requirement has a valid evidence-backed disposition. Missing ownership blocks only checks that depend on it. |
| 2. Explain and propose | Evaluate fit, recommend a level in practical terms, explain value and tradeoffs, prepare the ownership proposal where needed, and produce the scoped proposal and six-page report. | A product-level recommendation, exact proposed changes, benefits, costs, risks, decisions and next step. | The proposal and report agree with the evidence and preserve unknown or blocked states. |
| 3. Review and authorize | Present the proposal, collect ownership decisions and record exact approval provenance and scope. | The specific choices, paths and stages that can be approved, declined, changed or deferred. | The user has inspected the exact report and explicitly approved the exact scope. |
| 4. Implement | Execute only the approved stages and paths, validating each stage before continuing. | What is being changed now, why, which files are involved, and what happens next. | Every change remains inside the approval. New scope or changed evidence returns to review. |
| 5. Verify and hand off | Run fresh checks, compare results, validate artifacts and explain what is complete and what remains. | What changed, what passed, what is still unverified and how to run the checks. | The handoff is evidence-backed. It does not overstate conformance or imply commit, push, merge or release approval. |

### What each phase must explain

Every phase in the skill, CLI, report and documentation uses the same small content contract:

- **Purpose:** why this phase exists.
- **ACIMA does:** the work performed by the system or agent.
- **You see:** the result presented to the user.
- **You decide:** the decision, if any, reserved for the owner.
- **Done when:** the observable completion condition.
- **Next:** the single next action and why it is now possible.

Keep this structure consistent. Do not invent a new phase vocabulary for each surface.

## Guided and automated adoption

Both modes use the same assessment, evidence quality, map-quality rules, proposal content, approval requirements, implementation restrictions and verification criteria. The only meaningful difference is the timing and grouping of review.

**Guided adoption**
- ACIMA pauses at meaningful decisions.
- The user reviews the module map and its individual boundaries before ownership-dependent checks use it.
- The user reviews the completed proposal and six-page report before approving exact scope.
- CI, adoption notifications, agent guidance and remediation remain distinct decisions wherever the current skill requires separate approval.
- Implementation is divided into understandable stages. Each stage is checked before the next.

**Automated adoption**
- ACIMA performs the same complete assessment and prepares the full adoption package before asking for the consolidated review.
- The user sees the map, findings, proposal, exact file impact, CI recommendation, guidance proposal, stage plan, risks and limitations together.
- The user may approve all, selected, modified or no implementation stages.
- Automated preparation does not approve inferred module ownership, authorize writes, or grant blanket permission.
- After the user approves the exact scope, ACIMA performs the selected work automatically and verifies each stage.

Automated means **ACIMA prepares and executes approved work with less step-by-step interruption**. It does not mean that ACIMA makes consequential ownership or scope decisions for the user.

## Non-negotiable product guarantees

These are product requirements, not optional simplification choices:

1. **Assessment is read-only.** No target source, configuration, build or CI changes during assessment.
2. **All 56 requirements are reviewed.** Each receives an individual, evidence-backed disposition. Incomplete or unresolved review cannot be presented as a decision-ready clean assessment.
3. **A missing module map is not a reason to skip assessment.** Propose evidence-backed ownership candidates, continue independent qualitative review, and block only checks that genuinely require approved ownership.
4. **Discovery is not ownership.** A directory, project, package, service, namespace or runtime host is evidence, not an approved ACIMA module. Never auto-approve inferred boundaries.
5. **The report is a decision document.** Generate and validate the six offline pages: Overview, Proposal, Findings, Files, Plan and Evidence. The user must be shown the exact report before approval is requested.
6. **Approval is explicit and scoped.** Record the reviewer and exact report/proposal/repository identity. Partial approval is supported. A changed report, proposal or target invalidates stale approval.
7. **No writes before approval.** Adoption intent, assessment completion, report generation or acknowledgement is not permission to edit.
8. **Existing architecture is evaluated, not discarded.** Preserve sound existing maps, analyzers, gates, instructions, workflows and tests. ACIMA adds missing guarantees; it does not replace working systems without evidence and approval.
9. **CI configuration is not a CI run.** A copied enforcer or written workflow is not proof of observed enforcement.
10. **Remediation is a separate decision.** The owner can choose none, selected or all recommendations; manual work remains manual.
11. **Optional artefacts stay optional.** Do not generate communication plans, dashboards or organizational documents by default.
12. **Conformance is evidence-based.** The claim layer computes the result from current repository evidence. A clean error count, empty findings list or completed adoption workflow is not full conformance.
13. **No health score.** Report actual evidence and coverage, not a synthetic score.
14. **Technical preview limits remain visible.** Keep unsupported languages, unexecuted rules, manual evidence, draft status and independent-validation limits explicit.

## Language and prompt-engineering principles

Use these rules consistently in the skill, agent prompts, Markdown, CLI help, HTML report and generated developer guidance.

### Write for the reader's decision

- Use short, literal sentences and active verbs.
- Put the reason before the mechanism.
- Name the responsible actor: ACIMA, the owner, the enforcer or the repository.
- Explain the business or engineering consequence before a technical identifier.
- State one action per instruction.
- Use the same term for the same concept everywhere.
- Define an unavoidable technical term the first time it appears.
- Prefer concrete examples over abstract admonitions.
- Preserve uncertainty explicitly. "Not established" is better than a guess.

### Separate requirements from advice

Use **must** for a binding requirement, **must not** for a prohibition, **should** for a reasoned recommendation, **may** for an option, and **is not supported** when the current implementation cannot do something. Do not turn a preference into a rule.

### Keep the skill easy to navigate

The top-level skill is the entry point and workflow controller, not an encyclopedia. It should explain the product, start the user correctly, list the phase sequence, state the non-negotiable guarantees and route the agent to the relevant reference. Detailed procedures belong in one authoritative reference each. Avoid repeating the same rule in multiple files; link to the authoritative explanation instead.

Use progressive disclosure: load detailed references when the agent enters the relevant phase or handles the relevant decision. Do not load every reference into every interaction.

### Give every agent task a contract

Each subagent prompt states:
- the outcome it owns;
- why that outcome matters to the product;
- the authoritative inputs it must read;
- the exact files it may change;
- files and behaviours it must preserve;
- decisions it must not make;
- required output and evidence;
- acceptance checks and commands;
- dependencies and handoff format.

No subagent may silently expand its owned paths or redefine a product guarantee.

## Architecture and data separation for ACIMA itself

Organize the implementation around business responsibilities and data ownership, not around file size or framework fashion.

| Responsibility | Owns | Must not own |
|---|---|---|
| Product and standard | Normative requirements, product promises, adoption constraints and terminology. | Runtime workflow progress or generated report state. |
| Assessment and discovery | Repository observations, source evidence, qualitative dispositions and proposed ownership. | Approval or target writes. |
| Ownership and conformance | Approved module map, dependency graph, deterministic findings and conformance evidence. | User interaction or report copy. |
| Adoption workflow | Phase progression, prerequisites, approval receipts, scope, resumption and one next action. | Recalculating findings or maintaining a second copy of assessment facts. |
| Proposal and reporting | Evidence-backed projections, explanation and navigable reader views. | Creating facts that are absent from the assessment and workflow records. |
| Adapters | CLI, filesystem, Git, subprocesses, language toolchains, agent runtime and HTML rendering. | Duplicating business rules or independently authorizing changes. |

Apply these patterns selectively:

- **Functional core, imperative shell:** keep assessment rules, map reconciliation, approval validation and state transitions deterministic. Put filesystem, Git, subprocess and model interactions at the edges.
- **Ports and adapters:** expose narrow contracts for repository access, enforcer execution, report rendering and agent-runtime integration so business logic can be tested without those tools.
- **Bounded contexts:** assessment, ownership/conformance, adoption workflow and reporting have separate responsibilities and authoritative data.
- **Single source of truth:** an approval, finding, map, requirement disposition or workflow state has one canonical record. CLI, skill and HTML are views or adapters over that record.
- **Versioned data contracts:** validate inputs and outputs at boundaries. Reports are projections of authoritative evidence, not a second assessment engine.
- **Explicit orchestration:** one workflow coordinates operations and checks prerequisites. Individual components do not independently discover, invoke or approve peers.

Do not introduce microservices, event sourcing, generic plugin systems, elaborate CQRS or abstraction layers without a demonstrated need. The purpose is to reduce coupling and duplicated decisions, not add architecture for its own sake.

## Parallel work and integration

The work is divided into non-overlapping workstreams. A product contract is the first dependency. Once it is agreed, the implementation lanes can proceed concurrently.

\`\`\`mermaid
flowchart TB
    A["0. Preserve baseline and inventory current behaviour"] --> B["1. Agree product experience and phase contract"]
    B --> C1["WS-01 Product language and documentation"]
    B --> C2["WS-02 Adoption skill and prompt architecture"]
    B --> C3["WS-03 Workflow, domain data and CLI"]
    B --> C4["WS-04 Report model, HTML and design"]
    B --> C5["WS-05 Enforcers, waivers and baseline"]
    B --> C6["WS-06 Independent QA and acceptance matrix"]
    C1 --> D["2. Integrate by file ownership"]
    C2 --> D
    C3 --> D
    C4 --> D
    C5 --> D
    C6 --> D
    D --> E["3. Validate shared product guarantees"]
    E --> F["4. Human-readable handoff and next release decision"]
\`\`\`

### Workstream boundaries

| Workstream | Owns | Parallel rule |
|---|---|---|
| WS-01 Product language and documentation | PRODUCT.md, README.md, docs/commands.md, product/quickstart Markdown and user-facing glossary. | Does not edit the adoption skill, workflow engine or report renderer. |
| WS-02 Adoption skill and prompt architecture | skills/acima-adoption/SKILL.md, its procedural references and skill manifest. | Does not edit workflow Python, report schema or renderer. Regenerate vendor copies only after canonical skill changes are complete. |
| WS-03 Workflow, domain data and CLI | conformance/adoption_workflow.py, module_map.py, adoption_reports.py, tools/acima.py and their corresponding workflow/map/CLI tests. | Does not edit the skill prose or HTML renderer. Propose/extract boundaries incrementally; preserve behavior. |
| WS-04 Report model, HTML and design | Report JSON schema, renderer, CSS, DESIGN.md, report tests. | Does not redefine assessment or approval logic; consume validated data contracts. |
| WS-05 Enforcers, waivers and baseline | Four language reference enforcers and their waiver/fingerprint/profile tests. It inherits the existing uncommitted fingerprint and .NET detector work. | Does not change the rule catalog or CLI orchestration. Coordinate any baseline CLI contract with WS-03. |
| WS-06 Independent QA | Read-only audit, acceptance matrix and test results under docs/product/simplification/qa/; an isolated new test file only when approved by the integrator. | Does not rewrite production files or weaken assertions to obtain a pass. |
| Integrator | Cross-workstream contracts, overlap resolution, final source/vendor synchronization and full-suite verification. | Runs after all lanes return their handoff; owns merge decisions. |

### Integration rules

- Establish one baseline and record existing uncommitted changes before parallel work starts.
- Each worker writes only to its owned files. If a change crosses ownership, it proposes the change to the integrator.
- Workers do not commit, push, switch branches or modify another repository.
- Preserve the current in-progress enforcer changes. The owner of WS-05 must inspect them before editing and retain useful work.
- No worker changes the normative standard or 56-rule catalog as part of a language simplification task.
- The integrator reconciles duplicate terminology and data contracts before merging.
- Run focused tests per workstream, then the complete conformance suite, skill-bundle integrity check and adoption regression matrix.
- Keep model-conversation quality distinct from deterministic tool tests. If a live conversation is not executed and scored, state that honestly.

## Definition of done

The initiative is complete when a new user can explain what ACIMA does and what will happen next without knowing its internal IDs; the guided and automated journeys are clear and honest; the skill can route an agent with minimal repeated context; workflow facts and approvals have one authoritative owner; the report explains the result without inventing evidence; the CLI and docs use the same vocabulary; all existing product guarantees remain intact; and the regression suite proves that simplification did not weaken them.

The handoff must state:
- which workstreams completed and which did not;
- files changed and the responsible workstream;
- focused and full tests run with actual results;
- existing behaviour deliberately preserved;
- any unresolved conflicts, unknowns or manual checks;
- the one next decision needed from the product owner.
