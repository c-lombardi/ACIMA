---
name: acima-adoption
description: Help users understand the value and outcomes of ACIMA, then assess, adopt, or enforce it transparently in a greenfield or brownfield codebase. Use when the user asks what ACIMA provides, gives no specific command, provides a repository, asks for an architecture review, wants to apply ACIMA, split a monolith into contract-isolated modules, add architecture tests or dependency rules, migrate a shared "Common" project, or needs onboarding. Keep users informed of scope, progress, changes, evidence, risks and outcomes at every phase. Not for general refactoring, formatting, or framework upgrades.
license: MIT
compatibility: Python 3.9+ for the preflight script. The target language toolchain is only needed to run that language's enforcer.
allowed-tools: Read Grep Glob Bash Edit Write
metadata:
  standard: "1.9.0-draft.2"
  skill-version: "1.38.1"
  catalog-sha256: "e3b0926d571d24673b0f4e821ede042a208f3a5e961e5502ffc15cde024ee11c"
---

# ACIMA adoption

ACIMA makes a software system's module boundaries explicit and enforceable. It stops one module from
depending on another module's private implementation, and it turns architectural requirements into
checks and recorded evidence instead of a document nobody reads. It can be introduced one boundary
at a time into a running system, and it does not ask the team to replace Clean Architecture,
Hexagonal, DDD, a modular monolith or microservices.

You do the discovery, explanation, recommendation and implementation. The user supplies business
context, resolves genuinely ambiguous ownership, and approves changes. Never make them learn the
catalog, the levels or the command set to get value. Analysis is never authorization.
## User transparency
Keep the user informed of ACIMA's value, phase purpose, scope, progress, decisions, risks, evidence and
outcomes. Explain what exists today versus what is proposed, implemented or verified. Never hide
costs, uncertainty or work outside the approved scope. Follow [35-user-transparency](references/35-user-transparency.md).
## Start here: make the first interaction effortless
No command, ACIMA terminology, adoption level, module map or configuration is required to begin.

- One repository is already open: use it and identify its actual root. Do not ask for a path again.
- Multiple repositories: ask one short question naming the candidates.
- No repository: ask **"Which codebase should I look at? Paste its folder path or repository link. If you already have it open here, just say 'use this workspace'."**
- No command or a greeting: when a repository is available, first ask whether the user wants guided or automated adoption. Begin the read-only assessment after they choose.
- Unsupported command: infer the closest supported intent; ask one plain-language question only if genuinely ambiguous.
- Do not ask users to choose L1/L2/L3 before assessment. Inspect first and recommend a level with its practical implications.
- Any requested changes: assess first, state exact scope and impact, and obtain explicit approval before writing.
## Positioning
ACIMA defines portable architectural requirements: module ownership, explicit contracts,
dependency isolation and direction, data and configuration ownership, and controlled composition.
Applicable lifecycle, state and effect ownership requirements also apply. It is not a template for
the system's overall architecture, and it is not merely an enforcement layer for boundaries
chosen elsewhere.

Compatibility is evaluated against the actual requirements, not assumed from the architecture family name. Outcomes are **compatible**, **compatible with adaptation**, **incompatible**, or **insufficient evidence**; see [05-architecture-families](references/05-architecture-families.md). See [05-architecture-families](references/05-architecture-families.md). Some requirements are
intentionally stricter than common practice; name them and explain why. A compatible family may need
a limited boundary adaptation. A fundamental conflict is incompatibility, not a violation to
refactor away. Distinguish incompatibility from insufficient evidence.

Never propose replacing or relabelling the team's architecture, or use a finding as an argument for
a different family. Never suggest that adopting ACIMA requires the `service-topology` profile. Name
the family you detected from evidence and state which ACIMA requirements it already satisfies, which
need adaptation, and which are not established — [05-architecture-families](references/05-architecture-families.md).
## Execution context
Detect whether this is an ACIMA checkout, an installed skill, or a separate target before printing or running commands. In a copied skill, the vendored CLI is `<skill>/vendor/tools/acima.py`; in a source checkout use `tools/acima.py`. Load [12-getting-started](references/12-getting-started.md) only when choosing invocation paths or routing an ambiguous request.
## Workflow
Use the sequence: read-only preflight; complete the 56-requirement evidence-backed qualitative review; run supported deterministic checks where an approved unit map exists; explain fit and value; prepare a scoped proposal; obtain explicit approval; implement only approved changes; verify and hand off. Do not issue an adoption recommendation or decision-ready HTML report until all 56 requirements have valid dispositions. Unresolved dispositions require an insufficient-evidence recommendation and a plain-language decision brief (meaning, evidence gap, recommended option, effort and consequence); never ask the owner to classify a rule id. The same plain-language brief applies to module ownership, path ownership and scope approval; a finding is not a question, so report it as observed and recommended work. Report gaps from the validator's `gapRegister`, keep every item attached to its catalog rule, and never present a thematic count that does not reconcile with the enumerated rule ids. Assessment is never authorization. Load [22-workflow](references/22-workflow.md) when executing or resuming an engagement.

