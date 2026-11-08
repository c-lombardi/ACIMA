# Skill Discovery Validation

**Status:** IN PROGRESS — internal review only
**Question:** Can the skill independently inspect an unfamiliar repository and discover the
facts needed to map it to ACIMA?
**Method:** Read `preflight.py`; run it against controlled temporary fixtures with no
boundaries, misleading structure, and 18 candidate modules; inspect the output shape and
the reference workflow.

## Verdict

**PARTIAL — useful heuristics, not reliable discovery.**

The preflight detects languages, counts sources, proposes directory/project units, and
reports coverage gaps. It is read-only by default and labels drafts as heuristic. That is a
good start.

It cannot discover several facts the architecture requires. Two unsafe failure modes were
found; both are fixed in skill 1.2.2 and covered by `conformance/test_preflight_discovery.py`:

1. A repository with **no discoverable boundaries** exited `0` with warnings; it now fails
   `TGT-004` and exits `1`, so no baseline can be taken over zero units.
2. A repository with **more than 16 candidate modules** was silently truncated to 16; the cap
   is removed, and an 18-module fixture now proposes all 18.

## What it discovers

| Fact | Mechanism | Status | Evidence |
|---|---|---|---|
| Language(s) | Marker files + source extension counts | PARTIAL | `detect_languages`; markers for .NET/Go/TS/Python/Java; extension mapping |
| Source count | `walk_files` + extension set | PARTIAL | 50,000-file cap not reported |
| Mode | config present / source present | PASS | Observed: one source file -> `brownfield` |
| .NET projects | `rglob("*.csproj")` | PARTIAL | Includes test projects; no candidate cap |
| Directory units | Top-level children of `src`/`internal`/`packages`/`app`/`apps`/`services`/`lib`/`modules` | PARTIAL | Only one level; no nested modules; no dependency graph |
| Unit coverage | `TGT-005` against proposed units | PARTIAL | Warns; zero-unit `TGT-004` now blocks |
| Existing config | `acima.config.json` | PASS | Mode `adopting`; `GOV-*` checks |
| Enforcer availability | manifest | PASS | `GOV-002`; Java fail-closed |
| Java unsupported | profile manifest `null` | PASS | `ENF-java` skipped; `GOV-002` fail |
| Library profile evidence | not discovered | NOT SUPPORTED | No package publishability check in preflight |
| Service topology | not discovered | NOT SUPPORTED | No `acima.topology.json` inspection |
| Frameworks | not discovered | NOT SUPPORTED | No framework manifest/model detection |
| Application vs library | not discovered | NOT SUPPORTED | Skill text asks the agent; no code support |
| Public interfaces | not discovered | NOT SUPPORTED | No export/public API scan |
| Adapters/integrations | not discovered | NOT SUPPORTED | No adapter map; only enforcer findings if configured |
| Persistence | not discovered | NOT SUPPORTED | No schema/ORM inventory |
| Deployment topology | not discovered | NOT SUPPORTED | No Docker/K8s/serverless inspection |
| Architecture docs | not read | NOT SUPPORTED | No docs/ADR scan |
| Ownership | not inferred | N/A | Must ask a human; correct |
| Existing dependency graph | not built before config | NOT SUPPORTED | Enforcer builds it only after units exist |
| Ambiguous intent | labels proposed units heuristic | PARTIAL | No confidence/evidence per unit |

## Controlled observations

### 1. No boundaries

Fixture: `main.py` at repository root, no config.

Result (before 1.2.2): exit `0`; mode `brownfield`; `proposedUnits: []`; warnings
`TGT-004`/`TGT-005`. Result now: `TGT-004` fails and the process exits `1`, so the skill's
own blocker rule stops the workflow before a baseline.

**Assessment:** The original behavior was a **FAIL** for safe discovery. The fail-closed fix
is covered by `test_preflight_discovery.py`.

### 2. Misleading structure

Fixture: `README.md` says “modules Orders and Catalog”; only source is
`src/legacy/only.py`; no config.

