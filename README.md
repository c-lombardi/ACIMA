# ACIMA

**Build systems that stay modular as your organization grows.**

ACIMA is an executable architecture standard for codebases where modules must be changed,
tested and released without coordinated rewrites. It makes ownership, contracts,
dependencies and architectural exceptions visible to the build — not just to the people who
remember the diagram.

It is not a framework, a project template or a microservices requirement. It is a small set
of rules, a machine-readable unit map, and reference enforcers for Python, TypeScript, Go
and C#/.NET. The Java profile is documented but has no reference enforcer in this revision.

> Status: **Draft 1** (`1.0.0-draft.1`). See [Capability status](docs/status.md) for what is
> verified, what is limited, and what is still proposed, and the
> [product contract](docs/product-contract.md) for consumer guarantees and release gates.

---

## If this sounds familiar, ACIMA is for you

| What teams experience | What it costs |
|---|---|
| A `Common` or `Shared` project everyone depends on | every change becomes a cross-team release |
| Orders imports Catalog's implementation “just this once” | Catalog can no longer change its store or be tested alone |
| A contract change requires several teams to coordinate | independent evolution stops; releases become lockstep |
| Two modules read and write the same tables | incidents and schema changes cross ownership boundaries |
| The architecture rules live in a wiki | nobody knows they were broken until production |
| A cycle appears between two modules | neither can be extracted or replaced |
| A waiver has no owner or expiry | “temporary” becomes permanent |
| An AI agent adds an unauthorized dependency | review catches it late, or not at all |

The underlying problem is the same: **the boundary exists as a convention, not as a fact the
build can check**.

## What changes with ACIMA

| Problem | ACIMA mechanism | Executable evidence |
|---|---|---|
| Implementation coupling | Contracts are the only public surface; implementations are private | `D001`, `D008`, `D009` |
| Contracts are not independent | Each contracts unit imports nothing; value types are local | `D003`, `D004`, `P12`, `ST-5` |
| Contract changes are unpredictable | Immutable messages and a reviewed API baseline | `C001`–`C007`, `G004` |
| Shared persistence | One module owns each schema and store | `A001` |
| Hidden configuration coupling | Each module owns its configuration namespace | `A002` (manual/native review) |
| Unowned exceptions | Waivers carry owner, reason, scope, finding fingerprint, expiry and review date | `G001`, `G002` |
| Architecture is not enforced | Findings fail the gate at the declared level | `L1`–`L3`, `G005` |
| AI agents drift | Catalog hash, unit map, CLI, structured findings and an agent skill | [AI agents](docs/guides/ai-agents.md) |

The rule catalog has **29 rules**; **23 are portable** across the reference enforcers. The
six remaining rules need native analyzers, package metadata or human judgement, and are
listed explicitly rather than silently counted as passes.

## Before and after

```text
Before: convenience coupling

Orders ──> Catalog implementation ──> catalog_products
   │
   ├────> mutable DTO from Common
   └────> direct SQL into Catalog's schema

After: contract isolation

Orders ──> Catalog.Contracts (ProductView, CatalogReader)
   │
   ├────> its own value types and orders schema
   └────> explicit map at the boundary

Catalog ──> its own schema
Payments ──> Payments.Contracts and its own schema
Host ─────> constructs every module; modules never construct each other
```

A module can be tested with a fake port. A contract can be versioned without recompiling
the world. A schema has one owner. Exceptions are visible, owned and expiring.

See the full [before/after demonstration](docs/guides/before-after.md), including the
violations that are intentionally **not** claimed as automatically detected.

## See it work

From the repository root, the walkthrough injects a real defect into a temporary copy of the
ordering application, prints the enforcer finding, corrects the code and reruns the gate:

```bash
python3 tools/acima_walkthrough.py
```

```text
before: clean ordering application — 0 findings
introduced: Orders imports Catalog's implementation (src/acima/orders/impl/reach_into_catalog.py)
finding: ACIMA-D001 — Module orders imports the implementation unit catalog (expected catalog.contracts).
  src/acima/orders/impl/reach_into_catalog.py:1  from acima.catalog.impl.repository import InMemoryProductStore
fixed: depend on Catalog's contract instead of its implementation
after: 0 findings
result: violation detected, corrected, and verified
```