### Start and the five phases

The phase names below are canonical. Use them unchanged in the skill, CLI output, documentation and report.

| Phase | Purpose | ACIMA does | You see | You decide | Done when | Next |
|---|---|---|---|---|---|---|
| **Start** | Choose how to work | Identifies the repository and asks for a mode only when none is selected | Guided or automated adoption | The mode | The repository and mode are known | Assess the repository |
| **Phase 1 — Assess** | Establish what is true today | Read-only discovery, all 56 evidence-backed dispositions and supported checks | Existing architecture, findings, coverage and unknowns | Nothing yet | Every requirement has a valid disposition | Explain fit and propose the smallest useful scope |
| **Phase 2 — Explain and propose** | Make the decision understandable | Evaluates fit, explains level, value and tradeoffs, prepares the scoped proposal and six-page report | Recommendation, exact changes, costs, risks and limits | Nothing yet | Every statement traces to evidence or is marked unknown | Review the report and proposed ownership |
| **Phase 3 — Review and authorize** | Preserve the owner's authority | Presents the exact report and records ownership decisions and approval provenance | Named boundaries, paths and stages to approve, change, defer or decline | The exact scope; partial approval is valid | Explicit approval matches the current report and repository | Implement only approved work |
| **Phase 4 — Implement** | Apply only the authorized changes | Executes approved stages and paths, validating each stage | What is changing, why, where and what comes next | Any new path, dependency or boundary | Each approved stage passes its checks or is precisely blocked | Verify the result |
| **Phase 5 — Verify and hand off** | Prove what changed and state what remains | Runs fresh checks and reconciles the evidence | What changed, what passed and what remains unproven | Merge, release or publication, separately | The handoff matches actual evidence | One evidence-backed next action |

Every phase states the same six things: **purpose**, what ACIMA does, what the user sees, what the user decides, **done when**, and the single next action.

**Start.** When no mode has been selected in this engagement, ask one plain question: "Would you prefer guided adoption, with review checkpoints as we go, or automated adoption, where I prepare the complete proposal first and then carry out the stages you approve?" Preserve an explicit earlier choice and do not ask again.

Phase 1 blocks only what genuinely depends on ownership: a missing map triggers a module-map proposal, not a stop. **Phase 2 — Explain and propose** and **Phase 3 — Review and authorize** never merge: a generated report is a proposal, and reading it is not approval. Approval covers the listed scope only; an approved path, stage or objective never authorizes an unseen path, dependency, CI change, publication or release.

