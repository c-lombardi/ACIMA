# Consent workflow review

## The problem

The prior adoption skill treated invocation as intent to adopt. It routed “adopt” directly to
preflight, copied an adoption plan and a communication plan into the target, wrote a draft
`acima.config.json` and waivers, and defined success partly by those files existing. A developer who
only wanted a fit assessment could receive a governance change.

The reporting revision made the issue sharper: it required `docs/acima/adoption-summary.md` after
*every* assessment, which is a write. A read-only result must be allowed to stay read-only.

**Analysis is not authorization to adopt.** The redesign adds a consent gate without relaxing any
rule, level, waiver, execution-map or evidence requirement.

## The model

| Phase | Default? | Target writes | Result |
|---|---|---|---|
| 1. Assessment | yes | none | verdict, findings, limits, candidate map |
| 2. Proposal | follows adoption intent | none | exact artifact list, decisions, costs, one approval question |
| 3. Approved adoption | only after explicit yes | approved paths only | configuration and the approved subset |
| 4. Verification and handoff | after Phase 3 | none beyond approved scope | evidence, capabilities and limitations |

`preflight --write-draft` and `--write-waivers` remain the only preflight writers. They are now
described as adoption acts requiring approval, not as steps in an assessment. A draft config is
heuristic and is never presented as a confirmed architecture.

## Consent boundary

No approval: inspect, read the standard, run `assess`/`inspect`/`analyze`/`report`/`claim`/`status`,
calibrate with preflight, prove detection with disposable fixtures, prepare a report outside the
target, and prepare the proposal.

Explicit approval: `acima.config.json`, `.acima/`, baselines, waivers, plans, tooling, CI, build
configuration, application source, existing documentation, and new or changed architectural
boundaries. Merge, publish and release need a separate decision.

Request wording is mapped explicitly in `references/15-consent-and-scope.md`; “adopt ACIMA” starts
assessment and proposal, and “do the whole thing” does not pre-approve files the owner has not seen.

## Artifact policy

Artifacts are classified as **Required**, **Conditional**, **Optional** or **Not applicable** against
the selected objective. The full matrix is in
[`artifact-requirements-matrix.md`](artifact-requirements-matrix.md).

The important changes:

- assessment needs no repository artifacts;
- a local enforcement trial needs a config and a runner, not CI, plans or a dashboard;
- brownfield baseline/waivers are conditional on keeping existing findings and gating new ones;
- plans and communication documents are optional and are never copied by default;
- a summary may be delivered in the response or outside the target;
- no artifact is evidence of conformance.

## Module mapping

Heuristic discovery remains useful, but it is labelled. The skill now distinguishes discovered
projects, proposed modules, confirmed modules, supporting libraries, shared kernels, hosts, test
projects, tooling projects and uncertain roles, with evidence and confidence. Low-confidence or
conflicting classifications stay in the proposal until the owner decides. A shared kernel is an
architectural decision, not a rename that makes a dependency legal.

## Technical rigor preserved

The change does not alter the catalog, rule severity, enforcer behavior, waiver fingerprint rules,
execution-map requirements, controlled-violation proof, CI verification language or conformance
claims. A limited adoption is allowed; an inaccurate description of it is not. The skill still says a
config is not conformance, a baseline is not conformance, a green gate is not proof that every
finding is a defect, configured CI is not observed CI, and automation does not replace human
judgement.

## Files changed

| File | Change |
|---|---|
| `skills/acima-adoption/SKILL.md` | four phases, consent table, proposal-first routing, gated steps, mapping confidence, stop conditions |
| `skills/acima-adoption/references/15-consent-and-scope.md` | full boundary, artifact statuses, dependencies, partial approval, mapping classes, implementation discipline |
| `skills/acima-adoption/assets/adoption-proposal.md` | plain-language proposal and exact approval question |
| `skills/acima-adoption/references/10-greenfield.md` | consent gate; no scaffold before approval |
| `skills/acima-adoption/references/20-brownfield.md` | config, baseline, waivers and gate are approved subsets |
| `docs/start/brownfield.md` | public adoption flow now has proposal/consent before files |
| `docs/commands.md` | write flags and target summaries require approval |
| `docs/guides/ai-agents.md` | assessment read-only; no writes outside approved scope |
| `skills/acima-adoption/manifest.json`, `docs/product-contract.md`, `references/00-preflight.md` | version 1.8.0 and new files |
| `conformance/test_consent_workflow.py`, `conformance/run.py` | disposable-fixture consent proofs |

## Boundaries of this review

This is a behavioral specification plus tool-level write tests. It does not execute an LLM agent
conversation, so it cannot prove that every future agent will ask rather than write. It proves that
the instructions are explicit and that the scripts do not write unless asked. The validation
document records this limitation rather than claiming an end-to-end conversational test.
