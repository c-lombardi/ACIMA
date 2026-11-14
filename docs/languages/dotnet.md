# C# / .NET profile

`net8.0` · C# 12 · one solution, one project per unit.

> **Reference example.** The tree below is the compiled example in `examples/dotnet`. It uses the
default: every contracts project imports nothing and owns its value types; see
[section 6](#6-service-topology-profile).

## 1. Layout

```
examples/dotnet/
  Directory.Build.props            net8.0, nullable, implicit usings
  src/Catalog/Catalog.Contracts/   contracts       → nothing (owns Money, ProductId)
  src/Catalog/Catalog/             implementation  → Catalog.Contracts
  src/Orders/Orders.Contracts/     contracts       → nothing (owns Money, ids)
  src/Orders/Orders/               implementation  → Orders.Contracts, Catalog.Contracts, Payments.Contracts
  src/Payments/Payments.Contracts/ contracts       → nothing (owns Money, PaymentId)
  src/Payments/Payments/           implementation  → Payments.Contracts
  host/Host/                       host            → every implementation
  tools/Acima.ArchTests/           tooling         the rule runner (Roslyn package only)
  violations/                      gallery         deliberately broken sources, never compiled
```

## 2. What the toolchain enforces without help

| Obligation | Mechanism |
|---|---|
| No cycles | MSBuild refuses circular `ProjectReference` |
| Implementation invisible | `internal` types + no `InternalsVisibleTo` |
| No transitive leak | `PrivateAssets="all"` on the implementation's reference to its own contracts |
| Contracts have no packages | the csproj simply has no `<PackageReference>` — and `D004` checks it |

```xml
<!-- src/Acima.Catalog.Contracts/Acima.Catalog.Contracts.csproj -->
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
    <Nullable>enable</Nullable>
    <TreatWarningsAsErrors>true</TreatWarningsAsErrors>
  </PropertyGroup>
  <!-- no ProjectReference, no PackageReference: that is the rule, not an omission -->
</Project>
```

```xml
<!-- src/Acima.Orders/Acima.Orders.csproj -->
<Project Sdk="Microsoft.NET.Sdk">
  <ItemGroup>
    <!-- own contracts, redacted so consumers of this project do not inherit them -->
    <ProjectReference Include="..\Acima.Orders.Contracts\Acima.Orders.Contracts.csproj" PrivateAssets="all" />
    <!-- other modules: contracts only -->
    <ProjectReference Include="..\Acima.Catalog.Contracts\Acima.Catalog.Contracts.csproj" />
  </ItemGroup>
</Project>
```

## 3. Architecture tests

**Idiomatic (team scale):** `NetArchTest.Rules` or `Purview.Architecture.Testing` in an xunit/TUnit
project.

```csharp
[Fact]
public void Orders_must_not_reference_Catalog_implementation() =>
    Types.InAssembly(typeof(Acima.Orders.OrdersModule).Assembly)
         .ShouldNot().HaveDependencyOn("Acima.Catalog")
         .GetResult().IsSuccessful.Should().BeTrue();

[Fact]
public void Contracts_must_have_no_third_party_dependencies() =>
    typeof(Acima.Catalog.Contracts.ProductView).Assembly
        .GetReferencedAssemblies()
        .Select(a => a.Name!)
        .Where(n => n is not "System.Runtime" and not "System.Private.CoreLib")
        .Should().BeEmpty();
```

**Reference runner (this repository):** `tools/Acima.ArchTests` — a console program with one NuGet
dependency, `Microsoft.CodeAnalysis.CSharp`. It parses Roslyn syntax trees and builds a project-level
semantic compilation from each project's sources, project references and package assets without
loading product assemblies. It reads `.csproj` files as well as sources, so a `ProjectReference` from
an implementation to another module's implementation is a `D001` finding before anything is compiled.

```bash
dotnet run --project tools/Acima.ArchTests -- --root . --format json
dotnet run --project tools/Acima.ArchTests -- --verify     # clean tree + gallery baseline
```

It scans `.csproj` files and `.cs` sources, classifies units from `acima.config.json`, and emits ACIMA
findings. It reads source rather than executing it: no assembly loading, no type initialisers. The
project model includes referenced project sources and falls back to a loose-source compilation for
fixtures outside a project.

## 4. Analyzers and linters

| Tool | Catches | Notes |
|---|---|---|
| **Roslyn analyzer** (custom) | `C001`, `C002`, `C004`, `L002` at author time | the production answer for contract shape; runs in the IDE |
| `Microsoft.CodeAnalysis.BannedApiAnalyzers` + `BannedSymbols.txt` | `C004` (clocks, `Guid.NewGuid`), `C005` (`IQueryable`, `DbContext`) inside contracts projects | zero code, high value |
| `Microsoft.CodeAnalysis.NetAnalyzers` | `CA1051` (public fields), `CA2227` (collection setters) | enabled by `TreatWarningsAsErrors` |
| `dotnet format analyzers` | formatting of the above | CI-friendly |
| `Microsoft.VisualStudio.Threading.Analyzers` | sync-over-async, not ACIMA but adjacent | optional |

`BannedSymbols.txt` in a contracts project is the cheapest `C004`/`C005` enforcement available:

```
T:System.DateTime; Contracts must not read ambient time (ACIMA-C004)
M:System.Guid.NewGuid; Contracts must not generate identity (ACIMA-C004)
T:System.Linq.IQueryable`1; Contracts must not expose queryables (ACIMA-C005)
```

## 5. Idioms and pitfalls

| Trap | Rule | Fix |
|---|---|---|
| `record` with a `List<T>` property | `C002` | `IReadOnlyList<T>` assigned from `ToArray()` in a constructor |
| `record` with `{ get; init; }` on a collection of mutable items | `C002` | freeze at construction; make the element type immutable too |
| `public class` in the implementation project | `L003` | `internal` — and move cross-boundary types to contracts |
| `IQueryable<T>` returned from a "repository" in contracts | `C005` | return a view; keep queryables in the implementation |
| `IServiceProvider` injected into a handler | `L004` | constructor-inject the ports you need |
| `object Payload` on an integration event | `C006` | one typed event per fact |
| `DateTime.UtcNow` inside a contract | `C004` | pass time in from the implementation |
| `InternalsVisibleTo("Acima.Orders")` added to Catalog | `D009` | this is the .NET-specific way to break the boundary; it is a review blocker |
| `ProjectReference` to an implementation "for the DI registration" | `D001` | register in the host; the module exposes a composition function |

### One .NET-specific note

`PrivateAssets="all"` is doing real work: without it, a reference to `Acima.Catalog` transitively delivers
`Acima.Catalog.Contracts` *and* whatever Catalog itself references. With it, the implementation's
internal dependency edges stop at the project boundary. It is the .NET expression of `D008`'s redaction,
and it is the single most useful line in an ACIMA csproj.

### Partial types and generated code

A `partial` class, struct or record is still **one type**. Every part belongs to the same assembly,
project and ACIMA unit; do not split one type across a contracts project and an implementation
project, or use `partial` to move code between units. Keep each part self-contained: a part must not
rely on a member declared only in another part to satisfy its own unit's contract or to cross a
module boundary. References between parts are restricted to members of the same type in the same
assembly, project and unit. A reference from a partial part to any other type or module is reviewed
exactly like the same reference in an ordinary class: `D001`–`D003` still decide whether the target
is allowed. A partial declaration is never a way to hide a second construction path or bypass the
single-required-constructor shape in `A007`.

Generated code is **not judged as a defect in itself**. `.g.cs`, designer output and source-generator
output are evidence of a generator and its inputs, not an automatic violation. Review the generator
input and the generated result: if generated code adds a package dependency, references another
module's implementation, exposes a vendor type in a contract, or creates an implicit construction
path, the corresponding dependency, contract, tier or explicit-input rule applies to what was
generated. Generated declarations may be skipped by naming and style checks when the generator owns
the name, but architectural dependency, contract and construction checks still inspect the generated
source. Keep generated output deterministic, traceable to a checked-in input, and reproducible in CI;
“generated” is an explanation of provenance, not a waiver.

### Explicit inputs (`D011`, `D012`)

C# optional parameters (`IPaymentService? payments = null`) and nullable reference types make the two
construction paths easy to write. The rule requires the parameter and leaves `IPaymentService?`
without a default legal: the composition root passes `null` deliberately. Nullable reference analysis
does not object to an optional parameter, so `TreatWarningsAsErrors` is not a substitute. The reference
enforcer now executes both rules from the Roslyn syntax tree for `implementation`, `host`, `adapter`
and `port` units. It flags constructor and primary-constructor defaults as `D011`, and method or local
function defaults as `D012`. Contracts are excluded, as are nullable parameters without a default;
`override`, `abstract` and `extern` declarations are skipped because their defaults are not a new
caller-visible construction path. The check is syntactic, so framework-managed construction and
reflection remain manual review.

### Third-party tiers (`L005`–`L007`, `D010`, `G006`)

The enforcer reads direct `PackageReference` entries from `.csproj` files (or the configured
`manifests`) and resolves each declared package through the project's `obj/project.assets.json`
compile assets. It then uses a Roslyn semantic model for every mapped source file: a using directive
resolves to its namespace or type symbol, a signature or field type resolves to its named type, and
the containing assembly maps back to the package id. `L005` flags an integration package imported
outside its declared adapter, `L007` flags a vendor type in a non-adapter signature or field, and
`D010` flags either shape in a port. `L006` validates the declared adapter/port pair and every
adapter unit; `G006` checks direct package references against `externals` and checks entry expiry.
The compilation is project-level, not a full solution build: project references are included from
source, unresolved framework-managed types fall back to the declared `specifiers` and `types`, and a
package with no resolvable metadata cannot prove a vendor-type leak. Tooling and test units are
outside the product graph.

### Values and configuration (`A005`, `A006`)

Bind typed options at the host (`IOptions<OrdersSettings>` or a validated record) and require the
settings object in the module constructor. A module must not call
`Environment.GetEnvironmentVariable` or reach into `IConfiguration` for a value the host can pass.
Named constants for fixed policy are preferable to options that imply runtime changeability. Use
`const` or `static readonly` for stable values, a validated options record for deployment values,
and a secret store for credentials. Equal literals with different receiving meaning remain separate;
a matching identifier does not prove matching units. The reference enforcer executes `A005` for
`Environment.GetEnvironmentVariable(s)` and `ConfigurationManager` access in implementation/adapter
units, and `A006` for meaningful mutable declarations, inline literals at source-declared calls,
duplicate immutable values and configuration/secret-looking literals. `A006` findings are
`classification: "candidate"`; static analysis cannot prove semantic equivalence, infer units or
choose the right owner. Injected `IConfiguration` reads remain manual review.

### Composition and injection (`D013`, `D014`)

`Orders.Host` registers `IOrderRepository`/`IOrderService` and selects the concrete implementations.
`AddScoped<IOrderRepository, SqlOrderRepository>()` is inspectable when the constructor is unambiguous;
a scan/convention that decides which types exist is `D013`. The reference enforcer detects reflection
discovery (`Assembly.GetTypes`, `GetExportedTypes`, `DefinedTypes`, `AppDomain.GetAssemblies`) and
the explicit assembly-scanning APIs `Scan`, `FromAssemblyOf`, `FromAssemblies`, `AddClasses` and
`RegisterAssemblyTypes`. It does not flag framework router registration, `Activator.CreateInstance`,
single-type resolution, or MediatR/FluentValidation/AutoMapper setup; those remain review items.
`[Inject]`, `[Autowired]`, `[Dependency]`, `[FromServices]` or `[FromKeyedServices]` on an application
field or property is `D014`. Constructor and method parameters are not findings, and
post-construction/object-initializer assignment remains manual: the .NET detector is deliberately
attribute-only to avoid treating ordinary property updates as injection.

### Functional capture (`D015`, `D016`)

A lambda or local function must not capture an application service from a static field or enclosing
local when it could receive it as a parameter. Instance fields and enclosing parameters are visible
and allowed; `this` access to an explicit field is not a capture. `D015` uses the semantic model to
distinguish those owners. C# has no native `functools.partial`, so `D016` is opt-in: configure an
explicit `partialHelpers` allowlist and it reports only those helper calls in implementation/adapter
units. Without the property, the rule reports `executed: false`; an explicit empty list is a valid
owner declaration that no helper is used. Generic `Partial`/`Bind` matching is not attempted. The
generated HTML proposal carries the missing `partialHelpers` decision for owner approval.

### Lifecycle and state ownership (`A007`–`A009`)

`AddSingleton`, `AddScoped` and `AddTransient` make lifetime explicit, and the container can validate
some captive dependencies at startup. A singleton constructor that takes a scoped service is the
canonical `A008`; a singleton holding a `Dictionary` mutated after construction is the canonical
`A009`. `IDisposable`/`IAsyncDisposable` establish a cleanup contract, not a guarantee; `IHostedService`
owns a worker lifecycle that must stop on shutdown. Static fields are process-wide and remain shared
mutable state even when they do not cross a module boundary. The reference enforcer reads direct
`AddSingleton`/`AddScoped`/`AddTransient` and `TryAdd*` registrations. `A007` is behaviorally
stateless: one required construction path, no mutable instance or static state, no setter or `init`
accessor and no assignment outside the constructor. A readonly field or get-only property populated
from a constructor parameter is a dependency, not state, so constructor-injected readonly services
are still candidates. `A008` resolves direct
constructor dependencies through a simple service/implementation lifetime map. `A009` reports a
shared class with a mutable container field or property. Factories, keyed services, open generics,
decorators, proxies, tenant isolation, thread safety and cleanup remain manual evidence (chapter 17).

### Intent-revealing naming (`N001`–`N003`)

Types, public members and methods use `PascalCase`; parameters and locals use `camelCase`;
interfaces conventionally begin with `I`; async methods end in `Async` when meaningful. Name the
responsibility (`OrderValidator`), not a generic role (`OrderHelper`). `N001` checks class, struct,
record, interface and enum declarations in application units for PascalCase; `N002` uses the same
exact-name and suffix set as the other enforcers. Generated declarations are skipped. `N003`
remains manual: use recorded evidence for side effects, units, boolean clarity and domain
terminology (chapter 18).

## 6. Service topology profile

Chapter 11 defines the profile. In .NET it is one solution folder per service and one project per
layer:

```
services/Orders/
  Orders.Api/                       Orders.Api.csproj
  Orders.Api.Contracts/             Orders.Api.Contracts.csproj
  Orders.Application/               Orders.Application.csproj
  Orders.Application.Contracts/     Orders.Application.Contracts.csproj
  Orders.Domain/                    Orders.Domain.csproj
  Orders.Infrastructure/            Orders.Infrastructure.csproj
  Orders.Integrations.Stripe/       Orders.Integrations.Stripe.csproj
  Orders.Integrations.Stripe.Contracts/
  Orders.Catalog/                   contracts for messages Orders -> Catalog
  Orders.Host/                      composition root

tests/
  Orders.Domain.Tests/
```

### A contract project with no references

```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
    <Nullable>enable</Nullable>
    <ImplicitUsings>disable</ImplicitUsings>
  </PropertyGroup>
  <!-- Deliberately no ProjectReference and no PackageReference. -->
</Project>
```

```csharp
// Orders.Application.Contracts/PlaceOrder.cs
public sealed record OrderLine(string ProductId, decimal Amount, string Currency, int Quantity);
public sealed record PlaceOrder(string CustomerId, IReadOnlyList<OrderLine> Lines);
public sealed record PlaceOrderResult(bool Accepted, string? OrderId, string? Rejection);

public interface IPlaceOrderHandler
{
    PlaceOrderResult Handle(PlaceOrder command);
}
```

No `Acima.SharedKernel` reference, no `System.Text.Json` attributes, no `Microsoft.Extensions.*`, no
EF annotations. `Money` is either a primitive pair (`decimal` + currency code) or a record declared
inside this project and duplicated where another contract needs it (ST-5).

### Layer references

| Project | References | Never references |
|---|---|---|
| `Orders.Api` | `Orders.Api.Contracts`, `Orders.Application.Contracts` | `Orders.Application`, `Orders.Domain`, `Orders.Infrastructure` |
| `Orders.Application` | `Orders.Application.Contracts`, `Orders.Domain`, `Orders.Stripe.Contracts` | `Orders.Api`, `Orders.Infrastructure` |
| `Orders.Domain` | the language core only | any contracts project, any package with IO |
| `Orders.Infrastructure` | `Orders.Domain` ports, persistence packages | `Orders.Api`, vendor SDKs |
| `Orders.Integrations.Stripe` | `Orders.Integrations.Stripe.Contracts`, Stripe SDK | `Orders.Domain`, `Orders.Application` |
| `Orders.Host` | everything | — |

The API talks to `IPlaceOrderHandler` from `Orders.Application.Contracts`; the host registers the
implementation. `Orders.Api` never has a `ProjectReference` to `Orders.Application`.

### Third-party isolation

`Orders.Integrations.Stripe.Contracts` holds `IStripeGateway` and its request/result records. It has
zero references. `Orders.Integrations.Stripe` references that project and `Stripe.net`, implements
the gateway and translates Stripe exceptions into the contract's typed failures. Application and
domain see only the contracts project; a Stripe type in a domain signature is an ST-8 failure.

### Domain tests

```bash
dotnet test tests/Orders.Domain.Tests --collect:"XPlat Code Coverage"
```

Gate `Orders.Domain` at 100% line and branch coverage in CI. Test names state the rule
(`PlaceOrder_rejects_more_than_available_stock`), not the method. The domain test project references
`Orders.Domain` and nothing with IO.

### What .NET checks without help

`ProjectReference` is the graph: a contract project with no references cannot compile against
domain types, and `PrivateAssets="all"` stops an implementation's dependencies leaking transitively
(D008). `dotnet list package --include-transitive` is the evidence for ST-5. `InternalsVisibleTo`
from a contracts project is a review blocker.

### Named call arguments (D017)

C# supports named arguments. Supply every argument to a locally resolvable module-owned method or
constructor as parameter: value, including the first argument. This keeps the receiver visible in
raw diffs and makes same-typed swapped values easier to spot. The reference enforcer parses C#
syntax and checks locally declared method/constructor signatures; unresolved external and dynamic
call targets remain outside the deterministic subset. This is independent of nullable reference
types and does not prohibit required nullable parameters.
