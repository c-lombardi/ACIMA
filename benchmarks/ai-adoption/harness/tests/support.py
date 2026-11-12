"""Shared fixtures for the benchmark's own tests.

Every fixture is local: a temporary git repository, a scripted adapter, no network and no model.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

HARNESS_ROOT = Path(__file__).resolve().parents[2]
HARNESS_CODE = HARNESS_ROOT / "harness"
if str(HARNESS_CODE) not in sys.path:
    sys.path.insert(0, str(HARNESS_CODE))

from adapters.base import AgentInvocation  # noqa: E402
from runner.provenance import load_config  # noqa: E402

GIT_ENV = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0"}

FIXTURE_FILES = {
    "README.md": "# orders fixture\n\nA small two-module fixture repository.\n",
    "src/orders/service.py": "def place_order():\n    return 'placed'\n",
    "src/orders/api.py": "from src.billing.service import charge\n\n\ndef place():\n    return charge()\n",
    "src/billing/service.py": "def charge():\n    return 'charged'\n",
}


def git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True,
                            env=GIT_ENV)
    if result.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {result.stderr}")
    return result.stdout.strip()


def make_repository(root: Path, files: dict[str, str] | None = None) -> tuple[Path, str]:
    files = files or FIXTURE_FILES
    root.mkdir(parents=True, exist_ok=True)
    git(["init", "--quiet"], root)
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    git(["add", "-A"], root)
    git(["-c", "user.email=benchmark@example.invalid", "-c", "user.name=Benchmark",
         "commit", "--quiet", "-m", "fixture"], root)
    return root, git(["rev-parse", "HEAD"], root)


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def scenario_stub(root: Path, commit: str, **overrides) -> dict:
    scenario = {
        "schemaVersion": 1,
        "id": "fixture-orders",
        "name": "Fixture orders repository",
        "description": "A two-unit Python fixture used to verify the benchmark pipeline deterministically.",
        "category": "modular-monolith",
        "repository": {"url": root.as_uri(), "commit": commit, "license": "test-fixture"},
        "softwareCategory": "Fixture application",
        "architectureFamily": "Two feature modules",
        "expectedCharacteristics": ["orders unit", "billing unit"],
        "applicableProfiles": ["base"],
        "executionModes": ["read-only", "authorized-adoption"],
        "expectedBoundaries": [
            {"id": "orders", "module": "orders", "evidencePaths": ["src/orders"], "required": True,
             "confidence": "high", "rationale": "order use cases"},
            {"id": "billing", "module": "billing", "evidencePaths": ["src/billing"], "required": True,
             "confidence": "high", "rationale": "billing use cases"},
        ],
        "expectedObservations": [
            {"id": "O1", "type": "applicability",
             "statement": "There is no ACIMA unit map in the fixture.",
             "evidence": ["README.md"], "required": True, "keywords": ["unit map"]},
        ],
        "expectedFindings": [
            {"id": "F1", "rule": "ACIMA-D001", "path": "src/orders/api.py",
             "kind": "confirmed-violation", "rationale": "orders imports billing's implementation"},
        ],
        "acceptableCompatibility": ["compatible-with-adaptation"],
        "acceptableRecommendations": ["RECOMMENDED_WITH_LIMITATIONS"],
        "expectedProposedChangeKinds": ["config", "tooling"],
        "knownLimitations": ["Fixture repository; ground truth is exact and authored for this test."],
        "groundTruth": {"establishedBy": "test", "establishedOn": "2026-11-10",
                        "method": "authored fixture with a known violation",
                        "blind": False, "independentReview": False},
    }
    if overrides:
        scenario.update(overrides)
    return scenario


GOOD_OUTPUT = {
    "schemaVersion": 1,
    "mode": "read-only",
    "summary": "Two feature units with one cross-module import. There is no ACIMA unit map yet.",
    "application": {
        "purpose": "order placement fixture", "languages": ["python"], "frameworks": [],
        "entryPoints": ["src/orders/api.py"], "existingEnforcement": [],
    },
    "boundaries": [
        {"module": "orders", "units": ["src/orders"],
         "evidence": [{"path": "src/orders/service.py", "note": "order use cases"}], "confidence": "high"},
        {"module": "billing", "units": ["src/billing"],
         "evidence": [{"path": "src/billing/service.py", "note": "billing use cases"}], "confidence": "high"},
    ],
    "profiles": ["base"],
    "compatibility": "compatible-with-adaptation",
    "findings": [{
        "rule": "ACIMA-D001", "path": "src/orders/api.py", "line": 1,
        "classification": "confirmed-violation", "evidence": ["src/orders/api.py:1"],
        "rationale": "orders imports billing's implementation directly",
    }],
    "recommendation": "RECOMMENDED_WITH_LIMITATIONS",
    "uncertainties": ["No ACIMA unit map exists yet, so the boundary map is a proposal."],
    "commandsRun": [],
    "testsRun": [],
    "proposedChanges": [
        {"kind": "config", "path": "acima.config.json", "purpose": "declare units", "required": True}
    ],
    "changesMade": [],
}


def script(output: dict | None = None, **overrides) -> dict:
    payload = {
        "model": "fake-scripted-1",
        "behavior": "complete",
        "events": [{"type": "message", "role": "assistant", "text": "inspecting the repository"}],
        "toolCalls": [{"name": "read", "command": [], "arguments": {"path": "src/orders/api.py"}}],
        "filesRead": ["src/orders/api.py"],
        "commands": [],
        "tests": [],
        "tokenUsage": {"input": 100, "output": 50},
        "output": output,
        "writeFiles": {},
        "messages": [{"role": "assistant", "text": "assessment complete"}],
    }
    payload.update(overrides)
    return payload


def approval(path: Path, paths: list[str]) -> Path:
    return write_json(path, {
        "version": 1, "approvedBy": "repository-owner", "approvedOn": "2026-11-10",
        "proposal": "docs/acima/adoption-proposal.md", "paths": paths, "level": "L1",
    })


def invocation(tmp_path: Path, *, mode: str = "read-only", approved: tuple[str, ...] = (),
               timeout: float = 10.0) -> AgentInvocation:
    repository = tmp_path / "repo"
    repository.mkdir(parents=True, exist_ok=True)
    output = tmp_path / "out"
    output.mkdir(parents=True, exist_ok=True)
    _config, limits = load_config(HARNESS_ROOT)
    return AgentInvocation(
        run_id="fixture-run", scenario_id="fixture-orders", mode=mode, model="fake-scripted-1",
        model_config=None, repository_dir=repository, output_dir=output,
        skill_dir=HARNESS_ROOT.parents[1] / "skills" / "acima-adoption",
        instructions="fixture instructions", limits=limits, approved_paths=approved,
        deadline=time.monotonic() + timeout,
    )


def execution_stub(*, mode: str = "read-only", duration: float = 1.0) -> dict:
    _config, limits = load_config(HARNESS_ROOT)
    return {
        "schemaVersion": 1,
        "runId": "fixture-run",
        "scenarioId": "fixture-orders",
        "mode": mode,
        "status": "Completed",
        "startedAt": "2026-11-10T10:00:00Z",
        "updatedAt": "2026-11-10T10:00:01Z",
        "finishedAt": "2026-11-10T10:00:01Z",
        "provenance": {
            "skill": {"name": "acima-adoption", "version": "1.18.0", "contentSha256": "a" * 64},
            "standard": {"version": "1.9.0-draft.1"},
            "catalog": {"version": "1.9.0-draft.1", "sha256": "b" * 64, "rules": 56, "portable": 42},
            "instructions": {"id": "read-only-assessment.md", "sha256": "c" * 64},
            "harness": {"version": "test"},
            "approval": None,
        },
        "adapter": {"provider": "fake", "model": "fake-scripted-1", "modelConfig": None,
                    "capabilities": {}},
        "limits": limits.as_dict(),
        "repository": {"url": "file:///fixture", "commit": "d" * 40, "verifiedCommit": "d" * 40,
                       "treeSha256": "e" * 40, "fileCount": 4, "bytes": 100,
                       "manifestSha256": "f" * 64},
        "sandbox": {"backend": "local-process", "enforced": [], "notEnforced": [],
                    "network": "not-enforced"},
        "agent": {"status": "completed", "exitCode": 0, "durationSeconds": duration,
                  "messages": [], "toolCalls": [], "commands": [], "filesRead": [],
                  "filesModified": [], "tests": [], "tokenUsage": {"input": 10, "output": 5},
                  "errors": [], "terminationReason": None},
        "changes": {"added": [], "removed": [], "modified": [], "unauthorized": [],
                    "worktreeRetained": True},
        "verification": {"commands": []},
        "artifacts": {},
        "stateHistory": [],
        "success": True,
        "errors": [],
        "limitations": [],
    }
