"""C5D offline-only guards over already captured plans. No query recognizer.

Not imported by production. No IO, gold, context ID, query-text or score access.
All recommendations restrict the supplied baseline; none authorizes execution.
"""
import math
import unicodedata

CANDIDATES=('A_BASELINE','B_CANDIDATE_OPERAND_GUARD','C_PARSED_CONSISTENCY_GUARD','D_SUPPORTED_OUTPUT_GUARD','E_COMPOSED_GUARD')

def norm(value):return ' '.join(unicodedata.normalize('NFKC',str(value or '')).casefold().split())
def expanded(values):return {v for x in values for v in (['ONLINE','PHYSICAL'] if x=='BOTH' else [x])}

def numeric_entails(plan,field,operator,value):
    lo,hi=plan.get(field+'_min'),plan.get(field+'_max')
    le,he=plan.get(field+'_min_exclusive',False),plan.get(field+'_max_exclusive',False)
    if operator=='RANGE':return isinstance(value,list) and len(value)==2 and lo is not None and hi is not None and lo>=value[0] and hi<=value[1]
    if not isinstance(value,(int,float)) or isinstance(value,bool) or not math.isfinite(value):return False
    if operator=='=':return lo==hi==value and not le and not he
    if operator=='>':return lo is not None and (lo>value or lo==value and le)
    if operator=='>=':return lo is not None and lo>=value
    if operator=='<':return hi is not None and (hi<value or hi==value and he)
    if operator=='<=':return hi is not None and hi<=value
    return None

def operand_reasons(plan):
    reasons=[]
    for c in plan.get('constraint_candidates',[]):
        if c.get('support_status')!='SUPPORTED':continue
        field,value,op=c.get('field'),c.get('normalized_value'),c.get('operator')
        good=None
        if field in ['rating','year']:good=numeric_entails(plan,field,op,value)
        elif field in ['author','title','language']:good=norm(plan.get({'author':'author_text','title':'title_text','language':'language'}[field]))==norm(value)
        elif field in ['subject','excluded_subject']:good=norm(value) in {norm(v) for v in plan.get('subjects' if field=='subject' else 'exclude_subjects',[])}
        elif field=='format':good=expanded([value]).issubset(expanded(plan.get('formats',[]))) and (op!='ONLY' or value in plan.get('exclusive_formats',[]))
        elif field=='excluded_format':good=value in plan.get('excluded_formats',[])
        elif field=='availability':
            target={'PHYSICAL_NOW':'AVAILABLE_NOW','PHYSICAL_REQUESTABLE':'REQUESTABLE'}.get(value,value)
            good=plan.get('availability')==target and (value not in ['PHYSICAL_NOW','PHYSICAL_REQUESTABLE'] or plan.get('physical_available_only') is True)
        if good is False:reasons.append({'code':'RECOGNIZED_OPERAND_NOT_PRESERVED','field':field,'recognizer_id':c.get('recognizer_id'),'source_span':[c.get('source_span_start'),c.get('source_span_end')]})
    return reasons

def consistency_reasons(plan):
    reasons=[]
    if any(c.get('support_status') in ['AMBIGUOUS','INCOMPLETE','UNSUPPORTED'] for c in plan.get('constraint_candidates',[])):
        reasons.append({'code':'PARSED_UNRESOLVED_OR_UNSUPPORTED_CANDIDATE'})
    if plan.get('decision',{}).get('unresolved_fragments'):reasons.append({'code':'PARSED_UNRESOLVED_FRAGMENT'})
    for field in ['rating','year']:
        lo,hi=plan.get(field+'_min'),plan.get(field+'_max')
        if lo is not None and hi is not None and (lo>hi or lo==hi and (plan.get(field+'_min_exclusive') or plan.get(field+'_max_exclusive'))):
            reasons.append({'code':'PARSED_NUMERIC_CONTRADICTION','field':field})
    positive=expanded(plan.get('formats',[]));exclusive=set(plan.get('exclusive_formats',[]))
    if len(exclusive)>1 or exclusive and positive-exclusive or positive & set(plan.get('excluded_formats',[])):
        reasons.append({'code':'PARSED_FORMAT_CONTRADICTION'})
    if {norm(x) for x in plan.get('subjects',[])} & {norm(x) for x in plan.get('exclude_subjects',[])}:
        reasons.append({'code':'PARSED_SUBJECT_CONTRADICTION'})
    # matches() rejects broad excluded text in author/title as well as other
    # fields. Requiring that same literal there makes the conjunction empty.
    for term in plan.get('exclude_terms',[]):
        if norm(term) and any(norm(term) in norm(plan.get(field)) for field in ['title_text','author_text']):
            reasons.append({'code':'PARSED_LITERAL_INCLUDE_EXCLUDE_CONTRADICTION'})
    return reasons

def supported_reasons(plan,caps,intents,modes):
    reasons=[]
    if plan.get('intent') not in intents:reasons.append({'code':'UNKNOWN_OUTPUT_INTENT'})
    if plan.get('mode') not in modes:reasons.append({'code':'UNKNOWN_OUTPUT_MODE'})
    required_lists=['subjects','exclude_subjects','exclude_terms','formats','exclusive_formats','excluded_formats','constraint_candidates']
    if any(not isinstance(plan.get(k),list) for k in required_lists):return reasons+[{'code':'INVALID_OUTPUT_SCHEMA'}]
    for field in ['rating','year']:
        low,high=(0,5) if field=='rating' else (1000,2100)
        for side in ['min','max']:
            value=plan.get(field+'_'+side)
            if value is not None and (isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not low<=value<=high or field=='year' and int(value)!=value):
                reasons.append({'code':'INVALID_NUMERIC_OUTPUT','field':field})
    if any(v not in caps.get('formats',[]) for v in plan.get('formats',[])):reasons.append({'code':'PARSED_SCOPE_FORMAT_UNSUPPORTED'})
    for field in ['year','language','availability']:
        present=plan.get('year_min') is not None or plan.get('year_max') is not None if field=='year' else bool(plan.get(field))
        if present and caps.get(field) is False:reasons.append({'code':'PARSED_SCOPE_FIELD_UNSUPPORTED','field':field})
    return reasons

def recommend(candidate,payload):
    assert candidate in CANDIDATES
    assert set(payload)=={'plan','baseline_executable','baseline_policy','capabilities','intents','modes'}
    plan=payload['plan']
    # raw_query is intentionally stripped upstream. This module cannot consult
    # benchmark text, gold, IDs, strata, scores, reviewer evidence or rationales.
    assert 'raw_query' not in plan and 'normalized_query' not in plan
    reasons=[]
    if candidate in ['B_CANDIDATE_OPERAND_GUARD','E_COMPOSED_GUARD']:reasons+=operand_reasons(plan)
    if candidate in ['C_PARSED_CONSISTENCY_GUARD','E_COMPOSED_GUARD']:reasons+=consistency_reasons(plan)
    if candidate in ['D_SUPPORTED_OUTPUT_GUARD','E_COMPOSED_GUARD']:reasons+=supported_reasons(plan,payload['capabilities'],payload['intents'],payload['modes'])
    baseline=payload['baseline_executable']
    permit=baseline and not reasons
    return {'recommend_execution':permit,'baseline_preserved':permit==baseline,
            'action':payload['baseline_policy'] if permit==baseline else 'SHADOW_WITHHOLD_FOR_REVIEW',
            'reasons':reasons,'baseline_authority_required':True,
            'unassessable':['Unrecognized or discarded mandatory query requirements','Fresh scope/actor/transaction authorization and operation-specific live preconditions'],
            'not_a_native_clarification_issuance':True}