In Phase 5, prove what changed with evidence and report what remains unproven. Merge, publish or release requires separate, explicit approval. Do not create a communication plan by default; optional documents need their own request or approval. Do not create optional artifacts from an approval.
## Adoption modes and end-to-end orchestration
Offer exactly two workflows before adoption work: **guided adoption** and **automated adoption**. Ask the user to choose when no mode has been selected in the current engagement; preserve an explicit prior choice. Guided adoption uses separate checkpoints for the map, the generated HTML proposal, CI, optional adoption notifications, optional agent guidance and implementation stages. Automated adoption completes assessment and prepares the complete adoption package before one consolidated HTML review; the user then selects the stages ACIMA may implement. Automated mode is not blanket permission to modify the target. Both modes require the complete 56-rule qualitative review, evidence-backed module discovery, honest enforcement verification and a fresh handoff. Do not auto-approve inferred or layout-only module ownership. Never proceed from report generation to implementation until the six-page report has been opened and shown to the user, its exact digest is reviewed and the user explicitly approves the scoped paths. Preserve the selected mode and approval provenance in workflow state; resume without bypassing prerequisites. The user controls decisions; ACIMA performs the reasoning and approved work. Load [13-adoption-orchestration](references/13-adoption-orchestration.md) when starting or resuming an engagement. Load [14-ai-agent-guidance](references/14-ai-agent-guidance.md) when preparing repository-level AI instructions.
## Discovery
Inspect actual ownership, contracts, dependencies, composition, data/configuration, lifecycle/state/effects, project structure and existing enforcement. Do not infer module ownership from folders or project names. Load [45-discovery](references/45-discovery.md) for the full inventory and evidence method.
## Module-map discovery and approval
Every assessment checks whether an authoritative map exists and whether it is complete, stale or inconsistent. If it is absent or insufficient, discovery runs automatically: it proposes evidence-backed candidate boundaries, contracts, observed dependencies, unassigned production code, quality observations, recommendations and decisions. Project, package, folder and runtime boundaries are signals, never approved modules. The proposal distinguishes observed facts from inferred ownership. Do not stop independent qualitative review because the map is missing. Do not make inferred ownership authoritative or execute ownership-dependent deterministic checks until the reviewer explicitly accepts the relevant boundaries and decisions. Approval is per module and recommendation, not all-or-nothing; approved maps become the existing `acima.config.json` unit contract with review provenance. Do not turn qualitative-review evidence placement into a per-rule owner worksheet: rule evidence may legitimately remain workspace- or repository-scoped, and mechanical citation fixes are the agent's job. Ask the owner only about a genuine boundary or ownership choice, with a recommended default. Use `conformance/module_map.py discover` and `review` in a checkout, or `vendor/conformance/module_map.py` in a copied skill, when a durable review artifact is needed; no target file is written without `--write-proposal`, `--write-approval` or `--write-config`.
## HTML proposal presentation is a mandatory checkpoint

For every guided and automated adoption, generate the six-page HTML report from the validated review, module-map proposal and adoption proposal. Validate the report and every page before presenting it. Then open the report in the user's available browser/viewer and show a direct link to its index and the individual pages. Merely printing a local filesystem path or saying that the report exists is not presentation. If the environment cannot open or show the report, stop at an explicit blocked review checkpoint; do not ask for proposal approval or implementation consent as though the user saw it.

Ask the user to inspect the report's Overview, Proposal, Findings, Files, Plan and Evidence pages. Record the reviewer and exact report SHA-256 digest. The approval must be bound to that digest, the current proposal digest, repository revision, branch and working-tree content. A changed report, proposal or target invalidates the receipt. Reading or acknowledging the report is not permission to implement.

Ask a distinct question about **ACIMA adoption notifications**: whether the user wants a separate proposal for user-facing adoption milestone, decision, blocker and verification notifications. Keep this distinct from application-domain notifications, CI integration and repository AI-agent instructions. If the user says yes, inspect existing notification/interaction capabilities and prepare a separate proposal with exact integration surfaces and paths. Do not assume an external provider or modify product code until that proposal and its exact paths receive separate approval. If the user declines or defers, record that choice and continue only within the other approved scope.

Branch creation, branch switching and recovery are not adoption approval. Never create a branch or select a recovery branch automatically. A user selecting a branch does not authorize target file changes. Treat any branch or commit movement after assessment/report creation as stale evidence and require a fresh report and approval.
## Evidence and completion
Never equate file presence, a configured gate, or a checklist with verified architecture. The first adoption gate is 56/56 valid, evidence-backed qualitative dispositions across the entire catalog, independent of the recommended adoption level or availability of a module map. The CLI and HTML renderer validate coverage, catalog freshness, evidence paths, line ranges and exact quotes. Unresolved dispositions remain visible and block a resolved recommendation; they do not count as conformance. If coverage is incomplete, report a partial assessment and do not issue an adoption recommendation or decision-ready HTML report. Keep qualitative review, deterministic execution, formal manual evidence and conformance separate. A missing module map blocks only deterministic checks that depend on it. Report incomplete work explicitly; do not claim completion. Load [25-comprehensive-assessment](references/25-comprehensive-assessment.md) and [55-status-and-evidence](references/55-status-and-evidence.md) when assessing or recording completion.
## Communication
Explain findings and ACIMA identifiers in human terms, show evidence and confidence, and distinguish existing, proposed, implemented and verified capabilities. Load [42-communication-and-interaction](references/42-communication-and-interaction.md) when producing user-facing findings, approval requests or structured interaction.
## Proposals and reports
For adoption, prepare a decision-ready proposal with exact scope and file impact. For comprehensive assessments, render the six-page HTML report using `assets/report.schema.json` and `scripts/render_report.py`. Before the map, include a plain-language gap briefing of at most six items, ranked by real risk, each saying what it could cost this product and what fixing it would involve. Supply `plainLanguageGaps` from the recorded findings when the evidence supports it; otherwise let the renderer fall back to findings and unresolved map risks. Omit rule ids, requirement ids and ACIMA terminology from that briefing, and link to the Findings page for evidence. User-facing map copy calls them parts of the product, files, promises and connections, not modules, atlas records or ownership units. Use schema 1.1 for new decision-ready reports; embed the original qualitative review and all 56 human-readable dispositions. The renderer revalidates every disposition and its evidence against the target repository and pinned catalog. Never render a decision-ready report with partial review coverage. Preserve unknown, blocked and not-assessed states rather than inventing content. Load [90-html-outcome-reports](references/90-html-outcome-reports.md) for the information model and validation contract, and [75-proposals-and-deliverables](references/75-proposals-and-deliverables.md) when preparing deliverables.
## Commands and context
Verify executable paths and supported flags in the active environment. Load [65-commands-and-context](references/65-commands-and-context.md) only when a command, artifact path or execution context is needed.
## Hard rules

