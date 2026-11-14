"""CI socket and shrink-only baseline for ACIMA adoption.

The module has two independent responsibilities:

* plan and install a provider-specific CI step without overwriting a repository's workflow;
* classify enforcer findings against a stable-fingerprint baseline so existing debt is a warning
  and new debt is an error.

Nothing here runs a remote pipeline or claims that one ran. The generated runner reads the copied
enforcer command from ``acima/evidence/enforcement.json`` and fails closed on missing or malformed
input.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

CI_FILE = "acima/evidence/ci-integration.json"
PLAN_FILE = "acima/evidence/ci-plan.json"
BASELINE_FILE = "acima/evidence/ci-baseline.json"
OBSERVED_FILE = "acima/evidence/gate-observed.json"
WORKFLOW_FILE = ".github/workflows/acima.yml"
RUNNER_FILE = "acima/tooling/acima_baseline.py"
SCHEMA_VERSION = 1


class CiError(ValueError):
    """A CI plan, approval or baseline is not usable."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CiError("cannot read %s: %s" % (path, error)) from error
    if not isinstance(value, dict):
        raise CiError("%s must contain a JSON object" % path)
    return value


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def discover(root: Path) -> dict:
    """Detect the existing provider without changing anything."""
    github = []
    workflow_dir = root / ".github/workflows"
    if workflow_dir.is_dir():
        github = sorted(workflow_dir.glob("*.yml")) + sorted(workflow_dir.glob("*.yaml"))
    if github:
        return {"provider": "github-actions",
                "existing": [path.relative_to(root).as_posix() for path in github],
                "workflowPath": WORKFLOW_FILE,
                "integration": "existing-provider"}
    for provider, name in (("gitlab-ci", ".gitlab-ci.yml"),
                           ("azure-devops", "azure-pipelines.yml"),
                           ("jenkins", "Jenkinsfile")):
        if (root / name).is_file():
            return {"provider": provider, "existing": [name], "workflowPath": name,
                    "integration": "existing-provider"}
    return {"provider": None, "existing": [], "workflowPath": None,
            "integration": "none"}


def _command(root: Path) -> str | None:
    enforcement = root / "acima/evidence/enforcement.json"
    if not enforcement.is_file():
        return None
    try:
        document = _read(enforcement)
    except CiError:
        return None
    enforcer = document.get("enforcer") or {}
    return enforcer.get("command") or None


def plan(root: Path, *, configured: bool = False) -> dict:
    """Create the reviewable CI plan. This function writes only the plan artifact."""
    root = root.resolve()
    discovery = discover(root)
    command = _command(root)
    provider = discovery.get("provider")
    if not command:
        status = "blocked"
        reason = "No executable enforcer command exists; finish local enforcement first."
    elif not provider:
        status = "no_provider"
        reason = "No supported CI provider was detected. The local command remains the gate."
    elif provider != "github-actions":
        status = "manual_instructions"
        reason = "The provider is detected but this release does not rewrite its configuration."
    elif (root / WORKFLOW_FILE).is_file():
        status = "already_present"
        reason = "The ACIMA workflow already exists; it is never overwritten."
    else:
        status = "ready"
        reason = "A dedicated workflow can be added without touching existing workflows."
    instructions = []
    if status == "no_provider":
        instructions = [
            "No CI provider was detected. Keep the local enforcement command in the developer workflow.",
            "When CI is added, run the generated baseline command on pull requests and fail on a non-zero exit.",
        ]
    elif status == "manual_instructions":
        instructions = [
            "Add the generated baseline command to the detected provider's pull-request validation stage.",
            "Fail the job on a non-zero exit code and preserve its output as an artifact.",
        ]
    document = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "acima-ci-plan",
        "generatedAt": _now(),
        "provider": provider,
        "instructions": instructions,
        "existing": discovery.get("existing") or [],
        "workflowPath": discovery.get("workflowPath"),
        "command": command,
        "baselineCommand": "python3 %s --root . --config acima.config.json" % RUNNER_FILE,
        "baselinePath": BASELINE_FILE,
        "status": status,
        "reason": reason,
        "configured": bool(configured),
        "claim": "Configured locally only; no remote CI run is observed or claimed.",
        "approvalRequired": status in {"ready", "already_present"},
        "plannedWrite": WORKFLOW_FILE if status == "ready" else None,
    }
    _write(root / PLAN_FILE, document)
    return document


