# Tools

Two things live here: the developer CLI, and the rule catalog that everything else derives from.

## `acima-spec/rules.json` — the single source of truth

Defines the 29 rules (id, severity, level, `automation`, manual-evidence hint), the five categories, the three conformance levels, the finding schema and the claim model.

Consumers: every reference enforcer, `conformance/coverage.json`, `conformance/run.py`, `acima.py`, and the adoption skill (which pins its SHA-256 in `manifest.json`). Changing it is a standard change — see [`../docs/README.md`](../docs/README.md#changing-the-standard).

## `acima.py` — developer entry point

```bash
python3 tools/acima.py inspect --root examples/python          # units, language, level, enforcer readiness
python3 tools/acima.py analyze --root examples/python          # findings from the reference enforcer
python3 tools/acima.py report  --root examples/python --format markdown
python3 tools/acima.py claim   --report acima.json --level L2 --require full
python3 tools/acima.py verify  [profiles...]                   # delegates to conformance/run.py
```

| Command | Guarantees |
|---|---|
| `inspect` | read-only; never writes to the target |
| `analyze` | runs the real enforcer for the detected language; exit `1` findings, `2` tool/config error |
| `report` | evidence only — lists the rules the run did **not** evaluate; no health score |
| `claim` | `FULL CONFORMANCE` only when every required rule executed or has accepted manual evidence, and there are zero unwaived errors |

`acima.py` is a thin wrapper: it does not implement a second rule engine, and it must not gain one.

## `acima_walkthrough.py`

An executable D001 walkthrough against the Python example: introduces a forbidden reference, shows the finding, fixes it, and confirms a clean run. Covered by `conformance/test_walkthrough.py`; it is the fastest way to see the enforcement loop end to end.

## What does not belong here

- Analyzer implementations — they live beside the reference implementation they analyse, in `examples/<language>/tools/`.
- Adoption workflow logic — `skills/acima-adoption/`.
