import json, subprocess
from pathlib import Path
from collections import Counter

B=Path('/tmp/acima-real-world-benchmark')
RUN='rw-2026-11-08-01'

repos = [
 ('httpx','encode/httpx','python','BSD-3-Clause','library: client/transport layers','pass-with-upstream-failure','1,416 passed / 1 failed / 1 skipped','httpx-test.log'),
 ('flask','pallets/flask','python','BSD-3-Clause','micro-framework','pass','494 passed','flask-test.log'),
 ('fastapi','fastapi/fastapi','python','MIT','framework','pass','4,732 passed / 20 skipped / 1 xfailed','fastapi-test-3.log'),
 ('hono','honojs/hono','typescript','MIT','framework with platform adapters','fail-upstream','5,834 passed / 5 failed / 108 skipped (2 files)','hono-test.log'),
 ('drizzle-orm','drizzle-team/drizzle-orm','typescript','Apache-2.0','ORM monorepo','blocked','dependency build failed: better-sqlite3 native module','drizzle-install.log'),
 ('trpc','trpc/trpc','typescript','MIT','framework monorepo','fail-upstream','1,811 passed / 1 failed (225 files)','trpc-test.log'),
 ('cobra','spf13/cobra','go','Apache-2.0','CLI library','pass','go test ./... pass','go-cobra-test.log'),
 ('bubbletea','charmbracelet/bubbletea','go','MIT','TUI framework','pass','go test ./... pass','go-bubbletea-test.log'),
 ('gin','gin-gonic/gin','go','MIT','HTTP framework','pass','go test ./... pass','go-gin-test.log'),
 ('fluentvalidation','FluentValidation/FluentValidation','dotnet','Apache-2.0','two-assembly validation library','pass','3 TFMs: 894 passed / 1 skipped each','dotnet-fluentvalidation-test-2.log'),
 ('serilog','serilog/serilog','dotnet','Apache-2.0','logging library + sinks','pass','passes across net8/net9/net10','dotnet-serilog-test-2.log'),
 ('spectre-console','spectreconsole/spectre.console','dotnet','MIT','multi-project console library/extensions','pass','passes across net8/net9/net10','dotnet-spectre-test-2.log'),
 ('jsoup','jhy/jsoup','java','MIT','HTML parser library','pass','mvn test pass','java-jsoup-test.log'),
 ('gson','google/gson','java','Apache-2.0','JSON library','partial-fail','core tests pass; test-jpms module boot failure','java-gson-test.log'),
 ('mall','macrozheng/mall','java','Apache-2.0','layered multi-module application','blocked','mvn -DskipTests package timed out at 295s','java-mall-build.log'),
]

summaries={}
for lang,rid in [('python','httpx'),('python','flask'),('python','fastapi'),('typescript','hono'),('typescript','drizzle-orm'),('typescript','trpc'),('go','cobra'),('go','bubbletea'),('go','gin'),('dotnet','fluentvalidation'),('dotnet','serilog'),('dotnet','spectre-console')]:
 p=B/'runs'/RUN/lang/rid/'assessment'/'summary.json'
 if p.exists(): summaries[rid]=json.loads(p.read_text())

def prod_stats(rid, lang):
 src=B/'repositories'/lang/rid/'source'
 cfg=B/'repositories'/lang/rid/'adoption'/'acima.config.json'
 files=set()
 if cfg.exists():
  c=json.loads(cfg.read_text())
  for u in c['units']:
   if u.get('role') not in ('implementation','contracts','host'): continue
   for rel in u.get('paths',[]):
    p=src/rel
    if p.is_file(): files.add(p)
    elif p.is_dir():
     for x in p.rglob('*'):
      if x.is_file() and x.suffix in ('.py','.ts','.tsx','.go','.cs','.java'): files.add(x)
 else:
  for p in src.rglob('*.java'):
   if 'src/test' in p.as_posix() or '/target/' in p.as_posix(): continue
   files.add(p)
 files=sorted(files)
 loc=0
 for p in files:
  try: loc += sum(1 for line in p.read_text(errors='ignore').splitlines() if line.strip())
  except OSError: pass
 modules=set()
 if cfg.exists():
  c=json.loads(cfg.read_text())
  for u in c['units']:
   if u.get('role') in ('implementation','contracts','host'): modules.add(u.get('module',u['id']))
 return len(files),loc,len(modules)

def sha(rid,lang):
 p=B/'repositories'/lang/rid/'source'
 try: return subprocess.check_output(['git','-C',str(p),'rev-parse','HEAD'],text=True).strip()
 except Exception: return 'unknown'

def findings(rid):
 s=summaries.get(rid)
 if not s: return None
 return s.get('findings')

