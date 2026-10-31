"""Typed operand evidence; delimiters are syntax, quoted text stays literal."""
from dataclasses import dataclass
from enum import Enum
import re
from scratch.search_v2c_c5er.candidate_search_v4.requirement_ledger import outside

class OperandState(str, Enum):
    RESOLVED='PRESENT_RESOLVED'
    EMPTY='PRESENT_EMPTY'
    OMITTED='REQUIRED_OMITTED'
    PLACEHOLDER='EXPLICIT_PLACEHOLDER'
    REFERENCE='UNRESOLVED_REFERENCE'
    RELATIONSHIP='UNKNOWN_MANDATORY_RELATIONSHIP'
    OPTIONAL_UNSUPPLIED='OPTIONAL_UNSUPPLIED'
    CONTRADICTORY='CONTRADICTORY'
    UNSUPPORTED='UNSUPPORTED'
    ADVISORY='PRESENT_ADVISORY'

def state_for(status,ownership,operator,value):
    if status=='CONTRADICTORY':return OperandState.CONTRADICTORY
    if status=='UNSUPPORTED':return OperandState.UNSUPPORTED
    if status in ['AMBIGUOUS','UNRESOLVED_RELATIONSHIP']:
        return OperandState.RELATIONSHIP if operator in ['ALTERNATIVE','UNRESOLVED_RELATIONSHIP'] else OperandState.REFERENCE
    if status=='INCOMPLETE':return OperandState.EMPTY if value=='' else OperandState.OMITTED
    if ownership=='ADVISORY':return OperandState.ADVISORY
    return OperandState.RESOLVED

@dataclass(frozen=True)
class Slot:
    field:str
    start:int
    end:int
    state:OperandState

# A field introducer licenses a slot; words inside quoted operands never do.
# No catalog term, benchmark identifier or placeholder wording is consulted.
CUES={
 'author':r'\bby\b|\b(?:author|creator|writer)(?:\s+name)?\s*[:=]',
 'title':r'\b(?:titled|called|named)\b|\btitle\s*[:=]',
 'subject':r'\b(?:subject|category|classification)\b',
 'exclude':r'\b(?:exclude|excluding|without|reject)\s+(?:the\s+)?(?:whole[ -]word|word|term|phrase|text)\b',
 'rating':r'\brat(?:ing|ed)\s*(?:(?:must|should)\s+be\s*)?(?:at\s+least|at\s+most|above|below|under|over|>=|<=|>|<|=)',
 'year':r'\b(?:published|publication\s+year)\s*(?:after|before|in|from|[:=])',
 'language':r'\blanguage\s*[:=]?',
 'format':r'\bformat\s*[:=]',
}
PLACEHOLDER=re.compile(r'\s*(?:\[[^\]\n]*\]|<[^>\n]*>|\{[^}\n]*\}|\.{3,}|…|_{2,})')

def scan_slots(text):
    visible=outside(text)
    for field,pattern in CUES.items():
        for m in re.finditer(pattern,visible,re.I):
            tail=text[m.end():]
            if field=='subject' and re.search(r'\b(?:either|both|each|this|that|their|same)\s+$',visible[:m.start()],re.I):continue
            # Postfix classification is an already supplied operand, and a
            # field name mentioned in a sort is not a new operand request.
            if field=='subject' and re.search(r'\b(?:exclude|excluding|without)\s+(?:the\s+)?\S+\s+$',visible[:m.start()],re.I):continue
            if field=='subject' and re.search(r'\bin\s+(?:the\s+)?\S+\s+$',visible[:m.start()],re.I):continue
            placeholder=PLACEHOLDER.match(tail)
            if placeholder:
                yield Slot(field,m.start(),m.end()+placeholder.end(),OperandState.PLACEHOLDER)
                continue
            empty=re.match(r'\s*(?:"\s*"|“\s*”)',tail)
            if empty:
                yield Slot(field,m.start(),m.end()+empty.end(),OperandState.EMPTY)
                continue
            # Dangling field before end or an explicit clause boundary.
            if re.match(r'\s*(?:$|[;.!?]|(?:and|but)\s+(?:by|titled|rated|published|exclude|include)\b)',tail,re.I):
                yield Slot(field,m.start(),m.end(),OperandState.OMITTED)
