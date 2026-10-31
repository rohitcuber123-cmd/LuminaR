"""Disabled compositional ownership layer over the verified native QueryPlan.

The frozen V4 grammar is a shared compatibility dependency, not copied code.
Only source-owned field families are recomposed; unrelated native controls,
literal modes, predicates and the C4 assessment are retained.
"""
from copy import deepcopy
from dataclasses import asdict
import re
from scratch.search_v2c_c5er.candidate_search_v4 import query_plan as native
from scratch.search_v2c_c5er.candidate_search_v4 import query_confidence as decisions
from scratch.search_v2c_c5er.candidate_search_v4.query_session import explicit_filters,omit_fields
from scratch.search_v2c_c5er.candidate_search_v4.semantic_safety import prepare
from scratch.search_v2c_c5er.candidate_search_v4.requirement_ledger import clauses
from .query_ir import understand,Requirement,FAMILIES

PARSER_VERSION='search-smarteng-disabled-compositional-1'
QueryPlan=native.QueryPlan
FacetVocabulary=native.FacetVocabulary
normalize=native.normalize
matches=native.matches
sort_books=native.sort_books
executable=decisions.executable
decide=decisions.decide
assess=__import__('scratch.search_v2c_c5er.candidate_search_v4.query_calibration',fromlist=['assess']).assess
FRAME=set('the a an and but then while both at same time in sense moment require requires required must be is are with without find show search use keep entries entry works work books book hits hit its each for every carry include exclude by of on only access simultaneously'.split())

def __getattr__(name):return getattr(native,name)

def validate(plan,capabilities=None):
    # Capability limitations cannot erase an already explained unresolved
    # mandatory relationship. Contradiction checks still run first.
    prior=deepcopy(plan.decision)
    checked=decisions.validate(plan,capabilities)
    if prior.get('decision_type') in ['AMBIGUOUS','INCOMPLETE','CONTRADICTORY'] and checked.decision.get('reason_code','').startswith('SCOPE_'):
        checked.decision=prior
    return checked

def _apply(plan,items,changed):
    for family in changed:
        for name in FAMILIES.get(family,[]):
            setattr(plan,name,[] if isinstance(getattr(plan,name),list) else False if isinstance(getattr(plan,name),bool) else 'RELEVANCE' if name=='sort' else None)
    for c in items:
        f,op,v=c.field,c.operator,c.normalized_value
        if f not in changed or c.support_status!='SUPPORTED':continue
        if f in ['rating','year']:
            bounds=[('min',v[0],False),('max',v[1],False)] if op=='RANGE' else [('min',v,False),('max',v,False)] if op=='=' else [('min' if op in ['>','>='] else 'max',v,op in ['>','<'])]
            for side,value,exclusive in bounds:
                key=f+'_'+side;old=getattr(plan,key)
                if old is None or (value>old if side=='min' else value<old):setattr(plan,key,value);setattr(plan,key+'_exclusive',exclusive)
                elif value==old:setattr(plan,key+'_exclusive',getattr(plan,key+'_exclusive') or exclusive)
        elif f=='subject':plan.subjects.append(v);plan.include_terms.append(v)
        elif f=='excluded_subject':plan.exclude_subjects.append(v)
        elif f=='exclude':
            if op=='TEXT_NOT':plan.exclude_terms.append(v)
            else:
                for term in re.split(r'\s*(?:,|\band\b|\bor\b)\s*',str(v)):
                    if term.strip():plan.exclude_terms.append(term.strip())
        elif f=='format':
            plan.formats.append(v)
            if op=='ONLY':plan.exclusive_formats.append(v)
        elif f=='excluded_format':plan.excluded_formats.append(v)
        elif f=='author':plan.author_text=v
        elif f=='title':plan.title_text=v
        elif f=='sort':plan.sort=v
        elif f=='availability':
            plan.availability='AVAILABLE_NOW' if v=='PHYSICAL_NOW' else 'REQUESTABLE' if v=='PHYSICAL_REQUESTABLE' else v
            if v in ['PHYSICAL_NOW','PHYSICAL_REQUESTABLE']:plan.physical_available_only=True
        elif f=='language':plan.language=v
    for key in ['subjects','include_terms','exclude_terms','exclude_subjects','formats','exclusive_formats','excluded_formats']:
        setattr(plan,key,list(dict.fromkeys(getattr(plan,key))))

