# AI agent architectural guidance

AI instructions are a mandatory adoption deliverable, not a generic appendix. Generate or update
them only after the approved module map and actual enforcement exist.

## Discovery

Recognize root `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `COPILOT_INSTRUCTIONS.md`,
`.github/copilot-instructions.md`, `.github/instructions/`, `.cursor/rules/`, and nested scoped
files. Existence is not proof that an agent consumes a file. Record the convention, primary file,
secondary mechanisms and the consumption caveat. Preserve all existing user-authored content.

Selection:

- Extend the established primary convention rather than creating a competing root file.
- Prefer an existing root `AGENTS.md`; otherwise respect `CLAUDE.md`, `GEMINI.md`, or Copilot.
- Multiple active mechanisms get one complete instruction set and short supported references from
  the others, not a duplicated copy of every rule.
- With no recognized convention, create root `AGENTS.md`.

## Generated structure

The root file is concise and operational. It establishes ACIMA as mandatory, names the authoritative
map and support files, gives the ownership snapshot, lists the actual local/CI checks, and states the
approval boundary. It references the authoritative map instead of copying the whole configuration.

Support files live under `docs/architecture/acima/`:

- `agent-architecture-guidance.md` — ownership, contracts, dependency, data/configuration,
  composition and profile guidance.
- `enforcement.md` — actual commands, test evidence, CI status and failure behavior.
- `judgment-guidance.md` — every catalog requirement, including automated, partially automated and
  wholly manual obligations, with a judgment prompt, sound response and escalation rule.
- `architectural-workflow.md` — the proportionate 12-step decision process.

The generated block is delimited so it can be refreshed without touching user content. Support
documents must be actual files, not vague references. Never claim an enforcer or CI run that was not
recorded.

## Validation and approval

Validate that:

- the primary file and all support files exist;
- the block, references and authoritative map are present;
- every current catalog rule appears in judgment guidance;
- documented local commands match the enforcement record;
- existing user content is preserved;
- unresolved ownership or design decisions remain explicit;
- source hashes of the map, enforcement, verification and CI are current.

A valid file is not proof of agent behavior. Representative feature, dependency, contract, data,
state and composition tasks should be evaluated manually where feasible. In guided mode, modifying
existing user instructions requires approval; generating a proposal does not. In full automation,
apply within the authorized adoption scope. After remediation, refresh the guidance from the final
map and fresh verification.
