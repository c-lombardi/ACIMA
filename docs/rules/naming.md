# Naming rules (`N`)

Three rules. Naming is a semantic architectural concern: two are mechanical candidates and one is a
manual review requirement. A convention finding is not proof that a name is misleading, and a clean
scan is not proof that names communicate intent.

Full context: [Intent-revealing naming](../standard/18-intent-revealing-naming.md) ·
[Principles P14](../standard/01-principles.md#p14-intent-revealing-naming) ·
[Language profiles](../languages/index.md).

---

## ACIMA-N001 · Non-idiomatic type identifier

**Severity** `warning` · **Level** L3 · **Principle** P14.5

> A user-defined class, interface, type alias or enum MUST follow the target language's established
> type-name convention. Casing is a convention; semantic clarity is assessed separately.

### Violation

```python
class order_validator:          # ❌ Python types use PascalCase
    def validate(self, order):
        return bool(order)
```

```typescript
class order_validator {         // ❌ TypeScript types use PascalCase
  validate(order: unknown): boolean { return Boolean(order); }
}
```

### Finding

```text
ACIMA-N001  warning  host declares the type order_validator without the Python PascalCase
                     type-name convention.
  src/host/validators.py:3
  class order_validator:
```

### Why

Casing is not architecture by itself, but inconsistent type names make declarations harder to
recognise and break the ecosystem's shared conventions. The rule is deliberately limited to type
declarations: it does not enforce formatting, local variable style or a universal casing scheme.

### Fix

Rename the type using the language convention and keep the domain term: `OrderValidator`. Do not
rename a framework-required, generated or external type to satisfy the rule.

### Detection

Python and TypeScript inspect class, interface, type-alias and enum declarations in application
units. Python expects `PascalCase` (an optional leading underscore is allowed); TypeScript expects
`PascalCase`; .NET checks class, struct, record, interface and enum declarations. The scanners do not
see generated code, framework decoration or external packages. Go and Java report `executed: false`
in this revision.

---

## ACIMA-N002 · Generic responsibility name

**Severity** `warning` · **Level** L3 · **Principle** P14.1

> A module-owned type MUST NOT use a generic placeholder as a substitute for its actual
> responsibility. A generic role is permitted when the surrounding abstraction makes it precise and
> the decision is recorded.

### Violation

```typescript
class OrderHelper {              // ❌ Helper of what, exactly?
  validate(order: unknown): boolean { return Boolean(order); }
}

class PaymentManager {           // ❌ management is not a responsibility
  authorize(payment: unknown): boolean { return Boolean(payment); }
}
```

```python
class OrderUtility:              # ❌ utility is not a domain concept
    def validate(self, order):
        return bool(order)
```

### Finding

```text
ACIMA-N002  warning  host names the type OrderHelper after a generic role; name the
                     responsibility or domain concept instead.
  src/host/orders.ts:8
  class OrderHelper {
```

### Why

A generic name is an unbounded container. Every new responsibility can be justified as "helper"
work, so the type grows without a boundary and callers cannot tell what it owns. Naming the
responsibility (`OrderValidator`, `PriceCalculator`, `PaymentAuthorizer`) makes the boundary
visible before the implementation grows around it.

Generic names are not automatically wrong. `OrderRepository`, `PaymentGateway` and `OrderFactory`
may be precise roles. The finding asks for the responsibility; the reviewer decides whether the
role name already supplies it.

### Fix

Name the responsibility or domain concept, or split the type into the responsibilities it
currently hides. If the generic role is intentional, record why it is precise in this context and
keep it scoped.

### Detection

Python and TypeScript inspect user-defined type declarations. N002 reports exact names `Helper`,
`Manager`, `Handler`, `Processor`, `Utility`, `Service`, `Provider`, `Factory`, `Common`, `Base`,
`Default` and `Generic`, and names ending in `Helper`, `Manager`, `Processor`, `Utility`, `Common`,
`Default` or `Generic`. It does not report `OrderService`, `PaymentProvider` or `OrderFactory`.
Framework, generated and external types are not inspected. The .NET detector uses the same exact-name
and suffix set over application type declarations. Go inspects `TypeSpec` declarations with
`go/ast` in naming roles using the same exact-name and suffix set, so `OrderService`,
`RequestHandler` and `OrderFactory` are not reported; Go's `N001` and Java's `N001`–`N002` report
`executed: false`.

---

## ACIMA-N003 · Semantic naming clarity review

**Severity** `warning` · **Level** L3 · **Principle** P14.1–P14.5

> Names MUST communicate responsibility, behaviour, side effects, domain meaning and relevant
> units. Abbreviations, boolean polarity, contextual sufficiency and incidental lifecycle/version
> information require semantic review.

### Violation

```csharp
GetCustomer(id)                    // ❌ creates the customer when absent
Process(data)                      // ❌ what happens to the data?
bool NotDisabled                   // ❌ double negative
int timeout                        // ❌ unit unknown
class OrderServiceV2               // ❌ development history in the identity
```

```python
def get_customer(customer_id):      # ❌ silently creates on miss
    ...
```

### Finding

N003 is manual. A review records the identifier, the public or application surface, the reason it
is misleading, the proposed name and the reviewer. It is not emitted by the portable enforcers.

### Why

Static analysis can check the spelling of a type but cannot establish that `GetCustomer` creates a
customer, that `timeout` means milliseconds, that `NotDisabled` is understood correctly at every
call site, or that `OrderServiceV2` no longer describes the component. Those are semantic claims,
and presenting them as deterministic findings would be false confidence.

### Fix

Rewrite the name in the domain vocabulary:

- state the operation and outcome (`FindCustomerById`, `GetOrCreateCustomer`, `AuthorizePayment`);
- make a meaningful side effect explicit in the name;
- use a positive boolean (`IsEnabled`, `HasPermission`, `CanSubmitOrder`);
- name the unit or scale when the type does not (`timeoutMilliseconds`, `retentionDays`);
- expand local abbreviations or add the term to the domain glossary;
- keep one term per domain concept across boundaries;
- remove incidental lifecycle, version and development history from the identity;
- rely on the enclosing abstraction where it already supplies context.

### Detection

Manual review in every profile. The reviewer records one repository-scoped entry per required
scope in `acima/evidence/manual-evidence.json`; without it, a full claim is a `PARTIAL ASSESSMENT`.
`N001` and `N002` can point at likely candidates, but they do not decide responsibility, side
effects, units, domain consistency or boolean clarity.

---

## What the rules do not decide

- Formatting, line length, comments or documentation style.
- Local variable names, unless a language-specific analyzer chooses to add a convention.
- The correctness of a domain term; that belongs to the domain owner.
- Whether a public API rename is compatible; that is a versioning decision.
- Generated code, serialization contracts or framework-required names without an owned exception
  (`G001`).

Naming is a comprehension requirement, not a mandate to rename a repository in bulk. Prefer targeted
changes at boundaries and call sites where the current name causes a real misreading.
