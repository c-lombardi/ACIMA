# Verification report

Environment: Windows, Git Bash; `python3` 3.12.16 and `node` 22.23.4 inside a WSL Docker image (`acima-python:3.12`), .NET SDK 8/9/10 on the host, **no Go toolchain**, GitHub Actions not executed.

All commands below were run in this session. Nothing is reported as passing without execution.

## 1. Result summary

| Check | Command | Result |
|---|---|---|
| Internal links + catalog/docs sync | `python3 conformance/test_documentation_integrity.py` | **pass** — 2 tests |
| Documentation contract | `python3 conformance/test_documentation_contract.py` | **pass** — 13 tests |
| Reference implementation (Python) | `python3 conformance/run.py python` | **pass** — clean tree, 23 rules / 33 gallery findings |
| Reference implementation (TypeScript) | `python3 conformance/run.py typescript` | **pass** — clean tree, 23 rules / 33 gallery findings |
| Service-topology profile | `python3 conformance/run.py topology` | **pass** — `ST-1`–`ST-12` on clean and violating fixtures |
| CLI, walkthrough and test modules | `python3 conformance/run.py tools` | **pass** |
| .NET enforcer (native, host SDK) | `dotnet run --project examples/dotnet/tools/Acima.ArchTests -- --root .` | **pass** — `sourceFiles` > 0, zero findings, full execution map |
| Adoption preflight | `python3 skills/acima-adoption/scripts/preflight.py --project . --format text` | **pass** — exit 0, `SKL-002` now matches |

## 2. Every test module

| Module | Baseline | After | Note |
|---|---|---|---|
| `test_adoption_safety` | pass | pass (5) | — |
| `test_claim_model` | pass | pass (12) | — |
| `test_cli` | pass | pass (7) | — |
| `test_documentation_contract` | **fail** (1) | pass (13) | fixed by the re-pin; version now read from the manifest |
| `test_documentation_integrity` | — (new) | pass (2) | new: links + catalog/doc sync |
| `test_dotnet_profile` | skipped (5) | pass, 5 skipped | no .NET inside the container; **not verified** here |
| `test_exclusions` | **error** | pass (1) | was `node` missing, not a defect |
| `test_injected_violation` | **fail** (1) | pass, 2 skipped | proven for python/typescript/dotnet; Go skipped |
| `test_library_profile` | **error** (9) | pass (9) | was `node` missing |
| `test_mode_precedence` | **fail** (1) | pass (6) | cascaded from `SKL-002` |
| `test_preflight_discovery` | **fail** (1) | pass (2) | cascaded from `SKL-002` |
| `test_rule_catalog` | pass (1) | pass (1) | — |
| `test_topology` | pass (7) | pass (7) | — |
| `test_waiver_fingerprints` | pass, 1 skipped | pass, 1 skipped | Go-only waiver case **not verified** |
| `test_walkthrough` | pass (1) | pass (1) | — |

Net: 15/15 modules exit 0; 6 skips remain, all attributable to absent toolchains.

## 3. Status vocabulary for this run

| Status | Meaning here |
|---|---|
| **Passed** | executed in this session with exit 0 |
| **Skipped** | the test decided its own precondition was missing (5 .NET profile tests, 1 Go waiver test, 2 injection proofs) |
| **Unsupported** | Java enforcement — no enforcer exists; a Java run fails closed by design |
| **Not independently verified** | hosted CI, independent review, benchmark rerun, Go profile, .NET library profile inside the container |

## 4. What was not run

- **Full `run.py` (all profiles in one process)** — requires Go and .NET inside the container. Profiles were run individually instead (`python`, `typescript`, `topology`, `tools`), and .NET was verified natively on the host.
- **Go profile** — no toolchain on host or in container. The Go reference implementation and enforcer were not exercised in this session, so **no Go claim is made**.
- **Java** — profile only, unchanged.
- **GitHub Actions** — not executable here; both workflows remain unobserved, as before.
- **Benchmark rerun** — needs network access to clone 15 repositories; the existing evidence is unchanged and still predates the current exclusion/catalog fixes.

## 5. Regression check on the change set

- `git status` shows only the 37 intended paths: 23 deletions (20 `validation/`, 1 ledger, 1 `docs/index.md`, plus the replaced docs index), 5 modifications, 9 additions.
- No rule, severity, level, mode, finding shape, waiver format or enforcer implementation was modified. The enforcement behaviour is therefore unchanged, which is why the gallery counts are identical before and after (33 findings, 23 rules, both Python and TypeScript).
- The only behavioural change in tooling is the addition of one test module to the `tools` profile.

## 6. Honest limits of this report

Passing tests prove the reference enforcers still detect the 23 portable rules on their fixtures, and that the documentation now matches the catalog. They do **not** prove that ACIMA fits any particular application, that the six manual rules were evaluated, or that runtime isolation holds. No independent reviewer has examined this change set.

## Follow-up verification — benchmark evidence split

Re-verified after moving raw benchmark artifacts out of the working tree.

| Check | Command | Result |
|---|---|---|
| Documentation integrity (now covering `benchmark-evidence/`) | `conformance/test_documentation_integrity.py` | **passed** — 2 tests; no broken links, rule index still matches the catalog |
| Profile gate | `conformance/run.py python typescript tools topology` | **passed** — all four profiles conform |
| All conversation modules | every `conformance/test_*.py` | **passed** — 15/15, same 8 skips as before (.NET 5, Go 1, injection 2) |
| Archive recoverability | `git cat-file -e 5c74eb4:benchmark-evidence/<dir>` for each removed directory | **passed** — all present in history |
| File count | `find benchmark-evidence -type f` | 459 → **48** in tree; 459 still present at `5c74eb4` |

One real defect was found by the newly extended check: an executive report in run 02 linked to `../runs/`, which no longer exists in the tree. The link and its description were corrected; the test was not loosened. The `SHA256SUMS` manifests were removed with the artifacts they covered, and the directory README records that, the recovery command, and the fact that the archived set is the checksummed one.

Not verified: restoration was confirmed by reading history (`git cat-file`), not by executing the documented `git checkout` and re-inspecting the restored files.
