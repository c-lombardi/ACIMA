# Changelog

All normative changes to the ACIMA standard. The machine-readable catalog is
[`tools/acima-spec/rules.json`](tools/acima-spec/rules.json); this file explains *why* it changed and
what an adopting repository has to do about it.

## 1.1.0-draft.1 — third-party library governance

**Version change:** MINOR. `1.0.0-draft.1` → `1.1.0-draft.1`. Five rules added; no rule removed,
renumbered or weakened. The catalog total goes from 29 to 34 and the portable set from 23 to 28.

### Why

The only third-party protection in 1.0 was a prohibition *inside* contracts (`D004`, `L002`, `D007`)
plus a hardcoded database-client list in `L001`. §11.7 described the right shape — a vendor contract
project plus an adapter — but only under service topology, which the adoption skill marks
`NOT SUPPORTED`. The result was that a UI integration such as Monaco could be imported anywhere and
the gate stayed silent. 1.1 closes that gap in the base profile.

### Added

| Rule | Title | Severity now | Severity at 2.0.0 | Level |
|---|---|---|---|---|
| `L005` | Integration library used outside its declared adapter | `warning` | `error` | L1 |
| `L006` | Adapter without a port | `error` | `error` | L1 |
| `L007` | Vendor type outside the adapter | `warning` | `error` | L1 |
| `D010` | Port exposes a vendor shape | `error` | `error` | L1 |
| `G006` | Undeclared external dependency | `warning` | `error` | L1 |

Three declared tiers (`platform`, `integration`, `utility`) and two roles (`adapter`, `port`), all
configured in `externals` in `acima.config.json` — declared per package, never inferred. See chapter
4 §4.10, chapter 5 §5.12, chapter 7 §7.4 and chapter 8 §8.10.

### The severity ratchet

The design target for all five rules is `error` at L1. The three that change how existing code is
*organized* rather than whether it compiles ship as `warning` for one minor release, because a
repository with a working build should be able to declare its tiers before the gate starts failing
it. `L006` and `D010` ship as `error` immediately: an adapter with no port produces no governance at
all, and a port carrying a vendor shape is the same defect family as `D002`/`D004`, which are already
errors.

`rules.json` records the ratchet as `severityRatchet: { "to": "error", "at": "2.0.0" }` on `L005`,
`L007` and `G006`. A run at 1.x reports them; a 2.0 catalog reports them as errors and the gate
blocks. Nothing else about the rules changes.

### Not changed

- `D004`, `L001`, `L002` and `D007` are unchanged. Contracts and the shared kernel remain
  third-party-free; `D004` still fires on any package in a contracts unit.
- `L001` keeps its database semantics. An `externals` entry with `tier: integration` supersedes the
  `L001` token list **for that package only**, because `L005`/`L007` are the sharper rules for a
  package with a declared seam.
- The library profile (chapter 12) is unchanged. It governs a repository that *publishes* a library;
  the new rules govern an application reaching a vendor.

### Migration

1. **Declare the tiers.** `python3 tools/acima.py externals --root . --write-draft` generates one
   entry per manifest package. Every entry starts as `tier: utility`, `owner: UNASSIGNED`. Re-running
   it never overwrites an existing entry.
2. **Review each entry.** Set `owner`, `reason`, `reviewedOn` and `expires`. Classify honestly:
   `platform` for runtime/framework surfaces, `integration` for anything with IO, state, a wire
   format or a third-party UI surface, `utility` for pure helpers.
3. **Build the seams.** For each `integration` package, add the port unit and the adapter unit and
   complete `adapter`/`port` in the entry. `L006` fails until both exist; the adapter is the only
   place allowed to import the vendor (`L005`).
4. **Move the imports.** Application, domain, contracts and host code call the port. Map vendor
   types inside the adapter (`L007`); keep the port free of vendor names (`D010`).
5. **Run the swap drill** on a fixture or a small module (chapter 8 §8.10). Keep the output as
   evidence next to the run artefact.
6. **Expect warnings, not failures**, for `L005`, `L007` and `G006` until 2.0.0. They are reported
   and countable; they do not block merges at 1.x.

### Language scope

`L005`, `L006`, `L007`, `D010` and `G006` are implemented by the **Python** and **TypeScript**
reference enforcers, with gallery fixtures and a positive fixture
(`conformance/fixtures/third-party/python`). The **Go** and **.NET** enforcers report the five rules
`executed: false` with that reason; a Go or .NET repository needs manual evidence for them or the
scoped statement in §8.10. The swap drill is implemented for Python fixtures in this revision.

### Artefacts updated in this change

`tools/acima-spec/rules.json` (catalog + `thirdPartyTiers`), `docs/rules/{index,dependency,autonomy,README}.md`,
chapters 2, 4, 5, 7, 8 and 11, `conformance/coverage.json`, the Python and TypeScript enforcers and
their galleries, `conformance/swap_drill.py` and `conformance/test_third_party_governance.py`,
`tools/acima.py` (`externals`), `docs/commands.md`, `skills/acima-adoption/manifest.json`,
`skills/acima-adoption/SKILL.md` and the regenerated skill bundle.
