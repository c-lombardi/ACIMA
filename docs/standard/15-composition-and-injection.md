# 15. Explicit composition and injection

> **Normative.** A software system MUST have one or more identifiable composition boundaries that
> declare and construct the module-owned components they assemble. A composition boundary may be a
> host, a public factory or constructor surface, a package initializer, a framework integration
> point, a plugin loader, a test fixture, or another explicitly designated construction boundary. A
> developer MUST be able to inspect each boundary and determine which components it assembles, which
> implementation backs each one, what each component requires, where every dependency comes from,
> and which components depend on which others.

This chapter is about **construction**, not about a particular dependency-injection framework or a
particular executable host. ACIMA does not require a container, a registration DSL, a process entry
point or a specific object lifetime. It requires that module-owned construction is explicit enough
to inspect and verify. A framework MAY own activation and lifetime; it MUST NOT own the answer to
“what does this component depend on?”

## 15.1 Why this is a boundary rule

A module can satisfy every import rule and still be impossible to reason about. The failure is
usually visible at startup:

```python
# The imports are clean; the graph is not.
container.scan("acima")
container.resolve(OrdersService)
```

Nothing in `OrdersService`'s source says what it needs. The component works until a registration is
missing, a scan includes the wrong assembly, two constructors become ambiguous, or a test wants a
fake repository. The dependency graph exists, but only in a framework's runtime state. That is the
same loss of autonomy as a module reaching into another module's database: the code looks isolated
while its real dependencies are decided elsewhere.

Explicit composition is also what makes the other ACIMA rules meaningful. `D001` checks edges,
`D011` checks that a constructor does not quietly accept a missing dependency, `L004` forbids
resolving a peer at runtime, and `A005` sends configuration to the boundary. This chapter closes
the remaining gap: the boundary must show the actual construction.

## 15.2 Composition boundaries

The **composition boundary** is an explicitly designated place where a module graph is assembled. It
may be a host, a library consumer constructing dependencies, a package initialisation function, a
public factory, an executable entry point, a framework integration point, a plugin host, a service
composition mechanism, a test fixture, a module's composition function, or another named construction
surface. A system MAY have several composition boundaries; each MUST declare its scope and together
they MUST make the graph inspectable.

A composition boundary is the only place allowed to:

- register or construct module-owned components;
- select a concrete implementation for a port;
- read and validate configuration, then construct typed settings;
- decide the lifetime and scope for the graph it assembles;
- adapt a framework's activation contract to the module's constructors.

A module MAY publish a composition function for its own implementation, as described in
[chapter 3](03-module-anatomy.md#35-the-composition-boundary-and-optional-host). That function MUST
construct only that module's graph. Cross-module wiring remains at a composition boundary (`D006`,
`P4.5`). A library's consumer, factory or package initializer is a valid boundary; it does not need
to be an executable host.

At each boundary, a reviewer MUST be able to answer:

1. Which components does this boundary assemble?
2. Which implementation is used for each component?
3. What does each component require?
4. Where does each dependency come from?
5. Which components depend on which others?
6. Where is construction performed?

If the answer to any question is “the framework discovers it”, the boundary is incomplete for that
component. A generated component list is acceptable only when the generation is deterministic, the
result is checked in or reproducible, and the produced graph can still be reviewed.

## 15.3 Explicit registration

Module-owned components MUST be registered by a declaration that names the component and its
implementation. These are acceptable starting points:

```csharp
// .NET: the component and its implementation are both named.
services.AddScoped<IOrderRepository, SqlOrderRepository>();
services.AddScoped<IOrderService>(provider =>
    new OrderService(
        provider.GetRequiredService<IOrderRepository>(),
        provider.GetRequiredService<IPaymentService>(),
        provider.GetRequiredService<IClock>()));
```

```python
# Python: construction is ordinary code.
catalog = CatalogModule(InMemoryProductStore())
payments = PaymentsModule(FakeGateway(...))
orders = OrdersModule(catalog=catalog.reader(), payments=payments.gateway())
```

```typescript
// TypeScript: construction is ordinary code.
const catalog = new CatalogModule(new InMemoryProductStore());
const orders = new OrdersModule(catalog.reader(), payments.port(), () => new Date());
```

```go
// Go: a constructor function is the composition unit.
catalog := catalog.New(inmemory.NewStore())
orders := orders.New(catalog.Reader(), payments.Port(), time.Now)
```

