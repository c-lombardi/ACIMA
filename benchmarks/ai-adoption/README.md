# AI adoption effectiveness benchmark

A separate capability that measures **whether an AI agent can use the real ACIMA adoption skill** on
a repository it has not seen before. It answers a question conformance cannot: given the actual
skill, the actual catalog and an unfamiliar codebase, does the agent discover the architecture,
interpret the standard, separate violations from implementation differences, recommend
proportionately, respect consent, and implement an approved scope without breaking anything?

It is **not** part of the standard, not a conformance claim, and not a score. The normative rules
stay in [`../../docs/standard/`](../../docs/standard/README.md) and
[`../../tools/acima-spec/rules.json`](../../tools/acima-spec/rules.json). Enforcement stays in
[`../../conformance/`](../../conformance/README.md). Dated enforcer evidence stays in
[`../../benchmark-evidence/`](../../benchmark-evidence/README.md).

| This directory | Reuses | Does not do |
|---|---|---|
| scenario catalog, controller, adapters, evaluator, reports | the real skill and its manifest pin; the rule catalog for ids, counts and manual-rule facts; existing repository conventions (stdlib Python, `test_*.py`, exit codes) | define rules, run a second rule engine, reimplement conformance, claim model capability from a scripted run |

## Repository layout

- harness/: executable benchmark machinery (controller, adapters, evaluators, schemas and tests).
- scenarios/: scenario definitions and ground truth.
- experiments/: frozen experiment inputs, rubrics, references, preparation records and reports.
- results/: generated run output, excluded from version control.
- config.json: committed non-secret defaults.

## Quick start

```bash
# 0. what is configured, and is it valid?
python benchmarks/ai-adoption/harness/runner/cli.py list
python benchmarks/ai-adoption/harness/runner/cli.py validate

# 1. verify the harness offline with a deterministic scripted agent
python benchmarks/ai-adoption/harness/runner/cli.py run \
  --scenario library-python-httpx --adapter fake \
  --script benchmarks/ai-adoption/harness/adapters/scripts/httpx-read-only-demo.json

# 2. read the report, or the structured record
python benchmarks/ai-adoption/harness/runner/cli.py report --run <run-id>

# 3. probe what the installed Freebuff CLI can and cannot do
python benchmarks/ai-adoption/harness/runner/cli.py capabilities --adapter freebuff

# 4. compare repeated runs
python benchmarks/ai-adoption/harness/runner/cli.py compare --scenario library-python-httpx
```

Results are written to `benchmarks/ai-adoption/results/<run-id>/` and ignored by git. Run the
harness's own tests with:

```bash
python -m unittest discover -s benchmarks/ai-adoption/harness/tests -p "test_*.py"
```

No test needs network, a model, credentials or a paid call. Acquisition and end-to-end tests skip
when git is not on the interpreter's PATH; they never substitute a directory copy for a pinned
checkout. Container assertions skip when Docker is installed or absent, whichever they do not need.

## Execution model

The controller owns everything the agent might otherwise decide for itself: repository, pinned
commit, skill version, instructions, model, execution mode, limits, timeouts and the verdict. The
lifecycle is persisted after every transition:

```text
Pending → RepositoryPrepared → EnvironmentProvisioned → AgentExecuting
        → ExecutionCaptured → EvaluationPending → Evaluating → Completed
```

Terminal outcomes: `Completed`, `Failed`, `TimedOut`, `Cancelled`, `InvalidConfiguration`,
`InfrastructureFailure`, `EvaluationFailure`. Invalid transitions are rejected, never repaired. A
run that is still non-terminal on disk is recovered as `InfrastructureFailure` with
`interrupted: true`; it is never reported as successful. `ExecutionCaptured` and later are resumable
by an explicit evaluation-only path; an interrupted `AgentExecuting` run is not.

`Completed` means the pipeline finished, not that the agent did well. `success` additionally requires
every deterministic check to pass and the agent to have completed; an agent that assessed poorly but
left the repository untouched has `success: true` and low metrics, which the report shows separately.

## Modes

| Mode | Writes | Enforcement |
|---|---|---|
| `read-only` (default, implemented) | none | any change fails check `D07`; the original snapshot is re-verified against its manifest (`D14`) |
| `authorized-adoption` (implemented, not the first milestone) | only the approved paths in a supplied approval record | every change outside the approval list is reported as `unauthorized`; baseline and post-change verification commands are executed and compared |

