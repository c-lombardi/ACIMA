#!/usr/bin/env python3
"""Command line for the AI adoption effectiveness benchmark.

    python benchmarks/ai-adoption/harness/runner/cli.py list
    python benchmarks/ai-adoption/harness/runner/cli.py validate
    python benchmarks/ai-adoption/harness/runner/cli.py run --scenario library-python-httpx \\
        --adapter fake --script path/to/script.json
    python benchmarks/ai-adoption/harness/runner/cli.py run --scenario library-python-httpx --adapter freebuff
    python benchmarks/ai-adoption/harness/runner/cli.py report --run <run-id-or-path>
    python benchmarks/ai-adoption/harness/runner/cli.py compare --scenario library-python-httpx
    python benchmarks/ai-adoption/harness/runner/cli.py capabilities --adapter freebuff

Exit codes: 0 verified, 1 the run completed but the pipeline or scope check failed, 2 invalid
configuration or a tool failure.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HARNESS_ROOT = Path(__file__).resolve().parents[2]
HARNESS_CODE = HARNESS_ROOT / "harness"
if str(HARNESS_CODE) not in sys.path:
    sys.path.insert(0, str(HARNESS_CODE))

from adapters.fake import FakeAdapter  # noqa: E402
from adapters.freebuff import FreebuffAdapter  # noqa: E402
from runner.controller import BenchmarkController  # noqa: E402
from runner.lifecycle import InvalidConfiguration, LifecycleError  # noqa: E402
from runner.provenance import load_config  # noqa: E402
from runner.reporting import compare, load_results, render_comparison  # noqa: E402
from runner.schema import SchemaError, validate  # noqa: E402


def _adapter(name: str, script: Path | None, model: str | None):
    if name == "fake":
        return FakeAdapter(script_path=script, model=model)
    if name == "freebuff":
        config, _limits = load_config(HARNESS_ROOT)
        return FreebuffAdapter((config.get("adapters", {}).get("freebuff") or {}).get("command", "freebuff"))
    raise InvalidConfiguration(f"unknown adapter {name!r}")


def _print_result(result: dict) -> None:
    execution = result["execution"]
    print(f"run        {result['runId']}")
    print(f"scenario   {result['scenarioId']} ({execution['mode']})")
    print(f"outcome    {result['outcome']}  pipeline success: {str(result['success']).lower()}")
    print(f"agent      {execution['adapter']['provider']}/{execution['adapter']['model']} "
          f"({execution['agent']['status']})")
    print(f"repository {execution['repository']['url']} @ {execution['repository']['commit']}")
    checks = result["evaluation"]["deterministic"]["checks"]
    failed = [check for check in checks if check["status"] == "fail"]
    print(f"checks     {len(checks) - len(failed)}/{len(checks)} passed")
    for check in failed:
        print(f"  FAIL {check['id']} {check['description']}: {check['detail']}")
    print("metrics    " + ", ".join(
        f"{metric['id']}={metric['value'] if metric['value'] is not None else metric['status']}"
        for metric in result["metrics"][:6]
    ))
    if result["errors"]:
        for error in result["errors"]:
            print(f"error      {error}")
    report = Path(result["_directory"]) / "report.md"
    if report.is_file():
        print(f"report     {report}")
        print(f"record     {Path(result['_directory']) / 'result.json'}")


def command_list(args) -> int:
    controller = BenchmarkController(results_root=Path(args.results_root) if args.results_root else None)
    manifest = controller.scenario_manifest()
    print("Scenarios")
    for entry in manifest.get("scenarios", []):
        print(f"  {entry['id']:<58} {entry['category']:<18} {entry['status']}")
    planned = manifest.get("plannedCategories") or []
    if planned:
        print("\nPlanned (not implemented)")
        for entry in planned:
            print(f"  {entry['category']:<58} {entry['status']}")
    print("\nExecution modes: read-only (default), authorized-adoption (requires --approval)")
    return 0


def command_validate(args) -> int:
    controller = BenchmarkController(results_root=Path(args.results_root) if args.results_root else None)
    schema = json.loads((HARNESS_CODE / "schemas" / "scenario.schema.json").read_text(encoding="utf-8"))
    failures = 0
    for entry in controller.scenario_manifest().get("scenarios", []):
        try:
            scenario = controller.load_scenario(entry["id"])
            validate(scenario, schema)
            print(f"ok    {entry['id']:<58} {len(scenario['expectedBoundaries'])} boundaries, "
                  f"{len(scenario['expectedObservations'])} observations")
        except (InvalidConfiguration, SchemaError) as error:
            failures += 1
            print(f"fail  {entry['id']}: {error}")
    for schema_path in sorted((HARNESS_CODE / "schemas").glob("*.schema.json")):
        try:
            json.loads(schema_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            failures += 1
            print(f"fail  {schema_path.name}: {error}")
    return 2 if failures else 0


def command_run(args) -> int:
    controller = BenchmarkController(results_root=Path(args.results_root) if args.results_root else None)
    script = Path(args.script) if args.script else None
    model_config = json.loads(args.model_config) if args.model_config else None
    adapter = _adapter(args.adapter, script, args.model)
    status = 0
    for index in range(args.repeat):
        try:
            result = controller.run(
                args.scenario, adapter, model=args.model, mode=args.mode,
                model_config=model_config,
                approval_path=Path(args.approval) if args.approval else None,
                keep_worktree=args.keep_worktree,
            )
        except (InvalidConfiguration, SchemaError) as error:
            print(f"acima benchmark: {error}", file=sys.stderr)
            return 2
        except LifecycleError as error:
            print(f"acima benchmark: run could not continue: {error}", file=sys.stderr)
            return 2
        result["_directory"] = str(controller.results_root / result["runId"])
        if args.repeat > 1:
            print(f"\n--- run {index + 1}/{args.repeat} ---")
        _print_result(result)
        if not result["success"]:
            status = 1
    return status


def _resolve_run(controller: BenchmarkController, value: str) -> Path:
    candidate = Path(value)
    if candidate.is_dir():
        return candidate
    directory = controller.results_root / value
    if directory.is_dir():
        return directory
    raise InvalidConfiguration(f"no run directory at {value!r}")


def command_report(args) -> int:
    controller = BenchmarkController(results_root=Path(args.results_root) if args.results_root else None)
    directory = _resolve_run(controller, args.run)
    result_path = directory / "result.json"
    if not result_path.is_file():
        print(f"acima benchmark: no result.json in {directory}", file=sys.stderr)
        return 2
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["_directory"] = str(directory)
    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print((directory / "report.md").read_text(encoding="utf-8"))
    return 0 if result.get("success") else 1


def command_compare(args) -> int:
    controller = BenchmarkController(results_root=Path(args.results_root) if args.results_root else None)
    results = load_results(controller.results_root, scenario=args.scenario)
    comparison = compare(results)
    if args.format == "json":
        print(json.dumps(comparison, indent=2, sort_keys=True))
    else:
        print(render_comparison(comparison))
    return 0 if comparison["groups"] else 1


def command_capabilities(args) -> int:
    if args.adapter == "freebuff":
        capabilities = FreebuffAdapter().capabilities()
    elif args.adapter == "fake":
        capabilities = FakeAdapter().capabilities()
    else:
        raise InvalidConfiguration(f"unknown adapter {args.adapter!r}")
    print(json.dumps(capabilities.as_dict(), indent=2, sort_keys=True))
    return 0


def command_portfolio(args) -> int:
    from runner import portfolio as portfolio_module

    action = args.action
    if action in ("build", "all"):
        written = portfolio_module.write_references(HARNESS_ROOT, args.experiment)
        print(f"references  {len(written)} written")
    summary = None
    if action in ("prepare", "all"):
        summary = portfolio_module.prepare(HARNESS_ROOT, args.experiment,
                                           only=args.repository or None)
        print(f"prepared    {summary['verified']}/{summary['expected']} verified")
        for record in summary["repositories"]:
            if record.get("status") != "verified":
                error = (record.get("error") or {}).get("code", record.get("status"))
                print(f"  FAIL {record['id']}: {error}")
    if action in ("freeze", "all"):
        frozen = portfolio_module.freeze(HARNESS_ROOT, args.experiment, force=args.force)
        print(f"frozen      rubric {frozen['rubric']['sha256'][:12]} "
              f"references {frozen['referencesCombinedSha256'][:12]}")
    if action == "status":
        print(json.dumps(portfolio_module.status(HARNESS_ROOT, args.experiment),
                         indent=2, sort_keys=True))
    if action in ("report", "all"):
        directory = portfolio_module.experiment_directory(HARNESS_ROOT, args.experiment)
        path = directory / "report.md"
        path.write_text(portfolio_module.render_report(HARNESS_ROOT, args.experiment),
                        encoding="utf-8")
        print(f"report      {path}")
    return 1 if summary and summary["failed"] else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ACIMA AI adoption effectiveness benchmark")
    parser.add_argument("--results-root", default=None, help="override the results directory")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="list scenarios and their status")

    validate_parser = subparsers.add_parser("validate", help="validate every scenario against its schema")
    validate_parser.set_defaults(handler=command_validate)

    run_parser = subparsers.add_parser("run", help="execute one scenario")
    run_parser.add_argument("--scenario", required=True)
    run_parser.add_argument("--adapter", default="fake", choices=["fake", "freebuff"])
    run_parser.add_argument("--model", default=None)
    run_parser.add_argument("--model-config", default=None, help="JSON object recorded with the run")
    run_parser.add_argument("--mode", default=None, choices=["read-only", "authorized-adoption"])
    run_parser.add_argument("--script", default=None, help="fake adapter script (JSON)")
    run_parser.add_argument("--approval", default=None, help="approval record for authorized-adoption")
    run_parser.add_argument("--keep-worktree", action="store_true")
    run_parser.add_argument("--repeat", type=int, default=1)
    run_parser.set_defaults(handler=command_run)

    report_parser = subparsers.add_parser("report", help="print a saved run report")
    report_parser.add_argument("--run", required=True)
    report_parser.add_argument("--format", default="markdown", choices=["markdown", "json"])
    report_parser.set_defaults(handler=command_report)

    compare_parser = subparsers.add_parser("compare", help="compare saved runs of one scenario")
    compare_parser.add_argument("--scenario", default=None)
    compare_parser.add_argument("--format", default="markdown", choices=["markdown", "json"])
    compare_parser.set_defaults(handler=command_compare)

    capabilities_parser = subparsers.add_parser("capabilities", help="print adapter capabilities")
    capabilities_parser.add_argument("--adapter", default="freebuff", choices=["fake", "freebuff"])
    capabilities_parser.set_defaults(handler=command_capabilities)

    portfolio_parser = subparsers.add_parser(
        "portfolio", help="portfolio experiment: build references, prepare pins, freeze, report"
    )
    portfolio_parser.add_argument("--experiment", default=None)
    portfolio_parser.add_argument("--action", default="status",
                                  choices=["build", "prepare", "freeze", "report", "status", "all"])
    portfolio_parser.add_argument("--repository", action="append", default=None,
                                  help="prepare only these repository ids")
    portfolio_parser.add_argument("--force", action="store_true",
                                  help="re-freeze before any execution (recorded as corrected)")
    portfolio_parser.set_defaults(handler=command_portfolio)

    subparsers.choices["list"].set_defaults(handler=command_list)
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except InvalidConfiguration as error:
        print(f"acima benchmark: {error}", file=sys.stderr)
        return 2
    except SchemaError as error:
        print(f"acima benchmark: invalid scenario: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
