---
name: acima-adoption
description: Help users understand the value and outcomes of ACIMA, then assess, adopt, or enforce it transparently in a greenfield or brownfield codebase. Use when the user asks what ACIMA provides, gives no specific command, provides a repository, asks for an architecture review, wants to apply ACIMA, split a monolith into contract-isolated modules, add architecture tests or dependency rules, migrate a shared "Common" project, or needs onboarding. Keep users informed of scope, progress, changes, evidence, risks and outcomes at every phase. Not for general refactoring, formatting, or framework upgrades.
license: MIT
compatibility: Python 3.9+ for the preflight script. The target language toolchain is only needed to run that language's enforcer.
allowed-tools: Read Grep Glob Bash Edit Write
metadata:
  standard: "1.9.0-draft.1"
  skill-version: "1.31.0"
  catalog-sha256: "b593d28e81dacfdb9ba61b5792cbab04c521c0631cec6ff61292045acada678a"
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
- No command or a greeting: begin a read-only assessment when a repository is available.
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
Use the sequence: read-only preflight; complete the 55-requirement evidence-backed qualitative review; run supported deterministic checks where an approved unit map exists; explain fit and value; prepare a scoped proposal; obtain explicit approval; implement only approved changes; verify and hand off. Do not issue an adoption recommendation or decision-ready HTML report until all 55 requirements have valid dispositions. Unresolved dispositions require an insufficient-evidence recommendation. Assessment is never authorization. Load [22-workflow](references/22-workflow.md) when executing or resuming an engagement.

### The five phases

**Phase 1 — Assessment.** Read-only discovery, the complete 55-requirement review, and deterministic checks only where an approved map exists. A missing map triggers a module-map proposal, not a stop.

**Phase 2 — Proposal.** A decision document with exact scope, file impact, tradeoffs, decisions and a single recommendation. Module-map boundaries and recommendations remain open to individual review.

**Phase 3 — Explicit authorization.** The owner approves named files, level, boundaries and recommendations. Partial approval is supported. Approval covers the listed scope only. Do not create optional artifacts from this approval.

**Phase 4 — Approved implementation.** Change only the approved paths and scope. A new path, level, dependency or boundary requires a new decision.

**Phase 5 — Verification and handoff.** Prove what changed with evidence; report what remains unproven. Merge, publish or release requires separate, explicit approval. Do not create a communication plan by default; optional documents need their own request or approval.

## Adoption modes and end-to-end orchestration
At pre-flight, explicitly offer **guided adoption** and **full automation**. Guided generates the module-map proposal, adoption proposal, enforcement plan and CI proposal, then waits for scoped approval before implementation. Full automation is available only after an explicit confirmation; it applies supported module-map decisions, implements enforcement, adds a gate to a detected CI provider when safe, verifies the result and writes a handoff. Full automation is not permission to deploy, release, commit, push, modify another repository, expose secrets or make destructive changes. Any unsupported or ambiguous ownership decision pauses only that decision and is recorded; independent work continues. Preserve the selected mode in `.acima/adoption-workflow.json` and use `acima.py adoption status` to resume. Every stage has an artifact, completion condition and next action; never leave proposal, enforcement, CI or verification dangling. After CI is decided, ask the separate final question: apply **none**, **selected**, or **all applicable** recommended fixes. Do not infer remediation from adoption consent. Classify greenfield/brownfield from implementation and compatibility evidence, not age alone. Large or high-risk brownfield work needs two distinct affirmations: scope acknowledgement, then implementation authorization. Apply only the authorized changes, preserve user changes, revalidate stale findings, and run a fresh assessment afterward. Load [13-adoption-orchestration](references/13-adoption-orchestration.md) when starting or resuming an engagement.

## Discovery
Inspect actual ownership, contracts, dependencies, composition, data/configuration, lifecycle/state/effects, project structure and existing enforcement. Do not infer module ownership from folders or project names. Load [45-discovery](references/45-discovery.md) for the full inventory and evidence method.

## Module-map discovery and approval
Every assessment checks whether an authoritative map exists and whether it is complete, stale or inconsistent. If it is absent or insufficient, discovery runs automatically: it proposes evidence-backed candidate boundaries, contracts, observed dependencies, unassigned production code, quality observations, recommendations and decisions. Project, package, folder and runtime boundaries are signals, never approved modules. The proposal distinguishes observed facts from inferred ownership. Do not stop independent qualitative review because the map is missing. Do not make inferred ownership authoritative or execute ownership-dependent deterministic checks until the reviewer explicitly accepts the relevant boundaries and decisions. Approval is per module and recommendation, not all-or-nothing; approved maps become the existing `acima.config.json` unit contract with review provenance. Use `conformance/module_map.py discover` and `review` when a durable review artifact is needed; no target file is written without `--write-proposal`, `--write-approval` or `--write-config`.

## Evidence and completion
Never equate file presence, a configured gate, or a checklist with verified architecture. The first adoption gate is 55/55 valid, evidence-backed qualitative dispositions across the entire catalog, independent of the recommended adoption level or availability of a module map. The CLI and HTML renderer validate coverage, catalog freshness, evidence paths, line ranges and exact quotes. Unresolved dispositions remain visible and block a resolved recommendation; they do not count as conformance. If coverage is incomplete, report a partial assessment and do not issue an adoption recommendation or decision-ready HTML report. Keep qualitative review, deterministic execution, formal manual evidence and conformance separate. A missing module map blocks only deterministic checks that depend on it. Report incomplete work explicitly; do not claim completion. Load [25-comprehensive-assessment](references/25-comprehensive-assessment.md) and [55-status-and-evidence](references/55-status-and-evidence.md) when assessing or recording completion.

## Communication
Explain findings and ACIMA identifiers in human terms, show evidence and confidence, and distinguish existing, proposed, implemented and verified capabilities. Load [42-communication-and-interaction](references/42-communication-and-interaction.md) when producing user-facing findings, approval requests or structured interaction.

## Proposals and reports
For adoption, prepare a decision-ready proposal with exact scope and file impact. For comprehensive assessments, render the six-page HTML report using `assets/report.schema.json` and `scripts/render_report.py`. Use schema 1.1 for new decision-ready reports; embed the original qualitative review and all 55 human-readable dispositions. The renderer revalidates every disposition and its evidence against the target repository and pinned catalog. Never render a decision-ready report with partial review coverage. Preserve unknown, blocked and not-assessed states rather than inventing content. Load [90-html-outcome-reports](references/90-html-outcome-reports.md) for the information model and validation contract, and [75-proposals-and-deliverables](references/75-proposals-and-deliverables.md) when preparing deliverables.

## Commands and context
Verify executable paths and supported flags in the active environment. Load [65-commands-and-context](references/65-commands-and-context.md) only when a command, artifact path or execution context is needed.

## Hard rules

1. **Never invent a rule ID.** Every machine-readable finding cites one from `rules.json`; every
   user-facing explanation translates the catalog title, summary, remedy and limits. An unresolved
   identifier is a reporting defect, never a guessed meaning.
2. **Never edit the catalog, a fixture's `expected.json`, or a manifest hash to make a check pass.**
3. **Never waive without owner, reason, scope, fingerprint, expiry and review date.**
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
