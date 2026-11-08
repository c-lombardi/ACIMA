# Five-minute quickstart

This is the shortest path from a clone to seeing ACIMA detect and correct a real
architectural violation. The Python path needs only Python 3.12.

## 1. Run the reference application

```bash
cd examples/python
python3 -m unittest discover -s tests -p 'test_*.py'
```

The example is a small ordering system. Catalog, Orders, Customers and Payments each
own a contracts package and an implementation. Orders validates a customer through the
Customers contract and keeps its own order view; it never imports the Customers
implementation. The TypeScript, Go and .NET examples carry `customer_id` as a value and
do not yet ship the fourth module.

## 2. Inspect the declared architecture

From the repository root:

```bash
python3 tools/acima.py inspect --root examples/python
python3 tools/acima.py analyze --root examples/python
python3 tools/acima.py report  --root examples/python
```

`inspect` is read-only. `analyze` runs the reference enforcer. `report` produces an
evidence report and explicitly lists the rules the portable runner did not evaluate.
There is no overall health score.

## 3. Watch a violation get fixed

```bash
python3 tools/acima_walkthrough.py
```

The walkthrough copies the clean application to a temporary directory, introduces an
Orders → Catalog implementation import, prints the `ACIMA-D001` finding, replaces it
with a dependency on `catalog.contracts`, and reruns the enforcer. The source tree is
not modified. The same flow is checked by `conformance/test_walkthrough.py`.

## 4. Run the whole verified suite

```bash
python3 conformance/run.py
```

This runs the topology checks, the Python/TypeScript/Go/.NET galleries, and the CLI and
walkthrough tests. A selected profile fails when its toolchain is unavailable. Java has
no reference enforcer in this revision, so a Java assessment fails closed rather than
reporting a clean result.

## 5. Apply it to another repository

```bash
python3 skills/acima-adoption/scripts/preflight.py --project /path/to/repository --format text
```

The preflight is read-only. It classifies the target, verifies its catalog pin, and prints
the next step. For the full phased rollout, read [Brownfield adoption](brownfield.md).

## What to read next

- [Executable before/after](../guides/before-after.md) — the seven common failure modes
  and the rule that catches each one.
- [Capability status](../status.md) — what is verified, limited, or only proposed.
- [For engineering leaders](../guides/engineering-leadership.md) — the investment case
  without invented ROI numbers.
