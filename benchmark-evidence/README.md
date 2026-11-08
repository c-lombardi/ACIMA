# Benchmark evidence

Dated records of running the ACIMA enforcers against real open-source repositories. This is evidence for claims in [`../docs/status.md`](../docs/status.md) and [`../docs/product-contract.md`](../docs/product-contract.md) — it is **not** part of the standard and not required to use ACIMA.

| Run | Scope | Keep in tree | Archived in git history |
|---|---|---|---|
| [`rw-2026-11-08-01`](rw-2026-11-08-01/README.md) | 15 repositories, 5 languages | portfolio, scorecards, ledger, ground truth, pinned config | per-repo runs, logs, candidate discovery, tooling |
| [`rw-2026-11-08-02`](rw-2026-11-08-02/README.md) | 12 repositories | headline tables, portfolio, ground truth, configs | per-repo runs |
| [`rw-2026-11-08-03`](rw-2026-11-08-03/README.md) | 12 assessed, 3 Java blocked | portfolio | per-repo runs, tooling |

## What lives where

The repository keeps what a reader needs to cite a result and replay it: the aggregate reports, the author-adjudicated ground truth, and the `acima.config.json` used per repository.

Raw per-repository enforcer output and toolchain logs are **archived in git history** rather than the working tree, because they are release artifacts, not source, and they accounted for roughly 90% of the repository's files. Recover them with:

```bash
git checkout 5c74eb4 -- \
  benchmark-evidence/rw-2026-11-08-01/runs \
  benchmark-evidence/rw-2026-11-08-01/logs \
  benchmark-evidence/rw-2026-11-08-01/candidates \
  benchmark-evidence/rw-2026-11-08-01/tooling \
  benchmark-evidence/rw-2026-11-08-02/runs \
  benchmark-evidence/rw-2026-11-08-03/runs \
  benchmark-evidence/rw-2026-11-08-03/tooling
```

`SHA256SUMS` files were removed with the artifacts they covered: a checksum manifest cannot certify a partial set. The archived set at that commit is the checksummed one.

## Rules for this directory

- **Headline results are immutable.** Never edit a published run's aggregate numbers; a correction is a new dated directory.
- **Evidence, not a score.** A run records findings, classifications and blocked assessments. It does not compute an "architecture health" number, and none should be inferred.
- **Author-adjudicated.** Classifications were reviewed by the repository author, not an independent reviewer. Treat them as reproducible observations, not certification.

## How to read a run

| Path | Meaning |
|---|---|
| `README.md` | that run's scope, environment and headline results |
| `aggregate/` | portfolio and per-repo scorecards, executive summary, ledger |
| `configs/` or `config/` | the `acima.config.json` and pinned versions used per repository |
| `ground-truth/` | author classifications and controlled-violation records |
| archived | raw enforcer JSON, stderr, exit codes, toolchain and clone logs |

## Publishing a new run

Add a new dated directory containing its headline results, ground truth and configs; publish the raw artifacts as a release attachment or keep them in git history, not in the default branch.
