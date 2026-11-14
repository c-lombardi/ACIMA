"""Go coverage for A005 configuration reads and D015 closure captures."""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "conformance/fixtures/values-config/go"
GO = ["go", "run", "./tools/archtest"]


def run(root: Path, config: str) -> dict:
    result = subprocess.run(
        GO + ["--root", str(root), "--config", config, "--format", "json"],
        cwd=ROOT / "examples/go", capture_output=True, text=True,
    )
    if not result.stdout.strip():
        raise AssertionError(result.stderr or "the Go enforcer printed nothing")
    return json.loads(result.stdout)


class GoValuesCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("go") is None:
            raise unittest.SkipTest("go toolchain is not installed")
        cls.gallery = run(ROOT / "examples/go", "acima.gallery.config.json")

    def test_gallery_executes_both_rules(self) -> None:
        fired = {}
        for finding in self.gallery["findings"]:
            fired.setdefault(finding["rule"], set()).add(finding["path"])
        self.assertEqual(fired["ACIMA-A005"], {"violations/a005_ambient_config.go"})
        self.assertEqual(fired["ACIMA-D015"], {
            "violations/d015_closure_capture.go",
            "violations/d015_cross_file_capture.go",
        })
        self.assertTrue(self.gallery["execution"]["ACIMA-A005"]["executed"])
        self.assertTrue(self.gallery["execution"]["ACIMA-D015"]["executed"])

    def test_gallery_reports_flag_and_process_argument_configuration(self) -> None:
        findings = [finding for finding in self.gallery["findings"]
                    if finding["rule"] == "ACIMA-A005"]
        messages = [finding["message"] for finding in findings]
        self.assertTrue(any("flag configuration" in message for message in messages), messages)
        self.assertTrue(any("process arguments" in message for message in messages), messages)

    def test_host_and_tooling_are_exempt_from_configuration_reads(self) -> None:
        report = run(FIXTURE, "acima.config.json")
        findings = [finding for finding in report["findings"]
                    if finding["rule"] == "ACIMA-A005"]
        self.assertEqual(findings, [])
        self.assertTrue(report["execution"]["ACIMA-A005"]["executed"])

    def test_adapter_flag_and_argument_reads_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "src/adapter").mkdir(parents=True)
            (root / "acima.config.json").write_text(json.dumps({
                "standard": "1.0.0",
                "mode": "base",
                "language": "go",
                "level": "L3",
                "root": ".",
                "modulePath": "example.test",
                "units": [
                    {"id": "adapter", "role": "adapter", "paths": ["src/adapter"]},
                ],
            }), encoding="utf-8")
            (root / "src/adapter/main.go").write_text(
                "package adapter\n\n"
                "import (\n\t\"flag\"\n\t\"os\"\n)\n\n"
                "func Configure() {\n"
                "\t_ = os.Args\n"
                "\t_ = flag.String(\"endpoint\", \"\", \"endpoint\")\n"
                "\tflag.Parse()\n"
                "}\n",
                encoding="utf-8",
            )
            report = run(root, "acima.config.json")
            findings = [finding for finding in report["findings"]
                        if finding["rule"] == "ACIMA-A005"]
        self.assertEqual({finding["path"] for finding in findings}, {"src/adapter/main.go"})
        messages = [finding["message"] for finding in findings]
        self.assertTrue(any("flag configuration" in message for message in messages), messages)
        self.assertTrue(any("process arguments" in message for message in messages), messages)

    def test_cross_file_dependency_is_reported_in_the_capture_file(self) -> None:
        findings = [finding for finding in self.gallery["findings"]
                    if finding["rule"] == "ACIMA-D015"]
        cross_file = [finding for finding in findings
                      if finding["path"] == "violations/d015_cross_file_capture.go"]
        self.assertEqual(len(cross_file), 1, findings)
        self.assertIn("crossFileStore", cross_file[0]["message"])

    def test_clean_and_curried_gocode_does_not_fire(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "internal/orders/impl").mkdir(parents=True)
            (root / "cmd/host").mkdir(parents=True)
            (root / "acima.config.json").write_text(json.dumps({
                "standard": "1.0.0",
                "mode": "base",
                "language": "go",
                "level": "L3",
                "root": ".",
                "modulePath": "example.test",
                "units": [
                    {"id": "orders", "module": "orders", "role": "implementation",
                     "paths": ["internal/orders/impl"]},
                    {"id": "host", "role": "host", "paths": ["cmd/host"]},
                ],
            }), encoding="utf-8")
            (root / "internal/orders/impl/service.go").write_text(
                "package orders\n\n"
                "type Store struct{}\n\n"
                "func (s *Store) Save(id string) {}\n\n"
                "type fakeOS struct{}\n\n"
                "func (fakeOS) Getenv(string) string { return \"\" }\n\n"
                "var restore = &Store{}\n\n"
                "func Bound(store *Store) func(string) {\n"
                "\treturn func(id string) { store.Save(id) }\n"
                "}\n\n"
                "func Shadowed() func(string) {\n"
                "\torderStore := &Store{}\n"
                "\treturn func(id string) { orderStore.Save(id) }\n"
                "}\n\n"
                "func ShadowOS() string {\n"
                "\tos := fakeOS{}\n"
                "\treturn os.Getenv(\"NOT_THE_ENVIRONMENT\")\n"
                "}\n\n"
                "func RestoreAction() func(string) {\n"
                "\treturn func(id string) { restore.Save(id) }\n"
                "}\n\n"
                "func LiteralOnly() string {\n"
                "\treturn \"os.Getenv(\\\"ORDERS_DATABASE_URL\\\")\"\n"
                "}\n\n"
                "func Pure() func(int) int {\n"
                "\treturn func(value int) int { return value + 1 }\n"
                "}\n",
                encoding="utf-8",
            )
            (root / "internal/orders/impl/deps.go").write_text(
                "package orders\n\nvar orderStore = &Store{}\n",
                encoding="utf-8",
            )
            (root / "cmd/host/main.go").write_text(
                "package main\n\nimport \"os\"\n\n"
                "func main() { _ = os.Getenv(\"ORDERS_DATABASE_URL\") }\n",
                encoding="utf-8",
            )
            report = run(root, "acima.config.json")
            self.assertFalse([f for f in report["findings"]
                              if f["rule"] in {"ACIMA-A005", "ACIMA-D015"}], report["findings"])


if __name__ == "__main__":
    unittest.main()
