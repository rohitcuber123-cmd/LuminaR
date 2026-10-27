"""Bounded clause ownership for required operands and relationships.

Pure source analysis. No corpus IDs, gold, IO, model, catalogue or actor state.
An unsupported predicate never becomes an approximation using a known field.
"""
import re

def clauses(text):
    """Original offsets; decimal periods and literal punctuation are opaque."""
    quoted=False;close='';start=0
    for i,ch in enumerate(text):
        if quoted:
            if ch==close:quoted=False
            continue
        if ch in ['"','“']:quoted=True;close='”' if ch=='“' else '"';continue
        if ch in ';!?\n' or ch=='.' and (i+1==len(text) or text[i+1].isspace()) and not (i and text[i-1]=='.') and not (i+1<len(text) and text[i+1]=='.') and not (i and i+1<len(text) and text[i-1].isdigit() and text[i+1].isdigit()):
            if text[start:i].strip():yield start,i,text[start:i]
            start=i+1
    if text[start:].strip():yield start,len(text),text[start:]

def outside(text):return re.sub(r'"[^"\n]*"|“[^”\n]*”',lambda m:' '*len(m[0]),text)

class Clause:
    def __init__(self,a,b,text):self.a=a;self.b=b;self.text=text
    def __getitem__(self,index):return self.text if index==0 else None
    def start(self):return self.a
    def end(self):return self.b
    def span(self):return self.a,self.b
def clause_matches(text):return (Clause(a,b,t) for a,b,t in clauses(text))

FIELDS={'author':r'\b(?:author|creator|writer|by)\b','title':r'\b(?:title|titled)\b','rating':r'\b(?:rating|rated|stars?|minimum|ceiling)\b',
    'year':r'\b(?:published|publication|year)\b','subject':r'\b(?:subject|category|tag|membership)\b','format':r'\b(?:online|digital|physical|access|format)\b',
    'exclude':r'\b(?:exclude|exclusion|negative|whole.word)\b'}

