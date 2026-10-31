"""Source segmentation and interpretation proposals. No validation or projection.

Finite compositional field grammar; legacy recognition supplies additional
proposals only. Unknown mandatory language is never licensed by that fallback.
"""
from dataclasses import dataclass,replace
import re
from .contract import QueryIR,requirement,State
from .source_roles import Role,Modality

QUOTES=re.compile(r'"[^"\n]*"|“[^”\n]*”')

@dataclass(frozen=True)
class SourceUnit:
    start:int
    end:int
    text:str


def visible(text):
    return QUOTES.sub(lambda m:' '*(m.end()-m.start()),text)


def segment(query):
    """Quoted punctuation opaque; initials protected only in entity syntax."""
    masked=visible(query);start=0;units=[]
    for i,c in enumerate(masked):
        if c not in ';,.!?:\n':continue
        if c==':':
            prefix=masked[start:i]
            if not re.search(r'\b(?:correction|instruction|note)\b',prefix,re.I):continue
        if c==',':
            tail=masked[i+1:];prefix=masked[start:i]
            new_head=bool(re.match(r'\s*(?:(?:but|and)\s+)?(?:by|rated|rating|published|language|exclud\w*|includ\w*|must|require|prefer\w*|optional|advisory|should|may)\b',tail,re.I))
            suffix_advice=bool(re.match(r'\s*[^,;.!?]*\b(?:optional|advisory|preferable)\b',tail,re.I))
            independent_prefix=bool(re.search(r'\b(?:by|rated|rating|published|language|about|topic)\b',prefix,re.I))
            if not (new_head or suffix_advice and independent_prefix):continue
        if c=='.':
            if i+1<len(query) and not query[i+1].isspace() and query[i+1] not in '"“”':continue
            if i and i+1<len(query) and query[i-1].isdigit() and query[i+1].isdigit():continue
            if (i and query[i-1]=='.') or (i+1<len(query) and query[i+1]=='.'):continue
            prefix=masked[start:i+1]
            if re.search(r'\b(?:by|author|writer|creator)\b[^;:!?]*\b[A-Za-z]\.$',prefix,re.I) and i+1<len(query) and not re.match(r'\s*(?:Find|Search|Sort|Require|Exclude|Exactly|Published|Language)\b',query[i+1:]):continue
        a,b=start,i
        while a<b and query[a].isspace():a+=1
        while b>a and query[b-1].isspace():b-=1
        if a<b:units.append(SourceUnit(a,b,query[a:b]))
        start=i+1
    a,b=start,len(query)
    while a<b and query[a].isspace():a+=1
    while b>a and query[b-1].isspace():b-=1
    if a<b:units.append(SourceUnit(a,b,query[a:b]))
    return tuple(units)


def mode_of(text):
    t=visible(text).strip()
    if re.match(r'^(?:ignore|bypass|override|disregard)\b',t,re.I) and re.search(r'\b(?:rules?|safety|policy|permissions?|authentication)\b',t,re.I):return 'CONTEXT'
    if re.match(r'^(?:switch|select|change)\s+(?:the\s+)?(?:tenant|library|institution|workspace)\b',t,re.I):return 'CONTEXT'
    if re.match(r'^(?:in\s+(?:an?|the|my)\s+(?:old|previous|hypothetical)?\s*(?:example|story)|I\s+(?:cannot\s+remember\b.*?\b(?:another|different)\s+book|remember|once\s+read|was\s+reading)|for\s+example|suppose|imagine)\b',t,re.I):return 'CONTEXT'
    if re.search(r'\b(?:for\s+this\s+correction|metalinguistic|correction\s+instruction)\b',t,re.I) or re.match(r'^(?:use\s+[a-z\s]+,\s*not\s+[a-z\s]+,\s*for\s+this\s+correction)\b',t,re.I):return 'CONTEXT'
    if re.match(r'^(?:explain|what\s+(?:does|is|would))\b',t,re.I):return 'CONTEXT'
    hard=re.search(r'\b(?:must|required?|mandatory|hard\s+(?:condition|filter)|strict)\b',t,re.I)
    if not hard and re.search(r'\b(?:prefer\w*|optional|advisory|bonus|welcome|would\s+be\s+nice|should|may)\b',t,re.I):return 'ADVISORY'
    return 'MANDATORY'


