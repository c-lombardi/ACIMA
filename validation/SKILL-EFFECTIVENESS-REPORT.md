# Skill Effectiveness Report

**Status:** IN PROGRESS — internal review only
**Subject:** `skills/acima-adoption` (1.2.3) as a product capability
**Question:** Can an independent engineer or AI agent understand, map, adopt, and maintain
ACIMA with this skill?

## 1. Verdict

**PARTIAL — useful for base-mode assessment, not validated for real-world adoption.**

The skill has strong safety instincts: it is read-only by default, requires an owner,
refuses to call zero files clean, demands fingerprint-scoped waivers, proves zero findings
with injection, and tells the agent to stop for Java and for library profiles without
evidence. Its brownfield ratchet and newcomer material are better than most architecture
guides.

It does not yet demonstrate adoption. It has no service-topology workflow, no library
profile workflow beyond a warning, no real application pilot and no independent verifier.
The benchmark's 5.3/10 skill score is author-adjudicated and measures benchmark execution,
not adoption.

**Revalidation (1.2.2):** the stale references identified in the audit were corrected and
pinned by `test_documentation_contract.py`; the zero-unit and 16-unit discovery failures are
fixed and pinned by `test_preflight_discovery.py`. These close documentation and discovery
defects, not the missing adoption evidence.

## 2. Evidence base

| Evidence | What it shows | Limit |
|---|---|---|
| `SKILL.md` 1.2.3 + `manifest.json` | Calibration, hard rules, workflow, mode selector | Self-description |
| `preflight.py` + controlled fixtures | Classification, unit proposals, zero-unit/truncation behavior | No real repo adoption |
| `test_adoption_safety.py` | Fail-closed assessment validation | Synthetic payloads |
| `test_waiver_fingerprints.py` | Exact waivers, brownfield, baseline uniqueness | Fixtures |
| `test_injected_violation.py` | L001/D001 proof, Java fail-closed | Two rules, synthetic fixture |
| `test_library_profile.py` | TS library public API/adapters | TS only |
| `test_dotnet_profile.py` | .NET package metadata/public API | .NET only |
| `test_preflight_discovery.py` | Zero-unit blocker; 18-module completeness | Controlled fixtures |
| `test_documentation_contract.py` | Rule counts; brownfield; fingerprint waivers; partial-assessment template | Documentation only |
| `benchmark-evidence/rw-2026-11-08-02` | 12 supported repos, 8/9 zero-finding proofs, 45.2% yield, 5.3/10 skill | Author-adjudicated; libraries, not application adoption |

## 3. C7 measurements

The mandate asks for discovery accuracy, boundary accuracy, principle interpretation,
mapping, finding interpretation, plan quality, unnecessary changes, human intervention,
time to assessment/baseline/enforcement, adoption rate, and preservation during later
development. Most cannot be measured with the current evidence.

| Measurement | Status | Evidence |
|---|---|---|
| Architecture discovery accuracy | PARTIAL / NOT MEASURED | Language detection works; zero-unit and 16-cap failures fixed in 1.2.2; still no ground-truth application comparison |
| Boundary identification accuracy | NOT MEASURED | No application repo with a confirmed unit map |
| Principle interpretation accuracy | PARTIAL | Base principles mostly correct; mode/conformance misreadings |
| Mapping accuracy | NOT MEASURED | No service/library adoption; no independent map |
| Finding interpretation accuracy | PARTIAL | Benchmark triage; 30 valid choices unclassified, 1 false positive |
| Adoption-plan quality | PARTIAL | Template is strong; no completed plan |
| Unnecessary changes proposed | NOT MEASURED | No implementation pilot; 16-unit cap risks over-splitting |
| Human intervention required | PARTIAL | Owner/stop conditions defined; no measured count |
| Time to first assessment | OBSERVED (fixture) | Seconds on small fixtures; no real repo measure |
| Time to baseline | NOT MEASURED | Requires config + enforcer + waivers; no pilot |
| Time to enforcement | NOT MEASURED | No CI gate merged |
| Successful adoption rate | NOT TESTED | Zero real adoptions |
| Preservation during later development | NOT TESTED | No longitudinal run |

## 4. What works

1. **Read-only preflight.** The default does not modify the target.
2. **Fail-closed assessment.** Zero source, missing execution map, invalid JSON, unexecuted
   rule without reason are rejected.
3. **Injection proof.** A zero-finding result is not accepted without a detected controlled
   violation (L001/D001).
4. **Exact waivers.** A baseline cannot hide new findings in the same unit.
5. **No bulk renewal.** Correct governance instinct.
6. **Brownfield ratchet.** L1, baseline, gate, reduce; no big-bang rewrite.
7. **Migration order.** Contracts/cycles before persistence; avoids the classic failure.
8. **Newcomer material.** Plain-language, pain-first, misconception table; useful for teams.
9. **Plan template.** Names, dates, metrics, risks, exit criteria.
10. **Explicit stop conditions.** Java, no owner, legitimate design repeated, library
    profile without evidence.