def own(s,facets):
    from scratch.search_v2c_c5er.candidate_search_v4.query_constraints import Candidate
    from scratch.search_v2c_c5er.candidate_search_v4.query_plan import FacetVocabulary
    vocab=FacetVocabulary(facets)
    spans=list(clauses(s.text));previous=[]
    def add(field,op,value,a,b,rid,status='SUPPORTED',repair=None,ownership='MANDATORY',representation='HARD_FILTER'):
        x,y=s.span(a,b)
        if any(x<c.source_span_end and y>c.source_span_start for c in s.items):return
        clause=next(([u,v] for u,v,_ in spans if u<=a<v),[a,b])
        s.items.append(Candidate(field,op,value,x,y,s.raw[x:y],rid,support_status=status,repair_provenance=repair,
            owning_clause_span=list(s.span(*clause)),ownership=ownership,representation=representation))
    # Background scaffold is owned only as a complete source clause.
    for a,b,text in spans:
        if re.fullmatch(r'\s*(?:search|use|browse)\s+(?:the\s+)?(?:(?:global|public|private|institutional|patron|staff|library)\s+)*(?:catalogue|catalog|collection)(?:\s+in\s+(?:the\s+)?(?:patron|staff)\s+workspace)?\s*',text):
            add('connector','GRAMMAR',None,a,b,'ledger.scope_scaffold',representation='GRAMMAR')
    for a,b,text in spans:
        plain=outside(text);fields=[f for f,p in FIELDS.items() if re.search(p,plain)]
        optional=bool(re.search(r'\b(?:optional|advisory|prefer\w*|merely\s+preferred)\b',plain))
        mandatory=bool(re.search(r'\b(?:mandatory|required|must|strict|only\s+when|condition|instruction|slots?)\b',plain))
        # Whole-clause advisory ownership precedes any hard-field recognition.
        preference=next((v for p,v in [(r'\b(?:short|shorter)\b','Prefer shorter books'),(r'\b(?:beginner|introductory)\b','Introductory / beginner (preference)'),
            (r'\b(?:advanced|research)\b','Advanced (preference)'),(r'\breference\b','Reference material (preference)')] if re.search(p,plain)),None)
        if optional and not mandatory:
            cue=re.search(r'\b(?:prefer|preferably|optional\s+(?:condition|preference))\b',plain)
            adjective=re.search(r'\b(?:short|shorter|beginner|introductory|advanced|research|reference)\b',plain) if preference else None
            begin=cue.start() if cue else adjective.start() if adjective else None
            if begin is not None:
                # Advisory ownership is local; it cannot erase an earlier hard
                # author or a following explicit field joined in the sentence.
                tail=plain[begin:]
                boundary=re.search(r'\b(?:and|but)\s+(?=(?:by|titled|include|exclude|require|rated|published|must)\b)',tail)
                end=begin+boundary.start() if boundary else len(text)
                add('preference','SOFT',preference or 'Advisory preference: '+s.raw[s.span(a+begin,a+end)[0]:s.span(a+begin,a+end)[1]],a+begin,a+end,'ledger.advisory_clause',ownership='ADVISORY',representation='ADVISORY')
                if begin==0 and end==len(text):continue
        # Explicit unknown ownership/assignment is a relationship, not a value.
        pending=bool(re.search(r'\b(?:undecided|unsettled|unresolved|pending|uncertain|not\s+(?:chosen|decided|settled))\b',plain))
        alternatives=bool(re.search(r'\b(?:choice|choose|chosen|assignment|alternatives?|whether|either|or|slots?)\b',plain))
        context=' '.join(previous[-2:]+[text])
        context_fields=[f for f,p in FIELDS.items() if re.search(p,outside(context))]
        if re.search(r'\bslots?\b',outside(context)):
            if re.search(r'["“]by["”]',context):context_fields.append('author')
            if re.search(r'["“]titled["”]',context):context_fields.append('title')
        if pending and alternatives and (mandatory or re.search(r'\b(?:assignment|instruction|choice|slots?)\b',plain)) and context_fields:
            add('relationship','UNRESOLVED',{'fields':context_fields},a,b,'ledger.required_relationship','AMBIGUOUS',representation='RELATIONSHIP')
            previous.append(text);continue
        # Cross-sentence anaphora may refer only to an explicit nearby field.
        missing=bool(re.search(r'\b(?:empty|blank|unfilled|missing|unnamed|unspecified|not\s+(?:provided|named|entered|filled|supplied))\b',plain))
        requested=mandatory or bool(re.search(r'\b(?:by|titled|title\s+box|numeric\s+box|creator\s+value)\b',plain))
        if missing and requested and not (optional and not mandatory):
            target=fields or context_fields
            for f in target:
                add(f,'MISSING',None,a,b,'ledger.empty_required_operand','INCOMPLETE',representation='UNRESOLVED')
                break
            previous.append(text);continue
        # Aggregate semantics have a different owning entity than a work.
        aggregate=bool(re.search(r'\b(?:creator|author|writer)[ -](?:wide|level)\b|\bacross\s+(?:every|all|the\s+entire)\s+works?\b|\b(?:creator|author|writer)\b[^;]*\b(?:average|mean|median|sum|total|number\s+of)\b',plain))
        if aggregate and not (optional and not mandatory):
            add('aggregate','AGGREGATE',text.strip(),a,b,'ledger.entity_aggregate','UNSUPPORTED',representation='UNSUPPORTED');previous.append(text);continue
        # The native plan has conjunction/category exclusion, not XOR or word
        # distance operators. Preserve the requested operation as unsupported.
        operator=next((op for op,pattern in [('EXCLUSIVE_MEMBERSHIP',r'\bexclusive.membership\b|\bexactly\s+one\s+(?:of|tag)\b|\bone\s+of\s+(?:those|these|the)\s+two\s+tags\b'),
            ('PROXIMITY',r'\b(?:words?\s+apart|within\s+\d+\s+words?|proximity\s+(?:rule|condition|filter))\b')] if re.search(pattern,plain)),None)
        if operator and (mandatory or re.search(r'\b(?:exclude|include|qualif\w*|partition|precisely|filter|restrict)\b',plain)) and not re.match(r'\s*(?:books?\s+)?about\b',plain):
            add('relationship',operator,text.strip(),a,b,'ledger.unsupported_operator','UNSUPPORTED',representation='UNSUPPORTED');previous.append(text);continue
        previous.append(text)
    # Opaque quoted bibliographic operands with explicit owners.
    quote=r'["“]([^"”\n]*)["”]'
    patterns=[('author',r'\b(?:by\s+(?:(?:the\s+)?(?:exact\s+)?(?:(?:author|creator|writer)\s+)?name\s+|(?:the\s+)?(?:exact\s+)?(?:author|creator|writer)\s+)?|(?:author|creator|writer)(?:\s+name)?\s*(?::|=|is)\s*(?:exactly\s+)?)'+quote),
        ('title',r'\b(?:titled|called|named|(?:the\s+)?title\s+(?:is|equals))\s+(?:exactly\s+)?'+quote)]
    for field,pattern in patterns:
        for m in re.finditer(pattern,s.text):
            add(field,'CONTAINS',m[1],*m.span(),'ledger.literal_'+field,'SUPPORTED' if m[1].strip() else 'INCOMPLETE')
    # Canonical membership and literal whole-word predicates have distinct owners.
    for m in re.finditer(r'\b(?:exclude|excluding|reject|without)\s+(?:works?|books?|records?)\s+(?:tagged|labelled|labeled|classified)\s+'+quote,s.text):
        value,_,repair=vocab.resolve(m[1],fuzzy=True)
        add('excluded_subject' if value else 'subject_clause','NOT',value or m[1],*m.span(),'literal.explicit_field_owner','SUPPORTED' if value else 'UNSUPPORTED',
            'scoped canonical alias/typo resolution' if repair else None)
    words=[]
    for m in re.finditer(r'\b(include|exclude|excluding|reject)\s+(?:(?:a\s+)?match\s+of\s+)?(?:the\s+)?(?:whole[ -]word|exact\s+(?:word|phrase))\s+'+quote+r'(?:\s+from\s+searchable\s+text)?',s.text):
        words.append((m[1],m[2],m.span()))
    positives={value for op,value,_ in words if op=='include'}
    negatives={value for op,value,_ in words if op!='include'}
    for op,value,(a,b) in words:
        if value in positives&negatives:add('text_relationship','CONFLICT',value,a,b,'ledger.identical_text_domain','CONTRADICTORY',representation='RELATIONSHIP')
        elif op=='include':add('text_positive','CONTAINS_WORD',value,a,b,'ledger.positive_text_unsupported','UNSUPPORTED',representation='UNSUPPORTED')
        else:add('exclude','TEXT_NOT',value,a,b,'ledger.whole_word_exclusion')
    # Descriptive numeric boundaries require rating context within their clause.
    number=r'(-?\d+(?:\.\d+)?)'
    for a,b,text in spans:
        if not re.search(r'\brat(?:ing|ed)\b',outside(text)):continue
        for pattern,op in [(r'\b(?:rating\s+)?(?:minimum|floor)(?:\s+rating)?\s+(?:of\s+|is\s+|=\s*)?'+number+r'(?:\s*,?\s*inclusive)?','>='),
            (r'\b(?:rating\s+)?(?:maximum|ceiling)(?:\s+rating)?\s+(?:of\s+|is\s+|=\s*)?'+number+r'(?:\s*,?\s*inclusive)?','<='),
            (r'\brating\s+must\s+(?:reach|meet)\s+'+number,'>='),
            (r'\brating\s+of\s+'+number+r'\s+or\s+(?:greater|higher)','>=')]:
            for m in re.finditer(pattern,text):add('rating',op,float(m[1]),a+m.start(),a+m.end(),'ledger.descriptive_rating')
    for m in re.finditer(r'\b(?:sort|order)\s+(?:(?:the\s+)?(?:surviving\s+)?titles?|by\s+title)\s+(?:a\s+to\s+z|alphabetically|ascending)\b',s.text):
        add('sort','=','TITLE',*m.span(),'ledger.title_order')

