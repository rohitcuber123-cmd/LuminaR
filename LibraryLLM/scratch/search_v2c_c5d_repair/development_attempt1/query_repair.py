"""Compose recognized spans with the accepted facet/intent parser."""
from dataclasses import asdict
import re
from scratch.search_v2c_c5d_repair.candidate_search.query_constraints import recognize,comparator,topical_not
from scratch.search_v2c_c5d_repair.candidate_search.query_confidence import decide,validate

def annotate(plan,s,facets):
    from scratch.search_v2c_c5d_repair.candidate_search.query_plan import FacetVocabulary,normalize
    vocab=FacetVocabulary(facets)
    for subject in plan.subjects:
        keys=[normalize(subject),*(a for a,target in vocab.aliases.items() if target==normalize(subject))]
        keys += [normalize(c['from']) for c in plan.corrections if c.get('to')==subject]
        for key in keys:
            pattern=r'(?<!\w)'+r'[-\s]+'.join(re.escape(w) for w in key.split())+r'(?!\w)'
            found=next((m for m in re.finditer(pattern,s.text) if s.free(*m.span())),None)
            if found:
                s.add('subject','EXACT',subject,found,'subject.scoped_vocabulary');break
    plan.constraint_candidates=[dict(asdict(c),source_query=s.raw) for c in sorted(s.items,key=lambda c:c.source_span_start)]
    plan.source_spans=[{'kind':'CANONICAL_FACET' if c.field in ('subject','excluded_subject') else 'GRAMMATICAL_CONNECTOR' if c.field=='connector' else 'UNRESOLVED_CONSTRAINT_CUE' if c.field=='subject_clause' else 'CANONICAL_ENTITY' if c.field in ('author','title') else 'STRUCTURED_CONSTRAINT',
      'start':c.source_span_start,'end':c.source_span_end,'text':c.source_text,'recognizer_id':c.recognizer_id} for c in s.items]
    for m in re.finditer(r'\S+',s.remaining()):
        a,b=s.span(*m.span())
        plan.source_spans.append({'kind':'GRAMMATICAL_CONNECTOR' if m[0] in ('books','book','about','with','and','of','in','the','please') else 'SEMANTIC_TOPIC',
          'start':a,'end':b,'text':s.raw[a:b]})
    for a,b in s.protected:plan.source_spans.append({'kind':'SEMANTIC_TOPIC','start':a,'end':b,'text':s.raw[a:b],'protected_literal':True})
    return plan

