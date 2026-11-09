# Artifact requirements matrix

This matrix is the source for proposal statuses. It describes the current implementation, not the
template inventory. “Required” means required for the stated objective; it never means required for
an assessment.

## Individual artifacts

| Artifact | Purpose in plain language | Status | Depends on | What it proves | What it does not prove |
|---|---|---|---|---|---|
| `acima.config.json` | declares which code is a module, which role it has, and the level | **Required** for unit-aware assessment, enforcement or baseline | reviewed map | boundaries are declared | that code follows them |
| `.acima/waivers.json` | records exceptions with owner, scope, fingerprint and expiry | **Conditional**: findings remain or a gate is used; an adopted gate needs an empty file if clean | config and measured run | exceptions are governed | that no violation exists |
| `.acima/baseline.json` | snapshots measured fingerprints at adoption | **Conditional**: brownfield gating/ratcheting; optional when starting clean | valid run | what was known at that commit | conformance or absence of defects |
| Enforcement tooling | makes rules executable locally or in CI | **Required** for automated enforcement; **not applicable** to read-only assessment | config and supported enforcer | checks can run | that they passed or covered every rule |
| CI workflow | runs the gate on pull requests | **Conditional**: only when integration blocking is approved | tooling, config, exception policy | CI is configured | that CI executed, or blocked a real violation |
| `.acima/manual-evidence.json` | records human/native evidence for non-portable required rules | **Conditional** for a full claim at a level with such rules | named reviewer, method and artifact | a review happened | automated coverage |
| Adoption plan | sequence, owners, boundaries and metrics | **Optional** | named people and approved scope | coordination intent | implementation |
| Communication plan | audiences, messages and responsibilities | **Optional** | approved adoption and stakeholders | coordination intent | adoption |
| `docs/acima/STATUS.md` | current phase, findings, next action and blockers | **Conditional**: useful once an adopted repo has state | approved adoption and a run | recorded programme state | that the state is current without a run |
| Adoption summary | reader-facing interpretation of evidence | **Optional**; outside target by default, inside only with approval | run or manual assessment | interpretation | new evidence |
| `.acima/triage.json` | defects vs review items vs detector artifacts | **Optional** | run and human review | reviewed classification | suppression; it never removes a finding |
| Source/build changes | correct a boundary or wire a gate | **Conditional and separately approved** | approved slice | the change itself | that the gate is green |

The prior skill treated plan, communication plan, summary and status dashboard as defaults. They are
not defaults now; they are proposed when the objective or coordination need justifies them.

## Dependencies

```text
reviewed unit map
      ↓
measured run
      ├── baseline (optional)
      └── waivers (if findings remain)
              ↓
        gate policy
              ↓
         CI workflow
              ↓
 manual evidence (full claim only)
```

- A baseline without a config has no meaning.
- A waiver file without a measured fingerprint is broad and is rejected by `G001` rules in spirit and
  by the preflight's fingerprint check.
- CI without an enforcer command only creates an appearance of enforcement.
- A full claim without manual evidence for unexecuted required rules is partial.
- Plans do not depend on any artifact; they depend on people and decisions.

## Recommended sets by objective

| Objective | Create | Do not create | What the user gets |
|---|---|---|---|
| Fit assessment | nothing in the target; report outside | config, baseline, waivers, CI, plans | a recommendation and limits |
| Pilot one module | config for that scope, local enforcer | repository-wide CI, plans | local measurement |
| Local enforcement | config, enforcer invocation, waivers if needed | CI, dashboard, plans | developers can check before merging |
| Brownfield gate | config, run artifact, baseline/waivers, CI | adoption narrative unless needed | new findings can be blocked |
| Full level claim | gate set + manual evidence | an unsupported claim | a claim class backed by evidence |
| Multi-team programme | gate set + adoption/communication plans | extra ACIMA metadata | coordination across owners |

## Partial approval matrix

| Approved subset | Enabled | Not enabled |
|---|---|---|
| Config only | inspection, first measurement | blocking, ratcheting, level claim |
| Config + local enforcer | local checks | merge prevention, CI observation |
| Config + baseline, no CI | frozen measurement | automatic protection |
| Config + CI, no baseline | blocking on the declared policy | known-vs-new distinction unless the gate supports it |
| Config + waivers, no manual evidence | governed exceptions | full claim at levels with non-portable rules |
| Plans only | coordination document | any technical enforcement |
| One module | pilot boundary | repository-wide coverage or conformance |

## Verification limits

Artifacts are claims about intent and configuration, not about runtime behavior:

- a config can declare a map that hides a dependency;
- a baseline can freeze a detector artifact as debt;
- a waiver can hide a new finding if its fingerprint is imprecise;
- a workflow file can be present but never executed;
- a green run can be a false pass if the enforcer discovered no units;
- a manual evidence file can be stale or overbroad.

The skill must report these limits, not turn artifact existence into a score.