def primitive(query,unit,field,op,value,status='SUPPORTED',ownership='MANDATORY'):
    state=None
    if status=='INCOMPLETE':
        state=State.PLACEHOLDER if re.search(r'\[[^\]]*\]|\.{3,}|…|_{2,}',unit.text) else State.EMPTY if re.search(r'"\s*"|“\s*”',unit.text) else State.OMITTED
    r=requirement(query,field,op,value,(unit.start,unit.end),(unit.start,unit.end),status=status,ownership=ownership,
        representation='ADVISORY' if ownership=='ADVISORY' else 'CONTEXT' if ownership=='NON_OPERATIVE' else 'SEMANTIC_RETRIEVAL' if field=='semantic' else 'RELATIONSHIP' if field=='relationship' else 'HARD_FILTER',
        provenance={'origin':'V9_INTERPRETATION','recognizer':'v9.compositional_unit','interpreted_text':unit.text},state=state)
    role=Role.PREFERENCE if ownership=='ADVISORY' else Role.OPERATION if field=='sort' else Role.LITERAL if field=='literal' else Role.RELATION if field=='relationship' else Role.SLOT if status=='INCOMPLETE' else Role.EXCLUSION if r.polarity=='NEGATIVE' else Role.CONDITION
    modality=Modality.SHOULD if ownership=='ADVISORY' else Modality.NON_OPERATIVE if ownership=='NON_OPERATIVE' else Modality.MUST_NOT if r.polarity=='NEGATIVE' else Modality.UNKNOWN if status=='AMBIGUOUS' else Modality.MUST
    if ownership=='NON_OPERATIVE':role=Role.BACKGROUND
    return replace(r,source_role=role,modality=modality,resolution='RESOLVED' if status=='SUPPORTED' else 'UNRESOLVED')


