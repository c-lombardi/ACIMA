# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

The primary users are teams building and changing software with AI coding agents. They need architectural constraints an agent can read, follow, and be checked against, and they often evaluate or adopt those constraints inside a repository they did not design.

Staff engineers and architects are the main human evaluators and adopters: they decide whether ACIMA fits an existing codebase, define module ownership, review findings, and own exceptions. Engineering leaders are a secondary audience deciding whether the resulting evidence justifies adoption, cost, and risk.

## Product Purpose

ACIMA exists so architectural boundaries survive AI-accelerated change. It turns ownership into an executable obligation: a module owns its implementation, exposes an explicit contract, and prevents anything outside from depending on its internals.

Success means a new cross-module dependency can fail before merge, a reader can understand why it failed without knowing the rule catalog by heart, and a conformance claim never states more than the evidence supports. Adoption must remain an explicit, scoped decision rather than an automatic rewrite.

## Positioning

ACIMA's boundary is executable, not documentary. Its distinguishing mechanism is a small unit map plus enforcers that produce deterministic findings, owned and expiring waivers, and a claim computed from the run and repository-scoped manual evidence.

The honest completeness model is part of the position: every rule the run did not decide is visible, automated findings are candidates rather than proof of semantic correctness, and there is deliberately no health score. ACIMA is not a folder convention, a style linter, an automatic restructuring tool, a hosted dashboard, or a replacement for architectural judgement.

## Operating Context

ACIMA is used in brownfield repositories, during agent-assisted development, and in CI. The normal sequence is read-only assessment, a proposal, explicit authorization of a named scope, approved implementation, then verification and handoff. Assessment must be safe on a repository the user does not own and must change nothing.

The working surfaces are the `acima` CLI, the adoption skill used by AI agents, the normative documentation and rule catalog, and a generated six-page offline HTML outcome report (`index`, `proposal`, `findings`, `files`, `plan`, `evidence`). The HTML report is the primary designed surface; CLI and agent output remain supporting surfaces.

## Capabilities and Constraints

- The standard is a technical preview, currently `1.9.0-draft.1`; the adoption skill is versioned separately and pins the catalog hash.
- The catalog contains 55 rules: 41 automated and 14 that require repository-scoped human evidence. A clean automated run is not full conformance.
- Python and TypeScript reference enforcers cover all 41 automated rules. Go and .NET cover 23. Java is documented but has no enforcer and fails closed.
- Enforcers analyse source and project metadata, not runtime behaviour. They do not prove isolation, type correctness, framework behaviour, tenant isolation, or ownership.
- Findings carry a rule, severity, message, path, line, evidence, and fingerprint. Rule and requirement identifiers are internal navigation and traceability keys, not the explanation.
- Assessment is read-only. Adoption writes require explicit approval of named paths, scope, and level; partial approval is supported.
- Waivers require an owner, reason, fingerprint, expiry, and review date. Broad or fingerprint-less waivers are rejected.
- There is no health score, trend dashboard, hosted service, organizational metrics product, or `acima adopt` command.
- The generated report must not infer a clean result from empty findings or style an incomplete assessment as verified.

## Brand Commitments

The product name is ACIMA, short for Autonomous, Contract-Isolated, Immutable Modular Architecture. Its framing is “Architecture that enforces itself.”

The voice is precise, candid, and consequence-first. It explains what was observed, why it matters, what action is recommended, and how confident the assessment is before citing internal identifiers. It does not use certainty it cannot support, and it does not hide unevaluated work behind a passing result.

The technical-preview limits are binding commitments, phrased constructively: ACIMA makes meaningful enforcement available today while stating exactly which rules and languages remain outside automated proof. Draft status, coverage gaps, manual-evidence requirements, and the absence of a score or hosted service must remain visible rather than being smoothed into marketing language.

## Evidence on Hand

The repository contains the normative standard, the 55-rule catalog, four reference implementations and their violation galleries, the conformance suite, adoption-skill assets, and versioned benchmark evidence. These are the substantive proof available today.

There are no customer testimonials, case studies, press mentions, customer logos, pricing claims, or independent evaluator results in the repository. The published benchmark predates some current fixes and must not be presented as current portfolio-level validation. Hosted CI has not been observed, and independent validation is explicitly incomplete. Future work must not fabricate any of this evidence.

## Accessibility & Inclusion

The offline HTML report targets WCAG 2.2 AA for the content and interaction it provides. It must
remain keyboard-operable, announce a clear heading and table structure, preserve text contrast,
show visible focus, respect reduced-motion and forced-colours preferences, and reflow at 320 CSS
pixels and 200% zoom without page-level horizontal scrolling.

Automated checks cover the structural, contrast-token and stylesheet baseline. Screen-reader
behaviour and real-browser zoom remain manual release checks; the project does not claim that a
passing static test proves every assistive-technology combination works.

## Product Principles

1. **Make the boundary executable.** A rule that cannot fail a build is only advice; prefer enforceable obligations with deterministic evidence.
2. **Report evidence, not a score.** Never compress skipped or unresolved rules into a number that implies more confidence than the run supports.
3. **Preserve human authority.** Assessment may be automatic; adoption, ownership, exceptions, and merges remain explicit human decisions.
4. **Explain before you identify.** Lead with architectural meaning, observed behaviour, consequence, and remedy; keep rule IDs for traceability.
5. **Fail honestly.** An unsupported language, incomplete review, expired evidence, or unreadable run must fail closed and say why.
