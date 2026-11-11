#!/usr/bin/env python3
"""Render a six-page, plain-language ACIMA report from the skill's normalized JSON model."""
from __future__ import annotations
import argparse, hashlib, html, json, re, sys
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
PAGES={'index.html':'Overview','proposal.html':'Proposal','findings.html':'Findings','files.html':'Files','plan.html':'Plan','evidence.html':'Evidence'}
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

def module_map_sections(d):
    mm=d.get('moduleMap') or {}; authority=mm.get('authoritativeMap') or {}; proposal=mm.get('proposal') or {}
    gate=d.get('ownershipGate') or {}; modules=arr(proposal.get('modules')); recs=arr(proposal.get('recommendations')); decisions=arr(proposal.get('decisions'))
    review=mm.get('review') or {}; review_status=review.get('status') or proposal.get('status') or 'pending'
    authority_status=authority.get('status') or ('present' if authority.get('present') else 'absent')
    gate_status=gate.get('status') or ('ready' if authority_status=='complete' else 'blocked')
    if proposal:
        map_intro=(f'<p class="reconciliation"><b>This map is proposed, not authoritative.</b> {e(proposal.get("basis") or mm.get("summary"))} The review status is <b>{e(status_label(review_status))}</b>. Inferred boundaries remain candidates until accepted individually.</p>'
                   '<p class="note">Evidence below distinguishes observed repository facts from inferred boundaries. A folder, project or package is a discovery signal, not proof of ownership.</p>')
    else:
        map_intro=f'<p class="reconciliation"><b>Authoritative map:</b> {e(status_label(authority_status))}. {e(authority.get("summary") or "No module-map proposal was required.")}</p>'
    issues=arr(authority.get('issues'))
    issue_html=table(['Map issue','Detail'],[(x.get('code') if isinstance(x,dict) else 'Issue',x.get('detail') if isinstance(x,dict) else x) for x in issues],caption='Authoritative map issues',row_headers=True) if issues else '<p class="empty">No structural map issue was recorded.</p>'
    module_rows=[(x.get('name') or x.get('id'),x.get('responsibility'),status_label(x.get('ownership') or x.get('status')),', '.join(arr((x.get('contracts') or {}).get('paths')) or ['None identified']),', '.join(arr((x.get('implementation') or {}).get('paths'))),map_evidence(x.get('evidence')),status_label(x.get('reviewDecision') or 'pending')) for x in modules]
    module_table=table(['Proposed module','Responsibility','Ownership basis','Candidate contracts','Implementation paths','Evidence','Review'],module_rows,'No candidate ownership boundary was identified. The repository may be a single ownership area or may need owner-led discovery.',caption='Proposed module boundaries',row_headers=True) if modules else '<p class="empty">No candidate ownership boundary was identified. This is not a claim that the repository has no architecture; it means layout and source evidence did not support a safe proposal.</p>'
    dep_rows=[]
    for module in modules:
        for dep in arr(module.get('dependencies')):
            dep_rows.append((module.get('name'),dep.get('module'), 'Private implementation suspected' if dep.get('leaksImplementation') else 'Observed import', map_evidence(dep.get('evidence'))))
    dep_table=table(['Module','Observed dependency','Nature','Evidence'],dep_rows,'No cross-candidate dependency was observed in the inspected import lines.',caption='Observed candidate dependencies',row_headers=True)
    unassigned=arr(proposal.get('unassigned'))
    unassigned_table=table(['Unassigned production path','Why it is unresolved'],[(x.get('path'),x.get('reason')) for x in unassigned],'Every discovered production source path falls under a candidate boundary. Ownership itself still requires review.',caption='Unassigned or ambiguous production code',row_headers=True)
    quality=proposal.get('quality') or {}; observations=arr(quality.get('observations'))
    quality_table=table(['Observation','What was observed','Basis','Confidence'],[(x.get('topic'),x.get('observation'),status_label(x.get('basis')),status_label(x.get('confidence'))) for x in observations],'No architectural-quality observation was recorded for the proposal.',caption='Proposed map quality observations',row_headers=True)
    rec_cards=''.join(f'<article class="decision-row"><div class="row"><h3>{e(x.get("title"))}</h3>{pill(x.get("classification"),status_label(x.get("classification")))}</div><p><b>Observed:</b> {e(x.get("observed"))}</p><p><b>Why it matters:</b> {e(x.get("whyItMatters"))}</p><p><b>Recommendation:</b> {e(x.get("recommendation"))}</p><p><b>Benefit:</b> {e(x.get("benefit"))}</p><p><b>Risk and uncertainty:</b> {e(x.get("risk"))} {e(x.get("uncertainty"))}</p><p><b>Owner input:</b> {"Required" if x.get("requiresUserInput") else "Not required"} &middot; <b>Essential:</b> {"Yes" if x.get("essential") else "Optional refinement"}</p><details><summary>Evidence behind this recommendation</summary><p>{e(map_evidence(x.get("evidence")))}</p><p><b>Decision:</b> {e(status_label(x.get("decision") or "pending"))}</p></details></article>' for x in recs) or '<p class="empty">No change is recommended from the available evidence. That is a proposal judgement, not proof that the current boundaries are ideal.</p>'
    decision_rows=[(x.get('question'),x.get('context'),x.get('recommendation'),'Essential' if x.get('essential') else 'Optional',status_label(x.get('status')),', '.join(arr(x.get('options')))) for x in decisions]
    decision_table=table(['Decision','Why it matters','Recommendation','Essential?','Status','Options'],decision_rows,'No owner decision was generated for this proposal.',caption='Module-map decisions requiring user input',row_headers=True) if decisions else '<p class="empty">No module-map decision was generated. This does not mean the existing map is correct; it means discovery found no proposal-level decision to record.</p>'
    review_html=f'<p class="note"><b>Review provenance:</b> reviewer {e(review.get("reviewer") or "not recorded")} &middot; reviewed {e(review.get("reviewedOn") or "not recorded")} &middot; proposal {e(mm.get("proposalId") or "not recorded")}.</p>' if review else '<p class="note">No review or approval is recorded. Generated boundaries are not authoritative and must not enable ownership-dependent checks.</p>'
    return f'''<section id="module-map"><small>MODULE OWNERSHIP</small><h2>Proposed module map</h2>{map_intro}<div class="metrics compact">{metric('CANDIDATE MODULES',len(modules))}{metric('UNASSIGNED PATHS',len(unassigned))}{metric('OWNERSHIP GATE',status_label(gate_status),'Independent review continues' if gate.get('independentReviewContinues') else 'Review gate not recorded')}</div>{module_table}{review_html}</section><section id="contracts-and-dependencies"><h2>Contracts and dependencies</h2><p class="lead">Public contracts are candidate locations, not proof that an API is well designed. Dependencies below come from observed import lines.</p>{dep_table}</section><section id="unassigned-code"><h2>Unassigned or ambiguous code</h2>{unassigned_table}</section><section id="map-quality"><h2>Architectural quality observations</h2>{quality_table}</section><section id="map-recommendations"><h2>Recommendations and rationale</h2><div class="stack">{rec_cards}</div></section><section id="map-decisions"><h2>Decisions requiring user input</h2>{decision_table}<p class="note">You can accept, modify, reject or defer individual boundaries and recommendations. Reading this report does not approve the map. {e(mm.get("nextDecision") or "No approval is implied.")}</p></section>'''

