import json
from pathlib import Path
B=Path('/tmp/acima-real-world-benchmark')
P=json.loads((B/'aggregate/portfolio.json').read_text())
plans={
'httpx':'No architectural refactor is justified. If adopted, add a reviewed gate and a named owner; do not treat zero as proof because six rules were not executed.',
'flask':'No architectural refactor is justified. Add a gate only with a named owner; the single-package map does not exercise cross-module boundaries.',
'fastapi':'Reject L001: the match is the parameter name `sqlalchemy_safe`, not an import. Add a false-positive regression test; make no source change.',
'hono':'Do not adopt on the zero result. Resolve adapter/package imports first; the zero is a probable false negative, not a clean bill of health.',
'drizzle-orm':'L001 is dominated by intentional database-driver integration. One test path is outside production scope. No source change without owner-approved rule fit.',
'trpc':'Blocked. Output is truncated at 65,536 bytes and invalid; no assessment or plan can rest on it.',
'cobra':'No boundary change is justified for this single-module library. Add a gate only with an owner; zero is limited to executed rules.',
'bubbletea':'No boundary change is justified for this single-module framework. Add a gate only with an owner; zero is limited to executed rules.',
'gin':'No boundary change is justified for this single-module framework. Add a gate only with an owner; zero is limited to executed rules.',
'fluentvalidation':'The two assemblies have a real DI-to-core implementation dependency. Contract extraction or named-owner exceptions are required. The disposable gate correctly fails on baseline; no green adoption is claimed.',
'serilog':'No actionable finding in this single-unit map. Add a gate only with an owner; zero does not cover the six non-executable rules.',
'spectre-console':'D005 is an analyzer-reference false positive. D009 identifies real internal access. D001 is a probable contract-boundary violation; L003 is mostly shipped public API. Requires an owner decision; no source change.',
'jsoup':'No Java enforcer exists. Discovery and build/test only; no enforcement claim. A Java reference enforcer is required.',
'gson':'No Java enforcer exists. JPMS test boot fails because `com.google.gson` is not on the module path; a baseline limitation.',
'mall':'No Java enforcer exists and Maven exceeded five minutes. Discovery is partial; no plan can be validated.',
}
disc={
'httpx':'Single package with client, transport, auth, models and helpers; one implementation unit.',
'flask':'Single package with app, blueprints, CLI, config, sessions and testing; one unit.',
'fastapi':'Single package with routing, DI, params, security, encoders and openapi; one unit.',
'hono':'Core `src` and broad `adapters`; distinct modules still returned zero, suggesting unresolved adapter imports.',
'drizzle-orm':'Monorepo with ORM, kit and seed; eight modules. L001 reflects product-level database drivers.',
'trpc':'Monorepo with client, server, react-query and tests; assessment output unusable.',
'cobra':'Single Go module with command/flag/completion concerns; one unit.',
'bubbletea':'Single Go module; one unit.',
'gin':'Single Go module; one unit.',
'fluentvalidation':'Two production assemblies with a one-way project reference. The earlier same-module map hid the edge.',
'serilog':'One core library unit; sinks are not in this repository.',
'spectre-console':'Five production library units plus analyzer/build tooling; extensions/testing depend on core; JSON uses internal StringBuffer.',
'jsoup':'Single Maven library; no Java enforcer.',
'gson':'Two Maven production modules plus JPMS test; core tests run, JPMS boot fails.',
'mall':'Seven Maven modules; build timed out; no enforcer.',
}
for r in P['repositories']:
 out=B/'runs'/'rw-2026-11-08-01'/r['language']/r['id']/'report'; out.mkdir(parents=True,exist_ok=True)
 f=r['acima']['findings']; fs='not executable' if f is None else f'{f} findings'
 gt='\n'.join(f"- **{k}**: {v['count']} — {v['classification']}: {v.get('why','')}" for k,v in r['ground_truth'].items()) or '- No classification available.'
 text=f"""# Repository completion record — {r['repo']}

**Status:** blocked (no named upstream owner; no production changes)  
**Run:** rw-2026-11-08-01  
**Pinned commit:** `{r['commit']}`  
**License:** {r['license']}

## Inventory

- Language: {r['language']}; style: {r['architectural_style']}
- Production files: {r['source_files']:,}; nonblank LOC: {r['production_loc']:,}; units/modules: {r['modules']}
- {disc[r['id']]}

This is configuration-guided discovery, not an independent human architecture review. Directory layout was not treated as proof of ownership.

## Baseline

- Result: **{r['baseline_test_state']}**
- Detail: {r['baseline_test_detail']}
- Log: `logs/{r['test_log']}`

Failures and blocked builds are recorded as baseline conditions, not attributed to ACIMA or silently repaired.

## ACIMA assessment

- Parseable report: **{r['acima']['executed']}**
- Findings: **{fs}**
- Source files reported: {r['acima']['source_files_reported']}; portable rules: 23; non-executable: 6 (A002, A004, C003, C007, G004, L004)
- By rule: `{json.dumps(r['acima']['by_rule'])}`

Zero findings is not a conformance claim.

## Ground truth (author-adjudicated)

{gt}

No separate reviewer was available; this is not independent adjudication.

## Adoption plan

{plans[r['id']]}

## Implementation and verification

- Product source changes: none. No named owner exists and the evidence does not support an autonomous contract/ownership decision.
- Verification: baseline build/test and enforcer run only.
- Before/after architectural delta: not measured; no source change.
- This repository is not a completed adoption.

## Evidence

- `runs/rw-2026-11-08-01/{r['language']}/{r['id']}/assessment/`
- `runs/rw-2026-11-08-01/{r['language']}/{r['id']}/discovery/`
- `logs/{r['test_log']}`
"""
 (out/'report.md').write_text(text)

