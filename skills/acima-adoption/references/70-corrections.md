# Corrections

Every finding already names its remedy. The authoritative text is the **Fix** section of the rule's
page in `docs/rules/`; this file adds what that text does not: which remedy to choose when several
are legal, the trap that turns one finding into another, and how to prove the correction worked.

## Before editing: read the rule's Fix section

| Finding prefix | Authoritative page |
|---|---|
| `D`, `L` | [`docs/rules/dependency.md`](../vendor/docs/rules/dependency.md) |
| `C` | [`docs/rules/contracts.md`](../vendor/docs/rules/contracts.md) |
| `A`, `G` | [`docs/rules/autonomy.md`](../vendor/docs/rules/autonomy.md) |
| `N` | [`docs/rules/naming.md`](../vendor/docs/rules/naming.md) |

Each entry has Statement, Violation, Finding, Why, **Fix**, Detection. Read the Fix and Detection
together: the Detection section says what the enforcer can and cannot see, which tells you whether a
green run will actually confirm the change. For the language idiom, use
[`docs/languages/`](../vendor/docs/languages/index.md).

If the Fix text conflicts with what the target's owners consider correct, stop and say so. That is
the "the rule may be wrong" stop condition, not a licence to invent a remedy.

## The four correction shapes

Every remedy is one of these. Pick the smallest one that stops the rule firing.

| Shape | Move | Rules |
|---|---|---|
| **Invert** | introduce or consume a port so the arrow points at contracts | `D001`, `D002`, `L001`, `L003`, `A004` |
| **Localise** | duplicate the shape, or carry identity instead of the model | `D003`, `D004`, `C005`, `C006` |
| **Remove** | delete the reference or the state; nothing replaces it | `D006`, `D009`, `A003` |
| **Restructure** | process manager, event, or merge — only when the graph itself is wrong | `D005`, `D007`, `D008` |

Restructuring is last because it moves code between owners and needs their agreement. Inverting is
usually first because it adds a seam instead of moving a boundary.

## Naming findings (`N`)

- **`N001` type casing** — rename the type in its own language convention, then update every reference
  in the same change. The enforcer checks declarations, not the semantic quality of the name. Do not
  rename external contracts or generated declarations; record an owned exception instead.
- **`N002` generic responsibility** — split the type by what it actually does (`OrderValidator`,
  `OrderCalculator`) or rename it when one responsibility is already clear. A generic name that is
  precise inside a narrow abstraction is not automatically a defect; record why it is meaningful.
- **`N003` semantic clarity** — this is a review finding, never scanner output. Establish the domain
  term, make side effects explicit (`Find` vs `Create`, `Get` vs `GetOrCreate`), state units, and
  remove unexplained local abbreviations. Propose the smallest rename that removes the ambiguity and
  obtain consent before editing consumer code.

A rename changes the finding fingerprint, so move the baseline or waiver in the same pull request.
Never bulk-rename to reduce the count, and never treat a preferred synonym as a proven violation.

## Dependency findings (`D`)

| Rule | Move | Trap |
|---|---|---|
| `D001` impl → impl | Import the provider's contracts port. If the port lacks the operation, request an additive contract change from its owner — the import is the conversation, not the solution. | Reaching into the provider's repository "just for a read" keeps its store in your build. |
| `D002` contracts → impl | Define the contract shape on its own terms; map inside the implementation, which already knows both types. | Reusing an entity in the contract to avoid writing a mapper. |
| `D003` contracts → contracts | Local value, carry identity (`ProductId`, price, quantity), or duplicate the shape. | Moving the shared type to a "shared kernel" — legal only as a legacy allowance, never as a new contract. |
| `D004` contracts → third party | Constructor checks instead of validation attributes; serializer attributes on a transport type in the host, or a convention-based serializer. | Keeping the package "because the contract needs JSON" — the boundary's adapter owns serialization. |
| `D005` cycle | In order: a process manager that owns the workflow, an event replacing one direction, or a merge if both are one bounded context. | Breaking the cycle with a shared kernel — the cycle becomes `D007` next month. |
| `D006` contracts → host | Delete the reference. Composition happens in the host; the contract must not know it exists. | Passing `IServiceProvider` or a logger into a message. |
| `D007` shared kernel | Give the type an owner and move it there; consumers take a contracts reference to that owner. | Growing the kernel "temporarily" — it has no owner, so nothing ever removes it. |
| `D008` transitive leak | Remove the direct reference that makes the implementation transitive; check package and project references, not only imports. | Adding a direct reference to "make the type visible", which is `D001` again. |
| `D009` internals access | Publish a port in contracts; make the implementation type internal or unexported. | Widening visibility until the rule stops seeing it. |

