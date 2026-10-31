"""Lexical source units and typed reference/operand boundaries.

Quoted text and initials are opaque to clause punctuation. These source-only
nodes do not execute filters; unsupported reference graphs retain their target
instead of being projected as an ordinary scalar operand.
"""
from dataclasses import dataclass
import re


@dataclass(frozen=True)
class Token:
    kind:str
    text:str
    start:int
    end:int


PATTERN=re.compile(r'"[^"\n]*"|“[^”\n]*”|(?<!\w)(?:[A-Za-z]\.\s*)+(?=[A-Za-z])|\d+(?:\.\d+)?|[^\W\d_]+(?:[’\x27-][^\W\d_]+)*|[^\s]',re.UNICODE)


def tokens(query):
    result=[]
    for m in PATTERN.finditer(query):
        t=m[0]
        kind='QUOTED' if t[0] in '"“' else 'INITIALS' if re.fullmatch(r'(?:[A-Za-z]\.\s*)+',t) else 'NUMBER' if re.fullmatch(r'\d+(?:\.\d+)?',t) else 'WORD' if t[0].isalpha() else 'PUNCT'
        result.append(Token(kind,t,m.start(),m.end()))
    return result


def outside(query):
    chars=list(query)
    for t in tokens(query):
        if t.kind=='QUOTED':chars[t.start:t.end]=' '*(t.end-t.start)
    return ''.join(chars)


def clauses(query):
    from .language import segment
    for u in segment(query):yield u.start,u.end,u.text


@dataclass(frozen=True)
class Frame:
    start:int
    end:int
    field:str
    operator:str
    value:object
    status:str='SUPPORTED'
    rule:str='lexical.operand'


LANGUAGES=frozenset(['english','french','german','spanish','italian','portuguese','hindi','tamil','telugu','bengali','arabic','chinese','japanese','korean','russian'])


def references(query):
    """A field/concept instruction prefix is distinct from its later predicate."""
    from .ontology import DOMAINS
    result=[]
    for a,b,text in clauses(query):
        colon=text.find(':')
        colon_end=a+colon+1 if colon>=0 else (b+1 if b<len(query) and query[b]==':' else -1)
        if colon_end<0:continue
        prefix=text[:colon] if colon>=0 else text;plain=outside(prefix)
        if not re.search(r'\b(?:correction|field|label|concept|meaning)\b',plain,re.I):continue
        domains={d.name for d in DOMAINS.values() if any(re.search(r'\b'+re.escape(label)+r'\b',plain,re.I) for label in d.labels)}
        if not domains or any(t.kind in ['NUMBER','QUOTED'] for t in tokens(prefix)):continue
        if not re.search(r'\b(?:use|mean|refer|label|field)\b',plain,re.I):continue
        result.append((a,colon_end))
    return result


