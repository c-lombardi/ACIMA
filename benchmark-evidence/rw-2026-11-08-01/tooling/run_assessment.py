#!/usr/bin/env python3
"""Run the pinned ACIMA reference enforcer against each disposable adoption copy."""
import json, os, subprocess, sys
from pathlib import Path

BENCH = Path(__file__).resolve().parents[1]
ACIMA = Path("/workspace/chats/0f1a05b504fd9f340dbbe0f7")
RUN = BENCH / "runs/rw-2026-11-08-01"
ENV = os.environ.copy()
ENV["PATH"] = "/tmp/toolchains/go/bin:/tmp/toolchains/dotnet:/tmp/toolchains/jdk/bin:/tmp/toolchains/pnpm12/node_modules/.bin:" + ENV.get("PATH", "")
ENV["DOTNET_ROOT"] = "/tmp/toolchains/dotnet"
ENV["DOTNET_CLI_TELEMETRY_OPTOUT"] = "1"

commands = {
 "python": [sys.executable, str(ACIMA/"examples/python/tools/acima_arch.py")],
 "typescript": ["node", str(ACIMA/"examples/typescript/tools/acima-arch.mjs")],
}
for s in json.load(open(BENCH/"candidates/selected.json")):
    lang, rid = s["language"], s["id"]
    target = BENCH/"repositories"/lang/rid/"adoption"
    out = RUN/lang/rid/"assessment"
    out.mkdir(parents=True, exist_ok=True)
    if lang == "java":
        (out/"enforcer.json").write_text(json.dumps({"executed": False, "reason": "No Java reference enforcer in pinned ACIMA revision"}, indent=2)+"\n")
        (out/"summary.json").write_text(json.dumps({"language": lang, "id": rid, "findings": None, "executed": False, "reason": "no Java enforcer"}, indent=2)+"\n")
        print(lang, rid, "no-enforcer")
        continue
    if lang == "go":
        cmd = ["go", "run", "./tools/archtest", "--root", str(target), "--format", "json"]
        cwd = ACIMA/"examples/go"
    elif lang == "dotnet":
        cmd = ["dotnet", "run", "--project", str(ACIMA/"examples/dotnet/tools/Acima.ArchTests"), "--", "--root", str(target), "--format", "json"]
        cwd = ACIMA
    else:
        cmd = commands[lang] + ["--root", str(target), "--format", "json"]
        cwd = ACIMA
    proc = subprocess.run(cmd, cwd=cwd, env=ENV, capture_output=True, text=True, timeout=240)
    (out/"enforcer.stdout").write_text(proc.stdout)
    (out/"enforcer.stderr").write_text(proc.stderr)
    (out/"enforcer.exit").write_text(str(proc.returncode)+"\n")
    try:
        payload = json.loads(proc.stdout)
    except Exception:
        payload = None
    if payload is None:
        (out/"summary.json").write_text(json.dumps({"language":lang,"id":rid,"findings":None,"exit":proc.returncode,"error":(proc.stderr or proc.stdout)[-1000:]},indent=2)+"\n")
        print(lang,rid,"NO-JSON",proc.returncode)
        continue
    findings = payload.get("findings", [])
    by_rule = {}
    for f in findings:
        by_rule[f["rule"]] = by_rule.get(f["rule"], 0) + 1
    summary = {
        "language": lang, "id": rid, "exit": proc.returncode,
        "sourceFiles": payload.get("sourceFiles"), "level": payload.get("level"),
        "findings": len(findings), "errors": sum(1 for f in findings if f.get("severity")=="error"),
        "byRule": dict(sorted(by_rule.items())), "executed": payload.get("execution", {}),
        "config": str((target/"acima.config.json").relative_to(BENCH)),
    }
    (out/"enforcer.json").write_text(json.dumps(payload, indent=2)+"\n")
    (out/"summary.json").write_text(json.dumps(summary, indent=2)+"\n")
    print(lang,rid,"exit",proc.returncode,"files",summary["sourceFiles"],"findings",summary["findings"],summary["byRule"])