def decode(query,unit):
    """Return complete-unit proposals, or None for legacy proposals to inspect."""
    text=unit.text;v=visible(text);low=v.casefold();mode=mode_of(text)
    if mode=='CONTEXT':return [primitive(query,unit,'context','NON_OPERATIVE',text,ownership='NON_OPERATIVE')]
    if mode=='ADVISORY':return [primitive(query,unit,'preference','SOFT',text,ownership='ADVISORY')]
    if re.search(r'\b(?:exclude|without)\s+[A-Za-z]+\s*,\s*[A-Za-z]+\b',v,re.I):
        return [primitive(query,unit,'relationship','ALTERNATIVE',{'source':text},'AMBIGUOUS')]
    if re.search(r'\b(?:forgot|cannot\s+(?:remember|tell)|unclear|undecided|unsure|uncertain|wait\s+for|need\s+to\s+(?:pick|choose)|resolve\s+my\s+choice)\b',low) and re.search(r'\b(?:or|versus|whether|which|choice|lower|upper|field|direction|one)\b',low):
        return [primitive(query,unit,'relationship','ALTERNATIVE',{'source':text},'AMBIGUOUS')]
    if re.search(r'\b(?:higher|lower|same|different|earlier|later)\b',low) and re.search(r'\b(?:book|work|record)\b',low) and (QUOTES.search(text) or re.search(r'\b(?:other|another|previous)\b',low)):
        return [primitive(query,unit,'relationship','CROSS_BOOK',{'source':text},'UNSUPPORTED')]
    if re.search(r'\b(?:author|writer|creator)\s+of\s+',low) and QUOTES.search(text):return [primitive(query,unit,'relationship','CROSS_BOOK',{'source':text},'UNSUPPORTED')]
    metadata=re.search(r'\b(publishers?|publishing\s+house|imprint|prices?|costs?|dollars?|pages?|page\s+count|editions?)\b',low)
    if metadata and not re.search(r'\b(?:about|topic\s*(?::|is)?|discussing|accounts?\s+of|studies?\s+(?:on|about|of)|history\s+of)\b',low):
        field='publisher' if metadata[1].startswith(('publish','imprint')) else 'price' if metadata[1].startswith(('price','cost','dollar')) else 'edition' if metadata[1].startswith('edition') else 'page_count'
        if re.search(r'\b(?:under|over|above|below|at\s+least|at\s+most|more\s+than|less\s+than)\s+pages?\b',low) and not re.search(r'\d+',low):
            return [primitive(query,unit,field,'UNENFORCEABLE',None,'INCOMPLETE')]
        return [primitive(query,unit,field,'UNENFORCEABLE',text,'UNSUPPORTED')]
    # Entity syntax composes operation, match strength and literal operand.
    literal=re.fullmatch(r'\s*(?:(?:find|show|return|keep|books?\s+)?\s*)?(?:the\s+)?(?:exact\s+(?:title|literal)|exactly\s+(?:titled|called|named))\s*[:=]?\s*("[^"\n]*"|“[^”\n]*”)\s*',text,re.I)
    author=re.fullmatch(r'\s*(?:(?:find|show|keep|books?|written)\s+)*(?:by\b(?:\s+(?:the\s+)?(?:author|writer|creator)(?:\s+text)?)?|(?:author|writer|creator)(?:\s+names?)?\s+(?:containing|contains|is)|(?:author|writer|creator)\s*:)\s*:?\s*(.*?)\s*',text,re.I)
    if literal:
        value=' '.join(literal[1][1:-1].casefold().split());return [primitive(query,unit,'literal','EXACT',value,'SUPPORTED' if value.strip() else 'INCOMPLETE')]
    if author:
        value=author[1].strip().strip('"“”')
        if re.search(r'\b(?:of\s+(?:the\s+)?book|same|different)\b',value,re.I):return [primitive(query,unit,'relationship','CROSS_BOOK',text,'UNSUPPORTED')]
        if re.search(r'\b(?:paired\s+with|associated\s+with|linked\s+to|corresponding\s+to)\b',value,re.I):return [primitive(query,unit,'relationship','ALTERNATIVE',{'source':text},'AMBIGUOUS')]
        if not value or re.fullmatch(r'\[[^\]]*\]|\.{3,}|…|_{2,}',value):return [primitive(query,unit,'author','CONTAINS',None,'INCOMPLETE')]
        # A whole entity must not absorb a later field operation.
        if not re.search(r'\b(?:rated|rating|published|language|sort|exclude\w*|include\w*|about|topic|not|without|but\s+not)\b',visible(value),re.I):return [primitive(query,unit,'author','CONTAINS',value.casefold())]
    if re.search(r'\b(?:title|titles|title-only)\s+(?:containing|contains)\b',low):return [primitive(query,unit,'operation','TITLE_ONLY_CONTAINS',text,'UNSUPPORTED')]
    # Positive source topic syntax prevents field words in the topic becoming predicates.
    topic=re.fullmatch(r'\s*(?:(?:for\s+our\s+collection\s+session,?\s*)?(?:find|search|show)(?:\s+me)?(?:\s+books?)?(?:\s+(?:about|on))?\s*:?|(?:books?|novels?|works)\s+(?:about|on)|my\s+topic\s+is|I\s+am\s+preparing\s+a\s+reading\s+list\s+about)\s+(.+)',text,re.I)
    if topic and not re.search(r'\b(?:by|rated|rating|stars?|published|must|required|exclude\w*|include\w*|sort|available|between\s+\d+)\b',visible(topic[1]),re.I):
        return [primitive(query,unit,'semantic','TOPIC',topic[1].strip())]
    return None


def interpret(query,base):
    rr=list(base.requirements);units=segment(query);handled=[]
    for u in units:
        proposals=decode(query,u)
        if proposals is None:continue
        if len(proposals)==1 and proposals[0].field=='semantic' and not re.search(r'\b(?:about|topic)\b',visible(u.text),re.I) and any(r.field not in ['semantic','semantic_residue','context'] and r.source_span[0]>=u.start and r.source_span[1]<=u.end for r in rr):continue
        # Overlay source-owned units, not benchmark cases or native plan fields.
        retained=[r for r in rr if not (r.source_span[0]<u.end and u.start<r.source_span[1])]
        if any(r.field=='operation' and r.operator=='TITLE_ONLY_CONTAINS' for r in proposals):
            retained.extend(r for r in rr if r.source_span[0]>=u.start and r.source_span[1]<=u.end and r.field not in ['title','literal','operation','semantic','semantic_residue'])
        if any(r.support=='UNSUPPORTED' for r in proposals):
            retained.extend(r for r in rr if r.source_span[0]>=u.start and r.source_span[1]<=u.end and r.field in ['semantic','semantic_residue'])
        rr=retained
        rr.extend(proposals);handled.append((u.start,u.end))
    return QueryIR(query,tuple(rr),tuple((u.start,u.end) for u in units),base.trusted_controls,version=9),units,handled
