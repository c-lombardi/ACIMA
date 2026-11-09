# 18. Intent-revealing naming and semantic clarity

> **Normative.** Names MUST communicate the intent, responsibility and meaningful behaviour of the
> constructs they identify. A name MUST NOT be merely well formatted while concealing what the
> construct does, what it owns, what it changes or what its values mean.
>
> Naming quality is distinct from naming syntax. Language-specific casing and formatting are
> conventions; responsibility, side effects, units and domain meaning are architectural claims.

This chapter makes naming a first-class ACIMA concern without turning the standard into a universal
style guide. A consistently formatted identifier can still mislead:

```csharp
ProcessOrderData()
ExecuteCustomerOperation()
HandlePaymentInformation()
```

Prefer:

```csharp
CalculateOrderTotal()
FindCustomerById()
AuthorizePayment()
```

The defect is not the casing. It is that the first set names a vague activity instead of an outcome,
so a reader must inspect the body to learn what changed and what was returned.

## 18.1 Why naming is architectural

Architecture is the set of decisions a reader can recover without reading every implementation.
Names are the most frequently read part of that record. They tell a caller which capability to
depend on, which operation changes state, which value carries a unit, and which module owns a
concept. When those signals are wrong, every boundary above them becomes harder to use correctly:

- a contract named `OrderData` does not say whether it is a command, a view or an entity;
- a method named `GetCustomer` that creates a customer hides a write behind a read;
- a parameter named `timeout` does not say whether it is seconds or milliseconds;
- a class named `OrderHelper` gives no clue which responsibility belongs there, so everything does;
- a singleton named `OrderServiceV2` encodes deployment history in a domain identity;
- two names for one concept split the vocabulary at a contract boundary.

Naming is therefore part of Total Visibility. A reader should be able to navigate from a name to a
responsibility, and from a call site to its effect, without reverse-engineering the implementation.

## 18.2 The principle

**P14. Intent-Revealing Naming.** Names communicate responsibility, behaviour, domain meaning and
relevant units. Naming syntax follows the language; naming semantics follow the architecture.

### 18.2.1 Responsibility clarity

A type name MUST identify a responsibility or domain concept. `OrderValidator`,
`PriceCalculator`, `PaymentAuthorizer` and `OrderRepository` state what the type is for.
`OrderHelper`, `OrderManager`, `OrderProcessor` and `OrderUtility` state only that something
happens to orders.

Generic names are not automatically invalid. `OrderRepository` is a role; `PaymentGateway` is a
capability; `OrderFactory` may be the precise abstraction. The question is whether the surrounding
vocabulary makes the responsibility unambiguous. A generic name becomes a defect when it is a
placeholder for an undecided responsibility, or when it lets unrelated behaviour accumulate.

`N002` reports application-owned types whose name is exactly `Helper`, `Manager`, `Handler`,
`Processor`, `Utility`, `Service`, `Provider`, `Factory`, `Common`, `Base`, `Default` or `Generic`,
or whose name ends in `Helper`, `Manager`, `Processor`, `Utility`, `Common`, `Default` or `Generic`.
It is a candidate: `RequestHandler` may be the framework's precise role, and a reviewed exception is
allowed.

### 18.2.2 Operation and behaviour clarity

A method or function name MUST describe the operation, its target where useful, and its outcome
where the outcome is not obvious. `ValidateOrder`, `CalculateTax`, `SaveCustomer`, `PublishInvoice`
and `FindCustomerById` are explicit. `Handle`, `Process`, `Execute`, `Perform`, `Check`, `Run` and
`DoWork` are acceptable only when the surrounding abstraction makes the operation unambiguous.

A method name MUST NOT misrepresent whether it changes state or crosses an external boundary:

| Name | Expected meaning | Defect when |
|---|---|---|
| `FindCustomerById` | read; returns absence explicitly | it creates a customer to satisfy the lookup |
| `CreateCustomer` | write; creates | it returns an existing customer silently |
| `SaveCustomer` | write; persists | it only validates |
| `GetOrCreateCustomer` | read-then-write; creation is stated | it hides the creation behind `GetCustomer` |

A name need not name the database, HTTP or vendor technology. `SaveCustomer` is clearer than
`ExecuteSqlInsertForCustomer`; the side effect is the claim, not the transport.

### 18.2.3 Domain terminology consistency

