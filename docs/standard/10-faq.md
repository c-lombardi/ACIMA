# 10. FAQ

Objections and questions, answered as directly as possible. Most of these are arguments you will
actually have, usually in review, usually at 5pm.

---

### "Isn't this just Clean Architecture with extra steps?"

No. Clean Architecture describes *layers inside an application* — domain knows nothing, application
depends on domain, infrastructure depends on both. ACIMA contains that (`L001`) as one of five rule
categories, but its subject is **ownership between modules**: contracts, zero-dependency public
surfaces, acyclicity, and data ownership.

You can have a textbook Clean Architecture solution that violates ACIMA completely by having one
`Domain` project every feature references. And you can satisfy ACIMA's dependency rules with a
three-folder module. The subject matter is different: Clean Architecture is about *direction*, ACIMA is
about *ownership and surface*. They compose: keep Clean Architecture inside a module, and let ACIMA
enforce the module boundaries the rings do not express.

---

### "Do we have to abandon Clean Architecture, Hexagonal, DDD or microservices to adopt ACIMA?"

No. ACIMA is an enforcement standard that sits beside the architecture you chose. It does not
replace Clean Architecture, Hexagonal Architecture, domain-driven design, a modular monolith or
microservices; it makes the boundaries that choice declares executable, in your language, on every
commit. Keep your layers, ports, contexts or services, declare the units and contracts, and let the
gate fail when a boundary is crossed.

ACIMA is more prescriptive than some families in specific places — contracts may not reference
other contracts, a cross-module in-process transaction is forbidden, contracts carry no third-party
dependencies. Each is justified independently and scoped to boundaries, not internal design;
departures are owned waivers. [Your architecture, enforced](../guides/architecture-families.md) has
the per-family mapping and the qualification.

---

### "Why can't contracts reference other contracts? That's stricter than ModularMonoliths says."

The published guidance is "no dependencies, ideally". ACIMA makes it absolute, for two reasons.

**Cycles.** The moment `A.Contracts → B.Contracts` is legal, `B.Contracts → A.Contracts` is legal, and
the cycle you were trying to prevent reappears one level up — where it is harder to see and, in .NET,
impossible to compile. The whole guarantee of acyclicity rests on contracts being leaves.

**Independent evolution.** A contracts package that references another cannot be versioned, published
or consumed independently. Its version becomes a function of another module's version, which is exactly
the version-lock coupling `A004` forbids.

The practical cost is small: if two modules truly need the same type, it is either a value (kernel) or
you duplicate the shape at the boundary (which is usually correct, see `5.5`).

---

### "Doesn't zero-dependency contracts mean I can't use a validation library / JSON attributes / enums with attributes?"

Yes, and that is the point. Contracts are the boundary; the boundary should not dictate technology to
every consumer.

- **Validation**: validate in the contract's constructor with plain code. You need `if (price.IsNegative) throw`
  far more often than you need a declarative attribute.
- **Serialization**: configure the serializer in the host. If a serializer cannot handle your immutable
  type, map to a transport type in the host. That mapping is one file; the dependency would be forever.
- **Enums**: plain language enums are fine — they are core language constructs, not packages.
- **Source generators**: if a generator emits code that references a package, the generated code is a
  dependency; put the generated types in the implementation or host, not in contracts.

If a contracts unit genuinely cannot exist without a package, that is a signal the type is not a
contract — it is an implementation detail that wants to cross a boundary.

---

### "Aren't immutable messages expensive? Every update allocates."

They are cheap enough, and the alternative is worse. Immutable messages are typically short-lived
(created per request, per event), which is exactly the allocation profile modern runtimes handle best.
The expensive pattern is not allocation — it is a shared mutable object whose ownership becomes
ambiguous, which produces retries, defensive copies scattered across the codebase, and bugs that only
appear under concurrency.

If profiling shows allocation as a real cost in a hot path, use a builder or a struct-pool *inside* the
implementation, and map to the immutable contract at the boundary. Never let a hot path become the
reason a published contract can be mutated.

---

### "How do I report across modules if every module owns its data?"

Subscribe to events and build a projection, owned by the reporting module (`6.5`). This is the standard
answer and it is genuinely better than the join: the projection has a defined schema, it survives
provider refactors, and it can be rebuilt by replay.

The trade is latency and eventual consistency. For most reporting that is acceptable (reports are
rarely read-your-write). For the cases where it is not, ask whether the report is really a *query of one
module* — often it is, and the answer is to ask that module.

---

### "Our modules genuinely need each other. What do we do?"

You have three legitimate answers, in order of preference (`P5`):

1. **A process manager/saga** in the module that owns the decision. It reacts to events and issues
   commands; neither module references the other's contracts except to receive facts and send commands
   it is entitled to send.
2. **An event instead of a call.** If A only needs to *know*, publish.
3. **Merge the modules.** Sometimes two modules are one bounded context. Merging is honest and cheap;
   a cycle is expensive and dishonest.

