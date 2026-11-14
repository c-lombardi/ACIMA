#!/usr/bin/env python3
"""Render a six-page, plain-language ACIMA report from the skill's normalized JSON model."""
from __future__ import annotations
import argparse, hashlib, html, json, re, sys
from collections import Counter
from datetime import datetime
from pathlib import Path
HERE=Path(__file__).resolve().parent
SKILL=HERE.parent
CSS=SKILL/'assets/report-template.css'
VENDOR=SKILL/'vendor'
sys.path.insert(0, str(VENDOR/'conformance'))
from qualitative_review import validate_review, ReviewValidationError
CATALOG_PATH=VENDOR/'tools/acima-spec/rules.json'
CATALOG=json.loads(CATALOG_PATH.read_text(encoding='utf-8'))
CATALOG_SHA256=hashlib.sha256(CATALOG_PATH.read_bytes()).hexdigest()
EXPECTED_RULES={rule['id']:rule for rule in CATALOG.get('rules',[])}
PAGES={'index.html':'Overview','proposal.html':'Architecture and map','findings.html':'Findings','files.html':'Changes and files','plan.html':'Plan and decisions','evidence.html':'Evidence and limits'}
NAV=list(PAGES.items())
class ReportError(Exception): pass

def e(v):
    if v is None or v=='': return 'Not recorded'
    if isinstance(v,(dict,list)): v=json.dumps(v,ensure_ascii=False)
    return html.escape(str(v),quote=True)
def arr(v): return v if isinstance(v,list) else []
def refs(v):
    if isinstance(v,list): return ', '.join(str(x) for x in v) if v else 'No evidence references'
    return v
def finding_rules(x):
    if not isinstance(x,dict): return []
    out=[]
    if x.get('rule'): out.append(str(x.get('rule')))
    out.extend(str(r) for r in arr(x.get('requirementRefs')) if r)
    return out
def finding_rule(x):
    rules=finding_rules(x)
    return rules[0] if rules else ''
def key(v): return re.sub(r'[\s-]+','_',str(v).strip().lower()) if v is not None else ''
STATUS_LABELS={
    'recommended':'Recommended','recommended_with_limitations':'Recommended, with limitations',
    'not_recommended':'Not recommended','insufficient_evidence':'Needs more evidence',
    'not_supported':'Not supported','complete':'Complete','completed':'Complete',
    'incomplete':'Incomplete','not_started':'Not started','in_progress':'In progress',
    'pending':'Review pending','unknown':'Not established','not_supplied':'Not supplied',
    'not_recorded':'Not recorded','confirmed':'Confirmed','proposed':'Proposed',
    'approved':'Approved','required':'Required','optional':'Optional',
    'owner_decision':'Owner decision needed','conforms':'Meets requirement',
    'does_not_conform':'Does not meet requirement','partially_conforms':'Partly meets requirement',
    'not_applicable':'Not applicable','unverified':'Needs more evidence',
    'not_assessed':'Not yet reviewed','unsupported':'Not supported','blocked':'Blocked',
    'not_established':'Not established','standard_guarantee':'Standard guarantee',
    'implementation_dependent':'Depends on implementation','potential_benefit':'Potential benefit',
    'high':'High confidence','medium':'Medium confidence','low':'Low confidence',
    'proposal_required':'Proposal generated','proposal_for_incomplete_map':'Proposal for incomplete map',
    'authoritative':'Authoritative map','absent':'No map declared','stale':'Stale map',
    'incomplete':'Incomplete map','inconsistent':'Inconsistent map','ready':'Ready',
    'partially_approved':'Partly approved','deferred':'Deferred','rejected':'Rejected',
    'candidate':'Candidate','existing':'Declared','accepted':'Accepted','modified':'Modified',
    'discovery_failed':'Discovery did not complete','blocked_ownership':'Blocked until ownership is approved',
}
MODE_LABELS={'greenfield':'New codebase','brownfield':'Existing codebase','mixed':'Mixed codebase','unknown':'Not established'}
MODULE_STATE_ORDER=('accepted','modified','needs_owner','deferred','declared','rejected')
MODULE_STATE_LABELS={'accepted':'Accepted','modified':'Needs changes','needs_owner':'Needs an owner','deferred':'Set aside','declared':'Already documented','rejected':'Rejected'}
MODULE_STATE_CLASSES={'accepted':'good','modified':'good','needs_owner':'review','deferred':'neutral','declared':'neutral','rejected':'risk'}
PLAIN_GAP_RISK_ORDER={'high':0,'medium':1,'low':2,'review':3}
PLAIN_GAP_RISK_LABELS={'high':'High impact','medium':'Medium impact','low':'Lower impact','review':'Needs a closer look'}
PLAIN_GAP_RISK_PILLS={'high':'risk','medium':'review','low':'neutral','review':'review'}
MODULE_MAP_SCRIPT='''<script>
(() => {
  const root = document.querySelector('[data-module-directory]');
  if (!root) return;
  const tools = root.querySelector('[data-module-tools]');
  const input = root.querySelector('[data-module-search]');
  if (!tools || !input) return;
  tools.hidden = false;
  const buttons = Array.from(root.querySelectorAll('[data-status-filter]'));
  const rows = Array.from(root.querySelectorAll('[data-module-row]'));
  const count = root.querySelector('[data-module-count]');
  const empty = root.querySelector('[data-module-empty]');
  const total = rows.length;
  let status = 'all';
  const apply = () => {
    const query = input.value.trim().toLowerCase();
    let shown = 0;
    rows.forEach(row => {
      const text = row.textContent.toLowerCase();
      const matches = (!query || text.includes(query)) && (status === 'all' || row.dataset.status === status);
      row.hidden = !matches;
      if (matches) shown += 1;
    });
    count.textContent = shown === total ? total + ' parts' : shown + ' of ' + total + ' parts';
    empty.hidden = shown !== 0;
    buttons.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.statusFilter === status)));
  };
  input.addEventListener('input', apply);
  buttons.forEach(button => button.addEventListener('click', () => {
    status = button.dataset.statusFilter;
    apply();
  }));
  const revealTarget = () => {
    if (!location.hash) return;
    try {
      const target = document.querySelector(location.hash);
      if (!target || !target.matches('[data-module-row]')) return;
      input.value = '';
      status = 'all';
      apply();
      rows.forEach(row => row.classList.remove('is-target'));
      target.classList.add('is-target');
    } catch (error) {
      // Ignore malformed fragment identifiers; the directory remains usable.
    }
  };
  window.addEventListener('hashchange', revealTarget);
  revealTarget();
  apply();
})();
</script>'''
ACTION_LABELS={'inspect':'Inspect only','create':'Create','modify':'Modify','delete':'Remove','preserve':'Keep unchanged','no-change':'No change'}
MONTHS=('January','February','March','April','May','June','July','August','September','October','November','December')
def status_label(v, default='Not recorded'):
    if v is None or v=='': return default
    raw=str(v).strip(); label=STATUS_LABELS.get(key(raw))
    if label: return label
    text=re.sub(r'[_\-]+',' ',raw)
    return text[:1].upper()+text[1:] if text else default
def recommendation(v):
    labels={'recommended':'Recommended','recommended_with_limitations':'Recommended, with limitations',
            'not_recommended':'Not recommended','insufficient_evidence':'Not enough evidence to recommend',
            'not_supported':'Not supported for this repository'}
    return labels.get(key(v), status_label(v,'Recommendation not provided'))
def assessment(v):
    labels={'complete':'Assessment complete','completed':'Assessment complete',
            'incomplete':'Assessment incomplete','not_started':'Assessment not started'}
    label=labels.get(key(v))
    if label: return label
    if not v: return 'Assessment status not recorded'
    text=status_label(v)
    return text if text.lower().startswith('assessment') else 'Assessment '+text[:1].lower()+text[1:]