def parse_query(query,facets=(),mode='SMART',filters=None,omit=()):
    base=native.parse_query(query,facets,mode,filters,omit)
    if mode!='SMART' or base.exact_text:
        base.parser_version=PARSER_VERSION;base.decision['parser_version']=PARSER_VERSION;return base
    original=str(query);prepared,grammar_repairs,offsets=prepare(original)
    ir=understand(prepared,facets);s=ir.source;plan=deepcopy(base)
    # Negative membership and broad text are separate families; a new explicit
    # owner supersedes the old broad fallback in both directions.
    if ir.changed_families & {'excluded_subject','exclude'}:ir.changed_families.update(['exclude','excluded_subject'])
    _apply(plan,s.items,ir.changed_families)
    # Keep only actual mandated fields; explicit UI/API edits remain trusted.
    explicit_filters(plan,filters or {});omit_fields(plan,omit)
    plan.parser_version=PARSER_VERSION
    # Build one explanation IR with exact original-query coordinates.
    requirements=[]
    def original_span(a,b):
        return [offsets[a] if a<len(offsets) else len(original),offsets[b-1]+1 if b and b-1<len(offsets) else len(original)]
    for c in s.items:
        if c.field=='connector':continue
        a,b=original_span(c.source_span_start,c.source_span_end)
        owner=next(([x,y] for x,y,_ in clauses(original) if x<=a<y),[a,b])
        requirements.append(Requirement(c.field,c.operator,c.normalized_value,[a,b],owner,
            'ADVISORY' if c.field=='preference' else 'RESOLVED' if c.support_status=='SUPPORTED' else c.support_status,
            'ADVISORY' if c.field=='preference' else 'MANDATORY',c.representation or 'HARD_FILTER',{'recognizer':c.recognizer_id}))
    for r in ir.evidence:
        r.source_span=original_span(*r.source_span);r.owning_clause_span=original_span(*r.owning_clause_span);requirements.append(r)
        if r.field=='relationship' and isinstance(r.value,dict):
            for family in r.value.get('fields',[]):
                requirements.append(Requirement(family,'UNRESOLVED_RELATIONSHIP',None,list(r.source_span),list(r.owning_clause_span),r.status,representation='RELATIONSHIP',provenance={'relationship_owner':r.source_span}))
    # Source residue is semantic unless it is solely a recognized grammatical
    # frame. Unknown REQUIRED content is retained and safely blocked below.
    remainder=s.remaining(protect=False)
    residue_parts=[];uncovered=[]
    for a,b,t in clauses(remainder):
        words=normalize(t).split()
        if not words or all(w in FRAME for w in words):continue
        residue_parts.append(t.strip(' ,;:.'))
        raw=prepared[a:b]
        if re.search(r'\b(?:require|requires|must\s+be|strict\s+condition|mandatory)\b',raw,re.I):uncovered.append([a,b,t])
    topic=[c.normalized_value for c in s.items if c.field=='semantic']
    if ir.changed_families or any(c.field in ['semantic','preference'] for c in s.items):
        remainder='; '.join([*topic,*residue_parts])
        # Parse only soft legacy intent/facet fallback; no structured grammar.
        soft=native._parse_legacy(remainder,facets,'SMART',recognize_constraints=False)
        plan.semantic_text=soft.semantic_text
        if not plan.semantic_text and soft.subjects and remainder.strip() and not base.subjects:plan.semantic_text=remainder.strip(' ,;:.')
        if topic:plan.semantic_text='; '.join([*topic,*(residue_parts or [])])
        advice=[c.normalized_value for c in s.items if c.field=='preference']
        if advice:
            plan.soft_preference='; '.join(dict.fromkeys(advice))
            if re.search(r'beginner|introduct|easy',plan.soft_preference,re.I):plan.intent='LEARN'
            elif re.search(r'advanced|research',plan.soft_preference,re.I):plan.intent='RESEARCH'
            elif re.search(r'reference',plan.soft_preference,re.I):plan.intent='REFERENCE'
    notices=list(base.decision.get('repair_notices',[]))
    for repair in ir.corrections:
        a,b=original_span(*repair['source_span']);fragment=original[a:b]
        found=re.search(re.escape(repair['from']),fragment,re.I)
        if not found:continue
        correction={k:repair[k] for k in ['from','to','kind']};correction['from']=fragment[found.start():found.end()]
        if correction not in plan.corrections:plan.corrections.append(correction)
        item={**correction,'source_span':[a+found.start(),a+found.end()]}
        if item not in notices:notices.append(item)
    plan.constraint_candidates=[]
    for c in s.items:
        item=asdict(c);a,b=original_span(c.source_span_start,c.source_span_end)
        item.update(source_span_start=a,source_span_end=b,source_text=original[a:b],source_query=original)
        edits=[r for r in grammar_repairs if a<r['end'] and b>r['start']]
        if edits:item['repair_provenance']={'kind':'bounded_grammar_repair','edits':[{k:r[k] for k in ['from','to','start','end']} for r in edits]}
        plan.constraint_candidates.append(item)
    plan.source_spans=[{'kind':'STRUCTURED_CONSTRAINT','start':r.source_span[0],'end':r.source_span[1],'text':original[slice(*r.source_span)],'source_query':original} for r in requirements]
    # One decision composition: contradiction > missing > unresolved > unsupported.
    decisions.decide(plan,'EXECUTABLE','COMPOSITION_VALIDATED')
    decisions.validate(plan)
    priority=next((k for k in ['CONTRADICTORY','INCOMPLETE','AMBIGUOUS','UNSUPPORTED'] if any(r.status==k for r in requirements)),None)
    if plan.decision.get('decision_type')!='CONTRADICTORY' and priority:
        selected=[r for r in requirements if r.status==priority]
        decisions.decide(plan,priority,'REQUIREMENT_'+priority,fields=sorted({r.field for r in selected}),unresolved=[{'field':r.field,'source_span':r.source_span,'text':original[slice(*r.source_span)]} for r in selected])
    elif plan.decision.get('decision_type')=='EXECUTABLE':
        old=base.decision;kind=old.get('decision_type');reason=old.get('reason_code','')
        correctable=reason in ['MANDATORY_UNSUPPORTED','UNSUPPORTED_STRICT_FIELD','MISSING_SUBJECT_CLAUSE_VALUE'] and bool(ir.changed_families) and not uncovered
        correctable|=reason=='MISSING_CONSTRAINT_VALUE' and 'sort' in ir.changed_families and not uncovered
        correctable|=reason.startswith('SCOPE_') and bool(ir.changed_families)
        if kind in ['AMBIGUOUS','INCOMPLETE','UNSUPPORTED','CONTRADICTORY'] and not correctable:
            decisions.decide(plan,kind,reason,fields=old.get('affected_fields',[]),unresolved=old.get('unresolved_fragments',[]))
            for r in old.get('requirements',[]):
                if r.get('status') in ['AMBIGUOUS','INCOMPLETE','UNSUPPORTED','CONTRADICTORY']:
                    a,b=r.get('source_span',[0,len(original)]);owner=next(([x,y] for x,y,_ in clauses(original) if x<=a<y),[a,b])
                    requirements.append(Requirement(r['field'],'LEGACY_EVIDENCE',r.get('value'),[a,b],owner,r['status'],provenance={'compatibility_reason':r.get('reason')}))
        elif uncovered:decisions.decide(plan,'UNSUPPORTED','UNREPRESENTED_MANDATORY_OPERATION',fields=['requirement'],unresolved=[{'text':t,'source_span':original_span(a,b)} for a,b,t in uncovered])
        elif notices:decisions.decide(plan,'EXECUTABLE_WITH_NOTICE','SOURCE_OWNED_REPAIR')
    plan.raw_query=original;plan.normalized_query=normalize(original)
    ledger=[]
    unresolved_fields={r.field for r in requirements if r.status in ['AMBIGUOUS','INCOMPLETE','UNSUPPORTED']}
    for r in requirements:
        if r.status=='RESOLVED' and r.field in unresolved_fields:r.status='UNRESOLVED_RELATIONSHIP'
        d=asdict(r);d.update(source_text=original[slice(*r.source_span)],owning_clause=original[slice(*r.owning_clause_span)])
        ledger.append(d)
    plan.decision.update(requirements=ledger,repair_notices=notices,query_ir={'version':1,'objective':plan.intent,'trusted_scope_from_text':False,
        'changed_field_families':sorted(ir.changed_families),'semantic_representation':plan.semantic_text,'advisory_representation':plan.soft_preference},
        parser_version=PARSER_VERSION,development_isolation={'disabled_candidate':True,'confidence_is_probability':False})
    return plan
