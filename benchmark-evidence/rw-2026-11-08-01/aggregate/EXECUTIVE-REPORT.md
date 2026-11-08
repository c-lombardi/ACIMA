# ACIMA real-world benchmark — executive report

**Run:** rw-2026-11-08-01  
**Date:** 2026-11-08  
**ACIMA commit:** 5a9ef295b2605e08c967238332f10caf71c6e09d  
**Catalog hash:** 125a1a3f…  
**Skill hash:** cfdbc9c6…  
**Standard:** 1.0.0-draft.1  
**Verdict:** **Not validated for broad adoption. Experimental use only.**

## Portfolio

Fifteen repositories were selected, three per language: Python (httpx, Flask, FastAPI), TypeScript (Hono, Drizzle ORM, tRPC), Go (Cobra, Bubble Tea, Gin), .NET (FluentValidation, Serilog, Spectre.Console) and Java (jsoup, Gson, mall). All selected licenses are permissive: MIT, Apache-2.0 or BSD-3-Clause. No upstream push, pull request or commit was made.

The portfolio is weighted toward libraries and frameworks because larger application seeds exceeded the resource budget. That is a benchmark limitation and weakens claims about layered enterprise applications. The source snapshot is pinned per repository; commits, licenses and file counts are in `aggregate/portfolio.json`.

Measured set: **3,299 production files** and **707,739 nonblank production lines**. The workspace is `/tmp/acima-real-world-benchmark`, outside ACIMA. ACIMA was not modified and contains no benchmark artifact.

## Execution

- Prepared with separate source, baseline and adoption copies: **15/15**.
- Complete baselines: **12**; partial: **1** (Gson); blocked: **2** (Drizzle native build, mall Maven timeout).
- Parseable ACIMA assessments: **11**. tRPC produced no JSON; Java produced no assessment because no Java enforcer exists.
- Findings: **120** across parseable reports.
- Implementations: **1 attempted enforcement slice**, blocked. Verified architectural improvements: **0**.
- Independent reviews: **0**. No separate reviewer/agent was available; all adjudication is by the same assistant.

Baseline behavior was preserved: httpx has one upstream async-generator warning failure; Hono has five declaration/JSX failures in two files; tRPC has one subscription-memory failure; Gson's JPMS module fails to boot; Drizzle could not build `better-sqlite3`; mall exceeded five minutes. None were repaired to make ACIMA look better.

## Findings and precision

- **26 confirmed or probable defects.** FluentValidation's DI-to-core implementation dependency; Spectre's extension-to-core dependencies and 21 cross-assembly internal accesses.
- **84 valid architectural choices under the product model.** 38 Drizzle database-driver integrations, 40 Spectre public API types, 6 FluentValidation public API types. ACIMA has no library/public-API profile separating a shipped surface from an accidental leak.
- **6 duplicates.** D008 transitive findings repeating D001 edges.
- **4 false positives.** FastAPI's only finding matches the parameter name `sqlalchemy_safe`, not an import; Spectre's two D005 cycles traverse an analyzer-only project reference (`ReferenceOutputAssembly=false`); one Drizzle finding is a test path outside production scope.

Actionable-defect yield is **21.7%** (26/120), but this is not an independent precision estimate. The defensible conclusion is narrower: **the enforcer produces too much context-insensitive noise to gate these library repositories without rule-fit work.** Hono's zero is not a counterexample; after separating core and adapters it still returned zero, a probable false negative. tRPC is unassessable because stdout is exactly 65,536 bytes and invalid JSON.

## What worked

- Pinning and isolation: 15 repositories at fixed SHAs, separate baseline/adoption copies, no upstream credentials.
- Baseline execution: Python, Go and .NET suites ran broadly; exact failures and limits were preserved.
- Exact evidence: findings carry rule, path, line, message and fingerprint.
- Controlled detection: adding a project cycle to a disposable FluentValidation copy produced D005.
- Human oversight: the skill stopped rather than manufacturing waivers or editing source without an owner.
- Separation: no ACIMA rule, catalog, expected result or upstream repository was changed.