The .NET factory form is not mandatory for every registration. `AddScoped<IOrderRepository,
SqlOrderRepository>()` is inspectable when the constructor is visible and unambiguous: the
implementation and its constructor dependencies are in source. A registration is a `D013` finding
when a scan, convention or reflection step decides *which* types exist or *which* constructor is
used, so the boundary no longer names the graph. The distinction is visibility, not syntax.

Framework infrastructure may keep its native registration mechanism. A web framework registering
its own router, a logging library adding its own sink, or a test host starting a server is not
module-owned construction. Module-owned services, controllers, handlers, consumers, repositories and
adapters are.

## 15.4 Explicit dependency construction

A component's constructor (or its explicit composition function) MUST declare what it needs:

```csharp
public sealed class OrderService : IOrderService
{
    public OrderService(
        IOrderRepository repository,
        IPaymentService payments,
        IClock clock)
    {
        Repository = repository;
        Payments = payments;
        Clock = clock;
    }
}
```

The important properties are:

- every required dependency is a parameter;
- the parameter is used to construct the object, not filled later;
- the concrete implementation is selected at the boundary;
- configuration and primitive values arrive as a typed settings object or an explicit argument;
- an optional dependency is not used to hide a decision (`D011`, `D012`).

A constructor is not automatically explicit merely because it exists. If a framework constructs the
object and then assigns a property, the dependency was not supplied at construction. That is
`D014`. If the component looks up the dependency from a global provider, that is `L004`.

## 15.5 Entry points and framework-managed activation

Controllers, HTTP handlers, message consumers, scheduled jobs and serverless functions are often
activated by a framework. That is legitimate where those entry points exist; a library or package
without them uses a public factory or consumer construction instead. The module does not have to
instantiate a framework-managed controller by hand.

The requirement still applies to the controller's **declared dependencies**:

```csharp
// ✅ The framework activates the controller, but every module-owned dependency is in the
// constructor and the composition boundary registers the implementations.
public sealed class OrdersController : ControllerBase
{
    private readonly IOrderService _orders;
    private readonly IClock _clock;

    public OrdersController(IOrderService orders, IClock clock)
    {
        _orders = orders;
        _clock = clock;
    }
}
```

```csharp
// ❌ The framework supplies dependencies after construction.
public sealed class OrdersController : ControllerBase
{
    [Inject] public IOrderService Orders { get; set; } = null!;
    [FromServices] public IClock Clock { get; set; } = null!;
}
```

For a framework-managed entry point, the enforcer or reviewer must verify:

- the framework's activation contract is understood;
- every module-owned dependency is represented in the constructor or an explicit factory;
- the composition boundary registers the implementation and lifetime;
- a framework service that is genuinely infrastructure (request context, cancellation token,
  model-state dictionary) is distinguished from a module-owned dependency;
- the activation cannot silently fall back to a default implementation or a service locator.

A framework that requires property injection for its own infrastructure is a documented exception.
It does not license property injection for module-owned services.

## 15.6 Forbidden acquisition paths

The following are not alternative injection styles; they conceal the graph:

| Mechanism | Rule | Why it fails |
|---|---|---|
| Resolve a peer from a global container/registry | `L004` | The component's required dependency is absent from its construction contract. |
| Static service locator | `L004` | The dependency is replaced by a global lookup that tests and readers cannot see. |
| Property or field injection for a module-owned dependency | `D014` | The object is usable before its required state exists, and the dependency is not at the construction site. |
| Assembly scanning or convention registration that chooses components | `D013` | The boundary no longer names which components exist or which implementation is selected. |
| Hidden framework context access | `L004`, `A005` | The component depends on ambient runtime state instead of an explicit input. |
| Post-construction assignment or an initializer that fills required fields | `D014`, `D011` | Construction can succeed while the object is incomplete. |
| Runtime resolution of an arbitrary type | `L004` | The graph is data, not code; it cannot be checked at build time. |
| Global mutable system state used as a dependency | `A003`, `L004` | Lifetime and ownership are implicit, and tests cannot isolate the component. |

A supported exception MUST be documented with an owner, scope, reason, expiry and review date
(`G001`). The exception MUST preserve as much inspectability as possible: name the discovered set,
record the registration source, and prove the resulting graph in a test. “The framework does it” is
not a justification; it is the condition the rule is testing.

## 15.7 Language and framework profiles

The languages do not share a DI convention. The invariant is the same; the representation differs.

