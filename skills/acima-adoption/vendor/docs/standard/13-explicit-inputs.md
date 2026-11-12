# 13. Explicit inputs

A component that needs something must ask for it. This chapter makes that sentence enforceable.

The obligation is deliberately narrow and deliberately absolute:

> **If a component or operation requires an input to perform its intended behaviour, that input MUST
> be required wherever the component is constructed or the operation is invoked.**

A developer reading a constructor or a call site must be able to see what is being supplied. Nothing
may be supplied on their behalf by an argument they did not make.

## 13.1 Why hidden inputs are an architectural defect

A default parameter looks like convenience. In practice it is a second, undeclared contract:

- **It creates a second construction path.** `new OrderService(repo)` and `new OrderService(repo, payments)`
  are different objects with different capabilities, and neither the type nor the call site says which
  one the system runs. Tests exercise one path; production takes the other.
- **It hides ownership.** If a default value is meaningful, someone owns it — a team, a configuration
  key, a policy. A literal in a signature is an owner nobody can name (`A002`, `G006`).
- **It makes behaviour change without a code change.** A default that reads the clock, picks a
  currency or chooses a store changes what the system does while every caller stays green.
- **It survives refactoring.** Moving the class, renaming the method, extracting an interface — the
  omission is invisible in all of them. By the time the behaviour is wrong, no call site looks guilty.

This is why the requirement targets **required inputs**, not "all parameters". Optional behaviour is
legitimate; hiding it behind an omitted argument is not.

## 13.2 Construction

A module-owned constructor MUST require every dependency and configuration value the object needs
in order to be usable. The composition boundary supplies them; the object never resolves them.

```csharp
// ❌ D011 — two construction paths, one of them undocumented
public OrderService(IOrderRepository repository, IPaymentService? payments = null)

// ✅ one path; every dependency is visible at the composition boundary
public OrderService(IOrderRepository repository, IPaymentService payments)
```

```python
# ❌ D011 — the fallback invents a dependency the caller did not choose
def __init__(self, gateway=None):
    self._gateway = gateway or FakeGateway(...)

# ✅
def __init__(self, gateway: PaymentGateway) -> None:
    self._gateway = gateway
```

A constructor with a default is a constructor with two signatures, and only one of them is tested.
The same applies to a nullable dependency whose absent value selects a fallback implementation, to a
parameterless overload used by "just the tests", and to conditional construction that silently omits
a collaborator.

If the behaviour is genuinely optional, model the absence explicitly: a policy object, a documented
no-op implementation of the port, or a required value whose type says "none" (`NoNotifier`) — never
an omitted argument.

## 13.3 Invocation

A module-owned method or function MUST NOT use an optional parameter, a default value or an implicit
fallback to conceal a decision its caller owns.

```typescript
// ❌ D012 — did the caller decide not to notify, or did they not think about it?
createOrder(request, sendNotification = true)

// ✅ the caller supplies the decision; the branch is in the open
createOrder(request, sendNotification: boolean)
```

When an operation has several modes, the fix is a shape that names them, in this order of preference:

1. **Require the argument.** Most "optional" flags are required once the question is asked.
2. **Split the operation.** `placeOrder` and `placeOrderQuietly` are clearer than a boolean.
3. **Take an explicit options value** whose fields are themselves required — a request object is a
   good home for a group of decisions, provided it does not default them.
4. **Take a policy or strategy dependency** when the decision is a rule rather than a flag.

Do not introduce a hierarchy of interfaces to avoid one boolean. The test is visibility, not
abstraction count.

## 13.4 A nullable value is not an optional parameter

The distinction is the centre of this chapter, and the rule depends on it:

| Shape | Meaning | Verdict |
|---|---|---|
| `deliveryDate: Date \| null` — no default | the caller **must** supply a value; the value may legitimately be "none" | compliant |
| `deliveryDate?: Date` | the caller may omit it; absence triggers whatever the implementation does | `D012` |
| `deliveryDate: Date \| null = null` | the omission itself carries meaning | `D012` |
| `payments: IPaymentService \| null` (required) | the caller explicitly chose "no payments" | compliant |

A required nullable parameter is a place where the domain genuinely has absence: an order without a
delivery date, an account without a referrer. That is data, not hidden behaviour. What ACIMA forbids
is **omission** as a way to select a behaviour.

Nullable return values, `Option`/`Maybe` fields and optional domain data are unaffected. `C001`–`C007`
continue to govern how contract types carry them.

## 13.5 Where a default belongs

Defaults do not disappear; they move to a place that owns them.

| Default kind | Owner | Expression |
|---|---|---|
| Dependency | composition boundary | construct the concrete implementation there and pass it |
| Configuration value | configuration | read it once at the boundary, pass the resolved value |
| Business rule | policy/value object | named implementation of a port, or an explicit policy type |
| Compatibility default | the published contract | documented additive member, per chapter 5 §5.7 |
| Language/framework requirement | the framework adapter | documented, narrow, and covered by a waiver or a framework note |

The rule of thumb: **a default may live where the value is owned.** A signature is not an owner.

## 13.6 Framework and compatibility exceptions

Some optional parameters are part of a contract ACIMA does not control. They are exceptions, not
holes in the rule:

- **Framework entry points** — lifecycle hooks, serializers, ORM constructors and callbacks whose
  signatures the framework defines. The exception is the callback itself, not the module-owned
  component it calls.
- **Generated code** — generated clients stubs, migration scaffolds, protocol buffers. Exclude the
  generated directory; do not weaken the rule for hand-written code beside it.
