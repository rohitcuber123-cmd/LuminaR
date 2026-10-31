"""Source-owned operation IR. No application, database, model or benchmark IO."""
from dataclasses import dataclass,field,asdict
import re
from scratch.search_v2c_c5er.candidate_search_v4 import query_constraints as grammar
from scratch.search_v2c_c5er.candidate_search_v4.requirement_ledger import clauses,outside
from scratch.search_v2c_c5er.candidate_search_v4.query_plan import normalize
from .vocabulary import FacetVocabulary
from .operands import OperandState, scan_slots, state_for
from scratch.search_v2c_c5er.candidate_search_v4.semantic_safety import distance_one

@dataclass
class Requirement:
    field:str
    operator:str
    value:object
    source_span:list
    owning_clause_span:list
    status:str='RESOLVED'
    ownership:str='MANDATORY'
    representation:str='HARD_FILTER'
    provenance:dict=field(default_factory=dict)
    operand_state:str=""

    def __post_init__(self):
        if not self.operand_state:self.operand_state=state_for(self.status,self.ownership,self.operator,self.value).value

@dataclass
class Understanding:
    source:object
    evidence:list=field(default_factory=list)
    changed_families:set=field(default_factory=set)
    corrections:list=field(default_factory=list)
    topic_spans:list=field(default_factory=list)

FAMILIES={'subject':['subjects','include_terms'],'excluded_subject':['exclude_subjects'],'exclude':['exclude_terms'],'author':['author_text'],'title':['title_text'],
    'rating':['rating_min','rating_max','rating_min_exclusive','rating_max_exclusive'],'year':['year_min','year_max','year_min_exclusive','year_max_exclusive'],
    'format':['formats','exclusive_formats'],'excluded_format':['excluded_formats'],'availability':['availability','physical_available_only'],'language':['language'],'sort':['sort']}
FIELD_CUES={'author':r'\bauthor|creator|writer|\bby\b','title':r'\btitle|titled\b','rating':r'\brat(?:ing|ed)|cutoff|stars?\b','year':r'\bpublication|published|year\b',
    'exclude':r'\bexclu\w*|whole.word\b','subject':r'\bsubject|category|classification\b','format':r'\bonline|digital|physical|format|access\b','availability':r'\bavailable|availability\b','language':r'\blanguage\b'}

