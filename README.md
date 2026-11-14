# ACIMA

**Architecture that enforces itself.**

AI is making it faster to generate, modify and ship software. It is not making it easier to keep that software internally consistent. Code generated at speed inherits the same failure mode as code written by hand, only faster: a module reaches into another module's implementation, and the boundary stops meaning anything.

Documentation does not stop this. Review does not scale to it. ACIMA does, because an ACIMA boundary is **executable** — a rule a build can fail on.

ACIMA (Autonomous, Contract-Isolated, Immutable Modular Architecture) is an architectural standard for software built and changed by people and AI agents together. It defines how modules are structured, what they may depend on, and how those limits are checked automatically.

ACIMA applies to any software composition with identifiable ownership: a package or library, a
framework or SDK, an application, a modular monolith, a distributed system, a service, a worker, or a
mixture. It does not require a service, an application entry point, a deployment unit or a single
composition host. A module is an ownership boundary; a project, package, service, process or host is
only one possible representation. The optional profiles add requirements for genuinely distinct
contexts; neither service topology nor library distribution is the default.

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
| An architectural standard with its own portable boundary requirements; independent of framework, deployment model and domain methodology | A replacement for your architecture, or a guarantee that every existing architecture already satisfies it |

## What ACIMA requires — and what stays yours

ACIMA defines portable architectural requirements: module ownership, explicit contracts,
dependency isolation and direction, data and configuration ownership, and controlled composition.
Applicable lifecycle, state and effect ownership requirements apply as well. Those requirements
belong to ACIMA; they are not derived from whatever architecture a team has already chosen.

Clean Architecture, Hexagonal Architecture, domain-driven design, a modular monolith and
microservices can often satisfy them, but compatibility is evaluated against the actual
requirements, not assumed from the architecture's name. Some ACIMA requirements are intentionally
stricter than common guidance in those approaches, and a compatible design may need a limited
boundary adaptation. ACIMA complements them rather than replacing or ranking them.

ACIMA deliberately leaves the overall architecture family, decomposition above its module
requirements, internal module design, language and framework, database, transport, infrastructure,
deployment topology, team structure and folder layout to the team. That freedom is not an exemption
from the normative requirements: a design that conflicts with one must adapt, use the standard's
exception process, or conclude that ACIMA is not a fit.

```
Your team decides                    architecture family · language and framework
                                     database, transport and infrastructure
                                     deployment · internal module design · layout

ACIMA requires                       ownership · contracts · dependency isolation
                                     data and configuration ownership
                                     controlled composition · lifecycle and effects

Language support                     analyzers · architecture tests · CI gate
                                     · AI adoption guidance
```

Where ACIMA is stricter — contracts that cannot reference other contracts, no cross-module
in-process transaction, zero-dependency contracts — the requirement is stated, justified
independently, and scoped to boundaries rather than internal design. A departure is an owned
waiver, never a silent exception. The full mapping, including what ACIMA does not decide, is in
[Architecture compatibility](docs/guides/architecture-families.md).

These obligations are expressed as eleven base principles and a 56-rule catalog — 42 of which the reference enforcers decide from source (Python covers all 42, TypeScript 41, Go 27 and .NET 42), and fourteen of which require recorded human evidence. P15 adds **owned effects**: every externally visible effect has an owner, visible semantics, a truthful outcome and evidence proportionate to its criticality. It also makes state mutation, consistency and observability explicit: one owner per consistency boundary, a declared guarantee instead of assumed atomicity, and telemetry that observes behaviour rather than replacing it. The obligations are conditional on the design: retries, transactions, idempotency keys and cancellation are required only where the operation's contract makes them applicable.

The catalog also makes **instance lifetime and state ownership** explicit: share stateless services, keep request- and tenant-bound state inside its boundary, never let a longer-lived component retain a shorter-lived one, and give shared mutable state an owner and a concurrency policy. It is not a requirement to register everything as a singleton.

## How it works

1. **Declare the boundaries.** A small `acima.config.json` names each module, the units that represent it, their roles (`contracts`, `implementation`, optional `host`, …) and their paths. A module may span several units; a library may declare no host.
2. **Run an enforcer.** The reference enforcer for your language reads that map and the source, then reports violations of the portable rules: an implementation importing another implementation, a contract that has grown dependencies, a module reaching around a contract.
3. **Read an honest report.** Every rule the run did not decide is listed as *not evaluated*. There is no health score, because a number that hides which rules were skipped is worse than no number.
4. **Freeze, then ratchet.** In an existing codebase, existing findings become owned, expiring, fingerprinted waivers. The gate then fails on **new** violations only — so the count can only go down.

The claim layer computes `FULL CONFORMANCE` or `PARTIAL ASSESSMENT` from the run and the manual evidence, and binds the result to the repository, commit, catalog, configuration and source inventory it measured. Authors do not choose the label, and an older full result is historical evidence, not current conformance.

## The adoption journey

ACIMA uses one journey in guided and automated adoption. These phase names are canonical: the skill,
the CLI and the HTML report use them unchanged.

| Phase | ACIMA does | You see | You decide | Done when | Next |
|---|---|---|---|---|---|
| **Start** | Identifies the repository and asks one plain mode question when none is chosen | Guided or automated adoption | The mode | The repository and mode are known | Assess the repository |
| **Phase 1 — Assess** | Read-only discovery, the complete 56-requirement review, supported checks | What exists, what was found, what remains unknown | Nothing | Every requirement has an evidence-backed disposition | Explain fit and propose a scope |
| **Phase 2 — Explain and propose** | Fit, level in practical terms, scoped proposal, six-page report | A recommendation, exact changes, costs, risks, limits | Nothing | Every statement traces to evidence or is marked unknown | Review the report and proposed ownership |
| **Phase 3 — Review and authorize** | Presents the exact report and records approval provenance | Named paths, stages and boundaries to approve, change or decline | The exact scope | An explicit approval matches the current report and repository | Implement only approved work |
| **Phase 4 — Implement** | Executes only approved stages and paths | What is changing, where, and what happens next | Any new path, dependency or boundary | Each approved stage passed its checks or is precisely blocked | Verify the result |
| **Phase 5 — Verify and hand off** | Fresh checks, evidence reconciliation, honest status | What changed, what passed, what remains unproven | Merge, release or publication, separately | The handoff matches actual evidence | Take one evidence-backed next action |

**Guided adoption** pauses at each review point: the module map, the proposal and report, CI, optional
adoption notifications, optional agent guidance, then each implementation stage. **Automated adoption**
performs the same assessment and prepares the same package before one consolidated review, then carries
out only the stages the owner selects. Both modes use identical evidence quality, ownership rules and
approval authority. Automated preparation never approves an inferred boundary or authorizes an unseen path.

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

ACIMA's requirements are language-neutral; what a given enforcer can decide automatically varies.
Missing language coverage is reported as not executed, never as a pass.

| Language | Enforcement | Status |
|---|---|---|
| C# / .NET | reference enforcer, 42 of 42 automated rules | implemented and verified on the clean example and 42-rule gallery; the fourteen manual rules report `executed: false` |
| TypeScript | reference enforcer, 41 of 42 automated rules | implemented and verified against its own fixtures; `D017` and the fourteen manual rules remain unevaluated |
| Python | reference enforcer, 42 automated rules | implemented and verified against its own fixtures; fourteen manual rules remain unevaluated |
| Go | reference enforcer, 27 of 42 automated rules | implemented and verified on the clean example and 27-rule gallery; fifteen automated and fourteen manual rules report `executed: false` |
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
