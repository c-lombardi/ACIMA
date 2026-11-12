# 45 Discovery


## Discovery: the agent's job

Inspect before asking architectural questions. The target may be a package, library, framework,
SDK, application, monolith, distributed system, service, worker, plugin host or a mixture; do not
assume a type. Establish, with evidence and confidence:

1. what constitutes an ownership boundary and how modules are represented;
2. which artifacts are only distribution or deployment units;
3. how contracts are exposed and dependencies are declared;
4. where composition occurs, including each composition boundary and whether a host is optional;
5. how state and configuration are owned;
6. which requirements already hold, which need adaptation and whether ACIMA adds meaningful value.

When no authoritative map exists, automatically run module-boundary discovery. The discovery
engine is shared by the preflight and assessment paths and produces a proposal, not an ownership
fact. It inspects manifests, source areas, contract-shaped paths, observed import lines, data and
configuration locations, composition roots, existing architecture evidence and unassigned source.
Each candidate module records observed evidence, inferred responsibility, confidence, limitations,
candidate contracts and dependencies. Unassigned production files remain visible; do not force them
into a module to make inventory look complete. Evaluate the proposed map qualitatively, including
responsibility coherence, contract separation, dependency cycles, private implementation coupling
and composition ownership. Findings are recommendations with observed facts, rationale, benefit,
risk, uncertainty and whether user input is necessary. The reviewer accepts, modifies, rejects or
defers each boundary and recommendation; the proposal is never silently promoted.

Also record languages, frameworks and manifests; project/package layout; entry points; construction
and injection patterns; existing boundaries and dependency direction; shared libraries;
persistence, configuration and external-effect ownership; tests and existing architecture checks.
Discover the enclosing Git repository root when the requested project is nested. Inspect root-level
architecture rules, CI workflows and architecture documentation as context without silently expanding
the production source scope to unrelated sibling projects. For a multi-project or multi-language
repository, inspect every relevant project and assess both project-local architecture and
cross-project integration contracts. Do not select only the first
detected language and imply the rest were covered. Discover and compare existing architecture tests,
custom rule engines, static analyzers, dependency restrictions and CI gates before recommending new
enforcement. Continue qualitative inspection when a module map is missing; project manifests,
imports, references, deployment manifests and composition roots are evidence for provisional
boundaries, not approval of module ownership.
build, packaging and CI. A repository may be several kinds at once — say so, and never present a
directory name as an ownership decision.

For each material inference give what was found, the evidence, confidence, and what remains
uncertain. Ask only what the repository cannot settle: shared-kernel status, composition-boundary
ownership, duplicate names, and who owns exceptions.

Then explain ACIMA against the target system: for each meaningful difference, the existing design, the
ACIMA expectation, why it matters, whether it is a confirmed problem, a suspected one, an acceptable
design or insufficient evidence, what would change, and whether judgement is required. Recognise what
already satisfies a requirement — do not sell existing good practice back as work. Complete all
56 evidence-backed requirement dispositions before making an adoption recommendation. If the full
review establishes that ACIMA would add little, say that plainly and recommend against adoption.

Ground benefits in observed characteristics: preventing a change in one implementation from breaking
its consumers, making ownership visible, stopping persistence or vendor details leaking across
boundaries, giving immediate feedback at the boundary, and enforcing the same constraint for people
and agents. Distinguish what this repository can achieve now from what needs organisational work.