def agent_guidance_section(d):
    guidance=d.get('agentGuidance') or {}
    if not guidance:
        return ''
    validation=guidance.get('validation') or {}
    files=guidance.get('files') or []
    problem_rows=[(x,) for x in arr(validation.get('problems'))]
    return f'<section id="ai-agent-guidance"><small>AI AGENT GUIDANCE</small><h2>How future agents will build here</h2><p class="lead">Primary instructions: <b>{e(guidance.get("primaryFile") or "not recorded")}</b>. Convention: <b>{e((guidance.get("convention") or {}).get("convention") or "not recorded")}</b>. Validation: <b>{e(status_label(validation.get("status") or "not run"))}</b>.</p><p class="note">Existing user-authored instructions preserved: {e("yes" if guidance.get("preservedExisting") else "not established")}. This is structural validation, not proof that every coding agent will follow the guidance.</p>{table(["Generated or updated file"],[(x,) for x in files],"No agent-instruction file was written.",caption="AI agent guidance files")}{table(["Validation problem"],problem_rows,"No validation problem was recorded.",caption="AI agent guidance validation problems") if problem_rows else ""}<p class="note">Rules covered: {e(validation.get("rulesCovered"))} of {e(validation.get("rulesRequired"))}. Supporting guidance is under <code>docs/architecture/acima/</code>.</p></section>'

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
    return f'<section id="adoption-workflow"><small>ADOPTION WORKFLOW</small><h2>Where the adoption stands</h2><p class="lead">Mode: <b>{e(status_label(wf.get("mode") or "unknown"))}</b>. Current stage: <b>{e(status_label((wf.get("currentStage") or {}).get("label") or "not started"))}</b>.</p>{warning}{guidance_summary}{remediation}{stage_table}<p class="note"><b>Next action:</b> {e(next_text)}</p><p class="note">Configured, generated and verified are separate states. This section does not turn a proposal or a CI file into proof that a remote check ran.</p></section>'

