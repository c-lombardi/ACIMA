# 16. Functional composition and dependency visibility

> **Normative.** An application dependency MUST remain explicitly declared, traceable and
> inspectable across its entire lifecycle: declaration, acquisition or construction, binding or
> composition, transfer, invocation and consumption. That obligation does not change because the
> dependency is supplied to a lambda, captured by a closure, bound with partial application, passed
> to a higher-order function or registered as a callback.

This chapter does **not** prohibit functional programming. Pure transformations, immutable data,
higher-order functions, currying and closures are all legitimate. The rule is about application
dependencies: repositories, services, clients, adapters, logging, configuration, security context,
resource handles and mutable application state. A pure helper may close over a constant or a
transformation; it must not silently close over a collaborator whose ownership belongs to the
application.

## 16.1 Why the lifecycle matters

A dependency can be visible at its declaration and invisible at the point where behaviour is
decided:

```typescript
// The repository exists, but createOrder's callers cannot see that it is required.
const createOrder = (request: CreateOrderRequest) =>
  orderRepository.save(request);
```

```python
order_repository = OrderRepository()

def create_order(request):
    return order_repository.save(request)
```

The function signature says `request` is the only input. The actual behaviour depends on a
module-level object, its lifetime, its configuration and its test replacement. The dependency graph
was not declared at the function; it was inherited from the file's runtime state. That is the
functional-composition version of a hidden constructor default (`D011`) or a property injection
(`D014`).

The same defect appears when a dependency is supplied earlier:

```typescript
// Binding at a component call site hides which collaborator the returned handler uses.
export const makeHandler = (repository: IOrderRepository) =>
  saveOrder.bind(null, repository);
```

The binding expression names the repository, but the returned handler does not. A caller sees
`handler(request)` and cannot tell what it will write to. If this binding happened at the
composition boundary, the application could point to it; inside a component, it is a new hidden
dependency.

## 16.2 The normative rule

For every application-owned dependency, a reader MUST be able to identify:

1. where it was declared;
2. where it was constructed or acquired;
3. where it was bound or composed;
4. how it reached the operation that uses it;
5. which component consumes it.

A component MUST receive its application dependencies through one of these visible paths:

- a constructor or composition-function parameter;
- an explicit function parameter at the operation's call site;
- a declared field supplied by the framework/constructor and visible in the component's contract;
- an explicit factory parameter at the composition boundary.

A function MUST NOT introduce a new application dependency by closing over a module binding or an
enclosing local that is not one of its declared parameters. A component MUST NOT pre-bind an
application dependency into a function it returns; that binding belongs at the composition
boundary. These are `D015` and `D016`.

## 16.3 Closures and callbacks

Closures are the normal way to express a pure transformation:

```typescript
const withTax = (rate: number) => (amount: number) => amount * (1 + rate);
```

`rate` is a value parameter, not an application collaborator. This is legal and should remain
legal. A closure that captures a module-level `taxRate` is a review candidate, not because closures
are bad, but because the rate's owner is now invisible at the call site (`A005`/`A006` may also
apply).

The distinction is ownership, not syntax:

| Captured binding | Example | Verdict |
|---|---|---|
| Pure value parameter | `(rate) => (amount) => amount * rate` | allowed |
| Pure local/constant | `const factor = 2; return (n) => n * factor` | allowed |
| Application collaborator parameter | `(repository) => (request) => repository.save(request)` | allowed: the dependency is declared by the outer function |
| Module-level collaborator | `const repository = new Repo(); (request) => repository.save(request)` | `D015` |
| Enclosing local collaborator | `const repository = new Repo(); return (request) => repository.save(request)` inside a function that did not declare it | `D015` |
| Constructor field | `this.repository.save(request)` | allowed if the field is an explicit constructor dependency (`D014` does not apply) |
| Framework context/service locator | `container.get(Repo)` inside the callback | `L004` |

A callback registered with a framework MAY close over a dependency **when the registration site is
the composition boundary and the dependency is named there**. A callback created inside an
application component must receive the dependency as a parameter or from an explicit constructor
field. A callback that reads a global mutable service is `D015` plus `L004`.

## 16.4 Currying is not the problem

Currying with every dependency as a parameter is explicit:

```typescript
const createOrder =
  (repository: IOrderRepository) =>
  (payments: IPaymentService) =>
  (request: CreateOrderRequest) =>
    repository.save(request);
```

Each layer declares the dependency it introduces. A reviewer can stop at any layer and see what is
still required. This is allowed. The same is true in Python:

```python
def create_order(repository):
    def handler(request):
        return repository.save(request)
    return handler
```

`repository` is an explicit parameter of the enclosing function; the inner function captures a
declared parameter, not an undeclared module binding. If a caller loses that context, the problem
is the call site's missing argument, not the curried form.

Currying becomes a problem when it hides a collaborator that was never a parameter:

```typescript
const repository = new OrderRepository();

// The empty first layer hides the real dependency.
export const createOrder = () => (request: CreateOrderRequest) =>
  repository.save(request);
```