## 5. What fails or remains unproven

| ID | Finding | Evidence | Impact |
|---|---|---|---|
| K-01 | Conformance can be claimed with six required rules unexecuted | `SKILL.md` definition; `coverage.json` | False assurance |
| K-02 | Brownfield/waiver guidance contradicts code | `00-preflight`, `20-brownfield`, `60-troubleshooting`, `glossary` | Wrong baseline; agent groups waivers |
| K-03 | No service-topology workflow | No `acima.topology.json`/P10–P13 mention | Cannot adopt the default architecture |
| K-04 | No library-profile workflow | Only hard rule 10/ link | Cannot use profile correctly |
| K-05 | Zero-unit repo exits 0 | Controlled fixture | False readiness |
| K-06 | 16-unit cap truncates | Controlled fixture (18 modules) | Hidden contexts |
| K-07 | No docs/ADR reconciliation | No scan | Stated vs actual boundaries unresolved |
| K-08 | No manual evidence plan | Six rules unexecuted | L2/L3 plan incomplete |
| K-09 | No target build/test verification | Workflow stops at enforcer | Architecture-clean but broken product |
| K-10 | No diff budget/approval gate | “Smallest boundary” only | Over-editing risk |
| K-11 | No independent verifier | Same agent | Self-confirmation |
| K-12 | Greenfield L3 immediate | `10-greenfield.md` | Vacuous/overclaimed level |
| K-13 | No real application pilot | Benchmark is libraries | Adoption effectiveness unknown |

## 6. Skill scorecard

Rubric: 0 absent, 1 asserted, 2 specified/partial, 3 implemented and tested, 4
independently validated in real use.

| Dimension | Score | Rationale |
|---|---:|---|
| Architecture understanding | 2 | Strong base; mode/conformance errors |
| Repository discovery | 1 | Heuristics; zero-unit and truncation failures |
| Boundary identification | 1 | Candidate directories only; no ground truth |
| Contextual interpretation | 2 | Library profile exists in two languages; no service mode |
| Adoption planning | 2 | Strong template; missing mode/manual/runtime evidence |
| Implementation quality | 1 | No pilot; no build/test verification |
| Brownfield practicality | 2 | Good ratchet; stale waiver docs; large-repo cap |
| Human oversight | 3 | Owner/stop rules are clear and conservative |
| Reproducibility | 2 | Fixtures repeatable; no hosted CI/pilot |
| Developer experience | 2 | Clear prose; stale contradictions and multiple layers |

**Do not average these into one score.** The high human-oversight dimension does not offset
the low discovery/implementation dimensions.

## 7. Benchmark comparison

The `rw-2026-11-08-02` skill scorecard is 5.3/10, up from 4.6. It rewards better
verification and repeatability. It also records the same structural limits: hand-built unit
maps, tRPC scope repair, FluentValidation profile rejection, no production adoption, no
independent review. The benchmark is a **benchmark-local judgement**, not a certification
and not an adoption measurement. It should not be used as the skill's release gate.

## 8. Release disposition

| Capability | Status |
|---|---|
| Base-mode preflight/assessment | PARTIAL |
| Base-mode brownfield adoption | PARTIAL |
| Service-topology adoption | NOT SUPPORTED |
| Library-profile adoption (TS/.NET) | PARTIAL |
| Library-profile adoption (Python/Go) | NOT SUPPORTED |
| Java adoption | BLOCKED |
| Independent real-world adoption | NOT TESTED |
| Skill release gate | **FAIL / NOT READY** |

## 9. Required next steps

1. Fix K-01/K-02/K-12 text before any further adoption use.
2. Make zero-unit and truncation blockers (K-05/K-06).
3. Build a base-mode application pilot with a named owner and a real merged slice; measure
   time to assessment, baseline, gate, and the human interventions.
4. Add the service-topology path only when a non-.NET fixture exists; otherwise stop.
5. Add a library-profile playbook for TS/.NET and an explicit unsupported stop for
   Python/Go.
6. Require target build/tests, a diff budget, and an independent verification pass.
7. Record the pilot in a new evidence directory; do not reuse the benchmark as adoption
   proof.

## 2026-11-08 revalidation (skill 1.2.4)

- The skill now names the executable claim gate and manual evidence file in Step 5.
- The catalog pin is updated for the 23 automated / 6 manual partition.
- K-01 is resolved at the instruction/gate level: a required `executed: false` rule makes
  the result partial unless accepted manual evidence exists.
- K-02 remains partially open (the broader adoption references are unchanged in this pass).
- K-03, K-04, K-09, K-11, K-13 remain open: no service workflow, no target build/test
  verification, no independent verifier, and no real application pilot.
- Local verification: 81 tests and conformance exit 0. This is not an adoption result.
