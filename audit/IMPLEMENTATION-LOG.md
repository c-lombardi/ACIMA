# Implementation log

Changes made, why each exists, and what it affects. Ordered by area; every entry names the reason and the blast radius.

## 1. Correctness fix that unblocked the rest

**`skills/acima-adoption/manifest.json`, `SKILL.md`, `docs/product-contract.md`, `references/00-preflight.md`, `conformance/test_documentation_contract.py`**

- Catalog hash re-pinned from `a774bea1…` to `59586eb7…` (the actual SHA-256 of `tools/acima-spec/rules.json`), skill version bumped `1.2.4` → `1.2.5`, and the two stale prose references to `1.2.3` corrected.
- The two tests that asserted the literal version now read it from the manifest, so the version has one authoritative home. The digest assertion is kept: it is what detects a hand-edited skill.
- Why: `SKL-002` blocked every preflight, which cascaded into `test_documentation_contract`, `test_mode_precedence` and `test_preflight_discovery`. This was a real defect, not an environment artifact — the catalog had changed after the skill was pinned.
- Impact: preflight exit 0; three failing tests now pass. No enforcement behaviour changed.

## 2. Documentation consolidation

| Change | Reason | Impact |
|---|---|---|
| Removed `docs/index.md`; added `docs/README.md` | two documentation indexes, neither authoritative | one entry point; GitHub renders `docs/README.md` for the directory |
| Added `docs/rules/README.md` | no document explained principle-vs-rule, authority order, or the human/automated split | a reader can find the one authoritative catalog |
| Added `conformance/README.md` | the runner's guarantees and limits were only in code | states what a pass proves and does not |
| Added `examples/README.md` | nothing explained what the four examples demonstrate | links each requirement to a location |
| Added `tools/README.md` | `acima.py` had no usage documentation outside `--help` | CLI contract in one page |
| Added `skills/acima-adoption/README.md` | `SKILL.md` is agent-facing; humans had no overview | short intro; `SKILL.md` stays authoritative |
| Rewrote `skills/README.md` | duplicated skill conventions already in `SKILL.md` | shorter install/navigation page |

## 3. Removals

| Removed | Size | Why | What depended on it |
|---|---:|---|---|
| `validation/` (20 files) | 3,633 lines | a second rule catalog, traceability matrix, language matrix and release narrative, all restating `rules.json`, `coverage.json`, `docs/status.md` and `docs/product-contract.md` as of a date | nothing — verified by repository-wide search; recoverable from git history |
| `docs/audit/continuous-improvement-ledger.md` | 422 lines | dated remediation log superseded by `audit/` | nothing |

Open work items that existed only in `validation/MASTER-BACKLOG.md` are carried into `audit/FINAL-REVIEW.md` §5 rather than dropped.

## 4. Root README

Link-only changes; the approved messaging, structure and claims are untouched:

| Before | After | Why |
|---|---|---|
| `[Architectural standard](docs/)` | `docs/README.md` | land on the document that explains where the standard lives |
| `[Principles and rules](docs/)` | `docs/rules/README.md` | the two links pointed at the same directory; neither reached the rule catalog |
| `[Reference implementations](examples/)` | `examples/README.md` | explains what the examples do and do not prove |
| `[Conformance tests](conformance/)` | `conformance/README.md` | explains what a pass proves |
| `[language profiles](docs/)` | `docs/languages/index.md` | pointed at the docs root, not the profiles |
| adoption-skill link | now also offers the human `README.md`; `SKILL.md` stays the agent entry point and is still linked | the agent entry point is preserved |

These are the only root README edits; no prose claim, positioning statement or limitation was changed.

## 5. New deterministic checks

**`conformance/test_documentation_integrity.py`** (wired into `conformance/run.py tools`):

1. every relative Markdown link in the repository resolves to a real file or directory (fenced code blocks and inline code spans excluded);
2. `docs/rules/index.md` lists exactly the catalog's rules with matching severity and level.

Why: the removed `validation/` matrix existed because nothing detected drift between a human document and `rules.json`. These two checks replace vigilance with a test. Both pass on the current tree.

## 6. Deliberately not changed

| Considered | Decision | Reason |
|---|---|---|
| Merge P1–P9 into fewer principles | rejected | each maps to a distinct requirement; folding immutability into contract isolation would weaken `C001`–`C007` (see `CORE-ARCHITECTURE.md` §3) |
| Move P10–P13 into chapter 11 | rejected | chapter 1 already declares them profile obligations; moving 160 lines creates a large diff for no clarity gain |
| Rewrite `tools/acima.py` to derive category labels/manual rules from `rules.json` | rejected | the duplication is pinned by `test_documentation_contract`; the rewrite adds risk without reducing what a reader holds |
| Trim `skills/acima-adoption/references/30,40,50` | deferred to the owner | adoption IP (onboarding, communication, metrics), not architectural duplication |
| Thin `benchmark-evidence/` | deferred at audit time, then applied as a follow-up — see §8 | cited evidence covered by `SHA256SUMS`; the split needed a retention decision first |
| Regenerate the benchmark after the skill re-pin | not possible here | requires network clones of 15 repositories; recorded as a limitation, not claimed |

## 7. Breaking changes and migration

| Change | Who is affected | Migration |
|---|---|---|
| `docs/index.md` no longer exists | any external bookmark or link | use `docs/README.md`; the reading order and chapter table moved there |
| `validation/` no longer exists | anyone citing those reports | `git show <commit>:validation/<file>` — nothing in the current repository replaced them because their content was duplicated |
| Skill is `1.2.5` | pinned skill copies in adopted repositories | re-copy `skills/acima-adoption`; the preflight will refuse the old pin, which is intended |
| No rule, severity, level, mode or finding-shape change | — | none |

## 8. Follow-up: benchmark evidence split

The audit deliberately left `benchmark-evidence/` in place: its artifacts were checksummed evidence, and thinning them needed a retention decision that the audit was not authorized to make. That decision was taken immediately afterwards — keep what a reader cites and can replay, archive the rest.

- **Removed 412 files.** Per-repository enforcer output (`runs/`, 301), toolchain logs (60), candidate discovery dumps (42), one-off tooling (6) and the three `SHA256SUMS` manifests.
- **Kept 48 files.** The directory README, each run's README, `aggregate/` headline results, the author-adjudicated `ground-truth/`, and the per-repository replay `configs/`.
- **The archive is unmodified and recoverable.** Everything removed is still in git history at `5c74eb4`; `benchmark-evidence/README.md` carries the exact `git checkout` command and notes that `SHA256SUMS` went with the set it certified, because a manifest cannot certify a partial set.
- **The link checker now covers the directory.** `benchmark-evidence` left `SKIP_DIRS`, so its remaining documents are navigated like every other document. That found one aggregate report linking to the archived `../runs/`; it now points at the directory README, and the surrounding text says the runs are archived.
- **No document still describes the old arrangement.** `docs/product-contract.md` (the immutability clause now names where each part lives), `audit/FINAL-REVIEW.md` (§4 weight and the remaining-opportunities entry), and a pointer at the top of `audit/SIMPLIFICATION-PLAN.md`.

Nothing in the standard, the rule catalog or any enforcer changed: this is evidence placement only.