The same domain concept SHOULD use the same term across contracts, implementations, modules, events,
commands, queries, persistence abstractions and API boundaries. If `Customer` is the contract term,
the repository should not call the same concept `Client`, `AccountHolder` and `User` in adjacent
layers. A different term is justified only when it represents a genuinely different concept.

Consistency is not artificial uniformity. A `Customer` and a `BillingAccount` may be related but
distinct; naming them identically would hide the distinction. The requirement is that the
vocabulary is deliberate, documented where it crosses a boundary, and not a synonym layer over one
concept.

### 18.2.4 Boolean and conditional naming

Boolean identifiers SHOULD express a positive condition, state or decision:

```csharp
IsEnabled
HasPermission
CanSubmitOrder
ShouldRetry
IsPaymentAuthorized
```

Avoid double negatives and polarity inversions that make every call site harder to read:

```csharp
NotDisabled
IsNotInvalid
NoPermission
IsNotUnavailable
```

Prefer `if (!IsEnabled)` over `if (IsNotDisabled)`. A legitimate negative domain concept — for
example `Disallowed` or `Unauthorized` — may remain negative when the domain itself defines that
state; the requirement is clarity, not a mechanical ban on the word "no".

`N003` covers boolean polarity as a semantic review item. A static scanner can find some names, but
it cannot establish that a condition is understood correctly at every call site.

### 18.2.5 Units, measures and distinctions

A name MUST communicate a meaningful unit, scale or distinction when omitting it could cause a
wrong interpretation:

```csharp
timeoutMilliseconds
retentionDays
maximumOrderAmount
distanceMeters
interestRatePercentage
```

Ambiguous names such as `timeout`, `retention`, `amount`, `distance` and `rate` are review items
when the type does not establish the unit. The requirement applies to durations, monetary values,
percentages, physical measurements, counts, rates, identifiers, version numbers and thresholds.

Do not repeat a unit that the type or the domain abstraction already makes unambiguous. A
`Money amount` is clear; `Money amountInMinorUnits` is clearer only if minor units are a meaningful
distinction at that boundary. Integrate this with the existing value and configuration ownership
requirements (`A006`, chapter 14): the name and owner must agree about what the value means.

### 18.2.6 Abbreviations and local vocabulary

Avoid unexplained or locally invented abbreviations:

```csharp
CustomerRepository
MaximumConnectionCount
ExpirationDate
```

instead of:

```csharp
CustRepo
MaxConnCnt
ExpDt
```

Widely recognised technical abbreviations (`HTTP`, `ID`, `URL`, `DTO`), established language
conventions and standard protocol or technology names are allowed. A domain abbreviation is
allowed when the team's glossary defines it and the definition is available at the boundary. An
abbreviation invented in one file is not a domain term.

### 18.2.7 Context and redundancy

A name must be sufficient within its context without repeating that context everywhere:

```csharp
public class OrderValidator
{
    public bool Validate(Order order)
}
```

`Validate` is clear inside `OrderValidator`; `ValidateOrder` would repeat the class name. A
standalone function or a public API may need the extra context because its call site has none. The
balance is local clarity, public discoverability, readability at the call site and avoidance of
redundant terminology. There is no maximum identifier length.

### 18.2.8 Boundary and ownership naming

Names SHOULD help a reader locate ownership and distinguish architectural roles:

```text
Orders/
    Contracts/
        IOrderRepository
        IOrderPricingService
    Implementation/
        SqlOrderRepository
        OrderPricingService
```

`SqlOrderRepository` and `InMemoryOrderRepository` are meaningful when the implementation
distinction matters. Names that encode incidental lifecycle, deployment or development history are
not:

- `SingletonOrderService`
- `TransientOrderValidator`
- `OrderServiceV2`
- `OrderServiceNew`
- `OrderServiceFinal`
- `OrderServiceImplementation`

Lifetime belongs in composition metadata, versioning belongs in release metadata, and
`Implementation` is the folder or package role, not an object's identity. A version suffix is
legitimate only when multiple versions genuinely coexist at a boundary and the version is part of
the public contract.

### 18.2.9 Syntax follows the language

ACIMA does not impose universal casing. The semantic requirements are portable; the syntax is not:

