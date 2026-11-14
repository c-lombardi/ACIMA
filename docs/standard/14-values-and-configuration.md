# 14. Values, constants and configuration

> **Every meaningful value should have one identifiable, immutable declaration at the highest
> appropriate ownership boundary. Its identity is determined by what it represents, not by its
> literal value.**

This chapter is normative. It applies to every repository in base mode at L3. It does not require
every literal to become a constant, every constant to become configuration, or every configuration
value to become dynamically adjustable.

## 14.1 The obligation

A meaningful primitive value MUST have an identifiable name, purpose, owner and declaration. A
developer must be able to answer, from the source and its composition:

- what the value represents;
- why it exists;
- which module, type or component owns it;
- where its one declaration is;
- which consumers receive it;
- whether it can change, and under whose authority;
- whether changing it requires a deployment.

The seven classifications are:

| # | Classification | Typical form | Owner |
|---|---|---|---|
| 1 | Local implementation literal | a value whose meaning is obvious at the expression | the containing function or type |
| 2 | Named constant | a name in the component that owns the value | that component |
| 3 | System-level constant | a named value shared by units of one system | the composition boundary or the module that genuinely owns the concept |
| 4 | Shared configuration | configuration consumed by several units with the same meaning | the system or service that owns the concept |
| 5 | Runtime-adjustable configuration | a value an operator may change without a deployment | the operating service, with an explicit refresh contract |
| 6 | Deployment or environment configuration | a value that differs between development, staging and production | the deployment environment and the resolving composition boundary |
| 7 | Secret | a credential or other sensitive value | the secret store, resolved at the boundary |

The classifications are not interchangeable. A deployment setting is not a business policy, a secret
is not an ordinary configuration file entry, and a fixed constant is not a runtime knob.

**Related rules.** `A005` covers ambient configuration access; `A006` covers meaningful value
ownership, immutability and semantic consolidation; `A002` covers cross-module configuration keys;
`P4.7` and `P4.8` state the principle. The language profiles document where enforcement is automatic
and where it is manual.

## 14.2 When a literal is meaningful

A literal is meaningful when at least one of these is true:

- it influences application behaviour, a business rule or a security decision;
- it is an operational threshold, timeout, retry count, rate limit, batch size, retention period,
  capacity or concurrency limit;
- it identifies a protocol, endpoint, queue, topic, bucket or other integration setting;
- it is a repeated string with application meaning, not merely a repeated token;
- a reviewer would need to ask why this exact value was chosen.

The following ordinarily do **not** require promotion:

- loop indices and trivial arithmetic operands;
- empty collection or object initialization;
- structural values whose meaning is obvious from the local expression;
- values required by language or framework syntax;
- a value whose extraction would make the expression harder to understand without adding meaning.

Occurrence count is not a criterion. A meaningful value used once still needs a name and an owner; a
literal repeated ten times may still be incidental formatting.

A named declaration is not automatically compliant. It can still be mutable, duplicated, owned by
the wrong scope, or classified as a constant when it is really deployment or runtime configuration.
Conversely, an inline value is not automatically a defect: it is a candidate for review.

## 14.3 Ownership, immutability and declaration

### 14.3.1 One declaration at the highest appropriate owner

A meaningful value MUST have one identifiable declaration. When several declarations appear to
represent the same semantic value, they SHOULD be consolidated at the highest appropriate common
owner: the broadest scope that genuinely owns the meaning and whose consumers are expected to change
together.

That owner may be:

- a single type or source file, when all uses share one local policy;
- a module-owned constants module or value object, when several files in one module share it;
- a composition boundary or typed settings object, when several modules genuinely share an
  application concept;
- deployment or environment configuration, when the value varies by deployment.

The highest appropriate owner is not a global constants file. Unrelated values MUST NOT be collected
there merely because a central location is convenient. Values owned by independently deployed
systems MUST NOT be centralized without an explicit shared ownership or contract relationship.

### 14.3.2 Immutable declarations

Where the language supports it, a meaningful value MUST use an immutable constant or equivalent
immutable construct. Appropriate mechanisms include:

- compile-time constants (`const`, `final`, `static final`);
- static readonly fields;
- immutable module-level declarations;
- frozen or readonly value objects;
- immutable configuration snapshots with explicitly controlled replacement.

A language that lacks a keyword-level guarantee MUST use its idiomatic equivalent: an unexported
field with a constructor, value semantics, a copy-on-write policy, or a reviewed naming convention.
The mechanism differs; the architectural obligation does not.

Distinguish carefully:

- **An immutable binding** prevents rebinding the name.
- **An immutable value** also prevents mutation of the represented state.
- **A readonly reference** to a mutable object is not an immutable value.
- **A mutable configuration snapshot** is acceptable when replacement is explicit, validated and
  observed; the snapshot itself should not be edited in place.
