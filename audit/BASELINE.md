# Baseline — ACIMA repository state before simplification

Recorded: 2026-11-08. Branch `main`, working tree clean at the time of measurement (no uncommitted user work existed; nothing was stashed).

## 1. What the repository is

ACIMA is an architectural standard for contract-isolated modules, delivered in three layers:

| Layer | Artifact | Authority |
|---|---|---|
| Standard | `docs/standard/`, `docs/rules/`, `tools/acima-spec/rules.json` | normative |
| Enforcement | `examples/<language>/tools/*`, `conformance/`, `.github/workflows/` | must not redefine the standard |
| Adoption | `skills/acima-adoption/` (`SKILL.md` + references + scripts) | guidance, not conformance authority |

## 2. Inventory

| Area | Files | Lines | Notes |
|---|---:|---:|---|
| `benchmark-evidence/` | 459 | 17,085 | three dated immutable runs; dominated by raw logs/JSON |
| `examples/` | 186 | 8,431 | four reference implementations + violation galleries |
| `docs/` | 37 | 7,639 | standard, rules, languages, guides, status, product contract |
| `conformance/` | 30 | 3,331 | runner, claim model, topology profile, 14 test modules, fixtures |
| `validation/` | 20 | 3,633 | dated release/audit reports and backlog |
| `skills/` | 18 | 3,205 | one skill: `SKILL.md`, 8 references, 5 assets, 2 scripts |
| `tools/` | 3 | 832 | `acima.py` CLI, walkthrough, `rules.json` |
| `.github/` | 2 | 105 | two workflows |

Total tracked files: 757. The repository is small in code and large in prose: ~34k non-evidence lines, of which documentation and reports are ~14.6k.

## 3. Architecture as implemented

- 13 principles in `docs/standard/01-principles.md`: P1–P9 base, P10–P13 service-topology profile (already labelled as profile).
- 29 catalog rules in `tools/acima-spec/rules.json`: 23 automated, 6 `automation: "manual"`.
- 3 conformance levels (L1 structural, L2 immutable, L3 autonomous).
- Two architecture modes: `base` (default) and `service-topology`, selected only by `acima.config.json.mode`.
- Optional profiles: service topology (`ST-1`–`ST-12`), library/framework (TypeScript, .NET only).
- Waivers are fingerprinted, owned, expiring (`G001`, `G002`); full claims additionally need `.acima/manual-evidence.json`.

Rule-to-implementation coverage is declared in `conformance/coverage.json` and enforced by `conformance/run.py`: each profile must partition the 29 rules into executed/not-executed, and every gallery rule must fire.

## 4. Verification environment

| Tool | Available | Notes |
|---|---|---|
| Python 3.12.16 | yes | in a WSL Docker image, exposed as `python3` on Windows |
| Node 22.23.4 | yes | added to the same image during baseline; also native on the host |
| Go | **no** | host and container |
| .NET SDK 8/9/10 | host only | not inside the container |
| GitHub Actions | **not executed** | workflows are unobserved |

## 5. Baseline test results

`python3 conformance/run.py python` — **passed**: clean tree, 23 rules / 33 findings in the gallery.

Per-module results (`conformance/test_*.py`), before any change:

| Test module | Result | Cause |
|---|---|---|
| `test_adoption_safety` | pass (5) | — |
| `test_claim_model` | pass (12) | — |
| `test_cli` | pass (7) | — |
| `test_documentation_contract` | **fail** (13, 1 failure) | manifest pins catalog hash `a774bea1…`; `rules.json` is `59586eb7…` |
| `test_dotnet_profile` | pass, 5 skipped | no .NET in the container |
| `test_exclusions` | **error** (1) | `node` absent in container |
| `test_injected_violation` | **fail** (1 of 9, 2 skipped) | `node` absent in container |
| `test_library_profile` | **error** (9) | `node` absent in container |
| `test_mode_precedence` | **fail** (1 of 6) | cascades from the stale catalog pin (`SKL-002`) |
| `test_preflight_discovery` | **fail** (1 of 2) | cascades from the stale catalog pin (`SKL-002`) |
| `test_rule_catalog` | pass (1) | — |
| `test_topology` | pass (7) | — |
| `test_waiver_fingerprints` | pass, 1 skipped | no Go toolchain |
| `test_walkthrough` | pass (1) | — |

Two root causes, not eight defects:

1. **Real defect:** `skills/acima-adoption/manifest.json` (and the hash copied into `SKILL.md`) pins a catalog hash that no longer matches `tools/acima-spec/rules.json`. This blocks the preflight (`SKL-002`), one documentation test, and two preflight-driven tests.
2. **Environment gap:** the Python image had no `node`, so every test that shells out to the TypeScript enforcer failed. Fixed during the baseline by adding Node to the image; Go and .NET remain unavailable, and their tests skip.

## 6. Known limitations carried into the work

- Java is a documented profile with no reference enforcer; a Java run fails closed.
- Six rules (`C003`, `C007`, `L004`, `A002`, `A004`, `G004`) are normative but not decided by the portable enforcers.
- Enforcers are source-text analysis, not type/symbol analysis; glob semantics are not uniform across languages.
- Hosted CI and independent review have never been observed.
- `benchmark-evidence/` is declared immutable; a rerun must be a new dated directory.