| Construct | C#/.NET | TypeScript | Python | Go | Java |
|---|---|---|---|---|---|
| Type | `PascalCase` | `PascalCase` | `PascalCase` | `MixedCaps`, exported if public | `PascalCase` |
| Interface | `IOrderRepository` | `OrderRepository` or `IOrderRepository` | `Protocol` class `OrderRepository` | `Reader`, `Writer` role names | `OrderRepository` |
| Method/function | `PascalCase` | `camelCase` | `snake_case` | `MixedCaps` | `camelCase` |
| Local/parameter | `camelCase` | `camelCase` | `snake_case` | `mixedCaps` | `camelCase` |
| Constant | `PascalCase` or `UPPER_SNAKE_CASE` | `UPPER_SNAKE_CASE` or `camelCase` | `UPPER_SNAKE_CASE` | `MixedCaps` | `UPPER_SNAKE_CASE` |
| Boolean | `IsEnabled` | `isEnabled` | `is_enabled` | `isEnabled` | `isEnabled` |

Established ecosystem conventions win unless they conflict with a semantic requirement. A
deliberate deviation is documented with its rationale; it is not an excuse for an unclear name.

## 18.3 Construct expectations

| Construct | Expected naming intent | Example |
|---|---|---|
| Class | responsibility or domain concept | `OrderValidator` |
| Interface | role or capability | `OrderRepository` |
| Method | operation or outcome | `ValidateOrder` |
| Function | specific operation | `calculateOrderTotal` |
| Boolean property | positive condition or state | `IsActive` |
| Boolean method | question or decision | `CanSubmitOrder` |
| Constant | meaningful value or purpose | `MaximumRetryCount` |
| Variable | specific meaning | `pendingOrders` |
| Parameter | expected input meaning | `customerId` |
| Collection | contents or domain concept | `activeSubscriptions` |
| Enum | classification or domain state | `PaymentStatus` |
| Enum member | specific classification | `Completed` |
| Event | something that occurred | `OrderSubmitted` |
| Command | requested action | `SubmitOrder` |
| Query | information being requested | `FindOrderById` |
| Exception | specific failure condition | `OrderNotFoundException` |

These are semantic expectations, not a required suffix list. A language may express them with its
own casing, prefixes and idioms.

## 18.4 Language profiles

### C#/.NET

Types, methods, properties, events and public members use `PascalCase`; parameters and locals use
`camelCase`; private fields follow the project's established convention; constants are
`PascalCase` or `UPPER_SNAKE_CASE`. Interfaces conventionally begin with `I`. Async methods end in
`Async` when they return a task and the suffix is meaningful at the call site. Generic parameters
use `T`-prefixed names. Extension methods are named for the operation they add. Framework-required
names (`Program`, `Startup`, controller actions) remain idiomatic.

### TypeScript and JavaScript

Types, classes, interfaces, enums and React components use `PascalCase`; functions, variables,
parameters and properties use `camelCase`; module-level constants are `UPPER_SNAKE_CASE` when they
are truly constant. Boolean names begin with `is`, `has`, `can` or `should` where the ecosystem
does not dictate otherwise. Hooks begin with `use` and follow the framework contract. Exported
names are part of the public surface and deserve the same care as contract names.

### Python

Classes and protocols use `PascalCase`; functions, methods, variables, parameters and modules use
`snake_case`; constants use `UPPER_SNAKE_CASE`. A leading underscore marks non-public names.
Dunder methods keep their fixed names. Type aliases are `PascalCase`. Decorators do not create a
new naming convention, and a framework-required name is documented rather than renamed.

### Go

Exported identifiers use `MixedCaps`; unexported identifiers use `mixedCaps`. Package names are
short, lower-case and describe the package's role, not a generic `util` or `common`. Interfaces
are usually named for the capability (`Reader`, `Writer`, `OrderStore`) rather than prefixed with
`I`. Receivers are short and consistent. Initialisms keep their conventional case (`ID`, `URL`,
`HTTP`). Error variables are named `err`; sentinel errors begin with `Err`.

### Java

Classes, interfaces, enums and records use `PascalCase`; methods, fields and parameters use
`camelCase`; constants use `UPPER_SNAKE_CASE`; packages are lower-case and domain-oriented. Boolean
accessors use `is`/`has`/`can` where the framework does not require `get`. Generic type parameters
use single uppercase letters or descriptive `T`-prefixed names. Annotations and framework-required
names remain idiomatic.

## 18.5 Enforcement

`N001` and `N002` execute in the Python and TypeScript reference enforcers. They inspect type
declarations in application units:

- **N001** reports a class, interface, type alias or enum that does not follow the language's type
  casing convention. It is a convention check, not a semantic judgement.
- **N002** reports a type whose name is a generic placeholder or ends in a generic role suffix. It
  is a candidate: the surrounding abstraction may make the role precise.