def module_map_overview(d):
    mm=d.get('moduleMap') or {}; authority=mm.get('authoritativeMap') or {}; proposal=mm.get('proposal') or {}; gate=d.get('ownershipGate') or {}
    if not mm:
        return '<section id="module-ownership"><small>MODULE OWNERSHIP</small><h2>Module-map discovery was not embedded in this report</h2><p>This report does not contain a module-map proposal or an assessment of an authoritative map. Do not infer ownership from the absence of this section.</p></section>'
    status=authority.get('status') or ('present' if authority.get('present') else 'absent'); review=mm.get('review') or {}
    review_status=review.get('status') or proposal.get('status') or 'pending'
    if proposal:
        next_text=mm.get('nextDecision') or 'Review the proposed boundaries and recommendations; no ownership is approved by this report.'
        body=f'<p class="lead">{e(mm.get("summary"))}</p><p class="reconciliation"><b>The proposed map is not authoritative.</b> Review status: <b>{e(status_label(review_status))}</b>. {e(next_text)}</p><p class="note">The 55-requirement qualitative review can continue independently. Deterministic ownership-dependent checks remain blocked until the map is explicitly approved.</p>'
    else:
        body=f'<p class="lead">{e(mm.get("summary") or authority.get("summary"))}</p><p class="reconciliation"><b>Authoritative map:</b> {e(status_label(status))}. It was evaluated in place rather than replaced by discovery.</p>'
    rules=arr(gate.get('ownershipDependentRules'))
    return f'<section id="module-ownership"><small>MODULE OWNERSHIP</small><h2>Can the boundary checks run?</h2>{body}<div class="metrics compact">{metric("AUTHORITATIVE MAP",status_label(status))}{metric("PROPOSAL REVIEW",status_label(review_status))}{metric("OWNERSHIP GATE",status_label(gate.get("status") or "blocked"),f"{len(rules)} graph-dependent rule(s)" if rules else "No graph-dependent rules listed")}</div><p class="cross-links"><span>Related:</span> <a href="proposal.html#module-map">Module-map proposal</a> <a href="proposal.html#map-decisions">Decisions</a> <a href="evidence.html#ownership-blocked">Blocked ownership checks</a></p></section>'

