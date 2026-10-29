"""Pure server-owned source edits. No client offsets, persistence, auth or CAS.

SourceEdit instances must remain in backend-owned choice state; this is not an
HTTP DTO or an issuance service. Commit needs fresh authority/version/one-use.
"""
from dataclasses import dataclass
import re
from .contract import State,digest
from .parser import parse_query,validate,executable,PARSER_VERSION,_decode
from .proposals import FAMILIES
from .proof import projection

@dataclass(frozen=True)
class SourceEdit:
    operation:str
    field:str
    requirement_ids:tuple
    replacements:tuple
    query_digest:str
    ir_digest:str
    controls_digest:str
    parser_version:str
    base_version:int
    expected_query:str

def _rewrite(query,replacements):
    last=len(query)+1
    for a,b,old,new in sorted(replacements,reverse=True):
        if not 0<=a<=b<=len(query) or b>=last or query[a:b]!=old:raise ValueError('Ambiguous or changed source ownership')
        query=query[:a]+new+query[b:];last=a
    if len(query)>500:raise ValueError('Completed query exceeds parser limit')
    return query

def _spec(plan,operation,field,requirements,replacements,base_version):
    blob=plan.decision['query_ir_contract'];ir=_decode(blob)
    return SourceEdit(operation,field,tuple(r.requirement_id for r in requirements),tuple(replacements),
        digest(plan.raw_query),digest(blob),digest(ir.trusted_controls),PARSER_VERSION,base_version,_rewrite(plan.raw_query,replacements))

def issue_completion(plan,requirement_id,value,base_version):
    ir=_decode(plan.decision['query_ir_contract']);rr=[r for r in ir.requirements if r.requirement_id==requirement_id]
    if len(rr)!=1:raise ValueError('No unique requirement')
    r=rr[0]
    if r.ownership!='MANDATORY' or r.state not in [State.EMPTY,State.OMITTED,State.PLACEHOLDER] or r.field not in FAMILIES:raise ValueError('No source-owned completable operand')
    slots=[x for x in ir.requirements if x.field==r.field and x.state in [State.EMPTY,State.OMITTED,State.PLACEHOLDER]]
    if len({x.source_span for x in slots})!=1:raise ValueError('Multiple field operands need an explicit edit')
    value=str(value).strip()
    if not value or len(value)>100 or re.search(r'["“”\r\n]',value):raise ValueError('Invalid operand')
    a,b=r.source_span;fragment=plan.raw_query[a:b]
    markers=list(re.finditer(r'\[[^\]]*\]|<[^>]*>|\{[^}]*\}|\.{3,}|…|_{2,}|"\s*"|“\s*”',fragment))
    if len(markers)==1:a,b=a+markers[0].start(),a+markers[0].end()
    elif not markers and r.state==State.OMITTED:a=b
    else:raise ValueError('No unique operand placeholder')
    if r.field in ['rating','year']:
        if not re.fullmatch(r'-?\d+(?:\.\d+)?',value):raise ValueError('Numeric operand required')
        replacement=value
    elif r.field=='sort':
        replacement={'TITLE':'title','RATING':'rating','NEWEST':'newest','RELEVANCE':'relevance'}.get(value.upper())
        if replacement is None:raise ValueError('Unsupported ordering criterion')
    else:replacement='"'+value+'"'
    if a==b:replacement=' '+replacement
    return _spec(plan,'complete',r.field,slots,[(a,b,plan.raw_query[a:b],replacement)],base_version)

def issue_correction(plan,operation,base_version):
    if operation not in ['correction_apply','correction_keep']:raise ValueError('Unsupported correction operation')
    ir=_decode(plan.decision['query_ir_contract']);nn=[n for n in plan.decision.get('repair_notices',[]) if n.get('kind') in ['typo','alias']]
    if len(nn)!=1:raise ValueError('Correction must have one source owner')
    n=nn[0];a,b=n['source_span']
    owners=[r for r in ir.requirements if r.field in ['subject','excluded_subject'] and r.source_span[0]<=a<b<=r.source_span[1]]
    if len(owners)!=1:raise ValueError('Correction owner ambiguous')
    r=owners[0]
    if operation=='correction_apply':edits=[(a,b,plan.raw_query[a:b],n['to'])]
    else:
        # An explicit choice withdraws just the corrected positive requirement;
        # its original operand is retained as semantic content. Negative-domain
        # changes require explicit editing, never recasting as broad text.
        if r.field!='subject':raise ValueError('Negative correction needs explicit query editing')
        a,b=r.source_span;edits=[(a,b,plan.raw_query[a:b],'about "'+n['from']+'"')]
    return _spec(plan,operation,r.field,[r],edits,base_version)

