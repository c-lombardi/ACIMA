# Conformance

This directory **verifies** ACIMA. It does not define it: every expectation here is derived from [`../tools/acima-spec/rules.json`](../tools/acima-spec/rules.json) and [`../docs/standard/`](../docs/README.md).

## Run it

```bash
python3 conformance/run.py                 # topology, python, typescript, go, dotnet, tools
python3 conformance/run.py python          # one reference implementation
python3 conformance/run.py tools           # the test modules only
python3 conformance/run.py --artifacts out # keep per-profile JSON evidence
```

Exit codes: `0` every selected profile conformed, `1` drift or a missing toolchain, `2` the runner could not start. **A missing toolchain is exit 1, never a green skip.**

## What it checks

| Check | Question |
|---|---|
| clean tree | does the reference implementation produce zero findings? |
| gallery | does every required rule fire, at the expected path? |
| `coverage.json` | does each profile partition all 34 rules into executed / not-executed, with a reason? |
| source count | did the enforcer actually see files? Zero files is a failure, not a pass |
| execution map | does the run name every catalog rule, with `executed: false` where applicable? |
| `tools` | do the CLI, claim model, waiver, exclusion, profile, topology and documentation contracts still hold? |

## Files

| File | Role |
|---|---|
| `run.py` | the runner and coverage contract |
| `coverage.json` | per-profile executed / not-executed / gallery partition |
| `acima_claim.py` | `FULL CONFORMANCE` vs `PARTIAL ASSESSMENT` computation |
| `topology.py` | optional service-topology profile (`ACIMA-S001`–`S012`) |
| `test_*.py` | focused contract tests; each is independently runnable |
| `fixtures/` | library and .NET profile fixtures used by those tests |

## Adding a fixture

1. Put the violating source under `../examples/<lang>/violations/`.
2. Add its exact path to that directory's `expected.json` under the rule id.
3. If the rule was not previously executed for that profile, move it in `coverage.json` and give the others a reason.
4. Confirm the clean tree still has zero findings.
5. Run `python3 conformance/run.py <lang>`; it fails if the gallery misses a rule, drifts from `expected.json`, or if the clean tree is not clean.

Positive fixtures (the clean reference implementations) and negative fixtures (the galleries) are both required: a suite that only proves violations fire cannot distinguish a correct enforcer from one that reports everything.

## What a pass proves, and what it does not

Passing means: for the four implemented languages, the reference enforcers detect the portable rules on checked-in fixtures (28 in Python and TypeScript, 23 in Go and .NET, where the five third-party tier rules report `executed: false`), agree on finding shape, and do not fire on a clean tree, and the claim model refuses to overstate.

Passing does **not** mean:

- your repository is architecturally sound — it is one input, not a certificate;
- the six manual rules were evaluated (they were not);
- runtime isolation, type correctness or framework behaviour was proven;
- Java is supported (it is not);
- hosted CI ever ran (see [`../docs/status.md`](../docs/status.md)).

## Supported implementations

| Language | Status |
|---|---|
| Python, TypeScript, Go, .NET | reference enforcer + gallery |
| Java | profile documented, no enforcer; selection fails closed |
