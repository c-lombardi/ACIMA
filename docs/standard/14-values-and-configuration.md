# 14. Values, constants and configuration

> **Meaningful values must have an identifiable owner, name, purpose and source. Their scope and
> configurability must be deliberate.**

This chapter is normative. It applies to every repository in base mode, at every conformance level
where the `A` rules are required (L3). It does not require every literal to become a constant, and it
does not require every configuration value to become dynamically adjustable.

## 14.1 The obligation

A meaningful value MUST have an intentional classification and an identifiable owner. A developer
must be able to answer, from the source and its composition:

- what the value represents;
- why it exists;
- which component owns it;
- where it is defined;
- where it is consumed;
- whether it can be changed;
- whether changing it requires a deployment.

The seven classifications are:

| # | Classification | Typical form | Owner |
|---|---|---|---|
| 1 | Local implementation literal | a value whose meaning is obvious at the expression | the containing function or type |
| 2 | Named constant | a name in the component that owns the value | that component |
| 3 | Application-level constant | a named value shared by units of one application | the composition boundary |
| 4 | Shared configuration | configuration consumed by several units with the same meaning | the application or service that owns the concept |
| 5 | Runtime-adjustable configuration | a value an operator may change without a deployment | the operating service, with an explicit refresh contract |
| 6 | Deployment or environment configuration | a value that differs between development, staging and production | the deployment environment |
| 7 | Secret | a credential or other sensitive value | the secret store, resolved at the boundary |

The classifications are not interchangeable. A deployment setting is not a business policy, a secret
is not an ordinary configuration file entry, and a fixed constant is not a runtime knob.

**Related rules.** `A005` covers ambient configuration access; `A006` covers operational literals
without a declared owner; `A002` covers cross-module configuration keys; `P4.7` and `P4.8` state the
principle. The language profiles document where enforcement is automatic and where it is manual.

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

Occurrence count is not a criterion. A value used once may be important policy; a literal repeated
ten times may be incidental formatting. `A006` therefore reports named operational positions, not
every numeric or string literal.

## 14.3 Ownership and declaration

### Local constants

A meaningful value that belongs exclusively to one component MAY be a named constant in that
component. It MUST have a name that states its purpose; `LIMIT = 3` in a payment module is weaker than
`MAX_PAYMENT_ATTEMPTS = 3`.

### Application-level constants

When several units of one application share the same concept, the value MUST have one owner at an
identifiable application boundary. It MUST NOT be copied into unrelated modules. Sharing the text
`30` is not sharing a concept: two modules using `30` may implement different policies.

### Shared values across entry points and services

Multiple handlers, jobs, controllers or services may use a value with the same meaning. Evaluate
whether the definition should be shared, but do not centralize by coincidence:

- identical values may have different meanings;
- different current values may implement the same policy at different stages;
- a value owned by one service is not automatically a platform-wide setting.

The semantic meaning and the owner decide. A value shared by independently deployed services should
be owned by the service that owns the concept, or be part of an explicit inter-service contract — not
silently read from a central table.

### Explicit injection

Meaningful application-level values MUST be supplied to their consumers at the composition boundary.
Where several related values exist, group them into a typed settings object or value object rather
than injecting unrelated primitives. The declaration and registration of that object MUST be visible
in the composition root, not discovered by the component at runtime.

## 14.4 Configuration categories

A **configuration category** is the declared nature and change model of a value. It determines who
owns the value, whether it may change without a deployment, and what validation and audit it needs.

**Deployment configuration** differs by environment: endpoints, database hosts, region names,
feature-environment switches. It is resolved once at startup and passed in.

**Operational configuration** may be adjusted by an operator without deploying a new version:
timeouts, retry limits, batch sizes, rate limits, retention periods. It requires the runtime contract
in §14.5.

**Business or domain policy** represents a rule the business owns: maximum order value, refund
window, eligibility thresholds. It needs a named owner, review and an explicit change process; making
it a mutable operator setting may be inappropriate.

**Secrets** are credentials, signing keys and tokens. They MUST be resolved through the environment's
secret mechanism and MUST NOT be committed, logged, placed in ordinary configuration files, or read
by a module that does not own them (`A002`).

**Fixed application constants** should remain fixed within a version: protocol version numbers,
algorithm identifiers, invariants. They are named and versioned with the code, not exposed as runtime
settings merely because a configuration system exists.

A value that changes category needs an explicit decision. Moving a business policy into runtime
configuration changes who can change the behaviour without a review.

## 14.5 Runtime configuration contract

Runtime configurability is justified when an operator can respond to production conditions faster
than a deployment allows. It is not required for every value. When runtime changes are supported, the
application MUST define:

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

The composition root is the only place that resolves ambient configuration. It:

- reads environment variables or the configuration platform;
- validates and converts the values;
- groups them into typed settings objects;
- passes them into module constructors or composition functions;
- owns the application-wide and shared-infrastructure namespaces.

A module implementation MUST NOT read `os.environ`, `process.env`, a global configuration object or a
service's own configuration store to obtain a value a caller could supply (`A005`). The test is
mechanical: delete the module; the remaining configuration must still make sense.

Shared infrastructure settings — log level, pool size, telemetry endpoint — belong to the host's
namespace, not to a module's. A module receives only the values it needs.

## 14.7 Architectural generality

