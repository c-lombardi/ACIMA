# Owned effects, retries and transactions

Most architectural rules describe where code lives. This guide is about what code **does** outside
its own memory — and who is accountable when that goes wrong.

ACIMA does not require every operation to be transactional, retryable, idempotent or cancellable.
It requires the decisions that apply to an effect to be owned and visible. The governing principle
is [P15 Owned Effects](../standard/01-principles.md#p15-owned-effects).

## The one question

> **Who owns this effect, where does its execution boundary end, and what does the caller learn when
> it succeeds, fails, is duplicated or stops partway?**

If the answer is a named component and a stated guarantee, the design is reviewable. If the answer
is "the framework handles it", the framework may still be the mechanism — but a person must be able
to name the policy it implements.

## What counts as an effect

| Effect | Example | Usually owned by |
|---|---|---|
| Persistent write | placing an order, updating stock | the module that owns the table |
| Message publication | publishing `OrderPlaced` | the module that owns the fact, through its outbox |
| Money movement | authorising or capturing a payment | Payments, or a declared payment adapter acting for it |
| Communication | sending an email or notification | the owning module's adapter, with a delivery policy |
| Required audit record | recording who approved a refund | the module that owns the decision |
| Cache invalidation | evicting a product projection | the component that owns the cache |

Ordinary mutation of an aggregate is **not** an external effect. A mutable `Order` inside Orders is
normal domain design. The effect is the repository write, the event publication or the payment call
that leaves the boundary.

## The ownership test

A caller performs a provider's effect when it:

- opens a transaction around another module's data;
- writes another module's table or reads it directly;
- publishes another module's event;
- retries another module's non-idempotent command because the transport failed;
- catches a post-commit error and reports that nothing happened.

The correction is not a new framework. It is to move the effect behind the owner's contract and let
the owner state the outcome and recovery semantics.

```python
# Wrong: the host owns both effects and calls the pair "atomic".
with db.transaction():
    orders_repo.save(order)
    payments.charge(order.total)

# Right: each module owns its effect; the workflow is explicit.
orders.place(command)             # Orders owns its state and outbox write
payments.capture(order.payment)   # Payments owns its idempotent capture
```

The second version is not automatically atomic. It is **honest**: the two commits are separate, and
the workflow needs an owner for the partial state between them.

## Conditional applicability

Use this matrix during review. "Not applicable" is a valid decision, but it must be recorded.

| Question | Applies when | Does not apply when |
|---|---|---|
| Retry policy | the operation can fail transiently and retrying is part of its execution contract | there is no retry behaviour |
| Idempotency | duplicate execution is possible and could repeat or corrupt the effect | the operation is a read, naturally idempotent, or cannot be duplicated |
| Transaction | several writes must share a consistency guarantee | each write is independent, or the guarantee is recovery/reconciliation instead |
| Atomicity | the domain requires all-or-nothing for a step | an intermediate state is legitimate and recoverable |
| Cancellation | the environment supports it and the operation is long-running or externally cancellable | the operation is short, non-cancellable or already irreversibly committed |
| Critical-effect evidence | failure can lose money, duplicate a commitment, corrupt data or lose a required record | the effect is low-impact and a retry or rebuild is enough |

A payment command needs duplicate and unknown-outcome semantics. A product lookup does not. A
nightly cache rebuild may need reconciliation but not an idempotency key. Do not flatten these into
one checklist.

## Retry and duplicate execution

Where retries exist, name the retry owner. The owner decides which failures are retryable, the
attempt limit, backoff, timeout and the exhausted-budget outcome. A retry library is a mechanism,
not the owner.

Where a retry could repeat an effect, define duplicate behaviour:

- derive the duplicate identity from the business operation, not only a transport message id;
- store the dedup record in the owner's persistence boundary;
- make concurrent duplicates contend on one record;
- return the original outcome, or no additional effect, on a duplicate;
- state the retention period;
- distinguish "newly applied" from "already applied" when the caller needs to know.

ACIMA does not claim exactly-once delivery. The obligation is explicit, owned duplicate behaviour.

## Transactions and recovery

One module owns a transaction around its own state and outbox writes. The host does not open a
transaction across modules. Cross-module workflows use an outbox, a saga or reconciliation with an
explicit intermediate state.

For a multi-step operation, choose one guarantee and say so:

- **atomic** — the state and its required outbox or audit record commit together;
- **recoverable** — the intermediate state is durable and can be resumed;
- **compensating** — the committed step has an owned compensation;
- **reconciled** — the system compares with the source of truth and repairs drift.

Partial completion must be observable, and someone must own the resume, compensation or
reconciliation. A retry is not a recovery strategy.

## Truthful outcomes

An effect owner must not lie about what happened:

- success only after the effect is durable or accepted;
- failure when the effect definitely did not happen;
- **unknown** when the remote side may have committed;
- **partial** when some steps completed and others did not.

A post-commit notification failure is not "nothing happened". Catch-and-return-failure after a
timeout is how customers get charged twice. Return an unknown outcome and make recovery idempotent.

## Cancellation

Cancellation is a request, not a guarantee. State whether the operation stopped, completed or
continued. A durable effect is not cancelled because a caller asked; it may need a separate
compensation. Do not add an unused cancellation token to satisfy a review.

## Evidence

Criticality determines evidence:

- a test that injects failure between steps;
- a duplicate-submission test;
- a reconciliation query and alert;
- a runbook for manual recovery;
- a recorded review explaining why the effect is not critical.

A clean architecture scan is not evidence for any of these. `A013` is a warning because some
effects are low-impact, but a payment, inventory decrement or required audit record is not.

## Assessment and reporting

`C008` and `A010`–`A013` are manual in every profile. In an assessment:

- **confirmed defect** — the reviewed effect is unowned, duplicates are silently repeated, or the
  outcome is false;
- **suspected defect** — the contract is opaque or the evidence is incomplete;
- **insufficient evidence** — the repository does not expose enough to decide;
- **not applicable** — the effect or the conditional obligation does not exist.

A suspected defect is a review item, not a proven violation. A missing detector is not a pass.
