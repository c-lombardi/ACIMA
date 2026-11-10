"""Provenance and frozen run configuration.

Everything recorded here is measured from the checkout the run actually used: the skill content
hash, the catalog hash, the standard version and the instruction template hash. A mismatch between
the skill manifest and the catalog on disk is a configuration failure, not a warning — a benchmark
that silently measures a different skill than it claims is worthless.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, fields
from pathlib import Path

from .lifecycle import InvalidConfiguration

HARNESS_VERSION = "1.0.0-m1"
SCHEMA_VERSION = 1
SKILL_DIR = Path("skills/acima-adoption")
CATALOG_PATH = Path("tools/acima-spec/rules.json")
MANIFEST_PATH = SKILL_DIR / "manifest.json"
INSTRUCTIONS = {
    "read-only": Path("scenarios/instructions/read-only-assessment.md"),
    "authorized-adoption": Path("scenarios/instructions/authorized-adoption.md"),
}

IGNORED_DIRECTORIES = frozenset({".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".DS_Store"})


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_tree(root: Path, *, exclude: frozenset[str] = IGNORED_DIRECTORIES) -> tuple[str, int, int]:
    """Content identity of a directory: sorted relative path and file hash for every file."""
    root = Path(root)
    digest = hashlib.sha256()
    count = 0
    total = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in exclude for part in relative.parts):
            continue
        size = path.stat().st_size
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256_file(path).encode("ascii"))
        digest.update(b"\n")
        count += 1
        total += size
    return digest.hexdigest(), count, total


def file_manifest(root: Path, *, exclude: frozenset[str] = IGNORED_DIRECTORIES) -> dict[str, str]:
    root = Path(root)
    manifest: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in exclude for part in relative.parts):
            continue
        manifest[relative.as_posix()] = sha256_file(path)
    return manifest


def manifest_sha256(manifest: dict[str, str]) -> str:
    digest = hashlib.sha256()
    for name in sorted(manifest):
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(manifest[name].encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def load_json(path: Path) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise InvalidConfiguration(f"missing file: {path}") from error
    except json.JSONDecodeError as error:
        raise InvalidConfiguration(f"invalid JSON in {path}: {error}") from error


@dataclass(frozen=True)
class Limits:
    """Controller-owned limits, frozen before the adapter sees them."""

    execution_timeout_seconds: int
    max_model_calls: int
    max_tokens: int
    max_container_memory_mb: int
    max_cpus: int
    max_disk_mb: int
    max_processes: int
    max_concurrent_runs: int
    max_correction_attempts: int
    max_captured_bytes: int
    max_output_bytes: int
    max_files: int

    def as_dict(self) -> dict:
        """The configured names, as they appear in config.json and in run records."""
        return {LIMIT_CONFIG_KEYS[field.name]: getattr(self, field.name) for field in fields(self)}


LIMIT_KEYS = {field.name for field in fields(Limits)}


def _snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(part.title() for part in parts[1:])


# snake_case attribute -> camelCase key used in config.json and run records.
LIMIT_CONFIG_KEYS = {name: _camel(name) for name in LIMIT_KEYS}


def build_limits(config: dict) -> Limits:
    raw = config.get("limits")
    if not isinstance(raw, dict):
        raise InvalidConfiguration("config.limits is missing")
    normalised: dict[str, int] = {}
    unknown = []
    for key, value in raw.items():
        snake = _snake(key)
        if snake not in LIMIT_KEYS:
            unknown.append(key)
            continue
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise InvalidConfiguration(f"limit {key} must be a positive integer")
        normalised[snake] = value
    if unknown:
        raise InvalidConfiguration(f"unknown limits: {', '.join(sorted(unknown))}")
    missing = LIMIT_KEYS - set(normalised)
    if missing:
        raise InvalidConfiguration(
            "missing limits: " + ", ".join(sorted(LIMIT_CONFIG_KEYS[name] for name in missing))
        )
    return Limits(**normalised)


def load_config(harness_root: Path) -> tuple[dict, Limits]:
    config = load_json(harness_root / "config.json")
    if config.get("version") != 1:
        raise InvalidConfiguration("config.version must be 1")
    return config, build_limits(config)


def catalog_provenance(acima_root: Path) -> dict:
    catalog = load_json(acima_root / CATALOG_PATH)
    rules = catalog.get("rules") or []
    manual = [rule for rule in rules if rule.get("automation") == "manual"]
    return {
        "version": str(catalog.get("version", "")),
        "sha256": sha256_file(acima_root / CATALOG_PATH),
        "rules": len(rules),
        "portable": len(rules) - len(manual),
    }


def skill_provenance(acima_root: Path) -> dict:
    skill_root = acima_root / SKILL_DIR
    manifest = load_json(skill_root / "manifest.json")
    content_hash, files, total = hash_tree(skill_root)
    catalog = catalog_provenance(acima_root)
    pinned = (manifest.get("catalog") or {}).get("sha256")
    if pinned != catalog["sha256"]:
        raise InvalidConfiguration(
            "skill manifest catalog hash does not match tools/acima-spec/rules.json; "
            "the benchmark would measure an unpinned skill"
        )
    return {
        "name": str(manifest.get("skill", "acima-adoption")),
        "version": str(manifest.get("skillVersion", "")),
        "contentSha256": content_hash,
        "files": files,
        "bytes": total,
        "path": SKILL_DIR.as_posix(),
        "standard": str(manifest.get("standard", catalog["version"])),
    }


def collection_provenance(acima_root: Path) -> dict:
    skill = skill_provenance(acima_root)
    catalog = catalog_provenance(acima_root)
    return {
        "skill": skill,
        "standard": {"version": skill["standard"]},
        "catalog": catalog,
        "harness": {"version": HARNESS_VERSION},
    }


def instruction_bundle(harness_root: Path, mode: str, values: dict[str, str]) -> dict:
    template_path = INSTRUCTIONS.get(mode)
    if template_path is None:
        raise InvalidConfiguration(f"unknown execution mode {mode!r}")
    path = Path(harness_root) / template_path
    try:
        template = path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise InvalidConfiguration(f"missing instruction template: {path}") from error
    text = template
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    missing = sorted(set(part.split("}}")[0] for part in text.split("{{")[1:]))
    if missing:
        raise InvalidConfiguration(f"unfilled instruction placeholders: {', '.join(missing)}")
    return {
        "id": template_path.name,
        "path": template_path.as_posix(),
        "sha256": sha256_bytes(text.encode("utf-8")),
        "text": text,
    }


def approval_provenance(path: Path | None) -> dict | None:
    if path is None:
        return None
    payload = load_json(path)
    for key in ("approvedBy", "approvedOn", "paths"):
        if key not in payload:
            raise InvalidConfiguration(f"approval record is missing {key!r}")
    if not payload["paths"]:
        raise InvalidConfiguration("approval record approves no paths")
    payload = dict(payload)
    payload["sha256"] = sha256_file(path)
    payload["approvedPaths"] = list(payload["paths"])
    return payload
