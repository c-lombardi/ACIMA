# 12 Getting Started


## Where you are running
Three execution contexts exist. Detect yours before printing a command; a path that does not exist
in the active context is not a runnable command.

| Context | What exists | How to invoke |
|---|---|---|
| ACIMA source checkout | `tools/`, `docs/`, `examples/`, the skill | `python3 tools/acima.py ...`, `python3 skills/acima-adoption/scripts/...`, `examples/<lang>/tools/...` |
| Copied or installed skill | `skills/acima-adoption/` with its `vendor/` snapshot | `python3 <skill>/scripts/preflight.py ...`, `python3 <skill>/vendor/tools/acima.py ...`, `python3 <skill>/vendor/examples/<lang>/tools/...` |
| A different target repository | the target software only | run ACIMA commands from the checkout or skill directory with `--root`/`--project <target>` |

`preflight --deep` and `acima.py verify` need the full checkout; if it is absent, say so and offer
the read-only assessment that the skill can run. Verify a command's path and `--help` before calling
it executable, and never present a flag you have not confirmed.



## Route the request

Pick one mode from the user's words. If intent is unclear, run the read-only assessment and say so.
Never upgrade an assessment into an adoption because the findings are interesting.

| The user says | Mode | Writes? | First action | Ends when |
|---|---|---|---|---|
| "what is ACIMA", "would it help", "assess", "audit", "review" | **Assess** | no | explain in plain English, then read-only analysis | a verdict, named gaps and limits |
| "adopt", "apply ACIMA", "set it up", "add the gate" | **Adopt** | only after consent | the assessment, then the proposal | an approved scope, implemented and verified |
| "continue", "where are we", "what next" | **Resume** | no | `acima.py status --root .` | one next action, stated plainly |
| "fix this", "why does the gate fail", "correct D001" | **Slice** | smallest named change | `acima.py fix`, then the rule page | one boundary changed, gate re-measured |
| "explain this rule" | **Explain** | no | the rule page, then `acima.py report` | the answer and its remedy |