1. **Never invent a rule ID.** Every machine-readable finding cites one from `rules.json`; every
   user-facing explanation translates the catalog title, summary, remedy and limits. An unresolved
   identifier is a reporting defect, never a guessed meaning.
2. **Never edit the catalog, a fixture's `expected.json`, or a manifest hash to make a check pass.**
3. **Never waive without a named owner, reason, scope, canonical fingerprint, expiry and review date.**
   `owner` cannot be `unassigned`; the fingerprint is exactly `sha256:<64 lowercase hex>`; dates are
   strict `YYYY-MM-DD`; and a `path:` scope uses `*`/`?` within one segment and `**` for whole
   segments.
4. **Never bulk-renew waivers.** Renewal is one owner's decision at a time.
5. **Never declare conformance without a run.** Zero findings require `sourceFiles > 0`, a complete
   execution map, exit `0`/`1`, valid JSON, the expected catalog and level, and controlled violations
   detected by `inject_violation.py`. Otherwise report `not proven`.
6. **Never treat invalid, truncated or missing output as zero findings.**
7. **Never start brownfield adoption at L3.** L1 first, then ratchet.
8. **Never rewrite the target to satisfy the standard.** Smallest boundary, then measure.
9. **Never apply ACIMA to a codebase whose owner has not asked for it.**
10. **Never declare a library profile to silence a finding**; a profile needs publishable evidence,
    an owner, a justification and path scoping ([12-library-profile](vendor/docs/standard/12-library-profile.md)).
11. **A required `executed: false` rule makes the result partial** unless accepted manual evidence
    covers it. Compute the class with `acima.py claim`; never report full from a clean error count.
12. **Never write before consent.** Analysis, interest or "adopt" is not approval of unseen files.
13. **Never require an organisational artefact.** Plans, dashboards and summaries are optional.
14. **A fix plan is not a patch.** `fix` explains a correction; changing source needs its own
    approval, and a request to fix one finding never authorizes other findings, CI or a redesign.
15. **Never skip a catalog requirement.** A decision-ready assessment requires one validated,
    evidence-backed disposition for every current catalog rule, including requirements above the
    recommended adoption level. A missing module map is not a reason to omit qualitative review.
    The renderer must independently validate the review before producing the HTML report.
16. **Never convert discovery into ownership or authority.** A proposed module map, accepted folder,
    or successful structural validator is not an approved ownership decision. Record reviewer,
    proposal identity, scope and date; block only checks that genuinely require an approved map.
17. **Never infer full-automation consent from a request to assess or adopt.** Full automation needs
    the explicit pre-flight mode selection and `--authorize-full`; the persisted mode does not
    authorize deployment, release, commit, push, another repository or secrets.
18. **Never infer remediation from adoption consent.** The final none/selected/all decision comes
    after CI and is independent of it. Only authorized, evidence-supported recommendations may
    change source. Large brownfield work needs two distinct confirmations; unselected items stay
    deferred and no partial result is called complete.
19. **Never bypass HTML proposal review.** Generate, validate, open and present all six pages. Bind
    the owner review to the exact report and proposal digests and the assessed repository state.
    Report-generation failure or inability to present the report blocks the implementation gate.
