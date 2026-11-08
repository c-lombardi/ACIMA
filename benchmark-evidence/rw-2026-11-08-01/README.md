# ACIMA real-world benchmark evidence — rw-2026-11-08-01

This directory preserves the external benchmark run requested on 2026-11-08.

## Scope

- ACIMA commit: `5a9ef295b2605e08c967238332f10caf71c6e09d`
- Catalog hash: `125a1a3f…`
- Skill hash: `cfdbc9c6…`
- Standard: `1.0.0-draft.1`
- Run ID: `rw-2026-11-08-01`
- Selected repositories: 15 (3 Python, 3 TypeScript, 3 Go, 3 .NET, 3 Java)
- Evidence origin: `/tmp/acima-real-world-benchmark`

## Included

- `aggregate/`: portfolio metrics, scorecards, ledger and executive report.
- `candidates/`: discovery and selection metadata.
- `config/`: pinned ACIMA/catalog/skill configuration.
- `ground-truth/`: author-adjudicated classifications and the controlled-violation manifest.
- `logs/`: provisioning, dependency, build and test logs.
- `runs/rw-2026-11-08-01/`: per-repository discovery, assessment, implementation and report artifacts.
- `tooling/`: benchmark scripts used to generate configs, metrics and reports.

## Excluded

Third-party source clones and build outputs under `repositories/` are not committed. They total about 6.5 GB, include third-party code, and are reproducible from the pinned SHAs in `logs/provision.log` and `aggregate/portfolio.json`.

## Result

The benchmark did **not** validate ACIMA for broad adoption. The final verdict is **experimental use only**. No production source was changed. The one bounded enforcement gate correctly failed on the FluentValidation baseline, and a controlled project cycle was detected as D005.

## Limitations

- No independent reviewer/agent was available; classifications are author-adjudicated.
- The controlled violation was not blind.
- Evidence was produced under `/tmp` and has been copied here for durability.
- Java has no ACIMA reference enforcer; Java assessment remains `executed:false`.
- tRPC produced invalid JSON truncated at 65,536 bytes.
- Token counts and model cost were unavailable.

See `aggregate/EXECUTIVE-REPORT.md` for the full result and limitations.
