# Skill Architecture Understanding

**Status:** IN PROGRESS — internal review only
**Subject:** `skills/acima-adoption` (SKILL.md 1.2.3, catalog pin
`ec2a77d7a2ed4d8c68fd71c32ad47ac486022b2eb541b959a23f1d2b7ea9221b`)
**Question:** Does the skill understand the abstract architecture, not merely the
analyzers?

## Verdict

**PARTIAL.** The skill understands the base contract model, the default no-shared-kernel
rule, fingerprint-scoped waivers, fail-closed assessment, and the difference between a
clean run and a proven run. It does **not** understand the two-mode architecture, and
several reference documents still describe the old pre-fingerprint, pre-any-source
behavior.

The skill is not a reliable interpreter of ACIMA until it can:

1. distinguish base mode from service mode;
2. distinguish full conformance from a partial assessment with six unexecuted rules;
3. stop treating “zero unwaived errors” as sufficient for conformance;
4. reconcile its stale brownfield/waiver guidance with preflight and the catalog.

## What the skill gets right

| Area | Correct understanding | Evidence |
|---|---|---|
| Contract boundary | A module's public surface is a contracts unit; implementation types are private. | `SKILL.md` hard rules, workflow, references 10/20 |
| Default kernel | New contracts own their value types; there is no shared kernel in the default. | `SKILL.md` step 3a; `10-greenfield.md`; `30-adoption-for-newcomers.md` |
| Portable subset | 23 of 29 rules are portable; six need human/framework-specific review. | `SKILL.md` calibration; `manifest.json`; `glossary.md` |
| Fingerprint waivers | A waiver is finding-scoped; a baseline must not hide new findings. | `SKILL.md` hard rule 3; `test_waiver_fingerprints` |
| No bulk renewal | Renewal is a named owner's decision. | `SKILL.md` hard rule 4; 20-brownfield |
| Fail closed | Invalid/truncated/missing output is not zero findings; zero files is not clean. | `SKILL.md` hard rules 5–6; `test_adoption_safety`; `test_library_profile` |
| Unsupported Java | Java profile has no reference implementation; say so, do not fake it. | `SKILL.md` stop conditions; 60-troubleshooting; injection test |
| Library profile | Do not use a library profile to silence a finding; it needs publishable evidence and path-scoped declarations. | `SKILL.md` hard rule 10; `12-library-profile.md` |
| Injection proof | A zero-finding result needs a controlled violation detected in a disposable copy. | `SKILL.md` step 5; `inject_violation.py`; tests |
| No unsolicited rewrite | Do not apply ACIMA without an owner; change the smallest boundary. | `SKILL.md` hard rules 8–9; stop conditions |

## Defects and contradictions

### S-01 — “Conformant” ignores unexecuted required rules

`SKILL.md` says:

> A repository is conformant at a level only when the run artefact shows zero unwaived
> errors at that level on the current commit.

A run with `C003`, `C007`, `G004` (L2) or `A002`/`A004` (L3) marked `executed: false` can
show zero unwaived errors and still not have evaluated required rules. The skill then says
elsewhere that `execution` must name every rule and every false must have a reason, but it
does not say the presence of a required false **prevents** conformance. This is a C1/C5
defect: the agent can produce a confident but false conformance claim.

**Required correction:** Add a hard rule: if any rule required by the declared level is
`executed:false`, the result is **PARTIAL ASSESSMENT**, never FULL CONFORMANCE. Name the
unexecuted rules and the manual evidence needed. This aligns with P8.1 and AD-01/AD-11.

### S-02 — Brownfield threshold is stale

`references/00-preflight.md` says brownfield is “no config, 10 or more source files” and
describes a 9-file deployed service as brownfield “in spirit.” `SKILL.md` and the
implementation classify **any existing source file** as brownfield. `references/glossary.md`
says greenfield is “fewer than ten source files.” These are three different definitions.

**Observed:** a temp repository with one `legacy.py` is classified `brownfield` by
`preflight.py`, and `test_waiver_fingerprints` pins that behavior. The references are
wrong.

**Required correction:** Make all references say “no config and no source” = greenfield;
“no config and at least one source” = brownfield. Remove the numeric threshold and the
“in spirit” exception. The situation can still be discussed, but the classification must
match the tool.

