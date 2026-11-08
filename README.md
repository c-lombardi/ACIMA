# ACIMA

**Architecture that enforces itself.**

AI is making it faster than ever to generate, modify, and ship software. But generating code faster does not automatically produce systems that are easier to maintain.

Without clear architectural boundaries, AI-generated code can introduce the same problems that affect traditionally developed software: unnecessary dependencies, tightly coupled modules, duplicated logic, unclear ownership, and changes that have unintended consequences elsewhere in the system.

**ACIMA helps engineering teams move faster without losing control of their architecture.**

ACIMA (Autonomous, Contract-Isolated, Immutable Modular Architecture) is an architectural standard that defines how software modules should be structured, how they may interact, and how their boundaries are enforced through executable checks.

It also includes an integrated AI agent skill that helps developers assess, adopt, and maintain the architecture in real-world codebases.

## Why ACIMA?

AI coding tools increase the amount of code teams can produce. They also increase the importance of having consistent architectural rules that developers and agents can understand and follow.

ACIMA provides a common architectural standard that can be applied to both human-written and AI-generated code.

The goal is to make systems easier to:

- **Change independently.** Modify one module without unnecessarily affecting others.
- **Understand.** Make ownership, responsibilities, and public interfaces explicit.
- **Test.** Isolate module behavior behind well-defined contracts.
- **Extend.** Add capabilities without creating uncontrolled dependencies.
- **Maintain.** Prevent architectural erosion as teams and codebases grow.
- **Govern.** Make architectural violations and approved exceptions visible.
- **Develop with AI.** Give coding agents explicit architectural constraints they can follow and verify.

Rather than relying exclusively on documentation, conventions, or code review, ACIMA makes supported architectural requirements executable.

## How ACIMA works

ACIMA brings together three complementary capabilities.

### 1. An architectural standard

ACIMA defines the rules governing module ownership, contracts, dependencies, immutability, and independent evolution.

Modules own their implementations and expose explicit contracts. Other modules depend on those contracts rather than reaching into implementation details.

The result is a system with clearer boundaries and fewer opportunities for unintended coupling.

### 2. Automated architectural enforcement

ACIMA provides language-specific architecture tests and enforcement tools that inspect a codebase for violations of the standard.

These checks can be incorporated into development workflows and CI pipelines so that supported architectural violations are identified before they become established patterns.

The enforcement model includes:

- Explicit architectural rules with consistent identifiers.
- Machine-readable findings with evidence and remediation guidance.
- Configurable conformance levels.
- Documented exceptions with ownership and expiration.
- Positive and negative test fixtures for verifying enforcement behavior.

Not every architectural decision can be automated. ACIMA distinguishes between requirements that can be mechanically verified and those that require human review.

### 3. An integrated AI adoption skill

**ACIMA includes an agent skill designed to help developers and AI coding agents apply the standard to real software projects.**

The `acima-adoption` skill provides a structured process for understanding an existing codebase, planning architectural changes, introducing enforcement, and maintaining the architecture over time.

It supports workflows for:

- **Greenfield projects:** Establish architectural boundaries from the beginning.
- **Brownfield projects:** Assess existing architecture, establish a baseline, and introduce improvements incrementally.
- **Ongoing development:** Evaluate changes against ACIMA and maintain architectural compliance.

The skill guides the agent through:

1. Inspecting the repository and verifying its compatibility with the ACIMA standard.
2. Identifying the existing architecture and module boundaries.
3. Developing an adoption plan appropriate to the codebase.
4. Establishing an initial architectural baseline.
5. Introducing changes incrementally rather than requiring a rewrite.
6. Integrating architectural checks into the development workflow.
7. Verifying results and documenting outstanding exceptions.

The skill is designed to work with Claude Code, Codex, Cursor, and other coding agents that support the `SKILL.md` convention.

**The agent helps apply the architecture. The enforcement tools verify supported requirements. Human owners remain responsible for architectural decisions and exceptions.**

See the [ACIMA adoption skill](skills/acima-adoption/SKILL.md).

## Related architectures, methodologies, and tools

ACIMA builds on established software architecture principles and engineering practices. It brings them together into a consistent standard with explicit module boundaries, enforceable contracts, cross-language rules, and an AI-assisted adoption workflow.

It is complementary to these approaches, not a replacement for them.

| Architecture or practice | Relationship to ACIMA |
|---|---|
| **Clean Architecture** | Reinforces separation of concerns and controlled dependency direction. ACIMA extends the focus to ownership and isolation between modules. |
| **Hexagonal Architecture (Ports and Adapters)** | Aligns with explicit interfaces and controlled communication across boundaries, keeping implementations separate from the contracts consumers depend on. |
| **Domain-Driven Design (DDD)** | Supports clear domain ownership and bounded contexts, helping prevent unrelated business capabilities from becoming tightly coupled. |
| **Modular Monolith Architecture** | Provides a natural deployment model for ACIMA. Modules maintain explicit boundaries while sharing an application and deployment environment. |
| **Explicit Contract Projects** | Builds on the practice of separating public contracts from private implementations, making module dependencies intentional and easier to govern. |
| **Architecture as Code and Fitness Functions** | Applies executable architectural rules to continuously evaluate whether a codebase conforms to its intended design. |
| **ArchUnit, NetArchTest, and similar tools** | Follows the established practice of testing architecture through code. ACIMA adds a portable rule catalog, consistent findings, conformance expectations, and cross-language reference implementations. |

