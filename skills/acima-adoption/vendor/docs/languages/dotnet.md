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
  tools/Acima.ArchTests/           tooling         the rule runner (no packages)
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

**Reference runner (this repository):** `tools/Acima.ArchTests` — a console program with no NuGet
dependencies, so it runs anywhere `dotnet run` does and can be executed in the conformance harness.
It reads `.csproj` files as well as sources, so a `ProjectReference` from an implementation to
another module's implementation is a `D001` finding before anything is compiled.

```bash
dotnet run --project tools/Acima.ArchTests -- --root . --format json
dotnet run --project tools/Acima.ArchTests -- --verify     # clean tree + gallery baseline
```

It scans `.csproj` files and `.cs` sources, classifies units from `acima.config.json`, and emits ACIMA
findings. It reads source rather than executing it: no assembly loading, no type initialisers.

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

### Explicit inputs (`D011`, `D012`)

C# optional parameters (`IPaymentService? payments = null`) and nullable reference types make the two
construction paths easy to write. The rule requires the parameter and leaves `IPaymentService?`
without a default legal: the composition root passes `null` deliberately. Nullable reference analysis
does not object to an optional parameter, so `TreatWarningsAsErrors` is not a substitute. The reference
enforcer reports `D011` and `D012` `executed: false` in this revision; a small Roslyn analyzer or the
manual review in chapter 8 §8.9 supplies the evidence.

### Values and configuration (`A005`, `A006`)

Bind typed options at the host (`IOptions<OrdersSettings>` or a validated record) and require the
settings object in the module constructor. A module must not call
`Environment.GetEnvironmentVariable` or reach into `IConfiguration` for a value the host can pass.
Named constants for fixed policy are preferable to options that imply runtime changeability. The
reference enforcer reports `A005` and `A006` `executed: false`; use a Roslyn analyzer or the manual
review in chapter 8 §8.9 for evidence.

### Composition and injection (`D013`, `D014`)

`Orders.Host` registers `IOrderRepository`/`IOrderService` and selects the concrete implementations.
`AddScoped<IOrderRepository, SqlOrderRepository>()` is inspectable when the constructor is unambiguous;
a scan/convention that decides which types exist, or a factory that resolves arbitrary types, is
`D013`. `[Inject]` or `[FromServices]` on an application property is `D014`; constructor injection on
an ASP.NET controller is legitimate framework-managed activation. The reference enforcer reports both
rules `executed: false` in this revision, so a Roslyn analyzer or manual evidence is required.

### Functional capture (`D015`, `D016`)

A lambda or method group must not capture an application service from a field or enclosing method
when it could receive it as a parameter; `this` access to an explicit constructor field is visible
and allowed. Delegate binding of a service belongs at the host. A Roslyn analyzer can inspect the
semantic model; until one is validated here, record manual evidence for `D015`/`D016` (chapter 16).

### Lifecycle and state ownership (`A007`–`A009`)

`AddSingleton`, `AddScoped` and `AddTransient` make lifetime explicit, and the container can validate
some captive dependencies at startup. A singleton constructor that takes a scoped service is the
canonical `A008`; a singleton holding a `Dictionary` mutated after construction is the canonical
`A009`. `IDisposable`/`IAsyncDisposable` establish a cleanup contract, not a guarantee; `IHostedService`
owns a worker lifecycle that must stop on shutdown. Static fields are process-wide and remain shared
mutable state even when they do not cross a module boundary. This profile reports `A007`–`A009`
`executed: false` in this revision; use a Roslyn analyzer, container validation and recorded manual
evidence for lifetime, concurrency, tenant isolation and resource cleanup (chapter 17).

### Intent-revealing naming (`N001`–`N003`)

Types, public members and methods use `PascalCase`; parameters and locals use `camelCase`;
interfaces conventionally begin with `I`; async methods end in `Async` when meaningful. Name the
responsibility (`OrderValidator`), not a generic role (`OrderHelper`). `N001` and `N002` report
`executed: false` in this revision, as does manual `N003`; use a Roslyn analyzer and recorded
manual evidence for side effects, units, boolean clarity and domain terminology (chapter 18).

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