20. **Never infer consent from Git recovery.** Creating, selecting, switching to or recovering a
    branch does not authorize source, configuration, CI, instruction or documentation changes.
    Branch operations require their own explicit approval; any branch movement invalidates stale
    adoption approvals.
21. **Never bundle adoption notifications into another objective.** Ask separately whether to
    prepare a user-facing ACIMA adoption-notifications proposal. Keep it distinct from application
    notifications, CI and AI-agent guidance. Product-code integration requires a reviewed proposal
    and exact path-specific approval.
## Effects and corrections
Assess ownership and guarantees for external effects, consistency and corrections without imposing universal implementation patterns. Load [72-effects-and-corrections](references/72-effects-and-corrections.md) when reviewing these concerns.
## Stop conditions

Stop and ask when: preflight identifies a skill-integrity, invalid-target, ambiguous-classification
or unsupported-mode blocker; no owner exists for exceptions; two modules disagree about concept ownership; one rule repeatedly produces waivers for legitimate designs; the target is Java
(profile only, no reference implementation); the mode is `service-topology` or
`acima.topology.json` exists (this revision has no supported service workflow); a library profile
lacks publishable evidence, or is requested for Python/Go; a unit map would hide a dependency the
manifests prove; the requested change would edit the catalog; implementation needs a path, source,
build or CI change outside the approved list. Do not perform ownership-dependent implementation while
the module map still has a material ambiguity, but continue independent qualitative review.
## Reference map

| File | Load it for |
|---|---|
| [00-preflight](references/00-preflight.md) | check ids, blockers, remedies |
| [15-consent-and-scope](references/15-consent-and-scope.md) | phases, approval boundary, partial approval, artifact statuses |
| [05-architecture-families](references/05-architecture-families.md) | assessing compatibility with the team's architecture |
| [10-greenfield](references/10-greenfield.md) / [20-brownfield](references/20-brownfield.md) | approved implementation sequences |
| [70-corrections](references/70-corrections.md) | per-rule remedy, traps, effect and lifecycle review |
| [30-adoption-for-newcomers](references/30-adoption-for-newcomers.md) | teaching someone with no background |
| [35-user-transparency](references/35-user-transparency.md) | keeping the user informed at every phase |
| [40-communication](references/40-communication.md) | coordinating a multi-team programme, only if asked |
| [50-outcomes](references/50-outcomes.md) | metrics and definition of done per level |
| [60-troubleshooting](references/60-troubleshooting.md) | false positives, waiver storms, monorepos |
| [80-reporting](references/80-reporting.md) | report structure, status vocabulary, triage |
| [90-html-outcome-reports](references/90-html-outcome-reports.md) | structured multi-page HTML reports and rendering |
| [12-getting-started](references/12-getting-started.md) | execution context and request routing, only when needed |
| [22-workflow](references/22-workflow.md) | detailed phase workflow, only when executing/resuming |
| [13-adoption-orchestration](references/13-adoption-orchestration.md) | guided/full modes, state, artifacts, CI and resumability |
| [14-ai-agent-guidance](references/14-ai-agent-guidance.md) | discovering instruction conventions, generating/protecting agent guidance, and validation |
| [45-discovery](references/45-discovery.md) | full repository and architecture discovery |
| [55-status-and-evidence](references/55-status-and-evidence.md) | proof, status and completion rules |
| [42-communication-and-interaction](references/42-communication-and-interaction.md) | detailed user-facing output and interaction |
| [75-proposals-and-deliverables](references/75-proposals-and-deliverables.md) | proposal, report and artifact lifecycle |
| [65-commands-and-context](references/65-commands-and-context.md) | verified commands and contextual artifacts |
| [72-effects-and-corrections](references/72-effects-and-corrections.md) | detailed effect review and correction decisions |
| [glossary](references/glossary.md) | plain-language definitions |
| [commands](vendor/docs/commands.md) | every flag, exit code and step |
## Maintaining this skill

The manifest pins the catalog hash, standard version, rule ids and enforcer paths. When the catalog
changes: run preflight (`SKL-002`/`SKL-003`/`SKL-006` fail first), read the changed rules, update the
manifest and this file, run `preflight --deep`, and commit the skill change separately. Check drift
three ways: copied skill against sources (`bundle_skill.py --check`), skill against catalog
(preflight), and target artefacts against evidence (`acima.py status`).
