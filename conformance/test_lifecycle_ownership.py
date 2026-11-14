"""Contract tests for A007/A008/A009: deliberate lifecycle and state ownership."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = [sys.executable, str(ROOT / "examples/python/tools/acima_arch.py")]
TYPESCRIPT = ["node", str(ROOT / "examples/typescript/tools/acima-arch.mjs")]
FIXTURES = ROOT / "conformance/fixtures/lifecycle"


def run(command: list[str], root: Path, config: str = "acima.config.json"):
    result = subprocess.run(command + ["--root", str(root), "--config", config,
                                       "--format", "json"],
                            capture_output=True, text=True)
    if not result.stdout.strip():
        raise AssertionError(result.stderr or "the enforcer printed nothing")
    return result, json.loads(result.stdout)


def paths_by_rule(report: dict) -> dict[str, set[str]]:
    fired: dict[str, set[str]] = {}
    for finding in report["findings"]:
        fired.setdefault(finding["rule"], set()).add(finding["path"])
    return fired


class LifecycleOwnershipTests(unittest.TestCase):
    def test_catalog_declares_three_rules_with_the_ratchet(self) -> None:
        catalog = json.loads((ROOT / "tools/acima-spec/rules.json").read_text(encoding="utf-8"))
        rules = {rule["id"]: rule for rule in catalog["rules"]}
        for rule_id in ("ACIMA-A007", "ACIMA-A008", "ACIMA-A009"):
            rule = rules[rule_id]
            self.assertEqual(rule["level"], "L3")
            self.assertEqual(rule["severity"], "warning")
            self.assertEqual(rule["severityRatchet"], {"to": "error", "at": "2.0.0"})
            self.assertEqual(rule["automation"], "automated")
        self.assertEqual(len(catalog["rules"]), 56)

    def test_python_gallery_fires_all_three_rules(self) -> None:
        result, report = run(PYTHON, ROOT / "examples/python", "acima.gallery.config.json")
        self.assertEqual(result.returncode, 1)
        fired = paths_by_rule(report)
        for rule in ("ACIMA-A007", "ACIMA-A008", "ACIMA-A009"):
            self.assertEqual(fired[rule], {"violations/lifecycle_registration.py"})

    def test_typescript_gallery_fires_all_three_rules(self) -> None:
        result, report = run(TYPESCRIPT, ROOT / "examples/typescript", "acima.gallery.config.json")
        self.assertEqual(result.returncode, 1)
        fired = paths_by_rule(report)
        for rule in ("ACIMA-A007", "ACIMA-A008", "ACIMA-A009"):
            self.assertEqual(fired[rule], {"violations/lifecycle_registration.ts"})

    def test_a007_allows_readonly_dependencies_but_requires_one_required_constructor(self) -> None:
        python_source = '''
class Clock:
    pass

class Injected:
    def __init__(self, clock: Clock):
        self._clock = clock

class Defaulted:
    def __init__(self, clock: Clock, retries=3):
        self._clock = clock

class Mutated:
    def __init__(self, clock: Clock):
        self._clock = clock

    def reset(self):
        self._clock = None

class Multiple:
    def __init__(self, clock: Clock):
        self._clock = clock

    def __init__(self, clock: Clock, other=None):
        self._clock = clock

register(Injected, lifetime="transient")
register(Defaulted, lifetime="transient")
register(Mutated, lifetime="transient")
register(Multiple, lifetime="transient")
'''
        typescript_source = '''
class Clock {}

class Injected {
  constructor(private readonly clock: Clock) {}
}

class Defaulted {
  constructor(private readonly clock: Clock, retries = 3) {}
}

class Mutated {
  constructor(private readonly clock: Clock) {}
  reset(): void { this.clock = null as unknown as Clock; }
}

class Multiple {
  constructor(private readonly clock: Clock) {}
  constructor(private readonly clock: Clock, other?: unknown) {}
}

register(Injected, { lifetime: 'transient' });
register(Defaulted, { lifetime: 'transient' });
register(Mutated, { lifetime: 'transient' });
register(Multiple, { lifetime: 'transient' });
'''
        for language, command, source in (("python", PYTHON, python_source),
                                          ("typescript", TYPESCRIPT, typescript_source)):
            with tempfile.TemporaryDirectory(prefix=f"acima-a007-{language}-") as temporary:
                root = Path(temporary)
                (root / "src/host").mkdir(parents=True)
                suffix = ".py" if language == "python" else ".ts"
                (root / "src/host" / ("main" + suffix)).write_text(source, encoding="utf-8")
                (root / "acima.config.json").write_text(json.dumps({
                    "standard": "1.6.0-draft.1", "mode": "base", "language": language,
                    "level": "L3", "units": [{"id": "host", "role": "host", "paths": ["src/host"]}],
                }), encoding="utf-8")
                result, report = run(command, root)
            a007 = [finding for finding in report["findings"] if finding["rule"] == "ACIMA-A007"]
            self.assertTrue(a007, (language, report["findings"]))
            self.assertEqual(len(a007), 1, (language, a007))
            self.assertIn("Injected", a007[0]["message"], (language, a007))

    def test_positive_fixtures_are_clean(self) -> None:
        for language, command in (("python", PYTHON), ("typescript", TYPESCRIPT)):
            result, report = run(command, FIXTURES / language)
            self.assertEqual(result.returncode, 0, report["findings"])
            self.assertEqual(report["findings"], [])
            for rule in ("ACIMA-A007", "ACIMA-A008", "ACIMA-A009"):
                self.assertTrue(report["execution"][rule]["executed"])

    def test_chapter_states_the_decision_model_and_limits(self) -> None:
        chapter = (ROOT / "docs/standard/17-lifecycle-and-state-ownership.md").read_text(encoding="utf-8")
        for phrase in ("stateless", "captive", "mutable state", "tenant", "resource", "manual"):
            self.assertIn(phrase.lower(), chapter.lower())


if __name__ == "__main__":
    unittest.main()