def _workflow(command: str) -> str:
    return (
        "name: ACIMA architecture\n"
        "on:\n  pull_request:\n  merge_group:\n"
        "jobs:\n  architecture:\n    runs-on: ubuntu-latest\n    steps:\n"
        "      - uses: actions/checkout@v4\n"
        "      - name: Run ACIMA enforcement against the recorded baseline\n"
        "        run: python3 %s --root . --config acima.config.json\n" % RUNNER_FILE
    )


def approve(root: Path, *, plan_sha256: str, reviewed_by: str) -> dict:
    """Approve the exact plan and install only the file the plan names."""
    root = root.resolve()
    plan_path = root / PLAN_FILE
    if not plan_path.is_file():
        raise CiError("no CI plan exists; run ci --plan first")
    approved_by = str(reviewed_by or "").strip()
    if not approved_by:
        raise CiError("CI approval requires the name of the reviewing owner")
    if not plan_sha256 or plan_sha256 != _sha(plan_path):
        raise CiError("CI approval requires the exact SHA-256 of the current plan")
    document = _read(plan_path)
    status = document.get("status")
    if status == "ready":
        target = root / str(document.get("plannedWrite") or WORKFLOW_FILE)
        if target.exists():
            raise CiError("the planned workflow appeared after the plan was generated; regenerate the plan")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(_workflow(document.get("command") or ""), encoding="utf-8")
        integration = "generated-workflow"
    elif status == "already_present":
        integration = "existing-workflow"
    elif status == "manual_instructions":
        integration = "manual_instructions"
    elif status == "no_provider":
        integration = "no_provider"
    else:
        raise CiError("the CI plan is %s and cannot be approved: %s"
                      % (status, document.get("reason") or "no reason recorded"))
    result = {
        "schemaVersion": SCHEMA_VERSION,
        "provider": document.get("provider"),
        "existing": document.get("existing") or [],
        "workflow": (document.get("plannedWrite")
                     if status == "ready" else document.get("workflowPath")),
        "command": document.get("command"),
        "baselineCommand": document.get("baselineCommand"),
        "baselinePath": BASELINE_FILE,
        "instructions": document.get("instructions") or [],
        "status": ("configured" if status == "ready" else status),
        "integration": integration,
        "approvedBy": approved_by,
        "approvedOn": datetime.now(timezone.utc).date().isoformat(),
        "planSha256": _sha(plan_path),
        "configuredAt": _now() if status in {"ready", "already_present"} else None,
        "observedAt": None,
        "observed": False,
        "claim": ("No CI provider was detected; no CI run was observed or claimed."
                  if status == "no_provider" else
                  "Configured locally; no CI run was observed or claimed."
                  if status in {"ready", "already_present", "manual_instructions"}
                  else "No CI integration was made."),
    }
    _write(root / CI_FILE, result)
    document["configured"] = status in {"ready", "already_present"}
    document["approvedBy"] = approved_by
    _write(plan_path, document)
    return result


def decline(root: Path, *, reviewed_by: str, reason: str = "") -> dict:
    """Record a declined CI decision without writing a workflow."""
    root = root.resolve()
    owner = str(reviewed_by or "").strip()
    if not owner:
        raise CiError("declining CI requires the name of the owner")
    result = {
        "schemaVersion": SCHEMA_VERSION,
        "provider": discover(root).get("provider"),
        "status": "declined",
        "integration": "declined",
        "approvedBy": owner,
        "approvedOn": datetime.now(timezone.utc).date().isoformat(),
        "reason": str(reason or "").strip(),
        "claim": "CI was declined. Local enforcement continues; no ratchet is claimed.",
    }
    _write(root / CI_FILE, result)
    return result