rows=[]
for r in P['repositories']:
 f='n/a' if r['acima']['findings'] is None else str(r['acima']['findings'])
 dens='n/a' if r['acima']['findings'] is None or not r['production_loc'] else f"{r['acima']['findings']/r['production_loc']*1000:.2f}"
 rows.append(f"| {r['id']} | {r['language']} | `{r['commit'][:10]}` | {r['source_files']:,} | {r['production_loc']:,} | {r['modules']} | {f} | {dens} | {r['baseline_test_state']} |")
md=f"""# Portfolio metrics — ACIMA real-world benchmark

Run `rw-2026-11-08-01`. Raw data: `aggregate/portfolio.json`.

| Repository | Language | Commit | Files | LOC | Units | Findings | /1k LOC | Baseline |
|---|---|---|---:|---:|---:|---:|---:|---|
{chr(10).join(rows)}

## Coverage

- 15 selected (3 each Python, TypeScript, Go, .NET, Java).
- 11 parseable ACIMA reports; 0 Java; tRPC unusable.
- 3,299 production files; 707,739 nonblank production LOC; 120 findings.
- Baselines: 12 complete, 1 partial (Gson), 2 blocked (Drizzle, mall).

## Interpretation

- 26 confirmed/probable defects.
- 84 valid architectural choices under the product model.
- 6 duplicates.
- 4 false positives.

The 84 valid choices are the central rule-fit problem: public library APIs and intentional database adapters are treated as boundary leaks. This is an author-labelled sample, not an independent precision estimate.

## Baseline limitations

- Drizzle: native `better-sqlite3` build failed; tests not run.
- tRPC: 1 upstream failure (`httpSubscriptionLink.memory.test.ts`, #6156); assessment unusable.
- Hono: 5 upstream declaration/JSX emit failures.
- httpx: 1 upstream async-generator warning failure.
- Gson: JPMS boot failure (`Module com.google.gson not found`).
- mall: Maven timeout at 295 seconds.
- Java: no enforcer; `executed:false` is not a pass.
"""
(B/'aggregate/portfolio.md').write_text(md)
print('reports',len(P['repositories']))