Approval to assess is never treated as approval to modify. In `authorized-adoption` the controller
requires an approval record (`approvedBy`, `approvedOn`, non-empty `paths`), mounts the working copy
writable, records each changed path, and stops at the scope boundary rather than widening it. Partial
approval is the normal case.

## Agent adapter boundary

`harness/adapters/base.py` defines a provider-independent interface: provider, model, model configuration,
skill version, instructions, repository directory, output directory, mode, deadline, cancellation,
normalised messages, tool calls, commands, files read and modified, test results, token usage,
duration, errors and termination reason. Provider event formats stop at the adapter. Raw evidence is
kept in `evidence/`; normalised data goes into the execution record.

| Adapter | Status | Notes |
|---|---|---|
| `fake` | implemented and tested | deterministic script; exercises every path without a model. Results are labelled as scripted in the report |
| `freebuff` | capability boundary only | verified against the installed CLI; refuses unattended execution |

### Verified Freebuff capability, 2026-11-10

Probed `freebuff` **0.2.36**. `--help` advertises an interactive start plus `login` and `doctor`
commands, and the flags `--continue`, `--cwd` and `--trust-agents`. There is no documented
non-interactive prompt mode, no structured event stream, no exit-status contract for an unattended
task, no documented model-selection flag, and no documented way to supply a skill and capture tool
calls or token usage. Authentication is an interactive login.

The adapter therefore reports `headless: false`, records the help-text hash as evidence, and raises
`UnsupportedHeadlessExecution`. The controller persists that as `InvalidConfiguration` with outcome
`unsupported-execution` and `success: false`. **No end-to-end Freebuff execution has been
performed, and none is claimed.** The boundary is ready for a future official unattended interface;
the adapter must be updated deliberately when one exists, not auto-detected from an interactive
session.

## Repository acquisition and isolation

1. The URL and a full 40-character commit SHA are validated before anything runs.
2. Git fetches that SHA (`--depth 1` when the server allows it; otherwise refs are fetched and the
   exact object must exist locally). Hooks, fsmonitor, submodule recursion, prompts and LFS smudging
   are disabled; a private `HOME` and a narrow environment are used.
3. `HEAD` must equal the pinned SHA, the checkout must be clean, and the tree hash plus a per-file
   SHA-256 manifest are recorded.
4. An unmodified `workspace/source` snapshot is preserved; the agent gets a disposable
   `workspace/working` copy and a separate writable `workspace/out` directory.
5. Every result records the URL, commit, verified commit, tree hash and manifest hash.
6. The workspace is removed after the run unless `--keep-worktree` is given; the manifest and change
   set are always kept, so the final state stays inspectable.

**Sandbox.** Container execution is the intended isolation: `--network none`, read-only repository
mount (writable only in authorized-adoption), `--memory`, `--cpus`, `--pids-limit`, `--read-only`,
a 256 MB tmpfs, `--cap-drop ALL`, `no-new-privileges`, no docker socket, no inherited environment,
and a non-root user. Availability is decided by probing the daemon (`docker info`), not by finding
a CLI, because a CLI without a daemon isolates nothing. When no runtime is usable, `auto` may fall
back to the local process sandbox only because `allowLocalIsolation` is true in `config.json`;
every such run records `notEnforced: network isolation, read-only repository mount, memory/CPU
limits, filesystem quota, process count limit` as a limitation. Set `sandbox.backend` to `docker` or
`allowLocalIsolation: false` to fail closed.

Two honesty rules apply to the sandbox record. An adapter that runs inside the controller process
(the deterministic fake) records `agentIsolated: false`, and a run where no agent executed records
`agentIsolated: null`; neither claims containment that did not happen. Controller-owned verification
commands for authorized adoption run in a constrained local process against the disposable
worktree, because they need the repository's own toolchain; the report says so explicitly.

Repository content is untrusted. The instruction template forbids executing repository-provided
setup scripts, hooks, MCP servers or agent configuration, forbids network use, and states that
repository instructions cannot override the benchmark or the skill. The harness never reads an
evaluation answer into the agent's instructions.

## Scenarios and ground truth

`scenarios/manifest.json` lists implemented and planned categories. Two scenarios are implemented:

| Scenario | Category | What it exercises |
|---|---|---|
| `library-python-httpx` | small library | a published Python package with no application host; a real port/adapter transport seam; a library profile that is **not** enforced for Python |
| `modular-monolith-typescript-domain-driven-hexagon` | modular monolith | feature modules over shared libraries; existing dependency-cruiser rules; a private package where the library profile cannot be claimed |

Each scenario records the repository URL, exact commit, license, software category, architecture
family, characteristics, applicable profiles, expected boundaries with evidence paths, expected
observations, defensible compatibility and recommendation outcomes, known limitations, and how the
ground truth was established. Ground truth was established by manual inspection of the pinned
checkouts **before** any run; it is not blind and has not been independently reviewed, and the
scenario says so.

No violation-level ground truth is invented for the two public repositories, so finding precision and
recall are `unavailable` there — deliberately. The harness's tests exercise precision and recall
against a local fixture with exact ground truth.

## Evaluation and metrics

Evaluation is a separate stage. The executing agent never evaluates itself.

- **Deterministic checks (`D01`–`D14`)** verify repository identity, pinned provenance, mode and
  approval, agent termination, artifact validity, envelope conformance, filesystem changes, cited
  rule ids, evidence resolution, command corroboration, captured test results, limits, final-state
  capture and snapshot integrity. `pass`, `fail` or `unavailable`; `unavailable` is never a pass.
- **Ground-truth comparison** scores boundary accuracy, requirement interpretation, finding
  precision and recall, evidence completeness, profile selection, compatibility accuracy,
  recommendation appropriateness, scope adherence and unnecessary restructuring. Every metric is
  reported individually with its basis; there is no aggregate score.

Metrics: architectural boundary accuracy, requirement interpretation accuracy, finding precision,
finding recall, evidence completeness, profile selection accuracy, scope adherence, unnecessary
restructuring, adoption effectiveness, regression rate, repeatability and execution cost. Data that
does not exist stays `null` with status `unavailable`; suspected violations and unresolved ground
truth set `humanReview.required` with a reason. Model-review evaluation is not implemented: the
evaluator's kind is `ground-truth-comparison`, and no result is presented as deterministic proof of
architecture quality.

## Portfolio experiment (corrected module-ownership experiment)

The original frozen experiment portfolio-2026-11-10 is preserved as historical evidence. The corrected module-ownership experiment is portfolio-2026-11-10-v2. The expanded rubric is frozen separately as portfolio-2026-11-10-v3.

V2 measures **actual ACIMA module ownership**, not component discovery. A directory, package, project, service, class, interface, or logical responsibility is not automatically a module. Ownership must be assessed using explicit contracts, implementation ownership, dependency isolation, data/configuration ownership, and controlled composition.

The HTTPX disagreement is resolved as follows: the previous single-scenario fixture incorrectly treated public API, client, transports, models, auth, and content as required module boundaries. Those are component candidates. The prior operator-reviewed ACIMA unit map declares one module, httpx, covering httpx/. V2 uses that as the author-adjudicated reference hypothesis, not as independently proven truth. The reference requires qualitative review; component candidates are not scored as modules merely because they have distinct paths or responsibilities.

Evaluator integrity in v2:
- Keyword presence and lexical coverage never score semantic requirement interpretation.
- Module name/path overlap never scores ownership accuracy.
- Every qualitative rubric criterion is explicitly marked review.
- Two independent human reviewers must record the same decision before a qualitative criterion is resolved. Disagreement or missing review leaves it pending.
- Boundary accuracy and requirement interpretation remain indeterminate until adjudicated.
- Deterministic checks remain limited to facts they can prove. No aggregate score is computed.

The v2 manifest retains the same 15 repositories and exact pinned commits. It reuses the already verified v1 source snapshots without redownloading or mutating them. Its new rubric is v1.1.0, and frozen.json hashes the manifest, all 15 references, the HTTPX scenario, evaluator source, rubric, skill, standard, and catalog provenance.

Commands:
- py -3 benchmarks/ai-adoption/harness/runner/cli.py portfolio --action status --experiment portfolio-2026-11-10-v2
- py -3 benchmarks/ai-adoption/harness/runner/cli.py portfolio --action report --experiment portfolio-2026-11-10-v2