def understand(text,facets,source=None):
    s=source if source is not None else grammar.Source(text);ir=Understanding(s);vocab=FacetVocabulary(facets);parts=list(clauses(s.text))
    def owner(a,b):return next(([x,y] for x,y,_ in parts if x<=a<y),[a,b])
    def claim(field,op,value,a,b,rid,status='SUPPORTED',literal=False,repair=None,changed=True):
        if a>=b:return False
        x,y=s.span(a,b)
        if any(x<c.source_span_end and y>c.source_span_start for c in s.items):return False
        if not literal and not s.free(a,b):return False
        s.items.append(grammar.Candidate(field,op,value,x,y,s.raw[x:y],rid,support_status=status,repair_provenance='source-owned canonical repair' if repair else None,
            owning_clause_span=list(s.span(*owner(a,b))),ownership='ADVISORY' if field=='preference' else 'MANDATORY',representation='ADVISORY' if field=='preference' else 'HARD_FILTER'))
        if changed and field in FAMILIES:ir.changed_families.add(field)
        if repair:
            correction={**repair,'source_span':[x,y]};ir.corrections.append(correction)
        return True
    def evidence(field,op,value,a,b,status):
        x,y=s.span(a,b);ca,cb=s.span(*owner(a,b))
        ir.evidence.append(Requirement(field,op,value,[x,y],[ca,cb],status,representation='RELATIONSHIP' if field=='relationship' else 'UNRESOLVED'))
    # Modality is assigned BEFORE numeric/facet extraction, for every field.
    for a,b,t in parts:
        plain=outside(t)
        if re.search(r'\b(?:prefer\w*|optional|advisory)\b',plain) and not re.search(r'\b(?:require|required|requires|must|mandatory|strict)\b',plain):
            prefix=re.search(r'\b(?:prefer|preferably)\b',plain)
            head=re.search(r'\b(?:beginner\w*|introduct\w*|advanced|research|reference\w*|short\w*|easy)\b',plain)
            start=prefix.start() if prefix else head.start() if head and re.search(r'\bby\b|\btitled\b',plain[:head.start()]) else 0
            end=len(t)
            next_field=re.search(r'\b(?:and|but)\s+(?=(?:require|must|by|titled|include|exclude|rated|published)\b)',plain[start:])
            if next_field:end=start+next_field.start()
            claim('preference','SOFT',t[start:end].strip(),a+start,a+end,'ir.advisory',literal=True)
            # Reset only operands whose original source is advisory, later
            # recompose all mandatory operands of those field families.
            for f,p in FIELD_CUES.items():
                if re.search(p,outside(t[start:end])):ir.changed_families.add(f)
        preamble=re.match(r'\s*(?:within|in)\s+[^:;]{0,90}\bcatalog(?:ue)?(?:\s+as\s+(?:(?:a|an)\s+)?\w+)?\s*:\s*',t)
        if preamble:claim('connector','GRAMMAR',None,a,a+preamble.end(),'ir.context_scaffold')
        topic=re.search(r'\btopic\s*:\s*(.+)',t)
        if topic:
            claim('semantic','TOPIC',s.raw[s.span(a+topic.start(1),a+topic.end(1))[0]:s.span(a+topic.start(1),a+topic.end(1))[1]],a+topic.start(),a+topic.end(),'ir.topic',literal=True)
    # Quoted bibliographic literals use the existing native contains contracts.
    q=r'["“]([^"”\n]*)["”]'
    for f,pat in [('author',r'\bby\s+(?:(?:the\s+)?(?:exact\s+)?(?:(?:author|creator|writer)\s+)?name\s+)?'+q),
        ('title',r'\b(?:titled|called|named)\s+(?:exactly\s+)?'+q)]:
        for m in re.finditer(pat,s.text):claim(f,'CONTAINS',m[1],*m.span(),'ir.literal',literal=True,status='SUPPORTED' if m[1].strip() else 'INCOMPLETE')
    # Canonical fields: bounded longest operand prefix followed by grammar.
    markers=r'\b(?:(include|exclude|excluding|without|not)\s+(?:the\s+)?)?(subject|category|classification)\s+'
    for m in re.finditer(markers,s.remaining(protect=False)):
        start=m.end();end=next((b for a,b,_ in parts if a<=start<b),len(s.text));tail=s.text[start:end]
        quote=re.match(q,tail);term=None;stop=None;repair=None
        candidates=[(quote.end(),quote[1])] if quote else [(w.end(),tail[:w.end()].strip()) for w in re.finditer(r'\S+',tail[:100])]
        for length,value in reversed(candidates):
            value=value.rstrip(' ,;.!?');resolved,confidence,correction=vocab.resolve(value,fuzzy=True)
            if resolved:term=resolved;stop=start+length;repair=correction;break
        negative=m[1] in ['exclude','excluding','without','not'];f='excluded_subject' if negative else 'subject'
        if term:claim(f,'NOT' if negative else 'INCLUDE',term,m.start(),stop,'ir.canonical',literal=bool(quote),repair=repair)
    for m in re.finditer(r'\b(?:exclude|excluding|without)\s+(?:the\s+)?([^,;.]+?)\s+classification\b',s.remaining()):
        term,_,repair=vocab.resolve(m[1].strip(),fuzzy=True)
        if term:claim('excluded_subject','NOT',term,*m.span(),'ir.canonical_negative',repair=repair)
    for m in re.finditer(r'\b(?:exclude|excluding|reject|without|but\s+not)\s+(?:the\s+)?(?:(?:searchable[ -]text|whole[ -]word)\s+)*(?:whole[ -]word|word|text|phrase)\s+'+q,s.text):
        claim('exclude','TEXT_NOT',m[1],*m.span(),'ir.text_negative',literal=True)
    for m in re.finditer(r'\bsort\s+(?:on|by)\s+(?:the\s+)?(highest\s+rating|rating|title|newest|relevance)\b',s.text):
        claim('sort','=',{'highest rating':'RATING','rating':'RATING','title':'TITLE','newest':'NEWEST','relevance':'RELEVANCE'}[m[1]],*m.span(),'ir.sort')
    for m in re.finditer(r'\b(?:no\s+more\s+than|no\s+fewer\s+than|at\s+most|at\s+least)\s+\d+\s+pages?\b',s.text):
        claim('pages','COMPARATOR',m[0],*m.span(),'ir.unsupported_unit',status='UNSUPPORTED')
    # Mature numeric, format, entity and negative grammar remains shared.
    for fn in [grammar.unsupported_and_sorts,grammar.ratings,grammar.years,grammar.formats_availability]:fn(s)
    grammar.owned_literals(s,facets)
    grammar.author_title_entities(s,facets)
    grammar.subject_clauses(s,facets)
    grammar.clause_connectors(s)
    from scratch.search_v2c_c5er.candidate_search_v4.requirement_ledger import grammar as claim_field_frames
    claim_field_frames(s)
    # A catalog-noun target of an entity clause is grammatical, not a subject
    # requirement. Explicit category owners and standalone requirements stay.
    for c in s.items:
        if c.field=='subject' and c.recognizer_id=='subject.requirement':
            tail=s.raw[c.source_span_end:]
            if re.match(r'\s+(?:titled|called|named|by)\b',tail,re.I) and not re.search(r'\b(?:subject|category|classification)\b',c.source_text,re.I):
                c.field='connector';c.operator='GRAMMAR';c.normalized_value=None
    # Pending alternatives are proposals, not simultaneous conjuncts. Their
    # fields cannot participate in native contradiction validation yet.
    for r in ir.evidence:
        if r.field!='relationship' or r.status!='AMBIGUOUS' or not isinstance(r.value,dict):continue
        families=set(r.value.get('fields',[]))
        if 'subject' in families:families.add('excluded_subject')
        for c in s.items:
            if c.field in families and c.support_status=='SUPPORTED':
                c.support_status='AMBIGUOUS';ir.changed_families.add(c.field)
    return ir
