"""Own modality, relationships and polarity before scalar proposal grammars."""
import re
from scratch.search_v2c_c5er.candidate_search_v4 import query_constraints as grammar
from scratch.search_v2c_c5er.candidate_search_v4.requirement_ledger import clauses,outside
from .vocabulary import FacetVocabulary
from .operands import scan_slots
from .source_roles import partition, Modality, Role

NEGATIVE=re.compile(r'\b(?:but\s+not|exclude|excluding|without|except|reject|forbid|disallow|not)(?!\s+only\b)\b')
Q=re.compile(r'"([^"\n]*)"|“([^”\n]*)”')
FIELD_WORDS={'author':r'\b(?:authors?|creators?|writers?|by)\b','title':r'\b(?:title|titled)\b',
    'subject':r'\b(?:subject|category|classification|facet|tag)\b','rating':r'\b(?:rating|rated|stars?|cutoff)\b',
    'year':r'\b(?:publication|published|year)\b','sort':r'\b(?:sort|order|ordering)\b','exclude':r'\b(?:exclude|exclusion|whole.word|negative)\b',
    'format':r'\b(?:format|online|physical|digital)\b','language':r'\blanguage\b'}

def front_end(text,facets):
    s=grammar.Source(text);parts=list(clauses(s.text));metadata={};vocab=FacetVocabulary(facets)
    def put(f,op,v,a,b,status='SUPPORTED',rid='ownership',literal=True,extra=None):
        if a>=b:return False
        x,y=s.span(a,b)
        if any(u<x<v for u,v in s.protected):return False
        if any(x<c.source_span_end and y>c.source_span_start for c in s.items):return False
        owner=next((s.span(u,w) for u,w,_ in parts if u<=a<w),(x,y))
        c=grammar.Candidate(f,op,v,x,y,s.raw[x:y],rid,support_status=status,owning_clause_span=list(owner),
            ownership='ADVISORY' if f=='preference' else 'MANDATORY',representation='ADVISORY' if f=='preference' else 'HARD_FILTER')
        s.items.append(c);metadata[(x,y,f)]=extra or {};return True
    # Speech acts and local modality own their intervals before field grammars.
    for unit in partition(text):
        a,b=unit.span
        if unit.modality in (Modality.SHOULD,Modality.MAY):
            put('preference','SOFT',text[a:b].strip(),a,b,rid='roles.'+unit.rule)
        elif unit.modality==Modality.NON_OPERATIVE:
            if put('context','NON_OPERATIVE',text[a:b],a,b,rid='roles.'+unit.rule):s.items[-1].ownership='NON_OPERATIVE';s.items[-1].representation='CONTEXT'
        elif unit.modality in (Modality.CONDITIONAL,Modality.UNKNOWN) and unit.role==Role.CORRECTION:
            put('relationship','SOURCE_EDIT',None,a,b,'AMBIGUOUS','roles.correction_requires_choice')
        elif unit.modality==Modality.CONDITIONAL:
            put('relationship','CONDITIONAL',None,a,b,'UNSUPPORTED' if re.search(r'\b(?:else|otherwise)\b',outside(text[a:b]),re.I) else 'AMBIGUOUS','roles.conditional')
        elif unit.modality==Modality.UNKNOWN and unit.rule=='segment.unresolved_association':
            fields=[f for f,p in FIELD_WORDS.items() if re.search(p,outside(text[a:b]),re.I)]
            if not fields:
                a,b=unit.clause_span
                fields=[f for f,p in FIELD_WORDS.items() if re.search(p,outside(text[a:b]),re.I)]
            put('relationship','ALTERNATIVE',{'fields':fields},a,b,'AMBIGUOUS','roles.unresolved_association')
        elif re.search(r'\b(?:per|for\s+each)\s+(?:author|creator|writer|category|subject)\b|\bgroup(?:ed)?\s+by\b',outside(text[a:b]),re.I):
            put('aggregate','GROUP_CARDINALITY',text[a:b],a,b,'UNSUPPORTED','roles.group_operation')
    # Advisory ownership comes first and is local to its grammatical segment.
    for a,b,t in parts:
        plain=outside(t)
        if re.search(r'\b(?:prefer\w*|optional|advisory)\b',plain) and not re.search(r'\b(?:require\w*|must|mandatory|strict)\b',plain):
            cue=re.search(r'\b(?:prefer\w*|optional|advisory)\b',plain)
            start=cue.start() if re.fullmatch(r'prefer|preferably',cue[0]) else 0
            # A suffix modifier after a comma owns that segment, not an
            # independently supplied bibliographic/filter clause before it.
            commas=[m.start() for m in re.finditer(',',plain[:cue.start()])]
            if start==0 and commas and any(re.search(p,plain[:commas[-1]]) for p in FIELD_WORDS.values()):start=commas[-1]+1
            boundary=re.search(r'\b(?:and|but)\s+(?=(?:require|must|by|titled|rated|published|exclude|include)\b)',plain[start:])
            end=start+boundary.start() if boundary else len(t)
            put('preference','SOFT',t[start:end].strip(),a+start,a+end,rid='ownership.advisory')
        # Resolve field assignment/domain ambiguity as a relationship before
        # words naming fields can be mistaken for dangling operand introducers.
        pending=re.search(r'\b(?:undecided|unresolved|unsettled|pending|uncertain|unsure|not\s+(?:chosen|decided)|yet\s+to\s+(?:choose|decide|pick)|cannot\s+(?:tell|remember))\b',plain)
        relation=re.search(r'\b(?:assignment|domain|between|either|whether|which|choice|alternatives?|direction|slots?|one\s+each)\b',plain)
        nearby=' '.join(z for _,_,z in parts[max(0,parts.index((a,b,t))-1):parts.index((a,b,t))+1])
        if pending and (relation or any(re.search(p,outside(nearby)) for p in FIELD_WORDS.values()) or re.search(r'\bfield\b',plain)):
            previous=parts[max(0,parts.index((a,b,t))-1):parts.index((a,b,t))+1]
            context=' '.join(z for _,_,z in previous)
            fields=[f for f,p in FIELD_WORDS.items() if re.search(p,outside(context))]
            put('relationship','ALTERNATIVE',{'fields':fields},a,b,'AMBIGUOUS','ownership.relationship',extra={'fields':fields})
        # Metalinguistic absence requires a field/operand role, not an entity
        # value that happens to contain Empty or Missing.
        if re.search(r'\b(?:slot|box|operand|value|quote|rest|remainder|remaining)\b',plain) and re.search(r'\b(?:blank|empty|unfilled|missing|unfinished|omitted|not\s+(?:provided|supplied|entered))\b',plain):
            fields=[f for f,p in FIELD_WORDS.items() if re.search(p,plain)]
            put(fields[0] if fields else 'requirement','MISSING',None,a,b,'INCOMPLETE','ownership.missing_role')
    for slot in scan_slots(s.text):
        put(slot.field,'SLOT',None,slot.start,slot.end,'INCOMPLETE','ownership.structural_slot',extra={'slot_state':slot.state.value})
    # A literal owner consumes the entire quoted operand before keywords inside
    # that operand are considered. This uses the existing contains contract.
    for m in re.finditer(r'\btitle\s+(?:containing|contains)\s+(?:(?:the\s+)?(?:words?|phrase)\s+)?["“]([^"”]*)["”]',s.text):
        put('title','CONTAINS',m[1],*m.span(),'SUPPORTED' if m[1].strip() else 'INCOMPLETE','ownership.literal_contains')
    for m in re.finditer(r'\blanguage\s*(?:(?:is|must\s+be|[:=])\s*)?["“]([^"”]*)["”]',s.text):
        put('language','EXACT',m[1],*m.span(),'SUPPORTED' if m[1].strip() else 'INCOMPLETE','ownership.literal_language')
    # Polarity and target-domain ownership precede positive entity/category
    # grammars. An unsupported domain remains unsupported, never broad text.
    visible=s.remaining(protect=True)
    for index,(a,b,t) in enumerate(parts):
        for m in NEGATIVE.finditer(visible[a:b]):
            start=a+m.start();operand_start=a+m.end()
            prefix=outside(s.text[a:start])
            if grammar.topical_not(visible,start) or re.search(r'\b(?:about|on)\b',prefix) and not re.search(r'\b(?:require|must|mandatory)\b',prefix):continue
            from .numeric_proposals import REQUEST_CUES
            if any(re.search(p+r'$',prefix) for p in REQUEST_CUES.values()):continue
            # Numeric negation belongs to the comparator algebra, not a text exclusion.
            if re.match(r'\s*(?:above|below|over|under|more|less|greater|fewer)\b',s.text[operand_start:b]) and re.search(r'\brat(?:ing|ed)\b',prefix):continue
            end=b
            tail=s.text[operand_start:end]
            # Commas and explicit following positive fields bound an operator.
            boundary=re.search(r',|\s+(?=(?:rated|rating|published)\b)|\s+(?:and|but)\s+(?=(?:by|titled|rated|published|include|require|sort)\b)',outside(tail))
            if boundary:end=operand_start+boundary.start();tail=s.text[operand_start:end]
            if not tail.strip():put('exclude','MISSING',None,start,end,'INCOMPLETE','ownership.negative');continue
            if re.search(r'\[[^\]]*\]|<[^>]*>|\.{3}|…|__',outside(tail)):
                put('exclude','SLOT',None,start,end,'INCOMPLETE','ownership.negative_slot');continue
            plain=outside(tail);quotes=list(Q.finditer(tail));value=(quotes[0][1] if quotes[0][1] is not None else quotes[0][2]) if quotes else None
            head=plain[:quotes[0].start()] if quotes else plain
            tokens=set(re.findall(r'\w+',head))
            text_domain=bool(tokens & {'word','text','phrase','searchable'})
            bib_domain=bool(tokens & {'author','authors','creator','creators','writer','writers','by','title','titled'})
            category_domain=bool(tokens & {'subject','category','classification','facet','tag','tagged','classified','labeled','labelled'})
            format_domain=bool(tokens & {'online','digital','physical'})
            if text_domain and not bib_domain:
                if value is None:
                    value=re.sub(r'\b(?:the|a|an|whole|word|searchable|text|phrase)\b',' ',tail).strip(' -:')
                put('exclude','TEXT_NOT',value,start,end,'SUPPORTED' if value else 'INCOMPLETE','ownership.negative_text')
            elif bib_domain:put('negative_domain','NOT',tail.strip(),start,end,'UNSUPPORTED','ownership.negative_entity')
            elif format_domain and not category_domain:
                fmt='PHYSICAL' if 'physical' in tokens else 'ONLINE'
                put('excluded_format','NOT',fmt,start,end,rid='ownership.negative_format')
            elif re.search(r'\b(?:available|availability|borrow|loan|requestable)\b',head):
                if re.search(r'\bavailable\s+now\b',prefix):put('relationship','CONFLICT',None,a,b,'CONTRADICTORY','ownership.availability_conflict')
                else:put('negative_domain','NOT',tail.strip(),start,end,'UNSUPPORTED','ownership.negative_availability')
            else:
                term=value or re.sub(r'^\s*(?:the\s+)?(?:subject|category|classification)\s+','',tail).strip(' .')
                term=re.sub(r'^\s*(?:the|a|an|any)\s+','',term)
                # Grammatical heads are not category operands. Resolve only
                # the complete domain-owned operand, never a noun prefix.
                term=re.sub(r'\s+(?:classification|category|subject)\s*$','',term).strip()
                if re.match(r'^about\s+',term):
                    put('exclude','TEXT_NOT',re.sub(r'^about\s+','',term),start,end,rid='ownership.negative_content');continue
                resolved,_,repair=vocab.resolve(term,True)
                if not resolved and category_domain and not quotes:
                    for w in reversed(list(re.finditer(r'\S+',term))):
                        suffix=term[w.end():].strip()
                        if suffix and not all(x in {'for','every','each','hit','work','book','record'} for x in re.findall(r'\w+',suffix)):continue
                        resolved,_,repair=vocab.resolve(term[:w.end()],True)
                        if resolved:break
                if resolved:
                    put('excluded_subject','NOT',resolved,start,end,rid='ownership.negative_category',extra={'correction':repair})
                elif category_domain:put('negative_domain','NOT',tail.strip(),start,end,'UNSUPPORTED','ownership.negative_unknown_field')
                elif quotes or re.fullmatch(r'[\w -]{1,60}',term):put('exclude','TEXT_NOT',term,start,end,rid='ownership.negative_literal')
                else:put('negative_domain','NOT',tail.strip(),start,end,'UNSUPPORTED','ownership.negative_unrepresented')
    # Declarative language has a field value and a copula; 'is' is never value.
    for a,b,t in parts:
        for pat in [r'\b([a-z][a-z-]+)\s+language\s+is\s+(?:mandatory|required)',r'\blanguage\s+(?:is|must\s+be|[:=])\s+([a-z][a-z-]+)']:
            for m in re.finditer(pat,t):put('language','EXACT',m[1],a+m.start(),a+m.end(),rid='ownership.language')
    # Sorting is an operation family, not an incidental token in free text.
    for m in re.finditer(r'\b(?:sort|order)\s+(?:(?:on|by)\s+)?(?:the\s+)?(highest\s+rating|rating|titles?|newest|relevance)\b(?:\s+(?:ascending|first|a\s+to\s+z))?',s.text):
        put('sort','=',{'highest rating':'RATING','rating':'RATING','title':'TITLE','titles':'TITLE','newest':'NEWEST','relevance':'RELEVANCE'}[m[1]],*m.span(),rid='ownership.sort')
    # Reuse established pure relationship/aggregate/descriptive-numeric
    # recognizers as proposals, without calling their plan/decision fallback.
    from scratch.search_v2c_c5er.candidate_search_v4.requirement_ledger import own
    proposed=grammar.Source(text);own(proposed,facets)
    for c in proposed.items:
        if c.field not in ['relationship','aggregate','text_relationship','text_positive','rating','year','sort']:continue
        if not any(c.source_span_start<x.source_span_end and c.source_span_end>x.source_span_start for x in s.items):s.items.append(c)
    for a,b,t in parts:
        if re.search(r'\b(?:mean|median|average|sum|total|count)\b',outside(t)) and re.search(r'\b(?:all|every|matching|across|result)\b',outside(t)):
            put('aggregate','AGGREGATE',t,a,b,'UNSUPPORTED','ownership.aggregate')
    from .numeric_proposals import recognize,finalize
    recognize(s)
    grammar.ratings(s);grammar.years(s)
    finalize(s)
    return s,metadata
