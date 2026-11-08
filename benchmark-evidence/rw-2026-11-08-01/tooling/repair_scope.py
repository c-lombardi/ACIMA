#!/usr/bin/env python3
"""Concrete scope repairs after source-layout review; no rule changes."""
import json
from pathlib import Path
BENCH=Path(__file__).resolve().parents[1]
def load(p): return json.loads(p.read_text())
def save(p,c): p.write_text(json.dumps(c,indent=2)+"\n")
for s in load(BENCH/'candidates/selected.json'):
    lang,rid=s['language'],s['id']
    cfg=load(BENCH/'repositories'/lang/rid/'adoption/acima.config.json')
    if lang=='go':
        src=BENCH/'repositories'/lang/rid/'adoption'
        roots=sorted(p.name for p in src.glob('*.go') if not p.name.endswith('_test.go'))
        for u in cfg['units']:
            if u['paths']==['.']:
                u['paths']=roots
    if (lang,rid)==('typescript','hono'):
        cfg['exclude'] += ['vite.config.ts','vitest.config.ts']
        cfg['exclude']=list(dict.fromkeys(cfg['exclude']))
    if (lang,rid)==('typescript','drizzle-orm'):
        cfg['units'] += [
            {'id':'eslint-plugin-drizzle','role':'implementation','paths':['eslint-plugin-drizzle'],'module':'eslint-plugin-drizzle'},
            {'id':'eslint-internal','role':'tooling','paths':['eslint'],'module':'eslint'},
        ]
        cfg['exclude'] += ['eslint-plugin-drizzle/tests']
        cfg['exclude']=list(dict.fromkeys(cfg['exclude']))
    if (lang,rid)==('dotnet','fluentvalidation'):
        cfg['units'].append({'id':'build','role':'tooling','paths':['src/CommonAssemblyInfo.cs'],'module':'build'})
    if (lang,rid)==('dotnet','spectre-console'):
        cfg['units'].append({'id':'sourcegenerator','role':'tooling','paths':['src/Spectre.Console.SourceGenerator'],'module':'sourcegenerator'})
        cfg['units'].append({'id':'build','role':'tooling','paths':['build.cs'],'module':'build'})
    save(BENCH/'repositories'/lang/rid/'adoption/acima.config.json',cfg)
    save(BENCH/'runs/rw-2026-11-08-01'/lang/rid/'discovery/acima.config.reviewed.json',cfg)
    print(lang,rid,len(cfg['units']))
