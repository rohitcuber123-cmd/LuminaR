"""Disabled A interpretation -> B source obligation validation -> C planning.

Legacy language rules remain proposal producers for compatibility. Their old
coverage flag and executable decision never authorize this pipeline.
"""
from copy import deepcopy
from dataclasses import asdict
import re
from . import legacy
from .language import interpret
from .validation import audit
from .planning import project

PARSER_VERSION='search-smarteng-disabled-proof-9'
QueryPlan=legacy.QueryPlan
normalize=legacy.normalize
matches=legacy.matches
sort_books=legacy.sort_books
executable=legacy.executable
assess=legacy.assess
decide=legacy.decide
_decode=legacy._decode


def __getattr__(name):return getattr(legacy,name)


def validate(plan,capabilities=None):
    metadata={k:deepcopy(plan.decision[k]) for k in ['interpretation_contract','source_obligations','clarification_targets'] if k in plan.decision}
    result=legacy.validate(plan,capabilities)
    blob=result.decision.get('query_ir_contract')
    if blob and metadata:
        check=audit(_decode(blob));result.decision['source_obligations']=check
        if check['violations'] and result.decision['decision_type']!='CONTRADICTORY':
            kind='AMBIGUOUS' if any(x.get('decision')=='AMBIGUOUS' for x in check['violations']) else 'UNSUPPORTED'
            legacy.decide(result,kind,'V9_UNVERIFIED_SOURCE_OBLIGATION',fields=sorted({x.get('field','requirement') for x in check['violations']}))
            # decide preserves the native proof/source contract through legacy wrapper.
        metadata['source_obligations']=check
    result.decision.update(metadata)
    return result


def parse_query(query,facets=(),mode='SMART',filters=None,omit=()):
    raw=str(query)
    if len(raw)>500:raise ValueError('Search query is too long.')
    base=legacy.parse_query(raw,facets,mode,filters,omit)
    if mode!='SMART' or 'query_ir_contract' not in base.decision:return base
    ir,units,handled=interpret(raw,_decode(base.decision['query_ir_contract']))
    obligations=audit(ir)
    p=project(ir,base,PARSER_VERSION,obligations)
    targets=[dict(field=r.field,state=r.state.value,span=list(r.source_span),source_text=r.source_text,requirement_id=r.requirement_id)
             for r in ir.requirements if r.ownership=='MANDATORY' and r.state.value!='EXPLICITLY_SUPPLIED']
    targets.extend(dict(field=x.get('field','requirement'),state='UNVERIFIED_SOURCE_OBLIGATION',span=x['span'],source_text=raw[slice(*x['span'])]) for x in obligations['violations'])
    p.decision.update(interpretation_contract=dict(version=9,authority='PROPOSAL_ONLY',units=[asdict(u) for u in units],overlaid_units=handled),
                      source_obligations=obligations,clarification_targets=targets)
    return validate(p)
