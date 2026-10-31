"""Pure bound completion draft. No issuance, persistence, auth or commits."""
from dataclasses import dataclass
import re
from .contract import State,digest
from .parser import parse_query,validate,executable,PARSER_VERSION,_decode
from .proof import projection
from .proposals import FAMILIES

@dataclass(frozen=True)
class BoundContext:
    owner:str
    login_session:str
    library_id:str|None
    workspace:str
    parser_version:str
    mode:str
    query_digest:str
    base_version:int
    expires_at:float
    used:bool=False

def complete_draft(plan,requirement_id,value,issued,current,*,now,facets,capabilities,authorized=False):
    if not authorized:raise ValueError('Fresh backend authorization required')
    if issued!=current or current.used or now>=current.expires_at:raise ValueError('Stale, foreign or consumed choice')
    if current.parser_version!=PARSER_VERSION or current.mode!='SMART' or current.query_digest!=digest(plan.raw_query):raise ValueError('Query/parser binding changed')
    ir=_decode(plan.decision['query_ir_contract'])
    r=next((r for r in ir.requirements if r.requirement_id==requirement_id),None)
    if r is None or r.ownership!='MANDATORY' or r.state not in [State.EMPTY,State.OMITTED,State.PLACEHOLDER] or r.field not in FAMILIES:
        raise ValueError('No unique source-owned supported slot')
    value=str(value).strip()
    if not value or len(value)>100 or re.search(r'["“”\r\n]',value):raise ValueError('Invalid completion operand')
    a,b=r.source_span;fragment=plan.raw_query[a:b]
    marker=re.search(r'\[[^\]]*\]|<[^>]*>|\{[^}]*\}|\.{3,}|…|_{2,}|"\s*"|“\s*”',fragment)
    if marker:a,b=a+marker.start(),a+marker.end()
    elif r.state==State.OMITTED:a=b
    else:raise ValueError('Source placeholder no longer matches')
    if r.field in ['rating','year']:
        if not re.fullmatch(r'-?\d+(?:\.\d+)?',value):raise ValueError('Numeric operand required')
        replacement=value
    elif r.field=='sort':
        replacement={'TITLE':'title','RATING':'rating','NEWEST':'newest','RELEVANCE':'relevance'}.get(value.upper())
        if replacement is None:raise ValueError('Unsupported ordering criterion')
    else:replacement='"'+value+'"'
    query=plan.raw_query[:a]+(' ' if a==b else '')+replacement+plan.raw_query[b:]
    if len(query)>500:raise ValueError('Completed query exceeds parser limit')
    draft=validate(parse_query(query,facets,'SMART',ir.trusted_controls.get('filters'),ir.trusted_controls.get('omit',())),capabilities)
    if not executable(draft):raise ValueError('Remaining requirements cannot execute')
    untouched=set(projection(plan))-set(FAMILIES[r.field])
    if any(getattr(plan,k)!=getattr(draft,k) for k in untouched):raise ValueError('Untouched mandatory projection changed')
    return {'query':query,'plan':draft,'replacement_span':[a,b],'field':r.field,'base_version':current.base_version,
        'commit_performed':False,'requires_atomic_revalidation_at_commit':True}
