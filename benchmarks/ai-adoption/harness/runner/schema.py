"""A deliberately small JSON Schema validator.

The repository is standard-library only, so the harness validates its own records against the
documented schemas without adding a dependency. Supported keywords are the ones the schemas in
``../schemas`` actually use; an unsupported keyword is an error rather than a silent pass, so a
schema cannot quietly stop enforcing something.
"""
from __future__ import annotations

import re

SUPPORTED = frozenset({
    "$schema", "$id", "$defs", "title", "description", "default", "examples",
    "type", "enum", "const", "properties", "required", "additionalProperties",
    "items", "minItems", "maxItems", "minimum", "maximum", "minLength", "maxLength", "pattern",
})

TYPE_NAMES = frozenset({"object", "array", "string", "integer", "number", "boolean", "null"})


class SchemaError(ValueError):
    def __init__(self, path: str, message: str) -> None:
        super().__init__(f"{path}: {message}")
        self.path = path
        self.message = message


def _type_matches(value: object, name: str) -> bool:
    if name == "object":
        return isinstance(value, dict)
    if name == "array":
        return isinstance(value, list)
    if name == "string":
        return isinstance(value, str)
    if name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if name == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if name == "boolean":
        return isinstance(value, bool)
    if name == "null":
        return value is None
    raise SchemaError("$", f"unsupported type name {name!r}")


def _check_supported(schema: dict, path: str) -> None:
    unknown = set(schema) - SUPPORTED
    if unknown:
        raise SchemaError(path, f"unsupported schema keyword(s): {', '.join(sorted(unknown))}")


def validate(instance: object, schema: dict, path: str = "$") -> None:
    """Raise SchemaError on the first violation. Returns None when the instance conforms."""
    if not isinstance(schema, dict):
        raise SchemaError(path, "schema must be an object")
    _check_supported(schema, path)

    if "type" in schema:
        declared = schema["type"]
        names = declared if isinstance(declared, list) else [declared]
        for name in names:
            if name not in TYPE_NAMES:
                raise SchemaError(path, f"unsupported type name {name!r}")
        if not any(_type_matches(instance, name) for name in names):
            raise SchemaError(path, f"expected {' or '.join(names)}, got {type(instance).__name__}")

    if "const" in schema and instance != schema["const"]:
        raise SchemaError(path, f"expected constant {schema['const']!r}")
    if "enum" in schema and instance not in schema["enum"]:
        raise SchemaError(path, f"value {instance!r} is not one of {schema['enum']}")

    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            raise SchemaError(path, f"shorter than {schema['minLength']} characters")
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            raise SchemaError(path, f"longer than {schema['maxLength']} characters")
        if "pattern" in schema and re.search(schema["pattern"], instance) is None:
            raise SchemaError(path, f"does not match {schema['pattern']!r}")

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            raise SchemaError(path, f"less than minimum {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            raise SchemaError(path, f"greater than maximum {schema['maximum']}")

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            raise SchemaError(path, f"fewer than {schema['minItems']} items")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            raise SchemaError(path, f"more than {schema['maxItems']} items")
        if "items" in schema:
            for index, item in enumerate(instance):
                validate(item, schema["items"], f"{path}[{index}]")

    if isinstance(instance, dict):
        for name in schema.get("required", []):
            if name not in instance:
                raise SchemaError(path, f"missing required property {name!r}")
        properties = schema.get("properties", {})
        for name, value in instance.items():
            if name in properties:
                validate(value, properties[name], f"{path}.{name}")
                continue
            additional = schema.get("additionalProperties", True)
            if additional is False:
                raise SchemaError(path, f"unexpected property {name!r}")
            if isinstance(additional, dict):
                validate(value, additional, f"{path}.{name}")