That is `D015`, not a prohibition on currying.

## 16.5 Partial application and method binding

Partial application is a legitimate way to derive a function by fixing arguments. Fixing a
**pure** argument is ordinary functional code:

```typescript
const double = multiply.bind(null, 2);
const withPrefix = partial(prefix, 'order-');
```

Fixing an **application dependency** changes the dependency graph. It must happen at the
composition boundary, where the binding is visible as application wiring:

```typescript
// host/main.ts — the composition boundary names the repository and the handler.
const repository = new SqlOrderRepository(connection);
const handler = saveOrder.bind(null, repository);
```

```typescript
// orders/service.ts — ❌ the component creates a handler with an undeclared dependency.
export const makeHandler = (repository: IOrderRepository) =>
  saveOrder.bind(null, repository);
```

`D016` reports the second form. It does not report `bind`/`partial` with pure values, and it does
not report a host binding. The host is allowed to compose; the component is not allowed to hide a
new collaborator in a returned function.

A factory is treated the same way. A factory that receives dependencies as arguments is explicit;
a factory that closes over them must either be at the composition boundary or be refactored to take
them as parameters. A factory that constructs a dependency internally is not automatically wrong —
the dependency is visible in the factory body — but its lifetime and ownership still need review.

## 16.6 Higher-order functions and composition

`map`, `filter`, `reduce`, `compose`, `pipe` and similar combinators are encouraged when their
arguments are pure or when every application dependency is explicit. These are fine:

```typescript
const names = orders.map((order) => order.id);
const total = orders.reduce((sum, order) => sum + order.amount, 0);
const normalize = compose(trim, lower);
```

This is not:

```typescript
// map's callback captures a repository and performs IO while pretending to be a transformation.
const saved = orders.map((order) => repository.save(order));
```

The second example is `D015`; it also usually indicates that the wrong layer is doing IO. The
standard does not ban side effects in a callback, but it requires the collaborator to be a declared
input or field. It also does not require replacing `compose`/`pipe` with classes; explicit function
composition is often the clearer representation.

A higher-order function that returns a function MUST make the returned function's application
dependencies visible in its parameters or in the composition boundary. A returned closure over an
undeclared collaborator is `D015`; a returned function that has already been partially applied with
one is `D016`.

## 16.7 Language profiles

| Language | Legitimate explicit form | Hidden form to avoid | Automated coverage |
|---|---|---|---|
| TypeScript/JavaScript | function/arrow parameters; constructor fields; host bind/partial; pure HOFs | module-level collaborator captured by an arrow; `bind`/`partial` of a collaborator inside a component | `D015`, `D016` |
| Python | function/lambda parameters; constructor fields; host `functools.partial`; pure closures | module-level/global collaborator closed over; `partial` of a collaborator inside a component | `D015`, `D016` |
| C#/.NET | constructor/base parameters; method parameters; explicit delegates; host composition | lambda/method group capturing `IServiceProvider` or a service; partial-like delegate binding inside a component | manual in this revision |
| Go | `NewX(dep)` arguments; explicit struct fields set at construction; pure closures | function literal closing over a package/global repository; `init()` wiring | manual in this revision |
| Java | constructor/method parameters; explicit factories; host composition | lambda/anonymous class capturing a service field or `ApplicationContext`; field injection | manual in this revision |

The portable enforcers implement `D015` and `D016` for Python and TypeScript. Go and .NET carry the
catalog entries but report both `executed: false`; Java has no reference enforcer. A profile is not
supported until its fixtures and enforcer pass.

### TypeScript specifics

The TypeScript scanner resolves a lightweight function-scope model. It reports a dependency name
read in a function body when it is bound at module scope or in an enclosing local, unless an
enclosing function declares it as a parameter. It does not perform full type checking, and a
callback created through an unqualified framework helper may be a manual-review item. Field access
through `this` is not a closure capture; the constructor still has to declare the field (`D014` if
it is injected after construction).

### Python specifics

The Python AST scanner collects direct loads in functions and lambdas. A name bound by an enclosing
**parameter** is the explicit curried form and is allowed. A name resolved from module scope or an
enclosing local is `D015`. A `functools.partial` call with a dependency-like argument inside an
implementation or adapter is `D016`. Pure closures over constants and transformations are ignored.
Dynamic `getattr`/`globals` lookup is a manual-review item.

## 16.8 Examples

### 16.8.1 Violation: a module-level capture

```typescript
const orderRepository = new SqlOrderRepository(connection);

export const createOrder = (request: CreateOrderRequest) =>
  orderRepository.save(request);
```

Finding: `ACIMA-D015` — captures `orderRepository` from an enclosing scope.

### 16.8.2 Correction: the dependency is a parameter

```typescript
export const createOrder = (
  orderRepository: IOrderRepository,
  request: CreateOrderRequest,
) => orderRepository.save(request);
```

The host supplies `orderRepository`; a test can supply a fake without module state.

### 16.8.3 Legal currying