- **A genuinely mutable value** is acceptable when mutation is part of its domain semantics or
  lifecycle, and the reason is explicit.

A meaningful value MUST NOT remain unnecessarily mutable merely because its current value is not
expected to change. `let`, `var`, a writable field, a mutable module global or a mutable settings
object requires a reason when the value is policy.

### 14.3.3 Declaration visibility

A meaningful value owned by a file, component or type MUST have one identifiable declaration near
the beginning of its owning source scope, following the language's idiomatic conventions.

The declaration MAY remain in the narrowest scope that genuinely owns it. Do not move a value to a
broader scope solely to satisfy a source-layout convention. Conversely, do not bury a policy value in
the middle of an implementation when a reviewer needs it to understand the component's behaviour.

This is a reviewable structural requirement, not a demand for identical physical layout across
languages. A local constant beside its only consumer can be visible and appropriately scoped; a
module-level policy buried after hundreds of lines of executable code is not.

### 14.3.4 Semantic identity and consolidation

ACIMA evaluates meaningful values by semantic purpose, not merely by literal value.

When identifying duplicates, begin with the variable, field or parameter that receives the value.
Names such as `maximumRetryAttempts`, `requestTimeout`, `retentionDays`,
`maximumConcurrentWorkers` and `maximumBatchSize` are evidence about intended meaning.

Follow the value through its relevant data flow:

1. the original declaration or literal;
2. the receiving variable or parameter;
3. assignments and transformations;
4. function and method arguments;
5. downstream parameters;
6. consumer decisions and behaviour;
7. ownership and composition boundaries.

Matching values do NOT establish matching meaning. These remain different policies:

```csharp
private const int MaximumOrderAttempts = 3;
private const int MaximumPaymentAttempts = 3;
```

Matching identifiers do NOT establish matching meaning either. A `Timeout` of `30` may be seconds in
one component and milliseconds in another. Evaluate at least:

- the receiving identifier and type;
- units and representation;
- domain meaning;
- module and component ownership;
- data-flow context and downstream use;
- whether the values are expected to change together.

If equivalence cannot be established confidently, preserve separate declarations and report the
candidate for human review. Static analysis MUST NOT claim semantic equivalence from equal literals
or matching names.

When equivalence is established, consolidate genuinely identical semantic values:

- several methods in one file using the same policy: one declaration in the owning file or type;
- several files in one module using the same policy: one declaration at the appropriate module-owned
  boundary;
- several components genuinely sharing a system value: one declaration at their highest genuine
  common owner, explicitly supplied to consumers;
- a value that varies by environment or deployment: application or deployment configuration.

Do not consolidate values across independently deployed systems unless an explicit shared ownership
or contract relationship justifies it. Do not create a global constants module as a shortcut.

### 14.3.5 Explicit propagation

A shared value MUST be supplied explicitly to the components that consume it. Replacing duplicate
literals with ambient globals, hidden singleton lookups, mutable static state, service locators,
implicit environment reads or hidden configuration access does not establish ownership; it conceals
it. Apply `A005`, `A002` and the explicit-input requirements.

### 14.3.6 Meaningful defaults

A default is a value the caller did not choose. It is legitimate when it is a declared policy the
owner reviews — a documented fallback, a framework-required optional parameter, a compatibility
default on a published library API. It is not legitimate when it silently decides an application
input the caller should supply (`D011`, `D012`). The distinction is ownership, not syntax.

Do not move a default into a composition boundary as a bare literal and call it fixed. Give it a name
in its owner: a system constant, a typed configuration value, or a documented policy object.

## 14.4 Configuration categories

A **configuration category** is the declared nature and change model of a value. It determines who
owns the value, whether it may change without a deployment, and what validation and audit it needs.

### Code-owned constants

Values that are stable within a version and owned by the software itself SHOULD remain named
immutable declarations in source:

- protocol and algorithm identifiers;
- fixed invariants;
- stable domain constants;
- policies intentionally versioned with the software.

Do not expose these as runtime configuration merely because a configuration system exists.

### Application and deployment configuration

Values that vary by environment, deployment or operational context SHOULD use the appropriate
configuration mechanism: application configuration, shared configuration, deployment manifests,
CI/CD environment configuration, environment variables or a configuration platform.

The composition boundary MUST resolve, validate and supply these values explicitly. Making every
constant a global configuration entry is not a goal.

### Runtime-adjustable configuration

Values intended to change without deploying a new version remain subject to §14.5. A configuration
value is not runtime-adjustable merely because it is stored outside source code. Without validation,
authorization, audit, propagation, refresh, failure behaviour and rollback, it is deployment
configuration with a misleading label.

### Business and domain policy

