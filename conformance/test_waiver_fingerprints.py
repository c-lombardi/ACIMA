"""Adversarial checks for finding-scoped waivers.

A baseline may suppress the exact findings it measured. It must not suppress a new
finding in the same unit, path, or rule merely because the scope still matches.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = {
    "python": {
        "dir": "examples/python",
        "command": [sys.executable, "tools/acima_arch.py"],
        "tool": sys.executable,
    },
    "typescript": {
        "dir": "examples/typescript",
        "command": ["node", "tools/acima-arch.mjs"],
        "tool": "node",
    },
    "go": {
        "dir": "examples/go",
        "command": ["go", "run", "./tools/archtest"],
        "tool": "go",
    },
    "dotnet": {
        "dir": "examples/dotnet",
        "command": ["dotnet", "run", "--project", "tools/Acima.ArchTests", "--no-build", "--"],
        "tool": "dotnet",
    },
}


def run(case: dict, root: Path) -> dict:
    result = subprocess.run(
        case["command"] + ["--root", str(root), "--config", "acima.gallery.config.json",
                           "--format", "json"],
        cwd=ROOT / case["dir"], capture_output=True, text=True,
    )
    assert result.stdout.strip(), result.stderr
    return json.loads(result.stdout)


def write_waiver(root: Path, finding: dict, fingerprint: str | None, *,
                 owner: str = "regression-test", expires: str = "2099-01-01",
                 reviewed_on: str = "2026-11-08", scope: str | None = None) -> None:
    waiver = {
        "rule": finding["rule"],
        "scope": scope or f"path:{finding['path']}",
        "owner": owner,
        "reason": "prove that a baseline is finding-scoped",
        "expires": expires,
        "reviewedOn": reviewed_on,
    }
    if fingerprint is not None:
        waiver["fingerprint"] = fingerprint
    path = root / "violations" / "waivers.json"
    path.write_text(json.dumps({"standard": "1.0.0", "waivers": [waiver]}, indent=2) + "\n",
                    encoding="utf-8")


class WaiverFingerprintTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("dotnet"):
            subprocess.run(
                ["dotnet", "build", "tools/Acima.ArchTests", "-v", "q", "--nologo"],
                cwd=ROOT / "examples/dotnet", capture_output=True, text=True, check=False,
            )

    def test_exact_fingerprint_suppresses_one_not_the_rule(self) -> None:
        for language, case in CASES.items():
            if shutil.which(case["tool"]) is None:
                self.skipTest(f"{case['tool']} is not installed")
            with self.subTest(language=language), tempfile.TemporaryDirectory() as temporary:
                target = Path(temporary) / language
                shutil.copytree(ROOT / case["dir"], target,
                                ignore=shutil.ignore_patterns("bin", "obj", "__pycache__",
                                                              "node_modules", ".git"))
                before = run(case, target)["findings"]
                counts = Counter(finding["rule"] for finding in before)
                candidates = [
                    finding for finding in before
                    if finding["rule"] == "ACIMA-D001" and counts[finding["rule"]] >= 2
                    and finding.get("fingerprint")
                ]
                if not candidates:
                    candidates = [
                        finding for finding in before
                        if counts[finding["rule"]] >= 2 and finding.get("fingerprint")
                    ]
                self.assertTrue(candidates, f"{language}: no repeatable finding to test")
                chosen = candidates[0]
                baseline = counts[chosen["rule"]]

                write_waiver(target, chosen, chosen["fingerprint"])
                exact = run(case, target)["findings"]
                exact_count = sum(1 for finding in exact if finding["rule"] == chosen["rule"])
                self.assertEqual(exact_count, baseline - 1,
                                 f"{language}: exact waiver suppressed the wrong number of findings")

                write_waiver(target, chosen, None)
                broad = run(case, target)["findings"]
                broad_count = sum(1 for finding in broad if finding["rule"] == chosen["rule"])
                self.assertEqual(broad_count, baseline,
                                 f"{language}: a fingerprint-less waiver hid findings")
                self.assertIn("ACIMA-G001", {finding["rule"] for finding in broad},
                              f"{language}: a broad waiver must be reported as G001")

    def test_unassigned_owner_and_malformed_fingerprint_are_rejected(self) -> None:
        for language, case in CASES.items():
            if shutil.which(case["tool"]) is None:
                self.skipTest(f"{case['tool']} is not installed")
            with self.subTest(language=language), tempfile.TemporaryDirectory() as temporary:
                target = Path(temporary) / language
                shutil.copytree(ROOT / case["dir"], target,
                                ignore=shutil.ignore_patterns("bin", "obj", "__pycache__",
                                                              "node_modules", ".git"))
                before = run(case, target)["findings"]
                counts = Counter(finding["rule"] for finding in before)
                candidates = [finding for finding in before
                              if finding.get("fingerprint") and counts[finding["rule"]] >= 2]
                if not candidates:
                    candidates = [finding for finding in before if finding.get("fingerprint")]
                self.assertTrue(candidates, f"{language}: no repeatable finding to test")
                chosen = candidates[0]
                baseline = counts[chosen["rule"]]
                cases = {
                    "unassigned owner": ("unassigned", chosen["fingerprint"]),
                    "malformed fingerprint": ("regression-test", "sha256:" + "0" * 63),
                }
                for label, (owner, fingerprint) in cases.items():
                    with self.subTest(language=language, case=label):
                        write_waiver(target, chosen, fingerprint, owner=owner)
                        after = run(case, target)["findings"]
                        count = sum(1 for finding in after if finding["rule"] == chosen["rule"])
                        self.assertEqual(count, baseline,
                                         f"{language}: {label} suppressed findings")
                        self.assertIn("ACIMA-G001", {finding["rule"] for finding in after},
                                      f"{language}: {label} must be reported as G001")

    def test_waiver_dates_are_strict_ordered_and_inclusive(self) -> None:
        today = datetime.now(timezone.utc).date().isoformat()
        date_cases = {
            "malformed expiry": ("2099-01-01T00:00:00", "2026-11-08", False),
            "malformed review date": ("2099-01-01", "not-a-date", False),
            "future review date": ("2099-01-01", "2999-01-01", False),
            "review after expiry": ("2026-11-01", "2026-11-02", False),
            "expiry today is inclusive": (today, today, True),
        }
        for language, case in CASES.items():
            if shutil.which(case["tool"]) is None:
                self.skipTest(f"{case['tool']} is not installed")
            with self.subTest(language=language), tempfile.TemporaryDirectory() as temporary:
                target = Path(temporary) / language
                shutil.copytree(ROOT / case["dir"], target,
                                ignore=shutil.ignore_patterns("bin", "obj", "__pycache__",
                                                              "node_modules", ".git"))
                before = run(case, target)["findings"]
                counts = Counter(finding["rule"] for finding in before)
                candidates = [finding for finding in before
                              if finding.get("fingerprint") and counts[finding["rule"]] >= 1]
                self.assertTrue(candidates, f"{language}: no finding to test")
                chosen = candidates[0]
                baseline = counts[chosen["rule"]]
                for label, (expires, reviewed_on, suppresses) in date_cases.items():
                    with self.subTest(language=language, case=label):
                        write_waiver(target, chosen, chosen["fingerprint"],
                                     expires=expires, reviewed_on=reviewed_on)
                        after = run(case, target)["findings"]
                        count = sum(1 for finding in after if finding["rule"] == chosen["rule"])
                        rules = {finding["rule"] for finding in after}
                        if suppresses:
                            self.assertEqual(count, baseline - 1,
                                             f"{language}: {label} did not suppress")
                            self.assertNotIn("ACIMA-G001", rules,
                                             f"{language}: {label} was rejected")
                        else:
                            self.assertEqual(count, baseline,
                                             f"{language}: {label} suppressed findings")
                            self.assertIn("ACIMA-G001", rules,
                                          f"{language}: {label} must be reported as G001")

    def test_waiver_path_globs_share_one_contract(self) -> None:
        for language, case in CASES.items():
            if shutil.which(case["tool"]) is None:
                self.skipTest(f"{case['tool']} is not installed")
            with self.subTest(language=language), tempfile.TemporaryDirectory() as temporary:
                target = Path(temporary) / language
                shutil.copytree(ROOT / case["dir"], target,
                                ignore=shutil.ignore_patterns("bin", "obj", "__pycache__",
                                                              "node_modules", ".git"))
                before = run(case, target)["findings"]
                nested = next((finding for finding in before
                               if finding.get("fingerprint") and finding["path"].count("/") >= 3),
                              None)
                direct = next((finding for finding in before
                               if finding.get("fingerprint") and finding["path"].count("/") == 1),
                              None)
                self.assertIsNotNone(nested, f"{language}: no nested finding to test")
                self.assertIsNotNone(direct, f"{language}: no direct finding to test")
                assert nested is not None and direct is not None

                parts = nested["path"].split("/")
                recursive = f"{parts[0]}/**/{parts[-1]}"
                write_waiver(target, nested, nested["fingerprint"], scope=f"path:{recursive}")
                after = run(case, target)["findings"]
                matches = {(finding["rule"], finding["path"]) for finding in after}
                self.assertNotIn((nested["rule"], nested["path"]), matches,
                                 f"{language}: **/ did not match at a segment boundary")

                crossing = f"{parts[0]}/*"
                write_waiver(target, nested, nested["fingerprint"], scope=f"path:{crossing}")
                after = run(case, target)["findings"]
                matches = {(finding["rule"], finding["path"]) for finding in after}
                self.assertIn((nested["rule"], nested["path"]), matches,
                              f"{language}: * crossed a path separator")

                direct_pattern = f"**/{direct['path'].split('/')[-1]}"
                write_waiver(target, direct, direct["fingerprint"], scope=f"path:{direct_pattern}")
                after = run(case, target)["findings"]
                matches = {(finding["rule"], finding["path"]) for finding in after}
                self.assertNotIn((direct["rule"], direct["path"]), matches,
                                 f"{language}: **/ did not match zero directories")

                invalid = f"{parts[0]}/**bad/{parts[-1]}"
                write_waiver(target, nested, nested["fingerprint"], scope=f"path:{invalid}")
                after = run(case, target)["findings"]
                matches = {(finding["rule"], finding["path"]) for finding in after}
                self.assertIn((nested["rule"], nested["path"]), matches,
                              f"{language}: an invalid glob suppressed a finding")
                self.assertIn("ACIMA-G001", {finding["rule"] for finding in after},
                              f"{language}: an invalid glob must be reported as G001")


class AdoptionPreflightTests(unittest.TestCase):
    def test_one_existing_source_file_is_brownfield(self) -> None:
        script = ROOT / "skills/acima-adoption/scripts/preflight.py"
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            (target / "src").mkdir()
            (target / "src" / "legacy.py").write_text("VALUE = 1\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(script), "--project", str(target), "--format", "json"],
                cwd=ROOT, capture_output=True, text=True,
            )
            payload = json.loads(result.stdout)
            # Classification is independent of readiness: one source file is brownfield,
            # and with no discoverable unit the run must fail closed (TGT-004), not say READY.
            self.assertEqual(payload["project"]["mode"], "brownfield")
            checks = {check["id"]: check for check in payload["checks"]}
            self.assertEqual(checks["TGT-004"]["status"], "fail")
            self.assertEqual(result.returncode, 1, result.stderr)

    def test_baseline_waivers_are_unique_and_fingerprinted(self) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "preflight", ROOT / "skills/acima-adoption/scripts/preflight.py")
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        units = [{"id": "orders", "module": "orders", "role": "implementation",
                  "paths": ["src/orders"]}]
        findings = [
            {"rule": "ACIMA-D001", "path": "src/orders/a.py", "line": 1,
             "message": "leak", "fingerprint": "sha256:one"},
            {"rule": "ACIMA-D001", "path": "src/orders/b.py", "line": 1,
             "message": "leak", "fingerprint": "sha256:two"},
        ]
        document = module.waiver_stub(findings, units)
        self.assertEqual(len(document["waivers"]), 2)
        self.assertEqual({waiver["fingerprint"] for waiver in document["waivers"]},
                         {"sha256:one", "sha256:two"})


PROJECT_FIXTURE = ROOT / "conformance/fixtures/dotnet-project-waiver"


class ProjectFileWaiverTests(unittest.TestCase):
    """Project-file findings belong to the unit that declares their path.

    The enforcer classified source files only, so a finding on `*.csproj` resolved to no
    unit and no `unit:` or `module:` waiver could ever match it.  That made project-level
    debt permanently unwaivable, which is why it was carried in a baseline instead.
    """

    def setUp(self) -> None:
        if shutil.which("dotnet") is None:
            self.skipTest("dotnet SDK is not installed")
        self.temporary = tempfile.TemporaryDirectory()
        self.target = Path(self.temporary.name) / "repo"
        shutil.copytree(PROJECT_FIXTURE, self.target,
                        ignore=shutil.ignore_patterns("bin", "obj"))

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_fixture(self) -> tuple[subprocess.CompletedProcess, dict]:
        result = subprocess.run(
            ["dotnet", "run", "--project", str(ROOT / "examples/dotnet/tools/Acima.ArchTests"),
             "--no-build", "--", "--root", str(self.target),
             "--config", "acima.config.json", "--format", "json"],
            cwd=ROOT, capture_output=True, text=True,
        )
        self.assertTrue(result.stdout.strip(), result.stderr)
        return result, json.loads(result.stdout)

    def write_waiver(self, finding: dict, scope: str, fingerprint: str | None = None) -> None:
        document = {
            "standard": "1.0.0",
            "waivers": [{
                "rule": finding["rule"],
                "scope": scope,
                "owner": "regression-test",
                "reason": "prove a project-file finding resolves to its unit",
                "expires": "2099-01-01",
                "reviewedOn": "2026-11-08",
                "fingerprint": fingerprint or finding["fingerprint"],
            }],
        }
        (self.target / "waivers.json").write_text(json.dumps(document, indent=2) + "\n",
                                                  encoding="utf-8")

    def project_finding(self, payload: dict) -> dict:
        findings = [finding for finding in payload["findings"]
                    if finding["rule"] == "ACIMA-D001"
                    and finding["path"].endswith(".csproj")]
        self.assertTrue(findings, payload)
        return findings[0]

    def test_unit_scoped_waiver_suppresses_a_project_file_finding(self) -> None:
        before, payload = self.run_fixture()
        self.assertEqual(before.returncode, 1, payload)
        finding = self.project_finding(payload)

        self.write_waiver(finding, "unit:alpha")
        after, payload = self.run_fixture()
        self.assertEqual(payload["findings"], [], payload)
        self.assertEqual(after.returncode, 0, payload)

    def test_a_wrong_fingerprint_leaves_the_project_finding_visible(self) -> None:
        _, payload = self.run_fixture()
        finding = self.project_finding(payload)

        self.write_waiver(finding, "unit:alpha", "sha256:" + "0" * 64)
        after, payload = self.run_fixture()
        self.assertIn(finding["path"], {item["path"] for item in payload["findings"]})
        self.assertEqual(after.returncode, 1, payload)

    def test_the_owning_unit_is_required(self) -> None:
        _, payload = self.run_fixture()
        finding = self.project_finding(payload)

        self.write_waiver(finding, "unit:beta")
        _, payload = self.run_fixture()
        self.assertIn(finding["path"], {item["path"] for item in payload["findings"]})


if __name__ == "__main__":
    unittest.main()