## Layering findings (`L`)

- **`L001` domain → infrastructure** — define the port in the domain and implement the adapter in
  infrastructure; the domain then owns the interface it needs. The trap is moving the domain type into
  infrastructure, which inverts the dependency instead of fixing it.
- **`L002` contracts → framework type** — replace the framework type with your own; map at the
  boundary adapter.
- **`L003` implementation type published** — return the contract type and keep the implementation type
  internal. The trap is making the type public so consumers "can see it".
- **`L004` service locator** — constructor injection. This rule needs human evidence, so the fix is
  confirmed by review plus a run, not by the enforcer alone.

## Contract findings (`C`)

| Rule | Idiom by language |
|---|---|
| `C001` mutable state | C# `sealed record` with `init`; TS `readonly`; Python `@dataclass(frozen=True, slots=True)`; Go unexported fields + constructor; Java `record` |
| `C002` mutable collection | C# `IReadOnlyList<T>` from `ToArray()`; TS `readonly T[]` / `ReadonlyArray`; Python `tuple[T, ...]` / `MappingProxyType`; Go accessor returning a copy; Java `List.copyOf` in the canonical constructor |
| `C003` behaviour | keep at most a pure fold; move anything that branches on business conditions, does IO or is `async` into the module |
| `C004` ambient state | pass the clock and the identifier in from the module that creates the fact |
| `C005` persistence type leak | map to a contract type at the boundary; no ORM or driver types in contracts |
| `C006` untyped payload | a named type per message; `object`/`any`/`interface{}` is a contract nobody can version |
| `C007` one-step construction | a builder only when construction is genuinely staged; otherwise required members in the constructor |

- **`C008` business behaviour visibility** — name the operation, its business outcome, material
  preconditions, typed failures and observable effects. Replace a read-shaped mutator or an untyped
  `execute`/`handle` contract. The boundary exposes the outcome; the domain decision stays in the
  implementation. This is a contract review, not a source-scan finding.

`C003`, `C007`, `C008` and `C005`'s judgement parts are decided by review: record the decision, do not assume a
green run decided them.

## Autonomy findings (`A`)

- **`A001` shared table** — call the owner's port for reads; subscribe to its events for data you keep,
  into your own schema. Never "just read" another module's table, even read-only.
- **`A002` foreign config key** — move the key under your own namespace, supplied by the host; if the
  value belongs to the provider, ask through a port.
- **`A003` shared static state** — make it an instance owned by the module; the host constructs one and
  injects it if several modules need it.
- **`A004` version lock** — depend on `X.Contracts` with a range. Needing the implementation's version
  means `D001` is still present.
- **`A007` unnecessary transient** — first confirm the component has no mutable state and is safe for
  concurrent calls. Then share it at the longest appropriate lifetime. Do **not** promote it to a
  singleton merely to silence the finding if it owns state: fix `A009` first. A domain object,
  value object or per-operation object is not an application service and should not be registered.
- **`A008` captive scoped dependency** — choose the state boundary. If the consumer itself holds
  request/tenant state, make it scoped. If only one operation needs the value, pass it as a
  parameter. If the consumer genuinely needs to create shorter-lived work, inject an explicit
  factory and invoke it inside the scope. Never replace the constructor with a service locator
  (`L004`), and never make the dependency a singleton to satisfy the container.
- **`A009` shared mutable state** — name the owner and move the container into it, or scope the
  component to the state's boundary. If the shared container is intentional, record the isolation
  key, synchronization, initialization, eviction/expiration, failure behaviour and consistency
  expectation, and test concurrent access and cross-tenant isolation. A lock alone does not make an
  unbounded or tenant-mixed cache correct.
