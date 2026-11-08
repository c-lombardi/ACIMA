# Repository completion record — spectreconsole/spectre.console

**Status:** blocked (no named upstream owner; no production changes)  
**Run:** rw-2026-11-08-01  
**Pinned commit:** `e8045f7c53c3c217a7f93f362f5256f1fadc0020`  
**License:** MIT

## Inventory

- Language: dotnet; style: multi-project console library/extensions
- Production files: 373; nonblank LOC: 44,929; units/modules: 5
- Five production library units plus analyzer/build tooling; extensions/testing depend on core; JSON uses internal StringBuffer.

This is configuration-guided discovery, not an independent human architecture review. Directory layout was not treated as proof of ownership.

## Baseline

- Result: **pass**
- Detail: passes across net8/net9/net10
- Log: `logs/dotnet-spectre-test-2.log`

Failures and blocked builds are recorded as baseline conditions, not attributed to ACIMA or silently repaired.

## ACIMA assessment

- Parseable report: **True**
- Findings: **72 findings**
- Source files reported: 384; portable rules: 23; non-executable: 6 (A002, A004, C003, C007, G004, L004)
- By rule: `{"ACIMA-D001": 4, "ACIMA-D005": 2, "ACIMA-D008": 5, "ACIMA-D009": 21, "ACIMA-L003": 40}`

Zero findings is not a conformance claim.

## Ground truth (author-adjudicated)

- **ACIMA-D001**: 4 — probable_true_positive: extensions/testing reference core implementation assembly; public library API design is intentional but unmodelled
- **ACIMA-D005**: 2 — false_positive: cycles traverse analyzer-only ProjectReference with ReferenceOutputAssembly=false; sourcegenerator has no json reference
- **ACIMA-D008**: 5 — false_positive: transitive closure of analyzer/extension edges; duplicates D001
- **ACIMA-D009**: 21 — true_positive: json uses internal StringBuffer from console; cross-assembly internal access is real coupling
- **ACIMA-L003**: 40 — valid_architectural_choice: public types are the shipped library surface, not an accidental implementation leak

No separate reviewer was available; this is not independent adjudication.

## Adoption plan

D005 is an analyzer-reference false positive. D009 identifies real internal access. D001 is a probable contract-boundary violation; L003 is mostly shipped public API. Requires an owner decision; no source change.

## Implementation and verification

- Product source changes: none. No named owner exists and the evidence does not support an autonomous contract/ownership decision.
- Verification: baseline build/test and enforcer run only.
- Before/after architectural delta: not measured; no source change.
- This repository is not a completed adoption.

## Evidence

- `runs/rw-2026-11-08-01/dotnet/spectre-console/assessment/`
- `runs/rw-2026-11-08-01/dotnet/spectre-console/discovery/`
- `logs/dotnet-spectre-test-2.log`
