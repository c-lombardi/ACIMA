# ACIMA documentation

This directory **defines** ACIMA. Everything here is either normative or explains something normative. Enforcement code lives in [`../examples/`](../examples/README.md) and [`../conformance/`](../conformance/README.md); adoption guidance lives in [`../skills/`](../skills/README.md).

## Where the architecture is defined

| Question | Authoritative document |
|---|---|
| What is ACIMA, in normative terms? | [`standard/00-preface.md`](standard/00-preface.md) |
| What are the obligations? | [`standard/01-principles.md`](standard/01-principles.md) — P1–P9 are the base standard; P10–P13 belong to the service-topology profile |
| What do the words mean? | [`standard/02-vocabulary.md`](standard/02-vocabulary.md) |
| What may reference what? | [`standard/04-dependency-model.md`](standard/04-dependency-model.md) |
| Which rules exist, and what severity/level? | [`../tools/acima-spec/rules.json`](../tools/acima-spec/rules.json) — machine source; [`rules/index.md`](rules/index.md) is its human form |
| What counts as conformance? | [`standard/08-conformance.md`](standard/08-conformance.md) |
| What does ACIMA promise, and what is unverified? | [`product-contract.md`](product-contract.md), [`status.md`](status.md) |

If two documents disagree, the order above wins: `rules.json` over `rules/index.md`, and the standard over any guide, report or README.

## Contents

| Path | Role |
|---|---|
| `standard/` | the specification, chapters 0–12 (normative) |
| `rules/` | the human rule catalog with violation/fix examples ([README](rules/README.md)) |
| `languages/` | per-language expression of the rules: .NET, TypeScript, Python, Go, Java ([index](languages/index.md)) |
| `start/` | [quickstart](start/quickstart.md) and [brownfield adoption](start/brownfield.md) |
| `guides/` | explanatory material: leaders, reviewers, AI agents, before/after, architecture tests, analyzers, walkthrough, architecture families |
| `commands.md` | every command, its flags and exit codes, mapped to the adoption step that uses it |
| `status.md` | verified vs proposed capability, with limits |
| `product-contract.md` | consumer guarantees, known gaps, release gates |

## Reading order

1. [`../README.md`](../README.md) — what ACIMA is for, and how it relates to Clean Architecture, Hexagonal, DDD, modular monoliths and microservices ([guide](guides/architecture-families.md))
2. [`start/quickstart.md`](start/quickstart.md) — see it work
3. `standard/00` → `standard/05` — the obligations
4. [`rules/index.md`](rules/index.md) — the rules that fail a build
5. [`languages/index.md`](languages/index.md) — your language
6. [`standard/08-conformance.md`](standard/08-conformance.md) — how a claim is proved

Chapters 11 (service topology) and 12 (library profile) are **optional profiles**. Read them only if you are building a multi-service product or publishing an artifact.

## Changing the standard

A normative change is a repository-wide change and touches, in this order:

1. `../tools/acima-spec/rules.json` — id, severity, level, `automation`;
2. `standard/` chapter and `rules/` page — statement, why, detection;
3. every enforcer in `../examples/<lang>/tools/` and a fixture in `../examples/<lang>/violations/` with its `expected.json`;
4. `../conformance/coverage.json` — the executed/not-executed partition;
5. `../skills/acima-adoption/manifest.json` — catalog hash and version (the preflight blocks until this is done);
6. `status.md` and `product-contract.md` if a capability claim moved.

Rule ids are never renumbered or reused. `../conformance/run.py` and `conformance/test_documentation_integrity.py` fail when those six steps drift apart.

## What does not belong here

- Adoption workflow instructions — see `../skills/acima-adoption/SKILL.md`.
- Analyzer implementations — see `../examples/<language>/tools/`.
- Verification results — see `../conformance/`.
- Dated release reports. History belongs in git, and current claims belong in `status.md`.