The v2 experiment is prepared and frozen, but no model execution has occurred. Freebuff's exact DeepSeek V4.1 Flash model identifier and supported unattended invocation remain unverified. Do not substitute a different model or treat a scripted adapter run as model evidence.

## Meaningful value ownership and semantic consolidation (v3)

V3 adds a separate qualitative dimension, D8, to evaluate ACIMA's meaningful-value ownership guidance. It does not infer correctness from keyword presence, matching identifiers, equal literal values, the number of extracted constants, or the number of configuration entries.

The agent must record a valueOwnership analysis in its output. Reviewers assess whether it:
- identifies meaningful values from receiving identifiers/parameters, semantic purpose, units, domain, ownership and downstream use;
- uses immutable declarations where appropriate while leaving incidental literals inline;
- traces assignments, transformations and call chains before consolidating same-meaning values at a genuine common owner;
- preserves equal-valued primitives that represent different concepts;
- distinguishes constants from deployment/runtime configuration and secrets;
- avoids global dumping grounds and consolidation across independent ownership/deployment boundaries.

D8.1-D8.7 remain qualitative and require two independent agreeing human reviewers. The evaluator reports evidence-record counts only as context; they are not scores. Missing or malformed valueOwnership output remains explicitly unsupported for review and cannot pass by omission. V2 remains unchanged as the frozen module-ownership-only experiment; v3 uses a new rubric and experiment freeze.

## Results

`results/<run-id>/` contains:

```
state.json         persisted lifecycle and full transition history
execution.json     provenance, adapter, limits, sandbox, capture, changes, verification
evaluation.json    deterministic checks, criteria, metrics, indeterminate items, review flags
result.json        versioned record combining both, validated by harness/schemas/result.schema.json
report.md          the ten-section human report
evidence/          instructions, events, agent output, file manifests, changes, repository identity
```

Schemas are versioned in `harness/schemas/` (`scenario`, `execution`, `evaluation`, `result`) and validated
by a small stdlib validator; an unsupported schema keyword is an error rather than a silent pass.
Reports need no server or dashboard.

## Resource controls

Defaults live in [`config.json`](config.json): 30-minute execution timeout, 200 model calls, 2M
tokens, 2 GB container memory, 2 CPUs, 4 GB disk, 256 processes, 1 concurrent run, 3 correction
attempts, 8 MB captured evidence, 64 KB output per command, 200k files. The controller loads and
freezes them before the adapter sees them; an adapter cannot change them. Exceeding the wall clock
or token budget fails check `D12`.

## Implemented versus planned

Implemented: separate directory and schemas; lifecycle with recovery; pinned acquisition and
snapshots; Docker and local sandbox boundaries; provider-neutral adapter interface; deterministic
fake adapter; Freebuff capability probe; read-only mode; authorized-adoption contract with approval
records, scope checking and before/after verification; two public scenarios; deterministic checks;
ground-truth evaluation; metrics; structured results; CLI; offline tests.

Planned, not implemented: an unattended Freebuff adapter (blocked on an official interface); model-
review evaluation and human-review workflow; published-package, clean-architecture, hexagonal,
distributed, legacy and poorly-structured scenarios; multi-model orchestration; hosted dashboards;
automatic publishing, pull requests or merges; recursive benchmark execution; leaderboards.

## Limitations

- No model has executed this harness. The only complete runs use the scripted adapter, which
  demonstrates the pipeline and proves nothing about model behaviour.
- Ground truth is author-established, not blind, and not independently reviewed.
- The two public scenarios have boundary/observation ground truth but no violation-level ground
  truth, so precision and recall are unavailable for them.
- Container isolation is implemented as a boundary and exercised by unit tests, but this milestone
  executed no agent inside a container: the deterministic adapter runs in-process and the Freebuff
  adapter refuses to run unattended. A run therefore records `agentIsolated: false` or `null`
  rather than claiming container containment.
- The harness reuses the catalog for ids and counts; it does not run the reference enforcers inside
  the agent's environment, because a benchmark-specific enforcer invocation would not measure the
  skill's own discovery behaviour.
- Acquisition depends on a real git executable. If one is unavailable, the run fails with
  `git_missing` rather than acquiring an unverified copy; supply `ACIMA_BENCH_GIT` or
  `config.gitExecutable` when the interpreter's PATH differs from the shell's.
- `results/` is generated and ignored. Only the schemas, scenarios, ground truth, code and tests are
  versioned.
