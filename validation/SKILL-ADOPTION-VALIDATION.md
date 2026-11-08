# Skill Adoption Validation

**Status:** IN PROGRESS — internal review only
**Scope:** C3 architecture mapping, C4 adoption planning, C5 implementation behavior.
**Evidence:** skill text, preflight, assets, tests, controlled fixtures. No production
repository was adopted.

## Verdict

**PARTIAL — a good base-mode adoption checklist, not a validated adoption capability.**

The skill is strongest at preventing the classic failures: rewriting the target, starting
with persistence, unowned waivers, zero-source green lights, and claiming conformance
without a run. It is weakest at discovery, service/library modes, and closing the loop with
real implementation evidence.

## C3 — Architecture mapping

| Requirement | Status | Assessment |
|---|---|---|
| Discover actual structure | PARTIAL | Directory/project heuristics; no dependency graph before config |
| Identify existing boundaries | PARTIAL | Candidate units only; no ownership/data evidence |
| Map boundaries to ACIMA concepts | PARTIAL | Base module mapping is explained; service/layer mapping absent |
| Identify incompatible structures | PARTIAL | Some warnings; no explicit incompatibility report |
| Distinguish valid choices from violations | PARTIAL | Library profile only; no general classification workflow |
| Identify where ACIMA cannot apply | PARTIAL | Java stop; no tenancy/full-stack/platform limits |
| Propose adoption approach | PARTIAL | Brownfield ratchet; no service/library playbook |
| Explain assumptions/uncertainty | PARTIAL | Draft is labeled heuristic; no per-unit evidence/confidence |
| Request human confirmation | PARTIAL | Owner stop condition; no mandatory confirmation of unit map |

**Critical gap: service mode.** The skill never mentions `acima.topology.json`, P10–P13, or
ST-1–ST-12. A service repository cannot be mapped to the standard's default architecture.
The agent may apply base P2.1 (one contracts unit) to a service that requires per-layer
contracts, or invent a service layout without the profile manifest.

**Critical gap: library mode.** The skill has one hard rule and a link, but no procedure to
discover publishability, declare `publicApi`, declare intentional adapters, or validate that
undeclared edges still fail. It cannot adopt the profile it warns about.

**Critical gap: no observed-vs-inferred format.** The preflight returns `proposedUnits`, but
the skill does not require the agent to separate:

- observed facts (manifests, imports, public exports);
- inferred boundaries (directory clusters);
- human decisions (ownership, product responsibility);
- unknowns (deployment, tenancy, intent).

This matters because the mandate explicitly requires that distinction.

## C4 — Adoption planning

The `assets/adoption-plan.md` template is a genuine strength: context, unit map, phases,
first slice, metrics, risks, cadence, exit criteria. It requires names and dates, not `TBD`.
The brownfield playbook has a coherent ratchet and a sensible migration order.

| Planning capability | Status | Notes |
|---|---|---|
| Greenfield plan | PARTIAL | Fixed day-zero sequence; overclaims L3 immediately; no service profile |
| Brownfield plan | PARTIAL | Good ratchet; guidance corrected in 1.2.2; 50k walk cap undisclosed |
| Existing debt | PARTIAL | Baseline/waiver model; no effort estimate beyond size bands |
| Incremental enforcement | PASS | L1 ratchet, gate on new findings |
| Baseline establishment | PARTIAL | Waiver writer is per fingerprint; docs corrected in 1.2.2 |
| Exception governance | PARTIAL | Owner/expiry; P9.5 not representable |
| CI integration | PARTIAL | Command examples; hosted CI unobserved; exit-code guidance good |
| Team onboarding | PASS (content) | Newcomer reference is strong, though “modular monolith” framing is narrow |
| AI-assisted workflow | PARTIAL | Instructions are clear; no role separation or independent verifier |
| Proportionate plan | PARTIAL | Size bands; 16-unit cap removed in 1.2.2; review remains manual |
| Avoid unnecessary restructuring | PASS (intent) | “Never rewrite” and smallest-boundary rules |
| Preserve legitimate architecture | PARTIAL | Library profile covers only two languages; no service profile |

