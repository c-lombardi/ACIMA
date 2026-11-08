# Java profile

> **Implementation status.** This profile is normative for Java, but the reference
> implementation and enforcer are **not included** in this revision. The commands and file
> layout below describe the intended shape and the enforcer contract, not a tested artifact.
> `conformance/run.py` skips this profile explicitly.

Java 21 · one module · packages per unit · `javac` + a JDK-only runner.

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