def _compose(query,facets,legacy,filters,omit):
    s=recognize(query,facets)
    remaining=s.remaining(protect=False)
    # Quoted spans are opaque to the legacy facet/constraint grammar.
    literals={}
    for i,(a,b) in reversed(list(enumerate(s.protected))):
        if not any(a<c.source_span_end and b>c.source_span_start for c in s.items):
            quoted=query[a:a+1] in ('"','“')
            key=f'quotedliteral{i}token';literals[key]=query[a+1:b-1] if quoted else query[a:b].casefold()
            indices=[j for j,n in enumerate(s.offsets) if a<=n<b]
            if indices:remaining=remaining[:indices[0]]+key+remaining[indices[-1]+1:]
    # Remove only grammatical wrappers, not general stopwords or numbers.
    remaining=re.sub(r'\b(?:available|copies|read digitally|i can read|with physical copies)\b',' ',remaining)
    if any(c.field=='availability' for c in s.items):remaining=re.sub(r'\bi can\b',' ',remaining)
    remaining=re.sub(r'\b(?:in the|in)\s+(.+?)\s+category\b',r'\1 books',remaining)
    remaining=re.sub(r'\bnovels\b','books',remaining)
    remaining=' '.join(remaining.split()).strip(' ,;')
    remaining=re.sub(r'^[,;:\s]+|[,;:.\s]+$','',remaining)
    remaining=re.sub(r'\b(?:with|and)\s*$','',remaining).strip()
    if any(c.field=='format' for c in s.items):remaining=re.sub(r'^of\s+','',remaining)
    missing_pattern=r'\b(?:(?:ratings?|rated)\s*(?:above|below|of|at least|at most|greater than|less than|no more than|no less than|[<>]=?|[≥≤])?|(?:rating\s+)?between\s+\d+(?:\.\d+)?\s+and|from\s+\d{4}\s+to|at\s+(?:least|most)|(?:published|released|publication\s+year)\s+(?:after|before|since)|books?\s+(?:written\s+)?by|written\s+by|books?\s+titled|under\s+pages|not|only)\s*$'
    missing=re.search(missing_pattern,s.remaining().rstrip(' .?!;,\t'))
    if missing and any(end>s.span(*missing.span())[1] for _,end in s.protected):missing=None
    if missing and missing[0].strip()=='not' and topical_not(s.text,missing.start()):missing=None
    if missing:
        # Remove a known unfinished cue before entity/facet resolution; the
        # original cue and offsets remain in the typed INCOMPLETE decision.
        remaining=re.sub(missing_pattern,'',remaining).strip()
    # Repair resolved whole phrases before legacy parsing; ensure every hard
    # field is later assigned exclusively from candidates or explicit controls.
    preference=next((c.normalized_value for c in s.items if c.field=='preference' and c.normalized_value.startswith(('Introductory','Advanced'))),None)
    intent_prefix='learn ' if preference and preference.startswith('Introductory') else 'research material about ' if preference else ''
    plan=legacy(intent_prefix+remaining,facets,'SMART',{},(),recognize_constraints=False)
    plan.raw_query=query;plan.normalized_query=__import__('scratch.search_v2c_c5d_repair.candidate_search.query_plan',fromlist=['normalize']).normalize(query)
    if not plan.subjects:
        from scratch.search_v2c_c5d_repair.candidate_search.query_plan import FacetVocabulary,normalize
        numeric_suffix=re.fullmatch(r'(.+?)\s+\d+(?:\.\d+)?',normalize(remaining))
        if numeric_suffix:
            subject,_,_=FacetVocabulary(facets).resolve(numeric_suffix[1],fuzzy=False)
            if subject:plan.subjects=[subject]
    for key,value in literals.items():
        if plan.semantic_text:plan.semantic_text=plan.semantic_text.replace(key,value)
    plan.constraint_candidates=[dict(asdict(c),source_query=query) for c in sorted(s.items,key=lambda c:c.source_span_start)]
    plan.source_spans=[{'kind':'STRUCTURED_CONSTRAINT' if c.field not in ('author','title','exclude','preference') else 'CANONICAL_ENTITY' if c.field in ('author','title') else 'SEMANTIC_TOPIC' if c.field=='preference' else 'STRUCTURED_CONSTRAINT',
       'start':c.source_span_start,'end':c.source_span_end,'text':c.source_text,'recognizer_id':c.recognizer_id} for c in s.items]
    for c in s.items:
        if c.support_status!='SUPPORTED':continue
        field,op,value=c.field,c.operator,c.normalized_value
        if field in ('rating','year'):
            bounds=[('min',value[0],False),('max',value[1],False)] if op=='RANGE' else [('min' if op in ('>','>=') else 'max',value,op in ('>','<'))] if op!='=' else [('min',value,False),('max',value,False)]
            for side,v,exclusive in bounds:
                key=field+'_'+side;prior=getattr(plan,key)
                # Conjunction takes the strongest bound, independent of order.
                stronger=prior is None or (v>prior if side=='min' else v<prior)
                if stronger:setattr(plan,key,v);setattr(plan,key+'_exclusive',exclusive)
                elif v==prior:setattr(plan,key+'_exclusive',getattr(plan,key+'_exclusive') or exclusive)
        elif field=='format':
            if op=='ONLY':plan.exclusive_formats.append(value)
            plan.formats.append(value)
        elif field=='excluded_format':plan.excluded_formats.append(value)
        elif field=='availability':
            plan.availability='AVAILABLE_NOW' if value=='PHYSICAL_NOW' else 'REQUESTABLE' if value=='PHYSICAL_REQUESTABLE' else value
            if value in ('PHYSICAL_NOW','PHYSICAL_REQUESTABLE'):
                plan.physical_available_only=True
                if not plan.formats:plan.formats=['PHYSICAL']
        elif field=='author':plan.author_text=value
        elif field=='language':plan.language=value
        elif field=='title':plan.title_text=value
        elif field=='subject':plan.subjects.append(value);plan.include_terms.append(value)
        elif field=='excluded_subject':
            plan.exclude_subjects.append(value)
        elif field=='exclude':
            from scratch.search_v2c_c5d_repair.candidate_search.query_plan import FacetVocabulary
            if op=='TEXT_NOT':
                plan.exclude_terms.append(value)
                continue
            for term in re.split(r'\s*(?:,|\band\b|\bor\b)\s*',value)[:5]:
                subject,_,_=FacetVocabulary(facets).resolve(term,fuzzy=False)
                if subject:plan.exclude_subjects.append(subject)
                else:plan.exclude_terms.append(term)
        elif field=='include':
            from scratch.search_v2c_c5d_repair.candidate_search.query_plan import FacetVocabulary
            subject,_,_=FacetVocabulary(facets).resolve(value,fuzzy=False)
            if subject:plan.subjects.append(subject);plan.include_terms.append(subject)
        elif field=='sort':plan.sort=value
        elif field=='preference':
            plan.soft_preference=value
            if value.startswith('Introductory'):plan.intent='LEARN'
            elif value.startswith('Advanced'):plan.intent='RESEARCH'
    plan.formats=list(dict.fromkeys(plan.formats))
    for field in ('subjects','include_terms','exclude_terms','exclude_subjects'):
        setattr(plan,field,list(dict.fromkeys(getattr(plan,field))))
    # Explicit "not physical" is a format exclusion, not a title-word test.
    for term in list(plan.exclude_terms):
        if term in ('physical','online','digital'):
            plan.excluded_formats.append('PHYSICAL' if term=='physical' else 'ONLINE');plan.exclude_terms.remove(term)
    from scratch.search_v2c_c5d_repair.candidate_search.query_session import explicit_filters,omit_fields
    explicit_filters(plan,{k:v for k,v in filters.items() if v is not None and v!='' and not(k=='sort' and v=='RELEVANCE')});omit_fields(plan,omit)
    if plan.author_text:plan.intent='FIND_AUTHOR'
    elif plan.title_text or plan.exact_text:plan.intent='FIND_EXACT'
    elif plan.availability:plan.intent='FIND_AVAILABLE'
    elif 'ONLINE' in plan.formats or 'BOTH' in plan.formats:plan.intent='FIND_ONLINE'
    elif (plan.subjects or plan.exclude_subjects) and not plan.semantic_text:plan.intent='BROWSE_CATEGORY'
    annotate(plan,s,facets)
    checked=validate(plan)
    if checked.decision.get('decision_type')=='CONTRADICTORY':return checked
    ambiguous_clauses=[c for c in s.items if c.support_status=='AMBIGUOUS']
    if ambiguous_clauses:
        return decide(plan,'AMBIGUOUS','UNRESOLVED_NEGATION_SCOPE',fields=['subject','exclusion'],
                      spans=[{'start':c.source_span_start,'end':c.source_span_end} for c in ambiguous_clauses],
                      unresolved=[c.source_text for c in ambiguous_clauses])
    unfinished=[c for c in s.items if c.support_status=='INCOMPLETE']
    if unfinished:
        return decide(plan,'INCOMPLETE','MISSING_SUBJECT_CLAUSE_VALUE',fields=['excluded_subject' if any(c.normalized_value in ('exclude','excluding') and 'subject' in c.source_text for c in unfinished) else 'subject'],
                      spans=[{'start':c.source_span_start,'end':c.source_span_end} for c in unfinished],
                      unresolved=[c.source_text for c in unfinished])
    unsupported=[c for c in s.items if c.support_status!='SUPPORTED']
    if unsupported:return validate(decide(plan,'UNSUPPORTED','UNSUPPORTED_STRICT_FIELD',fields=[c.field for c in unsupported]))
    from scratch.search_v2c_c5d_repair.candidate_search.query_numeric import valid_numeric_domain
    for field in ('rating','year'):
        if any(v is not None and not valid_numeric_domain(field,v) for v in (getattr(plan,field+'_min'),getattr(plan,field+'_max'))):
            setattr(plan,field+'_min',None);setattr(plan,field+'_max',None)
            return decide(plan,'UNSUPPORTED','OUT_OF_RANGE_'+field.upper(),fields=[field])
    # Only unconsumed source cues are guarded. Protected literals, numeric title
    # fragments and historical semantic clauses are never globally stripped.
    residue=s.remaining()
    if missing:
        a,b=s.span(*missing.span());frag=query[a:b]
        plan.source_spans.append({'kind':'UNRESOLVED_CONSTRAINT_CUE','start':a,'end':b,'text':frag})
        if plan.semantic_text:
            plan.semantic_text=re.sub(r'\b(?:rating|rated|above|below|written|by|published|after|before|under|pages|not)\b',' ',plan.semantic_text).strip() or None
        field='rating_max' if re.search(r'between',frag) else 'rating' if re.search(r'rat(?:ing|ed)',frag) else 'year' if re.search(r'publish|release|publication',frag) else 'author' if re.search(r'\bby\b',frag) else 'title' if 'titled' in frag else 'pages' if 'pages' in frag else 'format_or_subject' if frag.strip()=='only' else 'exclusion'
        return decide(plan,'INCOMPLETE','MISSING_CONSTRAINT_VALUE',spans=[{'start':a,'end':b}],fields=[field],unresolved=[frag])
    malformed=re.search(r'\b(?:(?:ratings?|rated)\s*(?:above|below|of|at least|at most|greater than|less than|more than|[<>]=?|[≥≤])|(?:published|released)\s+(?:after|before|since))\s*\S*',residue)
    if malformed:
        a,b=s.span(*malformed.span())
        return decide(plan,'INCOMPLETE','INVALID_CONSTRAINT_VALUE',spans=[{'start':a,'end':b}],fields=['year' if re.search(r'publish|release',malformed[0]) else 'rating'],unresolved=[query[a:b]])
    technical=bool(re.search(r'\b(?:python|windows|dune)\s+\d+\b|\bcatch-\d+\b|\bc(?:\+\+|#)|three-body',residue))
    topical_number=bool(re.search(r'\b(?:number|events?|history|century|war|era)\b',residue))
    ambiguous=re.search(r'(?<![\w-])\d+(?:\.\d+)?(?![\w-])',residue)
    if ambiguous and not technical and not topical_number and not re.fullmatch(r'\s*\d{4}(?::.*)?\s*',residue) and not plan.exact_text:
        a,b=s.span(*ambiguous.span())
        plan.source_spans.append({'kind':'AMBIGUOUS_SPAN','start':a,'end':b,'text':query[a:b]})
        return decide(plan,'AMBIGUOUS','NUMBER_WITHOUT_FIELD',spans=[{'start':a,'end':b}],unresolved=[query[a:b]])
    return validate(decide(plan))

def compose(query,facets,legacy,filters,omit):
    from scratch.search_v2c_c5d_repair.candidate_search.semantic_safety import prepare,finish
    prepared,repairs,offsets=prepare(query)
    plan=_compose(prepared,facets,legacy,filters,omit)
    return finish(plan,query,prepared,repairs,offsets,facets,filters,omit)