What is not an answer: a shared kernel entity, a `Common` interface, or a `D005` waiver. All three
defer the decision and make the eventual fix bigger.

---

### "Where do transactions live if modules can't share one?"

Inside the module that owns the data (`6.5`). Cross-module consistency is eventual — saga, outbox,
reconciliation. This is true in-process too: an in-process modular monolith can technically wrap two
modules in one transaction, and ACIMA forbids it, because that transaction is the exact coupling that
prevents either module from being extracted, and it is invisible in the dependency graph.

---

### "What about shared enums and constants? We have hundreds."

Enums: put them in the contracts of the module that owns the concept. If two modules need the same
enum, one owns it — the other references that module's contracts, which is legal (`implementation →
other contracts`). Constants: configuration is owned (`A002`); business constants belong to the module
whose rule they encode.

Hundreds of shared constants is the fingerprint of a `Common` project that has become a second domain
model. That is the migration, not an exception.

---

### "Does ACIMA require CQRS? Event sourcing? DDD?"

No. It requires a contracts surface with immutable messages, and it requires that boundaries be
crossed through that surface. How you implement the inside is yours:

- CRUD is fine, and the reference implementations are CRUD.
- CQRS is fine, and maps naturally onto commands/queries in contracts.
- Event sourcing is fine; events in contracts are integration events, which is a separate (and
  compatible) concept from domain events stored in a stream.
- DDD is not required, but aggregates make contracts much easier to define.

---

### "Is this only for monoliths?"

No, but it is *easiest* for monoliths, and it is where the enforcement pays the most, because that is
where boundaries are erased most easily. In a distributed system the same rules apply with the transport
in between; `D001` becomes "no service reads another service's database", which is a rule most teams
already believe and do not enforce.

The contracts unit maps to what a service exposes: OpenAPI, gRPC proto, or an event schema. `P6` maps
to "your wire format has no setters". `P7` maps to "you can deploy alone".

---

### "Our language has no enforced visibility. Is ACIMA pointless for us?"

Opposite. It is most valuable where the compiler is silent, because nothing else will catch the
violation. Python's `import` will happily reach into any module; the architecture test is the only
boundary Python has (see the [Python profile](../languages/python.md)).

The cost is that the rule runs as a test rather than as a compile error, so it must be in the pre-merge
gate. That is a process requirement, not a technical one.

---

### "How much does the enforcer have to do? Can't we just use ArchUnit/NetArchTest?"

Use them where they fit; they are excellent and ACIMA's rules map onto them directly (the language
profiles show the mapping). What they do not give you, and what ACIMA specifies, is:

- the same rule **ids** and finding **format** across languages, so one gate and one report work;
- contract-shape rules (`C001`–`C007`), which are usually written per repository and drift;
- waiver hygiene as a rule (`G001`, `G002`);
- the API baseline (`G004`).

In practice the layered answer is: ArchUnit/NetArchTest for dependency and layering rules,
Roslyn/eslint/import-linter/custom analyzers for contract-shape rules, and a thin runner that emits
ACIMA findings and enforces the waiver file. The reference enforcers in this repository are that thin
runner, implemented per language with no third-party dependencies, precisely so they are easy to read
and adapt.

---

### "Isn't the waiver file just a list of things we're going to ignore?"

It is a list of things you have *decided* to accept, with a date and an owner. The difference between
that and a suppressed warning is the entire point of P9: one is visible, reviewable and expiring; the
other is invisible and permanent.

The metric to watch is not the waiver count — it is the **median age** of waivers. If it is growing,
the architecture is being abandoned; if it is shrinking, the ratchet is working.

---

### "What if a rule produces a false positive?"

Two options, in this order:

1. **Fix the rule.** False positives are defects in the enforcer, and every rule here is specified
   precisely enough to be implemented without heuristics. If the implementation cannot avoid guessing,
   the rule needs a narrower definition in the next minor version.
2. **Waive it**, narrowly, with a reason that says "tool limitation", and open a ticket against the
   enforcer.

What you must not do is disable the rule, because then the next real violation goes unnoticed along
with the false positive. A false positive that stays is evidence the tool needs work, not evidence the
architecture is wrong.

---

### "How do I keep the configuration from becoming a second architecture document?"

The configuration is deliberately minimal: units and paths. It cannot express "this module may call
that one on Tuesdays". If someone wants to add expressive policy, that is the moment to check whether
the problem is a design problem (a missing module, a missing concept) rather than a policy problem.

`G005` keeps the file honest mechanically: every file must belong to a declared unit, so the config
cannot drift out of date without a failure.

---

### "What is the smallest thing I can do today?"

1. Create one `X.Contracts` project for your most-referenced module.
2. Move only what other modules actually use into it.
3. Add a test that fails if any other module references `X`'s implementation.
4. Put that test in CI.

That is L1 for one module, it takes a day, and it is the first turn of the ratchet.
