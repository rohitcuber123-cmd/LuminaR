"""Typed decisions and consistency validation; confidence is not probability."""
from dataclasses import asdict
import re
from scratch.search_v2c_c5er.candidate_search_v3.query_numeric import range_contradiction,valid_numeric_domain

EXECUTABLE=('EXECUTABLE','EXECUTABLE_WITH_NOTICE')
MESSAGES={'AMBIGUOUS':'This query could mean more than one thing. Add the field you mean, or use Exact mode for a literal search.',
 'INCOMPLETE':'A search constraint is unfinished. Complete it and search again.',
 'CONTRADICTORY':'These search filters conflict. Edit the query or remove a conflicting filter.',
 'UNSUPPORTED':'This search requests a strict field that this catalogue cannot enforce. Edit that constraint and try again.'}

def decide(plan,kind='EXECUTABLE',reason='VALIDATED',spans=(),fields=(),unresolved=()):
    retained={key:plan.decision[key] for key in ['requirements','repair_notices','development_isolation'] if key in plan.decision}
    plan.decision={'decision_type':kind,'reason_code':reason,'relevant_source_spans':list(spans),
      'affected_fields':list(fields),'recognized_candidates':plan.constraint_candidates,
      'unresolved_fragments':list(unresolved),'safe_public_message':MESSAGES.get(kind,''),'parser_version':plan.parser_version}
    plan.decision.update(retained)
    if kind not in EXECUTABLE:plan.interpretation_confidence=0.
    return plan

def validate(plan,capabilities=None):
    # Revalidate composed session/control edits too; never broaden on conflict.
    for field in ('rating','year'):
        low,high=getattr(plan,field+'_min'),getattr(plan,field+'_max')
        if range_contradiction(low,high,getattr(plan,field+'_min_exclusive'),getattr(plan,field+'_max_exclusive')):
            return decide(plan,'CONTRADICTORY','INCOMPATIBLE_'+field.upper()+'_BOUNDS',fields=[field])
        if any(v is not None and not valid_numeric_domain(field,v) for v in (low,high)):
            return decide(plan,'UNSUPPORTED','OUT_OF_RANGE_'+field.upper(),fields=[field])
        # A strict boundary at the end of the supported scale has no valid
        # value, even though the operand itself belongs to the scale.
        minimum,maximum=(0,5) if field=='rating' else (1000,2100)
        if low==maximum and getattr(plan,field+'_min_exclusive') or high==minimum and getattr(plan,field+'_max_exclusive'):
            return decide(plan,'UNSUPPORTED','EMPTY_SUPPORTED_'+field.upper()+'_DOMAIN',fields=[field])
    if len(set(plan.exclusive_formats))>1:
        return decide(plan,'CONTRADICTORY','EXCLUSIVE_FORMATS',fields=['format'])
    positives={f for f in plan.formats if f!='BOTH'}|({'ONLINE','PHYSICAL'} if 'BOTH' in plan.formats else set())
    if plan.exclusive_formats and positives-set(plan.exclusive_formats):
        return decide(plan,'CONTRADICTORY','EXCLUSIVE_FORMAT_REQUIREMENT',fields=['format'])
    if positives & set(plan.excluded_formats):return decide(plan,'CONTRADICTORY','FORMAT_INCLUDE_EXCLUDE',fields=['format'])
    from scratch.search_v2c_c5er.candidate_search_v3.query_plan import normalize
    if set(map(normalize,plan.subjects)) & set(map(normalize,plan.exclude_subjects)):
        return decide(plan,'CONTRADICTORY','SUBJECT_INCLUDE_EXCLUDE',fields=['subject'],
                      spans=[{'start':c['source_span_start'],'end':c['source_span_end'],
                              'source_query':c.get('source_query',plan.raw_query)}
                             for c in plan.constraint_candidates if c['field'] in ('subject','excluded_subject','exclude')])
    if capabilities:
        for requirement in plan.decision.get('requirements',[]):
            field=requirement['field'];family='year' if field.startswith('year') else field
            if family in capabilities and capabilities[family] is False:
                requirement['enforcement']='CONTEXTUALLY_INAPPLICABLE'
                requirement['scope_reason']='This catalogue cannot enforce the requested field; mandatory requests remain unsupported.'
        allowed=capabilities.get('formats')
        if allowed is not None and any(f not in allowed for f in plan.formats):
            return decide(plan,'UNSUPPORTED','SCOPE_FORMAT_UNSUPPORTED',fields=['format'])
        for key in ('year','language','availability'):
            present=(plan.year_min is not None or plan.year_max is not None) if key=='year' else bool(getattr(plan,key))
            if present and capabilities.get(key) is False:return decide(plan,'UNSUPPORTED','SCOPE_'+key.upper()+'_UNSUPPORTED',fields=[key])
    return plan

def executable(plan):return plan.decision.get('decision_type','EXECUTABLE') in EXECUTABLE

