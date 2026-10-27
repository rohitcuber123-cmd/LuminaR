"""Inspectable categorical Search evidence; never a probability or plan editor.

Typed safety decisions remain authoritative. This module performs no IO, model
calls, vocabulary lookups, authorization, or session mutation. Internal evidence
is used for evaluation; public interpretation exposes only the policy label.
"""
from copy import deepcopy

POLICIES={'AMBIGUOUS':'CLARIFY','INCOMPLETE':'CLARIFY','UNSUPPORTED':'UNSUPPORTED','CONTRADICTORY':'REJECT_CONTRADICTION'}
SLOTS={'subject':('subjects',('subject',)), 'author':('author_text',('author',)),
 'title_entity':('title_text',('title','exact_text')), 'rating_operator':('rating_min',('rating',)),
 'year_operator':('year_min',('year',)), 'format':('formats',('format','excluded_format')),
 'availability':('availability',('availability',)), 'negative_constraint':('exclude_terms',('exclude','excluded_subject')),
 'semantic_remainder':('semantic_text',()), 'correction_candidate':('corrections',())}

def execution_policy(plan):
    kind=plan.decision.get('decision_type','EXECUTABLE')
    if kind in POLICIES:return POLICIES[kind]
    repairs=bool(plan.corrections) or any(c.get('repair_provenance') for c in plan.constraint_candidates)
    return 'EXECUTE_WITH_NOTICE' if kind=='EXECUTABLE_WITH_NOTICE' or repairs or plan.unknown_subject else 'AUTO_EXECUTE'

def assess(plan):
    kind=plan.decision.get('decision_type','EXECUTABLE')
    slots={}
    for slot,(attribute,fields) in SLOTS.items():
        value=getattr(plan,attribute,None)
        if slot in ('rating_operator','year_operator'):
            prefix=slot.split('_')[0];value=getattr(plan,prefix+'_min') is not None or getattr(plan,prefix+'_max') is not None
        if slot=='title_entity':value=plan.title_text or plan.exact_text
        evidence=[{k:c.get(k) for k in ('field','operator','source_span_start','source_span_end','source_text','source_query','recognizer_id','support_status','repair_provenance')} for c in plan.constraint_candidates if c.get('field') in fields]
        if slot=='semantic_remainder':
            evidence=[deepcopy(s) for s in plan.source_spans if s.get('kind')=='SEMANTIC_TOPIC']
        unresolved=kind not in ('EXECUTABLE','EXECUTABLE_WITH_NOTICE') and any(f in plan.decision.get('affected_fields',[]) for f in fields)
        bucket='UNRESOLVED' if unresolved else 'ABSENT' if not value else 'REPAIRED' if slot=='correction_candidate' or slot=='subject' and plan.corrections else 'SOURCE_BACKED' if evidence else 'LITERAL_OR_SEMANTIC'
        slots[slot]={'recognized':bool(value),'unresolved':unresolved,'source_evidence':evidence,
                     'support_status':'UNSUPPORTED' if any(e.get('support_status')=='UNSUPPORTED' for e in evidence) else 'UNRESOLVED' if unresolved else 'SUPPORTED' if value else 'ABSENT',
                     'calibration_bucket':bucket}
    repairs=any(c.get('repair_provenance') for c in plan.constraint_candidates) or bool(plan.corrections)
    policy=execution_policy(plan)
    return {'policy':policy,'typed_decision':kind,'slots':slots,'repair_certainty':'DETERMINISTIC_REPAIR' if repairs else 'NO_REPAIR',
            'plan_risk':'BLOCKED_BY_TYPED_DECISION' if kind in POLICIES else 'VISIBLE_REPAIR' if repairs else 'NO_RECOGNIZED_SAFETY_FLAG',
            'bucket':kind if kind in POLICIES else 'REPAIRED_EXECUTABLE' if repairs else 'PLAIN_EXECUTABLE',
            'score_kind':'categorical heuristic evidence; not probability'}
