# Repository completion record — FluentValidation/FluentValidation

**Status:** blocked (no named upstream owner; no production changes)  
**Run:** rw-2026-11-08-01  
**Pinned commit:** `a8ca6ac3e7f35da9448a28e0ab84ae914cca4fb1`  
**License:** Apache-2.0

## Inventory

- Language: dotnet; style: two-assembly validation library
- Production files: 143; nonblank LOC: 11,675; units/modules: 2
- Two production assemblies with a one-way project reference. The earlier same-module map hid the edge.

This is configuration-guided discovery, not an independent human architecture review. Directory layout was not treated as proof of ownership.

## Baseline

- Result: **pass**
- Detail: 3 TFMs: 894 passed / 1 skipped each
- Log: `logs/dotnet-fluentvalidation-test-2.log`

Failures and blocked builds are recorded as baseline conditions, not attributed to ACIMA or silently repaired.

## ACIMA assessment

- Parseable report: **True**
- Findings: **8 findings**
- Source files reported: 144; portable rules: 23; non-executable: 6 (A002, A004, C003, C007, G004, L004)
- By rule: `{"ACIMA-D001": 1, "ACIMA-D008": 1, "ACIMA-L003": 6}`

Zero findings is not a conformance claim.

## Ground truth (author-adjudicated)

- **ACIMA-D001**: 1 — true_positive: DI extension assembly imports the implementation assembly; no contracts assembly
- **ACIMA-D008**: 1 — duplicate: derived from the same project reference
- **ACIMA-L003**: 6 — valid_architectural_choice: public library API is intentionally public; no contracts split

No separate reviewer was available; this is not independent adjudication.

## Adoption plan

The two assemblies have a real DI-to-core implementation dependency. Contract extraction or named-owner exceptions are required. The disposable gate correctly fails on baseline; no green adoption is claimed.

## Implementation and verification

- Product source changes: none. No named owner exists and the evidence does not support an autonomous contract/ownership decision.
- Verification: baseline build/test and enforcer run only.
- Before/after architectural delta: not measured; no source change.
- This repository is not a completed adoption.

## Evidence

- `runs/rw-2026-11-08-01/dotnet/fluentvalidation/assessment/`
- `runs/rw-2026-11-08-01/dotnet/fluentvalidation/discovery/`
- `logs/dotnet-fluentvalidation-test-2.log`