`N003` is **manual** in every profile. It covers responsibility accuracy, side effects, boolean
polarity, units, abbreviations, domain consistency, contextual sufficiency, boundary naming and
incidental lifecycle/version information. No portable static analysis can prove those claims.

The rules deliberately do **not** report:

- local variable names unless a language-specific rule says otherwise;
- framework, generated or external types;
- established abbreviations and domain terms documented in the glossary;
- a generic role name when the abstraction makes it precise and the decision is recorded;
- formatting or casing preferences beyond the language-specific type convention.

Go, .NET and Java carry the catalog entries but report `N001`–`N003` `executed: false` in this
revision. A full claim needs repository-scoped manual evidence, not a clean portable run.

A naming finding is not a mandate to rename an entire repository. Rename only when the change
improves comprehension at a boundary or call site, and treat public API, serialization, generated
code and compatibility-sensitive names separately.

## 18.6 Generated code, external contracts and legacy names

Naming exceptions are allowed, but they must be owned, scoped, reviewed and expiring (`G001`).
Legitimate cases include:

- generated code whose names are determined by a checked-in generator;
- serialization or protocol names fixed by an external contract;
- framework-required entry points, attributes or lifecycle methods;
- a legacy public API whose rename would break consumers;
- a domain abbreviation defined in the team's glossary.

The exception covers the name, not the concept. A legacy `CustRepo` may remain temporarily; its
new internal port should still be `CustomerRepository`, and the migration should record why the
legacy name remains and when it will be removed. An exception MUST NOT become a general mechanism
for avoiding meaningful names.

## 18.7 Integration with existing requirements

Naming does not replace ownership rules; it makes them visible:

- a module name should reflect its business capability, not a technical layer (`D001`–`D009`);
- a contract name should state the capability it exposes, not a consumer or a table (`P2`, `P3`);
- a constructor parameter should name the required input, not `data` or `deps` (`D011`, `D012`);
- a configuration identifier should state purpose and unit, consistent with `A006`;
- a component's name should not imply a lifetime that registration alone decides (`A007`–`A009`);
- a closure parameter should name the collaborator it receives (`D015`, `D016`);
- a query should read like a question and a command like an instruction (`P4`, chapter 16).

Where an existing rule already requires an explicit value or dependency, naming supplies the
semantic label; it does not duplicate the rule.

## 18.8 Generality and exceptions

| Architecture | Naming emphasis | Exception to document |
|---|---|---|
| Modular monolith | module capability and contract role | legacy folder names retained during migration |
| Microservices | service outcome, not database or framework | platform-required endpoint names |
| Event-driven | events name a past fact; commands name a request | wire-format names fixed by a broker |
| Functional | functions name transformations; effects are explicit | mathematical names established by the domain |
| Library/framework | public API names are the contract | compatibility aliases with an expiry |
| Plugin | plugin names state the capability, not the host | host-required registration names |
| Serverless | handler names state the trigger and outcome | runtime-required handler signature |
| Multi-tenant SaaS | tenant-scoped operations state the boundary | vendor identifiers embedded in external APIs |
| Generated code | generator owns the name | checked-in generator and regeneration test |
| Legacy system | new names improve the boundary; old names expire | compatibility shim with owner and date |

The principle does not prescribe a paradigm. A pure function, a class, a module and a capability
interface can all have clear names; none is preferred by the naming rule itself.

## 18.9 Review checklist

- [ ] Does each type name a responsibility or domain concept rather than a generic role (`N002`)?
- [ ] Does each operation name the action and outcome, not merely that something happened?
- [ ] Does any read-named operation create or mutate state (`N003`)?
- [ ] Do boolean names express a positive, unambiguous condition?
- [ ] Do values with units state the unit where the type does not?
- [ ] Are abbreviations either widely recognised or defined in the domain glossary?
- [ ] Is one domain concept named consistently across contracts, implementation and persistence?
- [ ] Is the name sufficient at its call site without repeating its enclosing context?
- [ ] Do boundary names distinguish contracts, implementations, commands, queries and events?
- [ ] Is incidental lifecycle, version or development history absent from the identity?
- [ ] Does the name follow the language's established casing convention (`N001`)?
- [ ] Are generated, external and legacy names backed by an owned, scoped, expiring exception?
- [ ] Does the report distinguish a convention finding, a generic-name candidate and a manual
      semantic review?

The objective is not decorative names. It is that a reader can navigate the system from its names:
what a component is for, what an operation does, what a value measures and where a responsibility
belongs.