- **Lifecycle claims are review claims.** `A007`–`A009` do not prove thread safety, tenant isolation,
  resource cleanup or the runtime graph. For Go, .NET and Java they report `executed: false`; record
  manual evidence instead of treating the green scan as a pass.

## Effect findings (`A010`–`A013`)

These are manual rules. A review names the effect owner, the boundary and the applicable semantics;
no code edit is "the fix" until that decision is made.

| Rule | Move | Trap |
|---|---|---|
| `A010` effect boundary | move the transaction, write or vendor call into the module that owns the affected state; expose a command whose contract states the effect | calling a provider inside the caller's transaction and declaring it atomic because it compiled |
| `A011` effect semantics | state retryability, duplicate identity, consistency, partial completion and cancellation where they apply | adding an unused idempotency key or cancellation token so the checklist looks complete |
| `A012` outcome truthfulness | return typed succeeded/failed/unknown/partial outcomes; commit before reporting durable success; report post-commit notification failure as partial | catching a timeout and reporting that nothing happened when the remote side may have committed |
| `A013` critical-effect evidence | add the failure-path test, reconciliation, alert or runbook that matches the blast radius | treating a clean scan or a happy-path test as evidence |

A retry is not a recovery policy. An idempotency key is not a transaction. A transaction is not a
compensation. A cancellation token is not proof that cancellation works. Fix the underlying ownership
and then choose the mechanism the domain needs.

## Governance findings (`G`)

| Rule | Correction |
|---|---|
| `G001` undocumented exception | add the waiver entry: rule, path, owner, reason, scope, expiry, review date |
| `G002` expired waiver | fix the finding, or renew individually with a new reason and expiry — never in bulk |
| `G003` undocumented contract surface | document the added surface; the enforcer only checks that documentation exists |
| `G004` unreviewed contract change | record the reviewed API baseline and classify the change as additive or breaking |
| `G005` unclassified source | fix the unit paths, or add an exclusion with a reason; a repository that classifies nothing is a false pass |

## Correction discipline

1. **One boundary per pull request.** Several findings inside one boundary is fine; two boundaries is
   two pull requests.
2. **Re-run and compare.** The count must be flat or falling, and `NEW` must be zero. A fix that lowers
   one rule and raises another is not a fix.
3. **Fingerprints move with files.** A rename changes the fingerprint, so update the baseline or waiver
   in the same pull request. Otherwise a corrected finding returns as `NEW`.
4. **Never pass by weakening.** No widened exclusion, no deleted assertion, no waiver without an owner
   and expiry, no rule edit — those are `G001` in spirit and a standards change, not an adoption task.
5. **Record the mapping.** The pull request body says which finding, which rule page, which shape
   (invert / localise / remove / restructure), and which run proves it. That is the audit trail a
   reviewer needs and the reason the next agent can continue.

## When not to "fix" it

Sometimes the honest answer is not a code change:

- the two modules are one bounded context → merge, and say so;
- the design is deliberately outside the rule's intent → propose a standard amendment, not a permanent
  waiver;
- the enforcer is wrong or blind → fix the enforcer or disclose the gap; never report clean.

## Reviewing an effect boundary

Use this sequence for `C008` and `A010`–`A014`. It is a review, not a source scan:

1. **Enumerate effects.** Use the contract, handlers, adapters and tests. Distinguish an external
   effect from ordinary local mutation; aggregate mutation is not a defect.
2. **Name the owner and boundary.** The owner is the module or declared adapter/host policy that can
   decide failure and duplicate behaviour. If two owners are plausible, say so; do not invent one.
3. **Check applicability.** Decide whether retry, duplicate handling, a consistency guarantee,
   cancellation and evidence apply. "Not applicable" is a valid, reviewable answer; it is not a
   pass by omission.
4. **Trace the outcome path.** Follow success, failure, unknown and partial completion. A caller must
   not mistake acceptance for durability, or a post-commit exception for no effect.
5. **Check the evidence.** A success-only test is not evidence for a critical effect. Name the missing
   failure-path test, reconciliation or operational signal.
6. **Report uncertainty.** Confirmed, suspected and insufficient evidence are different results.

A retry does not imply idempotency; idempotency does not imply atomicity; a transaction does not
cover a distributed workflow; cancellation does not undo a committed side effect. A clean scan of
these rules, a retry library or a transaction API proves nothing.
