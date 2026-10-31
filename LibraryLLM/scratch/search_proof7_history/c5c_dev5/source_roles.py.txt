"""Bounded speech-act/segment partition before field extraction.

This is an internal, deliberately bounded language contract, not a general
natural-language entailment oracle. Quotation masks delimit operators; lexical
cues select roles only within a grammatical segment and its governing act.
"""
from dataclasses import dataclass, asdict
from enum import Enum
import re
from scratch.search_v2c_c5er.candidate_search_v4.requirement_ledger import clauses, outside


class Role(str, Enum):
    OPERATION='USER_REQUESTED_OPERATION'
    CONDITION='MANDATORY_SEARCH_CONDITION'
    PREFERENCE='OPTIONAL_PREFERENCE'
    BACKGROUND='BACKGROUND_EXPLANATION'
    LITERAL='QUOTED_LITERAL'
    EXAMPLE='EXAMPLE_OR_HYPOTHETICAL'
    REFERENCE='FIELD_OR_CONCEPT_REFERENCE'
    EXCLUSION='EXPLICIT_EXCLUSION'
    CORRECTION='CORRECTION_INSTRUCTION'
    SLOT='MISSING_OPERAND_PLACEHOLDER'
    RELATION='UNRESOLVED_RELATION_OR_ALTERNATIVE'


class Modality(str, Enum):
    MUST='MUST'
    MUST_NOT='MUST_NOT'
    SHOULD='SHOULD'
    MAY='MAY'
    CONDITIONAL='CONDITIONAL'
    NON_OPERATIVE='NON_OPERATIVE'
    UNKNOWN='UNKNOWN'


@dataclass(frozen=True)
class Unit:
    span:tuple
    clause_span:tuple
    role:Role
    modality:Modality
    rule:str

    @property
    def operative(self):
        return self.modality in (Modality.MUST, Modality.MUST_NOT)


PREFERENCE=re.compile(r'\b(?:prefer(?:ably|red|ence)?|optional|advisory|should|may)\b',re.I)
HARD=re.compile(r'\b(?:must|required?|requires|mandatory|strict)\b',re.I)
REQUEST=re.compile(r'^\s*(?:(?:please|then)\s+)*(?:find|show|search|browse|include|exclude|require|keep|give|list|return)\b',re.I)
FIELD_START=r'(?:by|titled|called|named|author|title|category|subject|language|rating|rated|published|publication|year|online|physical|digital|sort|exclude|include|must|require|prefer|should|may)\b'