- **Published compatibility APIs** — a library that already shipped `method(arg, options?)` and cannot
  break consumers. The parameter stays, and the compatibility obligation is recorded as an owned,
  expiring waiver (`G001`, `G002`) with the reason and the removal plan.
- **Test doubles** — a fake may accept narrower inputs than the port; it may not require fewer.

An exception is acceptable when it is **named, scoped, owned and expiring**. "It was easier" is none
of those. A repository that exempts a whole layer has not adopted this chapter.

## 13.7 Enforcement and the review boundary

Two rules carry the requirement:

| Rule | Detects | Severity |
|---|---|---|
| `D011` | an optional or defaulted parameter on a module-owned constructor | `error` |
| `D012` | an optional or defaulted parameter on a module-owned method or function | `error` |

Both are `automation: "automated"` L1 errors. There is no migration ratchet: an optional or
defaulted parameter on a module-owned constructor, method or function is prohibited. A repository
that cannot remove the parameter must record a named, scoped, owned and expiring waiver under
`G001`/`G002`; ordinary adoption does not lower the rule.

**Scope.** The rules apply to the declared behaviour units: `implementation`, `host`, `adapter` and
`port`. Contract types are data with compatibility semantics — an optional member there is the
additive change chapter 5 §5.7 describes, and `C007` already governs one-step construction. Test,
tooling and end-to-end units are excluded because a fixture's convenience is not production
behaviour. The exclusions are deliberate and documented; they are not a silent skip.

**What the portable rules do not decide.** Static analysis can see that a parameter may be omitted;
it cannot see whether the omitted behaviour matters. A finding is a defect. The two compliant outcomes are:

- the input is required → make it required (`D011`/`D012` fixed);
- the omission is genuinely optional → model it explicitly, or record the exception.

Overload resolution, framework-managed construction, and reflection-based wiring are not analysed;
those remain manual-review cases. A clean portable run is not evidence that a constructor has no
hidden path.

**Go and .NET** report both rules `executed: false` in this revision. Their catalogs name the rules
so the obligation is visible; a full claim needs manual evidence for them (chapter 8 §8.9).

## 13.8 Relationship to the other rules

This chapter adds no new mechanism; it makes existing obligations visible at the signature.

- `D001`/`P4` say *what* a module may depend on. `D011` says the dependency must actually arrive.
- `L004` forbids resolving a peer at runtime. `D011` forbids receiving it by omission. Both leave the
  object with no declared dependency graph when violated.
- `C007` requires contract state to be obvious at construction. `D011` requires the same of the
  object constructed from those contracts.
- `G001`/`G002` govern every exception: a retained optional parameter is a waiver with an owner and
  an expiry, not a comment.
- `A002`/`G006` govern configuration: a default value in a signature bypasses the declared owner.
- `D013`/`D014` continue the same principle at the composition boundary: components are chosen
  explicitly, and their dependencies arrive at construction (chapter 15).

Where rules overlap, they are not duplicated: `D011`/`D012` judge the *shape of the signature*;
`D001`, `L004` and `C007` judge the edges and the contract types around it.

## 13.9 Review checklist

- [ ] Does every constructor require every dependency the object uses (`D011`)?
- [ ] Is there exactly one way to construct each module-owned component, and does its composition
      boundary use it?
- [ ] Does every method that branches on an input require that input (`D012`)?
- [ ] Is each nullable parameter required, and does the caller knowingly pass `null`?
- [ ] Does every retained default have a named owner — configuration, policy, framework contract or
      compatibility waiver?
- [ ] Are generated and framework files excluded by path, with the exclusion recorded?
- [ ] Do the tests construct the same graph production does?

If a reviewer cannot answer "who decided this value?" from the diff, the input is not explicit yet.

## 13.10 Named arguments at the call site

In languages that support named arguments, every argument supplied to a statically resolved
module-owned function or method MUST use the receiving parameter's name at the call site. The
reader should not have to navigate to the declaration to determine which value is being supplied.

Python:
    create_order(request_id=request_id, customer_id=wrong_variable, name=user_name)

C#:
    CreateOrder(requestId: requestId, customerId: wrongVariable, name: userName);

The label exposes the assignment; it does not prove that the value itself is semantically correct.
A matching label can still carry the wrong variable. This rule makes that mismatch directly
visible in the raw diff without requiring a lookup of the declaration.

This rule does not require artificial options objects, wrapper types, or one-property objects to
simulate labels in languages without native named-argument call syntax. TypeScript/JavaScript and
Go do not have native named arguments and report this rule as not executed. Use explicit request
or contract types when that shape is independently justified, not solely to imitate labels.

Scope: Python and C# reference enforcers report unlabeled arguments when they can resolve a call
to a locally declared module-owned function, method, or constructor. Built-ins, unresolved
third-party calls, reflection, dynamic dispatch, and argument expansion that cannot be statically
resolved remain outside the deterministic subset and require review. This is not a claim that
every call in a repository has been semantically resolved.

This requirement is separate from D011 and D012. It does not prohibit nullable values or nullable
parameters. A required nullable parameter remains valid and must still be supplied; an
optional/defaulted parameter remains governed by D011/D012.

## 13.11 Enforcement and the review boundary

D017 is an automated L1 warning. Python and .NET enforce it using their native named-argument
syntax. TypeScript/JavaScript and Go record executed:false because their call syntax does not
support parameter labels. A finding identifies the call site and the parameter label to use.
