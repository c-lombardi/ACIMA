"""The HTML outcome pack is readable offline, safe to render, and faithful to its model."""
from __future__ import annotations
import hashlib, json, re, subprocess, sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'conformance'))
import adoption_reports
SCRIPT=ROOT/'skills/acima-adoption/scripts/render_report.py'
SCHEMA=ROOT/'skills/acima-adoption/assets/report.schema.json'
CATALOG=json.loads((ROOT/'tools/acima-spec/rules.json').read_text(encoding='utf-8'))
CATALOG_SHA=hashlib.sha256((ROOT/'tools/acima-spec/rules.json').read_bytes()).hexdigest()
CSS=ROOT/'skills/acima-adoption/assets/report-template.css'

def _rgb(value):
    value=value.lstrip('#')
    if len(value)==3: value=''.join(character*2 for character in value)
    return tuple(int(value[index:index+2],16)/255 for index in (0,2,4))

def _contrast(foreground,background):
    def luminance(value):
        channels=[channel/12.92 if channel<=0.04045 else ((channel+0.055)/1.055)**2.4 for channel in _rgb(value)]
        return 0.2126*channels[0]+0.7152*channels[1]+0.0722*channels[2]
    high,low=sorted((luminance(foreground),luminance(background)),reverse=True)
    return (high+0.05)/(low+0.05)

def add_complete_review(d, root, unresolved=False):
    source=root/'src'/'sample.py'; source.parent.mkdir(parents=True,exist_ok=True)
    evidence_lines=[f"# Evidence for {rule['id']}: {rule['title']}" for rule in CATALOG['rules']]
    source.write_text("\n".join(evidence_lines)+"\n",encoding='utf-8')
    review={
        'schemaVersion':'1.0','reviewer':'Architecture reviewer','reviewedOn':'2026-11-10',
        'catalogSha256':CATALOG_SHA,
        'rules':[{
            'rule':rule['id'],
            'status':'insufficient_evidence' if unresolved and i==0 else 'conforms',
            'rationale':('Insufficient evidence exists to decide this requirement.' if unresolved and i==0 else
                         f"Reviewed {rule['title']}. The inspected source location was considered against this requirement: {rule['summary']}"),
            'evidence':[{'path':'src/sample.py','kind':'source','startLine':i+1,'endLine':i+1,
                         'quote':evidence_lines[i],
                         'observation':f"Inspected the dedicated evidence location for {rule['title']}."}]
        } for i,rule in enumerate(CATALOG['rules'])]
    }
    d['qualitativeReview']=review
    d['catalogSha256']=CATALOG_SHA
    d['repository']['path']=str(root)
    d['coverage'].update({
        'requiredRules':len(CATALOG['rules']),'reviewedRules':len(CATALOG['rules']),
        'pendingRules':0,'unresolvedRules':1 if unresolved else 0,
        'dispositionCounts':{'conforms':len(CATALOG['rules'])-(1 if unresolved else 0),
                             'doesNotConform':0,'partiallyConforms':0,
                             'notApplicable':0,'unverified':1 if unresolved else 0,
                             'notAssessed':0,'unsupported':0,'blocked':0}
    })
    d['conformance']=[{
        'rule':item['rule'],
        'requirement':next(rule['title'] for rule in CATALOG['rules'] if rule['id']==item['rule']),
        'meaning':next(rule['summary'] for rule in CATALOG['rules'] if rule['id']==item['rule']),
        'disposition':'unverified' if item['status']=='insufficient_evidence' else 'conforms',
        'rationale':item['rationale'],
        'evidenceRefs':[f"src/sample.py:{i+1}-{i+1}"]
    } for i,item in enumerate(review['rules'])]
    if unresolved:
        d['recommendation']['status']='INSUFFICIENT_EVIDENCE'
        d['assessmentStatus']='Assessment incomplete'
    return d

def model():
    return {"schemaVersion":"1.0","generatedAt":"2026-11-10T13:00:00-05:00","skillVersion":"1.27.0","standardVersion":"1.9.0-draft.1","catalogSha256":"abc123","assessmentStatus":"Assessment incomplete","repository":{"name":"Sample product","path":"C:/work/sample","commit":"abc","mode":"brownfield"},"recommendation":{"status":"RECOMMENDED_WITH_LIMITATIONS","summary":"Start with existing module boundaries; runtime ownership needs more evidence.","reasons":["The code already has distinct domain projects."],"caveats":["CI was not observed."]},"overview":{"plainLanguage":"This assessment found an existing boundary worth protecting.","nextAction":"Review the proposed local architecture check.","nextActionWhy":"It can catch new coupling without requiring a rewrite."},"value":{"benefits":[{"title":"Safer changes","description":"Modules depend on published contracts, not private implementation details.","availability":"Achievable after the gate is adopted."}],"adds":["Enforcement for dependency direction."],"costs":["A small maintenance cost for the check."]},"architecture":{"family":"Modular monolith","currentState":"Several projects already separate business capabilities.","proposedState":"Make the existing module contracts explicit and checkable."},"strengths":["Existing project boundaries."],"findings":[{"title":"A consumer reaches into a private implementation","rule":"ACIMA-D001","what":"The Orders project references Catalog internals.","why":"An internal Catalog change can break Orders unexpectedly.","paths":["src/Orders/OrderService.cs"],"recommendation":"Depend on the published Catalog contract.","status":"confirmed"}],"proposedChanges":[{"path":"acima.config.json","action":"create","purpose":"Declare module ownership.","expectedOutcome":"The check knows which code belongs to each module.","approval":"Requires approval","status":"proposed"},{"path":"src/Orders/OrderService.cs","action":"modify","purpose":"Replace private implementation reference.","expectedOutcome":"Orders depends only on Catalog's published contract.","approval":"Not approved","status":"proposed"}],"outcomes":[{"title":"Earlier boundary feedback","description":"A new cross-module implementation dependency is reported before merge.","measure":"A controlled bad import fails the local check.","status":"Proposed"}],"phases":[{"name":"Declare modules","purpose":"Record existing ownership boundaries.","deliverable":"acima.config.json","verification":"Validate map and run check.","approval":"Yes","status":"Proposed"}],"decisions":[{"question":"Who owns Catalog's public contract?","context":"The current ownership is not explicit.","recommendation":"Assign the Catalog team.","impact":"Needed before contract changes.","effort":"About 30 minutes with the Catalog team.","consequence":"Contract changes stay blocked until an owner is named.","evidenceGap":"The repository does not name a current owner.","blockedWork":"Contract changes and ownership-dependent checks.","whyOwner":"Only the repository owner can assign responsibility.","alternatives":[{"title":"Local check only","description":"Does not block merges."}],"requiredBeforeImplementation":True}],"outOfScope":["No database migration."],"limitations":["CI workflow was not inspected."],"coverage":{"requiredRules":56,"reviewedRules":56,"pendingRules":0,"automatedChecksRun":42,"manualReviewsCompleted":14,"skippedOrUnsupported":0},"evidence":[{"label":"Qualitative review","source":"assessment/review.json","whatItSupports":"Requirement dispositions and evidence references.","status":"Complete"}],"approvalStatement":"Only the listed report and implementation scope can be approved; no blanket authorization."}
