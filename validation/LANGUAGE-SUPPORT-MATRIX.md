# Language Support Matrix

**Status:** IN PROGRESS — internal review only
**Rule source:** `tools/acima-spec/rules.json`; `conformance/coverage.json`
**Legend:**

- **F** — reference enforcer executes the rule and the gallery fires it. This means
  *implemented and fixture-verified*, not semantically complete for every language form.
- **P** — executes, but has a known semantic limitation (heuristic, denylist, static-only,
  public-API profile, or limited edge set).
- **M** — no automated rule; manual/native analysis or review required.
- **N** — no implementation for that language.

**Important:** Java is `N` for every base rule. The Java profile is documented only. A Java
assessment must fail closed; it must never be reported as clean.

## Base catalog by language

| Rule | Python | TypeScript | Go | .NET | Java | Known limitation |
|---|---|---|---|---|---|---|
| D001 | F | F | F | F | N | Static imports/project references; not runtime coupling |
| D002 | F | F | F | F | N | Indirect forms via generated code may escape |
| D003 | F | F | F | F | N | Path/alias resolution varies |
| D004 | F | F | F | F | N | Package classification; framework allowlists |
| D005 | F | F | F | F | N | Graph closure; self-references legal |
| D006 | F | F | F | F | N | Host classification depends on config |
| D007 | F | F | F | F | N | Kernel admission is human |
| D008 | F | F | F | F | N | Duplicate paths reported; closure semantics |
| D009 | P | P | P | P | N | Public/visibility semantics differ |
| L001 | P | P | P | P | N | Four layer edges only |
| L002 | P | P | P | P | N | Framework/type list is finite |
| L003 | P | P | P | P | N | Public API profile only TS/.NET |
| L004 | M | M | M | M | N | Not executed |
| C001 | F | F | F | F | N | Language field/property semantics |
| C002 | F | F | F | F | N | Aliasing/copying semantics |
| C003 | M | M | M | M | N | Not executed; semantic judgment |
| C004 | P | P | P | P | N | Denylist; unlisted APIs escape |
| C005 | P | P | P | P | N | Known persistence type names |
| C006 | F | F | F | F | N | Explicit untyped forms; aliases |
| C007 | M | M | M | M | N | Not executed |
| A001 | P | P | P | P | N | Static SQL/ORM only; runtime grants manual |
| A002 | M | M | M | M | N | Not executed |
| A003 | F | F | F | F | N | Hidden/global state may escape |
| A004 | M | M | M | M | N | Not executed |
| G001 | F | F | F | F | N | Reason/owner quality is human |
| G002 | F | F | F | F | N | Date parsing/timezone |
| G003 | P | P | P | P | N | Documentation presence, not correctness |
| G004 | M | M | M | M | N | Not executed; no API baseline |
| G005 | F | F | F | F | N | Classification depends on config |

### Counts

| Language | Automated (F/P) | Not executed (M) | Total catalog |
|---|---:|---:|---:|
| Python | 23 | 6 | 29 |
| TypeScript | 23 | 6 | 29 |
| Go | 23 | 6 | 29 |
| .NET | 23 | 6 | 29 |
| Java | 0 | 29 (manual/none) | 29 |

"23 automated" is a count of rules that produce gallery findings, not a precision/recall
measure. The benchmark found 1 false positive, 3 duplicates, and 30 valid-but-unclassified
library/API choices in `rw-2026-11-08-02`; those are enforcement-quality findings, not
architecture validation.

## Profile support

| Profile | Python | TypeScript | Go | .NET | Java | Evidence |
|---|---|---|---|---|---|---|
| Library/framework | N | **P** | N | **P** | N | `test_library_profile`, `test_dotnet_profile` |
| Service topology (ST-1–ST-12) | N | N | N | **P** | N | `test_topology` (fixtures are .NET-shaped) |
| Service topology, non-.NET project model | N | N | N | N | N | No non-.NET fixture |

The topology runner *reads* `package.json`, `pyproject.toml`, and `go.mod` where present,
but the profile's tests, sample manifest, and project model are .NET-first. Do not claim
portable profile support from code that merely recognizes a manifest filename.

## Cross-language semantic equivalence

The same catalog rule does not mean the same algorithm:

| Concern | .NET | TypeScript | Python | Go | Java |
|---|---|---|---|---|---|
| Project boundary | `ProjectReference` / `csproj` | `package.json` exports, imports | package/module imports | `go.mod`, package import | JPMS/packages |
| Visibility | assembly/internal | module exports | underscore/module privacy | `internal/` | package-private/JPMS |
| Third-party detection | assembly refs / packages | manifest + imports | imports | imports | imports/JPMS |
| Transitive closure | project graph + source | import graph | import graph | import graph | package graph |
| Public API profile | MSBuild-evaluated `PackageId`/`IsPackable` | `package.json` name/private | *none* | *none* | *none* |
| Layer model | namespaces/projects | paths/imports | paths/imports | packages/imports | packages/JPMS |
| Runtime data isolation | static SQL/ORM only | static SQL/ORM only | static SQL/ORM only | static SQL/ORM only | none |

Consequences:

1. A rule can be "supported" in all four languages while detecting different forms. The
   matrix reports this rather than pretending the implementations are equivalent.
2. Java is not "partially supported"; it has no enforcer. Three benchmark repositories are
   blocked, not passed.
3. Python and Go libraries cannot use the library profile; their public API types can still
   be reported as L003 leaks. That is a known false-positive class, not a reason to waive
   the rule silently.
4. The service profile's `ST-10` coverage and `ST-11` UI/API checks are .NET/JSON/token
   shaped; they are review aids, not language-neutral semantics.

## Support dispositions

| Capability | Disposition |
|---|---|
| Base catalog, four languages | **PARTIAL** — 23/29 execute; six manual; semantic limits above |
| Java base | **NOT SUPPORTED** — profile only, fail closed |
| Library profile TS/.NET | **PARTIAL** — implemented, benchmark exposes rejected/remaining cases |
| Library profile Python/Go | **NOT SUPPORTED** |
| Service profile .NET | **PARTIAL** — 12/12 fixture, but semantic UI/coverage claims are tokens/JSON |
| Service profile non-.NET | **NOT SUPPORTED / NOT TESTED** |
| Cross-language equivalence | **PARTIAL** — same IDs, different algorithms and limits |
| Runtime autonomy | **NOT SUPPORTED** — static analysis only |