A business or domain policy represents a rule the business owns: a maximum order value, a refund
window, an eligibility threshold. It needs a named owner, review and an explicit change process;
making it an operator-adjustable setting may be inappropriate.

### Secrets

Secrets are credentials, signing keys and tokens. They MUST be resolved through the environment's
secret mechanism and MUST NOT be committed, logged, placed in ordinary configuration files, or read
by a module that does not own them (`A002`). A secret-looking literal in source is never made safe by
renaming it as a constant.

A value that changes category needs an explicit decision. Moving a business policy into runtime
configuration changes who can change the behaviour without a review.

## 14.5 Runtime configuration contract

Runtime configurability is justified when an operator can respond to production conditions faster
than a deployment allows. It is not required for every value. When runtime changes are supported, the
software system MUST define:

1. **ownership** — which service or role owns the value;
2. **validation** — the accepted type, range and invariants, rejected before use;
3. **safe defaults** — behaviour when the value is absent, including whether startup fails closed;
4. **authorization** — who may change it and under which change control;
5. **auditability** — who changed what, when, and the previous value;
6. **versioning** — how a change is identified and rolled back;
7. **propagation** — how running consumers observe the change;
8. **caching and refresh** — refresh interval, push or poll, and staleness bounds;
9. **failure behaviour** — what happens when the configuration source is unavailable or invalid.

Changing a global configuration file does not automatically change a running application. The
mechanism that reads, validates, distributes and observes the change MUST be implemented and
verified. Until it is, the value is deployment configuration, not runtime configuration.

## 14.6 The composition boundary

A composition boundary is the place that resolves ambient configuration for the modules it
assembles. It:

- reads environment variables or the configuration platform;
- validates and converts the values;
- groups them into typed settings objects or immutable snapshots;
- passes them into module constructors or composition functions;
- owns the system-wide and shared-infrastructure namespaces in its scope.

A module implementation MUST NOT read `os.environ`, `process.env`, a global configuration object or a
service's own configuration store to obtain a value a caller could supply (`A005`). The test is
mechanical: delete the module; the remaining configuration must still make sense.

Shared infrastructure settings — log level, pool size, telemetry endpoint — belong to the composition
boundary's namespace, not to a module's. A module receives only the values it needs.

## 14.7 Architectural generality

| Context | Expression |
|---|---|
| **Modular monolith** | One or more composition boundaries resolve configuration and construct modules; shared constants have one owner. |
| **Microservices** | Each service owns its configuration namespace. A value is not centralized merely because two services currently use the same number. |
| **Libraries and frameworks** | The library exposes typed options and required parameters; stable public constants are code-owned. The consumer resolves configuration. A published optional parameter may be a compatibility feature, but it must be documented and must not conceal a required input (`D012`). |
| **Plugin architectures** | The host supplies a typed plugin settings object through the plugin contract. A plugin must not read the host's environment directly. |
| **Serverless** | Environment variables are resolved at the handler boundary and passed into the domain; the domain remains testable without the platform. |
| **Distributed systems** | Shared configuration requires an explicit propagation, consistency and failure model. Cross-service coupling is a design decision, not a side effect of a shared config table. |
| **Centralized configuration platforms** | The platform is a delivery mechanism, not an ownership model. It must preserve service ownership, validation and auditability. |
| **Generated code** | Generated values are classified and traceable to their generator; a generated literal is not automatically a reviewed constant. |

## 14.8 Examples

**1. A meaningful inline value used once.**

```python
def submit(order):
    return gateway.send(order, 3)  # ❌ the receiving parameter is a retry policy
```

The occurrence count is one. That does not make the value incidental.

**2. A named immutable declaration.**

```python
from typing import Final

MAX_ORDER_ATTEMPTS: Final = 3

def submit(order):
    return gateway.send(order, MAX_ORDER_ATTEMPTS)
```

**3. Equal values, different meaning.**

```csharp
private const int MaximumOrderAttempts = 3;
private const int MaximumPaymentAttempts = 3;
```

These MUST remain separate until an owner establishes that they represent one policy.

**4. Same name, different units.**

```python
REQUEST_TIMEOUT_SECONDS = 30
REQUEST_TIMEOUT_MILLISECONDS = 30000
```

The identifiers and units are evidence of different meanings. Do not merge them into `TIMEOUT = 30`.

**5. A genuine duplicate candidate.**

```python
# orders/policy.py
MAX_RETRY_ATTEMPTS = 3

# orders/submission.py
MAX_RETRY_ATTEMPTS = 3
```

The names and values match, but the candidate still needs a human to confirm that both files share
one policy. If they do, declare it once in the owning module boundary and pass it explicitly.

**6. Deployment-specific configuration.**

```ts
// composition boundary only
const catalogUrl = requiredUrl(process.env.CATALOG_URL);
const catalog = new CatalogModule({ endpoint: catalogUrl });
```