def observe(root: Path) -> dict:
    """Attach a recorded local observation without turning it into a remote claim."""
    root = root.resolve()
    result = _read(root / CI_FILE) if (root / CI_FILE).is_file() else {}
    observed = _read(root / OBSERVED_FILE) if (root / OBSERVED_FILE).is_file() else None
    result["observed"] = bool(observed)
    result["observedAt"] = observed.get("executedAt") if observed else None
    if observed and not result.get("observedClaim"):
        result["observedClaim"] = ("A local observation artifact exists; it is not independently "
                                   "verified and is not a remote CI run.")
    _write(root / CI_FILE, result)
    return result


# ---------------------------------------------------------------------------------------------
# Baseline ratchet


def _normal(value: object) -> str:
    return str(value or "").replace("\\", "/").strip()


def fingerprint(finding: dict) -> str:
    """Use the enforcer fingerprint; otherwise derive one from stable fields, never a line."""
    supplied = str(finding.get("fingerprint") or "").strip().lower()
    if supplied.startswith("sha256:") and len(supplied) == 71:
        return supplied
    if len(supplied) == 64 and all(character in "0123456789abcdef" for character in supplied):
        return "sha256:" + supplied
    anchor = (finding.get("evidence") or finding.get("symbol") or finding.get("message") or "")
    material = "\0".join((str(finding.get("rule") or ""), _normal(finding.get("path")),
                          str(anchor)[:160]))
    return "sha256:" + hashlib.sha256(material.encode("utf-8")).hexdigest()


def build_baseline(findings: list[dict], *, revision: str = "", source: str = "first-run") -> dict:
    entries = []
    seen = set()
    for finding in findings or []:
        item = fingerprint(finding)
        if item in seen:
            continue
        seen.add(item)
        entries.append({
            "fingerprint": item,
            "rule": finding.get("rule"),
            "path": _normal(finding.get("path")),
            "severity": finding.get("severity"),
            "message": finding.get("message"),
        })
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "acima-ci-baseline",
        "createdAt": _now(),
        "revision": revision,
        "source": source,
        "entries": sorted(entries, key=lambda item: item["fingerprint"]),
    }


def save_baseline(root: Path, document: dict) -> Path:
    path = root / BASELINE_FILE
    _write(path, document)
    return path


def load_baseline(root: Path) -> dict:
    path = root / BASELINE_FILE
    if not path.is_file():
        return {"schemaVersion": SCHEMA_VERSION, "kind": "acima-ci-baseline",
                "entries": [], "createdAt": None}
    document = _read(path)
    if document.get("kind") != "acima-ci-baseline":
        raise CiError("%s is not an ACIMA CI baseline" % BASELINE_FILE)
    return document


def evaluate(findings: list[dict], baseline: dict) -> dict:
    """Classify findings and return the shrink-only baseline implied by this run."""
    known = {str(item.get("fingerprint")) for item in baseline.get("entries") or []
             if isinstance(item, dict) and item.get("fingerprint")}
    warnings, errors = [], []
    current = set()
    for finding in findings or []:
        item = fingerprint(finding)
        current.add(item)
        row = {"fingerprint": item, "rule": finding.get("rule"),
               "path": _normal(finding.get("path")), "message": finding.get("message")}
        (warnings if item in known else errors).append(row)
    resolved = sorted(known - current)
    pruned = {
        **baseline,
        "entries": [item for item in baseline.get("entries") or []
                    if isinstance(item, dict) and item.get("fingerprint") in current],
        "updatedAt": _now(),
    }
    return {
        "status": "new-findings" if errors else "clean",
        "warnings": warnings,
        "errors": errors,
        "resolved": resolved,
        "baseline": pruned,
        "warningCount": len(warnings),
        "errorCount": len(errors),
    }


def record_initial(root: Path, findings: list[dict], *, revision: str = "") -> dict:
    """Create the baseline once. A second call never grows it."""
    path = root / BASELINE_FILE
    if path.is_file():
        raise CiError("a CI baseline already exists; resolve findings instead of replacing it")
    document = build_baseline(findings, revision=revision)
    save_baseline(root, document)
    return document


