"""Internal source contract. These types are never accepted from a client."""
from dataclasses import dataclass,field,asdict
from enum import Enum
from hashlib import sha256
import json
from .source_roles import Role, Modality

class State(str,Enum):
    NOT_REQUESTED='NOT_REQUESTED'
    SUPPLIED='EXPLICITLY_SUPPLIED'
    EMPTY='EXPLICITLY_EMPTY'
    PLACEHOLDER='PLACEHOLDER_AWAITING_COMPLETION'
    OMITTED='OMITTED_REQUIRED_VALUE'
    AMBIGUOUS='AMBIGUOUS_ALTERNATIVE'
    CONTRADICTORY='CONTRADICTORY_VALUE'
    UNSUPPORTED='UNSUPPORTED_REQUIREMENT'

@dataclass(frozen=True)
class Requirement:
    requirement_id:str
    field:str
    operator:str
    value:object
    source_span:tuple
    source_text:str
    clause_span:tuple
    ownership:str
    polarity:str
    support:str
    state:State
    representation:str
    provenance:dict=field(default_factory=dict)
    source_role:Role=Role.CONDITION
    modality:Modality=Modality.MUST
    resolution:str='RESOLVED'

@dataclass(frozen=True)
class QueryIR:
    raw_query:str
    requirements:tuple
    clauses:tuple
    trusted_controls:dict=field(default_factory=dict)
    version:int=5

@dataclass(frozen=True)
class Proof:
    valid:bool
    decision:str
    reason:str
    fields:tuple
    violations:tuple
    covered_requirements:tuple

def digest(value):return sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()

def requirement(query,field,operator,value,span,clause,*,status='SUPPORTED',ownership='MANDATORY',
                representation='HARD_FILTER',polarity=None,provenance=None,state=None):
    a,b=span
    states={'INCOMPLETE':State.OMITTED,'AMBIGUOUS':State.AMBIGUOUS,'CONTRADICTORY':State.CONTRADICTORY,'UNSUPPORTED':State.UNSUPPORTED}
    state=state or states.get(status,State.SUPPLIED)
    polarity=polarity or ('NEGATIVE' if field.startswith('excluded') or field in ['exclude','negative_domain'] else 'POSITIVE')
    key=digest([field,operator,value,span,ownership])[:20]
    return Requirement(key,field,operator,value,tuple(span),query[a:b],tuple(clause),ownership,polarity,
        'SUPPORTED' if status not in ['UNSUPPORTED'] else 'UNSUPPORTED',state,representation,provenance or {})

def encode(ir):return asdict(ir)