def frames(query):
    from .ontology import DOMAINS
    result=[];refs=references(query)
    for a,b in refs:result.append(Frame(a,b,'label_reference','DECLARATION',query[a:b],rule='lexical.field_reference'))
    for a,b,text in clauses(query):
        tt=[t for t in tokens(query[a:b])]
        tt=[Token(t.kind,t.text,a+t.start,a+t.end) for t in tt]
        plain=outside(text).casefold()
        # A quoted record used as a relational operand is not a scalar author,
        # date or rating. Preserve the whole governing relation before field
        # recognizers can consume its bibliographic mentions independently.
        for quoted in (x for x in tt if x.kind=='QUOTED'):
            prefix=outside(query[a:quoted.start]).casefold()
            reference=re.search(r'\b(?:author|writer|creator|rating|year|published|issued)\b(?:\s+[a-z]+){0,4}\s+(?:of|than|before|after|as)\s+(?:(?:the|a)\s+(?:book|work|record|title)\s+)?$',prefix)
            if reference:
                result.append(Frame(a,b,'relationship','CROSS_BOOK',{'source':query[a:b],'reference':quoted.text[1:-1]},'UNSUPPORTED','lexical.record_operand_edge'))
        # Two complete catalogue predicates joined by OR form a union query,
        # distinct from an unresolved choice of one missing field operand.
        branches=re.split(r'\bor\b',plain)
        if len(branches)==2 and re.match(r'\s*either\s+(?:books?|records?|entries)\b',branches[0]) and re.match(r'\s*(?:books?|records?|entries)\b',branches[1]) and not re.search(r'\b(?:undecided|unresolved|choose|choice|unsure|pending)\b',plain):
            result.append(Frame(a,b,'relationship','BOOLEAN_OR',{'branches':[x.strip() for x in branches]},'UNSUPPORTED','lexical.record_union'))
        for i,t in enumerate(tt):
            if t.kind!='WORD' or any(x<=t.start<y for x,y in refs):continue
            word=t.text.casefold()
            if word in ['published','issued'] and i+1<len(tt) and tt[i+1].text.casefold()=='by':
                negative=re.search(r'\b(?:not|exclude|without)\b',plain[:t.start-a])
                start=a+negative.start() if negative else t.start
                result.append(Frame(start,b,'publisher','NOT' if negative else 'EXACT',query[tt[i+1].end:b].strip(),'UNSUPPORTED','lexical.publisher_agent'))
            if word in ['sort','order']:
                tail=query[t.start:b].casefold()
                field=next((f for f in ['title','rating','newest'] if re.search(r'\b'+f+r'\b',tail)),None)
                direction='ASC' if re.search(r'\b(?:ascending|lowest\s+to\s+highest)\b',tail) else 'DESC' if re.search(r'\b(?:descending|highest\s+to\s+lowest)\b',tail) else None
                from .ontology import SORT_DIRECTIONS
                if field and direction and SORT_DIRECTIONS[field.upper()]!=direction:
                    result.append(Frame(t.start,b,'sort','DIRECTION',{'field':field.upper(),'direction':direction},'UNSUPPORTED','lexical.sort_capability'))
            # Comparative domain + reference edge requires a join to another
            # record; no native scalar predicate enforces that relationship.
            if word in ['same','different']:
                look=tt[i+1:i+7]
                labels={label:d.name for d in DOMAINS.values() for label in d.labels if ' ' not in label}
                domain=next((labels[x.text.casefold()] for x in look if x.kind=='WORD' and x.text.casefold() in labels),None)
                edge=next((x for x in look if x.kind=='WORD' and x.text.casefold() in ['as','from','than']),None)
                if domain and edge and any(x.kind=='QUOTED' or x.text.casefold() in ['book','record','title'] for x in tt if x.start>=edge.end):
                    start=next((x.start for x in reversed(tt[:i]) if x.kind=='WORD' and x.text.casefold() in ['by','with','published','having']),t.start)
                    result.append(Frame(start,b,'relationship','CROSS_BOOK',{'referenced_domain':domain,'source':query[edge.end:b]},'UNSUPPORTED','lexical.record_reference'))
            # Explicit exact-title operator has an enforceable native predicate.
            if word=='exact' and i+2<len(tt) and tt[i+1].text.casefold() in ['title','literal'] and tt[i+2].kind=='QUOTED':
                q=tt[i+2];result.append(Frame(t.start,q.end,'literal','EXACT',q.text[1:-1],rule='lexical.exact_operand'))
            # Source language vocabulary is deliberately finite. Unknown terms
            # do not become a language or silently choose a different domain.
            if word=='in' and i+1<len(tt) and tt[i+1].text.casefold() in LANGUAGES:
                value=tt[i+1]
                if re.search(r'\b(?:books?|titles?|find|search|show|return|written|works)\b',outside(query[:t.start]),re.I):
                    result.append(Frame(t.start,value.end,'language','EXACT',value.text.casefold(),rule='lexical.language_operand'))
            # A requested title-only substring cannot use title_text, whose
            # active predicate also accepts author-only matches.
            if word in ['title','titles','title-only'] and i+2<len(tt) and tt[i+1].text.casefold() in ['containing','contains'] and tt[i+2].kind=='QUOTED':
                result.append(Frame(t.start,tt[i+2].end,'operation','TITLE_ONLY_CONTAINS',tt[i+2].text[1:-1],'UNSUPPORTED','lexical.native_enforcement_gap'))
            if word=='by':
                # Quotation owns punctuation and instruction-looking text.
                # Sort-by operations are not author introducers.
                if i+1<len(tt) and tt[i+1].kind=='QUOTED' and tt[i+1].text[1:-1].strip() and not re.search(r'\b(?:sort|order|exclude|without|not)\b',plain[:t.start-a]):
                    q=tt[i+1]
                    result.append(Frame(t.start,q.end,'author','CONTAINS',q.text[1:-1].casefold(),rule='lexical.quoted_author'))
                tail=[]
                for x in tt[i+1:]:
                    if x.kind=='PUNCT' or x.kind=='WORD' and x.text.casefold() in ['rated','rating','published','titled','online','language','excluding','exclude','in']:break
                    tail.append(x)
                if tail and any(x.kind=='INITIALS' for x in tail) and not any(x.text.casefold() in ['same','different'] for x in tail):
                    result.append(Frame(t.start,tail[-1].end,'author','CONTAINS',query[tail[0].start:tail[-1].end].strip().casefold(),rule='lexical.initialled_entity'))
            if word=='language' and i+1<len(tt) and tt[i+1].kind in ['WORD','QUOTED']:
                value=tt[i+1]
                if value.text.strip('"“”').strip() and value.text.casefold() not in ['must','required','is','field','should','unknown','and','or','are','was','were','the','for','to','not','only'] and not re.search(r'\b(?:exclude|without|not)\b',plain[:t.start-a]):
                    result.append(Frame(t.start,value.end,'language','EXACT',value.text.strip('"“”').casefold(),rule='lexical.explicit_language'))
    # Larger reference structures precede their scalar mentions.
    return sorted(result,key=lambda f:(f.status!='UNSUPPORTED',f.start,-(f.end-f.start)))