def reviewed_growth(root: Path, findings: list[dict], *, owner: str, reason: str,
                    reviewed_on: str, baseline_sha256: str) -> dict:
    """The only path that may add entries, with explicit provenance."""
    owner = str(owner or "").strip()
    reason = str(reason or "").strip()
    if not owner or not reason or not reviewed_on:
        raise CiError("a baseline update requires owner, reason and reviewed date")
    path = root / BASELINE_FILE
    if not path.is_file():
        raise CiError("no baseline exists; record the first baseline instead")
    if not baseline_sha256 or baseline_sha256 != _sha(path):
        raise CiError("the baseline update must name the exact current baseline digest")
    current = load_baseline(root)
    known = {item.get("fingerprint") for item in current.get("entries") or []}
    additions = []
    for finding in findings or []:
        item = fingerprint(finding)
        if item in known:
            continue
        known.add(item)
        additions.append({"fingerprint": item, "rule": finding.get("rule"),
                          "path": _normal(finding.get("path")),
                          "severity": finding.get("severity"),
                          "message": finding.get("message")})
    if not additions:
        return current
    current.setdefault("entries", []).extend(additions)
    current["entries"].sort(key=lambda item: item.get("fingerprint") or "")
    current["reviewedUpdates"] = list(current.get("reviewedUpdates") or []) + [{
        "owner": owner, "reason": reason, "reviewedOn": reviewed_on,
        "previousSha256": baseline_sha256, "added": len(additions), "at": _now(),
    }]
    current["updatedAt"] = _now()
    save_baseline(root, current)
    return current


RUNNER = '''#!/usr/bin/env python3
"""Run the copied ACIMA enforcer against the recorded CI baseline.

Existing baseline findings are warnings. A finding outside the baseline fails the run. Missing,
empty or malformed input fails closed. This script does not write application source.
"""
from __future__ import annotations
import argparse, hashlib, json, subprocess, sys
from pathlib import Path


def fingerprint(finding):
    supplied = str(finding.get("fingerprint") or "").strip().lower()
    if supplied.startswith("sha256:") and len(supplied) == 71:
        return supplied
    anchor = finding.get("evidence") or finding.get("symbol") or finding.get("message") or ""
    material = "\\0".join((str(finding.get("rule") or ""),
                          str(finding.get("path") or "").replace("\\\\", "/"),
                          str(anchor)[:160]))
    return "sha256:" + hashlib.sha256(material.encode("utf-8")).hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--config", default="acima.config.json")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    try:
        enforcement = json.loads((root / "acima/evidence/enforcement.json").read_text(encoding="utf-8"))
        command = (enforcement.get("enforcer") or {}).get("command")
        baseline = json.loads((root / "acima/evidence/ci-baseline.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print("acima baseline: cannot read enforcement or baseline: %s" % error, file=sys.stderr)
        return 2
    if not command:
        print("acima baseline: no enforcer command is recorded", file=sys.stderr)
        return 2
    executable = command.replace("python3", sys.executable, 1)
    try:
        result = subprocess.run(executable, cwd=root, shell=True, capture_output=True,
                                text=True, timeout=300)
        payload = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as error:
        print("acima baseline: enforcement did not return valid JSON: %s" % error, file=sys.stderr)
        return 2
    findings = payload.get("findings")
    if not isinstance(findings, list) or not isinstance(payload.get("sourceFiles"), int) or payload.get("sourceFiles", 0) <= 0:
        print("acima baseline: enforcement output is incomplete or scanned no source", file=sys.stderr)
        return 2
    known = {str(item.get("fingerprint")) for item in baseline.get("entries") or []
             if isinstance(item, dict) and item.get("fingerprint")}
    new = [item for item in findings if fingerprint(item) not in known]
    warnings = [item for item in findings if fingerprint(item) in known]
    for item in warnings:
        print("warning: %s %s: %s" % (item.get("rule"), item.get("path"), item.get("message")))
    for item in new:
        print("error: %s %s: %s" % (item.get("rule"), item.get("path"), item.get("message")),
              file=sys.stderr)
    print("acima baseline: %s warning(s), %s new error(s), %s source file(s)"
          % (len(warnings), len(new), payload.get("sourceFiles")))
    return 1 if new else 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def write_runner(root: Path) -> Path:
    path = root / RUNNER_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(RUNNER, encoding="utf-8")
    return path