def issue_remove(plan,field,base_version):
    ir=_decode(plan.decision['query_ir_contract']);rr=[r for r in ir.requirements if r.field==field and r.ownership=='MANDATORY']
    if not rr or field not in FAMILIES:raise ValueError('No source-owned field to remove')
    return _spec(plan,'remove',field,rr,[(*r.source_span,r.source_text,'') for r in rr],base_version)

def recompile(edit,plan,issued,current,*,now,facets,capabilities,authorized=False):
    if not authorized:raise ValueError('Fresh backend authorization required')
    if issued!=current or current.used or now>=current.expires_at:raise ValueError('Stale, foreign or consumed choice')
    if current.parser_version!=PARSER_VERSION or edit.parser_version!=PARSER_VERSION or current.mode!='SMART' or plan.mode!='SMART':raise ValueError('Parser/mode binding changed')
    if current.base_version!=edit.base_version or current.query_digest!=edit.query_digest or digest(plan.raw_query)!=edit.query_digest:raise ValueError('Accepted version/query binding changed')
    blob=plan.decision['query_ir_contract'];ir=_decode(blob)
    if digest(blob)!=edit.ir_digest or digest(ir.trusted_controls)!=edit.controls_digest:raise ValueError('Original IR/controls changed')
    original=parse_query(plan.raw_query,facets,plan.mode,ir.trusted_controls.get('filters'),ir.trusted_controls.get('omit',()))
    if digest(original.decision['query_ir_contract'])!=edit.ir_digest or projection(original)!=projection(plan):raise ValueError('Source plan or vocabulary changed')
    query=_rewrite(plan.raw_query,edit.replacements)
    if query!=edit.expected_query:raise ValueError('Unexpected resulting query')
    draft=validate(parse_query(query,facets,plan.mode,ir.trusted_controls.get('filters'),ir.trusted_controls.get('omit',())),capabilities)
    if not executable(draft):raise ValueError('Remaining mandatory requirements cannot execute')
    # Fingerprints of individual conditions preserve duplicate/conflicting
    # evidence that aggregate native fields alone cannot represent.
    next_ir=_decode(draft.decision['query_ir_contract'])
    def meaning(r):return (r.field,r.operator,digest(r.value),r.state,r.ownership,r.polarity,r.modality,r.support)
    untouched=[r for r in ir.requirements if r.ownership=='MANDATORY' and r.requirement_id not in edit.requirement_ids]
    remaining=list(next_ir.requirements)
    for r in untouched:
        match=next((x for x in remaining if meaning(x)==meaning(r) and x.source_text==r.source_text),None)
        if match is None:raise ValueError('Previously mandatory condition lost or changed')
        remaining.remove(match)
    before=projection(plan);after=projection(draft);allowed=set(FAMILIES[edit.field])
    if any(before[k]!=after[k] for k in before if k not in allowed):raise ValueError('Untouched projection changed')
    draft.decision['source_edit_provenance']={'operation':edit.operation,'field':edit.field,'original_query_digest':edit.query_digest,
        'original_parser_version':edit.parser_version,'accepted_plan_version':edit.base_version,'replacements':edit.replacements,
        'resulting_query':query,'resulting_query_digest':digest(query),'full_reparse':True,'untouched_mandatory_preserved':len(untouched)}
    return {'query':query,'plan':draft,'field':edit.field,'base_version':edit.base_version,'replacement_span':list(edit.replacements[0][:2]),
        'commit_performed':False,'requires_atomic_revalidation_at_commit':True}
