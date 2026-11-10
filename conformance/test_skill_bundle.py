"""The vendored skill snapshot must match the tree `tools/bundle_skill.py` generated it from."""
from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/acima-adoption"
VENDOR = SKILL / "vendor"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SkillBundleTests(unittest.TestCase):
    def setUp(self) -> None:
        manifest_path = VENDOR / "MANIFEST.json"
        self.assertTrue(manifest_path.is_file(), "vendor/ is not generated; run tools/bundle_skill.py")
        self.bundle = json.loads(manifest_path.read_text(encoding="utf-8"))

    def test_every_vendored_file_matches_its_source(self) -> None:
        for relative, recorded in self.bundle["files"].items():
            with self.subTest(relative):
                self.assertTrue((VENDOR / relative).is_file(), relative)
                self.assertEqual(sha256(VENDOR / relative), recorded["sha256"], relative)
                self.assertEqual(sha256(ROOT / relative), recorded["sha256"], relative)

    def test_catalog_pin_agrees_with_the_skill_manifest(self) -> None:
        skill = json.loads((SKILL / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(skill["catalog"]["sha256"], self.bundle["catalogSha256"])
        self.assertEqual(sha256(VENDOR / "tools/acima-spec/rules.json"), self.bundle["catalogSha256"])

    def test_no_unrecorded_files_are_shipped(self) -> None:
        expected = set(self.bundle["files"]) | {"MANIFEST.json"}
        actual = {path.relative_to(VENDOR).as_posix()
                  for path in VENDOR.rglob("*")
                  if path.is_file() and "__pycache__" not in path.parts
                  and path.suffix != ".pyc"}
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
