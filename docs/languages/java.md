# Java profile

> **Implementation status.** This profile is normative for Java, but the reference
> implementation and enforcer are **not included** in this revision. The commands and file
> layout below describe the intended shape and the enforcer contract, not a tested artifact.
> `conformance/run.py` skips this profile explicitly.

Java 21 · one module · packages per unit · `javac` + a JDK-only runner.

> **Compatibility example.** The tree below is the legacy shape with a shared kernel. Under the
default, contracts reference nothing; see [section 6](#6-service-topology-profile).

## 1. Layout

```
src/main/java/acima/
  sharedkernel/Money.java              shared-kernel
  catalog/contracts/ProductView.java   contracts   (records)
  catalog/contracts/CatalogReader.java contracts
  catalog/internal/*.java              implementation
  orders/contracts/*.java              contracts
  orders/internal/*.java               implementation  → catalog.contracts
  payments/contracts/*.java            contracts
  payments/internal/*.java             implementation
  host/Main.java                       host
tools/acima/ArchTests.java             tooling (single file, JDK only)
violations/                            fixtures (not compiled)
```

## 2. What the toolchain enforces without help

| Obligation | Mechanism |
|---|---|
| Implementation private | JPMS `module-info.java` exporting only `acima.catalog.contracts`; otherwise package-private classes + ArchUnit |
| Contracts immutable | `record` (Java 16+) — final fields, canonical constructor, value equality |
| Collections immutable | `List.copyOf(...)` in the compact canonical constructor |
| No cycles | `javac` refuses cyclic *package* dependencies only if you break the build — in practice ArchUnit |
| Zero-dependency contracts | `jdeps` on the contracts classes |

```java
// src/main/java/module-info.java
module acima {
    exports acima.catalog.contracts;
    exports acima.orders.contracts;
    exports acima.payments.contracts;
    exports acima.sharedkernel;
    // acima.catalog.internal is deliberately not exported
}
```

JPMS is the only compiler-level boundary Java offers, and it costs a `module-info.java` and a
`--module-path` build. Without it, the architecture test is the boundary — the same situation as Python,
with better static analysis available.

## 3. Architecture tests

**Idiomatic:** [ArchUnit](https://www.archunit.org/) — the origin of this whole idea.

```java
@AnalyzeClasses(packages = "acima")
class AcimaArchitectureTest {

    @ArchTest static final ArchRule contracts_are_leaves =
        noClasses().that().resideInAPackage("..contracts..")
            .should().dependOnClassesThat().resideInAnyPackage("..internal..", "..host..");

    @ArchTest static final ArchRule orders_does_not_reach_into_catalog =
        noClasses().that().resideInAPackage("acima.orders..")
            .should().dependOnClassesThat().resideInAPackage("acima.catalog.internal..");

    @ArchTest static final ArchRule contracts_are_immutable =
        classes().that().resideInAPackage("..contracts..")
            .should().beRecords();
}
```

**Reference enforcer (this repository):** `tools/acima/ArchTests.java`, a single file run with
`java tools/acima/ArchTests.java --root . --format json`. It scans `.java` sources and `import`
statements, so it runs with no build tool, no dependencies and no `mvn`/`gradle` download — which is
what makes it usable in this repository's conformance harness.

```bash
javac -d build $(find src -name '*.java')
java tools/acima/ArchTests.java --root . --format json
```

## 4. Analyzers and linters

| Tool | Catches | Notes |
|---|---|---|
| **ArchUnit** | `D*`, `L001`, `L003` | the strongest option; also checks layer definitions |
| **Error Prone** | `C001` (mutable fields), `C005`, `C006` | runs in `javac`, IDE integration |
| `Checkstyle` / `PMD` | naming, final fields, visibility | `FinalLocalVariable`, `VisibilityModifier` |
| `jdeps` | `D004` — the actual dependency set of the contracts classes | no plugin needed |
| **`module-info` + `jlink`** | `D001`, `D009` | the only hard boundary |

```bash
# D004, without a custom tool
jdeps --multi-release 21 -summary build/acima/catalog/contracts/*.class | grep -v 'java.base'
```

## 5. Idioms and pitfalls

| Trap | Rule | Fix |
|---|---|---|
| A `class` with getters/setters in contracts | `C001` | `record` |
| `record` with a `List<T>` component | `C002` | compact canonical constructor with `List.copyOf(lines)` |
| `Object payload` / `JsonNode` | `C006` | a sealed interface per event family |
| A `record` with business methods | `C003` | move behaviour to the implementation |
| `Instant.now()` in a record constructor | `C004` | pass `Instant` in |
| `@Entity` in a contract | `C005` | map to a record |
| Using `acima.catalog.internal` from `orders` | `D001` | import `acima.catalog.contracts` |
| `public` classes in `internal` packages | `L003` | package-private |

### One Java-specific note

Java 21 records give you `C001`, part of `C002` and value equality for free — by far the cheapest route
to L2 in any of the five languages. The remaining work is the collection copy in the compact constructor
and keeping behaviour out of the record body.

### Explicit inputs (`D011`, `D012`)

Java has no default parameters, but overloads and nullable constructor arguments reproduce the defect:
`new OrdersModule(catalog)` and `new OrdersModule(catalog, payments)` are two construction paths, and a
`null` payment service that triggers a fallback is a hidden dependency. Keep one constructor requiring
every collaborator, or make the shorter overload delegate with an explicit no-op implementation. This
profile has no enforcer in this revision, so `D011`/`D012` are manual-review requirements here
(chapter 13, chapter 8 §8.9).

### Values and configuration (`A005`, `A006`)

Java has no optional parameters, but a constructor overload or a `System.getenv` call can reproduce
the same hidden configuration. Require a typed `OrdersSettings` record in the constructor; the host
reads the environment and validates it. This profile has no enforcer in this revision, so `A005` and
`A006` are manual-review requirements here (chapter 14, chapter 8 §8.9).

### Composition and injection (`D013`, `D014`)

A Spring `@Configuration` class or an explicit `Main` factory is the composition boundary; constructor
injection is the default. Classpath scanning that selects application components, field injection
(`@Autowired` on a field) and `ApplicationContext.getBean` inside domain/application code are review
blockers (`D013`, `D014`, `L004`). Framework-managed controllers are fine when their application
dependencies are constructor parameters and the host declares the beans. This profile has no enforcer
in this revision; record manual evidence (chapter 15, chapter 8 §8.9).

### Functional capture (`D015`, `D016`)

A lambda or anonymous class must not capture an application service from an enclosing field or
local when it could be a parameter; constructor-injected fields are visible. Partial application is
not a Java idiom, but a returned function that closes over a service is the same `D015` defect.
This profile has no enforcer; record manual evidence (chapter 16, chapter 8 §8.9).

### Lifecycle and state ownership (`A007`–`A009`)

Spring and similar containers distinguish singleton, prototype and request scopes. A singleton bean
that depends on a request-scoped bean needs a scoped proxy or an explicit provider; a mutable field
in a singleton is shared across requests; static mutable state is process-wide. Decide lifetime from
the state boundary, not from the default scope annotation. This profile has no enforcer and reports
`A007`–`A009` as manual-review requirements: record the owner, isolation key, synchronization and
cleanup policy, and do not treat a `@Singleton` annotation as evidence of thread safety
(chapter 17, chapter 8 §8.9).

### Intent-revealing naming (`N001`–`N003`)

Classes, interfaces, enums and records use `PascalCase`; methods, fields and parameters use
`camelCase`; constants use `UPPER_SNAKE_CASE`; packages are lower-case and domain-oriented. Boolean
accessors use `is`/`has`/`can` where the framework permits. Name the responsibility, not a generic
`Manager` or `Helper`. This profile has no enforcer: record manual evidence for type casing,
generic responsibilities, side effects, units, boolean polarity and domain consistency
(chapter 18, chapter 8 §8.9).

## 6. Service topology profile

Chapter 11's naming maps to Gradle subprojects and JPMS module names:

```
services/orders/
  orders-api/                          acme.orders.api
  orders-api-contracts/                acme.orders.api.contracts
  orders-application/                  acme.orders.application
  orders-application-contracts/        acme.orders.application.contracts
  orders-domain/                       acme.orders.domain
  orders-infrastructure/               acme.orders.infrastructure
  orders-integrations-stripe/          acme.orders.integrations.stripe
  orders-integrations-stripe-contracts/
  orders-catalog/                      messages orders -> catalog
  orders-host/                         composition root
```

### A contracts module with no requires

```java
// orders-application-contracts/src/main/java/module-info.java
module acme.orders.application.contracts {
    exports acme.orders.application.contracts;
}
```

```java
// OrderLine.java
package acme.orders.application.contracts;

public record OrderLine(String productId, String amount, String currency, int quantity) {}

// PlaceOrder.java
package acme.orders.application.contracts;

import java.util.List;

public record PlaceOrder(String customerId, List<OrderLine> lines) {
    public PlaceOrder {
        lines = List.copyOf(lines);
    }
}

// PlaceOrderResult.java
package acme.orders.application.contracts;

public record PlaceOrderResult(boolean accepted, String orderId, String rejection) {}

// PlaceOrderHandler.java
package acme.orders.application.contracts;

public interface PlaceOrderHandler {
    PlaceOrderResult handle(PlaceOrder command);
}
```

No `requires` clause beyond the implicit `java.base`; no Jackson, no Jakarta Validation, no Lombok,
no shared kernel module. `Money` is a record declared in this module or a primitive pair. Compact
constructors may validate; they must not call `Instant.now()` or a UUID generator (C004).

### Layer references

| Module | Requires | Never requires |
|---|---|---|
| `acme.orders.api` | `acme.orders.api.contracts`, `acme.orders.application.contracts` | `acme.orders.application`, `acme.orders.domain` |
| `acme.orders.application` | `acme.orders.application.contracts`, `acme.orders.domain`, `acme.orders.integrations.stripe.contracts` | `acme.orders.api`, `acme.orders.infrastructure` |
| `acme.orders.domain` | `java.base` only | any contracts module, any third-party module |
| `acme.orders.infrastructure` | `acme.orders.domain`, JDBC/driver modules | `acme.orders.api` |
| `acme.orders.integrations.stripe` | `acme.orders.integrations.stripe.contracts`, Stripe SDK module | `acme.orders.domain` |
| `acme.orders.host` | everything | — |

JPMS makes the layer table a compile-time requirement, not a review convention. If the build still
uses the classpath, ArchUnit enforces the same table.

### Third-party isolation

`acme.orders.integrations.stripe.contracts` exports the gateway interface and its records and requires
nothing. `acme.orders.integrations.stripe` requires that module plus the Stripe SDK, implements the
gateway and translates vendor exceptions. A Stripe type in the domain module is an ST-8 failure.

### Domain tests

```bash
./gradlew :services:orders:orders-domain:test \
  :services:orders:orders-domain:jacocoTestCoverageVerification
```

Configure JaCoCo on the domain subproject with a 100% line and branch minimum. JUnit 5 test names
state the rule (`placeOrder_rejectsMoreThanAvailableStock`); the domain test module requires no
container, database or vendor SDK.

### What the toolchain checks without help

`module-info.java` refuses an undeclared `requires`; `jdeps --module-path` prints the real graph;
ArchUnit `layeredArchitecture()` encodes the layer table for the classpath build; JaCoCo provides the
ST-10 evidence.