def large_module_map_model(count=1000):
    data=model()
    modules=[]
    for index in range(1,count+1):
        area=index%12
        path=f"src/area-{area}/module-{index:04d}/service.py"
        review='accept' if index<=200 else 'modify' if index<=250 else 'defer' if index<=300 else 'reject' if index<=305 else 'pending'
        contracts={'paths':[f"src/area-{area}/module-{index:04d}/contract.py"]} if index%5==0 else {'paths':[]}
        dependencies=[]
        if index%7==0:
            next_index=index%count+1
            dependencies=[{'module':f"Module {next_index:04d}",'moduleId':f"module-{next_index:04d}",'leaksImplementation':index%11==0}]
        modules.append({
            'id':f"module-{index:04d}",'name':f"Module {index:04d}",
            'responsibility':f"Owns the behavior and data for module {index:04d}.",
            'ownership':'inferred','status':'proposed','reviewDecision':review,
            'implementation':{'paths':[path]},'contracts':contracts,
            'dependencies':dependencies,
            'evidence':[{'path':path,'observation':'Observed source path in layout discovery.'}],
        })
    data['moduleMap']={
        'authoritativeMap':{'status':'absent'},
        'proposal':{'status':'proposed','basis':'Layout and import discovery only.','modules':modules,
                    'recommendations':[],'decisions':[],'unassigned':[],'quality':{}},
    }
    data['ownershipGate']={'status':'blocked','deterministicChecksBlocked':True,
                           'ownershipDependentRules':['ACIMA-D001'],'independentReviewContinues':True}
    data['plainLanguageGaps']=[
        {'title':'A change in one area can break another',
         'risk':'high',
         'whatItCosts':'A routine change in the catalog area can break checkout without the catalog team seeing it first.',
         'fixInvolves':'Make checkout use the catalog area’s published interface instead of reaching into its internal code.',
         'paths':['src/area-1/module-0001/service.py'],
         'confidence':'confirmed'},
        {'title':'No one has confirmed the proposed parts',
         'risk':'high',
         'whatItCosts':'Work could be assigned to the wrong team, and checks could enforce a boundary the product does not actually have.',
         'fixInvolves':'Walk through each proposed part with its owner and accept, change or reject it before relying on the map.',
         'confidence':'not recorded'},
        {'title':'Two areas may be doing the same job',
         'risk':'medium',
         'whatItCosts':'The same rules can drift apart in two places, so a fix in one area may not reach the other.',
         'fixInvolves':'Compare the two areas and keep one owner for the shared rule, or make the split explicit.',
         'confidence':'needs review'},
        {'title':'The reporting area has no clear owner',
         'risk':'low',
         'whatItCosts':'Small reporting changes can wait for ad hoc help and lose context between changes.',
         'fixInvolves':'Name one owner for reporting, even if that person is not full time on it.',
         'confidence':'probable'},
    ]
    return data