### S-03 — Waiver grouping is stale and contradicts the fingerprint rule

`00-preflight.md` says the writer “groups findings by the unit ... one waiver per
`(rule, unit)` pair.” `20-brownfield.md` says “groups by `(rule, unit)`” and “One waiver per
rule per unit, not per line.” `60-troubleshooting.md` says “Write waivers per `(rule, unit)`.”

The implementation (`waiver_stub`) emits one waiver per **finding fingerprint**, and
`test_waiver_fingerprints` asserts two findings in one unit produce two waivers. `SKILL.md`
hard rule 3 requires a finding fingerprint.

**Required correction:** All references must say “one waiver per exact finding fingerprint;
scope identifies the unit/path, but scope alone is not sufficient.” The “not per line”
advice should be rephrased as “the fingerprint is stable across line moves,” not as
permission to group by unit.

### S-04 — “Six fields” omits the fingerprint

`00-preflight.md` says `GOV-003` checks “waivers have all six fields.” The listed fields in
`WAIVER_FIELDS` are rule, scope, owner, reason, expires, reviewedOn — six, without
fingerprint. `SKILL.md` hard rule 3 requires **owner, reason, scope, finding fingerprint,
expiry and review date** — six if you count scope/fingerprint separately, seven if not.
The template includes fingerprint. Preflight separately warns when active waivers have no
fingerprint.

**Required correction:** Define one canonical field list: rule, scope, fingerprint, owner,
reason, expires, reviewedOn (and ticket if required by the standard). Update the preflight
check text and the skill reference. A waiver without a fingerprint must be `G001`, not a
“structurally valid but incomplete” artifact.

### S-05 — The skill does not understand base vs service mode

`SKILL.md` describes ACIMA as “a modular monolith” in the newcomer reference and says
services are “an option later.” It contains no mention of `acima.topology.json`, P10–P13,
layer contracts, service naming, ST-1–ST-12, or the service profile's per-layer contracts.
A `service-topology` repository is therefore outside the skill's working model.

This contradicts the standard, which calls the service profile the default for new systems.
It also means the skill cannot answer the basic question “which contracts unit should this
service have?” without applying the base P2.1 rule, which is wrong in service mode.

**Required correction:** Add a mode-classification step before unit mapping, a service
profile playbook (or an explicit `NOT SUPPORTED` stop), and a statement that base P2.1/P3.5
are superseded in service mode. Do not let the agent apply a base rule to a service profile.

### S-06 — Outcome definitions claim more than the enforcers can show

`50-outcomes.md` says:

- L2 = “contracts are frozen data with no behaviour ... and the reviewed API baseline
  matches”;
- L3 = “each module owns its persistence and configuration ... consumers pin contracts
  versions. Evidence: L3 run + schema ownership map.”

But C003 (no behaviour), G004 (API baseline), A002 (configuration) and A004 (version
pinning) are **not executed**. An L2/L3 run cannot show those properties. The document's
definition of done is stronger than the tool's actual evidence.

**Required correction:** Mark those items as manual evidence and require the artifact;
or define L2/L3 as portable-subset levels. Do not say “L3 run” proves configuration and
version ownership.

### S-07 — The self-certification example is arithmetically inconsistent

`docs/standard/08-conformance.md` §8.5 showed, before the 1.2.2 correction:

> Rules executed | 24 of 24 required at L2

The L2 set is D (9) + L (4) + G (5) + C (7) = 25 rules, not 24. If warnings are excluded,
the count changes again but is not 24. The example also does not name the six unexecuted
rules. This is a product/documentation defect that the skill repeats by telling users to
use the template verbatim.

**Required correction:** Compute the count from the catalog; show the actual executed /
manual split; remove the fixed “24 of 24.” A test now derives the L2 counts from
`rules.json` and `coverage.json`.

### S-08 — Module and implementation-unit definitions are too narrow

`references/glossary.md` says a module has “one contracts unit and one implementation
unit.” The base standard allows one or more implementation units (§2.2), and the service
profile has layers with separate contracts. This can cause an agent to merge legitimate
implementation units or split a service incorrectly.