This is a real run of the Python enforcer, not a screenshot. The test that proves it is
[`conformance/test_walkthrough.py`](conformance/test_walkthrough.py).

## Five-minute quickstart

The Python path needs only Python 3.12. The full suite also uses Node, Go and .NET when
those toolchains are installed.

```bash
# 1. See the declared units and run the enforcer
python3 tools/acima.py inspect --root examples/python
python3 tools/acima.py analyze --root examples/python

# 2. Produce an evidence report with explicit unevaluated rules
python3 tools/acima.py report --root examples/python

# 3. See a violation detected and corrected
python3 tools/acima_walkthrough.py

# 4. Run the verified suite
python3 conformance/run.py
```

`analyze` returns exit code `1` when unwaived errors exist, `0` when clean, and `2` when
the tool cannot run. A tool failure is not architectural debt. A clean run with unevaluated
rules is not a conformance certificate.

Full instructions: [Five-minute quickstart](docs/start/quickstart.md).

## Apply it to an existing repository

Start read-only. Do not rewrite the application first.

```bash
export TARGET=/path/to/repository

python3 skills/acima-adoption/scripts/preflight.py --project "$TARGET" --format text
python3 tools/acima.py inspect  --root "$TARGET"
python3 tools/acima.py analyze  --root "$TARGET" --format json > acima-baseline.json
python3 tools/acima.py report   --root "$TARGET" --format markdown > acima-report.md
```

Then review the proposed unit map, write owned waivers for the baseline, gate new findings
in CI, and merge one boundary change. The full phased path is in
[Brownfield adoption](docs/start/brownfield.md).

Do not use `acima verify` as the target's gate: that command verifies this ACIMA repository
and its examples. The target must run its own enforcer in its own pipeline.

## Adoption paths

