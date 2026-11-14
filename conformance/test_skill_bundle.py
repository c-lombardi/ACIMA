"""The vendored skill snapshot must match the tree `tools/bundle_skill.py` generated it from."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/acima-adoption"
VENDOR = SKILL / "vendor"
sys.path.insert(0, str(ROOT / "tools"))
from bundle_skill import digest, shipped_files  # noqa: E402


class SkillBundleTests(unittest.TestCase):
    def setUp(self) -> None:
        manifest_path = VENDOR / "MANIFEST.json"
        self.assertTrue(manifest_path.is_file(), "vendor/ is not generated; run tools/bundle_skill.py")
        self.bundle = json.loads(manifest_path.read_text(encoding="utf-8"))

    def test_every_vendored_file_matches_its_source(self) -> None:
        for relative, recorded in self.bundle["files"].items():
            with self.subTest(relative):
                self.assertTrue((VENDOR / relative).is_file(), relative)
                self.assertEqual(digest(VENDOR / relative), recorded["sha256"], relative)
                self.assertEqual(digest(ROOT / relative), recorded["sha256"], relative)

    def test_catalog_pin_agrees_with_the_skill_manifest(self) -> None:
        skill = json.loads((SKILL / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(skill["catalog"]["sha256"], self.bundle["catalogSha256"])
        self.assertEqual(digest(VENDOR / "tools/acima-spec/rules.json"), self.bundle["catalogSha256"])

    def test_vendored_skill_can_run_every_positive_control(self) -> None:
        self.assertIn("conformance/coverage.json", self.bundle["files"])
        for language, executable in (("python", sys.executable),
                                     ("typescript", shutil.which("node")),
                                     ("go", shutil.which("go")),
                                     ("dotnet", shutil.which("dotnet"))):
            with self.subTest(language):
                self.assertIsNotNone(executable, f"{language} toolchain is required")
                script = (
                    "import json, sys\n"
                    "from pathlib import Path\n"
                    "vendor = Path(sys.argv[1])\n"
                    "sys.path.insert(0, str(vendor / 'conformance'))\n"
                    "import adoption_workflow\n"
                    "print(json.dumps(adoption_workflow._positive_fixture(sys.argv[2])))\n"
                )
                result = subprocess.run(
                    [sys.executable, "-c", script, str(VENDOR), language],
                    cwd=ROOT, capture_output=True, text=True, timeout=300,
                )
                self.assertEqual(result.returncode, 0, result.stderr[-1000:])
                payload = json.loads(result.stdout)
                self.assertEqual(payload.get("status"), "valid", payload)
                self.assertEqual(payload.get("exitCode"), 0, payload)
                self.assertGreater(payload.get("sourceFiles", 0), 0, payload)
                self.assertEqual(payload.get("findingCount"), 0, payload)

    def test_digest_is_line_ending_independent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lf = root / "lf.txt"
            crlf = root / "crlf.txt"
            lf.write_bytes(b"alpha\nbeta\ngamma\n")
            crlf.write_bytes(b"alpha\r\nbeta\rgamma\r\n")
            self.assertEqual(digest(lf), digest(crlf))

    def test_no_unrecorded_files_are_shipped(self) -> None:
        expected = set(self.bundle["files"]) | {"MANIFEST.json"}
        actual = {path.relative_to(VENDOR).as_posix() for path in shipped_files(VENDOR)}
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