## What did not work

- Rule fit for libraries: L001, D001 and L003 treat product infrastructure and public APIs as violations.
- Semantic analysis: FastAPI's L001 is a substring match; D005 does not exclude analyzer references.
- Output reliability: tRPC's fixed byte cap makes a real repository unassessable.
- Unit modeling: a same-module map initially hid FluentValidation's boundary; correction changed 0 findings to 8.
- Coverage transparency in practice: six rules are non-executable and Java has no enforcer, yet zero still looks like success.
- Adoption outcome: no repository received a safe, owner-approved architectural improvement.

## Before/after

The only bounded slice was a FluentValidation enforcement gate in a disposable copy. Before it, no ACIMA unit declaration existed. After it, 144 production files were declared, the gate ran, and it correctly failed with 8 findings (D001 1, D008 1, L003 6). A separately injected cycle produced D005. Product code was untouched, tests were unchanged, and the gate was not green.

There is therefore **no measured architectural improvement**. The before/after change is governance coverage (0 → 1 gate), not reduced coupling, cycles or improved modularity. Calling it a successful adoption would be false.

## Why implementation stopped

No named human owner or architecture-owner approval exists for any upstream repository. Under the skill's rules, exceptions require a named owner, fingerprint and expiry, and contract changes require an ownership decision. FluentValidation's D001 requires contract extraction or an approved exception; Spectre's 21 D009 accesses require an owner decision; Drizzle's L001 findings require a rule-fit decision for a product whose adapters are the architecture. None can be made autonomously. The correct result is a blocked adoption with an actionable plan, not a forced patch.

## Highest-value ACIMA improvements

1. **Fix L001 semantics.** Resolve imports and symbols, not identifier substrings; add `sqlalchemy_safe` and Drizzle driver adapters as regression fixtures.
2. **Exclude analyzer-only references from D005/D008.** Honor `ReferenceOutputAssembly=false`; add Spectre's source-generator case.
3. **Add a library/public-API profile.** Distinguish shipped surfaces and intentional product adapters before enforcing L003/D001.
4. **Remove the 65,536-byte output ceiling.** Stream/write JSON, validate it, and fail closed with a diagnostic on truncation.
5. **Implement a Java reference enforcer.** Until then Java remains `executed:false`, never “pass.”

## Highest-value skill improvements

1. Derive module boundaries from package/project manifests and require a sensitivity check; never collapse separate published packages.
2. Treat zero findings as “not proven”; run a known injected violation before declaring a repository clean.
3. Validate enforcer JSON, exit status and byte limits; stop on truncation instead of producing an empty assessment.
4. Stop before production changes when no named owner exists; label a gate that fails on baseline findings as blocked, not adopted.
5. Add library/framework discovery: identify the shipped API, intentional adapters and product infrastructure before applying application-module rules.

## Scorecards

The adoption skill scores **4.6/10** and the ACIMA standard **4.7/10**. These are judgement calls, not certifications. Critical failures—Java enforcement, tRPC truncation, FastAPI false positive, Spectre false cycles and no verified improvement—remain visible regardless of averages. Details: `aggregate/scorecards.md`.

## Limitations

- Evidence is under `/tmp`: outside ACIMA but not durable. It will not survive the session unless exported.
- No independent reviewer/agent; the controlled violation was not blind.
- The portfolio is library/framework-heavy; it does not establish behavior on layered or multi-service enterprise applications.
- Drizzle, tRPC assessment, Gson JPMS and mall are blocked or partial.
- Token counts and model cost were unavailable; no estimate is offered.
- No upstream owner approved a change; no production code was modified.

## Final verdict

**Experimental use only.** ACIMA is not validated for individual, small-team, broad-organization or enterprise adoption by this benchmark. A controlled small-team pilot could be justified only for application repositories with explicit module ownership, reviewed unit maps, a named architecture owner, and the five enforcer fixes above. Broad adoption and enterprise rollout are not supported.

The most important result is not the 120 findings. It is that the tool can appear green or red for the wrong reason—and that the benchmark caught both before anyone shipped a change.
