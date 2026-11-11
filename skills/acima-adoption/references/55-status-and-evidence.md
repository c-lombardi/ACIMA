# 55 Status And Evidence


## Status: what is actually proven

`acima.py status --root .` reports the evidence diagnostics and a scope-aware engagement summary.
The vocabulary is `NOT_STARTED`, `READY`, `IN_PROGRESS`, `BLOCKED`, `COMPLETE`, `NOT_APPLICABLE`
and `UNKNOWN`; objective dispositions also distinguish `declined`, `deferred`, `optional` and
`not-applicable`. A step or objective is complete only when its criterion is verified:

- **scope** is an explicit owner artifact (`.acima/adoption-scope.json` or an `adoption` object in
  the config) naming `required`, `approved`, `declined`, `deferred`, `optional` and
  `not-applicable` objectives. File presence never implies approval, and a missing scope is
  `UNKNOWN`, not full adoption. Required and approved objectives must complete; the others never
  block. A prerequisite is promoted to required, and a declined prerequisite for an approved
  objective is a scope conflict.
- **fit** is complete only when the approved scope exists and a read-only assessment artifact
  (`docs/acima/assessment.json`) records a valid verdict for this repository. A config file proves
  neither fit nor approval.
- **trust the tool** requires a proof record naming the standard and catalog hash with `L001` and
  `D001` detected; an empty or stale record blocks.
- **calibration** compares the manifest pin with the catalog on disk; a config file proves nothing.
- **declare** requires a parsable config with at least one unit that covers source; review and
  approval are not proven by the file.
- **freeze** requires a run artefact with `sourceFiles > 0`, an `execution` map and a findings list.
  A fingerprint file alone is in progress, not measured.
- **own** requires owners, scopes, fingerprints and unexpired waivers; invalid, unowned or expired
  exceptions block, and are never accepted as exceptions.
- **gate** reads the actual `run:` command, not just the file name: it must invoke a recognized
  enforcer with `--root .`, the declared level, and a pull-request or merge trigger. Disabled,
  advisory, conditional or reusable/composite steps are blocked; a valid configured step is
  *in progress, not observed*. An observation must name the repository, commit, workflow, command,
  time, standard, catalog hash, level, source count and exit status, and its workflow/command must
  match a valid invocation in that same workflow. A manually recorded result is *in progress, not
  independently verified*; only a provider-sourced, non-skipped run with a successful conclusion
  against the matching repository and `HEAD` completes the step. CI configuration alone never
  proves enforcement.
- **slice** compares runs only when standard, level, source scope and execution map match; a lower
  count from a different scope is not an improvement, and a resolved finding must be named with no
  new errors.
- **claim** computes the class with `acima.py claim` and binds it to the repository state. A
  manual-evidence file is not proof; invalid or expired evidence blocks, missing evidence is a
  partial assessment, and a full result from another commit, catalog or configuration is historical
  or stale. `--require full` succeeds only for a current claim; missing Git metadata never counts as
  current.

Assessment-only and local-only engagements can complete without CI, waivers or optional documents.
When full conformance is approved, every claim requirement still applies; adoption completion and
architectural conformance stay separate. Optional documents (adoption plan, communication plan,
STATUS dashboard, summary) never block progress and never appear in "next". Do not create optional
artifacts unless the approved scope includes them or the owner asks. Do not create a communication
plan by default.

Status output states what is complete, in progress, remaining and blocked within the approved
scope; what is declined, deferred, optional or not applicable; the single next action with its
prerequisite, command, done condition and effect; and whether approval is required. A status
command never recommends a write unless that scope was approved; it proposes instead.
