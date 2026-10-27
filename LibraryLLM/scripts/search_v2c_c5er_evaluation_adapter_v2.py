"""Versioned strict scalar mask adapter; never invokes a parser.

Only established norm() and formats-only BOTH normalization. Schema aliases
are reconciled independently of predictions; conflicting masks are errors.
Structured semantic/advisory assertions have no string equivalence adapter.
"""
from copy import deepcopy
import math
from scripts.search_v2c_c5c_score import OPERANDS,LISTS,rate,KINDS,summarize
from scripts.search_v2c_c_evaluate import norm
from scripts.search_v2c_c4_evaluate import normalize_both

APPLICABLE={'APPLICABLE','APPLICABLE_ABSENCE','PARTIALLY_APPLICABLE'}
STATES=APPLICABLE|{'UNRESOLVED','N/A','NOT_APPLICABLE','UNAVAILABLE_OUTPUT_ORACLE_ADAPTER','INAPPLICABLE'}
def mask_for(g,field):
    masks=g['metric_applicability'];choices=[masks[k] for k in [field,'hard_constraints.'+field] if k in masks]
    additional=g.get('expected_hard_field_masks',{})
    assert isinstance(additional,dict),(g['case_id'],'invalid field mask map')
    if field in additional:choices.append(additional[field])
    if not choices:return {'status':'N/A','reason':'No independently reviewed scalar oracle.'}
    assert all(isinstance(m,dict) and m.get('status') in STATES for m in choices),(g['case_id'],field,'invalid mask')
    assert len({m['status'] for m in choices})==1,(g['case_id'],field,'conflicting mask namespaces')
    resolved=[m['resolved_value'] for m in choices if 'resolved_value' in m]
    canonical=lambda v:normalize_both({'formats':v})['formats'] if field=='formats' else v
    assert not resolved or all(norm(canonical(v))==norm(canonical(resolved[0])) for v in resolved),(g['case_id'],field,'conflicting resolved values')
    return next((m for m in choices if 'resolved_value' in m),choices[0])

def check_gold(g):
    assert g['expected_typed_decision'] in KINDS and type(g['expected_executable']) is bool
    assert g['expected_executable']==(g['expected_typed_decision'] in ['EXECUTABLE','EXECUTABLE_WITH_NOTICE'])
    hard=g['expected_hard_constraints']
    for f in OPERANDS:
        m=mask_for(g,f)
        if m['status'] in ['APPLICABLE','PARTIALLY_APPLICABLE']:assert f in hard or 'resolved_value' in m,(g['case_id'],f,'missing gold operand')
        if m['status']=='PARTIALLY_APPLICABLE':assert f in LISTS and isinstance(m.get('resolved_value',hard.get(f)),list)
        if m['status']=='UNRESOLVED':assert 'resolved_value' not in m,(g['case_id'],f,'unknown cannot supply scalar oracle')
    for f in ['sort','semantic_remainder']:
        m=g['metric_applicability'].get(f,{'status':'N/A'})
        assert isinstance(m,dict) and m.get('status') in STATES
        assert m['status']!='PARTIALLY_APPLICABLE',(g['case_id'],f,'partial list rule cannot apply to scalar')
        if m['status']=='UNRESOLVED':assert 'resolved_value' not in m,(g['case_id'],f,'unknown cannot supply scalar oracle')
        if f=='sort' and m['status']=='APPLICABLE_ABSENCE':assert g.get('expected_sort') in [None,'RELEVANCE'],(g['case_id'],'absent sort cannot supply requested ordering')
    return True

