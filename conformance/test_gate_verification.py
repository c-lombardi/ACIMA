"""CI gate verification: configured is not observed, and observed is not verified.

The fixtures deliberately separate workflow discovery from execution proof. A workflow only
mentions ACIMA, a correct command that runs on every push, a disabled/advisory step, a wrong
root or level, and a provider record that does not match the actual workflow must all fail closed.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("acima_gate", ROOT / "tools/acima.py")
acima = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules["acima_gate"] = acima
SPEC.loader.exec_module(acima)

CATALOG = json.loads((ROOT / "tools/acima-spec/rules.json").read_text(encoding="utf-8"))
CATALOG_SHA = hashlib.sha256((ROOT / "tools/acima-spec/rules.json").read_bytes()).hexdigest()
HEAD = "a" * 40
REMOTE = "https://github.com/owner/repo.git"
WORKFLOW = ".github/workflows/acima.yml"


def write(root: Path, relative: str, content: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def config(root: Path, level: str = "L2") -> None:
    write(root, "acima.config.json", json.dumps({
        "standard": CATALOG["version"], "language": "python", "level": level, "mode": "base",
        "units": [{"id": "orders", "role": "implementation", "module": "orders",
                   "paths": ["src/orders"]}],
    }))
    write(root, "src/orders/app.py", "VALUE = 1\n")


def workflow(root: Path, content: str, name: str = "acima.yml") -> Path:
    return write(root, f".github/workflows/{name}", content)


def valid_workflow(trigger: str = "on:\n  pull_request:\n") -> str:
    return (
        "name: ACIMA gate\n"
        + trigger
        + "jobs:\n"
        "  gate:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - uses: actions/checkout@v4\n"
        "      - name: ACIMA\n"
        "        run: python3 examples/python/tools/acima_arch.py --root . --level L2\n"
    )


def observation(root: Path, **overrides) -> None:
    payload = {
        "repository": "owner/repo",
        "commit": HEAD,
        "workflow": WORKFLOW,
        "command": "python3 examples/python/tools/acima_arch.py --root . --level L2",
        "executedAt": "2026-11-09T10:00:00Z",
        "standard": CATALOG["version"],
        "catalogSha256": CATALOG_SHA,
        "level": "L2",
        "sourceFiles": 4,
        "exitCode": 0,
        "manual": False,
        "verified": True,
        "provider": "github-actions",
        "runId": "42",
    }
    payload.update(overrides)
    write(root, "docs/acima/gate-observed.json", json.dumps(payload))


def gate(root: Path) -> dict:
    with mock.patch.object(acima, "_git_head", return_value=HEAD), \
            mock.patch.object(acima, "_git_remote", return_value=REMOTE):
        report = acima.status_project(root)
    return {step["name"]: step for step in report["steps"]}["gate"]


class GateVerificationTests(unittest.TestCase):
    def test_mention_only_workflow_is_not_a_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config(root)
            workflow(root, "name: ACIMA notes\non: [pull_request]\njobs: {}\n")
            result = gate(root)
            self.assertEqual(result["state"], "BLOCKED")
            self.assertEqual(result["gateState"], "mention-only")
            self.assertIn("mentions ACIMA", result["evidence"])

    def test_correct_invocation_without_pull_request_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config(root)
            workflow(root, valid_workflow("on: [push]\n"))
            result = gate(root)
            self.assertEqual(result["state"], "BLOCKED")
            self.assertEqual(result["gateState"], "not-pull-request")
            self.assertIn("pull request", result["evidence"])

    def test_disabled_or_advisory_job_is_not_verified(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config(root)
            workflow(root, valid_workflow().replace(
                "      - name: ACIMA\n        run:",
                "      - name: ACIMA\n        if: false\n        run:"))
            result = gate(root)
            self.assertEqual(result["state"], "BLOCKED")
            self.assertEqual(result["gateState"], "disabled-or-advisory")
            self.assertIn("disabled", result["evidence"])

    def test_advisory_step_is_not_verified(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config(root)
            workflow(root, valid_workflow().replace(
                "      - name: ACIMA\n        run:",
                "      - name: ACIMA\n        continue-on-error: true\n        run:"))
            result = gate(root)
            self.assertEqual(result["state"], "BLOCKED")
            self.assertEqual(result["gateState"], "disabled-or-advisory")
            self.assertIn("allows failure", result["evidence"])

    def test_multiple_jobs_with_one_valid_gate_is_configured(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config(root)
            workflow(root, (
                "name: ACIMA gate\non:\n  pull_request:\n"
                "jobs:\n"
                "  disabled:\n    if: false\n    runs-on: ubuntu-latest\n    steps:\n"
                "      - run: python3 examples/python/tools/acima_arch.py --root . --level L2\n"
                "  gate:\n    runs-on: ubuntu-latest\n    steps:\n"
                "      - run: python3 examples/python/tools/acima_arch.py --root . --level L2\n"
            ))
            result = gate(root)
            self.assertEqual(result["state"], "IN_PROGRESS")
            self.assertEqual(result["gateState"], "configured-not-observed")

    def test_incorrect_root_is_not_verified(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config(root)
            workflow(root, valid_workflow().replace("--root .", "--root src"))
            result = gate(root)
            self.assertEqual(result["state"], "BLOCKED")
            self.assertIn("repository root", result["evidence"])

    def test_incorrect_level_is_not_verified(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config(root, level="L2")
            workflow(root, valid_workflow().replace("--level L2", "--level L1"))
            result = gate(root)
            self.assertEqual(result["state"], "BLOCKED")
            self.assertIn("declared level is L2", result["evidence"])

    def test_multiple_workflows_with_one_valid_gate_is_configured(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config(root)
            workflow(root, "name: ACIMA notes\non: [pull_request]\njobs: {}\n", "notes.yml")
            workflow(root, valid_workflow())
            result = gate(root)
            self.assertEqual(result["state"], "IN_PROGRESS")
            self.assertEqual(result["gateState"], "configured-not-observed")
            self.assertIn("configured, not observed", result["evidence"])

    def test_provider_run_for_wrong_workflow_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config(root)
            workflow(root, valid_workflow())
            workflow(root, "name: other\non: [pull_request]\njobs: {}\n", "other.yml")
            observation(root, workflow=".github/workflows/other.yml")
            result = gate(root)
            self.assertEqual(result["state"], "BLOCKED")
            self.assertEqual(result["gateState"], "observation-mismatch")
            self.assertIn("workflow does not exist", result["evidence"])

    def test_successful_run_for_old_commit_is_stale(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config(root)
            workflow(root, valid_workflow())
            observation(root, commit="b" * 40)
            result = gate(root)
            self.assertEqual(result["state"], "BLOCKED")
            self.assertEqual(result["gateState"], "observation-stale")
            self.assertIn("stale", result["evidence"])

    def test_observation_command_from_another_workflow_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config(root)
            workflow(root, valid_workflow())
            workflow(root, valid_workflow().replace(
                "python3 examples/python/tools/acima_arch.py --root . --level L2",
                "node examples/typescript/tools/acima-arch.mjs --root . --level L2"),
                "typescript.yml")
            observation(root, command="node examples/typescript/tools/acima-arch.mjs --root . --level L2")
            result = gate(root)
            self.assertEqual(result["state"], "BLOCKED")
            self.assertEqual(result["gateState"], "observation-mismatch")
            self.assertIn("observed workflow", result["evidence"])

    def test_failed_provider_conclusion_is_not_success(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config(root)
            workflow(root, valid_workflow())
            observation(root, conclusion="failure", exitCode=0)
            result = gate(root)
            self.assertEqual(result["state"], "IN_PROGRESS")
            self.assertEqual(result["gateState"], "observation-failed")
            self.assertIn("observed gate failure", result["evidence"])

    def test_observation_command_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config(root)
            workflow(root, valid_workflow())
            observation(root, command="node examples/typescript/tools/acima-arch.mjs --root .")
            result = gate(root)
            self.assertEqual(result["state"], "BLOCKED")
            self.assertEqual(result["gateState"], "observation-mismatch")
            self.assertIn("command does not match", result["evidence"])

    def test_missing_provider_provenance_is_not_verified(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config(root)
            workflow(root, valid_workflow())
            observation(root, provider="", runId="", verified=True, manual=False)
            result = gate(root)
            self.assertEqual(result["state"], "IN_PROGRESS")
            self.assertEqual(result["gateState"], "observation-unverified")
            self.assertIn("not independently verified", result["evidence"])

    def test_skipped_enforcer_execution_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config(root)
            workflow(root, valid_workflow())
            observation(root, enforcerExecuted=False)
            result = gate(root)
            self.assertEqual(result["state"], "BLOCKED")
            self.assertEqual(result["gateState"], "observation-mismatch")
            self.assertIn("did not execute", result["evidence"])

    def test_successful_run_without_actual_enforcer_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config(root)
            workflow(root, "name: ACIMA\non: [pull_request]\njobs:\n  gate:\n"
                           "    steps:\n      - run: echo 'ACIMA passes'\n")
            observation(root, command="echo ACIMA passes")
            result = gate(root)
            self.assertEqual(result["state"], "BLOCKED")
            self.assertEqual(result["gateState"], "mention-only")
            self.assertIn("invokes no gate command", result["evidence"])

    def test_conditional_enforcer_is_not_verified(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config(root)
            workflow(root, valid_workflow().replace(
                "      - name: ACIMA\n        run:",
                "      - name: ACIMA\n        if: ${{ github.event_name == 'push' }}\n"
                "        run:"))
            result = gate(root)
            self.assertEqual(result["state"], "BLOCKED")
            self.assertEqual(result["gateState"], "disabled-or-advisory")
            self.assertIn("conditional", result["evidence"])

    def test_reusable_workflow_is_not_verified(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config(root)
            workflow(root, "name: ACIMA\non: [pull_request]\njobs:\n  gate:\n"
                           "    uses: ./.github/workflows/reusable.yml\n")
            result = gate(root)
            self.assertEqual(result["state"], "BLOCKED")
            self.assertEqual(result["gateState"], "unsupported-workflow")
            self.assertIn("reusable workflow", result["evidence"])

    def test_observation_for_wrong_repository_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config(root)
            workflow(root, valid_workflow())
            observation(root, repository="other/repository")
            result = gate(root)
            self.assertEqual(result["state"], "BLOCKED")
            self.assertEqual(result["gateState"], "observation-mismatch")
            self.assertIn("repository does not match", result["evidence"])

    def test_other_reference_enforcer_forms_are_recognized(self) -> None:
        commands = (
            "python3 tools/acima.py analyze --root . --level L2",
            "./tools/archtest --root . --level L2",
            "dotnet run --project examples/dotnet/tools/Acima.ArchTests -- "
            "--root . --level L2",
        )
        for command in commands:
            with self.subTest(command=command):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    config(root)
                    workflow(root, valid_workflow().replace(
                        "python3 examples/python/tools/acima_arch.py --root . --level L2",
                        command))
                    observation(root, command=command)
                    result = gate(root)
                    self.assertEqual(result["state"], "COMPLETE")
                    self.assertEqual(result["gateState"], "verified")

    def test_fully_valid_pull_request_gate_is_verified(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config(root)
            workflow(root, valid_workflow())
            observation(root)
            result = gate(root)
            self.assertEqual(result["state"], "COMPLETE")
            self.assertEqual(result["gateState"], "verified")
            self.assertIn("independently recorded run 42", result["evidence"])
            self.assertTrue(result["verified"])


if __name__ == "__main__":
    unittest.main()
