"""Canonical paths for ACIMA-generated artifacts.

All new writes belong under ``acima/``. The root ``acima.config.json`` remains the
human-authored unit contract. Legacy ``.acima/`` and ``docs/acima/`` paths are accepted
for reads so existing repositories can migrate without losing evidence.
"""
from __future__ import annotations

from pathlib import Path

HOME = "acima"
CONFIG = "acima.config.json"
README = "acima/README.md"

STATE = "acima/state.json"
EVIDENCE = "acima/evidence"
REPORT = "acima/report"
HANDOFF = "acima/handoff"
AGENT_GUIDANCE = "acima/handoff/agent-guidance"
TOOLING = "acima/tooling"
OPTIONAL = "acima/optional"

PREFLIGHT = f"{EVIDENCE}/preflight.json"
QUALITATIVE_REVIEW = f"{EVIDENCE}/qualitative-review.json"
ASSESSMENT = f"{EVIDENCE}/assessment.json"
MODULE_MAP_PROPOSAL = f"{EVIDENCE}/module-map.proposal.json"
MODULE_MAP_DECISIONS = f"{EVIDENCE}/module-map.decisions.json"
MODULE_MAP_APPROVAL = f"{EVIDENCE}/module-map.approval.json"
SCOPE = f"{EVIDENCE}/adoption-scope.json"
ENFORCEMENT = f"{EVIDENCE}/enforcement.json"
ENFORCEMENT_PROPOSAL = f"{REPORT}/enforcement-proposal.json"
ARCHITECTURE_TESTS = f"{EVIDENCE}/architecture-tests.json"
CI = f"{EVIDENCE}/ci-integration.json"
CI_PROPOSAL = f"{REPORT}/ci-proposal.json"
VERIFICATION = f"{EVIDENCE}/verification.json"
REMEDIATION_PLAN = f"{EVIDENCE}/remediation-plan.json"
REMEDIATION_RESULT = f"{EVIDENCE}/remediation-result.json"
WAIVERS = f"{EVIDENCE}/waivers.json"
BASELINE = f"{EVIDENCE}/baseline.json"
MANUAL_EVIDENCE = f"{EVIDENCE}/manual-evidence.json"
TRIAGE = f"{EVIDENCE}/triage.json"
AGENT_GUIDANCE_RECORD = f"{EVIDENCE}/agent-guidance.json"

ADOPTION_PROPOSAL = f"{REPORT}/adoption-proposal.md"
ADOPTION_PROPOSAL_JSON = f"{REPORT}/adoption-proposal.json"
ADOPTION_NOTIFICATIONS_PROPOSAL = f"{REPORT}/adoption-notifications-proposal.json"
AGENT_GUIDANCE_PROPOSAL = f"{REPORT}/agent-guidance-proposal.md"
HANDOFF_FILE = f"{HANDOFF}/adoption-handoff.md"
DEVELOPER_GUIDE = f"{HANDOFF}/developer-guide.md"
REPORT_DATA = f"{REPORT}/report-data.json"

LEGACY_STATE = ".acima/adoption-workflow.json"
LEGACY_REVIEWS = (
    "docs/acima/qualitative-review.json",
    ".acima/qualitative-review.json",
)
LEGACY_SCOPES = (
    ".acima/adoption-scope.json",
    "docs/acima/adoption-scope.json",
)
LEGACY_WAIVERS = (".acima/waivers.json",)
LEGACY_BASELINE = (".acima/baseline.json",)
LEGACY_MANUAL_EVIDENCE = (".acima/manual-evidence.json",)
LEGACY_TRIAGE = (".acima/triage.json",)
LEGACY_APPROVAL = (".acima/module-map.approval.json",)
LEGACY_ENFORCEMENT = ("docs/acima/enforcement.json",)
LEGACY_VERIFICATION = ("docs/acima/verification.json",)
LEGACY_CI = ("docs/acima/ci-integration.json",)
LEGACY_AGENT_GUIDANCE = (".acima/agent-guidance.json",)


def existing(root: Path, *paths: str) -> Path | None:
    """Return the first existing repository-relative artifact, preserving read compatibility."""
    for relative in paths:
        candidate = root / relative
        if candidate.is_file():
            return candidate
    return None


def existing_or_default(root: Path, canonical: str, *legacy: str) -> Path:
    """Return an existing legacy path, otherwise the canonical path for a new write."""
    return existing(root, canonical, *legacy) or (root / canonical)