def score(g,p):
    check_gold(g)
    p=p if isinstance(p,dict) else {}
    raw=p.get('actual_plan');assessment=p.get('assessment',{})
    schema=isinstance(raw,dict) and bool(raw) and isinstance(assessment,dict)
    if schema:
        for field,value in raw.items():
            if field in LISTS and (not isinstance(value,list) or not all(isinstance(v,str) for v in value)):schema=False
            elif field.endswith('_exclusive') and field in OPERANDS and type(value) is not bool:schema=False
            elif field in ['rating_min','rating_max','year_min','year_max'] and value is not None and (type(value) not in [int,float] or not math.isfinite(value)):schema=False
            elif field in ['author_text','title_text','exact_text','availability','language','semantic_text'] and value is not None and not isinstance(value,str):schema=False
    a=normalize_both(deepcopy(raw)) if schema else {}
    hard=normalize_both(deepcopy(g['expected_hard_constraints']))
    decision=p.get('typed_decision',p.get('decision'));execution=p.get('executable',p.get('execution'))
    valid=schema and decision in KINDS and type(execution) is bool
    assertions=[];excluded={};mismatches={}
    def compare(field,wanted,got,mask,partial=False):
        good=set(norm(wanted)).issubset(set(norm(got))) if partial and isinstance(wanted,list) and isinstance(got,list) else norm(wanted)==norm(got)
        assertions.append({'field':field,'expected':wanted,'actual':got,'correct':good,'mask':mask,'partial':partial})
        if not good:mismatches[field]={'expected':wanted,'actual':got,'mask':mask}
    if valid:
        for field in sorted(OPERANDS):
            mask=mask_for(g,field);state=mask['status']
            if state not in APPLICABLE:excluded[field]=mask;continue
            wanted=([] if field in LISTS else False if field.endswith('_exclusive') else None) if state=='APPLICABLE_ABSENCE' else mask.get('resolved_value',hard.get(field))
            # BOTH applies to formats only, including a resolved_value list.
            if field=='formats':wanted=normalize_both({'formats':wanted})['formats']
            compare(field,wanted,a.get(field),mask,state=='PARTIALLY_APPLICABLE')
        semantic=g.get('expected_semantic_remainder');sm=g['metric_applicability'].get('semantic_remainder',{'status':'N/A'})
        if isinstance(semantic,str) and sm.get('status')=='APPLICABLE':compare('semantic_text',semantic,a.get('semantic_text') or '',sm)
        elif sm.get('status')=='APPLICABLE_ABSENCE':compare('semantic_text','',a.get('semantic_text') or '',sm)
        else:excluded['semantic_text']={'status':'N/A','frozen_mask':sm,'reason':'No definite literal scalar topic oracle; structured semantics not equated with a string.'}
        sort=g.get('expected_sort');sortmask=g['metric_applicability'].get('sort',{'status':'N/A'})
        if sortmask.get('status')=='APPLICABLE_ABSENCE':compare('sort','RELEVANCE',a.get('sort'),sortmask)
        elif sortmask.get('status')=='APPLICABLE' and sort in ['RELEVANCE','RATING','NEWEST','TITLE']:compare('sort',sort,a.get('sort'),sortmask)
    if decision!=g['expected_typed_decision']:mismatches['decision']={'expected':g['expected_typed_decision'],'actual':decision}
    if execution is not g['expected_executable']:mismatches['execution_allowed']={'expected':g['expected_executable'],'actual':execution}
    if not valid:mismatches['invalid_output']={'status':p.get('status'),'error':p.get('error')}
    critical=[x['field'] for x in assertions if not x['correct'] and x['field'] in OPERANDS ] if execution is True else []
    return {'case_id':g['case_id'],'scope':g['scope_type'],'stratum':g['decision_stratum'],'shared_semantic_pattern_id':g.get('shared_semantic_pattern_id'),
        'valid_output':valid,'expected_decision':g['expected_typed_decision'],'decision':decision,'expected_execution':g['expected_executable'],'execution':execution,
        'typed_correct':valid and decision==g['expected_typed_decision'],'execution_correct':valid and execution is g['expected_executable'],'policy':assessment.get('policy') if isinstance(assessment,dict) else None,
        'assertions':assertions,'scoring_excluded_fields':excluded,'mismatches':mismatches,'all_scored_dimensions_correct':valid and not mismatches,
        'critical_executed_operand_mismatches':critical,'structured_advisory_accuracy':'N/A; no native representation equivalence adapter'}

def summary(scored):
    """All gold remains in denominators, including invalid/missing output."""
    positive=[r for r in scored if r['expected_execution'] is True]
    blocked=[r for r in scored if r['expected_execution'] is False]
    false=[r for r in blocked if r['execution'] is True]
    missed=[r for r in positive if not r['valid_output'] or r['execution'] is not True]
    invalid=[r for r in scored if not r['valid_output']]
    return {'contexts':len(scored),'valid_outputs':len(scored)-len(invalid),'invalid_outputs':len(invalid),
        'typed_accuracy':rate(sum(r['typed_correct'] for r in scored),len(scored)),
        'execution_accuracy':rate(sum(r['execution_correct'] for r in scored),len(scored)),
        'false_execution':rate(len(false),len(blocked)),'missed_execution':rate(len(missed),len(positive)),
        'false_execution_ids':[r['case_id'] for r in false],'missed_execution_ids':[r['case_id'] for r in missed],
        'per_kind_recall':{k:rate(sum(r['typed_correct'] for r in scored if r['expected_decision']==k),sum(r['expected_decision']==k for r in scored)) for k in KINDS},
        'strict_scored_fields':rate(sum(r['all_scored_dimensions_correct'] for r in scored),len(scored)),
        'critical_executed_operand_case_ids':[r['case_id'] for r in scored if r['critical_executed_operand_mismatches']],
        'invalid_gold_blocked_outputs_never_get_safe_block_credit':True}
