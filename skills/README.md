# Agent skills

Skills in this repository are portable instructions for coding agents (Claude Code, Codex,
Cursor, and anything that reads a `SKILL.md`). Each skill is a directory with a `SKILL.md` entry
point, optional `references/` loaded on demand, deterministic `scripts/`, and `assets/` templates.

| Skill | Use it for |
|---|---|
| [`acima-adoption`](acima-adoption/SKILL.md) | applying, auditing and governing ACIMA in a greenfield or brownfield repository |

## Installing a skill

Copy or symlink the skill directory into the location your agent reads:

```bash
# Claude Code, project scope
mkdir -p .claude/skills && cp -R skills/acima-adoption .claude/skills/

# or user scope
cp -R skills/acima-adoption ~/.claude/skills/
```

Other agents: point them at `skills/acima-adoption/SKILL.md` and allow them to read the
directory. The skill itself needs only Python 3.9+ for its preflight.

## Conventions

- `SKILL.md` is the only required file and stays under ~500 lines; depth lives in `references/`.
- `manifest.json` pins the rule catalog hash, standard version and enforcer paths the skill was
  written against. The preflight fails when the standard moves, so advice cannot go stale silently.
- Scripts are read-only by default, stdlib-only, and exit `0` ready / `1` blocked / `2` tool failure.
