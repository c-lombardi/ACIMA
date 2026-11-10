"""Benchmark controller.

Owns the run lifecycle, repository acquisition, isolation, capture, evaluation and reporting. The
agent under test cannot choose the repository, the commit, the skill, the model, the limits or the
mode, and cannot report itself successful.
"""
from __future__ import annotations

import json
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from adapters.base import (
    AdapterFailure,
    AgentExecution,
    AgentInvocation,
    AuthenticationFailure,
    Control,
    READ_ONLY,
    AUTHORIZED_ADOPTION,
    UnsupportedHeadlessExecution,
)
from evaluators import architectural, deterministic as deterministic_evaluator

from . import acquisition as acquisition_module
from .lifecycle import (
    InvalidConfiguration,
    InvalidTransition,
    LifecycleError,
    RunState,
    RunStore,
    is_terminal,
    utcnow,
    write_json_atomic,
)
from .provenance import (
    HARNESS_VERSION,
    SCHEMA_VERSION,
    SKILL_DIR,
    approval_provenance,
    collection_provenance,
    file_manifest,
    instruction_bundle,
    load_config,
    load_json,
    sha256_file,
)
from .sandbox import allowlisted_environment, run_command, select_sandbox
from .schema import SchemaError, validate

TERMINAL_OUTCOME = {
    RunState.FAILED: "failed",
    RunState.TIMED_OUT: "timed-out",
    RunState.CANCELLED: "cancelled",
    RunState.INVALID_CONFIGURATION: "invalid-configuration",
    RunState.INFRASTRUCTURE_FAILURE: "infrastructure-failure",
    RunState.EVALUATION_FAILURE: "evaluation-failure",
}