**Required correction:** “One contracts surface per module in base mode; one or more
implementation units. In service mode, one per outward-facing layer.” Add the mode
qualification.

### S-09 — Greenfield “declare L3 immediately” is unsafe as stated

`10-greenfield.md` says “Declare L3 immediately. There is no legacy, so there is no reason
to start at L1.” The intent (don't defer the gate) is good, but L3 includes A002/A004 and
the six-rule gap. A day-zero skeleton has no persistence/configuration to evaluate, so a
green L3 run is mostly vacuous. The skill should require the gate and the full shape, not
claim a level before the evidence exists.

**Required correction:** “Build the full shape and wire the gate immediately; declare L1
until the contracts and implementation exist, then ratchet to L2/L3 with manual evidence
for the unexecuted rules.” This is more honest and still prevents the “rules are optional”
failure.

### S-10 — The skill has no service or library adoption playbook

The only profile mention is hard rule 10 (library profiles) and a stop condition. There is
no procedure to:

- classify application vs library vs service;
- discover publishable evidence and public API paths;
- write a library profile declaration;
- discover a service's layers and inter-service contracts;
- produce/validate `acima.topology.json`;
- handle a service with vendors, UI workflow, or coverage reports.

This is a C2/C4 gap, not a documentation nicety. The skill cannot currently adopt the
standard's **default** architecture for new systems.

### S-11 — Stale JSON example version

`00-preflight.md` shows a JSON example with `"version": "1.0.0"` and
`"standard": "1.0.0-draft.1"` while the manifest is skill 1.2.1. The example is not marked
as illustrative. Minor, but it undermines the calibration story.

**Disposition:** corrected in 1.2.2 — the example now reports `"version": "1.2.2"` and
matches `manifest.json`.

### S-12 — The skill does not separate assessment from implementation

The same agent is instructed to inspect, classify, plan, edit, and verify. Hard rules
reduce risk, but there is no role separation or second review. The mandate asks for
independent verification; the skill cannot provide it. This is a process limitation, not a
text bug, but it must be disclosed in every adoption report.

## Remediation in 1.2.2

| Finding | Disposition |
|---|---|
| S-01 conformance overclaim | **Corrected** — hard rule 11 and §8.6 require `PARTIAL ASSESSMENT` when a required rule is `executed:false`. |
| S-02 brownfield threshold | **Corrected** — all references use “no config + any source“; the doc test pins it. |
| S-03 waiver grouping | **Corrected** — references say one waiver per finding fingerprint; the doc test pins it. |
| S-04 six fields | **Corrected** — `fingerprint` added to `WAIVER_FIELDS`; one canonical field list documented. |
| S-05 / S-10 service mode | **Partially corrected** — mode selector and explicit `NOT SUPPORTED` stop added; no service workflow exists. |
| S-06 outcome definitions | **Corrected** — L2/L3 manual evidence is named in `50-outcomes.md`. |
| S-07 self-certification count | **Corrected** — template derives `<executed> of <required>`; the doc test pins it. |
| S-08 module definition | **Corrected** — glossary allows one or more implementation units in base mode. |
| S-11 stale JSON version | **Corrected** — the example reports 1.2.2. |
| S-09 greenfield L3 | **Open** — the playbook still recommends declaring L3 immediately. |
| S-12 same-agent verification | **Open / process** — no independent verifier. |

## C1 disposition

| Capability | Status |
|---|---|
| Understands base P1–P9 | PARTIAL — strong on ownership/contracts, weak on conformance claim |
| Understands P10–P13 | NOT SUPPORTED — no working model or playbook |
| Understands library profile | PARTIAL — one hard rule, no workflow |
| Distinguishes normative vs advisory | PARTIAL — conflates “no unwaived errors” with full conformance |
| Distinguishes observed vs inferred | PARTIAL — labels drafts heuristic, but no general evidence format |
| Identifies human-judgment decisions | PARTIAL — stop conditions exist; six manual rules not tracked |
| Avoids inventing requirements | PARTIAL — mostly cites catalog, but stale references assert wrong constraints |

**C1 score: 2/4** — specified and partly correct, but the conformance and mode
misunderstandings are material.
