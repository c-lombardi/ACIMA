# WS-05: Enforcement engine, waivers and baseline integrity

**Outcome:** language enforcers share the same evidence identity and governance contract, and findings remain precise enough to trust and act on.

**Depends on:** WS-00 product and adoption experience contract. Coordinate public baseline flags and CLI invocation with WS-03.

## Owned files

- examples/python/tools/acima_arch.py
- examples/typescript/tools/acima-arch.mjs
- examples/go/tools/archtest/main.go
- examples/dotnet/tools/Acima.ArchTests/**
- conformance/test_waiver_fingerprints.py
- conformance/test_value_ownership.py
- conformance/test_dotnet_profile.py
- additional language-specific fixture tests where needed

Do not edit tools/acima.py, adoption workflow files, report schema/renderer, skill instructions or the normative rule catalog.

## Existing in-progress changes to preserve

At the starting checkpoint, the working tree already contains uncommitted changes in:
- all four language enforcers;
- conformance/test_waiver_fingerprints.py;
- conformance/test_value_ownership.py.

These are part of this workstream. Inspect them first. Do not reset, discard or overwrite them without a reason documented in the handoff.

## Objective

Make equivalent evidence produce compatible outputs across supported language enforcers. Reduce false positives caused by source-text shortcuts without claiming semantic analysis the tools do not perform.

## Required work

1. Establish the canonical finding fingerprint contract. The current claim/waiver validator requires a full SHA-256 value in the form sha256: followed by 64 lowercase hexadecimal characters. Every enforcer must use the same payload, path normalization, evidence trimming and digest length.
2. Ensure waiver validation consistently rejects missing, malformed and overly broad fingerprints. A waiver must suppress only the exact finding, inside its approved scope, for its valid review period.
3. Verify project-file findings resolve to the owning unit so unit/module waivers can govern them.
4. Ensure baseline support exists where the enforcer advertises it and the public CLI forwards the baseline path consistently. Coordinate the CLI surface with WS-03 rather than editing tools/acima.py.
5. Fix the current .NET false-positive cases conservatively:
   - infrastructure path detection must not depend on lowercase directory spelling;
   - internal-type matching must not collapse unrelated declarations with the same simple name into one global lookup;
   - a source namespace declared in the same repository must not automatically be called a third-party dependency just because it is absent from explicit map metadata.
6. Keep any source-text heuristic explicitly conservative. If reliable symbol/type resolution is unavailable, do not report certainty beyond what the observed import/declaration supports.
7. Keep each language's supported-rule coverage and not-executed list accurate. Do not pretend the enforcers have equal feature coverage.
8. Verify clean fixtures, known-violation galleries, duplicate-finding handling, baseline matching and exact waiver scope.
9. Do not change rule meaning or standard severity/level as a side effect of making the detector pass.

## Acceptance

- Every emitted finding has a stable canonical fingerprint and the same semantic fingerprint contract across languages.
- A valid exact waiver suppresses exactly one matching finding and no neighbouring finding.
- Missing or malformed waiver identity produces a visible governance finding; it does not silently suppress.
- New violations still fail when an approved baseline contains only pre-existing fingerprints.
- .NET fixtures prove the three false-positive scenarios above are corrected while genuine violations remain detectable.
- Clean-tree and violation-gallery checks remain meaningful and are not weakened.
- The full conformance runner passes or reports a precisely understood pre-existing limitation. No unsupported language is marked clean.

## Handoff

Return:
- canonical fingerprint and baseline contract;
- per-language coverage summary and known limitations;
- false-positive fixtures added and their observed outputs;
- files changed, including any preserved starting changes;
- focused tests and full-suite result.
