# ACIMA

**Architecture that enforces itself.**

AI is making it faster to generate, modify and ship software. It is not making it easier to keep that software internally consistent. Code generated at speed inherits the same failure mode as code written by hand, only faster: a module reaches into another module's implementation, and the boundary stops meaning anything.

Documentation does not stop this. Review does not scale to it. ACIMA does, because an ACIMA boundary is **executable** — a rule a build can fail on.

ACIMA (Autonomous, Contract-Isolated, Immutable Modular Architecture) is an architectural standard for systems built and changed by people and AI agents together. It defines how modules are structured, what they may depend on, and how those limits are checked automatically.

> A module owns its implementation, exposes an explicit contract, and prevents anything outside from depending on its internals.

## The problem

Architectural intent usually lives in three places that all decay: a diagram, a conventions document, and the memory of whoever reviewed the last pull request. None of them fail loudly. The system does not break when a boundary is crossed; it just becomes harder to change, and the cost arrives months later as "we can't touch that module without touching five others."

AI agents accelerate exactly this. An agent optimising for a passing test will import the concrete class that works, not the contract it should have used. It has no reason to prefer the interface unless something tells it to — and unless something checks.

## What ACIMA is, and is not

| ACIMA is | ACIMA is not |
|---|---|
| A small set of architectural obligations about ownership, contracts and dependency direction | A folder-layout convention or a project template |
| Executable: reference enforcers produce findings with rule IDs, evidence and remediation | A linter for style; it does not care about formatting or naming taste |
| Incrementally adoptable in an existing codebase, starting with a measurement | A rewrite, a migration programme, or a mandate to restructure |
| Explicit about which rules are automated and which need human judgement | A promise that a clean run means the architecture is correct |
| Independent of framework, deployment model and domain methodology | A replacement for your architecture — it enforces the boundaries Clean Architecture, Hexagonal Architecture, DDD, modular monoliths or microservices define |

## Your architecture, enforced

ACIMA is not a competing architecture. Your team still chooses Clean Architecture, Hexagonal
Architecture, domain-driven design, a modular monolith or microservices; ACIMA makes the boundaries
that choice declares executable.

```
Your team chooses                    Clean Architecture · Hexagonal Architecture
                                     Domain-Driven Design · Modular monolith
                                     Microservices

ACIMA defines and enforces           the boundaries that choice declares:
                                     ownership, contracts, dependency direction

Language-specific enforcement        analyzers · architecture tests · CI gate
                                     · AI adoption guidance
```

Each family contributes something ACIMA does not replace: Clean's dependency direction, Hexagonal's
ports and adapters, DDD's bounded contexts and aggregates, the modular monolith's deployment
simplicity, microservices' independent deployability. ACIMA adds the same thing to all of them: a
build that fails when a module crosses its declared boundary, with findings, owned waivers and a
CI gate. They are pillars in their own right: mature practices a team may adopt for reasons that have
nothing to do with ACIMA, and ACIMA does not rank them.

Where ACIMA is stricter — contracts that cannot reference other contracts, no cross-module
in-process transaction, zero-dependency contracts — the requirement is stated, justified
independently, and scoped to boundaries rather than internal design. A departure is an owned
waiver, never a silent exception. The full mapping, including what ACIMA does not decide, is in
[Your architecture, enforced](docs/guides/architecture-families.md).

Five obligations carry the standard: **module ownership**, **explicit contracts**, **dependency isolation**, **data and configuration ownership**, and **controlled composition**. They are expressed as eleven base principles and a 55-rule catalog — 41 of which the reference enforcers decide from source (eighteen of those in Python and TypeScript only, in this revision), and fourteen of which require recorded human evidence. P15 adds **owned effects**: every externally visible effect has an owner, visible semantics, a truthful outcome and evidence proportionate to its criticality. It also makes state mutation, consistency and observability explicit: one owner per consistency boundary, a declared guarantee instead of assumed atomicity, and telemetry that observes behaviour rather than replacing it. The obligations are conditional on the design: retries, transactions, idempotency keys and cancellation are required only where the operation's contract makes them applicable.

The catalog also makes **instance lifetime and state ownership** explicit: share stateless services, keep request- and tenant-bound state inside its boundary, never let a longer-lived component retain a shorter-lived one, and give shared mutable state an owner and a concurrency policy. It is not a requirement to register everything as a singleton.

## How it works

1. **Declare the units.** A small `acima.config.json` names each module, its units, their roles (`contracts`, `implementation`, `host`, …) and their paths. This is the only thing ACIMA asks you to write.
2. **Run an enforcer.** The reference enforcer for your language reads that map and the source, then reports violations of the portable rules: an implementation importing another implementation, a contract that has grown dependencies, a module reaching around a contract.
3. **Read an honest report.** Every rule the run did not decide is listed as *not evaluated*. There is no health score, because a number that hides which rules were skipped is worse than no number.
4. **Freeze, then ratchet.** In an existing codebase, existing findings become owned, expiring, fingerprinted waivers. The gate then fails on **new** violations only — so the count can only go down.