The endpoint is not a stable source constant merely because it has a name.

**7. A runtime-adjustable setting.**

```ts
interface RuntimeSettings {
  readonly retryLimit: number;
}

// The settings source validates, audits and publishes a new immutable snapshot.
// Consumers hold the snapshot and observe a new one; they never read the environment.
```

**8. A secret-looking literal.**

```python
DB_PASSWORD = "..."  # ❌ never a normal constant or committed configuration value
```

Resolve it through the secret mechanism; do not rename it and keep the value.

**9. A structural value that remains local.**

```python
for index, line in enumerate(order.lines):
    total += line.amount * line.quantity
```

`index` and the multiplication are structural. Extracting them would add names without meaning.

## 14.9 Enforcement and review

| Requirement | Rule | Mechanism |
|---|---|---|
| Ambient configuration is not read by a component | `A005` | automated in Python, TypeScript, Go and .NET; Java reports it not executed |
| Meaningful inline values, mutable declarations and same-module duplicates are candidates | `A006` | automated candidate detection in Python, TypeScript and .NET; review required |
| Configuration, runtime and secret classification is deliberate | `A006`, §14.4 | candidate detection for configuration/secret-looking names; review required |
| A module does not read another module's key | `A002` | manual review |
| Runtime changes have a propagation and failure contract | §14.5 | review evidence |
| Shared values across services have an owner | §14.7 | review evidence |

`A005` detects direct access to the process environment, the process argument list (`os.Args`) and
the Go `flag` package in declared `implementation` and `adapter` units. A `host` unit is excluded
because it is a declared composition boundary, and `tooling` units are excluded because they are
operator surfaces rather than the product graph. The finding is a confirmed access; whether the
value belongs to that component is still an architectural judgement.

`A006` detects:

- meaningful-looking inline literals passed to a locally known parameter;
- meaningful values assigned to mutable bindings, writable fields or mutable object properties;
- immutable declarations that appear to duplicate another declaration in the same module;
- configuration-looking values that may belong at a deployment or runtime boundary;
- secret-looking values that must not remain in source or ordinary configuration.

Every A006 finding is a **candidate**, not a confirmed semantic violation. The deterministic scan can
establish a syntactic pattern; it does not decide whether two values share a semantic identity. It
cannot prove that two identifiers mean the same thing, know their units, choose their highest common
owner, or decide whether a value should be a constant,
deployment configuration, runtime configuration or secret. The JSON finding carries
`"classification": "candidate"` when the enforcer emits it.

The duplicate check groups immutable declarations only within the same declared module. It does not
merge across modules or independently deployed systems. Equal values with different names are not
grouped, and a name match alone is not enough to merge different values. Two declarations with the
same name in different modules are not automatically the same value, and matching name and value
still produce only a review candidate. When equivalence is uncertain, preserve the separate
declarations and record the evidence for human review.

`A006` does not rewrite source and does not perform automatic refactoring. Go and Java report
`executed: false` in this revision; a repository using those profiles records manual or AI-assisted
review evidence with source citations. The .NET enforcer executes `A006` as a candidate detector over
meaningful declarations, source-declared call arguments, duplicate immutable values and
configuration/secret-looking literals. A clean A006 scan does not prove semantic consolidation or
the correctness of a configuration category.

## 14.10 Checklist

- [ ] Every meaningful timeout, retry, limit, rate, batch, retention, threshold or capacity value has
      one name and one owner (`A006`).
- [ ] The declaration is immutable where the language supports it, or has a documented reason for
      remaining mutable (`A006`).
- [ ] Important declarations are visible in their owning file or type without searching through
      implementation details.
- [ ] A value used once is still reviewed for meaning; loop indices and structural literals remain
      local.
- [ ] Equal literals have not been consolidated when their receiving identifiers, units, domain
      meanings or owners differ.
- [ ] Apparent duplicates are review candidates until semantic identity and the highest appropriate
      common owner are established.
- [ ] Shared values are passed explicitly; no ambient global, singleton lookup or hidden config read
      replaced the duplicate (`A005`, `A002`).
- [ ] Components receive configuration values; they do not read the environment or a global config
      object (`A005`, `A002`).
- [ ] Each value is classified as local, named constant, system constant, shared config, runtime
      config, deployment config or secret.
- [ ] Constants that are stable within a version remain code-owned rather than becoming runtime
      settings.
- [ ] Secrets are resolved through the secret mechanism and never committed or logged.
- [ ] Runtime-adjustable values have validation, audit, propagation, refresh, rollback and failure
      behaviour (§14.5).
- [ ] Cross-service values have a service owner or an explicit inter-service contract; they are not
      centralized by coincidence.
- [ ] Retained defaults and framework-required optional parameters are documented and narrow
      (`D012`, §14.3.6).