def shell(data,file,title,subtitle,body):
    repo=e((data.get('repository') or {}).get('name') or 'Repository assessment'); active=''.join(f'<a href="{href}" class="{"active" if href==file else ""}"'+(' aria-current="page"' if href==file else '')+f'>{label}</a>' for href,label in NAV)
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light"><meta name="description" content="Plain-language ACIMA assessment for {repo}"><title>{e(title)} &middot; {repo} &middot; ACIMA</title><link rel="stylesheet" href="assets/report.css"></head><body><a class="skip" href="#main">Skip to report content</a><header><a class="brand" href="index.html" aria-label="ACIMA Architecture Outcome Report"><b aria-hidden="true">A</b><span>ACIMA<small>ARCHITECTURE OUTCOME REPORT</small></span></a><div class="meta"><span>{repo}</span><span>{time_tag(data.get('generatedAt'))}</span></div></header><div class="layout"><aside aria-label="Report navigation"><small>REPORT SECTIONS</small><nav aria-label="Report sections">{active}</nav><p class="rail-note">A practical guide to what ACIMA found, what it proposes, and what the proposed work would deliver.</p></aside><main id="main" tabindex="-1" aria-labelledby="page-title"><div class="page-head"><small>{repo} / {e(PAGES[file])}</small><h1 id="page-title">{e(title)}</h1><p>{e(subtitle)}</p></div>{body}<footer>ACIMA &middot; Architecture that enforces itself. <span>Generated from the accompanying evidence model.</span></footer></main></div></body></html>'''
def render(d):
    repo=d.get('repository') or {}; rec=d.get('recommendation') or {}; ov=d.get('overview') or {}; val=d.get('value') or {}; arch=d.get('architecture') or {}; cov=d.get('coverage') or {}; gate=d.get('ownershipGate') or {}
    strengths=arr(d.get('strengths')); findings=arr(d.get('findings')); changes=arr(d.get('proposedChanges')); outcomes=arr(d.get('outcomes')); phases=arr((d.get('roadmap') or {}).get('phases')) or arr(d.get('phases')); decisions=arr(d.get('decisions')); evidence=arr(d.get('evidence')); limits=arr(d.get('limitations'))
    conformance=arr(d.get('conformance'))
    exceptions=[x for x in conformance if isinstance(x,dict) and key(x.get('disposition')) not in ('conforms','not_applicable')]
    conformance_by_rule={x.get('rule'):x for x in conformance if isinstance(x,dict) and x.get('rule')}
    benefits=''.join(f'<article><small>{i+1:02}</small><h3>{e(x.get("title") or "Outcome")}</h3><p>{e(x.get("description") or x.get("benefit"))}</p><em>{e(x.get("availability") or "Proposed benefit; not yet verified")}</em></article>' for i,x in enumerate(arr(val.get('benefits')))) or '<p class="empty">No repository-specific benefits are recorded.</p>'
    finding_cards=''.join(f'<article class="finding"><div class="row"><h3>{e(x.get("title") or "Finding")}</h3>{pill(x.get("disposition") or x.get("status") or x.get("confidence"))}</div><p>{e(x.get("what") or x.get("summary"))}</p><p><b>Why it matters:</b> {e(x.get("why"))}</p><p><b>Recommended response:</b> {e(x.get("recommendation") or x.get("fix"))}</p><p><b>Action type:</b> {e(status_label(x.get("classification")))}</p><details><summary>Evidence and technical details</summary><p><b>What the requirement means:</b> {e(x.get("requirementMeaning"))}</p><p><b>Sources:</b> {e(x.get("paths") or x.get("path"))} &middot; {e(x.get("evidenceRefs"))}</p><p><b>What this should achieve:</b> {e(x.get("expectedOutcome"))}</p><p><b>How to verify:</b> {e(x.get("verification"))}</p><p><b>Confidence and limits:</b> {e(status_label(x.get("confidence")))} &middot; {e(x.get("limitations"))}</p></details></article>' for x in findings) or '<p class="empty">No findings were recorded. Check the Evidence page to confirm that review coverage is complete before interpreting this as a clean result.</p>'
    outcome_cards=''.join(f'<article class="row"><div><h3>{e(x.get("title") or "Outcome")}</h3><p>{e(x.get("description"))}</p><p><b>Why it matters:</b> {e(x.get("whyItMatters"))}</p><p><b>Practical change:</b> {e(x.get("practicalChange"))}</p><p><b>Type:</b> {e(status_label(x.get("classification")))} &middot; <b>Basis:</b> {e(status_label(x.get("realization")))}</p><p><b>Verification:</b> {e(x.get("verification"))}</p><em>{e(x.get("limitations"))}</em></div>{pill(x.get("status") or x.get("availability"))}</article>' for x in outcomes) or f'<p class="empty">{e(d.get("outcomesStatus") or "Outcomes have not yet been established. No benefits are inferred.")}</p>'
    phase_cards=''.join(f'<article class="phase"><div class="row"><h3>{e(x.get("name") or "Phase")}</h3>{pill(x.get("status"))}</div><p>{e(x.get("purpose"))}</p><p><b>Before this phase:</b> {e(x.get("prerequisites") or x.get("dependsOn"))}</p><p><b>What it produces:</b> {e(x.get("deliverable"))}</p><p><b>How to verify:</b> {e(x.get("verification"))}</p><p><b>Done when:</b> {e(x.get("completionCriteria"))}</p><p><b>Who approves:</b> {e(x.get("approval"))}</p><details><summary>Work and affected areas</summary>{bullets(x.get("activities",[]),"No activities recorded.")}{bullets(x.get("affectedFiles",[]),"Affected files not recorded.")}</details></article>' for x in phases) or f'<p class="empty">{e(d.get("roadmapStatus") or "An adoption plan has not been established yet.")}</p>'
    linked_findings=sum(1 for x in findings if any(r in conformance_by_rule for r in finding_rules(x)))
    unlinked_findings=len(findings)-linked_findings
    if conformance:
        finding_word='finding' if len(findings)==1 else 'findings'
        exception_word='exception' if len(exceptions)==1 else 'exceptions'
        reconciliation_sentence=f'{len(findings)} grouped {finding_word} and {len(exceptions)} requirement {exception_word} are recorded.'
        if linked_findings:
            verb='names' if linked_findings==1 else 'name'
            reconciliation_sentence += f' {linked_findings} {finding_word} {verb} a matching requirement result.'
        if unlinked_findings:
            verb='does' if unlinked_findings==1 else 'do'
            reconciliation_sentence += f' {unlinked_findings} {finding_word} {verb} not name a matching result; they remain grouped problems.'
    else:
        reconciliation_sentence='Requirement results were not supplied, so findings cannot be reconciled to them.'
    pages={}
    pages['index.html']=f'''<section class="decision"><div><small>RECOMMENDATION</small><h2>{e(recommendation(rec.get('status')))}</h2><p>{e(rec.get('summary') or ov.get('summary'))}</p></div>{pill(d.get('assessmentStatus'), assessment(d.get('assessmentStatus')))}</section><section><small>THE SHORT VERSION</small><h2>What this means for your product</h2><p class="lead">{e(ov.get('plainLanguage'))}</p></section><div class="metrics compact">{metric('FINDINGS RECORDED',len(findings) or 'None recorded')}{metric('REQUIREMENTS REVIEWED',coverage_ratio(cov),unresolved_note(cov))}</div><p class="context-line"><b>Repository:</b> {e(repo_mode(repo.get('mode')))} <span aria-hidden="true">&middot;</span> <b>Architecture:</b> {e(arch.get('family') or 'Not established')}</p>{module_map_overview(d)}<p class="cross-links"><span>Related:</span> <a href="findings.html#findings">Findings</a> <a href="plan.html#adoption-plan">Adoption plan</a> <a href="evidence.html#evidence-summary">Evidence summary</a></p><section id="completion"><h2>What has been completed?</h2>{table(['Milestone','Status'],[('Assessment', milestone((d.get('milestones') or {}).get('assessmentComplete'))),('Report generation', 'Completed when this report was written'),('Adoption proposal',milestone((d.get('milestones') or {}).get('adoptionProposalComplete'))),('Implementation',milestone((d.get('milestones') or {}).get('implementationComplete'))),('Conformance verification',milestone((d.get('milestones') or {}).get('conformanceVerified')))],caption='Completion status by milestone',row_headers=True)}<p class="note">Writing this report does not complete the assessment, approve the proposal, implement changes or verify conformance.</p></section><section><small>WHAT YOU GET</small><h2>What adoption would make possible</h2><div class="benefits">{benefits}</div></section><section><small>THE DECISION</small><h2>Why this recommendation?</h2><div class="cols"><div><h3>Why it fits this repository</h3>{bullets(arr(rec.get('reasons')))}</div><div><h3>Tradeoffs and caveats</h3>{bullets(arr(rec.get('caveats')))}</div></div></section><section class="next"><div><small>NEXT STEP</small><h2>{e(ov.get('nextAction') or 'Review the proposal')}</h2><p>{e(ov.get('nextActionWhy'))}</p></div><a href="proposal.html">See what would change <span aria-hidden="true">&rarr;</span></a></section>'''
    pages['proposal.html']=f'''{module_map_sections(d)}<section><small>CURRENT STATE</small><h2>How the repository works today</h2><p class="lead">{e(arch.get('currentState'))}</p><p class="cross-links"><span>Related:</span> <a href="findings.html#findings">Findings</a> <a href="files.html#file-changes">Proposed file changes</a> <a href="plan.html#adoption-plan">Adoption plan</a></p><div class="cols"><div><h3>Already working</h3>{bullets(strengths)}</div><div><h3>What would be added</h3>{bullets(arr(val.get('adds')))}</div></div></section><section><small>PROPOSED STATE</small><h2>What would change</h2><p>{e(arch.get('proposedState'))}</p>{table(['Capability','What changes','What it makes possible'],[(x.get('capability'),x.get('change'),x.get('outcome')) for x in arr(arch.get('targetCapabilities'))],caption='Proposed capabilities',row_headers=True)}</section><section><small>EXPECTED OUTCOMES</small><h2>What should become easier or safer</h2><div class="stack">{outcome_cards}</div></section><section><small>TRADEOFFS</small><h2>Costs, risks, and limits</h2><div class="cols"><div><h3>Cost and effort</h3>{bullets(arr(val.get('costs')))}</div><div><h3>Risks and mitigations</h3>{bullets(arr(val.get('risks')))}</div></div><h3>What ACIMA will not do</h3>{bullets(limits)}</section>'''
    pages['findings.html']=f'''<section id="strengths"><small>EXISTING STRENGTHS</small><h2>What is already in good shape</h2>{bullets(strengths,'No strengths were recorded. This does not mean none exist.')}</section><section id="findings"><small>ASSESSMENT FINDINGS</small><h2>What needs attention</h2><p class="lead">Findings are grouped by the underlying problem. Each explains what happens, why it matters, and the recommended response.</p><p class="reconciliation"><b>Findings and requirement results are separate ledgers.</b> {e(reconciliation_sentence)} <a href="evidence.html#exceptions">Review requirement exceptions</a>.</p><p class="note">Findings group related problems across files; requirement results decide one rule at a time. They are not expected to match one-to-one.</p><p class="cross-links"><span>Related:</span> <a href="files.html#file-changes">Proposed file changes</a> <a href="plan.html#adoption-plan">Adoption plan</a> <a href="evidence.html#exceptions">Requirement exceptions</a></p>{finding_cards}</section>'''
    inventory=d.get('fileImpact') or {}
    categorized=[]
    for action in ('inspect','create','modify','preserve'):
        source=arr(inventory.get(action)) or [x for x in changes if x.get('action')==action]
        categorized.extend((x.get('path'),action,x.get('purpose'),x.get('expectedOutcome'),status_label(x.get('classification')),x.get('confidence')) for x in source)
    file_rows=[(path,action_label(act),purpose,outcome,commitment,status_label(confidence)) for path,act,purpose,outcome,commitment,confidence in categorized]
    pages['files.html']=f'''<section id="file-changes"><h2>Proposed file changes</h2><p class="lead">Some files are listed only so they can be inspected; that is not a proposed edit. Creating or changing a file remains a proposal until someone approves it.</p><p class="cross-links"><span>Related:</span> <a href="findings.html#findings">Findings</a> <a href="plan.html#adoption-plan">Adoption plan</a> <a href="evidence.html#exceptions">Requirement exceptions</a></p>{table(['File or area','Action','Why it is involved','What it should achieve','Required or optional','Confidence'],file_rows,d.get('fileImpactStatus') or 'No proposed file changes were supplied.',caption='Proposed file changes',row_headers=True)}</section><section><h2>What should stay the same</h2>{bullets(arr(d.get('preservation')),d.get('preservationStatus') or 'What should stay the same has not yet been established.')}</section><div class="metrics">{metric('FILES TO CREATE',sum(x[1]=='create' for x in categorized))}{metric('FILES TO MODIFY',sum(x[1]=='modify' for x in categorized))}{metric('FILES TO INSPECT',sum(x[1]=='inspect' for x in categorized))}{metric('FILES TO PRESERVE',sum(x[1]=='preserve' for x in categorized))}</div>'''
    decision_html=''.join(f'<article class="decision-row"><h3>{e(x.get("question"))}</h3><p>{e(x.get("context"))}</p><p><b>Recommendation:</b> {e(x.get("recommendation"))}</p><p><b>What this blocks:</b> {e(x.get("blockedWork"))}</p><p><b>Needed before implementation:</b> {e(x.get("requiredBeforeImplementation"))}</p><details><summary>Other options and consequences</summary>{bullets(x.get("alternatives",[]),"Alternatives are not established.")}<p><b>Impact:</b> {e(x.get("impact"))}</p><p><b>Why an owner is needed:</b> {e(x.get("whyOwner"))}</p></details></article>' for x in decisions) or f'<p class="empty">{e(d.get("decisionsStatus") or "No owner decisions are recorded. The assessment has not established whether no decision is needed or discovery is incomplete.")}</p>'
    pages['plan.html']=f'''{adoption_workflow(d)}{agent_guidance_section(d)}{remediation_outcome(d)}<section id="adoption-plan"><h2>Adoption plan</h2><p class="cross-links"><span>Related:</span> <a href="findings.html#findings">Findings</a> <a href="files.html#file-changes">Proposed file changes</a> <a href="evidence.html#exceptions">Requirement exceptions</a></p><div class="stack">{phase_cards or e(d.get("roadmapStatus") or "An adoption plan has not been established yet.")}</div></section><section><h2>Decisions that need an owner</h2>{decision_html}</section><section><h2>What approval would mean</h2><p>{e(d.get('approvalStatement') or 'Reading this report does not authorize implementation. Approval must identify the specific proposed scope.')}</p></section>'''
    evrows=[(x.get('label') or x.get('kind'),x.get('source'),x.get('whatItSupports'),status_label(x.get('status'))) for x in evidence]
    reviewed=coverage_ratio(cov)
    unresolved='Not recorded' if cov.get('unresolvedRules') in (None,'') else str(cov.get('unresolvedRules'))
    exception_count=len(exceptions) if conformance else 'Not recorded'
    if conformance:
        if exceptions:
            noun='result' if len(exceptions)==1 else 'results'
            verb='needs' if len(exceptions)==1 else 'need'
            exception_sentence=f'{len(exceptions)} requirement {noun} {verb} attention.'
        else:
            exception_sentence='No requirement exceptions are recorded.'
    else:
        exception_sentence='Requirement-level results were not supplied, so this page does not claim conformance.'
    summary_sentence=f'The review covered {reviewed} requirements. {exception_sentence}'
    coverage_table=table(['What was checked','Result'],[('Requirements in the catalog',cov.get('requiredRules')),('Reviewed with evidence',cov.get('reviewedRules')),('Not yet reviewed',cov.get('pendingRules')),('Still unresolved',cov.get('unresolvedRules')),('Automated checks run',cov.get('automatedChecksRun')),('Manual reviews completed',cov.get('manualReviewsCompleted')),('Skipped because unsupported',cov.get('skippedOrUnsupported')),('Meets the requirement',(cov.get('dispositionCounts') or {}).get('conforms')),('Does not meet the requirement',(cov.get('dispositionCounts') or {}).get('doesNotConform')),('Partly meets the requirement',(cov.get('dispositionCounts') or {}).get('partiallyConforms')),('Not applicable',(cov.get('dispositionCounts') or {}).get('notApplicable')),('Not enough evidence',(cov.get('dispositionCounts') or {}).get('unverified')),('Not yet assessed',(cov.get('dispositionCounts') or {}).get('notAssessed')),('Not supported by current tools',(cov.get('dispositionCounts') or {}).get('unsupported')),('Blocked by another issue',(cov.get('dispositionCounts') or {}).get('blocked'))],caption='Requirement review coverage',row_headers=True)
    conformance_table=table(['Requirement','Result','Explanation','Evidence'],[(x.get('requirement') or x.get('title'),status_label(x.get('disposition')),x.get('meaning') or x.get('rationale'),refs(x.get('evidenceRefs'))) if isinstance(x,dict) else (x,'Not established','No explanation supplied.','No evidence supplied.') for x in conformance],'No requirement results were supplied.',caption='Full requirement results',row_headers=True)
    exception_table=table(['Requirement','Result','Explanation','Evidence'],[(x.get('requirement') or x.get('title'),status_label(x.get('disposition')),x.get('meaning') or x.get('rationale'),refs(x.get('evidenceRefs'))) for x in exceptions],'No requirement exceptions are recorded.',caption='Requirement exceptions',row_headers=True)
    evidence_table=table(['Evidence','Source','What it supports','Status'],evrows,caption='Evidence sources',row_headers=True)
    provenance_table=table(['Field','Value'],[('Repository',repo.get('path')),('Commit',repo.get('commit')),('Report generated',human_date(d.get('generatedAt'))),('ACIMA standard version',d.get('standardVersion')),('Adoption skill version',d.get('skillVersion')),('Rule catalog fingerprint',d.get('catalogSha256')),('Assessment status',assessment(d.get('assessmentStatus')))],caption='Report provenance',row_headers=True)
    result_label=f'All requirement results ({len(conformance)})' if conformance else 'Requirement results'
    exception_panel=exception_table if exceptions else f'<p class="empty">{e(exception_sentence)}</p>'
    ownership_rules=arr(gate.get('ownershipDependentRules'))
    ownership_sentence=(gate.get('reason') or ('Ownership-dependent checks can run against the authoritative map.' if gate.get('status')=='ready' else 'Ownership-dependent checks are blocked until an authoritative module map is approved.'))
    blocked_table=table(['Requirement','Status','Why it depends on ownership'],[(rule,'Blocked' if gate.get('status')!='ready' else 'Ready',ownership_sentence) for rule in ownership_rules],'No ownership-dependent rules were listed in this report. Do not treat that as proof that no check depends on ownership.',caption='Ownership-dependent checks',row_headers=True) if ownership_rules else '<p class="empty">No ownership-dependent rule list was supplied. Confirm the assessment did not silently omit graph-dependent checks.</p>'
    pages['evidence.html']=f'''<section id="evidence-summary"><small>EVIDENCE SUMMARY</small><h2>What the evidence shows</h2><p class="lead">{e(summary_sentence)}</p><ul class="summary-facts"><li><b>{e(reviewed)}</b><span>requirements reviewed</span></li><li><b>{e(unresolved)}</b><span>still unresolved</span></li><li><b>{e(exception_count)}</b><span>requirement exceptions</span></li></ul><p class="note">Review coverage is not a conformance score. Automated checks, the evidence-backed review and the final requirement results stay separate.</p><p class="cross-links"><span>Related:</span> <a href="findings.html#findings">Findings</a> <a href="files.html#file-changes">Proposed file changes</a> <a href="plan.html#adoption-plan">Adoption plan</a></p></section><section id="exceptions"><small>EXCEPTIONS</small><h2>What needs attention</h2>{exception_panel}</section><section id="limits"><small>LIMITS</small><h2>What could not be established</h2>{bullets(limits,'No limitations supplied. Confirm the assessment explicitly considered coverage and tooling limits.')}</section><section id="ownership-blocked"><small>OWNERSHIP GATE</small><h2>Checks that depend on module ownership</h2><p class="lead">{e(ownership_sentence)}</p>{blocked_table}<p class="note">Independent qualitative review continues for every catalog requirement. A missing or unapproved map does not make the whole architecture unassessed.</p></section><section id="detailed-evidence"><small>FULL RECORD</small><h2>Detailed evidence</h2><p class="lead">Open a section to inspect the complete coverage, every requirement result, the supporting sources and the report provenance.</p><details><summary>Review coverage: {e(reviewed)}</summary>{coverage_table}</details><details><summary>{e(result_label)}</summary>{conformance_table}</details><details><summary>Supporting evidence ({len(evidence)})</summary>{evidence_table}</details><details><summary>Report provenance</summary>{provenance_table}</details></section>'''
    titles={'index.html':('Overview','The decision at a glance'), 'proposal.html':('What would change','The proposed architecture and what it would deliver'),'findings.html':('What we found','What is working and what needs attention'),'files.html':('Files and impact','Exactly what is proposed to change'),'plan.html':('Plan and decisions','What happens, in what order, and who decides'),'evidence.html':('Evidence and limits','What was checked and what the results prove')}
    return {f:shell(d,f,*titles[f],body) for f,body in pages.items()}