The claim layer computes `FULL CONFORMANCE` or `PARTIAL ASSESSMENT` from the run and the manual evidence, and binds the result to the repository, commit, catalog, configuration and source inventory it measured. Authors do not choose the label, and an older full result is historical evidence, not current conformance.

## Five-minute quickstart

You need Python 3.9+ and, for the language you enforce, that language's toolchain.

```bash
git clone https://github.com/c-lombardi/ACIMA.git
cd ACIMA

# 1. See the reference implementations enforce their own rules
python3 conformance/run.py python dotnet

# 2. Assess any repository, read-only, before deciding anything
python3 tools/acima.py assess --root /path/to/your/repo
```

The second command changes nothing. It reports the repository's languages, whether an ACIMA unit map exists, which requirements are applicable, what the enforcer found, what needs human review, and whether ACIMA is a fit — or why it is not.

If a repository has no unit map yet, the assessment says `NEEDS_UNIT_MAP` rather than pretending the code is clean. Creating that map is a conversation about ownership, not an automated step.

### Watch a violation appear and get fixed

```bash
python3 tools/acima_walkthrough.py
```

One real `D001` violation — an implementation importing another implementation — is introduced, detected with its evidence, and repaired.

## Assessing an existing application

The default workflow is deliberately small:

| Step | Command | What you get |
|---|---|---|
| Inventory | `acima inspect --root .` | languages, declared units, enforcer availability |
| Assess | `acima assess --root .` | read-only compatibility assessment with findings and gaps |
| Report | `acima report --root .` | evidence report, including unevaluated rules |

Adoption is a separate, explicit decision. It adds a unit map, a measured baseline, owned waivers, a CI gate and a ratchet — the full process is in the [adoption skill](skills/acima-adoption/SKILL.md). Nothing in the assessment phase modifies your code, your build or your CI.

Assessment requires no authorization to modify anything. Adoption does: the workflow is assessment,
proposal, explicit authorization of a named scope, approved implementation, then verification and
handoff. Partial approval is supported, and plans and communication documents are optional unless
you ask for them. Merging and releasing always remain yours.

## Language support

| Language | Enforcement | Status |
|---|---|---|
| C# / .NET | reference enforcer, 23 of 41 automated rules | implemented and verified on the clean example and 23-rule gallery; eighteen automated rules (the five tier rules, two explicit-input, two value, two composition, two functional-capture, three lifecycle, and `N001`–`N002`) and the fourteen manual rules report `executed: false` |
| TypeScript | reference enforcer, 41 automated rules | implemented and verified against its own fixtures; fourteen manual rules remain unevaluated |
| Python | reference enforcer, 41 automated rules | implemented and verified against its own fixtures; fourteen manual rules remain unevaluated |
| Go | reference enforcer, 23 of 41 automated rules | implemented and verified on the clean example and 23-rule gallery; eighteen automated and fourteen manual rules report `executed: false` |
| Java | profile documented, no enforcer | not supported: an assessment fails closed rather than reporting clean |

Two limits matter more than the table:

- The enforcers analyse **source and project metadata**, not runtime behaviour. They do not prove isolation, type correctness or framework behaviour.
- Fourteen rules always require human evidence: `C003`, `C007`, `C008`, `L004`, `A002`, `A004`, `A010`–`A015`, `G004` and `N003`. A run that reports zero findings has not evaluated them.

Independent validation is **incomplete**. The standard has been exercised against its own examples and a small number of external repositories, not against independent evaluators. [`docs/status.md`](docs/status.md) separates verified from proposed capability, and [`docs/product-contract.md`](docs/product-contract.md) lists the release gates and what is still missing.

## Who it is for

- **Engineering leaders** who need architectural expectations that survive growth and turnover, not another document.
- **Staff engineers and architects** who want boundaries checked in CI instead of argued about in review.
- **Teams using AI coding agents** who need constraints an agent can read, follow and be verified against.

## Documentation

| Start here | For |
|---|---|
| [`docs/README.md`](docs/README.md) | where the standard lives, reading order, how a normative change is made |
| [`docs/start/quickstart.md`](docs/start/quickstart.md) | a guided first hour |
| [`docs/rules/index.md`](docs/rules/index.md) | every rule, with violation and fix examples |
| [`docs/languages/index.md`](docs/languages/index.md) | how the rules appear in your language |
| [`docs/guides/effects-and-atomicity.md`](docs/guides/effects-and-atomicity.md) | who owns an effect, and when retry, duplicate, transaction and cancellation rules apply |
| [`skills/acima-adoption/SKILL.md`](skills/acima-adoption/SKILL.md) | the agent workflow for assessing and adopting |
| [`conformance/README.md`](conformance/README.md) | how enforcement is verified |

## Contributing

Counterexamples are the most valuable contribution. If ACIMA's requirements exclude a legitimate architecture, or an enforcer reports a violation that is not one, that is a defect in the standard or its enforcement — [open an issue](https://github.com/c-lombardi/ACIMA/issues) with the repository shape and the finding.

Rule IDs are never renumbered. A meaning change requires a catalog version change, a skill re-pin and a migration note.

## License

See the repository license for usage and contribution terms.
