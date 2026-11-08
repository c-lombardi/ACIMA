# Updated scorecards — ACIMA and the adoption skill

Run: `rw-2026-11-08-02`
Scores: 1–10, anchored to this benchmark. They are benchmark-local judgements,
not statistical estimates, certifications, or independent reviews.

## Adoption skill effectiveness

| Dimension | Score | Evidence in this run |
|---|---:|---|
| Architectural discovery | 4 | Unit maps are still hand-built. The tRPC directory-exclude trap and FluentValidation's inherited `PackageId` both required human diagnosis. |
| Boundary identification | 5 | Hono's adapter edges are now visible (25 classified D001 findings), and the .NET project graph exposes the DI/core and extension/core edges. tRPC scope mapping remains fragile. |
| Finding precision | 5 | 28 of 62 unclassified findings are confirmed or probable defects (45.2%). That is a material improvement over 21.7%, but nearly half the queue is still duplicates or valid library choices. |
| Finding recall | 4 | tRPC is now parseable and Hono's previous zero is resolved, but 6 of 29 rules do not execute and Java has no enforcer. No recall measurement is possible. |
| False-positive avoidance | 5 | FastAPI's L001 substring false positive and Spectre's D005 analyzer-cycle false positives are gone. D008 duplicates remain, and FluentValidation's profile is rejected by a tooling check. Valid public API choices still dominate the .NET queue. |
| Adoption planning | 4 | Plans still stop correctly for ownership, but none produced a validated green production adoption. The tRPC scope error shows configuration planning is not yet robust. |
| Implementation quality | 3 | This is a configuration and gate slice only. No upstream product code changed, and no architectural improvement was implemented. |
| Verification quality | 6 | 12/12 supported assessments now produce valid, non-truncated JSON; 8 zero-finding repositories are injection-proven for L001 and D001; the fixture suite and CI guard exist. Hosted CI and independent review remain unobserved. |
| Human oversight | 8 | No production code was changed without an owner. The stop was correct. |
| Efficiency | 5 | The rerun reused pinned copies and completed quickly, but external toolchains, hand-built configs, and baseline-test reuse still limit a clean end-to-end cost measure. |
| Repeatability | 7 | Raw outputs, configs, adjudications, commands and hashes are published in this run. Sources and toolchains remain external to the repository. |
| Transparency about limits | 8 | Raw tRPC scope output is preserved beside the selected corrected run; Java, non-executable rules, author adjudication and missing product adoption are explicit. |

**Skill average: 5.3/10** (64 points across 12 dimensions). Prior run: 4.6.

## ACIMA standard effectiveness

| Dimension | Score | Evidence in this run |
|---|---:|---|
| Specification clarity | 7 | The principles and evasion checks are understandable, but library/contracts semantics still need interpretation, especially when a public package surface is intentional. |
| Rule applicability | 5 | The library profile now handles real public API and adapter edges (150 classifications), but it is not portable in practice: FluentValidation's profile is rejected, and tRPC needs manual scope repair. |
| Language support | 5 | Python, TypeScript, Go and .NET have enforcers. Java still has none; three repositories are blocked, not passed. |
| Enforcement reliability | 6 | tRPC truncation is fixed and all 12 supported outputs are valid. Directory-exclude handling and inherited .NET package metadata are still reliability gaps. |
| Semantic coverage | 4 | 23 of 29 rules are portable; 6 do not execute. Import/name matching still cannot distinguish every intentional library edge. |
| Legitimate architecture flexibility | 5 | Profiles now classify 150 legitimate edges across Hono, Drizzle and Spectre, a clear improvement. FluentValidation cannot use its profile, and 30 valid choices remain unclassified. |
| Brownfield adoption friction | 4 | Unit maps are manual, multi-segment excludes are a trap, and library profile validation assumes project-local package metadata. These are real onboarding costs. |
| Actionability of findings | 5 | Findings have paths, fingerprints, severities and classification metadata. The remaining .NET queue mixes a true D001 with a tooling G001 and valid public API, so triage is still required. |
| Developer experience | 5 | JSON output, profiles and CI wiring are usable, but configuration edge cases and false profile rejection make the first adoption pass harder than it should be. |
| CI integration | 5 | The strict D001 fixture guard and no-skip log assertion are present, and the supported assessments are green or explainable. Hosted CI was not observed. |
| AI-agent compatibility | 5 | The prover and fixture tests reduce false greens, but this rerun still needed human adjudication for scope and profile behavior, and no independent agent ran it. |
| Governance and exception management | 7 | Fingerprints, owners and explicit classification reasons are sound. No approved production exception or owner-signed adoption was exercised. |

**Standard average: 5.3/10** (63 points across 12 dimensions). Prior run: 4.7.

The decimal is not a precision claim: the evidence supports a move from
“experimental, weak” to “experimental, materially improved,” not a move to
production-ready.

## Critical failures and limits

1. **Java remains unsupported.** jsoup, gson and mall are blocked. They are not
   counted as passes.
2. **Six rules still do not execute.** Coverage is 23/29 portable rules.
3. **FluentValidation's library profile is rejected.** `G001` fires because the
   `PackageId` is inherited from shared build props, not declared in the
   `.csproj`. Five valid public API findings therefore remain unclassified.
4. **tRPC's raw config silently admitted out-of-scope files.** The selected run
   corrects this with `/**` excludes, but the original directory strings did not
   work. The raw 105 `G005` findings are preserved and classified as a
   configuration false positive.
5. **The queue is still noisy.** 30 valid architectural choices remain
   unclassified, almost all public API in FluentValidation and Spectre.
6. **No independent review or production adoption.** Scores are
   author-adjudicated, and no product architecture changed.