| Language | Composition boundary | Explicit construction | Implicit acquisition to reject | Framework-managed exception |
|---|---|---|---|---|
| C#/.NET | `Host` project and its `Program`/startup registration | constructor injection; host registration naming interface and implementation; factory when activation needs arguments | assembly scanning, convention registration, `[Inject]`/`[FromServices]` properties, `IServiceProvider` in module code | ASP.NET controller activation and middleware may be framework-managed when constructor dependencies are declared |
| TypeScript/JavaScript | host entry point and app factory | `new Component(dep)` or an explicit factory | `import.meta.glob`, `require.context`, property decorators such as `@Inject`, container resolution inside a component | framework router/controller activation with constructor injection |
| Python | host `build()`/`main()` and module composition functions | constructor arguments or explicit factory functions | `pkgutil.walk_packages`, dynamic `importlib` scans, `Provide[...]`/`Inject[...]` fields, `container.get` in a component | web framework request handlers; dependency must still be a declared constructor argument |
| Go | `cmd/<service>/main.go` and explicit constructor calls | `NewX(dep)` returning a value; no init-time registry | package `init()` registration, global registries, reflection-based lookup | HTTP framework handler adaptation; handler struct fields must be set at construction |
| Java | `Main`, Spring configuration or explicit factory | constructor injection; `@Bean` methods naming the implementation | classpath scanning that selects module-owned components, field injection, `ApplicationContext.getBean` in domain code | framework-managed controllers with constructor injection |

The reference enforcers implement `D013` and `D014` for Python and TypeScript. Go and .NET carry the
catalog entries but report them `executed: false` in this revision; Java has no reference enforcer.
A language profile is not claiming support until its enforcer and conformance fixtures pass.

## 15.8 Examples

### 15.8.1 Violation: discovery decides the graph

```python
# host/main.py — the host does not say which components exist.
import importlib
import pkgutil


def build():
    for module in pkgutil.walk_packages(["acima"]):
        importlib.import_module(module.name)
```

Finding: `ACIMA-D013` — the composition host discovers components with `pkgutil.walk_packages`;
register and construct each module-owned component explicitly.

### 15.8.2 Correction: the boundary names the graph

```python
from acima.catalog.impl import CatalogModule
from acima.orders.impl import OrdersModule


def build():
    catalog = CatalogModule(InMemoryProductStore())
    return OrdersModule(catalog=catalog.reader(), clock=system_clock)
```

The host shows both components, the concrete store, the reader supplied to Orders, and the clock
source. There is no discovery step to reproduce.

### 15.8.3 Explicit composition boundary

```typescript
// host/main.ts
import { CatalogModule, InMemoryProductStore } from '../catalog/impl/module.ts';
import { OrdersModule } from '../orders/impl/module.ts';

const catalog = new CatalogModule(new InMemoryProductStore());
const orders = new OrdersModule(catalog.reader(), () => new Date());
```

The construction expressions are the dependency graph. A reviewer can follow each argument to its
source; a test can replace either dependency without booting a container.

### 15.8.4 Framework-managed controller that still satisfies the requirement

```csharp
[ApiController]
[Route("orders")]
public sealed class OrdersController : ControllerBase
{
    private readonly IOrderService _orders;

    public OrdersController(IOrderService orders) => _orders = orders;

    [HttpPost]
    public ActionResult<OrderView> Place(PlaceOrder command) => _orders.Place(command);
}
```

The framework creates the controller and supplies `IOrderService`. That is acceptable: the
module-owned dependency is a constructor parameter, and the composition boundary registers the
implementation. The
controller does not resolve anything from `HttpContext.RequestServices`.

### 15.8.5 Service-locator violation

```csharp
public sealed class OrderService : IOrderService
{
    public OrderView Place(PlaceOrder command)
    {
        var payments = _provider.GetRequiredService<IPaymentService>(); // ❌ L004
        return PlaceWith(payments, command);
    }
}
```

The constructor does not declare `IPaymentService`; the call site does. The fix is to add it to the
constructor and let the host supply it. `L004` is the applicable rule even when a container is
legitimate elsewhere in the system.

### 15.8.6 Manual review: generated components

A source generator may emit a registration list. That is not automatically a violation. A reviewer
must establish:

- the generator input is checked in and deterministic;
- the generated output is reviewed or diffed in CI;
- the emitted registrations name implementations and lifetimes;
- no reflection chooses among multiple constructors at startup;
- an integration test boots the generated graph and asserts its edges.

If those conditions hold, the boundary is inspectable through generated evidence. If they do not,
the correct result is `PARTIAL ASSESSMENT` with `D013` recorded as not executed — not a pass.