```typescript
export const createOrder =
  (orderRepository: IOrderRepository) =>
  (payments: IPaymentService) =>
  (request: CreateOrderRequest) =>
    repositoryAndPayment(orderRepository, payments, request);
```

Every collaborator is a parameter. The layers may be partially applied at the host, where the
binding is visible.

### 16.8.4 Violation: partial application inside a component

```python
def make_handler(order_repository):
    return functools.partial(save_order, order_repository)
```

Finding: `ACIMA-D016` — the component pre-binds `order_repository` into a returned handler. Move
the `partial` to the host, or return a function that takes the repository as a parameter.

### 16.8.5 Correct: partial application at the boundary

```python
# host/main.py
repository = SqlOrderRepository(connection)
handler = functools.partial(save_order, repository)
```

The composition boundary names both the repository and the binding. Callers receive a handler whose
dependency was deliberately supplied by the application, not discovered inside the component.

### 16.8.6 Pure higher-order function

```typescript
export const applyTwice = <T>(transform: (value: T) => T, value: T): T =>
  transform(transform(value));
```

No application dependency is captured. This remains legal; the rule is not a ban on HOFs.

### 16.8.7 Manual review: dynamic callback registration

```python
registry.register(getattr(module, handler_name))
```

The scanner cannot resolve `getattr` or the registry's runtime lookup. A reviewer must establish
which handler is selected, what it captures and whether the registration is at the composition
boundary. The correct result is a manual-review item, not an automatic pass.

## 16.9 Generality and exceptions

The same invariant applies to every architecture family, but the visible form differs:

| Architecture | Explicit form | Exception to document |
|---|---|---|
| Modular monolith | function/constructor parameters; host composition | a plugin callback may close over a host-owned capability if the registration site and capability are named |
| Microservices | handler/consumer constructor parameters; per-service host | framework middleware may capture infrastructure context, not domain services |
| Library | public function parameters and documented factory contracts | compatibility overload that binds a default must be documented and tested; it is still a dependency |
| Plugin | plugin factory receives capabilities; host registers the loader | plugin discovery may capture the plugin's own configuration, not another plugin's service |
| Serverless | function handler parameters and explicit client construction | runtime-provided request context is infrastructure; application clients must still be visible |
| Generated code | generated signatures must include dependencies; generated binding is reviewed | generated closure is acceptable only with deterministic, checked-in source and a boot test |
| Framework-managed entry point | constructor parameters; host registration | framework context/authorization primitives may be injected by the framework if the application boundary is documented |

An exception MUST be owned, scoped, expiring and reviewed (`G001`). It MUST preserve as much
inspectability as possible: name the captured dependency, the binding site and the test that proves
it. “It is just a closure” is not an exception; it is the defect.

## 16.10 Enforcement and limits

`D015` and `D016` execute in Python and TypeScript:

- Python uses the AST to compare direct loads in each function/lambda with its parameters and
  locals, then walks enclosing scopes. Module bindings and enclosing locals are captures; enclosing
  parameters are the explicit curried form. `functools.partial` in an implementation or adapter is
  `D016` when an argument names a dependency.
- TypeScript builds a lightweight function-scope list from arrows and function declarations,
  compares identifiers with parameters/locals, and consults module bindings and enclosing scopes.
  `partial(...)` and `.bind(...)` in an implementation or adapter are `D016` when an argument names
  a dependency.
- Both are **candidate detectors**. They do not type-check, resolve a container, inspect a
  framework's dependency graph, evaluate `getattr`/`globals`, understand generated code, or prove
  that every callback's binding site is the composition boundary.
- Pure closures over constants and transformations are intentionally not findings. A dependency
  captured through an unqualified wrapper or a framework-specific mechanism remains manual review.
- Go, .NET and Java report the rules `executed: false` (or have no enforcer). A clean portable run
  is not evidence for them.

The report MUST distinguish a confirmed syntactic capture, a potential framework capture, a
reviewed composition-boundary binding, an unsupported profile and a manual-review requirement. It
MUST NOT say that registration presence or a clean scan proves the runtime graph.

## 16.11 Review checklist

- [ ] Does every operation declare each application dependency it uses, directly or through an
      explicit enclosing parameter/field?
- [ ] Does any function close over a module-level or enclosing-local repository, service, client,
      adapter, logger, configuration object or resource handle (`D015`)?
- [ ] Is every partial application or method binding of a dependency at the composition boundary
      (`D016`)?
- [ ] Does a curried function introduce every dependency as a parameter rather than an empty layer
      over a hidden value?
- [ ] Are callbacks registered with a dependency that is named at the registration site?
- [ ] Are `compose`/`pipe`/`map`/`filter` callbacks pure, or do they receive their collaborators
      explicitly?
- [ ] Does a factory accept its dependencies, or is it visibly located at the composition boundary?
- [ ] Are framework-managed callbacks and generated bindings backed by manual evidence?
- [ ] Does the report name the captured dependency, the binding site and the remaining limitation?

Functional composition is a tool for making behaviour smaller and clearer. A dependency that becomes
invisible at the call site makes the code smaller and the architecture less clear. The standard keeps
the first and rejects the second.