def rule_counts(rid):
 s=summaries.get(rid)
 return s.get('byRule',{}) if s else {}

# Ground-truth classification. Counts are findings reviewed, not claims of exhaustive truth.
gt = {
 'fastapi': {'ACIMA-L001':{'classification':'false_positive','count':1,'why':'identifier sqlalchemy_safe at fastapi/encoders.py:206; no SQLAlchemy import'}},
 'drizzle-orm': {'ACIMA-L001':{'classification':'valid_architectural_choice','count':38,'why':'ORM product adapters intentionally reference pg/mysql2/knex; one test path is out of production scope'}, 'test-path':{'classification':'false_positive','count':1}},
 'fluentvalidation': {'ACIMA-D001':{'classification':'true_positive','count':1,'why':'DI extension assembly imports the implementation assembly; no contracts assembly'}, 'ACIMA-D008':{'classification':'duplicate','count':1,'why':'derived from the same project reference'}, 'ACIMA-L003':{'classification':'valid_architectural_choice','count':6,'why':'public library API is intentionally public; no contracts split'}},
 'spectre-console': {'ACIMA-D001':{'classification':'probable_true_positive','count':4,'why':'extensions/testing reference core implementation assembly; public library API design is intentional but unmodelled'}, 'ACIMA-D005':{'classification':'false_positive','count':2,'why':'cycles traverse analyzer-only ProjectReference with ReferenceOutputAssembly=false; sourcegenerator has no json reference'}, 'ACIMA-D008':{'classification':'false_positive','count':5,'why':'transitive closure of analyzer/extension edges; duplicates D001'}, 'ACIMA-D009':{'classification':'true_positive','count':21,'why':'json uses internal StringBuffer from console; cross-assembly internal access is real coupling'}, 'ACIMA-L003':{'classification':'valid_architectural_choice','count':40,'why':'public types are the shipped library surface, not an accidental implementation leak'}},
 'hono': {'zero':{'classification':'insufficient_evidence','count':0,'why':'adapter units remain zero even after module separation; relative adapter imports may be unresolved'}},
 'trpc': {'tool':{'classification':'tool_failure','count':0,'why':'stdout truncated at 65,536 bytes; invalid JSON; no assessment'}},
 'java': {'no-enforcer':{'classification':'not_applicable','count':0,'why':'no ACIMA Java reference enforcer; executed:false'}},
}

out=[]
for rid,repo,lang,lic,style,test_state,test_detail,log in repos:
 n,loc,mods=prod_stats(rid,lang)
 s=summaries.get(rid)
 f=s.get('findings') if s else None
 out.append({
  'id':rid,'repo':repo,'language':lang,'license':lic,'commit':sha(rid,lang),
  'architectural_style':style,'source_files':n,'production_loc':loc,'modules':mods,
  'baseline_test_state':test_state,'baseline_test_detail':test_detail,'test_log':log,
  'acima': {'executed': s is not None, 'findings':f,'by_rule':rule_counts(rid),
            'rules_portable':23,'rules_not_executed':6,'source_files_reported':s.get('sourceFiles') if s else None},
  'ground_truth': gt.get(rid,{}),
  'implementation': 'blocked: no named upstream owner; no production changes',
  'status': 'blocked'
 })

# Specific implementation record
impl={
 'repository':'FluentValidation/FluentValidation','commit':sha('fluentvalidation','dotnet'),
 'slice':'enforcement gate and boundary declaration in a disposable adoption copy',
 'source_changes':'none to product code; added acima.config.json, empty waivers, docs and CI workflow',
 'baseline_before_gate':{'acima_findings':None,'assessment':'not declared'},
 'after_gate':{'source_files':144,'findings':8,'by_rule':{'ACIMA-D001':1,'ACIMA-D008':1,'ACIMA-L003':6},'gate_exit':1},
 'controlled_violation':{'injection':'core -> DI project reference cycle','expected':'ACIMA-D005','detected':True,'findings':11,'d005':1,'blind':False},
 'tests':'baseline 3 TFMs pass; no product code changed','verdict':'gate is enforceable, adoption is blocked; not a green adoption'}

(B/'aggregate').mkdir(exist_ok=True)
(B/'aggregate'/'portfolio.json').write_text(json.dumps({'run_id':RUN,'repositories':out,'implementation':impl},indent=2)+'\n')
(B/'ground-truth'/'classifications.json').write_text(json.dumps(gt,indent=2)+'\n')
print('repos',len(out),'findings',sum((r['acima']['findings'] or 0) for r in out),'loc',sum(r['production_loc'] for r in out))
for r in out: print(r['id'],r['language'],r['source_files'],r['production_loc'],r['modules'],r['acima']['findings'],r['baseline_test_state'])
