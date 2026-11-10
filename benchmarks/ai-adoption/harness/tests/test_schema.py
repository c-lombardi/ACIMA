"""The small schema validator and the shipped schemas."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from support import HARNESS_ROOT

from runner.schema import SchemaError, validate


class SchemaTests(unittest.TestCase):
    def test_valid_object_passes(self) -> None:
        schema = {"type": "object", "required": ["name"],
                  "properties": {"name": {"type": "string", "minLength": 2}},
                  "additionalProperties": False}
        validate({"name": "ok"}, schema)

    def test_missing_required_property_fails(self) -> None:
        with self.assertRaises(SchemaError):
            validate({}, {"type": "object", "required": ["name"]})

    def test_unexpected_property_fails(self) -> None:
        with self.assertRaises(SchemaError):
            validate({"name": "ok", "extra": 1},
                     {"type": "object", "properties": {"name": {"type": "string"}},
                      "additionalProperties": False})

    def test_type_union_and_null(self) -> None:
        schema = {"type": ["string", "null"]}
        validate(None, schema)
        validate("value", schema)
        with self.assertRaises(SchemaError):
            validate(3, schema)

    def test_boolean_is_not_an_integer(self) -> None:
        with self.assertRaises(SchemaError):
            validate(True, {"type": "integer"})

    def test_unsupported_keyword_is_an_error(self) -> None:
        with self.assertRaises(SchemaError):
            validate({}, {"type": "object", "oneOf": []})

    def test_shipped_schemas_are_valid_json(self) -> None:
        for path in sorted((HARNESS_ROOT / "harness" / "schemas").glob("*.schema.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("$id", payload)
            self.assertEqual(payload.get("$schema"),
                             "https://json-schema.org/draft/2020-12/schema")

    def test_scenario_schema_accepts_both_shipped_scenarios(self) -> None:
        from runner.controller import BenchmarkController

        controller = BenchmarkController()
        schema = json.loads((HARNESS_ROOT / "harness" / "schemas" / "scenario.schema.json")
                            .read_text(encoding="utf-8"))
        for entry in controller.scenario_manifest()["scenarios"]:
            scenario = controller.load_scenario(entry["id"])
            validate(scenario, schema)

    def test_rejects_an_invented_category(self) -> None:
        from runner.controller import BenchmarkController

        controller = BenchmarkController()
        scenario = controller.load_scenario("library-python-httpx")
        scenario["category"] = "not-a-category"
        with self.assertRaises(SchemaError):
            validate(scenario, json.loads(
                (HARNESS_ROOT / "harness" / "schemas" / "scenario.schema.json").read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