Result: exit `0`; zero proposed units; `TGT-004`/`TGT-005` warnings. The README is not read.
The agent is not told that the documentation conflicts with the tree.

**Assessment:** The skill does not reconcile architecture docs with source structure. It
also fails to propose `src/legacy` because the descent logic treats `src` as a wrapper and
`legacy` has no child directories. A human would need to intervene; the tool does not say
that the heuristic failed, only that no units were found.

### 3. More than 16 candidate modules

Fixture: 18 directories under `src`, each with one Python file.

Result (before 1.2.2): exactly 16 proposed units (`mod01`–`mod16`). Result now: all 18 are
proposed, with no cap.

**Assessment:** The truncation was a **FAIL** for complete discovery. It is fixed and pinned
by the 18-module regression test. The 50,000-file walk cap remains unreported (R-30).

### 4. Existing repository

Running the preflight on this repository: exit `0`, `brownfield`, language `python`,
5 proposed units, no warnings or blockers. The proposal is not a product architecture; it
is a heuristic over the repository's directories. This confirms that a successful exit does
not mean the unit map is meaningful.

## Discovery quality by requirement

| Requirement | Status | Reason |
|---|---|---|
| Identify languages/frameworks | PARTIAL | Languages yes; frameworks no |
| Applications vs libraries | NOT SUPPORTED | No manifest/publishability analysis |
| Projects/packages | PARTIAL | .NET project scan; directory heuristics elsewhere |
| Existing module boundaries | PARTIAL | Directory children; no dependency/ownership evidence |
| Dependency relationships | NOT SUPPORTED before config | Enforcer only after a unit map |
| Public interfaces | NOT SUPPORTED | No exports/API scan |
| Adapters/integrations | NOT SUPPORTED | No inventory |
| Persistence | NOT SUPPORTED | No schema/ORM inventory |
| Deployment topology | NOT SUPPORTED | No deployment file scan |
| Existing architecture docs | NOT SUPPORTED | No README/ADR reconciliation |
| Likely ownership | NOT SUPPORTED | Must ask human; acceptable |
| Ambiguous intent | PARTIAL | Draft labels; no per-unit confidence/evidence |

## Safety findings

1. **Zero-unit success was unsafe — fixed.** `preflight.py` now returns 1 with `TGT-004`
   failed on a source-bearing repository, so “do not continue past a blocker” applies.
2. **Truncation was unsafe — fixed.** The 16-unit cap is removed; the 50,000-file walk cap
   is still not reported (R-30).
3. **No source vs no boundaries is conflated.** A repo with no source is greenfield; a repo
   with source but no proposed units is a discovery failure. The output distinguishes
   `proposedUnits: []` but the exit code does not.
4. **No docs reconciliation.** An architecture README can contradict the tree and the skill
   will not notice. It should read `README`, `docs/`, ADRs, and existing architecture
   documents, then report observed vs stated boundaries separately.
5. **No application/library distinction.** The skill says to classify the architecture kind
   but provides no executable evidence, so the agent may choose a base profile for a
   library or vice versa.
6. **No service-profile path.** A service repository is not recognized; the skill has no
   topology manifest step.

## Required corrections

- Treat `proposedUnits: []` on a source-bearing repository as a blocker, not a warning.
- Remove the 16-unit cap or report every omitted path and stop.
- Report the source-walk cap (50,000) and any truncation.
- Scan README/docs/ADRs and report stated vs observed boundaries, with citations.
- Add manifest-based application/library/service classification.
- Add `acima.topology.json` discovery and validation, or stop with `NOT SUPPORTED`.
- Add a public API/adapter/persistence inventory before proposing units.
- Add a confidence/evidence field to each proposed unit; never present a heuristic as fact.

## C2 disposition

**PARTIAL (unsafe at the edges).** It discovers languages and rough directory candidates;
it does not discover the architecture facts ACIMA needs, and it can return a ready exit
with zero or truncated boundaries.
