"""Contract C: fresh native projection only from validated typed requirements."""
from types import SimpleNamespace
from .contract import State,encode,digest
from .ontology import FAMILIES
from .projection import _apply
from .surface import semantic_projection
from .proof import projection


def project(ir,base,version,validation):
    from .legacy import QueryPlan
    from scratch.search_v2c_c5er.candidate_search_v4.query_session import explicit_filters,omit_fields
    p=QueryPlan(ir.raw_query,base.mode);p.parser_version=version
    invalid=set(validation.get('invalid_atom_ids',[]))
    active=[r for r in ir.requirements if r.requirement_id not in invalid and r.state==State.SUPPLIED and r.support=='SUPPORTED' and r.ownership=='MANDATORY' and r.field in FAMILIES]
    unresolved={f for r in ir.requirements if r.field=='relationship' and isinstance(r.value,dict) for f in r.value.get('fields',[])}
    active=[r for r in active if r.field not in unresolved]
    _apply(p,[SimpleNamespace(field=r.field,operator=r.operator,normalized_value=r.value,support_status='SUPPORTED') for r in active],set(FAMILIES))
    explicit_filters(p,ir.trusted_controls.get('filters',{}));omit_fields(p,ir.trusted_controls.get('omit',()))
    p.semantic_text=semantic_projection(ir)
    advisory=[r.value for r in ir.requirements if r.ownership=='ADVISORY' and isinstance(r.value,str)]
    p.soft_preference='; '.join(dict.fromkeys(advisory)) or None
    p.intent='FIND_AUTHOR' if p.author_text else 'FIND_EXACT' if p.exact_text or p.title_text else 'BROWSE_CATEGORY' if p.subjects and not p.semantic_text else base.intent
    if p.soft_preference:
        import re
        if re.search(r'beginner|introduct',p.soft_preference,re.I):p.intent='LEARN'
        elif re.search(r'advanced|research',p.soft_preference,re.I):p.intent='RESEARCH'
    p.corrections=list(base.corrections);p.unknown_subject=base.unknown_subject;p.suggested_subject=base.suggested_subject
    notices=base.decision.get('repair_notices',[])
    p.constraint_candidates=list(base.constraint_candidates)
    p.source_spans=[dict(kind='STRUCTURED_CONSTRAINT',start=r.source_span[0],end=r.source_span[1],text=r.source_text,source_query=ir.raw_query) for r in ir.requirements]
    p.decision=dict(base.decision)
    p.decision.update(decision_type='EXECUTABLE_WITH_NOTICE' if notices else 'EXECUTABLE',reason_code='V9_NATIVE_PROJECTION',parser_version=version,
                      query_ir_contract=encode(ir),execution_proof=dict(projection=projection(p),IR_digest=digest(encode(ir)),violations=[]))
    return p
