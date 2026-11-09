# Consent workflow validation

## Method

Validation used disposable repositories under the system temporary directory. No eShop or other
real repository was modified. The executable checks are in
`conformance/test_consent_workflow.py`; the behavioral rules are in `SKILL.md` and
`references/15-consent-and-scope.md`.

```bash
python3 conformance/test_consent_workflow.py
```

The fixture contains `src/orders`, `src/catalog`, `src/shared` and `tests/`, which is enough to
produce heuristic candidate units and to expose an ambiguous shared path.

## Scenario results

| Scenario | Input | Method and evidence | Result |
|---|---|---|---|
| A. Assessment | “Assess this repository using ACIMA.” | `assess`, `inspect` and read-only preflight; SHA-256 snapshot before/after | pass: byte-identical; no config, `.acima`, CI or docs |
| B. What adoption requires | “What would it take to adopt ACIMA here?” | read-only assessment plus the proposal contract test | pass: proposal has recommendation, scope, exact paths, statuses, decisions, costs and approval question |
| C. Approve adoption | “Proceed with the proposed adoption.” | explicit `--write-draft acima.config.json` on a disposable target | pass: only that config was added; no other artifact appeared |
| D. Partial approval | “Configuration and local enforcement, no CI or baseline.” | config-only write; assert absence of `.acima`, `.github`, `docs`, and source/test changes | pass: partial scope honored; no full-adoption claim is made |
| E. Decline | “No, just give me the assessment.” | read-only path only; snapshot equality | pass: no artifacts created |
| F. New requirement during implementation | a required build change appears after approval | written stop condition: unapproved build/source/CI paths halt and require a new decision | **instruction-level only** — not conversationally executed |
| G. Ambiguous architecture | shared libraries, hosts, test projects cannot be classified by name | proposed units are labelled heuristic; mapping classes and confidence required; low-confidence map cannot become confirmed config | **partial** — tool-level labeling tested; owner clarification not conversationally executed |

## Executable evidence

`conformance/test_consent_workflow.py` checks:

1. **Read-only assessment** — `assess`, `inspect` and preflight leave every file hash unchanged.
2. **Explicit draft write** — `--write-draft` adds exactly `acima.config.json`, preserves existing
   files, and carries the `Heuristic` review note.
3. **Partial scope** — config-only approval creates no baseline, `.acima/`, CI, docs or source edits.
4. **Proposal contract** — the seven required sections, status vocabulary, “what this will not
   accomplish”, exact approval question, and “no persistent changes” statement are present.
5. **Ambiguous map** — candidate roles are labelled, `src/shared` is visible as a proposal, and no
   config is written without an explicit request; the reference defines the full mapping vocabulary.

The read-only test also inspects preflight's printed next steps and requires approval language there;
the first recommendation is to present the proposal, not to generate a draft.

The test does not simulate a live agent choosing whether to ask. Scenario F and the judgement part
of G remain behavioral specifications, and the validation records that limitation rather than
claiming a completed conversation.

## Read-only evidence

Before each assessment, the test records a SHA-256 digest for every fixture file. After the commands,
it compares the whole map: no added, removed or changed file is accepted. The same comparison runs
before and after preflight without write flags.

The draft test separately computes the set difference. It asserts exactly one added path,
`acima.config.json`, and no deletions.

## Consent evidence

- `SKILL.md` changes routing for “adopt” to assessment plus proposal, with the target-write column
  reading “not until consent”.
- The four phases and the approval table are in `SKILL.md`; the full boundary is in
  `references/15-consent-and-scope.md`.
- The proposal template ends with: “Would you like me to proceed with this adoption plan and create
  the listed files and changes?”
- Greenfield and brownfield playbooks are explicitly Phase 3 and require approval for their writes.
- Commands and agent guidance distinguish read-only assessment from `--write-*` adoption acts.

## Partial approval evidence

The config-only fixture proves the tool does not cascade into a baseline, waiver file, CI workflow or
documentation. The skill and reference state that a partial scope must be described with its gaps and
must not be called full adoption or conformance. The artifact matrix gives the enabled/not-enabled
pairs for common subsets.

## Remaining limitations

- **No live conversational evaluator.** The agent runtime available in this session could not run an
  independent semantic evaluator (provider authentication failed). The validation is the executable
  tool contract plus a review of the instructions, not an independently scored agent transcript.
- **Behavioral scenarios F and G** depend on an agent recognizing a new requirement or ambiguity.
  The stop conditions exist, but no end-to-end conversation was executed.
- **No CI execution.** A workflow's presence is not evidence that it ran; none was claimed.
- **No conformance claim.** Creating a config or passing the fixture does not establish architectural
  conformance for any real repository.
- **No real-repository adoption.** The eShop assessment was not repeated with writes; that would
  require explicit owner approval and is outside this validation.