def partition(text):
    units=[]
    for ca,cb,t in clauses(text):
        visible=outside(t)
        # Conjunctions introducing a new field/modal head are independent;
        # numeric conjunctions and coordinated operands retain their owner.
        cuts=[0,len(t)]
        for m in re.finditer(r',\s*|\b(?:and|but|then)\s+(?='+FIELD_START+r')',visible,re.I):
            cuts.extend([m.start(),m.end()])
        cuts=sorted(set(cuts))
        for a,b in zip(cuts,cuts[1:]):
            segment=t[a:b];plain=outside(segment).strip()
            if not plain or re.fullmatch(r'[,\s]*(?:and|but|then)?\s*',plain,re.I):continue
            role=Role.CONDITION;modal=Modality.MUST;rule='implicit.search_condition'
            head=re.sub(r'^\s*(?:and|but|then)\s+','',plain,flags=re.I)
            # Speech-act scope precedes any noun naming a database field.
            if re.match(r'^(?:if|suppose|imagine|for\s+example|as\s+an\s+example)\b',head,re.I):
                if re.search(r'\b(?:would|wanted|were|hypothetical|example|mean)\b',head,re.I):
                    role=Role.EXAMPLE;modal=Modality.NON_OPERATIVE;rule='speech_act.hypothetical'
                else:role=Role.RELATION;modal=Modality.CONDITIONAL;rule='speech_act.conditional'
            elif re.match(r'^(?:what\s+(?:does|would|is)|explain\s+(?:the\s+)?(?:field|concept|meaning))\b',head,re.I):
                role=Role.REFERENCE;modal=Modality.NON_OPERATIVE;rule='speech_act.reference'
            elif re.search(r'\b(?:cannot\s+remember|cannot\s+tell|undecided|unresolved|unsure)\b',head,re.I) and re.search(r'\b(?:whether|which|assignment)\b',head,re.I) and re.search(r'\b(?:requirements?|conditions?|filters?|clauses?|requests?|instructions?|modif\w*|applies)\b',head,re.I):
                role=Role.RELATION;modal=Modality.UNKNOWN;rule='segment.unresolved_association'
            elif re.match(r'^I\s+(?:cannot\s+remember|can.t\s+remember|remember|read|once\s+read|was\s+reading|was\s+told|thought|used\s+to)\b',head,re.I) and not HARD.search(head):
                role=Role.BACKGROUND;modal=Modality.NON_OPERATIVE;rule='speech_act.background'
            elif re.search(r'\b(?:whether|assignment|alternatives?)\b',head,re.I) and re.search(r'\b(?:undecided|unresolved|unsure|yet\s+to\s+(?:choose|decide)|cannot\s+(?:tell|choose))\b',head,re.I) and not re.search(r'\bprefer\w*|optional|advisory\b',head,re.I):
                role=Role.RELATION;modal=Modality.UNKNOWN;rule='segment.unresolved_association'
            elif re.search(r'\bif\b.*\b(?:else|otherwise)\b',head,re.I):
                role=Role.RELATION;modal=Modality.CONDITIONAL;rule='segment.conditional_branch'
            elif PREFERENCE.search(head) and not HARD.search(head):
                role=Role.PREFERENCE;modal=Modality.MAY if re.search(r'\bmay\b',head,re.I) else Modality.SHOULD;rule='segment.advisory'
            elif re.search(r'\b(?:either|whether|assignment|alternative|undecided|unresolved)\b',head,re.I):
                role=Role.RELATION;modal=Modality.UNKNOWN;rule='segment.relationship'
            elif re.match(r'^(?:instead|correct|replace|change)\b',head,re.I):
                role=Role.CORRECTION;modal=Modality.UNKNOWN;rule='segment.correction'
            elif re.search(r'\b(?:exclude|excluding|without|forbid|reject|must\s+not)\b',head,re.I):
                role=Role.EXCLUSION;modal=Modality.MUST_NOT;rule='segment.negative'
            elif REQUEST.match(head):role=Role.OPERATION;rule='speech_act.request'
            units.append(Unit((ca+a,ca+b),(ca,cb),role,modal,rule))
    return tuple(units)


def governing(units,a,b):
    owners=[u for u in units if u.span[0]<=a<b<=u.span[1]]
    return min(owners,key=lambda u:u.span[1]-u.span[0]) if owners else None


def annotate(requirement,units):
    u=governing(units,*requirement.source_span)
    role=u.role if u else Role.CONDITION
    modality=u.modality if u else Modality.MUST
    if requirement.ownership=='ADVISORY':role=Role.PREFERENCE;modality=Modality.SHOULD
    # A requested search speech act owns its arguments; it does not make each
    # author/rating operand an independent operation. Nested domain ownership
    # supplies the more precise role without changing mandatory modality.
    if role==Role.OPERATION and requirement.field not in ['sort','operation','aggregate','relationship','context','label_reference']:
        role=Role.CONDITION
    if requirement.field=='sort' and requirement.ownership=='MANDATORY':role=Role.OPERATION
    if requirement.field=='label_reference':role=Role.REFERENCE
    if requirement.field=='literal':role=Role.LITERAL
    if requirement.polarity=='NEGATIVE' and modality==Modality.MUST:role=Role.EXCLUSION;modality=Modality.MUST_NOT
    if requirement.state.value in ('EXPLICITLY_EMPTY','OMITTED_REQUIRED_VALUE','PLACEHOLDER_AWAITING_COMPLETION'):role=Role.SLOT
    if requirement.state.value=='AMBIGUOUS_ALTERNATIVE':role=Role.RELATION
    if requirement.representation=='LITERAL':role=Role.LITERAL
    return dict(source_role=role,modality=modality,
                resolution='RESOLVED' if requirement.state.value=='EXPLICITLY_SUPPLIED' else 'UNRESOLVED')


def records(units):return [asdict(u) for u in units]
