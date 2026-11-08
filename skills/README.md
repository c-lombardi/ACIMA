# Agent skills

Portable instructions for coding agents (Claude Code, Codex, Cursor, and anything that reads a `SKILL.md`). ACIMA ships one skill because adoption is the part of the standard that needs judgement: reading an existing architecture, proposing boundaries, and knowing when to stop.

| Skill | Use it for |
|---|---|
| [`acima-adoption`](acima-adoption/README.md) | assessing, adopting, and maintaining ACIMA in a greenfield or brownfield repository |

## Install

```bash
# Claude Code, project scope
mkdir -p .claude/skills && cp -R skills/acima-adoption .claude/skills/

# or user scope
cp -R skills/acima-adoption ~/.claude/skills/
```

Other agents: point them at `acima-adoption/SKILL.md` and allow them to read that directory. The skill needs only Python 3.9+ for its preflight.

## How the skill relates to the other layers

- It **reads** the standard ([`../docs/`](../docs/README.md)) and never redefines it.
- It **runs** the enforcers ([`../examples/`](../examples/README.md)) and reports their findings verbatim.
- It is **not** the authority on conformance: [`../conformance/`](../conformance/README.md) computes the claim class, and `SKILL.md` says so explicitly.

`manifest.json` pins the rule catalog hash and the skill version. When the catalog changes, the preflight blocks until the skill is re-calibrated — a skill that silently follows a moving standard gives confident, outdated advice.

## Conventions

- `SKILL.md` is the only required file; depth lives in `references/`, loaded on demand.
- Scripts are read-only by default, standard-library only, and exit `0` ready / `1` blocked / `2` tool failure.
