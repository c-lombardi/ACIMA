# Analyzers and linters

ACIMA is enforced by two layers, and they are good at different things.

| Layer | Strength | Weakness |
| --- | --- | --- |
| Native analyzers and linters | Understand types, symbols and semantics; fast; IDE feedback | Poor at cross-project dependency policy; local rules only |
| ACIMA enforcer | Understands the unit graph and the dependency matrix; language-neutral rule ids | Text/AST level; does not type-check |

Use both. The enforcer owns the matrix; native tooling owns everything a compiler can prove.

## Rule-by-rule mapping

The rule ids are defined in `tools/acima-spec/rules.json` and documented in `docs/rules/`.
This table maps each portable rule to the native mechanism that can also catch it.

### Dependency rules

| Rule | Meaning | Native mechanism |
| --- | --- | --- |
| `ACIMA-D001` | No implementation-to-implementation references across modules | .NET: project references + `NetArchTest`; Java: Maven module deps + ArchUnit; TS: `eslint-plugin-boundaries`; Python: `import-linter`; Go: internal package layout |
| `ACIMA-D002` | Contracts never reference implementations | ArchUnit `noClasses().that().resideInAPackage("..contracts..").should().dependOnClassesThat().resideInAPackage("..impl..")` |
| `ACIMA-D003` | Contracts never reference other contracts | ArchUnit / NetArchTest sibling-module isolation |
| `ACIMA-D004` | Contracts have no third-party dependencies | .NET: `PackageReference` audit; Java: `maven-enforcer-plugin` banned dependencies; TS: `import/no-extraneous-dependencies`; Python: `import-linter` forbidden modules |
| `ACIMA-D005` | No module cycles | ArchUnit `slices().should().beFreeOfCycles()`; NetArchTest cycle checks; `dependency-cruiser` `no-circular` |
| `ACIMA-D006` | No unit references the composition boundary | ArchUnit layered architecture with the boundary on top |
| `ACIMA-D007` | The shared kernel is a leaf | .NET: kernel project has zero references; `bannedApiAnalyzers` for kernel types |
| `ACIMA-D008` | No transitive reach into another implementation | ArchUnit `noClasses().should().dependOnClassesThat(...)` with transitive `onlyBeAccessedBy`; NetArchTest `HaveDependencyOnAny` |
| `ACIMA-D009` | No private types crossing a boundary | Compiler visibility (`internal` in C#, package-private in Java, unexported in Go) |

### Layering rules

| Rule | Meaning | Native mechanism |
| --- | --- | --- |
| `ACIMA-L001` | Domain code does not touch persistence | ArchUnit/NetArchTest package rules; Python `import-linter` |
| `ACIMA-L002` | Contracts expose no framework types | ArchUnit `noClasses().that().resideInAPackage("..contracts..").should().dependOnClassesThat().resideInAnyPackage("org.springframework..")` |
| `ACIMA-L003` | Implementation types are not public API | C# `internal`; Java package-private; TS `exports` discipline + `eslint-plugin-boundaries` |

### Contract-shape rules

| Rule | Meaning | Native mechanism |
| --- | --- | --- |
| `ACIMA-C001` | Contract types are immutable | C#: `Meziantou.Analyzer` / custom Roslyn `readonly struct`; TS: `eslint-plugin-functional`; Java: `ErrorProne` `@Immutable`; Python: `dataclasses(frozen=True)` |
| `ACIMA-C002` | No mutable collection exposure | Roslyn API-shape analyzers; Java `Immutables`; TS `readonly T[]` |
| `ACIMA-C003` | No public setters on contracts | Roslyn `CA1044`-style custom analyzer |
| `ACIMA-C004` | No ambient state in contracts | Custom analyzer banning `DateTime.Now`, `new Date()`, `time.Now()`, `Instant.now()` in contracts |
| `ACIMA-C005` | No persistence types in contracts | ArchUnit banned packages; `import-linter` |
| `ACIMA-C006` | No untyped members | C# `dynamic`/`object` analyzer; TS `no-explicit-any`; Python `disallow-any-expr` |
| `ACIMA-C007` | Value objects validate in the constructor | Roslyn analyzer for guard clauses; property-based tests |

### Autonomy rules

| Rule | Meaning | Native mechanism |
| --- | --- | --- |
| `ACIMA-A001` | No cross-module schema access | SQL linters (`sqlfluff` naming rules); migration review |
| `ACIMA-A002` | No shared transactional writes across modules | Integration tests; architecture review |
| `ACIMA-A003` | No cross-module mutable statics | Custom analyzer / grep gate |
| `ACIMA-A004` | Independent deployability | Build graph + CI boundary checks |

### Governance rules

| Rule | Meaning | Native mechanism |
| --- | --- | --- |
| `ACIMA-G001` | Waivers are complete | Enforcer only |
| `ACIMA-G002` | Waivers have not expired | Enforcer only |
| `ACIMA-G003` | Public contracts are documented | C# `CS1591` + `GenerateDocumentationFile`; TS `eslint-plugin-jsdoc`; Go `revive` exported rule; Java `javadoc` |
| `ACIMA-G004` | Rule catalog matches the implementation | Enforcer only |
| `ACIMA-G005` | Every file belongs to a unit | Enforcer only |

`G001`, `G002`, `G004` and `G005` have no native equivalent: they are properties of the
governance system itself, which is exactly why the enforcer must own them.

## .NET

```xml
<PackageReference Include="Microsoft.CodeAnalysis.NetAnalyzers" Version="8.0.0" PrivateAssets="all" />
<PackageReference Include="Meziantou.Analyzer" Version="2.0.0" PrivateAssets="all" />
<PackageReference Include="ArchUnitNET" Version="0.10.0" PrivateAssets="all" />
```

```xml
<PropertyGroup>
  <TreatWarningsAsErrors>true</TreatWarningsAsErrors>
  <GenerateDocumentationFile>true</GenerateDocumentationFile>
  <Nullable>enable</Nullable>
</PropertyGroup>
```

Project references are the first line of defence. If `Orders.csproj` has no
`ProjectReference` to `Catalog.csproj`, `ACIMA-D001` cannot be violated at compile time; the
enforcer exists to catch the cases where a reference was added "temporarily".

## TypeScript

```bash
npm i -D eslint eslint-plugin-boundaries eslint-plugin-functional eslint-plugin-jsdoc
```

```js
// eslint.config.js (excerpt)
{
  plugins: { boundaries },
  settings: {
    'boundaries/elements': [
      { type: 'contracts', pattern: 'src/*/contracts' },
      { type: 'implementation', pattern: 'src/*/impl' },
      { type: 'shared-kernel', pattern: 'src/shared-kernel' },
      { type: 'host', pattern: 'src/host' },
    ],
  },
  rules: {
    'boundaries/element-types': [2, { default: 'disallow', rules: [
      { from: 'contracts', allow: [] },   // default: contracts reference nothing (ST-5)
      { from: 'implementation', allow: ['contracts', 'shared-kernel'] },
      { from: 'host', allow: ['contracts', 'implementation', 'shared-kernel'] },
    ]}],
    'functional/prefer-readonly-type': 'error',
    'functional/immutable-data': 'error',
    '@typescript-eslint/no-explicit-any': 'error',
  },
}
```

`eslint-plugin-boundaries` is the closest native equivalent to the ACIMA matrix, but it
operates on file patterns, not modules: the enforcer is what distinguishes "another
implementation" from "my own implementation".

## Python

```bash
pip install import-linter
```

```ini
# .importlinter
[importlinter]
root_package = acima

[importlinter:contract:contracts-are-independent]
name = Contracts are independent
type = independence
modules =
    acima.catalog.contracts
    acima.orders.contracts
    acima.payments.contracts

[importlinter:contract:no-implementation-imports]
name = No cross-module implementation imports
type = forbidden
source_modules = acima.catalog.impl
forbidden_modules = acima.orders.impl
```

`import-linter` understands packages and imports, which covers `D001` and `D003` well. It has
no notion of "this file is a contract and therefore may not use `datetime.now()`", which is
why `C004` stays in the enforcer.

## Go

Go's compiler already enforces the strongest possible boundary: an `internal/` package cannot
be imported from outside its subtree, and unexported identifiers cannot be imported at all.
That gives `D009` for free and makes `D001` a matter of package layout.

What Go does not give you:

- The distinction between a contracts package and an implementation package.
- Immutability of contract structs (`C001`, `C002`).
- Cycle detection across `internal` packages — the compiler rejects import cycles, but it
  rejects them *as compile errors*, not as architecture findings with rule ids.

`go vet` plus the reference enforcer covers the rest.

## Java

```xml
<dependency>
  <groupId>com.tngtech.archunit</groupId>
  <artifactId>archunit-junit5</artifactId>
  <version>1.3.0</version>
  <scope>test</scope>
</dependency>
```

```java
@AnalyzeClasses(packages = "com.acima")
class ArchitectureTest {
    @ArchTest
    static final ArchRule contractsAreIndependent = noClasses()
        .that().resideInAPackage("..contracts..")
        .should().dependOnClassesThat().resideInAPackage("..impl..");

    @ArchTest
    static final ArchRule noCycles = slices()
        .matching("com.acima.(*)..")
        .should().beFreeOfCycles();
}
```

ArchUnit is the strongest native option of the five: it has cycle detection, slice isolation
and transitive dependency rules out of the box. The ACIMA enforcer's value there is the shared
rule ids and the waiver model, not detection capability.

## Why keep the enforcer at all

Because the matrix is the part no single tool expresses completely, and because a rule that
exists under the same id in all five languages can be reviewed once and enforced everywhere.

The enforcer is deliberately small. It is a reference implementation of the standard, not a
product: it is meant to be read, forked and replaced by the team that adopts it.
