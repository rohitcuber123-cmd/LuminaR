"""Four-channel, source-grounded view of the existing proof-carrying IR.

An intent is internal evidence, never an authorization or client DTO. Recognition
is finite English grammar; a valid span is necessary, not proof of understanding.
"""
from dataclasses import dataclass, asdict
from .contract import digest
from .ontology import FAMILIES


@dataclass(frozen=True)
class IntentUnit:
    source_span: tuple
    source_text: str
    source_role: str
    domain: str
    operator: str
    operand: object
    modality: str
    polarity: str
    ownership: str
    supported: str
    relationship: str | None
    resolution: str
    native_projection: tuple
    correction_provenance: dict
    requirement_id: str
    channel: str


@dataclass(frozen=True)
class QueryIntent:
    original_source: str
    objective: str
    units: tuple
    source_digest: str
    ir_digest: str
    version: str = 'V10-query-intent-v1'


def from_ir(ir):
    units=[]
    for r in ir.requirements:
        channel=('NONOPERATIVE' if r.ownership in ('NON_OPERATIVE','REMOVED_BY_CONTROL') else
                 'C_ADVISORY' if r.ownership=='ADVISORY' else
                 'D_UNRESOLVED' if r.state.value!='EXPLICITLY_SUPPLIED' or r.support!='SUPPORTED' else
                 'A_SEMANTIC' if r.field in ('semantic','semantic_residue') else 'B_STRUCTURED')
        units.append(IntentUnit(r.source_span,r.source_text,str(r.source_role),r.field,r.operator,r.value,
            str(r.modality),r.polarity,r.ownership,r.support,r.operator if r.field=='relationship' else None,
            r.resolution,tuple(FAMILIES.get(r.field,())),r.provenance,r.requirement_id,channel))
    from .contract import encode
    return QueryIntent(ir.raw_query,'DISCOVER_LIBRARY_RESOURCES',tuple(units),digest(ir.raw_query),digest(encode(ir)))


def public_contract(ir):
    return asdict(from_ir(ir))
