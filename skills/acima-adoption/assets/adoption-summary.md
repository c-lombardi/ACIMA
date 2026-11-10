# ACIMA Repository Assessment

**Repository:** <repository>
**Assessment date:** <date>
**Architecture:** <family and the evidence for it, or "not recorded">
**Assessment status:** **<Not assessed | Assessment incomplete | Significant issues found | Partially aligned | Baseline established | Verified>** — <one sentence>

## 1. Overall result

<What ran, how many findings, how many are waived, how many are detector artefacts, what the
baseline means. Never a score.>

## 2. What this means

<Two or three short paragraphs: the repository's shape, the most consequential problem in plain
words, and what the gate does and does not prove.>

## 3. Key findings

| What was found | Why it matters | Evidence | Recommended improvement | Confidence |
|---|---|---|---|---|
| <meaning in plain language, including what the code does and how often> | <consequence or risk> | <modules, representative paths, occurrence count> | <the actual change, not a rule identifier> | <confirmed | probable | uncertain | requires review> |

Do not make an internal identifier the finding title. Keep rule IDs, fingerprints and machine coverage
in the technical evidence section; include one only when the reader asks for traceability.

## 4. What should happen next?

**<One action.>**

- **Why:** <the consequence it removes>
- **Where:** <modules and paths>
- **Done when:** <observable state>
- **Verified by:** <the command and the result it must show>
- **Needs human judgement:** <yes | no>

Then, in order:

1. <next action>

## 5. What has already been completed?

- <Only what an artefact proves.>

## 6. What has not been verified?

- <Unexecuted rules, unobserved CI, missing manual evidence, detector artefacts, expiring waivers,
  count reconciliation. Each with why it matters.>

## 7. Supporting technical details

- Full run: `<path>` — every finding with its internal check reference, path, line, fingerprint and status.
- Frozen baseline: `<path>`.
- Waivers: `<path>`.
- Triage: `<path>`.
- Adoption plan: `<path>` (if created).
- Status dashboard: `<path>` (if created).