| Starting point | Path |
|---|---|
| Greenfield product or new service | Full shape from day zero; see [Adoption](docs/standard/09-adoption.md#91-greenfield) and the agent skill. |
| Existing monolith | Measure, waive, gate, then extract one boundary at a time: [Brownfield adoption](docs/start/brownfield.md). |
| Modular monolith with weak seams | Start with contract extraction for the two most-coupled modules. |
| Distributed services | Apply the same contract and ownership rules at the network boundary; see [Service topology](docs/standard/11-service-topology.md). |
| AI-assisted engineering | Use the pinned [agent skill](skills/acima-adoption/SKILL.md), CLI and structured findings; see [AI agents](docs/guides/ai-agents.md). |

## What is in this repository

| Area | Contents |
|---|---|
| Standard | 13 principles, dependency model, contract design, runtime boundaries, governance, conformance and adoption. |
| Rule catalog | 29 rules with IDs, severity, level, detection strategy and remediation. |
| Language profiles | Python, TypeScript, Go, C#/.NET and Java. Four have reference enforcers; Java is profile-only. |
| Reference implementations | Ordering systems in Python, TypeScript, Go and C#/.NET. Python carries four modules (Catalog, Orders, Customers, Payments); the others carry three. |
| Violation galleries | Deliberately broken fixtures with checked-in expected findings. |
| Conformance runner | Good tree + gallery + topology + CLI/walkthrough checks. |
| Developer CLI | `python3 tools/acima.py inspect/analyze/report/verify`. |
| Agent skill | `skills/acima-adoption` — preflight, unit-map draft, waiver baseline and playbooks. |
| CI workflow | [`.github/workflows/acima.yml`](.github/workflows/acima.yml). |

## Technical specification

- [Principles](docs/standard/01-principles.md)
- [Vocabulary](docs/standard/02-vocabulary.md) — module, service, contract, implementation and integration boundary
- [Dependency model](docs/standard/04-dependency-model.md)
- [Contract design](docs/standard/05-contract-design.md)
- [Runtime boundaries](docs/standard/06-runtime-boundaries.md)
- [Executable governance](docs/standard/07-executable-governance.md)
- [Conformance levels](docs/standard/08-conformance.md)
- [Rule catalog](docs/rules/index.md)
- [Language profiles](docs/languages/index.md)
- [Service topology](docs/standard/11-service-topology.md)
- [Capability status](docs/status.md)

The machine-readable source of truth for rules is
[`tools/acima-spec/rules.json`](tools/acima-spec/rules.json). The standard version is
declared in that catalog; changing a rule's meaning is a standards change, not an adoption
shortcut.

## FAQ

**Is ACIMA another Clean Architecture implementation?** No. Clean Architecture constrains
layers inside an application. ACIMA constrains ownership and the public surface between
modules. You can comply with one and violate the other.

**Why not just use ArchUnit or NetArchTest?** Use them where they fit. ACIMA adds portable
rule IDs, one finding format, contract-shape rules, waiver hygiene and a conformance runner
that compares profiles. The reference enforcers are deliberately thin and readable.

**Do I need microservices?** No. ACIMA is designed for modular monoliths first. A module
that satisfies the rules is easier to extract later; extraction is not required to get
value.

**Does adoption require a rewrite?** No. The brownfield path is measure → waive → gate →
one boundary at a time. Do not start with persistence.

**Can I adopt incrementally?** Yes. Start at L1, baseline existing findings, and ratchet.
A waiver is an owned, expiring exception, not a silent suppression.

**Does it work with an existing modular monolith?** Yes, that is the primary use case.

**Can modules use different databases?** They can, and they may also share a database
server as long as each module owns its own schema and no module reads another's tables.
The rule is ownership, not deployment topology.

**Does ACIMA dictate infrastructure or deployment technology?** No. Infrastructure and
vendor SDKs belong in adapters and the host; the standard is neutral about the platform.

**Can AI coding agents use it?** Yes. The agent skill verifies the catalog hash, reads the
unit map, runs the enforcer and reports contract changes. It is instructed not to edit the
config or waivers to pass a check.

**What happens when a rule needs an exception?** Write a scoped waiver with an owner,
reason, expiry and review date. Expired waivers fail the build. Bulk renewal is forbidden.

**How much developer overhead does enforcement add?** The gate runs in the existing
pipeline. The recurring work is reviewing findings and waivers; the one-off work is
contract extraction and boundary cleanup. The standard gives cost ranges, not invented
delivery estimates.

**What is not verified?** Runtime autonomy, deployment independence and organizational
ownership are not proven by a static enforcer. Six portable rules require native analyzers
or human review. Java is profile-only. See [Capability status](docs/status.md).

## Prior art

ACIMA assembles documented practice rather than inventing it:

- **Explicit Contract Projects** — module + contracts split and dependency-light contracts.
- **Clean Architecture / Hexagonal / Ports & Adapters** — layering and boundary direction.
- **Domain-Driven Design and Modular Monoliths** — bounded contexts and composition roots.
- **ArchUnit, NetArchTest and Purview Architests** — architecture rules as executable tests.
- **Microsoft library guidance and MSBuild `PrivateAssets`** — dependency minimisation and
  transitive control.

ACIMA's contribution is the combination made portable and enforceable: absolute contract
isolation by default, immutable contract shape, runtime ownership rules, owned expiring
waivers, one finding format across languages, and an agent-readable adoption path.

## Repository map

```text
docs/            standard, rules, language profiles, guides, quickstart and status
examples/        Python, TypeScript, Go and .NET reference implementations + galleries
conformance/     cross-profile runner, topology checks, CLI and walkthrough tests
tools/           rule catalog, CLI, executable walkthrough
skills/          portable adoption skill and templates
```

## Licence and governance

The standard is versioned (`major.minor.patch`). Adding a rule is a minor version; changing
an existing rule's meaning or identifier is a major version. Rule identifiers are permanent:
`ACIMA-D001` means the same thing in every language and every version.

See the repository's licence terms when present.
