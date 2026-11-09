"""Pin the human-readable catalog contract for the executable G005 rule."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class RuleCatalogTests(unittest.TestCase):
    def test_g005_is_unclassified_source(self) -> None:
        catalog = json.loads((ROOT / "tools/acima-spec/rules.json").read_text(encoding="utf-8"))
        rule = next(item for item in catalog["rules"] if item["id"] == "ACIMA-G005")
        self.assertEqual(rule["title"], "Unclassified source")
        self.assertIn("declared unit", rule["summary"])


    def test_every_rule_carries_a_remedy(self) -> None:
        catalog = json.loads((ROOT / "tools/acima-spec/rules.json").read_text(encoding="utf-8"))
        rules = catalog["rules"]
        self.assertEqual(len(rules), 53)
        for rule in rules:
            fix = rule.get("fix", "").strip()
            self.assertGreaterEqual(len(fix), 40, rule["id"])
            self.assertNotEqual(fix.lower(), rule["summary"].strip().lower(), rule["id"])

if __name__ == "__main__":
    unittest.main()
