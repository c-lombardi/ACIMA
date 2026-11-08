"""Pin the exclusion contract across the reference enforcers.

A literal path excludes that file or directory subtree. It must not exclude a
sibling whose name only starts with the same text. A bare segment keeps the
legacy "any directory with this name" behaviour. Glob patterns remain globs.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENFORCERS = {
    "python": {
        "extension": ".py",
        "command": [sys.executable, str(ROOT / "examples/python/tools/acima_arch.py")],
    },
    "typescript": {
        "extension": ".ts",
        "command": ["node", str(ROOT / "examples/typescript/tools/acima-arch.mjs")],
    },
}


def write_fixture(root: Path, extension: str) -> None:
    files = {
        "src/app": "VALUE = 1\n",
        "packages/tests/ignored": "VALUE = 2\n",
        "packages/tests-extra/visible": "VALUE = 3\n",
        "packages/generated/ignored_test": "VALUE = 4\n",
    }
    for stem, source in files.items():
        path = root / f"{stem}{extension}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
    config = {
        "standard": "1.0.0",
        "language": extension == ".py" and "python" or "typescript",
        "level": "L1",
        "root": ".",
        "units": [
            {
                "id": "app",
                "module": "app",
                "role": "implementation",
                "paths": ["src"],
            }
        ],
        "exclude": ["packages/tests", "**/*_test" + extension],
    }
    (root / "acima.config.json").write_text(json.dumps(config, indent=2) + "\n",
                                             encoding="utf-8")


def run_enforcer(language: str, root: Path) -> dict:
    result = subprocess.run(
        ENFORCERS[language]["command"] + [
            "--root", str(root), "--config", "acima.config.json", "--format", "json",
        ],
        cwd=ROOT, capture_output=True, text=True,
    )
    if not result.stdout.strip():
        raise AssertionError(f"{language} enforcer produced no JSON: {result.stderr}")
    return json.loads(result.stdout)


class ExclusionContractTests(unittest.TestCase):
    def test_literal_directory_and_glob_exclusions_are_prefix_safe(self) -> None:
        for language, spec in ENFORCERS.items():
            with self.subTest(language=language), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                write_fixture(root, spec["extension"])
                payload = run_enforcer(language, root)
                actual = {(item["rule"], item["path"]) for item in payload["findings"]}
                expected = {
                    ("ACIMA-G005", f"packages/tests-extra/visible{spec['extension']}"),
                }
                self.assertEqual(actual, expected,
                                 f"{language}: exclusion matched the wrong paths")
                self.assertGreaterEqual(payload["sourceFiles"], 1)


if __name__ == "__main__":
    unittest.main()