## 15.9 Generality and exceptions

The invariant applies across architecture families, but the shape of the boundary changes.

| Architecture | Boundary | What must remain visible | What is not required |
|---|---|---|---|
| Modular monolith | one host and module composition functions | every cross-module implementation choice and every module entry point | one global container |
| Microservices | each service's host | that service's components and its outbound ports | a shared composition mechanism across services |
| Library or framework | public constructor/factory surface and documented extension points | how a consumer supplies required collaborators and configuration | an executable host |
| Plugin architecture | plugin loader plus the plugin's explicit factory/registration contract | plugin discovery input, selected plugin, required capabilities | treating every dynamically loaded plugin as a violation |
| Serverless | function entry point and its explicit client/factory construction | each function's clients, configuration and outbound dependencies | a long-lived process or a global container |
| Framework-managed entry point | framework configuration plus constructor signatures | module-owned dependencies and their registrations | manual instantiation of framework-managed controllers |
| Generated components | generator input, deterministic output and reviewed graph | generated registrations and their source | hand-writing generated code |

A library may have no host at all. Its composition surface is its public constructor, factory or
package initializer, used by a consumer; `D013`'s declared-host discovery check applies only where a
`host`-role composition unit exists, while `D014` still applies to module-owned components inside the
library. A plugin loader may discover plugins, but the composition boundary must name the loader, its
input and the capabilities each plugin receives. **Discovery is not forbidden; invisible discovery
is.** An exception that hides the graph is not made acceptable by documenting it.

## 15.10 Enforcement and limits

`D013` and `D014` execute in the Python and TypeScript reference enforcers:

- `D013` scans only declared `host`-role composition units for dynamic discovery calls: `pkgutil.walk_packages`,
  `pkgutil.iter_modules`, `importlib.import_module`, `__import__`, and explicit
  `autodiscover`/`auto_register`/`scan_packages`/`register_all` calls in Python; `import.meta.glob`,
  `require.context`, `autodiscover`, `autoRegister`, `scanPackages` and `registerAll` in TypeScript.
- `D014` scans `implementation`, `adapter` and `host` units for `Provide[...]`, `Inject[...]` and
  `Autowired[...]` class-field annotations in Python, and for `@Inject`/`@inject`/`@Autowired`
  decorators immediately above a field declaration in TypeScript.

Both are **candidate detectors**, not proof. They cannot see:

- module-owned components absent from a declared composition boundary because a framework
  auto-registers a whole assembly;
- a container's runtime graph, constructor selection or lifetime validation;
- property injection implemented by a framework-specific mechanism the scanner does not know;
- a service locator call hidden behind a local wrapper or an unqualified import;
- a generated registration list whose source is not checked in.

Missing registration and a framework's activation contract are manual-review items. The correct
report distinguishes:

- **confirmed violation** — a checked-in dynamic scan or property/field injection pattern;
- **potential violation** — a framework registration whose graph is not visible in source;
- **framework-managed exception** — activation is allowed, but only when constructor dependencies
  and registrations are inspectable;
- **unsupported pattern** — the language/profile has no executable detector (`executed: false`);
- **manual review** — the evidence cannot be decided statically.

A clean run does not prove the system is explicitly composed. It proves the detector found no
matching pattern in the files it analyzed. The claim model must still list an unexecuted rule as
missing evidence.

## 15.11 Review checklist

- [ ] Does the system have one or more identifiable composition boundaries, each with a declared
      scope? (A library or package may have no executable host; a public factory can be its
      boundary.)
- [ ] Does every module-owned component appear in an explicit registration or construction
      expression?
- [ ] Does every component's constructor declare its required dependencies?
- [ ] Is the concrete implementation for every port selected at the boundary?
- [ ] Are configuration and primitive values supplied by the boundary, not discovered inside?
- [ ] Are controllers, handlers and consumers framework-activated with declared constructor
      dependencies, not property injection?
- [ ] Is every service-locator/global-provider access in module code eliminated or justified
      (`L004`)?
- [ ] Are scans and conventions limited to infrastructure, or documented and proven (`D013`)?
- [ ] Does a test or boot check construct the graph with fakes and assert the intended edges?
- [ ] Are exceptions owned, scoped, expiring and recorded as manual evidence?
- [ ] Does the report distinguish confirmed, potential, framework-managed and unevaluated cases?

The goal is not purity. It is that a developer can open the composition boundary and see the
system's construction without guessing what a framework will do at runtime.