def validate(d):
    p=[]
    if not isinstance(d,dict):return ['Report model must be a JSON object.']
    if d.get('schemaVersion') not in ('1.0','1.1'):p.append("schemaVersion must be '1.0' or '1.1'.")
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
    for i,x in enumerate(arr(d.get('proposedChanges'))):
        if not isinstance(x,dict) or not x.get('path') or x.get('action') not in ('create','modify','delete','inspect','no-change') or not x.get('purpose') or not x.get('expectedOutcome'):p.append(f'proposedChanges[{i}] needs path, supported action, purpose and expectedOutcome.')
    mm=d.get('moduleMap')
    if mm is not None:
        if not isinstance(mm,dict): p.append('moduleMap must be an object when supplied.')
        else:
            authority=mm.get('authoritativeMap')
            if not isinstance(authority,dict) or not authority.get('status'): p.append('moduleMap.authoritativeMap.status is required.')
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
    workflow=d.get('adoptionWorkflow')
    if workflow is not None:
        if not isinstance(workflow,dict) or workflow.get('mode') not in ('guided','full'):
            p.append('adoptionWorkflow.mode must be guided or full.')
        else:
            for i,stage in enumerate(arr(workflow.get('stages'))):
                if not isinstance(stage,dict) or not stage.get('name') or not stage.get('status'):
                    p.append(f'adoptionWorkflow.stages[{i}] needs name and status.')
    gate=d.get('ownershipGate')
    if gate is not None:
        if not isinstance(gate,dict) or gate.get('status') not in ('ready','blocked'): p.append('ownershipGate.status must be ready or blocked.')
        elif gate.get('status') == 'blocked' and gate.get('deterministicChecksBlocked') is not True: p.append('A blocked ownership gate must mark deterministicChecksBlocked true.')
        for i,rule in enumerate(arr(gate.get('ownershipDependentRules'))):
            if not re.match(r'^ACIMA-[A-Z][0-9]{3}$',str(rule)): p.append(f'ownershipGate.ownershipDependentRules[{i}] must be a catalog rule ID.')
    if d.get('schemaVersion') == '1.1':
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
