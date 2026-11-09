#!/usr/bin/env python3
"""Consent-workflow regression proofs on disposable targets.

These tests exercise the tool-level half of the consent contract:

* assessment leaves the target byte-identical;
* a draft write creates only the explicitly requested path;
* a partial scope does not grow baselines, waivers, CI or plans;
* the proposal and skill carry the required approval gate and classification vocabulary.

They cannot execute an agent conversation. Scenario F (new requirement during implementation)
and the judgement half of Scenario G (asking the owner about an ambiguous role) are verified by
the written stop conditions in SKILL.md and references/15-consent-and-scope.md, not by this file.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = ROOT / "skills/acima-adoption/scripts/preflight.py"
ACIMA = ROOT / "tools/acima.py"
SKILL = ROOT / "skills/acima-adoption/SKILL.md"
PROPOSAL = ROOT / "skills/acima-adoption/assets/adoption-proposal.md"
CONSENT_REF = ROOT / "skills/acima-adoption/references/15-consent-and-scope.md"


def snapshot(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*")) if path.is_file()
    }


def fixture(tmp: Path) -> Path:
    root = tmp / "target"
    files = {
        "src/orders/order.py": "class Order:\n    pass\n",
        "src/catalog/catalog.py": "class Catalog:\n    pass\n",
        "src/shared/money.py": "class Money:\n    pass\n",
        "tests/test_orders.py": "def test_order():\n    assert True\n",
    }
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return root


def invoke(script: Path, *args: str) -> subprocess.CompletedProcess:
    result = subprocess.run([sys.executable, str(script), *args],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode in (0, 1), (result.returncode, result.stdout, result.stderr)
    return result


def test_assessment_is_read_only() -> None:
    """Scenarios A, B and E: assess, ask what adoption needs, decline adoption."""
    with tempfile.TemporaryDirectory() as directory:
        root = fixture(Path(directory))
        before = snapshot(root)

        assessed = invoke(ACIMA, "assess", "--root", str(root), "--format", "json")
        json.loads(assessed.stdout)
        preflight = invoke(PREFLIGHT, "--project", str(root), "--format", "json")
        guidance = " ".join(json.loads(preflight.stdout).get("next", [])).lower()
        assert "approval" in guidance or "approved" in guidance, guidance
        assert not json.loads(preflight.stdout)["next"][0].startswith("Generate a draft")
        invoke(ACIMA, "inspect", "--root", str(root), "--format", "json")

        assert snapshot(root) == before, "read-only commands changed the target"
        assert not (root / "acima.config.json").exists()
        assert not (root / ".acima").exists()
        assert not (root / ".github").exists()
        assert not (root / "docs/acima").exists()


def test_explicit_draft_creates_only_the_requested_config() -> None:
    """Scenario C: explicit approval of the config path creates that path only."""
    with tempfile.TemporaryDirectory() as directory:
        root = fixture(Path(directory))
        before = snapshot(root)

        invoke(PREFLIGHT, "--project", str(root), "--format", "json")
        assert snapshot(root) == before, "preflight without --write-* modified the target"

        invoke(PREFLIGHT, "--project", str(root),
               "--write-draft", "acima.config.json", "--format", "json")
        after = snapshot(root)
        added = set(after) - set(before)
        assert added == {"acima.config.json"}, f"unexpected files created: {sorted(added)}"
        assert set(before) - set(after) == set(), "assessment or draft removed a target file"

        config = json.loads((root / "acima.config.json").read_text(encoding="utf-8"))
        assert config["_generatedBy"] == "acima-adoption preflight --write-draft"
        assert "Heuristic" in config["_note"]
        assert config["units"], "draft must contain proposed units, not an empty map"


def test_partial_scope_does_not_grow_artifacts() -> None:
    """Scenario D: config only; no baseline, waivers, CI, plans or source edits."""
    with tempfile.TemporaryDirectory() as directory:
        root = fixture(Path(directory))
        before = snapshot(root)
        invoke(PREFLIGHT, "--project", str(root),
               "--write-draft", "acima.config.json", "--format", "json")

        assert not (root / ".acima").exists(), "partial scope created .acima/"
        assert not (root / ".github").exists(), "partial scope created CI"
        assert not (root / "docs").exists(), "partial scope created docs or plans"
        changed = {path for path, digest in snapshot(root).items()
                   if before.get(path) not in (None, digest)}
        assert changed == set(), f"partial scope changed source or tests: {sorted(changed)}"

        skill = SKILL.read_text(encoding="utf-8")
        reference = CONSENT_REF.read_text(encoding="utf-8")
        assert "approval covers the listed scope only" in skill.lower()
        assert "approval covers only what was shown" in " ".join(reference.lower().split())
        assert "partial" in reference.lower()


def test_proposal_contract_is_reviewable() -> None:
    """Scenario B: the proposal names scope, paths, status, decisions, costs and one question."""
    proposal = PROPOSAL.read_text(encoding="utf-8")
    skill = SKILL.read_text(encoding="utf-8")
    reference = CONSENT_REF.read_text(encoding="utf-8")

    for heading in ("## 1. Recommendation", "## 2. Proposed scope",
                    "## 3. Files to be created or modified", "## 4. Proposed module map",
                    "## 5. Architectural decisions required", "## 6. Tradeoffs and maintenance",
                    "## 7. Approval"):
        assert heading in proposal, heading
    assert "Required" in proposal and "Conditional" in proposal and "Optional" in proposal
    assert "What this will not accomplish" in proposal
    assert "Would you like me to proceed with this adoption plan and create the listed files and changes?" in proposal
    assert "No persistent repository changes have been made" in proposal
    assert "Analysis is never authorization" in " ".join(skill.split())
    assert "Analysis is not authorization to adopt" in " ".join(reference.split())
    assert "explicit approval" in reference.lower()
    assert "Merge, publish or release" in skill


def test_ambiguous_mapping_stays_a_proposal() -> None:
    """Scenario G (tool half): heuristic roles are labelled and never written without a request."""
    with tempfile.TemporaryDirectory() as directory:
        root = fixture(Path(directory))
        before = snapshot(root)
        result = invoke(PREFLIGHT, "--project", str(root), "--format", "json")
        payload = json.loads(result.stdout)
        units = payload.get("proposedUnits") or []
        assert units, "fixture should produce candidate units"
        assert all(unit.get("role") for unit in units), units
        assert any(unit.get("paths") == ["src/shared"] for unit in units), units
        assert snapshot(root) == before
        assert not (root / "acima.config.json").exists()

        invoke(PREFLIGHT, "--project", str(root),
               "--write-draft", "acima.config.json", "--format", "json")
        config = json.loads((root / "acima.config.json").read_text(encoding="utf-8"))
        assert "Heuristic" in config["_note"]
        assert "Review module names" in config["_note"]
        reference = CONSENT_REF.read_text(encoding="utf-8")
        for word in ("Discovered project", "Confirmed module", "Supporting library",
                     "Shared kernel", "Host / composition root", "Test project", "Uncertain"):
            assert word in reference, word


def main() -> int:
    tests = [value for name, value in sorted(globals().items())
             if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"{len(tests)} consent-workflow tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
