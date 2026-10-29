"""Test-only source refinement drafts. Durable one-use CAS is not implemented.

Existing completion/removal uses recompilation.py. This module adds explicit
filters by appending source, retaining original query and accepted source/IR
digests plus backend identity, version and expiry in the existing BoundContext.
"""
from dataclasses import dataclass,asdict
import re,math
from .parser import parse_query,validate,executable,PARSER_VERSION
from .contract import digest
from .proof import projection


@dataclass(frozen=True)
class RefinementPreview:
    original_query: str
    accepted_query: str
    previous_source_digest: str
    accepted_source_digest: str
    previous_ir_digest: str
    accepted_ir_digest: str
    parser_version: str
    accepted_plan_version: int
    binding: object
    plan: object
    durable: bool=False


def add_filter(plan,field,value,issued,current,*,now,facets,capabilities,authorized=False):
    if not authorized:raise ValueError('Fresh backend authorization required')
    if issued!=current or current.used or now>=current.expires_at:raise ValueError('Stale, foreign or consumed refinement')
    if current.parser_version!=PARSER_VERSION or current.mode!='SMART':raise ValueError('Parser/mode changed')
    if digest(plan.raw_query)!=current.query_digest:raise ValueError('Accepted query changed')
    old=validate(parse_query(plan.raw_query,facets,plan.mode),capabilities)
    if digest(asdict(old))!=digest(asdict(plan)):raise ValueError('Plan/source or controls changed')
    if not executable(old):raise ValueError('Resolve the previous query first')
    value=str(value).strip()
    if not value or len(value)>100 or re.search(r'["“”\r\n;]',value):raise ValueError('Invalid refinement operand')
    if field=='author':suffix='by "'+value+'"'
    elif field=='format':
        if value.upper() not in ['ONLINE','PHYSICAL','BOTH']:raise ValueError('Unknown format')
        suffix='require '+('both online and physical' if value.upper()=='BOTH' else value.lower())+' format'
    elif field=='rating':
        if not re.fullmatch(r'\d(?:\.\d+)?',value) or not 0<=float(value)<=5:raise ValueError('Invalid rating')
        suffix='rating at least '+value
    elif field=='subject':
        if value not in facets:raise ValueError('Choose an existing category')
        suffix='include subject "'+value+'"'
    elif field=='sort':
        suffix={'TITLE':'sort by title','RATING':'sort by rating','NEWEST':'sort newest first','RELEVANCE':'sort by relevance'}.get(value.upper())
        if suffix is None:raise ValueError('Unsupported sort')
    else:raise ValueError('Unsupported refinement')
    source=plan.raw_query+'; '+suffix
    draft=validate(parse_query(source,facets,plan.mode),capabilities)
    if not executable(draft):raise ValueError('Refinement conflicts or cannot be enforced')
    previous=projection(plan);next_projection=projection(draft)
    allowed={'author':{'author_text'},'format':{'formats'},'rating':{'rating_min','rating_min_exclusive'},
             'subject':{'subjects','include_terms'},'sort':{'sort'}}[field]
    for k,v in previous.items():
        if k not in allowed and next_projection[k]!=v:raise ValueError('Refinement lost another constraint')
    if field=='author' and plan.author_text and plan.author_text!=draft.author_text:raise ValueError('Remove the prior author explicitly')
    if field=='rating' and plan.rating_min is not None and draft.rating_min<plan.rating_min:raise ValueError('Refinement weakened a prior cutoff')
    if field in ('format','subject'):
        for k in allowed:
            if not set(previous[k]).issubset(set(next_projection[k])):raise ValueError('Refinement lost a prior selection')
    return RefinementPreview(plan.raw_query,source,digest(plan.raw_query),digest(source),
        digest(plan.decision['query_ir_contract']),digest(draft.decision['query_ir_contract']),
        PARSER_VERSION,current.base_version+1,current,draft)