class HtmlReportTests(unittest.TestCase):
    def test_schema_is_valid_json_and_defines_the_file_impact_contract(self):
        schema=json.loads(SCHEMA.read_text(encoding='utf-8-sig'))
        self.assertEqual(schema['properties']['schemaVersion']['enum'],['1.0', '1.1', '1.2', '1.3'])
        self.assertIn('qualitativeReview',schema['properties'])
        self.assertEqual(schema['properties']['conformance']['minItems'],56)
        self.assertEqual(schema['$defs']['fileChange']['required'],['path','action','purpose','expectedOutcome'])
        self.assertIn('preservation',schema['properties'])
        self.assertIn('roadmap',schema['properties'])
        self.assertIn('conformance',schema['properties'])
        self.assertIn('anyOf',schema['allOf'][1]['then']['properties']['findings']['items'])
        workflow=schema['properties']['adoptionWorkflow']
        self.assertEqual(workflow['required'],['mode','stages','phase','phaseLabel','phaseOrder'])

    def test_plan_page_states_the_canonical_phase(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); src=root/'model.json'; out=root/'report'
            data=model()
            data['adoptionWorkflow']={"mode":"guided","stages":[],"next":{},
                "phase":"review_and_authorize","phaseLabel":"Phase 3 — Review and authorize",
                "phaseOrder":["start","assess","explain_and_propose","review_and_authorize","implement","verify_and_hand_off"]}
            src.write_text(json.dumps(data),encoding='utf-8')
            result=subprocess.run([sys.executable,str(SCRIPT),'--input',str(src),'--out-dir',str(out)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            plan=(out/'plan.html').read_text(encoding='utf-8')
            self.assertIn('Current phase',plan)
            self.assertIn('Phase 3 — Review and authorize',plan)

    def test_plan_page_does_not_invent_a_missing_phase(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); src=root/'model.json'; out=root/'report'
            data=model()
            data['adoptionWorkflow']={"mode":"guided","stages":[],"next":{}}
            src.write_text(json.dumps(data),encoding='utf-8')
            result=subprocess.run([sys.executable,str(SCRIPT),'--input',str(src),'--out-dir',str(out)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            plan=(out/'plan.html').read_text(encoding='utf-8')
            self.assertIn('Current phase',plan)
            self.assertIn('not recorded',plan)
            self.assertNotIn('Phase 5 — Verify and hand off',plan)

    def test_report_model_projects_the_engine_phase_without_recalculating_it(self):
        projected=adoption_reports._canonical_phase({
            "mode":"guided",
            "authorized":True,
            "stages":{"implementation":{"name":"implementation","status":"in_progress"}},
        })
        self.assertEqual(projected["phase"],"implement")
        self.assertEqual(projected["phaseLabel"],"Phase 4 — Implement")
        self.assertEqual(projected["phaseOrder"],[
            "start","assess","explain_and_propose","review_and_authorize",
            "implement","verify_and_hand_off"])
        self.assertEqual(adoption_reports._canonical_phase({}),{})

    def test_large_module_map_renders_an_atlas_and_searchable_directory(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); src=root/'model.json'; out=root/'report'
            src.write_text(json.dumps(large_module_map_model()),encoding='utf-8')
            result=subprocess.run([sys.executable,str(SCRIPT),'--input',str(src),'--out-dir',str(out)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            page=(out/'proposal.html').read_text(encoding='utf-8')
            self.assertEqual(page.count('<tr id="module-'),1000)
            self.assertIn('class="module-atlas"',page)
            self.assertIn('The map at a glance',page)
            self.assertIn('data-module-search',page)
            self.assertIn('data-status-filter="needs_owner"',page)
            self.assertIn('href="#module-module-0001"',page)
            self.assertIn('id="module-module-0001"',page)
            self.assertIn('src/area-1/module-0001/service.py',page)
            self.assertIn('<noscript>',page)
            self.assertIn('1000 parts',page)
            self.assertIn('PARTS OF THE PRODUCT',page)
            gap_section=page.split('id="plain-language-gaps"',1)[1].split('id="module-map"',1)[0]
            self.assertEqual(gap_section.count('class="gap-card'),4)
            self.assertIn('What it could cost this product:',gap_section)
            self.assertIn('What fixing it involves:',gap_section)
            self.assertNotIn('ACIMA-',gap_section)
            self.assertLess(page.index('A change in one area can break another'),page.index('Two areas may be doing the same job'))
            self.assertLess(page.index('Two areas may be doing the same job'),page.index('The reporting area has no clear owner'))
            self.assertIn('role="region" aria-labelledby="module-table-caption" tabindex="0"',page)
            self.assertIn('<caption id="module-table-caption"',page)
            self.assertIn('<th scope="col">Part</th>',page)
            self.assertIn('<th scope="row">',page)
            self.assertIn('<script>\n(() => {',page)
            self.assertNotIn('\\n  const root',page)
            self.assertIn('data-module-count aria-live="polite"',page)
            self.assertIn('data-module-empty hidden',page)
            self.assertIn("addEventListener('hashchange', revealTarget)",page)

    def test_plain_language_gap_brief_falls_back_to_recorded_findings(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); src=root/'model.json'; out=root/'report'
            data=large_module_map_model(3); data.pop('plainLanguageGaps')
            src.write_text(json.dumps(data),encoding='utf-8')
            result=subprocess.run([sys.executable,str(SCRIPT),'--input',str(src),'--out-dir',str(out)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            page=(out/'proposal.html').read_text(encoding='utf-8')
            gap_section=page.split('id="plain-language-gaps"',1)[1].split('id="module-map"',1)[0]
            self.assertIn('A consumer reaches into a private implementation',gap_section)
            self.assertIn('No one has confirmed the proposed map',gap_section)
            self.assertIn('What it could cost this product:',gap_section)
            self.assertIn('What fixing it involves:',gap_section)
            self.assertNotIn('ACIMA-',gap_section)

    def test_approved_map_with_no_recorded_gaps_omits_gap_briefing(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); src=root/'model.json'; out=root/'report'
            data=model(); data['findings']=[]
            units=[{'id':'orders-impl','module':'orders','role':'implementation','paths':['src/orders']}]
            data['moduleMap']={
                'status':'authoritative',
                'summary':'The existing map was checked without replacement.',
                'proposal':None,
                'review':{'status':'approved','approval':{'status':'approved','reviewer':'Repository owner','reviewedOn':'2026-11-12'}},
                'authoritativeMap':{
                    'present':True,'status':'complete','unitCount':1,
                    'coveredProduction':1,'productionFiles':1,'unownedPaths':[],'issues':[],'units':units,
                },
                'authoritativeUnits':units,
            }
            data['ownershipGate']={'status':'ready','deterministicChecksBlocked':False,
                                   'ownershipDependentRules':[],'independentReviewContinues':True}
            src.write_text(json.dumps(data),encoding='utf-8')
            result=subprocess.run([sys.executable,str(SCRIPT),'--input',str(src),'--out-dir',str(out)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            page=(out/'proposal.html').read_text(encoding='utf-8')
            self.assertNotIn('id="plain-language-gaps"',page)
            self.assertNotIn('No gap was recorded',page)
            self.assertIn('id="module-map"',page)
            self.assertIn('How the product is divided today',page)

    def test_d016_allowlist_is_presented_as_an_owner_approved_configuration_proposal(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); src=root/'model.json'; out=root/'report'
            data=model()
            data['d016Allowlist']={
                'rule':'ACIMA-D016','configPath':'acima.config.json','status':'owner_decision',
                'currentExecution':'not_executed',
                'reason':'partial helper allowlist not declared in acima.config.json',
                'candidates':[],'proposedValue':[],
                'approval':'Confirm that no partial-application helper is used, or name every exact helper.',
                'verification':'Run the .NET enforcer and confirm ACIMA-D016 reports executed: true.',
            }
            data['proposedChanges'].append({
                'path':'acima.config.json','action':'modify',
                'purpose':'Declare the partial-application helper allowlist.',
                'expectedOutcome':'ACIMA-D016 executes and 42/42 automated rules are covered.',
                'classification':'owner-decision','status':'proposed',
                'associatedFindings':['ACIMA-D016'],
            })
            src.write_text(json.dumps(data),encoding='utf-8')
            result=subprocess.run([sys.executable,str(SCRIPT),'--input',str(src),'--out-dir',str(out)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            proposal=(out/'proposal.html').read_text(encoding='utf-8')
            files=(out/'files.html').read_text(encoding='utf-8')
            self.assertIn('id="d016-allowlist"',proposal)
            self.assertIn('partialHelpers',proposal)
            self.assertIn('Not executed',proposal)
            self.assertIn('ACIMA-D016',proposal)
            self.assertIn('Configuration decision for the partial-application check',files)

    def test_generates_six_navigable_pages_and_impact_inventory(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); src=root/'model.json'; out=root/'report'; src.write_text(json.dumps(model()),encoding='utf-8')
            result=subprocess.run([sys.executable,str(SCRIPT),'--input',str(src),'--out-dir',str(out)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            for name in ('index.html','proposal.html','findings.html','files.html','plan.html','evidence.html'):
                self.assertTrue((out/name).is_file(),name)
                page=(out/name).read_text(encoding='utf-8')
                self.assertIn('assets/report.css',page)
                self.assertIn('evidence.html',page)
            files=(out/'files.html').read_text(encoding='utf-8')
            self.assertIn('acima.config.json',files); self.assertIn('src/Orders/OrderService.cs',files)
            self.assertIn('Replace private implementation reference',files)
            self.assertTrue((out/'assets/report.css').is_file()); self.assertTrue((out/'report-data.json').is_file())
    def test_proposal_opens_with_adoption_path_and_current_state(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); d=model()
            d['milestones']={'assessmentComplete':True,'adoptionProposalComplete':True,'implementationComplete':False,'conformanceVerified':False}
            src=root/'model.json'; out=root/'report'; src.write_text(json.dumps(d),encoding='utf-8')
            result=subprocess.run([sys.executable,str(SCRIPT),'--input',str(src),'--out-dir',str(out)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            page=(out/'proposal.html').read_text(encoding='utf-8')
            self.assertIn('id="adoption-path"',page)
            self.assertIn('Where this repository sits on the adoption path',page)
            self.assertLess(page.find('id="adoption-path"'),page.find('TODAY'))
            for title in ('No ACIMA','Foundation','Implemented','Continuous'):
                self.assertIn(title,page)
            self.assertIn('aria-current="step"',page)
            self.assertIn('Current position',page)
            self.assertIn('--path-progress:33%',page)

    def test_plan_decisions_use_plain_language_and_decision_brief_fields(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); src=root/'model.json'; out=root/'report'; src.write_text(json.dumps(model()),encoding='utf-8')
            result=subprocess.run([sys.executable,str(SCRIPT),'--input',str(src),'--out-dir',str(out)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            page=(out/'plan.html').read_text(encoding='utf-8')
            for text in ('Who owns Catalog', 'Recommendation:', 'Effort:',
                         'If left open:', 'Evidence gap:', 'Why an owner is needed:'):
                self.assertIn(text,page)
            self.assertIn('About 30 minutes with the Catalog team.',page)
            self.assertIn('Local check only',page)
            self.assertIn('Does not block merges.',page)
            self.assertNotIn('accept, modify',page)

    def test_pages_expose_accessible_structure_and_named_tables(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); src=root/'model.json'; out=root/'report'; src.write_text(json.dumps(model()),encoding='utf-8')
            result=subprocess.run([sys.executable,str(SCRIPT),'--input',str(src),'--out-dir',str(out)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            for name in ('index.html','proposal.html','findings.html','files.html','plan.html','evidence.html'):
                page=(out/name).read_text(encoding='utf-8')
                self.assertIn('<html lang="en">',page)
                self.assertEqual(page.count('<main '),1,name)
                self.assertIn('<main id="main" tabindex="-1" aria-labelledby="page-title">',page)
                self.assertIn('<h1 id="page-title">',page)
                self.assertIn('<a class="skip" href="#main">Skip to report content</a>',page)
                self.assertIn('<aside aria-label="Report navigation">',page)
                self.assertIn('<nav aria-label="Report sections">',page)
                self.assertIn('aria-current="page"',page)
                tables=re.findall(r'<table>.*?</table>',page,re.S)
                wrappers=re.findall(r'<div class="table-wrap" role="region" aria-labelledby="([^"]+)" tabindex="0">',page)
                self.assertEqual(len(tables),len(wrappers),name)
                for caption_id,table_html in zip(wrappers,tables):
                    self.assertIn(f'<caption id="{caption_id}" class="visually-hidden">',table_html)
                    self.assertIn('<th scope="col">',table_html)
                    self.assertIn('<tbody><tr><th scope="row">',table_html)
    def test_stylesheet_enforces_contrast_focus_and_user_preferences(self):
        css=CSS.read_text(encoding='utf-8-sig')
        colors=dict(re.findall(r'--([\w-]+):\s*(#[0-9a-fA-F]{3,6})',css))
        for name,value in (('accent','#3B82F6'),('sky','#60A5FA'),('ink','#1F2937'),('paper','#F0F9FF')):
            self.assertEqual(colors[name].lower(),value.lower(),name)
        for foreground,background,minimum in (
            ('ink','paper',4.5),('mid','lit',4.5),('muted','lit',4.5),('muted','shade',4.5),
            ('blue','paper',4.5),('blue','lit',4.5),('paper','board',4.5),
            ('focus-inner','board',3.0),('focus-outer','paper',3.0),('focus-inner','accent',3.0),
        ):
            self.assertGreaterEqual(_contrast(colors[foreground],colors[background]),minimum,
                                    f'{foreground} on {background}')
        for foreground,background in (('#14532D','#DCFCE7'),('#7F1D1D','#FEE2E2'),('#78350F','#FEF3C7')):
            self.assertGreaterEqual(_contrast(foreground,background),4.5,f'{foreground} on {background}')
        for required in (
            '.visually-hidden', ':focus-visible', 'outline:3px solid var(--focus-inner)',
            'box-shadow:0 0 0 6px var(--focus-outer)', 'main:focus-visible',
            '@media(forced-colors:active)', '@media(prefers-reduced-motion:reduce)',
            'overflow-wrap:anywhere', 'tbody th', 'overflow-x:auto',
        ):
            self.assertIn(required,css)
        self.assertIn('@media(max-width:900px)',css)
        self.assertIn('@media(max-width:600px)',css)
    def test_accessibility_baseline_is_documented_with_manual_limits(self):
        reference=(ROOT/'skills/acima-adoption/references/90-html-outcome-reports.md').read_text(encoding='utf-8-sig').lower()
        for required in (
            'wcag 2.2 aa','keyboard access','visible focus','programmatically associated caption',
            'scope="col"','scope="row"','reflow and zoom','reduced-motion','forced-colours',
            'manual release checks','not evidence that every assistive-technology combination',
        ):
            self.assertIn(required,reference)
    def test_escapes_untrusted_repository_and_finding_text(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); d=model(); d['repository']['name']='<script>alert(1)</script>'; d['findings'][0]['what']='<img src=x onerror=alert(1)>'
            src=root/'m.json'; out=root/'out'; src.write_text(json.dumps(d),encoding='utf-8')
            result=subprocess.run([sys.executable,str(SCRIPT),'--input',str(src),'--out-dir',str(out)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            page=(out/'findings.html').read_text(encoding='utf-8')
            self.assertNotIn('<script>alert(1)</script>',page); self.assertIn('&lt;script&gt;',page)
            self.assertNotIn('<img src=x onerror=',page)
    def test_rejects_missing_file_purpose_and_prevents_overwrite_by_default(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); d=model(); d['proposedChanges'][0].pop('purpose'); src=root/'m.json'; out=root/'out'; src.write_text(json.dumps(d),encoding='utf-8')
            bad=subprocess.run([sys.executable,str(SCRIPT),'--input',str(src),'--out-dir',str(out)],capture_output=True,text=True)
            self.assertEqual(bad.returncode,2); self.assertIn('purpose',bad.stderr)
            src.write_text(json.dumps(model()),encoding='utf-8')
            good=subprocess.run([sys.executable,str(SCRIPT),'--input',str(src),'--out-dir',str(out)],capture_output=True,text=True)
            self.assertEqual(good.returncode,0,good.stderr)
            second=subprocess.run([sys.executable,str(SCRIPT),'--input',str(src),'--out-dir',str(out)],capture_output=True,text=True)
            self.assertEqual(second.returncode,2); self.assertIn('--overwrite',second.stderr)
    def test_incomplete_assessment_is_never_styled_as_verified(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); d=model(); d['assessmentStatus']='Assessment incomplete'; d['coverage']['reviewedRules']=31; src=root/'m.json'; out=root/'out'; src.write_text(json.dumps(d),encoding='utf-8')
            result=subprocess.run([sys.executable,str(SCRIPT),'--input',str(src),'--out-dir',str(out)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            page=(out/'index.html').read_text(encoding='utf-8')
            self.assertIn('pill review',page)
            self.assertNotIn('pill good">Assessment incomplete',page)
            self.assertIn('31 of 56',page)

    def test_reader_facing_status_and_dates_are_plain_language(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); src=root/'m.json'; out=root/'report'; src.write_text(json.dumps(model()),encoding='utf-8')
            result=subprocess.run([sys.executable,str(SCRIPT),'--input',str(src),'--out-dir',str(out)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            index=(out/'index.html').read_text(encoding='utf-8')
            self.assertIn('Recommended, with limitations',index)
            self.assertIn('Assessment incomplete',index)
            self.assertIn('10 November 2026 at 1:00 pm (UTC-05:00)',index)
            self.assertIn('56 of 56',index)
            self.assertIn('coverage, not a score',index)
            self.assertLess(index.find('What this means for your product'),index.find('class="metrics compact"'))
            self.assertEqual(index.count('class="metric"'),2)
            self.assertIn('Repository:',index)
            self.assertIn('Structure:',index)
            self.assertIn('aria-label="ACIMA Architecture Outcome Report"',index)
            self.assertNotIn('REPOSITORY TYPE',index)
            self.assertNotIn('RECOMMENDED_WITH_LIMITATIONS',index)
            self.assertNotIn('>2026-11-10T13:00:00-05:00<',index)
            evidence=(out/'evidence.html').read_text(encoding='utf-8')
            self.assertIn('Checks in the catalog',evidence)
            self.assertIn('Reviewed with evidence',evidence)
            self.assertIn('Check results',evidence)

    def test_evidence_page_summarizes_exceptions_and_discloses_full_record(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); d=model(); d['coverage']['unresolvedRules']=1
            d['conformance']=[{'requirement':'Boundary','disposition':'does-not-conform','meaning':'A consumer reaches inside another module.','evidenceRefs':['src/Orders/OrderService.cs:12-14']}]
            src=root/'m.json'; out=root/'report'; src.write_text(json.dumps(d),encoding='utf-8')
            result=subprocess.run([sys.executable,str(SCRIPT),'--input',str(src),'--out-dir',str(out)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            page=(out/'evidence.html').read_text(encoding='utf-8')
            self.assertIn('What the evidence shows',page)
            self.assertIn('What needs attention',page)
            self.assertIn('Does not meet the check',page)
            self.assertIn('Evidence details',page)
            self.assertEqual(page.count('<details>'),4)
            self.assertIn('Review coverage: 56 of 56',page)
            self.assertIn('All check results',page)
            self.assertIn('src/Orders/OrderService.cs:12-14',page)

    def test_pages_reconcile_findings_and_cross_link(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); d=model(); d['findings'][0].pop('rule',None); d['findings'][0]['requirementRefs']=['ACIMA-X001','ACIMA-D001']
            d['conformance']=[{'rule':'ACIMA-D001','requirement':'Boundary','disposition':'does-not-conform','meaning':'A consumer reaches inside another module.','evidenceRefs':['src/Orders/OrderService.cs:12-14']}]
            src=root/'m.json'; out=root/'report'; src.write_text(json.dumps(d),encoding='utf-8')
            result=subprocess.run([sys.executable,str(SCRIPT),'--input',str(src),'--out-dir',str(out)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            findings=(out/'findings.html').read_text(encoding='utf-8')
            self.assertIn('id="findings"',findings)
            self.assertIn('href="files.html#file-changes"',findings)
            self.assertIn('href="plan.html#adoption-plan"',findings)
            self.assertIn('href="evidence.html#exceptions"',findings)
            self.assertIn('1 problem names a matching check result.',findings)
            self.assertIn('Internal reference:',findings)
            self.assertIn('id="exceptions"',(out/'evidence.html').read_text(encoding='utf-8'))
            self.assertIn('id="file-changes"',(out/'files.html').read_text(encoding='utf-8'))
            self.assertIn('id="adoption-plan"',(out/'plan.html').read_text(encoding='utf-8'))

    def test_schema_11_rejects_unlinked_and_unknown_findings(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); d=model(); d['schemaVersion']='1.1'; d['findings'][0].pop('rule')
            src=root/'unlinked.json'; out=root/'unlinked'; src.write_text(json.dumps(d),encoding='utf-8')
            result=subprocess.run([sys.executable,str(SCRIPT),'--input',str(src),'--out-dir',str(out)],capture_output=True,text=True)
            self.assertEqual(result.returncode,2)
            self.assertIn('must name at least one catalog rule',result.stderr)
            d['findings'][0]['rule']='ACIMA-X001'
            src=root/'unknown.json'; out=root/'unknown'; src.write_text(json.dumps(d),encoding='utf-8')
            result=subprocess.run([sys.executable,str(SCRIPT),'--input',str(src),'--out-dir',str(out)],capture_output=True,text=True)
            self.assertEqual(result.returncode,2)
            self.assertIn('references unknown catalog rule',result.stderr)

    def test_pages_have_accessible_links_table_regions_and_fragments(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); src=root/'m.json'; out=root/'report'; src.write_text(json.dumps(model()),encoding='utf-8')
            result=subprocess.run([sys.executable,str(SCRIPT),'--input',str(src),'--out-dir',str(out)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            pages={p.name:p.read_text(encoding='utf-8') for p in out.glob('*.html')}
            ids={name:set(re.findall(r'\bid="([^"]+)"',page)) for name,page in pages.items()}
            for name,page in pages.items():
                self.assertEqual(page.count('<main'),1,name)
                self.assertEqual(page.count('<h1'),1,name)
                self.assertEqual(page.count('aria-current="page"'),1,name)
                self.assertIn('aria-label="ACIMA Architecture Outcome Report"',page)
                self.assertEqual(page.count('<div class="table-wrap"'),page.count('<caption'),name)
                for tag,body in re.findall(r'(<a\b[^>]*>)(.*?)</a>',page,re.S):
                    href=re.search(r'href="([^"]+)"',tag)
                    self.assertIsNotNone(href,name)
                    label=re.search(r'aria-label="([^"]+)"',tag)
                    link_name=' '.join((label.group(1) if label else re.sub(r'<[^>]+>',' ',body)).split())
                    self.assertTrue(link_name,f'{name}: link {href.group(1)} has no accessible name')
                    self.assertNotIn(link_name.lower(),{'click here','read more','learn more','more'},f'{name}: generic link name')
                for tag in re.findall(r'<div class="table-wrap"[^>]*>',page):
                    self.assertIn('role="region"',tag,name)
                    self.assertIn('tabindex="0"',tag,name)
                    label=re.search(r'aria-labelledby="([^"]+)"',tag)
                    self.assertIsNotNone(label,f'{name}: table region has no label')
                    self.assertIn(label.group(1),ids[name],f'{name}: table label target missing')
                for href in re.findall(r'href="([^"]+)"',page):
                    if '#' not in href: continue
                    target,fragment=href.split('#',1) if not href.startswith('#') else (name,href[1:])
                    self.assertIn(target,pages,f'{name}: missing page target {href}')
                    self.assertIn(fragment,ids[target],f'{name}: missing fragment target {href}')

    def test_report_does_not_infer_clean_result_from_empty_findings(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); d=model(); d['findings']=[]; d['assessmentStatus']='Assessment incomplete'; d['coverage']['reviewedRules']=31
            src=root/'m.json'; out=root/'out'; src.write_text(json.dumps(d),encoding='utf-8')
            result=subprocess.run([sys.executable,str(SCRIPT),'--input',str(src),'--out-dir',str(out)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            page=(out/'findings.html').read_text(encoding='utf-8')
            self.assertIn('Check the evidence page to confirm that the review was complete',page)

    def test_schema_11_requires_explicit_unknown_states_and_never_infers_completion(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); d=model()
            d.update({
                "schemaVersion":"1.1",
                "outcomes":[], "outcomesStatus":"Outcome mapping is pending completion of qualitative review.",
                "decisions":[], "decisionsStatus":"No owner decision can be confirmed until module ownership discovery is complete.",
                "proposedChanges":[], "fileImpactStatus":"File-level impact is not established until ownership decisions are made.",
                "phases":[], "roadmapStatus":"Roadmap is blocked pending module ownership decisions.",
                "preservation":[], "preservationStatus":"Preservation inventory is not yet assessed.",
                "fileImpact":{"inspect":[],"create":[],"modify":[],"preserve":[]},
                "roadmap":{"status":"Blocked pending module ownership decisions.","phases":[]},
            })
            d["findings"][0].update({"classification":"required","disposition":"unverified","confidence":"low","requirementMeaning":"Modules must not depend on another module's private implementation.","expectedOutcome":"A contract-only dependency is established.","verification":"Run the dependency boundary check."})
            add_complete_review(d,root,unresolved=True)
            src=root/"model.json"; out=root/"report"; src.write_text(json.dumps(d),encoding="utf-8")
            result=subprocess.run([sys.executable,str(SCRIPT),"--input",str(src),"--out-dir",str(out)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn("Roadmap is blocked",(out/"plan.html").read_text(encoding="utf-8"))
            self.assertIn("not yet assessed",(out/"files.html").read_text(encoding="utf-8"))
            self.assertIn("Needs more evidence",(out/"evidence.html").read_text(encoding="utf-8"))

    def test_decision_report_rejects_54_of_55_qualitative_dispositions(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); d=model()
            d.update({"schemaVersion":"1.1","outcomes":[],"outcomesStatus":"No separate outcomes proposed.","decisions":[],"decisionsStatus":"No owner decisions are needed for this assessment.","proposedChanges":[],"fileImpactStatus":"No source changes proposed.","phases":[],"roadmapStatus":"No implementation roadmap until owner decisions are made.","preservation":[],"preservationStatus":"No source changes are proposed.","fileImpact":{"inspect":[],"create":[],"modify":[],"preserve":[]},"roadmap":{"status":"No implementation roadmap.","phases":[]}})
            d["findings"][0].update({"classification":"required","disposition":"unverified","confidence":"low","requirementMeaning":"Modules must not depend on another module's private implementation.","expectedOutcome":"A contract-only dependency is established.","verification":"Run the dependency boundary check."})
            add_complete_review(d,root)
            d["qualitativeReview"]["rules"].pop()
            d["conformance"].pop()
            src=root/"model.json"; out=root/"report"; src.write_text(json.dumps(d),encoding="utf-8")
            result=subprocess.run([sys.executable,str(SCRIPT),"--input",str(src),"--out-dir",str(out)],capture_output=True,text=True)
            self.assertEqual(result.returncode,2,result.stderr)
            self.assertIn("valid evidence-backed disposition",result.stderr)

    def test_decision_report_rejects_fabricated_evidence_quotes(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); d=model()
            d.update({"schemaVersion":"1.1","outcomes":[],"outcomesStatus":"No separate outcomes proposed.","decisions":[],"decisionsStatus":"No owner decisions are needed for this assessment.","proposedChanges":[],"fileImpactStatus":"No source changes proposed.","phases":[],"roadmapStatus":"No implementation roadmap until owner decisions are made.","preservation":[],"preservationStatus":"No source changes are proposed.","fileImpact":{"inspect":[],"create":[],"modify":[],"preserve":[]},"roadmap":{"status":"No implementation roadmap.","phases":[]}})
            d["findings"][0].update({"classification":"required","disposition":"unverified","confidence":"low","requirementMeaning":"Modules must not depend on another module's private implementation.","expectedOutcome":"A contract-only dependency is established.","verification":"Run the dependency boundary check."})
            add_complete_review(d,root)
            d["qualitativeReview"]["rules"][0]["evidence"][0]["quote"]="A fabricated quote absent from the source file"
            src=root/"model.json"; out=root/"report"; src.write_text(json.dumps(d),encoding="utf-8")
            result=subprocess.run([sys.executable,str(SCRIPT),"--input",str(src),"--out-dir",str(out)],capture_output=True,text=True)
            self.assertEqual(result.returncode,2,result.stderr)
            self.assertIn("valid evidence-backed disposition",result.stderr)

    def test_schema_11_rejects_empty_sections_without_explanation(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); d=model()
            d.update({"schemaVersion":"1.1","outcomes":[],"decisions":[],"proposedChanges":[],"phases":[],"preservation":[],"conformance":[]})
            src=root/"model.json"; out=root/"report"; src.write_text(json.dumps(d),encoding="utf-8")
            result=subprocess.run([sys.executable,str(SCRIPT),"--input",str(src),"--out-dir",str(out)],capture_output=True,text=True)
            self.assertEqual(result.returncode,2)
            self.assertIn("outcomesStatus",result.stderr)
            self.assertIn("roadmap.status",result.stderr)

    def test_schema_11_does_not_allow_assessment_complete_with_pending_rules(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); d=model()
            d.update({"schemaVersion":"1.1","assessmentStatus":"complete","outcomes":[],"outcomesStatus":"Not required.","decisions":[],"decisionsStatus":"No owner decisions required.","proposedChanges":[],"fileImpactStatus":"No changes proposed after complete assessment.","phases":[],"roadmapStatus":"No implementation required.","preservation":[],"preservationStatus":"No changes are proposed.","fileImpact":{"inspect":[],"create":[],"modify":[],"preserve":[]},"roadmap":{"status":"No implementation required.","phases":[]}})
            d["findings"][0].update({"classification":"required","disposition":"unverified","confidence":"low","requirementMeaning":"Module boundaries must be protected.","expectedOutcome":"Boundary check passes.","verification":"Run checks."})
            add_complete_review(d,root)
            d["coverage"].update({"reviewedRules":31,"pendingRules":25})
            src=root/"model.json"; out=root/"report"; src.write_text(json.dumps(d),encoding="utf-8")
            result=subprocess.run([sys.executable,str(SCRIPT),"--input",str(src),"--out-dir",str(out)],capture_output=True,text=True)
            self.assertEqual(result.returncode,2)
            self.assertIn("cannot be marked complete",result.stderr)

    def test_existing_authoritative_map_renders_declared_units_and_roles_without_proposal(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            d=model()
            d.update({
                "schemaVersion":"1.1",
                "outcomesStatus":"No future outcome is claimed by this renderer fixture.",
                "decisions":[],"decisionsStatus":"No additional ownership decision is pending; the existing map is authoritative.",
                "proposedChanges":[],"fileImpactStatus":"No file changes are proposed by this renderer fixture.",
                "fileImpact":{"inspect":[],"create":[],"modify":[],"preserve":[]},
                "phases":[],"roadmapStatus":"No implementation roadmap is asserted by this renderer fixture.",
                "roadmap":{"status":"No implementation is proposed.","phases":[]},
                "preservation":[],"preservationStatus":"No preservation change is proposed.",
                "assessmentSummary":{"benefitDetails":[]},
                "moduleMap":{
                    "status":"authoritative",
                    "summary":"The existing map was evaluated without replacement.",
                    "proposal":None,
                    "review":{"status":"approved","approval":{"status":"approved","reviewer":"Repository owner","reviewedOn":"2026-11-12"}},
                    "authoritativeMap":{
                        "present":True,"status":"complete","unitCount":4,
                        "coveredProduction":4,"productionFiles":4,"unownedPaths":[],"issues":[],
                        "units":[
                            {"id":"orders-impl","module":"orders","role":"implementation","paths":["src/orders"]},
                            {"id":"orders-contracts","module":"orders","role":"contracts","paths":["src/orders/contracts"]},
                            {"id":"host","module":"application","role":"host","paths":["src/host"]},
                            {"id":"shared-kernel","module":"shared","role":"shared-kernel","paths":["src/shared"]}
                        ]
                    },
                    "authoritativeUnits":[
                        {"id":"orders-impl","module":"orders","role":"implementation","paths":["src/orders"]},
                        {"id":"orders-contracts","module":"orders","role":"contracts","paths":["src/orders/contracts"]},
                        {"id":"host","module":"application","role":"host","paths":["src/host"]},
                        {"id":"shared-kernel","module":"shared","role":"shared-kernel","paths":["src/shared"]}
                    ],
                    "existingArchitecture":{"paths":["arch/architecture-rules.json"],"solutions":[],"dotnetProjects":[]}
                },
                "ownershipGate":{"status":"ready","deterministicChecksBlocked":False,"ownershipDependentRules":[],"independentReviewContinues":True}
            })
            d["findings"][0].update({
                "classification":"recommended","disposition":"not-applicable","confidence":"reviewed",
                "requirementMeaning":"This requirement is not applicable to the declared fixture scope.",
                "expectedOutcome":"The applicability decision remains explicit and evidence-backed.",
                "verification":"Review the applicability record and evidence.",
            })
            d["outcomes"][0].update({
                "whyItMatters":"A controlled example demonstrates the capability.",
                "practicalChange":"The selected enforcement reports the violation before merge.",
                "classification":"recommended","realization":"implementation-dependent",
                "verification":"Run positive and negative fixtures after implementation.",
            })
            add_complete_review(d,root)
            src=root/"model.json"; out=root/"report"
            src.write_text(json.dumps(d),encoding="utf-8")
            result=subprocess.run([sys.executable,str(SCRIPT),"--input",str(src),"--out-dir",str(out)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            page=(out/"proposal.html").read_text(encoding="utf-8")
            self.assertIn("How the product is divided today",page)
            self.assertIn("PARTS OF THE PRODUCT",page)
            self.assertIn("The map at a glance",page)
            for value in ("orders-impl","orders-contracts","application","host","shared-kernel","arch/architecture-rules.json"):
                self.assertIn(value,page)
            self.assertNotIn("CANDIDATE MODULES",page)
            self.assertIn("Who checked it:",page)
            self.assertIn("Repository owner",page)

    def test_schema_11_rejects_missing_findings_for_requirement_gaps_and_missing_outcomes(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); d=model()
            d.update({
                "schemaVersion":"1.1",
                "outcomesStatus":"Outcome mapping is pending.",
                "decisions":[],"decisionsStatus":"No owner decisions are required for this fixture.",
                "proposedChanges":[],"fileImpactStatus":"No file changes are proposed.",
                "fileImpact":{"inspect":[],"create":[],"modify":[],"preserve":[]},
                "phases":[],"roadmapStatus":"No implementation roadmap is asserted.",
                "roadmap":{"status":"No implementation roadmap.","phases":[]},
                "preservation":[],"preservationStatus":"No preservation action is proposed.",
                "assessmentSummary":{"benefitDetails":[{"benefit":"A gate can prevent new boundary violations.","classification":"achievable-through-adoption","basis":"A gate must be implemented."}]},
            })
            add_complete_review(d,root)
            d["qualitativeReview"]["rules"][0]["status"]="gap"
            d["qualitativeReview"]["rules"][0]["rationale"]="The inspected evidence shows a reviewed architectural gap for this requirement."
            d["conformance"][0]["disposition"]="does-not-conform"
            d["conformance"][0]["rationale"]=d["qualitativeReview"]["rules"][0]["rationale"]
            d["coverage"]["dispositionCounts"]["conforms"]-=1
            d["coverage"]["dispositionCounts"]["doesNotConform"]+=1
            d["findings"]=[]
            d["outcomes"]=[]
            d["value"]["benefits"]=[]
            src=root/"model.json"; out=root/"report"
            src.write_text(json.dumps(d),encoding="utf-8")
            result=subprocess.run([sys.executable,str(SCRIPT),"--input",str(src),"--out-dir",str(out)],capture_output=True,text=True)
            self.assertEqual(result.returncode,2)
            self.assertIn("Every nonconforming requirement",result.stderr)
            self.assertIn("Every assessment benefit detail",result.stderr)
            self.assertIn("The value summary must reconcile",result.stderr)

if __name__=='__main__': unittest.main()