def decorate(s):
    """Attach every final recognizer to an original owning clause."""
    cs=list(clauses(s.raw))
    for c in s.items:
        if c.owning_clause_span is None:
            c.owning_clause_span=next(([a,b] for a,b,_ in cs if a<=c.source_span_start<b),[c.source_span_start,c.source_span_end])
        if c.field=='preference':c.ownership='ADVISORY';c.representation='ADVISORY'
        elif c.field=='connector':c.representation='GRAMMAR'

def grammar(s):
    """Consume only bounded wrappers adjoining actual owned requirements."""
    for a,b,text in clauses(s.text):
        owned=[c for c in s.items if c.source_span_start>=s.span(a,b)[0] and c.source_span_end<=s.span(a,b)[1]]
        if not owned:continue
        chars=list(text)
        for c in owned:
            for j in range(a,b):
                if c.source_span_start<=s.offsets[j]<c.source_span_end:chars[j-a]=' '
        residue=''.join(chars)
        # These words introduce/display fields, never arbitrary topics.
        pattern=r'\b(?:the\s+catalogue\s+match|a\s+reading.list\s+entry|the\s+work\s+is|target\s+works?|use\s+works?|find\s+works?|for\s+works?|keep\s+works?|its\s+creator\s+filter\s+is|build\s+a\s+reading\s+shelf\s+from|delivery\s+is|and\s+carry|the\s+remaining\s+checks\s+are|apply\s+both\s+rating\s+checks\s+simultaneously|both\s+membership\s+checks\s+are\s+mandatory)\b'
        for m in re.finditer(pattern,residue):s.add_span('connector','GRAMMAR',None,a+m.start(),a+m.end(),'ledger.field_wrapper')