def repo_mode(v): return MODE_LABELS.get(str(v or '').lower(),status_label(v,'Not established'))
def action_label(v): return ACTION_LABELS.get(str(v or '').lower(),status_label(v))
def milestone(v): return 'Completed' if v is True else 'Not completed' if v is False else 'Not recorded'
def human_date(v):
    if v is None or v=='': return 'Date not recorded'
    raw=str(v).strip(); candidate=raw[:-1]+'+00:00' if raw.endswith('Z') else raw
    try: parsed=datetime.fromisoformat(candidate)
    except ValueError: return raw
    date=f'{parsed.day} {MONTHS[parsed.month-1]} {parsed.year}'
    if 'T' not in raw and ':' not in raw: return date
    hour=parsed.hour%12 or 12; minute=parsed.minute; ampm='am' if parsed.hour<12 else 'pm'
    offset=parsed.utcoffset()
    if offset is None: zone='local time'
    else:
        minutes=int(offset.total_seconds()//60); sign='+' if minutes>=0 else '-'; minutes=abs(minutes)
        zone='UTC' if minutes==0 else f'UTC{sign}{minutes//60:02d}:{minutes%60:02d}'
    return f'{date} at {hour}:{minute:02d} {ampm} ({zone})'
def when_text(v):
    return e(human_date(v)) if v else e('Date not recorded')


def decision_status(v):
    return {'superseded': 'Replaced', 'stale': 'Out of date'}.get(str(v), status_label(v))


def time_tag(v):
    if v is None or v=='': return e('Date not recorded')
    return f'<time datetime="{e(v)}">{e(human_date(v))}</time>'
def coverage_ratio(cov):
    reviewed=cov.get('reviewedRules'); required=cov.get('requiredRules')
    if reviewed in (None,'') or required in (None,''): return 'Not recorded'
    return f'{reviewed} of {required}'
def unresolved_note(cov):
    value=cov.get('unresolvedRules')
    if value in (None,''): return 'Unresolved count not recorded &middot; coverage, not a score'
    return f'{value} still unresolved &middot; coverage, not a score'
def pill(v, label=None):
    raw=str(v or 'Not recorded'); k=key(raw)
    cls='review' if any(x in k for x in ('incomplete','not_assessed','partial','pending','unknown','insufficient','review','unverified','not_enough','unsupported')) else 'risk' if any(x in k for x in ('gap','fail','blocked','not_recommended','significant','does_not_conform','not_met')) else 'good' if any(x in k for x in ('verified','pass','complete','approved','conforms','confirmed')) else 'neutral'
    return f'<span class="pill {cls}">{e(label if label is not None else status_label(raw))}</span>'
def bullets(xs,empty='No items supplied.'):
    if not xs:return f'<p class="empty">{e(empty)}</p>'
    out=[]
    for x in xs:
        if isinstance(x,dict):
            title=x.get('title') or x.get('name') or x.get('path') or x.get('question') or 'Item'; body=x.get('description') or x.get('why') or x.get('rationale') or x.get('outcome') or ''
            out.append(f'<li><b>{e(title)}</b>{f"<p>{e(body)}</p>" if body else ""}</li>')
        else:out.append(f'<li>{e(x)}</li>')
    return '<ul>'+''.join(out)+'</ul>'
def table(headers,rows,empty='No items supplied.',caption=None,row_headers=False):
    if not rows:return f'<p class="empty">{e(empty)}</p>'
    label=caption or 'Table: '+' / '.join(str(h) for h in headers)
    caption_id='table-'+hashlib.sha1(label.encode('utf-8')).hexdigest()[:10]
    head=''.join(f'<th scope="col">{e(h)}</th>' for h in headers)
    body=[]
    for row in rows:
        cells=[]
        for index,cell in enumerate(row):
            cells.append(f'<th scope="row">{e(cell)}</th>' if row_headers and index==0 else f'<td>{e(cell)}</td>')
        body.append('<tr>'+''.join(cells)+'</tr>')
    return f'<div class="table-wrap" role="region" aria-labelledby="{caption_id}" tabindex="0"><table><caption id="{caption_id}" class="visually-hidden">{e(label)}</caption><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'
def metric(label,value,note=''):
    return f'<div class="metric"><small>{e(label)}</small><strong>{e(value)}</strong>{f"<span>{e(note)}</span>" if note else ""}</div>'
def map_evidence(items):
    out=[]
    for item in arr(items):
        if isinstance(item,dict):
            path=item.get('path') or item.get('kind') or 'Evidence location not recorded'
            start=item.get('startLine'); end=item.get('endLine')
            location=f'{path}:{start}-{end}' if start and end and start!=end else f'{path}:{start}' if start else path
            observation=item.get('observation') or item.get('classification') or 'Evidence recorded'
            out.append(f'{location} — {observation}')
        elif item: out.append(str(item))
    return '; '.join(out) or 'No evidence references recorded'


def adoption_path(d):
    milestones=d.get('milestones') or {}
    if milestones.get('implementationComplete') is True:
        current=3
    elif milestones.get('assessmentComplete') is True or milestones.get('adoptionProposalComplete') is True:
        current=2
    elif milestones:
        current=1
    else:
        current=None
    stages=[
        ('No ACIMA','Ownership is implicit. Cross-module dependencies have no executable check.'),
        ('Foundation','Assessment, proposed boundaries and a scoped proposal exist. The check is not running yet.'),
        ('Implemented','The approved boundaries and checks are in place. The next step is making them routine.'),
        ('Continuous','The check, evidence review and agent guidance are part of normal change. Exceptions expire and the map is refreshed.'),
    ]
    progress=0 if current is None else (max(1,min(current,4))-1)/3*100
    steps=[]
    for number,(title,body) in enumerate(stages,1):
        if current is None:
            state='Destination' if number==4 else 'Stage'
            classes='path-step destination' if number==4 else 'path-step'
        elif number<current:
            state='Earlier'
            classes='path-step earlier'
        elif number==current:
            state='Current'
            classes='path-step current'
        elif number==4:
            state='Destination'
            classes='path-step destination'
        elif number==current+1:
            state='Next'
            classes='path-step upcoming'
        else:
            state='Later'
            classes='path-step'
        attr=' aria-current="step"' if number==current else ''
        steps.append(f'<li class="{classes}"{attr}><span class="path-step-label">{number:02d} &middot; {e(state)}</span><h3>{e(title)}</h3><p>{e(body)}</p></li>')
    now=stages[current-1][0] if current else 'Not recorded'
    if current and current<3:
        summary=f'Adoption path: current position {now}; next {stages[current][0]}; destination Continuous.'
    elif current==3:
        summary=f'Adoption path: current position {now}; destination Continuous.'
    else:
        summary='Adoption path: current position not recorded; destination Continuous.'
    return f'''<section id="adoption-path" class="adoption-path" aria-labelledby="adoption-path-title"><div class="path-head"><div><h2 id="adoption-path-title">Where this repository sits on the adoption path</h2><p class="lead">Four states, from no ACIMA work to an operating loop. The marker reflects recorded milestones; later states are proposals, not claims.</p></div><p class="path-now"><span>Current position</span><strong>{e(now)}</strong></p></div><ol class="path-track" style="--path-progress:{progress:.0f}%" aria-label="{e(summary)}">{''.join(steps)}</ol><p class="note">The last state is a destination, not a certification: a proposal cannot prove that checks, exception reviews and map updates continue over time. Current position is based on the report's recorded milestones.</p></section>'''

def module_state(item, *, declared=False):
    if declared:
        return 'declared'
    raw=key(item.get('reviewDecision') or item.get('status') or 'pending')
    if raw in ('accept','accepted','approved','complete','completed'):
        return 'accepted'
    if raw in ('modify','modified'):
        return 'modified'
    if raw in ('reject','rejected'):
        return 'rejected'
    if raw in ('defer','deferred'):
        return 'deferred'
    if raw in ('existing','declared'):
        return 'declared'
    return 'needs_owner'

def module_anchor(identifier, used=None):
    base=re.sub(r'[^a-z0-9]+','-',str(identifier or 'module').lower()).strip('-') or 'module'
    candidate='module-'+base
    if used is None:
        return candidate
    number=2
    while candidate in used:
        candidate=f'module-{base}-{number}'
        number+=1
    used.add(candidate)
    return candidate

def module_path_count(record):
    return len(record.get('paths') or [])+len(record.get('contracts') or [])

def module_records(d):
    mm=d.get('moduleMap') or {}
    proposal=mm.get('proposal')
    records=[]
    used=set()
    if isinstance(proposal,dict):
        for index,item in enumerate(arr(proposal.get('modules'))):
            if not isinstance(item,dict):
                continue
            identifier=str(item.get('id') or item.get('name') or f'module-{index+1}')
            name=str(item.get('name') or identifier)
            records.append({
                'id':identifier,
                'name':name,
                'anchor':module_anchor(identifier,used),
                'responsibility':str(item.get('responsibility') or ''),
                'ownership':str(item.get('ownership') or ''),
                'paths':arr((item.get('implementation') or {}).get('paths')),
                'contracts':arr((item.get('contracts') or {}).get('paths')),
                'dependencies':arr(item.get('dependencies')),
                'evidence':arr(item.get('evidence')),
                'state':module_state(item),
                'source':'proposal',
            })
    else:
        authority=mm.get('authoritativeMap') or {}
        units=arr(mm.get('authoritativeUnits') or authority.get('units'))
        for index,item in enumerate(units):
            if not isinstance(item,dict):
                continue
            identifier=str(item.get('id') or item.get('module') or f'unit-{index+1}')
            role=str(item.get('role') or 'declared')
            unit_paths=arr(item.get('paths'))
            contracts=unit_paths if key(role)=='contracts' else []
            paths=[] if key(role)=='contracts' else unit_paths
            records.append({
                'id':identifier,
                'name':str(item.get('module') or identifier),
                'anchor':module_anchor(identifier,used),
                'responsibility':f'{status_label(role)} unit',
                'ownership':str(item.get('source') or 'declared'),
                'paths':paths,
                'contracts':contracts,
                'dependencies':arr(item.get('dependencies')),
                'evidence':arr(item.get('evidence')),
                'state':'declared',
                'source':'declared',
            })
    return records

def module_pill(state):
    return f'<span class="pill {MODULE_STATE_CLASSES.get(state,"neutral")}">{e(MODULE_STATE_LABELS.get(state,status_label(state)))}</span>'

def module_path_list(paths, empty):
    values=[str(path) for path in arr(paths) if path]
    if not values:
        return f'<p class="empty">{e(empty)}</p>'
    return '<ul class="path-list">'+''.join(f'<li><code>{e(path)}</code></li>' for path in values)+'</ul>'

def module_dependency_list(dependencies):
    if not dependencies:
        return '<p class="empty">No connection to another part was recorded.</p>'
    items=[]
    for dependency in dependencies:
        if isinstance(dependency,dict):
            name=dependency.get('module') or dependency.get('moduleId') or 'Unnamed module'
            note='Private implementation suspected' if dependency.get('leaksImplementation') else 'Observed import'
            items.append(f'<li><b>{e(name)}</b> <span class="dep-note">{e(note)}</span></li>')
        elif dependency:
            items.append(f'<li>{e(dependency)}</li>')
    return '<ul class="path-list">'+''.join(items)+'</ul>' if items else '<p class="empty">No connection to another part was recorded.</p>'

def module_atlas_html(records):
    if not records:
        return '<p class="empty">No module records were supplied. This is not evidence that the repository has no architecture.</p>'
    ordered=sorted(records,key=lambda item:(MODULE_STATE_ORDER.index(item['state']),item['name'].lower(),item['id']))
    cells=[]
    for record in ordered:
        label=f'{record["name"]} — {module_path_count(record)} file or promise records — {MODULE_STATE_LABELS[record["state"]]}'
        cells.append(f'<a class="atlas-cell {record["state"]}" href="#{record["anchor"]}" title="{e(label)}" aria-hidden="true" tabindex="-1"></a>')
    return f'<div class="module-atlas" aria-hidden="true">{"".join(cells)}</div>'

def module_legend_html(records):
    counts=Counter(record['state'] for record in records)
    items=[]
    for state in MODULE_STATE_ORDER:
        if counts[state]:
            items.append(f'<li><span class="atlas-swatch {state}" aria-hidden="true"></span><span>{e(MODULE_STATE_LABELS[state])}</span><b>{counts[state]}</b></li>')
    return f'<ul class="module-legend" aria-label="Part status legend">{"".join(items)}</ul>'

def module_metrics_html(records, unassigned_count):
    total_paths=sum(module_path_count(record) for record in records)
    needs_owner=sum(record['state']=='needs_owner' for record in records)
    dependencies=sum(len(record['dependencies']) for record in records)
    private=sum(sum(1 for dependency in record['dependencies'] if isinstance(dependency,dict) and dependency.get('leaksImplementation')) for record in records)
    return (f'<div class="metrics">{metric("PARTS OF THE PRODUCT",len(records),"Proposed parts" if records and records[0]["source"]=="proposal" else "Parts already written down")}'
            f'{metric("FILES COVERED",total_paths,"Code files and promises")}'
            f'{metric("NEEDS AN OWNER",needs_owner,f"{unassigned_count} files outside any part" if unassigned_count else "No files outside the map")}'
            f'{metric("CONNECTIONS",dependencies,f"{private} private-code links")}</div>')

def module_directory_html(records):
    if not records:
        return '<p class="empty">No module directory can be shown because no module records were supplied.</p>'
    counts=Counter(record['state'] for record in records)
    filter_buttons=[f'<button type="button" class="filter-chip" data-status-filter="all" aria-pressed="true">All <span>{len(records)}</span></button>']
    for state in MODULE_STATE_ORDER:
        if counts[state]:
            filter_buttons.append(f'<button type="button" class="filter-chip" data-status-filter="{state}" aria-pressed="false">{e(MODULE_STATE_LABELS[state])} <span>{counts[state]}</span></button>')
    row_html=[]
    ordered=sorted(records,key=lambda item:(MODULE_STATE_ORDER.index(item['state']),item['name'].lower(),item['id']))
    for record in ordered:
        dependencies=record['dependencies']
        private=sum(1 for dependency in dependencies if isinstance(dependency,dict) and dependency.get('leaksImplementation'))
        details=(f'<details><summary>Open details</summary>'
                 f'<p><b>What it does:</b> {e(record["responsibility"])}</p>'
                 f'<p><b>How we identified it:</b> {e(record["ownership"])}</p>'
                 f'<p><b>Files</b></p>{module_path_list(record["paths"],"No file was recorded for this part.")}'
                 f'<p><b>Promises to other parts</b></p>{module_path_list(record["contracts"],"No promise to another part was recorded.")}'
                 f'<p><b>Connections to other parts</b></p>{module_dependency_list(dependencies)}'
                 f'<p><b>Where this came from</b></p><p>{e(map_evidence(record["evidence"]))}</p></details>')
        row_html.append(f'<tr id="{record["anchor"]}" data-module-row data-status="{record["state"]}">'
                        f'<th scope="row"><span class="module-name">{e(record["name"])}</span><small class="module-id">{e(record["id"])}</small></th>'
                        f'<td>{module_pill(record["state"])}</td>'
                        f'<td>{e(record["responsibility"])}</td>'
                        f'<td class="num">{module_path_count(record)}</td>'
                        f'<td class="num">{len(record["contracts"])}</td>'
                        f'<td class="num">{len(dependencies)}{"<small>"+str(private)+" private</small>" if private else ""}</td>'
                        f'<td>{details}</td></tr>')
    return (f'<div class="module-directory" data-module-directory>'
            f'<div class="map-tools" data-module-tools hidden>'
            f'<div class="map-search" role="search"><label for="module-search">Find a part</label>'
            f'<input id="module-search" type="search" data-module-search autocomplete="off" placeholder="Name, file, responsibility or connection"></div>'
            f'<div class="map-filters" role="group" aria-label="Filter parts by status">{"".join(filter_buttons)}</div>'
            f'<p class="map-result" data-module-count aria-live="polite">{len(records)} parts</p>'
            f'<p class="empty map-empty" data-module-empty hidden>No part matches this search.</p></div>'
            f'<noscript><p class="note">All parts are listed below. Use your browser\'s Find command to search; the filter buttons require JavaScript.</p></noscript>'
            f'<div class="table-wrap module-table-wrap" role="region" aria-labelledby="module-table-caption" tabindex="0">'
            f'<table class="module-table" id="module-table"><caption id="module-table-caption" class="visually-hidden">Parts of the product: name, status, what it does, files, promises, connections and details</caption>'
            f'<thead><tr><th scope="col">Part</th><th scope="col">Status</th><th scope="col">What it does</th><th scope="col">Files</th><th scope="col">Promises</th><th scope="col">Links</th><th scope="col">More</th></tr></thead>'
            f'<tbody>{"".join(row_html)}</tbody></table></div>{MODULE_MAP_SCRIPT}</div>')

def plain_gap_risk(*values):
    for value in values:
        if isinstance(value,(dict,list)):
            continue
        token=key(value)
        if not token:
            continue
        if any(word in token for word in ('critical','high','severe','blocker','urgent','essential')):
            return 'high'
        if any(word in token for word in ('medium','moderate','important')):
            return 'medium'
        if any(word in token for word in ('low','minor','cleanup')):
            return 'low'
        if any(word in token for word in ('review','unknown','uncertain','unverified','needs_more','pending')):
            return 'review'
    return ''

def finding_gap_risk(item):
    explicit=plain_gap_risk(item.get('risk'),item.get('realRisk'),item.get('severity'))
    if explicit:
        return explicit
    classification=key(item.get('classification'))
    disposition=key(item.get('disposition') or item.get('status'))
    if classification in ('required','essential') or disposition in ('does_not_conform','blocked'):
        return 'high'
    if classification=='recommended' or disposition in ('partially_conforms','unverified','not_assessed'):
        return 'medium'
    if classification in ('optional','no_change'):
        return 'low'
    return 'review'

def plain_gap_record(item,basis=''):
    raw_paths=item.get('paths') or []
    if isinstance(raw_paths,str):
        raw_paths=[raw_paths]
    paths=[str(path) for path in raw_paths if path]
    if not paths and item.get('path'):
        paths=[str(item.get('path'))]
    return {
        'title':str(item.get('title') or item.get('what') or item.get('summary') or 'Unrecorded gap'),
        'risk':plain_gap_risk(item.get('risk')) or finding_gap_risk(item),
        'whatItCosts':str(item.get('whatItCosts') or item.get('cost') or item.get('why') or 'The report does not record what this could cost.'),
        'fixInvolves':str(item.get('fixInvolves') or item.get('fix') or item.get('recommendation') or 'The report does not record what fixing it would involve.'),
        'paths':paths,
        'confidence':str(item.get('confidence') or ''),
        'basis':str(item.get('basis') or basis),
    }

def plain_gap_records(d):
    explicit=arr(d.get('plainLanguageGaps'))
    records=[]
    if explicit:
        for index,item in enumerate(explicit):
            if isinstance(item,dict):
                record=plain_gap_record(item)
                record['_order']=index
                records.append(record)
        if any(record['risk'] for record in records):
            records.sort(key=lambda item:(PLAIN_GAP_RISK_ORDER.get(item['risk'],4),item['_order']))
        for record in records:
            record.pop('_order',None)
        return records
    for item in arr(d.get('findings')):
        if isinstance(item,dict):
            records.append(plain_gap_record(item,'From a problem recorded on the Findings page.'))
    proposal=(d.get('moduleMap') or {}).get('proposal')
    if isinstance(proposal,dict):
        if not (d.get('moduleMap') or {}).get('review'):
            records.append({
                'title':'No one has confirmed the proposed map',
                'risk':'high',
                'whatItCosts':'The team could assign work or add checks against a boundary that does not match how the product is really owned.',
                'fixInvolves':'Walk through each proposed part with the person who owns that area. Accept it, change it or reject it before relying on the map.',
                'paths':[],'confidence':'','basis':'From the unreviewed map proposal.',
            })
        unassigned=arr(proposal.get('unassigned'))
        if unassigned:
            records.append({
                'title':'Some code is not claimed by any part',
                'risk':'high',
                'whatItCosts':f'{len(unassigned)} production path{"s" if len(unassigned)!=1 else ""} can drift, duplicate work or change without a clear owner noticing.',
                'fixInvolves':'Assign each path to a part or mark it as shared, tooling or not product code. Record the decision where the map is kept.',
                'paths':[str(item.get('path')) for item in unassigned if isinstance(item,dict) and item.get('path')],
                'confidence':'','basis':'From unassigned paths in the map proposal.',
            })
    seen=set(); unique=[]
    for record in records:
        marker=record['title'].strip().casefold()
        if marker and marker not in seen:
            seen.add(marker); unique.append(record)
    unique.sort(key=lambda item:PLAIN_GAP_RISK_ORDER.get(item.get('risk'),4))
    return unique

def plain_language_gaps_section(d):
    if not d.get('moduleMap') and not arr(d.get('plainLanguageGaps')):
        return ''
    records=plain_gap_records(d)
    if not records:
        return ''
    shown=records[:6]
    cards=[]
    for index,record in enumerate(shown,1):
        risk=record.get('risk') or 'review'
        label=PLAIN_GAP_RISK_LABELS.get(risk,'Worth knowing')
        paths=record.get('paths') or []
        paths_html=''
        if paths:
            paths_html=(f'<details class="gap-paths"><summary>Where this shows up</summary>'
                        f'<ul class="path-list">{"".join(f"<li><code>{e(path)}</code></li>" for path in paths)}</ul></details>')
        confidence=(f'<p class="gap-meta"><b>How sure we are:</b> {e(status_label(record["confidence"]))}</p>'
                    if record.get('confidence') else '')
        basis=(f'<p class="gap-meta">{e(record["basis"])}</p>' if record.get('basis') else '')
        cards.append(f'<li class="gap-card risk-{risk}"><span class="gap-rank" aria-hidden="true">{index}</span>'
                     f'<div class="gap-body"><div class="row"><h3>{e(record["title"])}</h3>'
                     f'<span class="pill {PLAIN_GAP_RISK_PILLS.get(risk,"neutral")}">{e(label)}</span></div>'
                     f'<p><b>What it could cost this product:</b> {e(record["whatItCosts"])}</p>'
                     f'<p><b>What fixing it involves:</b> {e(record["fixInvolves"])}</p>'
                     f'{paths_html}{confidence}{basis}</div></li>')
    more=(f'<p class="note">Showing the {len(shown)} highest-impact gaps. '
          f'<a href="findings.html#findings">See all findings and evidence</a>.</p>' if len(records)>len(shown) else '')
    return (f'<section id="plain-language-gaps" class="plain-gaps"><small>WHAT COULD GO WRONG</small>'
            f'<h2>What matters before the map</h2><p class="lead">These are the practical gaps behind the map, '
            f'ordered by what could affect the product soonest. Each one says what it could cost you and what fixing it would involve.</p>'
            f'<p class="note">This page stays in product language. '
            f'The <a href="findings.html#findings">Findings page</a> keeps the detailed evidence.</p>'
            f'<ol class="gap-list">{"".join(cards)}</ol>{more}</section>')

def d016_allowlist_section(d):
    proposal=d.get('d016Allowlist') or {}
    if not proposal:
        return ''
    candidates=arr(proposal.get('candidates'))
    rows=[(item.get('name'),item.get('path'),item.get('line'),item.get('evidence')) for item in candidates if isinstance(item,dict)]
    proposed=arr(proposal.get('proposedValue'))
    snippet=json.dumps({'partialHelpers':proposed},indent=2,ensure_ascii=False)
    current=proposal.get('currentExecution') or 'not executed'
    reason=proposal.get('reason') or 'The enforcer did not report why this check did not run.'
    approval=proposal.get('approval') or 'The repository owner must approve this configuration change before it is applied.'
    verification=proposal.get('verification') or 'After approval, run the enforcer and confirm the check reports executed: true.'
    candidate_table=table(['Helper candidate','File','Line','Evidence'],rows,
        'No helper names were discovered by this assessment. Confirm that the repository has no partial-application helpers, or add their exact names before approving.',
        caption='Partial-application helper candidates')
    empty_note=('The proposed value is an explicit empty list. It records an owner decision that no partial-application helper is used. '
                if not proposed else '')
    return (f'<section id="d016-allowlist"><small>COMPLETE THE AUTOMATED CHECK SET</small>'
            f'<h2>One configuration decision is still blocking a check</h2>'
            f'<p class="lead">The partial-application check is not running because the repository has not declared which helper names it should inspect. '
            f'Without that declaration the run cannot reach the full automated rule set; this is a configuration gap, not a clean result.</p>'
            f'<p class="reconciliation"><b>Current state:</b> {e(status_label(current))}. {e(reason)}</p>'
            f'{candidate_table}'
            f'<p><b>Proposed configuration</b></p><pre><code>{e(snippet)}</code></pre>'
            f'<p>{e(empty_note)}<b>Owner approval:</b> {e(approval)}</p>'
            f'<p><b>After approval:</b> {e(verification)}</p>'
            f'<p class="note">This changes which helper calls the check inspects. It does not waive a finding or make an unlisted helper safe. Internal reference: {e(proposal.get("rule") or "D016")}.</p></section>')

def module_map_sections(d):
    mm=d.get('moduleMap') or {}
    authority=mm.get('authoritativeMap') or {}
    proposal=mm.get('proposal')
    gate=d.get('ownershipGate') or {}
    modules=arr((proposal or {}).get('modules'))
    recs=arr((proposal or {}).get('recommendations'))
    decisions=arr((proposal or {}).get('decisions'))
    units=arr(mm.get('authoritativeUnits') or authority.get('units'))
    review=mm.get('review') or {}
    review_meta=review.get('approval') or review
    review_status=review.get('status') or (proposal or {}).get('status') or 'not recorded'
    authority_status=authority.get('status') or ('present' if authority.get('present') else 'absent')
    gate_status=gate.get('status') or ('ready' if authority_status=='complete' else 'blocked')
    has_proposal=isinstance(proposal,dict)
    if has_proposal:
        map_intro=(f'<p class="reconciliation"><b>This map is a proposal, not a decision.</b> {e(proposal.get("basis") or mm.get("summary"))} Current status: <b>{e(status_label(review_status))}</b>. Each part stays a question until its owner accepts, changes or rejects it.</p>'
                   '<p class="note">The map was built from folders, projects and imports. Those are clues about where work lives, not proof that an area is a real product boundary.</p>')
    else:
        map_intro=f'<p class="reconciliation"><b>The product already has a written map.</b> {e(status_label(authority_status))}. {e(authority.get("summary") or "The report checked the existing map rather than replacing it with a new proposal.")}</p>'
        if authority.get('present') and not review:
            map_intro+='<p class="note">The map is written down in repository settings, but no separate review receipt was supplied. A complete file is not proof that the current owners still agree with it.</p>'
    issues=arr(authority.get('issues'))
    issue_html=table(['Problem','What it means'],[(x.get('code') if isinstance(x,dict) else 'Problem',x.get('detail') if isinstance(x,dict) else x) for x in issues],caption='Problems with the map',row_headers=True) if issues else '<p class="empty">No problem with the map was recorded.</p>'

    records=module_records(d)
    if has_proposal:
        unassigned=arr(proposal.get('unassigned'))
        quality=proposal.get('quality') or {}
    else:
        unassigned=[{'path':path,'reason':'This production path is not covered by an authoritative module or explicit non-module disposition.'} for path in arr(authority.get('unownedPaths'))]
        quality=mm.get('quality') or {}

    dep_rows=[]
    if has_proposal:
        dependency_totals=[]
        for module in modules:
            dependencies=arr(module.get('dependencies'))
            if dependencies:
                private=sum(1 for dep in dependencies if isinstance(dep,dict) and dep.get('leaksImplementation'))
                dependency_totals.append((module.get('name') or module.get('id'),len(dependencies),private))
        dependency_totals.sort(key=lambda item:(-item[1],str(item[0]).lower()))
        dep_rows=dependency_totals[:12]
        dep_table=table(['Part','Connections to other parts','Private-code links'],dep_rows,
                        'No connection was seen in the imports inspected.',
                        caption='Parts with the most connections',row_headers=True)
        dep_note='Only the twelve most connected parts are shown here; each part record below lists its own connections.'
    else:
        for unit in units:
            if isinstance(unit,dict) and unit.get('role')=='contracts':
                dep_rows.append((unit.get('module'),unit.get('id'),'Declared contracts unit',', '.join(arr(unit.get('paths')))))
        dep_table=table(['Part or area','Connection or role','What it is','Where'],dep_rows,
                        'The written map does not prove that parts are actually kept apart. See the checks and evidence for that.',
                        caption='Promises written down in the map',row_headers=True)
        dep_note='A written promise does not prove that the code keeps it.'

    unassigned_table=table(
        ['File or folder','Why no one has claimed it'],
        [(x.get('path'),x.get('reason')) for x in unassigned],
        ('Every production file the scan found sits under a proposed part. Someone still has to confirm that assignment.' if has_proposal else
         'No unclaimed production files were recorded in the written map.'),
        caption='Code no one has claimed',row_headers=True
    )
    observations=arr(quality.get('observations'))
    quality_table=table(['What we looked at','What we saw','How we know','How sure'],[(x.get('topic'),x.get('observation'),status_label(x.get('basis')),status_label(x.get('confidence'))) for x in observations],'No observation about the map was recorded.',caption='What the map shows',row_headers=True)
    rec_cards=''.join(f'<article class="decision-row"><div class="row"><h3>{e(x.get("title"))}</h3>{pill(x.get("classification"),status_label(x.get("classification")))}</div><p><b>What we saw:</b> {e(x.get("observed"))}</p><p><b>What it could cost:</b> {e(x.get("whyItMatters"))}</p><p><b>What to do:</b> {e(x.get("recommendation"))}</p><p><b>What gets better:</b> {e(x.get("benefit"))}</p><p><b>What could go wrong:</b> {e(x.get("risk"))} {e(x.get("uncertainty"))}</p><p><b>Do you need to decide?</b> {"Yes" if x.get("requiresUserInput") else "No decision needed for this item"} &middot; <b>Priority:</b> {"Essential" if x.get("essential") else "Optional refinement"}</p><details><summary>Where this came from</summary><p>{e(map_evidence(x.get("evidence")))}</p><p><b>Your decision:</b> {e(status_label(x.get("decision") or "pending")) if x.get("requiresUserInput") else "No decision needed; this is a recommended fix."}</p></details></article>' for x in recs) or (
        '<p class="empty">No new recommendation about the map was generated. The existing map was checked in place; this does not mean other adoption work is unnecessary.</p>'
        if not has_proposal else
        '<p class="empty">No change is recommended from the available discovery evidence. That is a proposal judgement, not proof that the current boundaries are ideal.</p>'
    )
    if decisions:
        decision_table=(f'<p class="reconciliation"><b>{len(decisions)} map decision{"s" if len(decisions)!=1 else ""} need you.</b> Each is written as a plain-language choice on the <a href="plan.html#decisions">Plan page</a>, with a recommendation, effort and what stays blocked. This page keeps the evidence behind the map.</p>')
    else:
        decision_table='<p class="empty">No new map decision is pending because the report is using the existing written map. What is written above does not approve unrelated changes.</p>'

    if review:
        reviewer=review_meta.get('reviewer') or review.get('reviewer') or 'not recorded'
        reviewed_on=review_meta.get('reviewedOn') or review.get('reviewedOn') or 'not recorded'
        approval_status=review.get('status') or review_meta.get('status') or 'recorded'
        review_html=f'<p class="note"><b>Who checked it:</b> {e(status_label(approval_status))} &middot; {e(reviewer)} &middot; {e(reviewed_on)} &middot; proposal {e(mm.get("proposalId") or "not recorded")}.</p>'
    else:
        review_html=(
            '<p class="note">No one has reviewed or approved this map yet. These are proposed parts, not agreed boundaries, so do not rely on them for checks that need a clear owner.</p>'
            if has_proposal else
            '<p class="note">No separate review receipt was supplied. A complete file is shown as written down, not as proof that the current owners still agree with it.</p>'
        )
    unassigned_count=len(unassigned)
    heading="A proposed map of the product" if has_proposal else "How the product is divided today"
    atlas=module_atlas_html(records)
    legend=module_legend_html(records)
    directory=module_directory_html(records)
    module_metrics=module_metrics_html(records,unassigned_count)
    ownership_note=(f'<p class="context-line"><b>Can checks run?</b> {e(status_label(gate_status))} <span aria-hidden="true">&middot;</span> <b>Map status:</b> {e(status_label(review_status))} <span aria-hidden="true">&middot;</span> <b>How to read this:</b> each square is one part; the list below is the detail.</p>')
    return f'''<section id="module-map" class="module-map"><small>HOW THE PRODUCT IS DIVIDED</small><h2>{e(heading)}</h2>{map_intro}{module_metrics}{ownership_note}<div class="module-atlas-head"><h3>The map at a glance</h3><p>Each square is one part. Colour shows whether it has been accepted, needs changes, or still needs an owner. The list below has the same information in words.</p></div>{atlas}{legend}{review_html}{issue_html}{directory}</section><section id="contracts-and-dependencies"><h2>How parts depend on each other</h2><p class="lead">A promise from one part to another is a fact about ownership, not proof that the promise is clean or safe to depend on.</p>{dep_table}<p class="note">{e(dep_note)}</p></section><section id="unassigned-code"><h2>Code no one has claimed</h2>{unassigned_table}</section><section id="map-quality"><h2>What the map shows</h2>{quality_table}</section><section id="map-recommendations"><h2>What we recommend</h2><div class="stack">{rec_cards}</div></section><section id="map-decisions"><h2>What needs your decision</h2>{decision_table}<p class="note">Reading this report does not approve the map or authorize changes. {e(mm.get("nextDecision") or "No approval is implied.")}</p></section>'''

def agent_guidance_section(d):
    guidance=d.get('agentGuidance') or {}
    if not guidance:
        return ''
    validation=guidance.get('validation') or {}
    files=guidance.get('files') or []
    problem_rows=[(x,) for x in arr(validation.get('problems'))]
    return f'<section id="ai-agent-guidance"><small>AI AGENT GUIDANCE</small><h2>How future agents will build here</h2><p class="lead">Primary instructions: <b>{e(guidance.get("primaryFile") or "not recorded")}</b>. Convention: <b>{e((guidance.get("convention") or {}).get("convention") or "not recorded")}</b>. Validation: <b>{e(status_label(validation.get("status") or "not run"))}</b>.</p><p class="note">Existing user-authored instructions preserved: {e("yes" if guidance.get("preservedExisting") else "not established")}. This is structural validation, not proof that every coding agent will follow the guidance.</p>{table(["Generated or updated file"],[(x,) for x in files],"No agent-instruction file was written.",caption="AI agent guidance files")}{table(["Validation problem"],problem_rows,"No validation problem was recorded.",caption="AI agent guidance validation problems") if problem_rows else ""}<p class="note">Rules covered: {e(validation.get("rulesCovered"))} of {e(validation.get("rulesRequired"))}. Supporting guidance is under <code>acima/handoff/agent-guidance/</code>.</p></section>'

def remediation_outcome(d):
    rem=d.get('remediation') or {}
    if not rem:
        return ''
    rows=[(x.get('id'),x.get('status'),', '.join(arr(x.get('files')))) for x in arr(rem.get('changed')) if isinstance(x,dict)]
    failures=[(x.get('id'),x.get('status'),x.get('reason')) for x in arr(rem.get('failures')) if isinstance(x,dict)]
    return f'<section id="remediation-outcome"><small>IMMEDIATE REMEDIATION</small><h2>What was corrected</h2><p class="lead">Decision: <b>{e(status_label(rem.get("choice")))}</b>. Outcome: <b>{e(status_label(rem.get("status")))}</b>. {e(rem.get("claim"))}</p>{table(["Recommendation","Result","Files"],rows,"No recommendation was implemented; this is a deferred outcome, not a clean result.",caption="Recommendation-to-change traceability",row_headers=True)}{table(["Recommendation","Status","Why it remains"],failures,"No blocked or manual recommendation was recorded.",caption="Remaining remediation items",row_headers=True)}</section>'

def adoption_workflow(d):
    wf=d.get('adoptionWorkflow') or {}
    if not wf:
        return ''
    stages=arr(wf.get('stages'))
    rows=[(x.get('label') or x.get('name'),status_label(x.get('status')),x.get('detail'),x.get('nextAction')) for x in stages if isinstance(x,dict)]
    phase=wf.get('phaseLabel') or wf.get('phase') or 'not recorded'
    nxt=wf.get('next') or {}
    stage_table=table(['Stage','Status','What this proves or blocks','Next action'],rows,'No workflow stages were recorded.',caption='Adoption workflow stages',row_headers=True) if rows else '<p class="empty">No workflow stage evidence was supplied.</p>'
    warning=''
    if wf.get('staleWarning'):
        warning=f'<p class="reconciliation"><b>Stale workflow:</b> {e(wf.get("staleWarning"))}</p>'
    next_text=nxt.get('action') or 'No next action is recorded.'
    guidance=wf.get('agentGuidance') or {}
    guidance_summary=''
    if guidance:
        validation=guidance.get('validation') or {}
        guidance_summary=(f'<div class="reconciliation"><b>AI agent guidance:</b> {e(status_label(validation.get("status") or "proposed"))}. '
                          f'Primary file: <code>{e(guidance.get("primaryFile") or "not recorded")}</code>. '
                          f'Existing content preserved: {e(guidance.get("preservedExisting"))}; '
                          f'rules represented: {e(validation.get("rulesCovered"))}/{e(validation.get("rulesRequired"))}.</div>')
    rem=wf.get('remediation') or {}; result=rem.get('resultData') or {}
    remediation=''
    if rem:
        result_text=('No remediation decision has been recorded yet.' if not result else
                     f"Decision: {status_label(result.get('choice'))}. Outcome: {status_label(result.get('status'))}. Changed files: {len(arr(result.get('changed')))}. Remaining manual or failed items: {len(arr(result.get('failures')))}.")
        changed=table(['Recommendation','Files'],[(x.get('id'),', '.join(arr(x.get('files')))) for x in arr(result.get('changed'))],caption='Remediation changes applied',row_headers=True) if result else ''
        remaining=table(['Recommendation','Status','Reason'],[(x.get('id'),status_label(x.get('status')),x.get('reason')) for x in arr(result.get('failures'))],caption='Remediation items still outstanding',row_headers=True) if result and result.get('failures') else ''
        remediation=f'<div class="reconciliation"><b>Immediate remediation:</b> {e(result_text)} <b>Maturity:</b> {e(status_label((rem.get("maturity") or {}).get("mode") or "not established"))}. <b>Risk:</b> {e(status_label((rem.get("risk") or {}).get("level") or "not established"))}.</div>{changed}{remaining}'
    as_of=str(wf.get('asOf') or '')
    stamp=f"{as_of[:16].replace('T',' ')} UTC" if as_of else ''
    progress_note=(f'<p class="note">Progress as of <time datetime="{e(as_of)}">{e(stamp)}</time>. This section refreshes automatically after every recorded workflow change; the reviewed proposal content does not change.</p>' if stamp else '<p class="note">This section refreshes automatically after every recorded workflow change; the reviewed proposal content does not change.</p>')
    return f'<section id="adoption-workflow"><small>ADOPTION WORKFLOW</small><h2>Where the adoption stands</h2><p class="lead">Mode: <b>{e(status_label(wf.get("mode") or "unknown"))}</b>. Current phase: <b>{e(phase)}</b>. Current stage: <b>{e(status_label((wf.get("currentStage") or {}).get("label") or "not started"))}</b>.</p>{progress_note}{warning}{guidance_summary}{remediation}{stage_table}<p class="note"><b>Next action:</b> {e(next_text)}</p><p class="note">Configured, generated and verified are separate states. This section does not turn a proposal or a CI file into proof that a remote check ran.</p></section>'


def module_map_overview(d):
    mm=d.get('moduleMap') or {}
    if not mm:
        return '<section id="module-ownership"><small>HOW THE PRODUCT IS DIVIDED</small><h2>This report does not include a map of the product</h2><p>No proposed map or written map was included. Do not assume the product has no clear boundaries just because this section is missing.</p></section>'
    authority=mm.get('authoritativeMap') or {}
    proposal=mm.get('proposal')
    gate=d.get('ownershipGate') or {}
    review=mm.get('review') or {}
    review_meta=review.get('approval') or review
    status=authority.get('status') or ('present' if authority.get('present') else 'absent')
    review_status=review.get('status') or (proposal or {}).get('status') or 'not recorded'
    rules=arr(gate.get('ownershipDependentRules'))
    if proposal:
        next_text=mm.get('nextDecision') or 'Review the proposed boundaries and recommendations; no ownership is approved by this report.'
        body=f'<p class="lead">{e(mm.get("summary"))}</p><p class="reconciliation"><b>The proposed map is not agreed yet.</b> Current status: <b>{e(status_label(review_status))}</b>. {e(next_text)}</p><p class="note">The rest of the review can continue. Checks that need an agreed map stay blocked until someone confirms the parts.</p>'
        count_label='PARTS PROPOSED'
        count_value=len(arr(proposal.get('modules')))
    else:
        units=arr(mm.get('authoritativeUnits') or authority.get('units'))
        count_value=authority.get('unitCount') if authority.get('unitCount') is not None else len(units)
        coverage=f'{authority.get("coveredProduction",0)} of {authority.get("productionFiles",0)} production files covered'
        unowned=len(arr(authority.get('unownedPaths')))
        body=(f'<p class="lead">{e(mm.get("summary") or authority.get("summary"))}</p>'
              f'<p class="reconciliation"><b>The product already has a written map.</b> {e(status_label(status))}. '
              f'It lists {e(count_value)} parts; {e(coverage)}; {unowned} files are not claimed. '
              f'The report checked that map rather than replacing it.</p>')
        if review:
            reviewer=review_meta.get('reviewer') or review.get('reviewer') or 'not recorded'
            reviewed_on=review_meta.get('reviewedOn') or review.get('reviewedOn') or 'not recorded'
            body+=f'<p class="note">Who checked it: {e(status_label(review_status))}; {e(reviewer)}; {e(reviewed_on)}.</p>'
        else:
            body+='<p class="note">The map is written down, but no separate review receipt is recorded. A complete file is not proof that the current owners still agree with it.</p>'
        count_label='PARTS WRITTEN DOWN'
    return f'<section id="module-ownership"><small>HOW THE PRODUCT IS DIVIDED</small><h2>Can the checks run?</h2>{body}<div class="metrics compact">{metric("WRITTEN-DOWN MAP",status_label(status))}{metric(count_label,count_value)}{metric("CAN CHECKS RUN?",status_label(gate.get("status") or "blocked"),f"{len(rules)} checks need an agreed map" if rules else "No checks need an agreed map")}</div><p class="cross-links"><span>Related:</span> <a href="proposal.html#module-map">Map of the product</a> <a href="proposal.html#map-decisions">Decisions</a> <a href="evidence.html#ownership-blocked">Checks needing an agreed map</a></p></section>'

OBJECTIVE_LABELS={
    'assessment':'Assessment','local-enforcement':'Local enforcement','baseline-waivers':'Baseline waivers',
    'ci-enforcement':'CI enforcement','developer-handoff':'Developer handoff','agent-guidance':'AI agent guidance',
    'adoption-notifications':'Adoption notifications','source-remediation':'Source remediation',
    'full-conformance':'Full conformance','communication-governance':'Communication governance',
}
KIND_LABELS={
    'report-review':'Report review','module':'Part of the product','module-path':'File ownership',
    'recommendation':'Recommendation','scope-objective':'Stage','scope-path':'File','remediation':'Remediation',
}
CONSOLE_JS="""
<script>
(function(){
  var data=document.getElementById('acima-console');
  if(!data){return;}
  var catalog={},state={};
  try{catalog=JSON.parse(data.textContent||'{}')}catch(e){catalog={}}
  var stateNode=document.getElementById('acima-console-state');
  try{state=stateNode?JSON.parse(stateNode.textContent||'{}'):{}}catch(e){state={}}
  var page=data.getAttribute('data-page')||'plan';
  var error=document.getElementById('answers-error');
  var text=document.getElementById('answers-text');
  var status=document.getElementById('answers-status');
  var packageChoice=document.getElementById('answers-package');
  function show(message,focus){
    if(!error){return}
    error.textContent=message; error.hidden=false; if(focus){error.focus()}
  }
  if(!catalog.reportId){
    show('This report\\'s answer data could not be read. Regenerate the report and try again.',false);
    Array.prototype.forEach.call(document.querySelectorAll('#answers-save,#answers-copy,#use-recommended'),function(button){
      button.disabled=true;
    });
    return;
  }
  var inForce={};
  (state.answers||[]).forEach(function(a){
    inForce[a.kind+':'+a.id]={decision:a.decision,source:a.sourceSha256||''};
  });
  function radios(name){return Array.prototype.slice.call(document.querySelectorAll('input[name="'+name+'"]'))}
  function checkedValue(name){var found=radios(name).filter(function(r){return r.checked});return found.length?found[0].value:''}
  function markCustom(){if(packageChoice){packageChoice.value='custom'}}
  (catalog.objectives||[]).forEach(function(o){
    var prior=inForce['scope-objective:'+o.id];
    radios('objective:'+o.id).forEach(function(r){if(prior&&r.value===prior.decision){r.checked=true}});
  });
  (catalog.paths||[]).forEach(function(p){
    var prior=inForce['scope-path:'+p.path];
    var box=document.querySelector('input[name="path:'+p.path+'"]');
    if(box&&prior&&prior.decision!=='reject'){box.checked=true}
  });
  Array.prototype.forEach.call(document.querySelectorAll('input[name^="objective:"],input[name^="path:"],input[name^="remediation:"]'),function(input){
    input.addEventListener('change',markCustom);
  });
  var reviewer=document.getElementById('reviewer-name');
  if(reviewer&&!reviewer.value&&state.reviewer){reviewer.value=state.reviewer}
  var recommended=document.getElementById('use-recommended');
  if(recommended){recommended.addEventListener('click',function(){
    Array.prototype.forEach.call(document.querySelectorAll('input[name^="path:"]'),function(box){box.checked=true});
    if(packageChoice){packageChoice.value='recommended'}
    if(status){status.textContent='All proposed files are selected. Unticking one records a custom scope.'}
  })}
  function pageKinds(){return page==='files'?['scope-path']:['report-review','scope-objective','remediation']}
  function sourceKinds(hash){
    var kinds={};
    (state.answers||[]).forEach(function(a){if(a.sourceSha256===hash){kinds[a.kind]=true}});
    return Object.keys(kinds);
  }
  function collect(){
    var problems=[];
    var who=reviewer?reviewer.value.trim().replace(/\\s+/g,' '):'';
    if(!who){problems.push('Add your name so the file records who answered.')}
    var review=document.getElementById('reviewed-all');
    if(page==='plan'&&!(review&&review.checked)){problems.push('Confirm you have reviewed all six pages.')}
    var answers=[];
    if(page==='plan'&&review&&review.checked){answers.push({kind:'report-review',id:'all-pages',decision:'accept'})}
    (catalog.objectives||[]).forEach(function(o){
      var value=checkedValue('objective:'+o.id);
      if(value){answers.push({kind:'scope-objective',id:o.id,decision:value})}
    });
    if(page==='files'){
      (catalog.paths||[]).forEach(function(p){
        var box=document.querySelector('input[name="path:'+p.path+'"]');
        if(box&&box.checked){answers.push({kind:'scope-path',id:p.path,decision:'accept'})}
      });
    }
    Array.prototype.forEach.call(document.querySelectorAll('input[name^="remediation:"]'),function(input){
      if(input.checked){answers.push({kind:'remediation',id:input.name.slice('remediation:'.length),decision:input.value})}
    });
    return {problems:problems,answers:answers,reviewer:who};
  }
  function build(){
    var result=collect();
    if(result.problems.length){return {problems:result.problems}}
    if(page==='files'&&!result.answers.length){
      return {problems:['Tick at least one file, or save the Plan page to record the review.']}
    }
    var changed={},sources={};
    result.answers.forEach(function(a){
      var prior=inForce[a.kind+':'+a.id];
      if(prior&&prior.decision!==a.decision){
        changed[a.kind+':'+a.id]=true;
        if(prior.source){sources[prior.source]=true}
      }
    });
    var supersedes=null;
    var hashes=Object.keys(sources);
    if(Object.keys(changed).length){
      if(!hashes.length){
        return {problems:['This report does not record which answers file holds the decision being changed. Regenerate the report, then revise the answer.']}
      }
      if(hashes.length>1){
        return {problems:['These answers change decisions recorded in more than one answers file. Supersede them one file at a time, or ask the agent to combine them.']}
      }
      supersedes=hashes[0];
      var allowed=pageKinds();
      var extra=sourceKinds(supersedes).filter(function(kind){return allowed.indexOf(kind)<0});
      if(extra.length){
        return {problems:['The answers file being replaced also records choices this page does not save. Ask the agent to supersede it so those choices are kept.']}
      }
    }
    var today=new Date();
    today.setMinutes(today.getMinutes()-today.getTimezoneOffset());
    return {document:{
      schemaVersion:'1.0',kind:'acima-adoption-decisions',reportId:catalog.reportId,
      proposalSha256:catalog.proposalSha256,reportGeneratedAt:catalog.generatedAt,
      reviewer:result.reviewer,decidedOn:today.toISOString().slice(0,10),source:'html-report',
      package:(packageChoice&&packageChoice.value)||'custom',page:page,supersedes:supersedes,
      answers:result.answers
    }};
  }
  function download(name,body){
    var link=document.createElement('a');
    link.href=URL.createObjectURL(new Blob([body],{type:'application/json'}));
    link.download=name; document.body.appendChild(link); link.click(); link.remove();
  }
  function saved(name,count){
    if(status){status.textContent='Created '+name+' with '+count+' answers. Answering is not approval: the workflow prints the approval command after checking the file.'}
  }
  function save(){
    var built=build();
    if(built.problems){show('Nothing was saved. '+built.problems.join(' '),true);return}
    if(error){error.hidden=true}
    var body=JSON.stringify(built.document,null,2)+String.fromCharCode(10);
    if(text){text.value=body}
    var name='acima-decisions-'+catalog.reportId+'-'+page+'.json';
    var count=built.document.answers.length;
    if(window.showSaveFilePicker){
      window.showSaveFilePicker({suggestedName:name,types:[{description:'ACIMA decisions',accept:{'application/json':['.json']}}]})
        .then(function(handle){return handle.createWritable()})
        .then(function(writable){return writable.write(body).then(function(){return writable.close()})})
        .then(function(){saved(name,count)},function(failure){
          if(failure&&failure.name==='AbortError'){
            if(status){status.textContent='Save cancelled. Nothing was written; use Copy answers to paste them into the conversation instead.'}
            return;
          }
          download(name,body); saved(name,count);
        });
    } else {download(name,body); saved(name,count)}
  }
  var saveButton=document.getElementById('answers-save');
  if(saveButton){saveButton.addEventListener('click',save)}
  var copyButton=document.getElementById('answers-copy');
  if(copyButton){copyButton.addEventListener('click',function(){
    var built=build();
    if(built.problems){show('Nothing was copied. '+built.problems.join(' '),true);return}
    if(error){error.hidden=true}
    var body=JSON.stringify(built.document,null,2)+String.fromCharCode(10);
    if(text){text.value=body}
    function selected(){
      if(text){text.focus(); text.select()}
      if(status){status.textContent='This browser blocked the clipboard. The answers below are selected; press Ctrl+C to copy them.'}
    }
    if(navigator.clipboard&&navigator.clipboard.writeText){
      navigator.clipboard.writeText(body).then(function(){
        if(status){status.textContent='Copied. Paste it into the conversation and the agent will write the answers file.'}
      },selected);
    } else {selected()}
  })}
})();
</script>"""


def _json(value):
    import json as _json_module
    return _json_module.dumps(value, ensure_ascii=False).replace('</', '<\\/')


def console_state_json(d):
    wf=d.get('adoptionWorkflow') or {}
    console=wf.get('consoleState') or {}
    return _json({'answers':console.get('answers') or [],'reviewer':console.get('reviewer') or '',
                  'remediation':console.get('remediation') or {}})


def console_strip(d,file):
    console=d.get('console') or {}
    if not console.get('reportId'):
        return ''
    wf=d.get('adoptionWorkflow') or {}
    log=[x for x in arr(wf.get('decisionLog')) if isinstance(x,dict) and x.get('status')=='in force']
    answered=len({(x.get('kind'),x.get('id')) for x in log})
    mode=console.get('mode') or 'guided'
    answer_link=('<a href="plan.html#owner-answers">Answer this report</a>' if mode!='full' else
                 '<span>Automated adoption records answers in one consolidated review, not on this page.</span>')
    return (f'<p class="console-strip"><small>REPORT IDENTITY</small> <code>{e(console.get("reportId"))}</code> '
            f'<span aria-hidden="true">&middot;</span> version {e(int(console.get("generation") or 0) + 1)} '
            f'<span aria-hidden="true">&middot;</span> {(str(answered) + " answers in force") if answered else "No answers in force yet"} '
            f'<span aria-hidden="true">&middot;</span> <a href="plan.html#decision-log">Decision log</a> '
            f'<span aria-hidden="true">&middot;</span> {answer_link}</p>')


def answer_label(kind, identifier):
    """History names the same answer the page names: stage labels, not raw ids."""
    if kind=='scope-objective':
        return OBJECTIVE_LABELS.get(identifier,identifier)
    if kind=='report-review' and identifier=='all-pages':
        return 'All pages'
    return identifier


def stage_label(value):
    text=str(value or '').replace('_',' ').replace('-',' ').strip()
    return text[:1].upper()+text[1:] if text else text


def workflow_history(d):
    wf=d.get('adoptionWorkflow') or {}
    since=wf.get('sinceReview') or {}
    banner=''
    if since.get('status')=='changed':
        banner=f'<p class="reconciliation"><b>Changed since your review:</b> {e(", ".join(str(x) for x in arr(since.get("changed"))))}. Read the pages again before approving; your recorded review no longer describes everything here.</p>'
    elif since.get('status')=='current':
        banner=f'<p class="note">Reviewed by {e(since.get("reviewedBy") or "the owner")} on {e(since.get("reviewedOn") or "a recorded date")}; nothing that was reviewed has changed since.</p>'
    log=[x for x in arr(wf.get('progressLog')) if isinstance(x,dict)]
    timeline=table(['When','Stage','From','To','What changed'],
                   [(when_text(x.get('at')),stage_label(x.get('stage')),status_label(x.get('from')),status_label(x.get('to')),x.get('detail')) for x in log[-25:]],
                   'No stage changes are recorded yet.',caption='Stage changes',row_headers=True) if log else ''
    entries=[x for x in arr(wf.get('decisionLog')) if isinstance(x,dict)]
    current=[x for x in entries if x.get('status')=='in force']
    history=[x for x in entries if x.get('status')!='in force']
    current_table=table(['Kind','Answer','Decision','Reviewer','Date'],
                        [(KIND_LABELS.get(x.get('kind'),x.get('kind')),answer_label(x.get('kind'),x.get('id')),status_label(x.get('decision')),x.get('reviewer'),x.get('decidedOn')) for x in current],
                        'No answers recorded yet. Nothing here is approved.',caption='Current answers',row_headers=True)
    history_table=''
    if history:
        history_table=('<details><summary>Earlier answers that no longer apply ('+str(len(history))+')</summary>'
                       +table(['Kind','Answer','Decision','Status','Reason'],
                              [(KIND_LABELS.get(x.get('kind'),x.get('kind')),answer_label(x.get('kind'),x.get('id')),status_label(x.get('decision')),decision_status(x.get('status')),x.get('staleReason') or x.get('supersededBy')) for x in history],
                              'No earlier answers.',caption='Earlier answers',row_headers=True)+'</details>')
    integrity=wf.get('evidenceIntegrity') or {}
    missing=arr(integrity.get('missing'))
    if missing:
        integrity_html=('<p class="reconciliation"><b>Recorded but missing:</b> '
                        +', '.join(e(x.get('name'))+' ('+e(x.get('path'))+')' for x in missing)
                        +'. The stage that relies on it is not complete.</p>')
    elif integrity:
        integrity_html=f'<p class="note">All {e(integrity.get("checked"))} recorded evidence files exist.</p>'
    else:
        integrity_html=''
    return (f'<section id="decision-log"><small>HISTORY</small><h2>What is settled, and how it got there</h2>{banner}'
            f'<h3>Current answers</h3>{current_table}{history_table}'
            f'<h3>Stage changes</h3>{timeline}'
            f'<h3>Evidence files</h3>{integrity_html}'
            f'<p class="note">Earlier answers are shown for context only. They are not controls and do not count toward the current scope.</p></section>')


def owner_answers(d):
    console=d.get('console') or {}
    if (console.get('mode') or 'guided')=='full' or not console.get('reportId'):
        return ''
    remediation=(d.get('adoptionWorkflow') or {}).get('consoleState',{}).get('remediation') or {}
    objectives=''
    for item in arr(console.get('objectives')):
        identifier=item.get('id'); label=OBJECTIVE_LABELS.get(identifier,identifier)
        required=arr(item.get('requiredPaths'))
        needs=(f'<span class="required-note">Needs {len(required)} file{"s" if len(required)!=1 else ""} chosen on the Files page</span>' if required else '<span class="required-note">No file changes</span>')
        options=''.join(f'<label><input type="radio" name="objective:{e(identifier)}" value="{value}"> {label_text}</label>' for value,label_text in (('accept','Implement'),('defer','Defer'),('reject','Decline')))
        objectives+=f'<div class="answer-row"><div><b>{e(label)}</b> {needs}</div><div class="choices">{options}</div></div>'
    remediation_html=''
    if remediation.get('available'):
        rows=''.join(
            f'<div class="answer-row"><div><b>{e(item.get("id"))}</b> {e(item.get("title"))} <span class="required-note">Suggested fix: {e(item.get("recommendation"))}</span></div>'
            f'<div class="choices"><label><input type="radio" name="remediation:{e(item.get("id"))}" value="accept"> Fix now</label>'
            f'<label><input type="radio" name="remediation:{e(item.get("id"))}" value="defer"> Defer</label></div></div>'
            for item in arr(remediation.get('items')))
        remediation_html=(f'<fieldset><legend>Source fixes</legend><p class="note">Fix now still requires the remediation plan digest, its exact paths and its confirmations.</p>{rows}</fieldset>')
    template=('{"schemaVersion":"1.0","kind":"acima-adoption-decisions","reportId":"'+str(console.get('reportId'))+'",'
              '"reviewer":"<your name>","decidedOn":"<YYYY-MM-DD>","source":"html-report","package":"custom",'
              '"answers":[{"kind":"report-review","id":"all-pages","decision":"accept"},'
              '{"kind":"scope-objective","id":"<stage id>","decision":"accept"},'
              '{"kind":"scope-path","id":"<file path>","decision":"accept"}]}')
    return (f'<section id="owner-answers" class="answers"><small>YOUR ANSWERS</small><h2>Answer this report</h2>'
            f'<p class="note">Answering is not approval and changes nothing in the repository. These controls build one answers file; the workflow checks it and then prints the approval command.</p>'
            f'<div id="answers-error" class="answers-error" role="alert" tabindex="-1" hidden></div>'
            f'<label class="field">Your name <input id="reviewer-name" name="reviewer" autocomplete="off" maxlength="120" required></label>'
            f'<fieldset><legend>Report review</legend><label><input type="checkbox" id="reviewed-all"> I reviewed all six pages of this report</label></fieldset>'
            f'<fieldset><legend>Which stages may be implemented?</legend><p class="note">Leave every stage unanswered to record the review without choosing work.</p>{objectives}</fieldset>'
            f'{remediation_html}'
            f'<input type="hidden" id="answers-package" value="custom">'
            f'<div class="actions"><button type="button" class="button" id="answers-save">Save answers file</button>'
            f'<button type="button" class="button secondary" id="answers-copy">Copy answers</button></div>'
            f'<label class="field">Answers to paste back <textarea id="answers-text" rows="8" readonly placeholder="Save or copy builds the answers file here."></textarea></label>'
            f'<p id="answers-status" class="note" aria-live="polite"></p>'
            f'<noscript><p class="note">JavaScript is off, so Save and Copy cannot build the file. Copy this template into the conversation, fill in your decisions, and the agent will write the answers file.</p><pre class="template">{e(template)}</pre></noscript>'
            f'<script type="application/json" id="acima-console" data-page="plan">{_json(console)}</script>'
            f'<script type="application/json" id="acima-console-state">{console_state_json(d)}</script>'
            f'{CONSOLE_JS}</section>')


def scope_paths(d):
    console=d.get('console') or {}
    if (console.get('mode') or 'guided')=='full' or not console.get('reportId'):
        return ''
    paths=arr(console.get('paths'))
    if not paths:
        return ''
    def path_row(item):
        required=arr(item.get("requiredBy"))
        # One statement per row: the note names the stage that needs this file.
        needed=(f'<span class="required-note">Needed for {e(", ".join(OBJECTIVE_LABELS.get(x,x) for x in required))}</span>'
                if required else '')
        return (f'<div class="answer-row"><label><input type="checkbox" name="path:{e(item.get("path"))}"> '
                f'<code>{e(item.get("path"))}</code></label>{needed}</div>')
    rows=''.join(path_row(item) for item in paths)
    files_template=('{"schemaVersion":"1.0","kind":"acima-adoption-decisions","reportId":"'+str(console.get('reportId'))+'",'
                    '"reviewer":"<your name>","decidedOn":"<YYYY-MM-DD>","source":"html-report","package":"custom",'
                    '"page":"files","answers":[{"kind":"scope-path","id":"<file path>","decision":"accept"}]}')
    return (f'<section id="scope-paths" class="answers"><small>YOUR SCOPE</small><h2>Choose the files this adoption may change</h2>'
            f'<p class="note">A file is selected only when you tick it. Leaving a required file unticked defers its stage rather than producing an incomplete approval.</p>'
            f'<div class="actions"><button type="button" class="button secondary" id="use-recommended">Select all proposed files</button></div>'
            f'<fieldset><legend class="visually-hidden">Proposed files</legend>{rows}</fieldset>'
            f'<label class="field">Your name <input id="reviewer-name" name="reviewer" autocomplete="off" maxlength="120"></label>'
            f'<div id="answers-error" class="answers-error" role="alert" tabindex="-1" hidden></div>'
            f'<input type="hidden" id="answers-package" value="custom">'
            f'<div class="actions"><button type="button" class="button" id="answers-save">Save answers file</button>'
            f'<button type="button" class="button secondary" id="answers-copy">Copy answers</button></div>'
            f'<label class="field">Answers to paste back <textarea id="answers-text" rows="8" readonly placeholder="Save or copy builds the answers file here."></textarea></label>'
            f'<p id="answers-status" class="note" aria-live="polite"></p>'
            f'<p class="note">The review answer lives on the Plan page. Save that page too, or let the workflow merge both files.</p>'
            f'<noscript><p class="note">JavaScript is off, so Save and Copy cannot build the file. Copy this template into the conversation, list every file you want in it, and the agent will write the answers file.</p>'
            f'<pre class="template">{e(files_template)}</pre></noscript>'
            f'<script type="application/json" id="acima-console" data-page="files">{_json(console)}</script>'
            f'<script type="application/json" id="acima-console-state">{console_state_json(d)}</script>'
            f'{CONSOLE_JS}</section>')


def validate_console(d):
    p=[]
    console=d.get('console')
    if console is None:
        return p
    if not isinstance(console,dict):
        return ['console must be an object when supplied.']
    if not console:
        return p
    if not re.fullmatch(r'[a-f0-9]{20}',str(console.get('reportId') or '')):
        p.append('console.reportId must be a 20-hex report identity.')
    if console.get('mode') not in ('guided','full'):
        p.append('console.mode must be guided or full.')
    seen=set()
    for item in arr(console.get('objectives')):
        identifier=item.get('id') if isinstance(item,dict) else None
        if not identifier or identifier in seen:
            p.append('console.objectives must list unique objective ids.')
            continue
        seen.add(identifier)
        for item_path in arr(item.get('requiredPaths')):
            if (not isinstance(item_path,str) or not item_path or Path(item_path).is_absolute()
                    or '..' in Path(item_path).parts):
                p.append('console required paths must be repository-relative: %s' % item_path)
    known={x.get('path') for x in arr(console.get('paths')) if isinstance(x,dict)}
    for item in arr(console.get('objectives')):
        for item_path in arr(item.get('requiredPaths')) if isinstance(item,dict) else []:
            if item_path not in known:
                p.append('console path %s is required but not listed as selectable.' % item_path)
    for item in arr(console.get('paths')):
        if not isinstance(item,dict) or not isinstance(item.get('path'),str):
            p.append('console.paths entries need a repository-relative path.')
            continue
        if Path(item['path']).is_absolute() or '..' in Path(item['path']).parts:
            p.append('console path %s must not escape the repository.' % item['path'])
    return p


def shell(data,file,title,subtitle,body):
    repo=e((data.get('repository') or {}).get('name') or 'Repository assessment'); active=''.join(f'<a href="{href}" class="{"active" if href==file else ""}"'+(' aria-current="page"' if href==file else '')+f'>{label}</a>' for href,label in NAV)
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light"><meta name="description" content="Plain-language ACIMA assessment for {repo}"><title>{e(title)} &middot; {repo} &middot; ACIMA</title><link rel="stylesheet" href="assets/report.css"></head><body><a class="skip" href="#main">Skip to report content</a><header><a class="brand" href="index.html" aria-label="ACIMA Architecture Outcome Report"><b aria-hidden="true">A</b><span>ACIMA<small>ARCHITECTURE OUTCOME REPORT</small></span></a><div class="meta"><span>{repo}</span><span>{time_tag(data.get('generatedAt'))}</span></div></header><div class="layout"><aside aria-label="Report navigation"><small>REPORT SECTIONS</small><nav aria-label="Report sections">{active}</nav><p class="rail-note">A practical guide to what ACIMA found, what it proposes, and what the proposed work would deliver.</p></aside><main id="main" tabindex="-1" aria-labelledby="page-title"><div class="page-head"><small>{repo} / {e(PAGES[file])}</small><h1 id="page-title">{e(title)}</h1><p>{e(subtitle)}</p></div>{console_strip(data,file)}{body}<footer>ACIMA &middot; Architecture that enforces itself. <span>Generated from the accompanying evidence model.</span></footer></main></div></body></html>'''
def render(d):
    repo=d.get('repository') or {}; rec=d.get('recommendation') or {}; ov=d.get('overview') or {}; val=d.get('value') or {}; arch=d.get('architecture') or {}; cov=d.get('coverage') or {}; gate=d.get('ownershipGate') or {}
    strengths=arr(d.get('strengths')); findings=arr(d.get('findings')); changes=arr(d.get('proposedChanges')); outcomes=arr(d.get('outcomes')); phases=arr((d.get('roadmap') or {}).get('phases')) or arr(d.get('phases')); decisions=arr(d.get('decisions')); evidence=arr(d.get('evidence')); limits=arr(d.get('limitations'))
    conformance=arr(d.get('conformance'))
    exceptions=[x for x in conformance if isinstance(x,dict) and key(x.get('disposition')) not in ('conforms','not_applicable')]
    conformance_by_rule={x.get('rule'):x for x in conformance if isinstance(x,dict) and x.get('rule')}
    benefits=''.join(f'<article><small>{i+1:02}</small><h3>{e(x.get("title") or "Outcome")}</h3><p>{e(x.get("description") or x.get("benefit"))}</p><em>{e(x.get("availability") or "Proposed benefit; not yet verified")}</em></article>' for i,x in enumerate(arr(val.get('benefits')))) or '<p class="empty">No repository-specific benefits are recorded.</p>'
    finding_cards=''.join(f'<article class="finding"><div class="row"><h3>{e(x.get("title") or "Finding")}</h3>{pill(x.get("disposition") or x.get("status") or x.get("confidence"))}</div><p>{e(x.get("what") or x.get("summary"))}</p><p><b>What it could cost:</b> {e(x.get("why"))}</p><p><b>What fixing it involves:</b> {e(x.get("recommendation") or x.get("fix"))}</p><p><b>Required or optional:</b> {e(status_label(x.get("classification")))}</p><details><summary>Where this came from</summary><p><b>Internal reference:</b> {e(", ".join(finding_rules(x)) or "Not recorded")}</p><p><b>What this check means:</b> {e(x.get("requirementMeaning"))}</p><p><b>Files and evidence:</b> {e(x.get("paths") or x.get("path"))} &middot; {e(x.get("evidenceRefs"))}</p><p><b>What good looks like:</b> {e(x.get("expectedOutcome"))}</p><p><b>How to know it worked:</b> {e(x.get("verification"))}</p><p><b>How sure we are and what is still unknown:</b> {e(status_label(x.get("confidence")))} &middot; {e(x.get("limitations"))}</p></details></article>' for x in findings) or '<p class="empty">No problems were recorded. Check the evidence page to confirm that the review was complete before treating this as a clean result.</p>'
    outcome_cards=''.join(f'<article class="row"><div><h3>{e(x.get("title") or "Outcome")}</h3><p>{e(x.get("description"))}</p><p><b>Why it matters:</b> {e(x.get("whyItMatters"))}</p><p><b>Practical change:</b> {e(x.get("practicalChange"))}</p><p><b>Type:</b> {e(status_label(x.get("classification")))} &middot; <b>Basis:</b> {e(status_label(x.get("realization")))}</p><p><b>Verification:</b> {e(x.get("verification"))}</p><em>{e(x.get("limitations"))}</em></div>{pill(x.get("status") or x.get("availability"))}</article>' for x in outcomes) or f'<p class="empty">{e(d.get("outcomesStatus") or "Outcomes have not yet been established. No benefits are inferred.")}</p>'
    phase_cards=''.join(f'<article class="phase"><div class="row"><h3>{e(x.get("name") or "Phase")}</h3>{pill(x.get("status"))}</div><p>{e(x.get("purpose"))}</p><p><b>Before this phase:</b> {e(x.get("prerequisites") or x.get("dependsOn"))}</p><p><b>What it produces:</b> {e(x.get("deliverable"))}</p><p><b>How to verify:</b> {e(x.get("verification"))}</p><p><b>Done when:</b> {e(x.get("completionCriteria"))}</p><p><b>Who approves:</b> {e(x.get("approval"))}</p><details><summary>Work and affected areas</summary>{bullets(x.get("activities",[]),"No activities recorded.")}{bullets(x.get("affectedFiles",[]),"Affected files not recorded.")}</details></article>' for x in phases) or f'<p class="empty">{e(d.get("roadmapStatus") or "An adoption plan has not been established yet.")}</p>'
    linked_findings=sum(1 for x in findings if any(r in conformance_by_rule for r in finding_rules(x)))
    unlinked_findings=len(findings)-linked_findings
    if conformance:
        problem_word='problem' if len(findings)==1 else 'problems'
        check_word='check' if len(exceptions)==1 else 'checks'
        reconciliation_sentence=f'{len(findings)} {problem_word} and {len(exceptions)} {check_word} needing attention are recorded.'
        if linked_findings:
            verb='names' if linked_findings==1 else 'name'
            reconciliation_sentence += f' {linked_findings} {problem_word} {verb} a matching check result.'
        if unlinked_findings:
            verb='does' if unlinked_findings==1 else 'do'
            reconciliation_sentence += f' {unlinked_findings} {problem_word} {verb} not name a matching result; they remain grouped problems.'
    else:
        reconciliation_sentence='Check results were not supplied, so problems cannot be compared with them.'
    pages={}
    pages['index.html']=f'''<section class="decision"><div><small>RECOMMENDATION</small><h2>{e(recommendation(rec.get('status')))}</h2><p>{e(rec.get('summary') or ov.get('summary'))}</p></div>{pill(d.get('assessmentStatus'), assessment(d.get('assessmentStatus')))}</section><section><small>THE SHORT VERSION</small><h2>What this means for your product</h2><p class="lead">{e(ov.get('plainLanguage'))}</p></section><div class="metrics compact">{metric('PROBLEMS FOUND',len(findings) or 'None recorded')}{metric('CHECKS REVIEWED',coverage_ratio(cov),unresolved_note(cov))}</div><p class="context-line"><b>Repository:</b> {e(repo_mode(repo.get('mode')))} <span aria-hidden="true">&middot;</span> <b>Workflow:</b> {e(status_label((d.get('adoptionWorkflow') or {}).get('mode') or 'not recorded'))} <span aria-hidden="true">&middot;</span> <b>Structure:</b> {e(arch.get('family') or 'Not established')}</p>{module_map_overview(d)}<p class="cross-links"><span>Related:</span> <a href="findings.html#findings">Findings</a> <a href="plan.html#adoption-plan">Plan</a> <a href="evidence.html#evidence-summary">Evidence summary</a></p><section id="completion"><h2>What has been completed?</h2>{table(['Milestone','Status'],[('Assessment', milestone((d.get('milestones') or {}).get('assessmentComplete'))),('Report generation', 'Completed when this report was written'),('Change proposal',milestone((d.get('milestones') or {}).get('adoptionProposalComplete'))),('Implementation',milestone((d.get('milestones') or {}).get('implementationComplete'))),('Final verification',milestone((d.get('milestones') or {}).get('conformanceVerified')))],caption='Completion status by milestone',row_headers=True)}<p class="note">Writing this report does not complete the assessment, approve the proposal, implement changes or verify conformance.</p></section><section><small>WHAT GETS BETTER</small><h2>What this work would make possible</h2><div class="benefits">{benefits}</div></section><section><small>THE DECISION</small><h2>Why this recommendation?</h2><div class="cols"><div><h3>Why it fits this repository</h3>{bullets(arr(rec.get('reasons')))}</div><div><h3>Tradeoffs and caveats</h3>{bullets(arr(rec.get('caveats')))}</div></div></section><section class="next"><div><small>NEXT STEP</small><h2>{e(ov.get('nextAction') or 'Review the proposal')}</h2><p>{e(ov.get('nextActionWhy'))}</p></div><a href="proposal.html">See what would change <span aria-hidden="true">&rarr;</span></a></section>'''
    existing_arch=arch.get('existingArchitecture') or (d.get('moduleMap') or {}).get('existingArchitecture') or {}
    existing_enforcement=arch.get('existingEnforcement') or {}
    existing_asset_rows=[(path,'Existing repository architecture evidence; inspect and preserve unless a specific approved change is justified.') for path in arr(existing_arch.get('paths'))]
    existing_asset_rows += [(path,'Existing solution or project manifest; do not assume this is itself an ACIMA module.') for path in arr(existing_arch.get('solutions')) + arr(existing_arch.get('dotnetProjects'))]
    mechanism_rows=[]
    for item in arr(existing_enforcement.get('mechanisms')):
        if isinstance(item,dict):
            mechanism_rows.append((item.get('name') or item.get('kind') or item.get('path'),item.get('path'),item.get('status') or item.get('purpose')))
        else:
            mechanism_rows.append((str(item),'','Identified by read-only repository assessment.'))
    existing_section=f'<section id="existing-architecture"><small>WHAT TO KEEP</small><h2>What already works and should stay</h2><p class="lead">{e(existing_enforcement.get("summary") or existing_arch.get("note") or "The assessment did not establish existing architecture assets beyond the evidence listed below.")}</p>{table(["Existing asset","Assessment"],existing_asset_rows,"No existing architecture file paths were identified.",caption="Existing architecture and enforcement assets")}{table(["Existing enforcement","Path","Observed purpose or status"],mechanism_rows,"No existing executable enforcement mechanism was established by the assessment.",caption="Existing enforcement mechanisms")}</section>'
    pages['proposal.html']=f'''{adoption_path(d)}<section><small>TODAY</small><h2>How the repository works today</h2><p class="lead">{e(arch.get('currentState'))}</p><p class="cross-links"><span>Related:</span> <a href="findings.html#findings">Findings</a> <a href="files.html#file-changes">Proposed file changes</a> <a href="plan.html#adoption-plan">Plan</a></p><div class="cols"><div><h3>Already working</h3>{bullets(strengths)}</div><div><h3>What would be added</h3>{bullets(arr(val.get('adds')))}</div></div></section>{existing_section}<section><small>WHAT WOULD CHANGE</small><h2>What would change</h2><p>{e(arch.get('proposedState'))}</p>{table(['Capability','What changes','What it makes possible'],[(x.get('capability'),x.get('change'),x.get('outcome')) for x in arr(arch.get('targetCapabilities'))],caption='Proposed capabilities',row_headers=True)}</section>{d016_allowlist_section(d)}{plain_language_gaps_section(d)}{module_map_sections(d)}<section><small>WHAT GETS BETTER</small><h2>What should become easier or safer</h2><div class="stack">{outcome_cards}</div></section><section><small>TRADEOFFS</small><h2>Costs, risks, and limits</h2><div class="cols"><div><h3>Cost and effort</h3>{bullets(arr(val.get('costs')))}</div><div><h3>Risks and mitigations</h3>{bullets(arr(val.get('risks')))}</div></div><h3>What this work will not do</h3>{bullets(limits)}</section>'''
    pages['findings.html']=f'''<section id="strengths"><small>WHAT IS ALREADY WORKING</small><h2>What is already in good shape</h2>{bullets(strengths,'No strengths were recorded. This does not mean none exist.')}</section><section id="findings"><small>PROBLEMS FOUND</small><h2>What needs attention</h2><p class="lead">These are the problems found, what each one could cost you, and what fixing it would involve. Technical references stay in the details at the bottom of each card.</p><p class="reconciliation"><b>Problems and checks are counted separately.</b> {e(reconciliation_sentence)} <a href="evidence.html#exceptions">See which checks need attention</a>.</p><p class="note">Each problem shows the check behind it. The report does not claim that checks with similar wording describe the same underlying issue.</p><p class="cross-links"><span>Related:</span> <a href="files.html#file-changes">Proposed file changes</a> <a href="plan.html#adoption-plan">Plan</a> <a href="evidence.html#exceptions">Checks that need attention</a></p>{finding_cards}</section>'''
    inventory=d.get('fileImpact') or {}
    categorized=[]
    for action in ('inspect','create','modify','preserve'):
        source=arr(inventory.get(action)) or [x for x in changes if x.get('action')==action]
        categorized.extend((x.get('path'),action,x.get('purpose'),x.get('expectedOutcome'),status_label(x.get('classification')),x.get('confidence')) for x in source)
    file_rows=[(path,action_label(act),purpose,outcome,commitment,status_label(confidence)) for path,act,purpose,outcome,commitment,confidence in categorized]
    pages['files.html']=f'''<section id="file-changes"><h2>Proposed file changes</h2><p class="lead">Some files are listed only so they can be inspected; that is not a proposed edit. Creating or changing a file remains a proposal until someone approves it.</p><p class="cross-links"><span>Related:</span> <a href="findings.html#findings">Findings</a> <a href="plan.html#adoption-plan">Plan</a> <a href="evidence.html#exceptions">Checks needing attention</a>{' <a href="proposal.html#d016-allowlist">Configuration decision for the partial-application check</a>' if d.get('d016Allowlist') else ''}</p>{table(['File or area','Action','Why it is involved','What it should achieve','Must do or optional','How sure'],file_rows,d.get('fileImpactStatus') or 'No proposed file changes were supplied.',caption='Proposed file changes',row_headers=True)}</section><section><h2>What should stay the same</h2>{bullets(arr(d.get('preservation')),d.get('preservationStatus') or 'What should stay the same has not yet been established.')}</section><div class="metrics">{metric('FILES TO CREATE',sum(x[1]=='create' for x in categorized))}{metric('FILES TO MODIFY',sum(x[1]=='modify' for x in categorized))}{metric('FILES TO INSPECT',sum(x[1]=='inspect' for x in categorized))}{metric('FILES TO PRESERVE',sum(x[1]=='preserve' for x in categorized))}</div>{scope_paths(d)}'''
    decision_html=''.join(f'<article class="decision-row"><h3>{e(x.get("question"))}</h3><p>{e(x.get("context"))}</p><p><b>Recommendation:</b> {e(x.get("recommendation"))}</p><p><b>Effort:</b> {e(x.get("effort"))}</p><p><b>If left open:</b> {e(x.get("consequence"))}</p><p><b>What this blocks:</b> {e(x.get("blockedWork"))}</p><p><b>Needed before implementation:</b> {"Yes" if x.get("requiredBeforeImplementation") else "No"}</p><details><summary>Evidence gap and other options</summary><p><b>Evidence gap:</b> {e(x.get("evidenceGap"))}</p>{bullets(x.get("alternatives",[]),"Alternatives are not established.")}<p><b>Impact:</b> {e(x.get("impact"))}</p><p><b>Why an owner is needed:</b> {e(x.get("whyOwner"))}</p></details></article>' for x in decisions) or f'<p class="empty">{e(d.get("decisionsStatus") or "No owner decisions are recorded. The assessment has not established whether no decision is needed or discovery is incomplete.")}</p>'
    pages['plan.html']=f'''{adoption_workflow(d)}{agent_guidance_section(d)}{remediation_outcome(d)}<section id="adoption-plan"><h2>Plan</h2><p class="cross-links"><span>Related:</span> <a href="findings.html#findings">Findings</a> <a href="files.html#file-changes">Proposed file changes</a> <a href="evidence.html#exceptions">Checks needing attention</a></p><div class="stack">{phase_cards or e(d.get("roadmapStatus") or "An adoption plan has not been established yet.")}</div></section><section id="decisions"><h2>Decisions only you can make</h2>{decision_html}</section>{owner_answers(d)}<section><h2>What approval would mean</h2><p>{e(d.get('approvalStatement') or 'Reading this report does not authorize implementation. Approval must identify the specific proposed scope.')}</p></section>{workflow_history(d)}'''
    evrows=[(x.get('label') or x.get('kind'),x.get('source'),x.get('whatItSupports'),status_label(x.get('status'))) for x in evidence]
    reviewed=coverage_ratio(cov)
    unresolved='Not recorded' if cov.get('unresolvedRules') in (None,'') else str(cov.get('unresolvedRules'))
    exception_count=len(exceptions) if conformance else 'Not recorded'
    if conformance:
        if exceptions:
            noun='check' if len(exceptions)==1 else 'checks'
            verb='needs' if len(exceptions)==1 else 'need'
            exception_sentence=f'{len(exceptions)} {noun} {verb} attention.'
        else:
            exception_sentence='No check needs attention in the results supplied.'
    else:
        exception_sentence='Check results were not supplied, so this page does not claim a pass.'
    summary_sentence=f'The review covered {reviewed} checks. {exception_sentence}'
    coverage_table=table(['What was checked','Result'],[('Checks in the catalog',cov.get('requiredRules')),('Reviewed with evidence',cov.get('reviewedRules')),('Not yet reviewed',cov.get('pendingRules')),('Still unresolved',cov.get('unresolvedRules')),('Automated checks run',cov.get('automatedChecksRun')),('Manual reviews completed',cov.get('manualReviewsCompleted')),('Skipped because unsupported',cov.get('skippedOrUnsupported')),('Meets the check',(cov.get('dispositionCounts') or {}).get('conforms')),('Does not meet the check',(cov.get('dispositionCounts') or {}).get('doesNotConform')),('Partly meets the check',(cov.get('dispositionCounts') or {}).get('partiallyConforms')),('Not applicable',(cov.get('dispositionCounts') or {}).get('notApplicable')),('Not enough evidence',(cov.get('dispositionCounts') or {}).get('unverified')),('Not yet assessed',(cov.get('dispositionCounts') or {}).get('notAssessed')),('Not supported by current tools',(cov.get('dispositionCounts') or {}).get('unsupported')),('Blocked by another issue',(cov.get('dispositionCounts') or {}).get('blocked'))],caption='Check review coverage',row_headers=True)
    conformance_table=table(['Check','Result','Explanation','Evidence'],[(x.get('requirement') or x.get('title'),status_label(x.get('disposition')),x.get('meaning') or x.get('rationale'),refs(x.get('evidenceRefs'))) if isinstance(x,dict) else (x,'Not established','No explanation supplied.','No evidence supplied.') for x in conformance],'No check results were supplied.',caption='All check results',row_headers=True)
    exception_table=table(['Check','Result','Explanation','Evidence'],[(x.get('requirement') or x.get('title'),status_label(x.get('disposition')),x.get('meaning') or x.get('rationale'),refs(x.get('evidenceRefs'))) for x in exceptions],'No check needs attention in the results supplied.',caption='Checks needing attention',row_headers=True)
    evidence_table=table(['Evidence','Source','What it supports','Status'],evrows,caption='Evidence sources',row_headers=True)
    provenance_table=table(['Field','Value'],[('Repository',repo.get('path')),('Commit',repo.get('commit') or 'Not available'),('Branch',repo.get('branch') or 'Not available'),('Working-tree digest',repo.get('workingTreeDigest') or 'Not available'),('Adoption workflow',((d.get('adoptionWorkflow') or {}).get('mode') or 'Not recorded')),('Report generated',human_date(d.get('generatedAt'))),('ACIMA standard version',d.get('standardVersion')),('Adoption skill version',d.get('skillVersion')),('Rule catalog fingerprint',d.get('catalogSha256')),('Assessment status',assessment(d.get('assessmentStatus')))],caption='Report provenance',row_headers=True)
    result_label=f'All check results ({len(conformance)})' if conformance else 'Check results'
    exception_panel=exception_table if exceptions else f'<p class="empty">{e(exception_sentence)}</p>'
    ownership_rules=arr(gate.get('ownershipDependentRules'))
    ownership_sentence=(gate.get('reason') or ('Checks that need a clear owner can run against the written map.' if gate.get('status')=='ready' else 'Checks that need a clear owner are blocked until the map is agreed.'))
    blocked_table=table(['Check','Status','Why it needs an agreed map'],[(rule,'Blocked' if gate.get('status')!='ready' else 'Ready',ownership_sentence) for rule in ownership_rules],'No check that needs an agreed map was listed in this report. Do not treat that as proof that no check depends on the map.',caption='Checks that need an agreed map',row_headers=True) if ownership_rules else '<p class="empty">No list of checks needing an agreed map was supplied. Confirm the assessment did not silently omit them.</p>'
    pages['evidence.html']=f'''<section id="evidence-summary"><small>EVIDENCE SUMMARY</small><h2>What the evidence shows</h2><p class="lead">{e(summary_sentence)}</p><ul class="summary-facts"><li><b>{e(reviewed)}</b><span>checks reviewed</span></li><li><b>{e(unresolved)}</b><span>still unresolved</span></li><li><b>{e(exception_count)}</b><span>checks needing attention</span></li></ul><p class="note">Coverage is not a passing score. Automated checks, the evidence-backed review and the final results are counted separately.</p><p class="cross-links"><span>Related:</span> <a href="findings.html#findings">Findings</a> <a href="files.html#file-changes">Proposed file changes</a> <a href="plan.html#adoption-plan">Plan</a></p></section><section id="exceptions"><small>CHECKS NEEDING ATTENTION</small><h2>What needs attention</h2>{exception_panel}</section><section id="limits"><small>WHAT WE COULDN'T ESTABLISH</small><h2>What could not be established</h2>{bullets(limits,'No limitations supplied. Confirm the assessment explicitly considered coverage and tooling limits.')}</section><section id="ownership-blocked"><small>CHECKS THAT NEED AN AGREED MAP</small><h2>Which checks need an agreed map</h2><p class="lead">{e(ownership_sentence)}</p>{blocked_table}<p class="note">The rest of the review can continue. A missing or unapproved map does not make the whole architecture unassessed.</p></section><section id="detailed-evidence"><small>DETAILS</small><h2>Evidence details</h2><p class="lead">Open a section to see what was checked, every result, the sources behind it and how this report was made.</p><details><summary>Review coverage: {e(reviewed)}</summary>{coverage_table}</details><details><summary>{e(result_label)}</summary>{conformance_table}</details><details><summary>Supporting evidence ({len(evidence)})</summary>{evidence_table}</details><details><summary>How this report was made</summary>{provenance_table}</details></section>'''
    titles={'index.html':('Overview','The decision at a glance'), 'proposal.html':('What would change','The proposed architecture and what it would deliver'),'findings.html':('What we found','What is working and what needs attention'),'files.html':('Files and impact','Exactly what is proposed to change'),'plan.html':('Plan and decisions','What happens, in what order, and who decides'),'evidence.html':('Evidence and limits','What was checked and what the results prove')}
    return {f:shell(d,f,*titles[f],body) for f,body in pages.items()}
def validate_progress(d):
    """Validate only the progress section that an automatic refresh may replace."""
    p=[]
    workflow=d.get('adoptionWorkflow')
    if workflow is None:
        return p
    if not isinstance(workflow,dict) or workflow.get('mode') not in ('guided','full'):
        return ['adoptionWorkflow.mode must be guided or full.']
    if workflow.get('phase') is not None and not isinstance(workflow.get('phase'),str):
        p.append('adoptionWorkflow.phase must be a string or null.')
    if not isinstance(workflow.get('phaseOrder',[]),list):
        p.append('adoptionWorkflow.phaseOrder must be an array.')
    if d.get('schemaVersion') in ('1.2','1.3'):
        if d.get('progressSections') != ['adoptionWorkflow','milestones']:
            p.append('progressSections must declare exactly adoptionWorkflow and milestones for schema 1.2.')
        if not str(workflow.get('asOf') or '').strip():
            p.append('adoptionWorkflow.asOf is required by report schema 1.2.')
    for i,stage in enumerate(arr(workflow.get('stages'))):
        if not isinstance(stage,dict) or not stage.get('name') or not stage.get('status'):
            p.append(f'adoptionWorkflow.stages[{i}] needs name and status.')
    current=workflow.get('currentStage')
    if current is not None and (not isinstance(current,dict) or not current.get('name')):
        p.append('adoptionWorkflow.currentStage must be a stage record or null.')
    if not isinstance(workflow.get('next',{}),dict):
        p.append('adoptionWorkflow.next must be an object.')
    return p

def validate(d):
    p=[]
    if not isinstance(d,dict):return ['Report model must be a JSON object.']
    p.extend(validate_console(d))
    if d.get('schemaVersion') not in ('1.0','1.1','1.2','1.3'):p.append("schemaVersion must be '1.0', '1.1', '1.2' or '1.3'.")
    if not isinstance(d.get('repository'),dict) or not d['repository'].get('name'):p.append('repository.name is required.')
    if not d.get('generatedAt'):p.append('generatedAt is required.')
    if not isinstance(d.get('recommendation'),dict) or not d['recommendation'].get('status') or not d['recommendation'].get('summary'):p.append('recommendation.status and recommendation.summary are required.')
    elif d['recommendation']['status'] not in ('RECOMMENDED','RECOMMENDED_WITH_LIMITATIONS','NOT_RECOMMENDED','INSUFFICIENT_EVIDENCE','NOT_SUPPORTED'):p.append('recommendation.status is not a supported value.')
    if isinstance(d.get('repository'),dict) and d['repository'].get('mode') not in (None,'greenfield','brownfield','mixed','unknown'):p.append('repository.mode must be greenfield, brownfield, mixed, or unknown.')
    for k in ('findings','strengths','proposedChanges','outcomes','phases','decisions','evidence','limitations','outOfScope'):
        if k in d and not isinstance(d[k],list):p.append(f'{k} must be an array.')
    for i,x in enumerate(arr(d.get('findings'))):
        if not isinstance(x,dict) or not x.get('title') or not x.get('what') or not x.get('why'):p.append(f'findings[{i}] needs title, what and why.')
        if isinstance(x,dict) and x.get('rule') and not re.match(r'^ACIMA-[A-Z][0-9]{3}$',str(x.get('rule'))): p.append(f'findings[{i}].rule must be a catalog rule ID.')
        if isinstance(x,dict):
            for j,ref in enumerate(arr(x.get('requirementRefs'))):
                if not re.match(r'^ACIMA-[A-Z][0-9]{3}$',str(ref)): p.append(f'findings[{i}].requirementRefs[{j}] must be a catalog rule ID.')
            if d.get('schemaVersion')=='1.1':
                refs=finding_rules(x)
                if not refs: p.append(f'findings[{i}] must name at least one catalog rule in schema 1.1.')
                unknown=[ref for ref in refs if ref not in EXPECTED_RULES]
                if unknown: p.append(f'findings[{i}] references unknown catalog rule(s): '+', '.join(sorted(set(unknown)))+'.')
    for i,x in enumerate(arr(d.get('proposedChanges'))):
        if not isinstance(x,dict) or not x.get('path') or x.get('action') not in ('create','modify','delete','inspect','no-change') or not x.get('purpose') or not x.get('expectedOutcome'):p.append(f'proposedChanges[{i}] needs path, supported action, purpose and expectedOutcome.')
    allow=d.get('d016Allowlist')
    if allow is not None:
        if not isinstance(allow,dict):p.append('d016Allowlist must be an object when supplied.')
        else:
            if allow.get('rule')!='ACIMA-D016':p.append('d016Allowlist.rule must be ACIMA-D016.')
            for field in ('configPath','currentExecution','reason'):
                if not isinstance(allow.get(field),str) or not allow.get(field).strip():p.append(f'd016Allowlist.{field} is required.')
            if not isinstance(allow.get('proposedValue'),list) or any(not isinstance(item,str) for item in allow.get('proposedValue') or []):p.append('d016Allowlist.proposedValue must be an array of strings.')
            for i,item in enumerate(arr(allow.get('candidates'))):
                if not isinstance(item,dict) or not item.get('name'):p.append(f'd016Allowlist.candidates[{i}] needs a name.')
    mm=d.get('moduleMap')
    if mm is not None:
        if not isinstance(mm,dict): p.append('moduleMap must be an object when supplied.')
        else:
            authority=mm.get('authoritativeMap')
            if not isinstance(authority,dict) or not authority.get('status'): p.append('moduleMap.authoritativeMap.status is required.')
            units=arr(mm.get('authoritativeUnits') or authority.get('units'))
            declared_count=authority.get('unitCount')
            if declared_count is not None and declared_count != len(units):
                p.append('moduleMap authoritative unit count does not match the unit records supplied to the report.')
            for i,unit in enumerate(units):
                if not isinstance(unit,dict) or not unit.get('id') or not unit.get('module') or not unit.get('role') or not isinstance(unit.get('paths'),list):
                    p.append(f'moduleMap.authoritativeUnits[{i}] needs id, module, role and paths.')
            proposal=mm.get('proposal')
            if proposal is not None:
                if not isinstance(proposal,dict): p.append('moduleMap.proposal must be an object or null.')
                else:
                    modules=arr(proposal.get('modules'))
                    for i,module in enumerate(modules):
                        if not isinstance(module,dict) or not module.get('id') or not module.get('name') or not module.get('responsibility') or not module.get('ownership') or not module.get('status'): p.append(f'moduleMap.proposal.modules[{i}] needs id, name, responsibility, ownership and status.')
                        elif not arr(module.get('evidence')): p.append(f'moduleMap.proposal.modules[{i}] needs at least one evidence reference.')
                        else:
                            for j,item in enumerate(arr(module.get('evidence'))):
                                if not isinstance(item,dict) or not item.get('path') or not item.get('observation'): p.append(f'moduleMap.proposal.modules[{i}].evidence[{j}] needs path and observation.')
                    for i,item in enumerate(arr(proposal.get('recommendations'))):
                        required=('id','title','observed','whyItMatters','recommendation','benefit','risk','uncertainty','classification','requiresUserInput')
                        if not isinstance(item,dict) or not all(item.get(key) not in (None,'') for key in required): p.append(f'moduleMap.proposal.recommendations[{i}] needs observation, rationale, benefit, risk, uncertainty and owner-input fields.')
                    for i,item in enumerate(arr(proposal.get('decisions'))):
                        if not isinstance(item,dict) or not item.get('question') or not item.get('recommendation') or item.get('status') not in ('pending','accept','reject','defer'): p.append(f'moduleMap.proposal.decisions[{i}] needs question, recommendation and a pending/accepted/rejected/deferred status.')
                    if proposal.get('status') == 'approved' and not mm.get('review'): p.append('An approved module map requires recorded review provenance.')
            review=mm.get('review')
            if review is not None and (not isinstance(review,dict) or review.get('status') not in ('approved','partially_approved','rejected','deferred','pending')): p.append('moduleMap.review.status must be approved, partially_approved, rejected, deferred or pending.')
    p.extend(validate_progress(d))
    gate=d.get('ownershipGate')
    if gate is not None:
        if not isinstance(gate,dict) or gate.get('status') not in ('ready','blocked'): p.append('ownershipGate.status must be ready or blocked.')
        elif gate.get('status') == 'blocked' and gate.get('deterministicChecksBlocked') is not True: p.append('A blocked ownership gate must mark deterministicChecksBlocked true.')
        for i,rule in enumerate(arr(gate.get('ownershipDependentRules'))):
            if not re.match(r'^ACIMA-[A-Z][0-9]{3}$',str(rule)): p.append(f'ownershipGate.ownershipDependentRules[{i}] must be a catalog rule ID.')
    if d.get('schemaVersion') in ('1.1','1.2','1.3'):
        for key, reason in (('outcomes','outcomesStatus'),('decisions','decisionsStatus'),('preservation','preservationStatus')):
            if key not in d: p.append(f'{key} is required by report schema 1.1.')
            elif not d[key] and not d.get(reason): p.append(f'Empty {key} requires an explicit {reason} explanation.')
        if not isinstance(d.get('conformance'),list): p.append('conformance must be an explicit array in schema 1.1.')
        inventory=d.get('fileImpact')
        if not isinstance(inventory,dict): p.append('fileImpact must group inspect, create, modify and preserve actions.')
        else:
            for action in ('inspect','create','modify','preserve'):
                if not isinstance(inventory.get(action),list): p.append(f'fileImpact.{action} must be an array, even when empty.')
            if not any(inventory.get(action) for action in ('inspect','create','modify','preserve')) and not d.get('fileImpactStatus'):
                p.append('An empty file impact inventory requires fileImpactStatus.')
        roadmap=d.get('roadmap')
        if not isinstance(roadmap,dict) or not roadmap.get('status') or not isinstance(roadmap.get('phases'),list): p.append('roadmap.status and roadmap.phases are required.')
        elif not roadmap.get('phases') and not d.get('roadmapStatus'): p.append('An empty roadmap requires roadmapStatus.')
        for i,x in enumerate(arr(d.get('proposedChanges'))):
            if not isinstance(x,dict) or x.get('classification') not in ('required','recommended','optional','owner-decision'): p.append(f'proposedChanges[{i}] needs a valid action classification.')
        for i,x in enumerate(arr(d.get('outcomes'))):
            required=('title','description','whyItMatters','practicalChange','classification','realization','verification')
            if not isinstance(x,dict) or not all(x.get(k) for k in required): p.append(f'outcomes[{i}] needs {", ".join(required)}.')
        for i,x in enumerate(arr(d.get('findings'))):
            required=('classification','disposition','confidence','requirementMeaning','expectedOutcome','verification')
            if not isinstance(x,dict) or not all(x.get(k) for k in required): p.append(f'findings[{i}] needs {", ".join(required)}.')
        for i,x in enumerate(arr((d.get('roadmap') or {}).get('phases')) or arr(d.get('phases'))):
            required=('name','purpose','deliverable','verification','completionCriteria')
            if not isinstance(x,dict) or not all(x.get(k) for k in required): p.append(f'phases[{i}] needs {", ".join(required)}.')
        # A decision-ready report cannot be produced from a requirement inventory alone.
        # Revalidate the embedded review against the actual target repository and pinned catalog.
        review=d.get('qualitativeReview')
        repo=d.get('repository') or {}
        if not isinstance(review,dict):
            p.append('qualitativeReview must contain the original evidence-backed review for all catalog requirements.')
        elif not repo.get('path') or not Path(repo['path']).is_dir():
            p.append('repository.path must identify the existing assessed repository so evidence can be revalidated.')
        else:
            if d.get('catalogSha256') != CATALOG_SHA256:
                p.append('catalogSha256 does not match the adoption skill catalog.')
            try:
                validation=validate_review(review,Path(repo['path']),CATALOG,CATALOG_SHA256)
            except ReviewValidationError as ex:
                p.append(f'qualitativeReview could not be validated: {ex}')
            else:
                if not validation['coverageComplete']:
                    p.append('All catalog requirements need one valid evidence-backed disposition before a decision-ready report can be rendered.')
                cov=d.get('coverage') or {}
                if cov.get('requiredRules') != validation['required'] or cov.get('reviewedRules') != validation['reviewed'] or cov.get('pendingRules') != validation['pending']:
                    p.append('coverage counts do not match the independently validated qualitative review.')
                if cov.get('unresolvedRules') != validation['unresolved']:
                    p.append('coverage.unresolvedRules does not match the qualitative review.')
                mapping={'conforms':'conforms','gap':'does-not-conform','not_applicable':'not-applicable','insufficient_evidence':'unverified'}
                expected=[]
                for rule in validation['rules']:
                    if rule['status'] in mapping:
                        expected.append((rule['rule'],mapping[rule['status']]))
                    else:
                        p.append(f"qualitative review contains an invalid disposition for {rule['rule']}.")
                supplied=arr(d.get('conformance'))
                actual=[(item.get('rule'),item.get('disposition')) for item in supplied if isinstance(item,dict)]
                if len(actual)!=len(expected) or set(actual)!=set(expected) or len({x[0] for x in actual})!=len(expected):
                    p.append('conformance must contain exactly one matching disposition for every catalog requirement.')
                else:
                    by_id={item.get('rule'):item for item in supplied}
                    raw_by_id={item['rule']:item for item in review.get('rules',[]) if isinstance(item,dict) and item.get('rule')}
                    for rule_id,_ in expected:
                        item=by_id[rule_id]
                        catalog_rule=EXPECTED_RULES[rule_id]
                        raw_review=raw_by_id.get(rule_id,{})
                        if not item.get('requirement') or not item.get('meaning'):
                            p.append(f'conformance[{rule_id}] needs a human-readable requirement name and meaning.')
                        if item.get('requirement') != catalog_rule.get('title'):
                            p.append(f'conformance[{rule_id}] requirement name must match the current catalog title.')
                        if item.get('meaning') != catalog_rule.get('summary'):
                            p.append(f'conformance[{rule_id}] requirement meaning must match the current catalog summary.')
                        if item.get('rationale') != raw_review.get('rationale'):
                            p.append(f'conformance[{rule_id}] rationale must be copied from the validated requirement review.')
                        if not isinstance(item.get('evidenceRefs'),list) or not item['evidenceRefs']:
                            p.append(f'conformance[{rule_id}] needs evidence references.')
                        else:
                            allowed_refs=[]
                            for evidence_item in raw_review.get('evidence',[]):
                                if evidence_item.get('kind')=='absence':
                                    allowed_refs.append(evidence_item.get('path'))
                                else:
                                    allowed_refs.append(f"{evidence_item.get('path')}:{evidence_item.get('startLine')}-{evidence_item.get('endLine')}")
                            if not any(ref in allowed_refs for ref in item['evidenceRefs']):
                                p.append(f'conformance[{rule_id}] evidence references must point to its validated source evidence.')
                gap_ids={rule_id for rule_id,status in expected if status=='does-not-conform'}
                finding_ids=set()
                for item in arr(d.get('findings')):
                    if not isinstance(item,dict):
                        continue
                    refs=arr(item.get('requirementRefs'))
                    if item.get('rule'):
                        refs.append(item.get('rule'))
                    finding_ids.update(refs)
                missing_findings=sorted(gap_ids-finding_ids)
                if missing_findings:
                    p.append('Every nonconforming requirement must be represented by a human-readable finding; missing: '+', '.join(missing_findings)+'.')
                summary=d.get('assessmentSummary') or {}
                benefit_details=[item for item in arr(summary.get('benefitDetails')) if isinstance(item,dict) and item.get('benefit')]
                reported_outcomes=arr(d.get('outcomes'))
                outcome_text={str(item.get('description') or item.get('title') or '') for item in reported_outcomes if isinstance(item,dict)}
                missing_outcomes=[item.get('benefit') for item in benefit_details if str(item.get('benefit')) not in outcome_text]
                if missing_outcomes:
                    p.append('Every assessment benefit detail must be represented as an explicitly realized, conditional, or not-applicable report outcome; missing: '+', '.join(str(x) for x in missing_outcomes)+'.')
                value_benefits=arr((d.get('value') or {}).get('benefits'))
                value_titles={str(item.get('title') or '') for item in value_benefits if isinstance(item,dict)}
                missing_benefits=[item.get('benefit') for item in benefit_details if str(item.get('benefit')) not in value_titles]
                if missing_benefits:
                    p.append('The value summary must reconcile to the assessment benefit analysis; missing: '+', '.join(str(x) for x in missing_benefits)+'.')
                counts=cov.get('dispositionCounts') or {}
                expected_counts={
                    'conforms':validation['counts']['conforms'],
                    'doesNotConform':validation['counts']['gap'],
                    'notApplicable':validation['counts']['not_applicable'],
                    'unverified':validation['counts']['insufficient_evidence'],
                    'partiallyConforms':0,
                    'notAssessed':0,
                    'unsupported':0,
                    'blocked':0,
                }
                for key,value in expected_counts.items():
                    if counts.get(key) != value:
                        p.append(f'coverage.dispositionCounts.{key} does not match the validated review.')
                if validation['unresolved'] and d.get('recommendation',{}).get('status') != 'INSUFFICIENT_EVIDENCE':
                    p.append('An assessment with unresolved requirements must use an INSUFFICIENT_EVIDENCE recommendation.')
                if validation['unresolved'] and d.get('assessmentStatus') in ('complete','completed','COMPLETE'):
                    p.append('Assessment cannot be marked complete while qualitative requirements remain unresolved.')
        if d.get('assessmentStatus') in ('complete','completed','COMPLETE'):
            cov=d.get('coverage') or {}
            if cov.get('pendingRules') not in (0,'0') or cov.get('reviewedRules') != cov.get('requiredRules'):
                p.append('Assessment cannot be marked complete while requirements remain pending or unreviewed.')
    return p
def main():
    ap=argparse.ArgumentParser(description='Render the ACIMA multi-page HTML outcome report');ap.add_argument('--input',required=True);ap.add_argument('--out-dir',required=True);ap.add_argument('--overwrite',action='store_true');a=ap.parse_args()
    try:
        d=json.loads(Path(a.input).read_text(encoding='utf-8-sig'));problems=validate(d)
        if problems:raise ReportError('Invalid report model:\n- '+'\n- '.join(problems))
        out=Path(a.out_dir).resolve();out.mkdir(parents=True,exist_ok=True);names=list(PAGES)+['report-data.json','assets/report.css'];existing=[out/n for n in names if (out/n).exists()]
        if existing and not a.overwrite:raise ReportError('Output already contains report files; use --overwrite to replace them.')
        (out/'assets').mkdir(exist_ok=True)
        for name,body in render(d).items():(out/name).write_text(body,encoding='utf-8')
        (out/'report-data.json').write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');(out/'assets/report.css').write_text(CSS.read_text(encoding='utf-8'),encoding='utf-8')
        print(f'Rendered {len(PAGES)} HTML pages to {out}');print('Open index.html. No build step or network access required.');return 0
    except (OSError,json.JSONDecodeError,ReportError) as ex:print(f'render_report: {ex}',file=sys.stderr);return 2
if __name__=='__main__':raise SystemExit(main())