### What makes ACIMA different?

These approaches address important aspects of software design, modularity, and architecture enforcement. ACIMA brings them together under one standard that can be applied consistently across supported languages and repositories.

Its emphasis is on:

- **Contract isolation:** Modules expose explicit contracts rather than implementation details.
- **Independent ownership:** Modules own their implementations, data boundaries, and configuration.
- **Controlled dependencies:** Cross-module dependencies follow defined architectural rules.
- **Immutable contracts:** Contract changes are explicit and subject to compatibility expectations.
- **Consistent enforcement:** Architectural findings use shared rule identifiers and reporting conventions across language implementations.
- **AI-assisted adoption:** An integrated agent skill helps developers and coding agents understand, assess, adopt, and maintain the architecture.

ACIMA does not require Clean Architecture, microservices, a particular domain-modeling methodology, or a specific technology stack. It provides architectural constraints that can complement the design approach an engineering team already uses.

## Adopting ACIMA

ACIMA is intended to work with both new and existing systems. Adopting it does not require an organization to rewrite its applications or change its technology stack.

A typical adoption follows this progression:

| Step | Activity | Outcome |
|---|---|---|
| 1. Assess | Inspect the existing repository and architecture. | Understand the current state and compatibility. |
| 2. Plan | Identify module boundaries and prioritize improvements. | Establish an incremental adoption plan. |
| 3. Baseline | Run the applicable architectural checks. | Record existing violations and exceptions. |
| 4. Introduce | Improve one architectural boundary at a time. | Reduce existing coupling without a wholesale rewrite. |
| 5. Enforce | Integrate supported checks into CI. | Prevent new violations from being introduced unnoticed. |
| 6. Maintain | Review findings, exceptions, and architectural changes. | Keep the architecture aligned with the system as it evolves. |

### Get started with the adoption skill

Clone the repository:

```bash
git clone https://github.com/c-lombardi/ACIMA.git
```

Install the skill in a Claude Code project:

```bash
mkdir -p .claude/skills
cp -R ACIMA/skills/acima-adoption .claude/skills/
```

For other coding agents, provide access to `skills/acima-adoption/SKILL.md` and its supporting directory.

With the target repository open in your coding agent, start with:

```text
Use the ACIMA adoption skill to assess this repository.

Start with the required preflight and compatibility checks.
Identify the current architecture, determine whether this
repository is supported, and produce an adoption assessment.

Do not modify the codebase until I have reviewed and approved
the proposed adoption plan.
```

The skill includes additional instructions, scripts, references, and templates for carrying out the adoption process.

For manual preflight, run the following from the cloned ACIMA repository:

```bash
python3 skills/acima-adoption/scripts/preflight.py \
  --project /path/to/your/project \
  --format text
```

### Verify the reference implementations

ACIMA includes reference implementations and conformance tests for its implemented language profiles.

From the ACIMA repository:

```bash
python3 conformance/run.py
```

This runs the available conformance suites and checks their results against the documented violation fixtures.

See the [language profiles](docs/) and [conformance implementation](conformance/) for language-specific instructions.

## Language support and project status

ACIMA is currently published as a draft standard. Its reference implementations and adoption capabilities are evolving.

| Language | Architecture enforcement | Reference implementation |
|---|---|---|
| C# / .NET | Available | Available |
| TypeScript | Available | Available |
| Python | Available | Available |
| Go | Available | Available |
| Java | Profile documented | Not yet implemented |

Enforcement coverage varies by language and architectural rule. Some requirements require manual evidence or human review rather than automated checks.

The current adoption skill also has documented compatibility limitations. In particular, the service-topology workflow and Java enforcement are not yet supported by the skill. Review the documentation before adopting ACIMA in those environments.

A successful test run against a reference implementation should not be interpreted as proof that every architectural requirement is automatically enforceable in every target repository.

## Who is ACIMA for?

**CTOs and engineering leaders**

Establish consistent architectural expectations across teams, improve visibility into architectural risk, and reduce reliance on informal conventions that are difficult to maintain as organizations grow.

**Engineering directors and managers**

Give teams a shared standard for designing and evolving software while introducing measurable architectural controls into the development lifecycle.

**Software developers and architects**

Work with clearer module boundaries, explicit contracts, and actionable architectural feedback instead of discovering structural problems late in development.

**AI-assisted engineering teams**

Give coding agents a documented architectural standard and an adoption workflow that helps keep generated code aligned with the intended system design.

## Documentation and resources

- [Architectural standard](docs/)
- [Principles and rules](docs/)
- [ACIMA adoption skill](skills/acima-adoption/)
- [Skill installation and usage](skills/README.md)
- [Reference implementations](examples/)
- [Conformance tests](conformance/)

## Contributing

ACIMA is an evolving architectural standard. Contributions, implementation feedback, additional language support, and real-world adoption experience are valuable.

The objective is not to impose unnecessary structure on every codebase. It is to establish architectural boundaries that make software easier to change, understand, and maintain as systems and engineering teams grow.

## License

See the repository license for usage and contribution terms.
