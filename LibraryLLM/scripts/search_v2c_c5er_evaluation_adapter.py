"""Versioned strict scalar mask adapter; never invokes a parser.

Only established norm() and formats-only BOTH normalization. Schema aliases
are reconciled independently of predictions; conflicting masks are errors.
Structured semantic/advisory assertions have no string equivalence adapter.
"""
from copy import deepcopy
from scripts.search_v2c_c5c_score import OPERANDS,LISTS,rate,KINDS,summarize
from scripts.search_v2c_c_evaluate import norm
from scripts.search_v2c_c4_evaluate import normalize_both

APPLICABLE={'APPLICABLE','APPLICABLE_ABSENCE','PARTIALLY_APPLICABLE'}
STATES=APPLICABLE|{'UNRESOLVED','N/A','NOT_APPLICABLE','UNAVAILABLE_OUTPUT_ORACLE_ADAPTER','INAPPLICABLE'}
def mask_for(g,field):
    masks=g['metric_applicability'];choices=[masks[k] for k in [field,'hard_constraints.'+field] if k in masks]
    other=g.get('expected_hard_field_masks',{}).get(field)
    if other is not None:choices.append(other)
    if not choices:return {'status':'N/A','reason':'No independently reviewed scalar oracle.'}
    assert all(isinstance(m,dict) and m.get('status') in STATES for m in choices),(g['case_id'],field,'invalid mask')
    assert len({m['status'] for m in choices})==1,(g['case_id'],field,'conflicting mask namespaces')
    resolved=[m['resolved_value'] for m in choices if 'resolved_value' in m]
    assert not resolved or all(norm(v)==norm(resolved[0]) for v in resolved),(g['case_id'],field,'conflicting resolved values')
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
    return True

def score(g,p):
    check_gold(g);a=normalize_both(deepcopy(p.get('actual_plan',{})));hard=normalize_both(deepcopy(g['expected_hard_constraints']))
    decision=p.get('typed_decision',p.get('decision'));execution=p.get('executable',p.get('execution'))
    valid=decision in KINDS and type(execution) is bool and bool(a)
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
        if sortmask.get('status') in APPLICABLE and sort in ['RELEVANCE','RATING','NEWEST','TITLE']:compare('sort',sort,a.get('sort'),sortmask)
    if decision!=g['expected_typed_decision']:mismatches['decision']={'expected':g['expected_typed_decision'],'actual':decision}
    if execution is not g['expected_executable']:mismatches['execution_allowed']={'expected':g['expected_executable'],'actual':execution}
    if not valid:mismatches['invalid_output']={'status':p.get('status'),'error':p.get('error')}
    critical=[x['field'] for x in assertions if not x['correct'] and x['field'] in OPERANDS and not x['field'].endswith('_exclusive')] if execution is True else []
    return {'case_id':g['case_id'],'scope':g['scope_type'],'stratum':g['decision_stratum'],'shared_semantic_pattern_id':g.get('shared_semantic_pattern_id'),
        'valid_output':valid,'expected_decision':g['expected_typed_decision'],'decision':decision,'expected_execution':g['expected_executable'],'execution':execution,
        'typed_correct':decision==g['expected_typed_decision'],'execution_correct':execution is g['expected_executable'],'policy':p.get('assessment',{}).get('policy'),
        'assertions':assertions,'scoring_excluded_fields':excluded,'mismatches':mismatches,'all_scored_dimensions_correct':valid and not mismatches,
        'critical_executed_operand_mismatches':critical,'structured_advisory_accuracy':'N/A; no native representation equivalence adapter'}
