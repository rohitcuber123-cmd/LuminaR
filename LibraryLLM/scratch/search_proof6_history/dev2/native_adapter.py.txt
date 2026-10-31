"""Test-only native callback/500-character wire adapter. No persistence or auth IO.

The backend must own IssuedChoice and supply freshly authorized current context.
Preview never consumes a choice. Existing durable reservation/CAS is still required.
"""
from dataclasses import dataclass
from typing import Literal
from uuid import UUID,uuid4
from pydantic import BaseModel,ConfigDict,Field
from fastapi import HTTPException
from .completion import BoundContext
from .contract import State,digest
from .parser import PARSER_VERSION,_decode
from .recompilation import issue_completion,issue_correction,recompile

class ChoiceRequest500(BaseModel):
    model_config=ConfigDict(extra='forbid')
    clarification_id:UUID
    choice_id:UUID
    query:str=Field(max_length=500)
    mode:Literal['SMART','GENRE_SUBJECT','TITLE_AUTHOR','EXACT']='SMART'
    session_id:UUID|None=None
    library_id:UUID|None=None
    staff:bool=False
    value:str|None=Field(default=None,max_length=100)
    personalized:bool=False

@dataclass(frozen=True)
class IssuedChoice:
    clarification_id:str
    choice_id:str
    context:BoundContext
    original_query:str
    IR_digest:str
    operation:str
    field:str|None
    requirement_id:str|None

def issue_choice(plan,context,operation,field=None):
    if context.parser_version!=PARSER_VERSION or context.query_digest!=digest(plan.raw_query) or context.mode!=plan.mode:raise ValueError('Source binding changed')
    ir=_decode(plan.decision['query_ir_contract']);rid=None
    if operation=='complete':
        rr=[r for r in ir.requirements if r.field==field and r.state in [State.EMPTY,State.PLACEHOLDER,State.OMITTED] and r.ownership=='MANDATORY']
        if len(rr)!=1:raise ValueError('No unique source-owned operand')
        rid=rr[0].requirement_id
    elif operation not in ['correction_apply','correction_keep']:raise ValueError('Unsupported transformation')
    return IssuedChoice(str(uuid4()),str(uuid4()),context,plan.raw_query,digest(plan.decision['query_ir_contract']),operation,field,rid)

def resolve_choice(request,issued,plan,current,*,now,facets,capabilities,authorized=False):
    if not authorized:raise HTTPException(401,'Fresh backend authorization required.')
    ctx=issued.context
    if (current.owner,current.login_session,current.library_id,current.workspace)!=(ctx.owner,ctx.login_session,ctx.library_id,ctx.workspace):raise HTTPException(404,'Search choice unavailable.')
    if now>=ctx.expires_at:raise HTTPException(410,'Search choice expired.')
    if current!=ctx or current.used:raise HTTPException(409,'Accepted context changed or choice consumed.')
    if str(request.clarification_id)!=issued.clarification_id or str(request.choice_id)!=issued.choice_id:raise HTTPException(404,'Search choice unavailable.')
    lid=str(request.library_id) if request.library_id else None
    if lid!=ctx.library_id or request.staff!=(ctx.workspace=='STAFF'):raise HTTPException(404,'Search choice unavailable.')
    if request.query!=issued.original_query or request.mode!=ctx.mode or digest(plan.decision.get('query_ir_contract'))!=issued.IR_digest:raise HTTPException(409,'Query/source binding changed.')
    try:
        if issued.operation=='complete':
            if request.value is None:raise ValueError('Completion operand required')
            edit=issue_completion(plan,issued.requirement_id,request.value,ctx.base_version)
            if edit.field!=issued.field:raise ValueError('Wrong completion field')
        else:
            if request.value is not None:raise ValueError('Correction does not accept an operand')
            edit=issue_correction(plan,issued.operation,ctx.base_version)
        return recompile(edit,plan,ctx,current,now=now,facets=facets,capabilities=capabilities,authorized=True)
    except ValueError as e:raise HTTPException(422,str(e)) from e

def transformer(row,choice,value,*,current,now,authorized=False):
    """Same pure callback shape as native transformer: (plan, facets, caps)."""
    issued=row['issued_choice']
    if choice['choice_id']!=issued.choice_id or choice['operation']!=issued.operation:raise HTTPException(404,'Search choice unavailable.')
    request=ChoiceRequest500(clarification_id=issued.clarification_id,choice_id=issued.choice_id,query=row['query'],mode=row['mode'],
        library_id=issued.context.library_id,staff=issued.context.workspace=='STAFF',value=value)
    def apply(plan,facets,capabilities):
        return resolve_choice(request,issued,plan,current,now=now,facets=facets,capabilities=capabilities or {},authorized=authorized)['plan']
    return apply
