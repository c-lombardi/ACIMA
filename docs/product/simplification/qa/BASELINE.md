# Baseline

Captured before integration testing for the simplification and adoption-workflow program.

## Repository

- Repository: `G:\Code Repository\ACIMA`
- Branch: `main`
- Starting commit: `1236b37` — `Make adoption reports reconcile assessment evidence`
- Remote state: not inspected or changed; no commits, pushes, branch operations, deployments or releases were performed.

## Starting working tree

The tree was intentionally dirty. Existing uncommitted work was treated as intentional and preserved.

- 32 tracked files were already modified.
- `docs/product/` was already untracked and contained the orchestration and workstream briefs.
- `git diff --check` was clean at baseline.

### Pre-existing WS-05 enforcement changes

These six files were already modified before this program and were preserved:

- `conformance/test_value_ownership.py`
- `conformance/test_waiver_fingerprints.py`
- `examples/dotnet/tools/Acima.ArchTests/Program.cs`
- `examples/go/tools/archtest/main.go`
- `examples/python/tools/acima_arch.py`
- `examples/typescript/tools/acima-arch.mjs`

Their changes covered full 64-hex finding fingerprints, .NET repository-namespace handling, .NET internal-type identity, and case-insensitive .NET infrastructure-path matching.

### Additional partial changes observed

The baseline also contained partial phase work that this program completed rather than replaced:

- Phase fields and projection scaffolding in `conformance/adoption_workflow.py`, `conformance/adoption_reports.py`, `skills/acima-adoption/scripts/render_report.py` and `tools/acima.py`.
- Canonical-journey copy in `README.md`, `PRODUCT.md`, `docs/commands.md`, `docs/start/quickstart.md`, `skills/acima-adoption/SKILL.md` and skill references.
- Phase labels and schema fields in `skills/acima-adoption/assets/report.schema.json`.
- Skill version `1.35.0` in `skills/acima-adoption/manifest.json`.
- A canonical phase test update in `conformance/test_consent_workflow.py`.
- Generated vendor mirrors under `skills/acima-adoption/vendor/`.

The partial work contained literal `?` separators instead of em dashes, no `review_and_authorize` stage mapping, stale six-phase brownfield guidance, and report schema fields that were present but not required.

## Tooling environment

| Tool | Observation |
|---|---|
| OS | Windows, Git Bash shell |
| Python | `py -3` → Python 3.15.2 |
| .NET | `dotnet` → 11.0.100-rc.3.26522.148 |
| Node | `node` → v26.13.0 |
| Go | `go` → go1.27.3 windows/amd64 |
| Test runner | `py -3 -m unittest` for unittest modules; `conformance/run.py tools` for pytest-style consent checks |

The bare `python` command resolves to a WSL/Docker Python without host `git` or `dotnet`; all host-toolchain checks use `py -3`.

## Verification constraint

Independent subagent workspaces sharing this repository would also share its working tree. No isolated concurrent writers were available, so analysis was performed in parallel where possible and implementation was serialized. No result in this program claims parallel writing.