class BenchmarkController:
    def __init__(self, harness_root: Path | None = None, results_root: Path | None = None, *,
                 limits=None) -> None:
        self.harness_root = Path(harness_root) if harness_root else Path(__file__).resolve().parents[2]
        self.acima_root = self.harness_root.parents[1]
        self.config, configured_limits = load_config(self.harness_root)
        # A controller-side injection point for tests and for a host with a different budget. The
        # adapter still receives a frozen Limits object and cannot change it.
        self.limits = limits or configured_limits
        configured = self.config.get("resultsRoot", "results")
        self.results_root = Path(results_root) if results_root else self.harness_root / configured
        self._scenario_schema = load_json(self.harness_root / "harness" / "schemas" / "scenario.schema.json")

    # ------------------------------------------------------------------ scenarios
    def scenario_manifest(self) -> dict:
        return load_json(self.harness_root / "scenarios" / "manifest.json")

    def scenarios(self) -> list[dict]:
        result = []
        for entry in self.scenario_manifest().get("scenarios", []):
            try:
                result.append(self.load_scenario(entry["id"]))
            except (InvalidConfiguration, SchemaError) as error:
                result.append({"id": entry["id"], "name": entry.get("file", entry["id"]),
                               "category": entry.get("category", "unknown"),
                               "invalid": str(error)})
        return result

    def load_scenario(self, scenario_id: str) -> dict:
        manifest = self.scenario_manifest()
        entry = next((item for item in manifest.get("scenarios", [])
                      if item.get("id") == scenario_id), None)
        if entry is None:
            raise InvalidConfiguration(f"unknown scenario {scenario_id!r}")
        scenario = load_json(self.harness_root / "scenarios" / entry["file"])
        validate(scenario, self._scenario_schema)
        if scenario.get("id") != scenario_id:
            raise InvalidConfiguration(
                f"scenario file {entry['file']} declares id {scenario.get('id')!r}, expected {scenario_id!r}"
            )
        return scenario

    # ------------------------------------------------------------------ run
    def run(self, scenario_id: str, adapter, *, model: str | None = None,
            mode: str | None = None, model_config: dict | None = None,
            approval_path: Path | None = None, keep_worktree: bool = False,
            run_id: str | None = None, scenario: dict | None = None) -> dict:
        scenario = scenario or self.load_scenario(scenario_id)
        validate(scenario, self._scenario_schema)
        if scenario.get("id") != scenario_id:
            raise InvalidConfiguration("scenario id does not match the requested scenario")
        mode = mode or (scenario.get("executionModes") or [READ_ONLY])[0]
        if mode not in scenario.get("executionModes", []):
            raise InvalidConfiguration(
                f"scenario {scenario_id} does not support mode {mode!r}"
            )

        run_id = run_id or self._new_run_id(scenario_id, adapter.name)
        directory = self.results_root / run_id
        if directory.exists():
            raise InvalidConfiguration(f"run directory already exists: {directory}")
        self._assert_concurrency()
        directory.mkdir(parents=True, exist_ok=True)
        store = RunStore(directory, run_id)
        store.create()

        capabilities = {}
        agent_execution = AgentExecution()
        execution: dict = self._base_execution(run_id, scenario, mode, adapter, capabilities)
        evaluation: dict | None = None
        outcome = "failed"
        errors: list[str] = []
        limitations: list[str] = []
        agent_output: dict | None = None
        output_error: str | None = None
        control = None
        cancellation_requested = False

        try:
            approval = approval_provenance(approval_path) if mode == AUTHORIZED_ADOPTION else None
            if mode == AUTHORIZED_ADOPTION and approval is None:
                raise InvalidConfiguration(
                    "authorized-adoption mode requires an explicit approval record (--approval)"
                )
            approved_paths = tuple(approval.get("approvedPaths", [])) if approval else ()
            if mode == AUTHORIZED_ADOPTION and scenario.get("authorizedChanges", {}).get("approvedPaths"):
                for path in scenario["authorizedChanges"]["approvedPaths"]:
                    if not any(path == approved or path.startswith(str(approved).rstrip("/") + "/")
                               for approved in approved_paths):
                        raise InvalidConfiguration(
                            f"scenario-approved path {path!r} is not covered by the approval record"
                        )

            provenance = collection_provenance(self.acima_root)
            provenance["instructions"] = {}
            provenance["approval"] = approval
            execution["provenance"] = {
                "skill": provenance["skill"],
                "standard": provenance["standard"],
                "catalog": provenance["catalog"],
                "harness": provenance["harness"],
                "approval": approval,
                "instructions": {},
            }
            execution["repository"] = {
                "url": scenario["repository"]["url"],
                "commit": scenario["repository"]["commit"],
                "verifiedCommit": None,
                "treeSha256": None,
                "fileCount": None,
                "bytes": None,
                "manifestSha256": None,
            }

            capabilities = adapter.capabilities().as_dict()
            execution["adapter"]["capabilities"] = capabilities
            if not capabilities.get("headless"):
                raise UnsupportedHeadlessExecution(
                    f"{adapter.name} reports no supported unattended invocation"
                )

            workspace = store.ephemeral_directory("run")
            source_dir = workspace / "source"
            working_dir = workspace / "working"
            output_dir = workspace / "out"
            output_dir.mkdir(parents=True, exist_ok=True)

            values = {
                "REPOSITORY": str(working_dir),
                "OUTPUT_DIR": str(output_dir),
                "SKILL_PATH": str(self.acima_root / SKILL_DIR),
                "MODE": mode,
                "APPROVED_CHANGES": (", ".join(approved_paths)
                                     if approved_paths else "none (read-only assessment)"),
            }
            instructions = instruction_bundle(self.harness_root, mode, values)
            execution["provenance"]["instructions"] = {
                "id": instructions["id"], "path": instructions["path"], "sha256": instructions["sha256"],
            }
            (directory / "evidence").mkdir(parents=True, exist_ok=True)
            (directory / "evidence" / "instructions.md").write_text(instructions["text"], encoding="utf-8")

            try:
                acquired = acquisition_module.acquire(
                    scenario["repository"]["url"], scenario["repository"]["commit"], workspace,
                    git_executable=self.config.get("gitExecutable"),
                )
            except acquisition_module.AcquisitionError as error:
                if error.code in ("invalid_url", "invalid_commit", "git_missing"):
                    raise InvalidConfiguration(error.message) from error
                raise
            execution["repository"] = acquired.identity()
            write_json_atomic(directory / "evidence" / "repository.json",
                              {"identity": acquired.identity()})
            write_json_atomic(directory / "evidence" / "files-before.json", acquired.manifest)
            store.transition(RunState.REPOSITORY_PREPARED, {
                "commit": acquired.verified_commit, "files": acquired.file_count,
            })

            sandbox, sandbox_limitations = select_sandbox(
                self.config, self.limits, mode=mode, source_dir=source_dir,
                working_dir=working_dir, output_dir=output_dir,
            )
            execution["sandbox"] = sandbox.describe()
            in_process = bool(capabilities.get("inProcess"))
            execution["sandbox"]["agentIsolated"] = not in_process
            if in_process:
                limitations.append(
                    "the adapter executed inside the controller process: no agent process was "
                    "isolated, and the recorded sandbox did not contain the agent"
                )
            limitations.extend(sandbox_limitations)
            store.transition(RunState.ENVIRONMENT_PROVISIONED, {"backend": sandbox.backend})

            verification: dict = {"commands": []}
            if mode == AUTHORIZED_ADOPTION:
                commands = scenario.get("authorizedChanges", {}).get("verificationCommands", [])
                if commands:
                    verification = self._verify_commands(
                        commands, source_dir, working_dir, sandbox, workspace,
                        store.transition, phase="baseline",
                    )
            execution["verification"] = verification
            if verification.get("commands"):
                limitations.append(
                    "controller-owned verification commands ran in a constrained local process "
                    "against the disposable worktree, not inside the agent sandbox"
                )

            execution["limits"] = self.limits.as_dict()
            deadline = time.monotonic() + self.limits.execution_timeout_seconds
            invocation = AgentInvocation(
                run_id=run_id, scenario_id=scenario_id, mode=mode,
                model=model or (capabilities.get("models") or ["unspecified"])[0],
                model_config=model_config,
                repository_dir=working_dir, output_dir=output_dir,
                skill_dir=self.acima_root / SKILL_DIR, instructions=instructions["text"],
                limits=self.limits, approved_paths=approved_paths, deadline=deadline,
            )
            execution["adapter"]["model"] = invocation.model
            execution["adapter"]["modelConfig"] = model_config
            control = Control(invocation, directory / "evidence" / "events.jsonl",
                              self.limits.max_captured_bytes)
            store.transition(RunState.AGENT_EXECUTING, {
                "provider": adapter.name, "model": invocation.model, "mode": mode,
            })
            try:
                agent_execution = adapter.execute(invocation, control)
            except (UnsupportedHeadlessExecution, AuthenticationFailure) as error:
                agent_execution = AgentExecution(
                    status="unsupported" if isinstance(error, UnsupportedHeadlessExecution) else "unauthenticated",
                    errors=[str(error)],
                    termination_reason=getattr(error, "code", type(error).__name__),
                )
            except AdapterFailure as error:
                agent_execution = AgentExecution(
                    status="failed", errors=[str(error)], termination_reason=type(error).__name__
                )
            except KeyboardInterrupt:
                control.cancel()
                cancellation_requested = True
                agent_execution = AgentExecution(
                    status="cancelled", errors=["cancelled by the operator"],
                    termination_reason="operator-cancelled",
                )

            if control.expired and agent_execution.status == "completed":
                agent_execution.status = "timed_out"
                agent_execution.termination_reason = "execution deadline reached"
            if control.cancelled and agent_execution.status == "completed":
                agent_execution.status = "cancelled"
                agent_execution.termination_reason = "cancelled by controller"
            execution["agent"] = agent_execution.as_record()
            if agent_execution.status in ("unsupported", "unauthenticated", "not_run"):
                # Nothing executed, so no isolation guarantee can be claimed for this run.
                execution["sandbox"]["agentIsolated"] = None
                limitations.append(
                    "no agent process executed, so the recorded sandbox isolated nothing"
                )
            if control.truncated:
                limitations.append("event capture was truncated at the configured byte limit")

            # Capture is attempted for every terminal agent status, including failure.
            output_path = output_dir / "agent-output.json"
            if output_path.is_file():
                try:
                    agent_output = json.loads(output_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError as error:
                    output_error = f"agent-output.json is not valid JSON: {error}"
                (directory / "evidence" / "agent-output.json").write_text(
                    output_path.read_text(encoding="utf-8", errors="replace"), encoding="utf-8"
                )
            else:
                output_error = "agent-output.json was not produced"

            if mode == AUTHORIZED_ADOPTION:
                commands = scenario.get("authorizedChanges", {}).get("verificationCommands", [])
                if commands:
                    after = self._verify_commands(
                        commands, source_dir, working_dir, sandbox, workspace,
                        store.transition, phase="after",
                    )
                    execution["verification"] = self._merge_verification(
                        execution.get("verification") or {"commands": []}, after
                    )

            manifest_after = file_manifest(working_dir)
            write_json_atomic(directory / "evidence" / "files-after.json", manifest_after)
            changes = acquisition_module.diff_manifests(acquired.manifest, manifest_after)
            changed = sorted(set(changes["added"]) | set(changes["removed"]) | set(changes["modified"]))
            unauthorized = [path for path in changed
                            if mode == AUTHORIZED_ADOPTION and not self._approved(path, approved_paths)]
            changes["unauthorized"] = unauthorized
            changes["worktreeRetained"] = keep_worktree
            write_json_atomic(directory / "evidence" / "changes.json", changes)
            execution["changes"] = changes

            source_verified = acquisition_module.verify(acquired)
            execution["artifacts"] = {
                "evidence": "evidence",
                "agentOutput": "evidence/agent-output.json" if agent_output is not None or output_error else None,
                "filesBefore": "evidence/files-before.json",
                "filesAfter": "evidence/files-after.json",
                "instructions": "evidence/instructions.md",
                "events": "evidence/events.jsonl",
                "worktree": "workspace/working" if keep_worktree else None,
            }
            store.transition(RunState.EXECUTION_CAPTURED, {
                "changes": len(changed), "output": agent_output is not None,
            })

            store.transition(RunState.EVALUATION_PENDING, {})
            store.transition(RunState.EVALUATING, {})
            execution["status"] = RunState.EVALUATING.value
            context = {
                "scenario": scenario,
                "execution": {**execution, "limits": self.limits.as_dict()},
                "agent_output": agent_output,
                "output_error": output_error,
                "changes": changes,
                "catalog_rule_ids": self._catalog_rule_ids(),
                "file_manifest": acquired.manifest,
                "final_state_captured": True,
                "source_verified": source_verified,
            }
            deterministic = deterministic_evaluator.evaluate(context)
            evaluation = architectural.evaluate(
                scenario=scenario, agent_output=agent_output,
                execution={**execution, "changes": changes},
                deterministic=deterministic, changes=changes,
                file_manifest=acquired.manifest,
            )
            evaluation["deterministic"] = deterministic
            evaluation["schemaVersion"] = SCHEMA_VERSION
            evaluation["runId"] = run_id
            evaluation["scenarioId"] = scenario_id
            evaluation["file_manifest_size"] = len(acquired.manifest)
            evaluation["evaluator"] = {
                "name": "acima-ai-adoption-ground-truth",
                "kind": "ground-truth-comparison",
                "version": architectural.EVALUATOR_VERSION,
                "notes": "Deterministic checks plus comparison against evidence established before the run. "
                         "No model review was used; no evaluator output is a deterministic proof of architecture.",
            }

            status = RunState.COMPLETED
            if agent_execution.status == "timed_out":
                status = RunState.TIMED_OUT
            elif agent_execution.status == "cancelled":
                status = RunState.CANCELLED
            elif agent_execution.status in ("failed", "unsupported", "unauthenticated"):
                status = RunState.FAILED
            if not deterministic["passed"] and status == RunState.COMPLETED and unauthorized:
                status = RunState.COMPLETED  # a scope violation is an evaluated result, not a pipeline failure
            store.transition(status, {"deterministicPassed": deterministic["passed"]})
            outcome = self._outcome(status, deterministic, unauthorized, mode)
        except SchemaError as error:
            errors.append(f"scenario failed schema validation: {error}")
            outcome = "invalid-configuration"
            store.transition(RunState.INVALID_CONFIGURATION, {"reason": str(error)})
        except UnsupportedHeadlessExecution as error:
            errors.append(str(error))
            outcome = "unsupported-execution"
            try:
                store.transition(RunState.INVALID_CONFIGURATION,
                                 {"reason": "unsupported-headless-execution"})
            except InvalidTransition:
                pass
        except InvalidConfiguration as error:
            errors.append(str(error))
            outcome = "invalid-configuration"
            try:
                store.transition(RunState.INVALID_CONFIGURATION, {"reason": str(error)})
            except InvalidTransition:
                pass
        except LifecycleError as error:
            errors.append(str(error))
            outcome = "infrastructure-failure"
            try:
                store.transition(RunState.INFRASTRUCTURE_FAILURE, {"reason": str(error)})
            except InvalidTransition:
                pass
        except acquisition_module.AcquisitionError as error:
            errors.append(str(error))
            outcome = "infrastructure-failure"
            try:
                store.transition(RunState.INFRASTRUCTURE_FAILURE, {"reason": error.code})
            except InvalidTransition:
                pass
        except Exception as error:  # an infrastructure failure must be recorded, not raised into silence
            errors.append(f"{type(error).__name__}: {error}")
            outcome = "infrastructure-failure"
            try:
                store.transition(RunState.INFRASTRUCTURE_FAILURE, {"reason": type(error).__name__})
            except InvalidTransition:
                pass

        limitations = list(dict.fromkeys(limitations))
        state = store.read()
        execution["status"] = state["state"]
        execution["stateHistory"] = state["stateHistory"]
        execution["finishedAt"] = state.get("finishedAt")
        execution["errors"] = errors
        execution["limitations"] = limitations
        if evaluation is None:
            evaluation = self._degraded_evaluation(
                run_id, scenario_id, execution, errors or [state.get("reason") or "run did not reach evaluation"],
            )
        success = (
            state["state"] == RunState.COMPLETED.value
            and evaluation["deterministic"]["passed"]
            and execution.get("agent", {}).get("status") == "completed"
        )
        execution["success"] = success
        if outcome == "agent-assessed" and not success:
            outcome = "incomplete-execution"

        result = {
            "schemaVersion": SCHEMA_VERSION,
            "harnessVersion": HARNESS_VERSION,
            "runId": run_id,
            "scenarioId": scenario_id,
            "scenarioName": scenario.get("name"),
            "outcome": outcome,
            "success": success,
            "execution": execution,
            "evaluation": evaluation,
            "metrics": evaluation["metrics"],
            "errors": errors,
            "limitations": limitations + evaluation["limitations"],
            "artifacts": {
                "execution": "execution.json",
                "evaluation": "evaluation.json",
                "report": "report.md",
                "evidence": "evidence",
            },
        }
        write_json_atomic(directory / "execution.json", execution)
        write_json_atomic(directory / "evaluation.json", evaluation)
        from .reporting import render_markdown
        (directory / "report.md").write_text(render_markdown(result, scenario, directory), encoding="utf-8")
        write_json_atomic(directory / "result.json", result)

        if not keep_worktree:
            acquisition_module.remove_tree(directory / "workspace")
        return result

    # ------------------------------------------------------------------ helpers
    def _catalog_rule_ids(self) -> set[str]:
        catalog = load_json(self.acima_root / "tools" / "acima-spec" / "rules.json")
        return {rule["id"] for rule in catalog.get("rules", [])}

    def _new_run_id(self, scenario_id: str, adapter: str) -> str:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return f"{stamp}-{scenario_id}-{adapter}-{uuid.uuid4().hex[:6]}"

    def _assert_concurrency(self) -> None:
        limit = self.limits.max_concurrent_runs
        active = 0
        if self.results_root.is_dir():
            for state_path in self.results_root.glob("*/state.json"):
                try:
                    state = json.loads(state_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                try:
                    terminal = is_terminal(state.get("state", "Failed"))
                except ValueError:
                    terminal = False
                if not terminal:
                    active += 1
        if active >= limit:
            raise InvalidConfiguration(
                f"maxConcurrentRuns is {limit}; {active} run(s) are still not terminal"
            )

    @staticmethod
    def _approved(path: str, approved_paths: tuple[str, ...]) -> bool:
        for approved in approved_paths:
            approved = str(approved).rstrip("/")
            if path == approved or path.startswith(approved + "/"):
                return True
        return False

    def _base_execution(self, run_id: str, scenario: dict, mode: str, adapter,
                        capabilities: dict) -> dict:
        now = utcnow()
        return {
            "schemaVersion": SCHEMA_VERSION,
            "runId": run_id,
            "scenarioId": scenario["id"],
            "mode": mode,
            "status": RunState.PENDING.value,
            "startedAt": now,
            "updatedAt": now,
            "finishedAt": None,
            "provenance": {
                "skill": {"name": "acima-adoption", "version": "", "contentSha256": ""},
                "standard": {"version": ""},
                "catalog": {"version": "", "sha256": "", "rules": 0},
                "instructions": {"id": "", "sha256": ""},
                "harness": {"version": HARNESS_VERSION},
                "approval": None,
            },
            "adapter": {
                "provider": adapter.name,
                "model": "unspecified",
                "modelConfig": None,
                "capabilities": capabilities,
            },
            "limits": self.limits.as_dict(),
            "repository": {
                "url": scenario["repository"]["url"],
                "commit": scenario["repository"]["commit"],
                "verifiedCommit": None,
                "treeSha256": None,
                "fileCount": None,
                "bytes": None,
                "manifestSha256": None,
            },
            "sandbox": {"backend": "not-selected", "enforced": [], "notEnforced": [], "network": "unknown"},
            "agent": {"status": "not_run", "exitCode": None, "durationSeconds": None, "messages": [],
                      "toolCalls": [], "commands": [], "filesRead": [], "filesModified": [],
                      "tests": [], "tokenUsage": None, "errors": [], "terminationReason": None},
            "changes": {"added": [], "removed": [], "modified": [], "unauthorized": [],
                        "worktreeRetained": False},
            "stateHistory": [],
            "verification": {"commands": []},
            "artifacts": {},
            "success": False,
            "errors": [],
            "limitations": [],
        }

    @staticmethod
    def _merge_verification(baseline: dict, after: dict) -> dict:
        by_name = {command["name"]: command for command in baseline.get("commands", [])}
        merged = []
        for command in after.get("commands", []):
            entry = dict(command)
            baseline_entry = by_name.get(command["name"])
            entry["baselinePassed"] = baseline_entry["passed"] if baseline_entry else None
            if baseline_entry:
                entry["regression"] = bool(baseline_entry["passed"] and not command["passed"])
            merged.append(entry)
        merged_result = dict(after)
        merged_result["commands"] = merged
        return merged_result

    def _verify_commands(self, commands: list[dict], baseline_dir: Path, working_dir: Path,
                         sandbox, workspace: Path, transition, *, phase: str) -> dict:
        results = []
        for command in commands:
            argv = [str(part) for part in command.get("argv") or []]
            if not argv:
                continue
            target = baseline_dir if phase == "baseline" else working_dir
            outcome = run_command(argv, cwd=target, env=allowlisted_environment(),
                                  timeout=min(300, self.limits.execution_timeout_seconds),
                                  max_output_bytes=self.limits.max_output_bytes)
            results.append({
                "name": command.get("name", " ".join(argv)),
                "argv": argv,
                "phase": phase,
                "exitCode": outcome.returncode,
                "passed": outcome.ok,
                "durationSeconds": round(outcome.duration_seconds, 3),
                "stdoutTail": outcome.stdout[-1000:],
                "stderrTail": outcome.stderr[-1000:],
                "timedOut": outcome.timed_out,
            })
        return {"commands": results}

    def _degraded_evaluation(self, run_id: str, scenario_id: str, execution: dict,
                             reasons: list[str]) -> dict:
        return {
            "schemaVersion": SCHEMA_VERSION,
            "runId": run_id,
            "scenarioId": scenario_id,
            "evaluator": {
                "name": "acima-ai-adoption-ground-truth",
                "kind": "deterministic-checks",
                "version": architectural.EVALUATOR_VERSION,
                "notes": "The run did not reach independent evaluation. No success is inferred.",
            },
            "deterministic": {
                "checks": [{
                    "id": "D00",
                    "description": "The run reached the evaluation stage",
                    "status": "fail",
                    "detail": "; ".join(reasons) or "evaluation did not run",
                }],
                "passed": False,
            },
            "criteria": [{
                "id": "evaluation", "description": "Execution was evaluated independently",
                "status": "fail", "detail": "; ".join(reasons) or "evaluation did not run",
                "evidence": [],
            }],
            "metrics": [
                {
                    "id": identifier, "name": name, "value": None, "status": "unavailable",
                    "unit": "ratio", "detail": "the run did not reach evaluation",
                    "interpretation": architectural.INTERPRETATIONS[identifier],
                }
                for identifier, name in architectural.METRIC_NAMES.items()
            ],
            "indeterminate": ["every metric: the run did not reach independent evaluation"],
            "humanReview": {"required": True, "reason": "the run failed before evaluation",
                            "reviewedBy": None, "reviewedOn": None, "notes": None},
            "limitations": ["A failed or invalid run is never reported as a completed assessment."],
        }

    @staticmethod
    def _outcome(status: RunState, deterministic: dict | None, unauthorized: list[str], mode: str) -> str:
        if status in TERMINAL_OUTCOME:
            return TERMINAL_OUTCOME[status]
        if unauthorized and mode == AUTHORIZED_ADOPTION:
            return "agent-scope-violation"
        if mode == READ_ONLY and deterministic and not deterministic["passed"]:
            changes = deterministic.get("checks", [])
            scope = next((check for check in changes if check["id"] == "D07"), None)
            if scope and scope["status"] == "fail":
                return "agent-scope-violation"
            return "incomplete-execution"
        return "agent-assessed"
