# Adding a language

ACIMA is language-neutral in intent and per-language in expression. Adding a language must not change
the standard — only how it is expressed and enforced. This chapter is the checklist for a new profile.

## 1. What a new language must deliver

| Deliverable | Location | Requirement |
|---|---|---|
| **Profile** | `docs/languages/<language>.md` | the five sections every profile has (layout, toolchain, arch tests, analyzers, pitfalls) |
| **Reference implementation** | `examples/<language>/` | three modules (catalog, orders, payments), a kernel, a host, behaviour tests |
| **Architecture enforcer** | `examples/<language>/tools/` | implements the 23 portable rules, emits [the finding format](../standard/07-executable-governance.md#72-the-finding-format) |
| **`acima.config.json`** | `examples/<language>/` | declares units, level, excludes |
| **Violation gallery** | `examples/<language>/violations/` | one fixture per rule, plus `expected.json` |
| **Conformance entry** | `conformance/run.py` | one line adding the language to the run |
| **Rule-id mapping** | profile, §2 and §4 | for the four non-portable rules, say how this language covers them |

## 2. The portable rules

A language is conformant with the reference enforcer when it implements these 23 rules with these ids:

```
D001 D002 D003 D004 D005 D006 D007 D008 D009
L001 L002 L003
C001 C002 C003 C004 C005 C006 C007
A001 A003
G001 G002 G003 G005
```

The four that are not portable — `L004`, `A002`, `A004`, `G004` — are documented per language and covered
by ecosystem tooling or release review. A new profile must say which, and why.

## 3. The finding format is not negotiable

Every enforcer must implement:

```
<enforcer> --root <dir> [--config <path>] [--format json|text] [--level L1|L2|L3]
```

with the exit codes `0` / `1` / `2` and the JSON shape from
[07 · The tool interface](../standard/07-executable-governance.md#73-the-tool-interface).

If a language cannot produce a finding for a rule (no parser, no visibility model), the enforcer must
report the rule with `"executed": false` and `severity: "info"` rather than omitting it. A language that
silently checks less than it claims is worse than one that checks less and says so.

## 4. The gallery is the proof

A language profile is only complete when every implemented rule has a fixture that **breaks it on
purpose** and an expected finding in `violations/expected.json`:

```json
{
  "ACIMA-D001": ["violations/d001_impl_import.ts"],
  "ACIMA-C001": ["violations/c001_mutable_contract.ts"]
}
```

`conformance/run.py` asserts that the enforcer produces exactly those rule ids at those paths — no
missing rule, no extra finding. That single assertion is what makes "the same rules in every language"
a fact rather than a claim.

## 5. Order of work

1. Write the profile's layout section first. If you cannot describe the units, the language is not ready.
2. Build the three-module example. It will force every design question the profile has to answer.
3. Write the enforcer against the example: it must produce **zero** findings on the good code.
4. Write the gallery, one fixture per rule. Every fixture should be the smallest code that violates the
   rule and compiles in isolation (or is excluded from the build).
5. Wire it into `conformance/run.py` and get the run green.
6. Then write the analyzers section — after you know what the runner cannot catch in that language.

Step 6 last is deliberate: the ecosystem tooling is the author-time complement, and its value is only
visible once you know the gaps.

## 6. What must not change

- **Rule ids and meanings.** A new language never renumbers a rule.
- **The matrix.** The allowed edges are the standard, not a suggestion.
- **The finding format.** Diverging breaks the single gate.
- **The waiver format.** Ownership and expiry are language-independent.

If a language genuinely cannot express a rule — for example, a purely functional language with no
mutable state — the profile says `not applicable`, and the enforcer reports `executed: false` with that
reason. "Not applicable" and "not implemented" must never be confused.
