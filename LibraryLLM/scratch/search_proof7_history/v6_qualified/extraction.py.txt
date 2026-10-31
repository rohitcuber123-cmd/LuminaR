"""Disabled proposal interface; JSON/source spans never authorize execution.

No model/runtime, credentials, tools, database or tenant scope is imported here.
The deterministic compiler validates proposals and independently detects source
obligations. Omission of even one recognized mandatory requirement is rejected.
"""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
import json, math
from dataclasses import replace
from types import SimpleNamespace
from .ontology import DOMAINS, supports
from .contract import QueryIR, State, requirement, encode, digest
from .source_roles import Role, Modality, partition, annotate

MAX_OUTPUT_BYTES=24576
MAX_REQUIREMENTS=32


class ProposedRequirement(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    start:int=Field(ge=0,le=499)
    end:int=Field(ge=1,le=500)
    source_text:str=Field(min_length=1,max_length=500)
    domain:str=Field(min_length=1,max_length=40)
    operator:str=Field(min_length=1,max_length=40)
    operand:str|int|float|list[str]|list[float]|None=None
    role:Role
    modality:Modality
    polarity:Literal['POSITIVE','NEGATIVE']
    state:Literal['SUPPLIED','MISSING','UNKNOWN','UNSUPPORTED','CONTRADICTORY']
    relationship:str|None=Field(default=None,max_length=100)

    @model_validator(mode='after')
    def valid(self):
        if self.start>=self.end:raise ValueError('Empty or reversed source span')
        if self.domain not in DOMAINS:raise ValueError('Unknown canonical domain')
        d=DOMAINS[self.domain]
        if self.state=='SUPPLIED' and self.operator not in d.operators:raise ValueError('Unsupported domain/operator')
        if self.state=='SUPPLIED' and self.operand in [None,'',[]]:raise ValueError('Supplied operand is empty')
        values=self.operand if isinstance(self.operand,list) else [self.operand]
        if any(type(v) is float and not math.isfinite(v) for v in values):raise ValueError('Non-finite operand')
        if self.state=='SUPPLIED' and self.domain in ['rating','year']:
            if any(type(v) not in [float,int] for v in values):raise ValueError('Numeric domain requires numbers')
            lo,hi=(0,5) if self.domain=='rating' else (1000,2100)
            if any(not lo<=v<=hi or self.domain=='year' and int(v)!=v for v in values):raise ValueError('Numeric operand out of bounds')
        if self.domain in ['exclude','excluded_subject','excluded_format'] and self.polarity!='NEGATIVE':raise ValueError('Negative domain polarity mismatch')
        if d.enforcement=='UNSUPPORTED' and self.state=='SUPPLIED':raise ValueError('Backend cannot enforce domain')
        return self


class Extraction(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    query:str=Field(max_length=500)
    intent:Literal['SEARCH','CLARIFY','NON_SEARCH']
    requirements:list[ProposedRequirement]=Field(max_length=MAX_REQUIREMENTS)


def validate_proposal(query,output):
    if not isinstance(query,str) or len(query)>500:raise ValueError('Immutable query exceeds500 characters')
    if not isinstance(output,str) or len(output.encode('utf-8'))>MAX_OUTPUT_BYTES:raise ValueError('Output size exceeded')
    # Reject duplicate keys/NaN; accepting JSON syntax is not accepting meaning.
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise ValueError('Duplicate output key')
            result[key]=value
        return result
    obj=json.loads(output,object_pairs_hook=unique,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Invalid numeric constant')))
    if obj.get('query')!=query:raise ValueError('Original query changed')
    # JSON validation permits enum strings while preserving strict numeric types.
    parsed=Extraction.model_validate_json(json.dumps(obj,ensure_ascii=False,allow_nan=False),strict=True)
    for r in parsed.requirements:
        if query[r.start:r.end]!=r.source_text:raise ValueError('Source substring mismatch')
    return parsed


def compile_proposal(query,output,facets=(),capabilities=None):
    """Return a proposal/validation result, never call a retrieval backend.

    Model proposals cannot withdraw deterministic mandatory obligations. This
    conservative envelope may reject a correct alternative extraction; measure
    that usability cost rather than silently broadening the query.
    """
    from . import parser
    from .proof import projection,validate_ir
    from .projection import _apply
    from .ontology import FAMILIES
    from .surface import semantic_projection
    from .source_analysis import audit
    proposed=validate_proposal(query,output)
    base=parser.validate(parser.parse_query(query,facets),capabilities)
    if proposed.intent!='SEARCH':return {'status':'REJECTED','reason':'NON_EXECUTABLE_INTENT','proposal':proposed.model_dump(mode='json'),'plan':None}
    units=partition(query);rr=[]
    for x in proposed.requirements:
        unit=next((u for u in units if u.span[0]<=x.start<x.end<=u.span[1]),None)
        clause=unit.clause_span if unit else (x.start,x.end)
        advisory=x.modality in [Modality.SHOULD,Modality.MAY]
        nonoperative=x.modality==Modality.NON_OPERATIVE
        ownership='ADVISORY' if advisory else 'NON_OPERATIVE' if nonoperative else 'MANDATORY'
        representation='ADVISORY' if advisory else 'CONTEXT' if nonoperative else 'SEMANTIC_RETRIEVAL' if x.domain=='semantic' else 'RELATIONSHIP' if x.domain=='relationship' else 'HARD_FILTER'
        if advisory and x.domain!='preference':return {'status':'REJECTED','reason':'ADVISORY_DOMAIN_MUST_BE_PREFERENCE','plan':None}
        r=requirement(query,x.domain,x.operator,x.operand,(x.start,x.end),clause,status={'SUPPLIED':'SUPPORTED','MISSING':'INCOMPLETE','UNKNOWN':'AMBIGUOUS'}.get(x.state,x.state),ownership=ownership,polarity=x.polarity,representation=representation,provenance={'origin':'MODEL_PROPOSAL','recognizer':'bounded.proposed_source','interpreted_text':x.source_text})
        # The model's role/modality is checked, never trusted over original source.
        expected=annotate(r,units)
        if expected['source_role']!=x.role or expected['modality']!=x.modality:return {'status':'REJECTED','reason':'SOURCE_ROLE_OR_MODALITY_UNPROVEN','plan':None}
        rr.append(replace(r,**expected))
    ir=QueryIR(query,tuple(rr),tuple(u.span for u in units))
    original=base.decision.get('query_ir_contract',{}).get('requirements',[])
    def same(a,b):
        return a['field']==b.field and a['operator']==b.operator and a['value']==b.value and a['state']==b.state.value and a['ownership']==b.ownership and a['polarity']==b.polarity
    missing=[r for r in original if r['ownership']=='MANDATORY' and r['field'] not in ['semantic_residue','label_reference'] and not any(same(r,x) for x in rr)]
    if missing:return {'status':'REJECTED','reason':'DETERMINISTIC_MANDATORY_OBLIGATION_OMITTED','omitted_requirement_ids':[r['requirement_id'] for r in missing],'plan':None}
    plan=parser.QueryPlan(query,'SMART');plan.parser_version=parser.PARSER_VERSION
    active=[r for r in rr if r.state==State.SUPPLIED and r.ownership=='MANDATORY' and supports(r.field,r.operator)]
    _apply(plan,[SimpleNamespace(field=r.field,operator=r.operator,normalized_value=r.value,support_status='SUPPORTED') for r in active],set(FAMILIES))
    plan.semantic_text=semantic_projection(ir)
    coverage=audit(ir);proof=validate_ir(ir,plan)
    if not proof.valid:return {'status':'REJECTED','reason':proof.reason,'violations':list(proof.violations),'source_coverage':coverage,'plan':None}
    # Normal capability and contradiction policy still runs after structural proof.
    plan.decision={'query_ir_contract':encode(ir),'execution_proof':{'projection':projection(plan),'IR_digest':digest(encode(ir)),'violations':[]},'source_coverage':coverage,'decision_type':'EXECUTABLE'}
    checked=parser.validate(plan,capabilities)
    return {'status':'VALIDATED' if parser.executable(checked) else 'REJECTED','reason':checked.decision.get('decision_type'),'plan':checked,'source_coverage':coverage,'proposal':proposed.model_dump(mode='json'),'retrieval_performed':False}