| Context | Expression |
|---|---|
| **Modular monolith** | One composition root resolves configuration and constructs every module; application constants have one owner. |
| **Microservices** | Each service owns its configuration namespace. A value is not centralized merely because two services currently use the same number. |
| **Libraries and frameworks** | The library exposes typed options and required parameters; the consuming application resolves configuration. A published optional parameter may be a compatibility feature, but it must be documented and must not conceal a required input (`D012`). |
| **Plugin architectures** | The host supplies a typed plugin settings object through the plugin contract. A plugin must not read the host's environment directly. |
| **Serverless** | Environment variables are resolved per invocation at the handler boundary and passed into the domain; the domain remains testable without the platform. |
| **Distributed systems** | Shared configuration requires an explicit propagation, consistency and failure model. Cross-service coupling is a design decision, not a side effect of a shared config table. |
| **Centralized configuration platforms** | The platform is a delivery mechanism, not an ownership model. It must preserve service ownership, validation and auditability. |
| **Generated code** | Generated values are classified and traceable to their generator; a generated literal is not automatically a reviewed constant. |

## 14.8 Examples

**1. Unexplained inline business threshold.**

```python
if order.total > 500:
    require_manual_review(order)
```

**2. The same value promoted to a named constant.**

```python
MANUAL_REVIEW_THRESHOLD = Money.of("500.00", "USD")

if order.total > MANUAL_REVIEW_THRESHOLD:
    require_manual_review(order)
```

**3. An application constant, injected at the composition boundary.**

```python
# host
orders = OrdersModule(settings=OrdersSettings(manual_review_threshold=...))
```

**4. A shared value moved to shared configuration.**

```json
{ "orders": { "review": { "threshold": "500.00" } } }
```

The host reads `orders.review.threshold`, validates it as money, and passes it into `OrdersModule`.
No implementation reads the key directly.

**5. A deployment-specific setting.**

```ts
// host only
const catalogUrl = requiredUrl(process.env.CATALOG_URL);
const catalog = new CatalogModule({ endpoint: catalogUrl });
```

**6. An operational setting updated at runtime.**

```ts
interface RuntimeSettings {
  readonly retryLimit: number;
}

// The settings source validates, audits and publishes a new immutable snapshot.
// Consumers hold the snapshot and observe a new one; they never read the environment.
```

**7. A value that should remain a local implementation detail.**

```python
for index, line in enumerate(order.lines):
    total += line.amount * line.quantity
```

`index` and the multiplication are structural; extracting them would add names without meaning.

**8. Two identical literals with different meanings.**

```python
MAX_ORDER_ATTEMPTS = 3          # orders: retry a failed submission
MAX_PAYMENT_ATTEMPTS = 3        # payments: retry a declined charge
```

The values match today. They are different policies with different owners and may diverge. They must
not be centralized merely because the text is equal.

## 14.9 Enforcement and review

| Requirement | Rule | Mechanism |
|---|---|---|
| Ambient configuration is not read by a component | `A005` | automated in Python and TypeScript; other profiles report it not executed |
| Operational literals have a named owner | `A006` | automated candidate detection in Python and TypeScript; a warning requires review |
| A module does not read another module's key | `A002` | manual review |
| Deployment, operational, policy and secret categories are deliberate | §14.4 | review evidence |
| Runtime changes have a propagation and failure contract | §14.5 | review evidence |
| Shared values across services have an owner | §14.7 | review evidence |

`A005` detects direct access to the process environment in declared `implementation` and `adapter`
units. The host is excluded because it is the composition boundary. The finding is a confirmed
access; whether the value belongs to that component is still an architectural judgement.

`A006` detects literals bound to operational names: timeouts, retries, limits, thresholds, TTLs,
intervals, batch sizes, rates, retention periods, capacities, delays, quotas, concurrency, attempts,
workers, and integration names such as endpoint, URL, host, port, queue, topic and bucket. It skips
all-uppercase named constants because those are already named owners. It does not decide whether two
literals mean the same thing, whether a value is deployment- or runtime-configurable, or whether an
extraction improves readability. Those are review decisions.

Static analysis MUST NOT claim that two equal literals have the same meaning. A finding is a
candidate: confirm the value is meaningful, name its owner, and choose one of the classifications in
§14.1. If the literal is incidental, record why the local form is correct; do not centralize it to
silence the rule.

When a language or framework requires an optional value, the exception is narrow and documented.
Contract optional members remain governed by `C007` and the additive-evolution rules. Public library
APIs may retain optional parameters for compatibility, but a required application input must not be
concealed by them (`D012`).

## 14.10 Checklist

- [ ] Every operational timeout, retry, limit, rate, batch, retention or capacity value has a name
      and an owner (`A006`).
- [ ] Components receive configuration values; they do not read the environment or a global config
      object (`A005`, `A002`).
- [ ] Application-wide values have one owner at the composition boundary; identical text is not
      treated as identical meaning.
- [ ] Each value is classified as local, named constant, application constant, shared config,
      runtime config, deployment config or secret (§14.1).
- [ ] Secrets are resolved through the secret mechanism and never committed or logged.
- [ ] Runtime-adjustable values have validation, audit, propagation, refresh, rollback and failure
      behaviour (§14.5).
- [ ] Cross-service values have a service owner or an explicit inter-service contract; they are not
      centralized by coincidence.
- [ ] Retained defaults and framework-required optional parameters are documented and narrow
      (`D012`, §14.7).
