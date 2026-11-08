# ACIMA communication plan — <repository>

Owner: <name>            Audience size: <n>            Cadence: weekly + monthly

## 1. Audiences and messages

| Audience | What they care about | Core message | Channel | Owner | When |
|---|---|---|---|---|---|
| Engineers | Monday's workflow | "Import contracts, not implementations; the remedy is in the failure." | team channel + PR comments | <name> | kickoff, ongoing |
| Tech leads | review load, ownership | "You review contract changes for your module; waivers are yours." | leads sync | <name> | weekly |
| Manager | delivery risk | "Baseline first, gate second, no rewrite." | 1:1 | <name> | biweekly |
| Leadership | cost and trend | "Finding count, unowned exceptions, lead time." | monthly one-pager | <name> | monthly |
| New joiners | how the place works | "Contracts are the safe surface; here's the first-week path." | onboarding doc | <name> | on hire |

## 2. Moments that need a message

| Moment | Message | Template |
|---|---|---|
| Before the gate exists | kickoff: what changes, what does not, why | references/40-communication.md #1 |
| First new finding in a PR | consequence, rule, exact fix, waiver option | #2 |
| Waiver negotiation | owner, reason, expiry, renewal conversation | #3 |
| Monthly | count, owners, merged slice, next, risk | #4 |
| Shortcut request | offer the legitimate path, make the exception visible | #5 |
| Gate disabled | incident-style note: why, how long, who fixes | 60-troubleshooting.md |

## 3. Cadence

| When | What | Who | Artefact |
|---|---|---|---|
| Kickoff | 45-minute walkthrough, one real finding | all engineers | recording + this plan |
| Weekly | office hours, 30 minutes | volunteers, owners | notes in channel |
| Monthly | one-page status, waiver review | manager + owners | docs/acima/status-<month>.md |
| Quarterly | level review, rule amendments | architecture owner | decision record |

## 4. Escalation

- Boundary disagreement between teams → architecture owner decides by <date>; recorded in ADR.
- A rule producing repeated legitimate waivers → standard amendment proposal, not a quiet waiver.
- A gate that cannot be fixed within a week → disable with a dated note, report it as absent.

## 5. Tone rules

- Consequence first, rule ID second.
- Say "pre-existing" for every baselined finding.
- Never present a level as a maturity badge.
- Put the remedy in the failure message; documents are not communication on their own.
