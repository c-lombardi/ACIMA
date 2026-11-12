"""Provenance: pinned skill, catalog, standard and instruction templates."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from support import HARNESS_ROOT

from runner.lifecycle import InvalidConfiguration
from runner.provenance import (
    approval_provenance,
    catalog_provenance,
    hash_tree,
    instruction_bundle,
    load_config,
    sha256_file,
    skill_provenance,
)


class ProvenanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.acima_root = HARNESS_ROOT.parents[1]

    def test_skill_matches_its_catalog_pin(self) -> None:
        skill = skill_provenance(self.acima_root)
        catalog = catalog_provenance(self.acima_root)
        manifest = json.loads((self.acima_root / "skills/acima-adoption/manifest.json")
                              .read_text(encoding="utf-8"))
        self.assertEqual(skill["version"], manifest["skillVersion"])
        self.assertEqual(skill["standard"], manifest["standard"])
        self.assertEqual(catalog["sha256"], manifest["catalog"]["sha256"])
        self.assertEqual(catalog["rules"], 56)
        self.assertEqual(catalog["portable"], 42)
        self.assertEqual(len(skill["contentSha256"]), 64)

    def test_tree_hash_is_stable_and_content_sensitive(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "a.txt").write_text("one\n", encoding="utf-8")
            first, count, total = hash_tree(root)
            second, _count, _total = hash_tree(root)
            self.assertEqual(first, second)
            self.assertEqual(count, 1)
            (root / "a.txt").write_text("two\n", encoding="utf-8")
            third, _count, _total = hash_tree(root)
            self.assertNotEqual(first, third)

    def test_instruction_bundle_fills_every_placeholder(self) -> None:
        bundle = instruction_bundle(HARNESS_ROOT, "read-only", {
            "REPOSITORY": "/tmp/repo", "OUTPUT_DIR": "/tmp/out", "SKILL_PATH": "/tmp/skill",
            "MODE": "read-only", "APPROVED_CHANGES": "none (read-only assessment)",
        })
        self.assertNotIn("{{", bundle["text"])
        self.assertEqual(len(bundle["sha256"]), 64)
        self.assertEqual(bundle["id"], "read-only-assessment.md")
        self.assertIn("untrusted input", bundle["text"])
        self.assertNotIn("ACIMA-D001", bundle["text"].split("```json")[0])

    def test_missing_placeholder_value_is_an_error(self) -> None:
        with self.assertRaises(InvalidConfiguration):
            instruction_bundle(HARNESS_ROOT, "read-only", {"REPOSITORY": "/tmp/repo"})

    def test_unknown_mode_is_an_error(self) -> None:
        with self.assertRaises(InvalidConfiguration):
            instruction_bundle(HARNESS_ROOT, "autonomous", {})

    def test_limits_are_complete_and_positive(self) -> None:
        _config, limits = load_config(HARNESS_ROOT)
        payload = limits.as_dict()
        self.assertEqual(payload["maxConcurrentRuns"], 1)
        self.assertGreater(payload["executionTimeoutSeconds"], 0)
        self.assertGreater(payload["maxCorrectionAttempts"], 0)

    def test_approval_record_requires_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "approval.json"
            path.write_text(json.dumps({
                "approvedBy": "owner", "approvedOn": "2026-11-10", "paths": [],
            }), encoding="utf-8")
            with self.assertRaises(InvalidConfiguration):
                approval_provenance(path)

    def test_approval_record_is_hashed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "approval.json"
            path.write_text(json.dumps({
                "approvedBy": "owner", "approvedOn": "2026-11-10",
                "paths": ["acima.config.json"],
            }), encoding="utf-8")
            approval = approval_provenance(path)
            self.assertEqual(approval["approvedPaths"], ["acima.config.json"])
            self.assertEqual(approval["sha256"], sha256_file(path))


if __name__ == "__main__":
    unittest.main()