**Planning defects.**

1. The plan template asks for a “Language profile” but not an ACIMA **mode**. A service
   plan and a base-module plan look the same on paper.
2. The plan has no row for manual evidence for the six non-executed rules. A plan can claim
   L2/L3 without assigning C003/C007/G004/A002/A004.
3. The plan has no row for runtime persistence grants, release independence, or public API
   profile evidence.
4. The “first slice” guidance is base-module-centric; it does not cover layer contracts,
   inter-service contracts, or vendor seams.
5. The plan does not require a clean working copy/branch before edits. The injection prover
   uses a copy, but implementation changes are not isolated by the skill.

## C5 — Implementation behavior

The skill is instruction-only; it does not implement a patch engine. Its behavior depends
on the host agent. The following are evaluated as instructions, not as executed code.

| Requirement | Status | Assessment |
|---|---|---|
| Establish ACIMA boundaries | PARTIAL | Base mode yes; service/library no |
| Create/modify configuration | PARTIAL | `--write-draft`/`--write-waivers`; no service manifest; no schema validation loop |
| Introduce enforcement | PASS (base) | Enforcer commands and CI guidance; no Java |
| Resolve genuine violations | PARTIAL | Walkthrough and examples; no automated fix; no target build/test |
| Preserve legitimate architecture | PARTIAL | Library profile only TS/.NET; no service profile |
| Avoid unauthorized restructuring | PASS | Hard rules 8–9; owner stop |
| Explain proposed changes | PARTIAL | Templates and finding messages; no patch preview/approval gate |
| Validate implementation | PARTIAL | Enforcer run + prover; no build/test/runtime verification |
| Maintain after adoption | PARTIAL | CI gate only; no post-merge architecture review |
| Handle multiple teams | PARTIAL | Owner/named team concept; no org mapping evidence |
| Clean up temporary artifacts | PARTIAL | Prover copies; no explicit cleanup requirement |
| Handle uncertainty | PARTIAL | Stop conditions; no structured unknown list |

**Implementation hazards.**

- **No explicit “do not edit before the plan is approved” gate.** The workflow says plan
  before code, but an agent can run draft/waiver writes and then edit. A hard checkpoint
  would be safer.
- **No target test/build verification.** The skill verifies the architecture enforcer, not
  that the repository still builds or its tests pass. An architecture-clean change can break
  the product.
- **No diff budget.** “Smallest boundary” is a principle, not a limit. The skill should
  require a changed-file/line budget and a rollback plan for the first slice.
- **No service extraction safety.** P7/P10 claims extraction is cheap; the skill has no
  checklist for data migration, deployment, or runtime cutover.
- **No independent verifier.** The same agent plans, edits, and verifies. The mandate's
  separation-of-concerns requirement is not met.

## C3–C5 findings

| ID | Finding | Domain | Severity |
|---|---|---|---|
| S-13 | No service-topology adoption path | Adoption (C3/C4) | Critical |
| S-14 | No library-profile adoption path | Adoption (C3/C4) | High |
| S-15 | Zero-unit repository is not a blocker — fixed in 1.2.2 | Discovery/Adoption | Critical |
| S-16 | 16-unit proposal cap hides modules — fixed in 1.2.2 | Discovery/Adoption | High |
| S-17 | No observed/inferred/unknown evidence format | Mapping (C3) | High |
| S-18 | No manual-evidence plan for six rules | Planning (C4) | High |
| S-19 | No target build/test verification | Implementation (C5) | High |
| S-20 | No clean-copy/branch or diff-budget gate | Implementation (C5) | Medium |
| S-21 | No independent verifier | Process (C5) | High |
| S-22 | Greenfield L3 claim is premature | Planning (C4) | Medium |
| S-23 | Plan template lacks mode/runtime/manual evidence | Planning (C4) | High |

## C5 disposition

**PARTIAL / NOT TESTED.** The instructions are cautious and generally preserve the target,
but no real implementation was performed. “Can execute an assessment” is not “can adopt
ACIMA.” The skill has not demonstrated a merged boundary change, a green gate, or preserved
architecture in a real repository.
