#!/usr/bin/env python3
"""Write reviewed ACIMA unit maps into the disposable adoption copies."""
import json
from pathlib import Path

BENCH = Path(__file__).resolve().parents[1]
RUN = BENCH / "runs/rw-2026-11-08-01"
COMMON_EXCLUDE = [
    ".git", "node_modules", "bin", "obj", "dist", "build", "target", "out",
    ".venv", "venv", "__pycache__", "coverage", "vendor",
]

def unit(uid, role, paths, module=None):
    item = {"id": uid, "role": role, "paths": paths}
    if module:
        item["module"] = module
    return item

MAPS = {
 ("python","httpx"): ("python", [unit("httpx","implementation",["httpx"],"httpx")],
    ["tests","docs","scripts","requirements.txt","*.egg-info"]),
 ("python","flask"): ("python", [unit("flask","implementation",["src/flask"],"flask")],
    ["tests","docs","examples","CHANGES.rst"]),
 ("python","fastapi"): ("python", [unit("fastapi","implementation",["fastapi"],"fastapi")],
    ["tests","docs_src","docs","scripts","*.egg-info"]),
 ("typescript","hono"): ("typescript", [
    unit("hono","implementation",["src"],"hono"),
    unit("hono.adapters","implementation",["adapters"],"hono"),
  ], ["runtime-tests","benchmarks","perf-measures","build","**/*.test.ts","**/*.spec.ts","**/*.test.tsx"]),
 ("typescript","drizzle-orm"): ("typescript", [
    unit("orm","implementation",["drizzle-orm"],"orm"),
    unit("kit","implementation",["drizzle-kit"],"kit"),
    unit("zod","implementation",["drizzle-zod"],"zod"),
    unit("valibot","implementation",["drizzle-valibot"],"valibot"),
    unit("typebox","implementation",["drizzle-typebox"],"typebox"),
    unit("arktype","implementation",["drizzle-arktype"],"arktype"),
    unit("seed","implementation",["drizzle-seed"],"seed"),
  ], ["integration-tests","type-tests","drizzle-orm/type-tests","**/*.test.ts","**/*.test.tsx","**/*.spec.ts","examples","docs"]),
 ("typescript","trpc"): ("typescript", [
    unit("server","implementation",["packages/server"],"server"),
    unit("client","implementation",["packages/client"],"client"),
    unit("react-query","implementation",["packages/react-query"],"react-query"),
    unit("next","implementation",["packages/next"],"next"),
    unit("openapi","implementation",["packages/openapi"],"openapi"),
    unit("tanstack-react-query","implementation",["packages/tanstack-react-query"],"tanstack-react-query"),
  ], ["packages/tests","packages/upgrade","examples","www","**/*.test.ts","**/*.test.tsx","**/*.spec.ts","**/__fixtures__"]),
 ("go","cobra"): ("go", [
    unit("cobra","implementation",["."],"cobra"),
    unit("cobra.doc","implementation",["doc"],"cobra"),
  ], ["*_test.go","doc/**","site","**/testdata/**"]),
 ("go","bubbletea"): ("go", [unit("bubbletea","implementation",["."],"bubbletea")],
    ["*_test.go","examples","tutorials","**/testdata/**"]),
 ("go","gin"): ("go", [
    unit("gin","implementation",["."],"gin"),
    unit("gin.binding","implementation",["binding"],"gin"),
    unit("gin.render","implementation",["render"],"gin"),
    unit("gin.internal","implementation",["internal"],"gin"),
  ], ["*_test.go","binding","render","internal","**/testdata/**"]),
 ("dotnet","fluentvalidation"): ("dotnet", [
    unit("fluentvalidation","implementation",["src/FluentValidation"],"fluentvalidation"),
    unit("fluentvalidation.di","implementation",["src/FluentValidation.DependencyInjectionExtensions"],"fluentvalidation"),
  ], ["src/FluentValidation.Tests","src/FluentValidation.Tests.Benchmarks","docs","**/bin/**","**/obj/**"]),
 ("dotnet","serilog"): ("dotnet", [unit("serilog","implementation",["src/Serilog"],"serilog")],
    ["test","docs","**/bin/**","**/obj/**"]),
 ("dotnet","spectre-console"): ("dotnet", [
    unit("console","implementation",["src/Spectre.Console"],"console"),
    unit("ansi","implementation",["src/Spectre.Console.Ansi"],"ansi"),
    unit("testing","implementation",["src/Spectre.Console.Testing"],"testing"),
    unit("json","implementation",["src/Extensions/Spectre.Console.Json"],"json"),
    unit("imagesharp","implementation",["src/Extensions/Spectre.Console.ImageSharp"],"imagesharp"),
  ], ["src/Spectre.Console.Tests","src/Spectre.Console.Ansi.Tests","src/Benchmarks","docs","**/bin/**","**/obj/**"]),
}
JAVA = {
 "jsoup": [unit("jsoup","implementation",["src/main/java"],"jsoup")],
 "gson": [unit("gson","implementation",["gson/src/main/java"],"gson"),
          unit("extras","implementation",["extras/src/main/java"],"extras")],
 "mall": [unit("common","implementation",["mall-common/src/main/java"],"common"),
          unit("security","implementation",["mall-security/src/main/java"],"security"),
          unit("mbg","implementation",["mall-mbg/src/main/java"],"mbg"),
          unit("admin","implementation",["mall-admin/src/main/java"],"admin"),
          unit("portal","implementation",["mall-portal/src/main/java"],"portal"),
          unit("search","implementation",["mall-search/src/main/java"],"search"),
          unit("demo","implementation",["mall-demo/src/main/java"],"demo")],
}
for s in json.load(open(BENCH / "candidates/selected.json")):
    key = (s["language"], s["id"])
    if s["language"] == "java":
        units = JAVA[s["id"]]
        lang = "java"
        exclude = ["src/test","**/src/test/**","target"]
    else:
        lang, units, extra = MAPS[key]
        exclude = COMMON_EXCLUDE + extra
    config = {
        "standard": "1.0.0",
        "language": lang,
        "level": "L1",
        "root": ".",
        "units": units,
        "exclude": list(dict.fromkeys(exclude)),
        "waivers": ".acima/waivers.json",
    }
    target = BENCH / "repositories" / s["language"] / s["id"] / "adoption"
    (target / "acima.config.json").write_text(json.dumps(config, indent=2) + "\n")
    (target / ".acima").mkdir(exist_ok=True)
    (target / ".acima/waivers.json").write_text('{"waivers": []}\n')
    (RUN / s["language"] / s["id"] / "discovery/acima.config.reviewed.json").write_text(json.dumps(config, indent=2) + "\n")
    print(s["language"], s["id"], len(units), "units")
