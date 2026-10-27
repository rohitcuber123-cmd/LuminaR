"""Source-backed requirement checks for the disabled SMART development parser.

No gold, benchmark IDs, models, application access, confidence cutoffs or IO.
Literal interiors remain opaque except to their explicit field owner.
"""
import re
from hashlib import sha256
from scratch.search_v2c_c5er.candidate_search_v4.requirement_ledger import clause_matches,clauses

VOCABULARY=('rated','rating','published','between','exactly','greater','less','least','most','above','below','after','before','online','digital','physical','titled','by','only','beginner','advanced','short','reference','exclude','and')
FIELD_CONTEXT=re.compile(r'\b(?:rat\w*|stars?|publish\w*|year|format|online|digital|physical|only|books?|titled|prefer|subject|category|record|containing)\b',re.I)

def distance_one(a,b):
    if a==b:return False
    if len(a)==len(b):
        indices=[i for i in range(len(a)) if a[i]!=b[i]]
        return len(indices)==1 or len(indices)==2 and indices[1]==indices[0]+1 and a[indices[0]]==b[indices[1]] and a[indices[1]]==b[indices[0]]
    if abs(len(a)-len(b))!=1:return False
    short,long=(a,b) if len(a)<len(b) else (b,a)
    return any(long[:i]+long[i+1:]==short for i in range(len(long)))

def quotes(text):return [m.span() for m in re.finditer(r'"[^"\n]*"|“[^”\n]*”',text)]
def outside_literals(text):
    chars=list(text)
    for a,b in quotes(text):chars[a:b]=' '*(b-a)
    return ''.join(chars)

def prepare(query):
    from scratch.search_v2c_c5er.candidate_search_v4.query_numeric import COMPARATOR_GROUPS,YEAR_COMPARATOR_GROUPS
    accepted_words={word for groups in [COMPARATOR_GROUPS,YEAR_COMPARATOR_GROUPS] for phrases in groups.values() for phrase in phrases for word in phrase.split()}
    accepted_words.update(['must','should','be','are','is','stay','remain','the','and','or','not','sort','sorts','title','titles','authors','author','words','records','required','optional','preference','preferred','preferences','exact','access','first','last'])
    protected=quotes(query);edits=[]
    for token in re.finditer(r'\b[a-zA-Z]{3,}\b',query):
        if any(token.start()<b and token.end()>a for a,b in protected):continue
        word=token[0].casefold()
        if word in VOCABULARY or word in accepted_words or word in ('title','year','only','format','subject','category','author','release','language'):continue
        from scratch.search_v2c_c5er.candidate_search_v4.requirement_ledger import clauses
        left,right,_=next(((a,b,t) for a,b,t in clauses(query) if a<=token.start()<b),(0,len(query),query))
        clause=query[left:right]
        if not FIELD_CONTEXT.search(clause):continue
        choices=[v for v in VOCABULARY if distance_one(word,v)]
        # Field words in ordinary about-topic prose are not repair candidates.
        if re.match(r'\s*(?:(?:find|show)\s+)?(?:books?\s+)?about\b',clause,re.I):continue
        if len(choices)!=1:continue
        value=choices[0]
        # Avoid short-name and ordinary-topic false repairs. Structural words
        # need their own field/unit evidence, not a generic book noun alone.
        if value in ['least','most','greater','less','between','exactly','above','below'] and not re.search(r'\brat\w*\b|\bstars?\b',clause,re.I):continue
        if value in ['online','digital','physical'] and not re.search(r'\b(?:only|format|version|copies)\b',clause,re.I):continue
        if value=='only' and not re.search(r'\b(?:online|digital|physical|format|copies)\b',clause,re.I):continue
        if value in ['beginner','advanced','short','reference'] and not re.search(r'\b(?:prefer|preference)\b',clause,re.I):continue
        if value=='exclude' and not re.match(r'\s*(?:every|any|all|subject|category|record)\b',query[token.end():right],re.I):continue
        if value=='and' and not (re.search(r'["”]\s*$',query[left:token.start()]) and re.match(r'\s*(?:subject|category|["“])',query[token.end():right],re.I)):continue
        if value=='by' and not re.fullmatch(r'\s*(?:(?:find|show)\s+)?books?\s+',query[left:token.start()],re.I):continue
        if value=='titled' and not re.match(r'\s*(?:exactly\s+)?["“]',query[token.end():right]):continue
        edits.append((token.start(),token.end(),value))
    chunks=[];offsets=[];repairs=[];cursor=0
    for a,b,value in edits:
        chunks.append(query[cursor:a]);offsets.extend(range(cursor,a));start=sum(map(len,chunks))
        chunks.append(value);offsets.extend(a+min(i,b-a-1) for i in range(len(value)))
        repairs.append({'from':query[a:b],'to':value,'start':a,'end':b,'prepared_start':start,'prepared_end':start+len(value),'kind':'bounded_grammar_repair'})
        cursor=b
    chunks.append(query[cursor:]);offsets.extend(range(cursor,len(query)))
    return ''.join(chunks),repairs,offsets

def finish(plan,original,prepared,repairs,offsets,facets,filters,omit):
    from scratch.search_v2c_c5er.candidate_search_v4.query_confidence import decide,validate,executable
    from scratch.search_v2c_c5er.candidate_search_v4.query_plan import normalize
    from scratch.search_v2c_c5er.candidate_search_v4.query_session import item_edit_key
    omit=set(omit);ledger=[];spans_are_original=False
    def omitted(field,value=None):
        alias={'author':'author','title':'title','subject':'subject','excluded_subject':'exclude','exclude':'exclude','format':'format'}
        if alias.get(field,field) in omit:return True
        if alias.get(field,field) in filters and filters[alias.get(field,field)] not in (None,''):return True
        if field=='subject' and item_edit_key('subject',value) in omit:return True
        if field in ['excluded_subject','exclude'] and item_edit_key('exclude',value) in omit:return True
        return False
    def add(field,status,reason,span=None,value=None):
        if not omitted(field,value):
            if span is None:a,b=0,len(original)
            elif spans_are_original:a,b=span
            else:
                x,y=span;a=offsets[x] if x<len(offsets) else len(original);b=offsets[y-1]+1 if y and y-1<len(offsets) else a
            owner=next(([x,y] for x,y,_ in clauses(original) if x<=a<y),[a,b])
            ledger.append({'field':field,'status':status,'reason':reason,'source_span':[a,b],'source_text':original[a:b],'value':value,
                'owning_clause_span':owner,'owning_clause':original[owner[0]:owner[1]],'ownership':'ADVISORY' if status=='ADVISORY' else 'MANDATORY',
                'capability':'UNSUPPORTED' if status=='UNSUPPORTED' else 'UNRESOLVED' if status in ['AMBIGUOUS','INCOMPLETE'] else 'SUPPORTED',
                'representation':'ADVISORY' if status=='ADVISORY' else 'UNRESOLVED' if status in ['AMBIGUOUS','INCOMPLETE'] else 'HARD_FILTER'})
    text=outside_literals(prepared).casefold()
    # A conditional/explanatory clause cannot inherit the executable status of
    # a recognized prefix when its mandatory grouping or referent is unresolved.
    for m in clause_matches(prepared):
        clause=m[0];plain=outside_literals(clause).casefold()
        if re.search(r'\b(?:include|exclude|subject|category)\b',plain) and re.search(r'\band\b',plain) and re.search(r'\bor\b',plain) and not re.search(r'[()]',plain):
            add('relationship','AMBIGUOUS','Mixed Boolean subject grouping has no explicit grouping.',list(m.span()))
    uncertain_pattern=r'\b(?:(?:cannot|can\s+not|can\x27t)\s+(?:tell|remember|read|decide|determine)|(?:do|does|have)\s+not\s+(?:know|decided|remember)|lost\s+whether)\b'
    parts=list(clause_matches(prepared))
    for index,m in enumerate(parts):
        plain=outside_literals(m[0]).casefold()
        if not re.search(uncertain_pattern,plain):continue
        context=outside_literals((parts[index-1][0]+'; ' if index else '')+m[0]).casefold()
        field=next((f for f,pattern in [('format',r'\b(?:online|digital|physical|access|format)\b'),('rating',r'\brat(?:ing|ed)\b|\bfloor\b'),('title',r'\btitle\b'),('author',r'\bauthor|writer\b'),('subject',r'\bsubject|category|exclu\w*\b')] if re.search(pattern,context)),None)
        alternatives=bool(re.search(r'\b(?:whether|either|joint|alternative\w*|which|tolerance|how\s+close|crossed.out)\b',context))
        # An unrelated remembered-author anecdote is discharged by a separate
        # explicit named author. A relative author reference is not discharged.
        explicit_named_author=bool(re.search(r'(?:^|;)\s*(?:books?\s+)?by\s+(?!the\s+author\b)[A-Z][^;]+',prepared))
        if field and alternatives and not (field=='author' and explicit_named_author and not re.search(r'\b(?:joint|either|slash|alternativ\w*)\b',context)):
            add(field,'AMBIGUOUS','The required field has unresolved alternatives, scope or reference evidence.',list(m.span()))
    # Explicit unresolved references are different from an optional anecdote.
    relational=re.search(r'\bby\s+(?:the|that|an?)\s+(?:author|writer|person)\b[^;]*',text)
    if relational:add('author','AMBIGUOUS','Mandatory author reference lacks a uniquely grounded name.',list(relational.span()))
    uncertainty=re.search(r'\b(?:cannot|can\s+not|can\x27t)\s+(?:tell|remember|read|decide|determine)\b',text)
    if uncertainty and re.search(r'\bwhether\b[^;]*(?:\bor\b|\bmodif\w*\b)|\b(?:joint|either|alternatives|intersection)\b',text):
        if re.search(r'\b(?:rating|author|writer|title|subject|category|format|year|published|minimum|maximum|preferably|excluding)\b',text):
            add('relationship','AMBIGUOUS','Unresolved alternatives affect mandatory field/operator/association ownership.',list(uncertainty.span()))
    if re.search(r'\b(?:lost|missing|unknown)\b[^;]*\b(?:parentheses|grouping)\b',text) and re.search(r'\b(?:not|exclude|excluding)\b[^;]*\bor\b',text):
        add('relationship','AMBIGUOUS','The negative group scope is explicitly unresolved.')
    field_words={'rating':r'\brat(?:ing|ings|ed)\b|\bstars?\b','year':r'\b(?:published|publication|year|released)\b',
                 'author':r'\b(?:by|author)\b','title':r'\b(?:titled|title)\b','language':r'\blanguage\b',
                 'availability':r'\b(?:available|availability|borrow)\b','subject':r'\b(?:include|subject|category|genre)\b',
                 'format':r'\b(?:format|physical|online|digital)\b','exclude':r'\b(?:exclude|excluding|text|word|phrase)\b'}
    for m in clause_matches(prepared):
        clause=m[0];outside=outside_literals(clause)
        if re.match(r'\s*(?:(?:find|show)\s+)?(?:books?\s+)?about\b',outside,re.I):continue
        placeholder=bool(re.search(r'\.{3}|…|_{2,}|\[\s*\]|["“]\s*["”]',clause))
        missing=bool(re.search(r'\b(?:missing|blank|unnamed|not\s+(?:supplied|entered|provided|specified|selected|finished|given|named)|have\s+not\s+(?:entered|supplied|named))\b',outside,re.I))
        if placeholder or missing:
            for field,pattern in field_words.items():
                if re.search(pattern,outside,re.I):add(field,'INCOMPLETE','Explicit mandatory field or operand is blank/unfinished.',list(m.span()))
    strict=re.compile(r'\b(?:require|requires|must|hard\s+filter|only)\b',re.I)
    unavailable={'pages':r'\b(?:pages?|page\s+count)\b','edition':r'\bedition\b','price':r'\b(?:price|cost|costing|purchase\s+price|dollar|rupee)\b',
                 'difficulty':r'\b(?:difficulty|reading\s+level|audience|machine.verified)\b','binding':r'\b(?:hardcover|paperback|binding)\b',
                 'copy_status':r'\b(?:per.copy|on\s+loan|another\s+reader|individual\s+cop(?:y|ies))\b'}
    for m in clause_matches(text):
        clause=m[0]
        if re.match(r'\s*(?:(?:find|show)\s+)?(?:books?\s+)?about\b',clause):continue
        if strict.search(clause):
            for field,pattern in unavailable.items():
                if re.search(pattern,clause):add(field,'UNSUPPORTED','Requested strict metadata/operation has no enforceable search capability.',list(m.span()))
    # Inventory all explicit mandatory clauses, not a list of benchmark fields.
    # If source-backed recognizers do not own a clause's content, do not silently
    # reinterpret that required content as an ordinary topic or known intent.
    for m in clause_matches(prepared):
        plain=outside_literals(m[0]);mandatory=re.search(r'\b(?:require|requires|must\s+be)\b',plain,re.I)
        if not mandatory:continue
        start=m.start()+mandatory.end();end=m.end();residue=list(prepared[start:end])
        for c in plan.constraint_candidates:
            a,b=c['source_span_start'],c['source_span_end']
            for i in range(max(start,a),min(end,b)):residue[i-start]=' '
        leftover=''.join(residue).strip(' ,.!?')
        leftover=re.sub(r'\b(?:books?|records?|the|a|an|and|but|both|versions?|formats?|as|hard|filter|enforced|mandatory)\b',' ',leftover,flags=re.I)
        if leftover.strip(' ,.!?'):
            add('requirement','UNSUPPORTED','Explicit mandatory clause contains content not owned by a supported field recognizer.',[start,end])
    operation=re.match(r'\s*(?:please\s+)?(?:borrow|return|reserve|delete|purchase|checkout|check\s+out|renew|transfer|update)\b',text)
    if operation:add('operation','UNSUPPORTED','This parser interprets catalogue searches, not account/inventory transactions.',list(operation.span()))
    # Candidate provenance and original offsets are restored after bounded repair.
    spans_are_original=True
    for c in plan.constraint_candidates:
        start,end=c['source_span_start'],c['source_span_end']
        relevant=[r for r in repairs if start<r['prepared_end'] and end>r['prepared_start']]
        if relevant:c['repair_provenance']='bounded unique one-edit field/operator repair: '+', '.join(r['from']+' -> '+r['to'] for r in relevant)
        a=offsets[start] if start<len(offsets) else len(original);b=offsets[end-1]+1 if end and end-1<len(offsets) else a
        c.update(source_span_start=a,source_span_end=b,source_text=original[a:b],source_query=original)
        if c['field']=='preference':
            add('preference','ADVISORY','Explicit preference does not authorize a hard filter.',[a,b],c.get('normalized_value'))
        elif c.get('support_status') in ['AMBIGUOUS','INCOMPLETE','UNSUPPORTED','CONTRADICTORY']:
            add(c['field'],c['support_status'],'Recognizer retained an unresolved mandatory clause.',[a,b],c.get('normalized_value'))
        elif c['field'] not in ['connector','preference']:
            field,value,op=c['field'],c.get('normalized_value'),c.get('operator');preserved=True
            if field in ['author','title','language']:
                actual=getattr(plan,{'author':'author_text','title':'title_text','language':'language'}[field])
                preserved=bool(normalize(value)) and (normalize(value) in normalize(actual) if field in ['author','title'] else normalize(value)==normalize(actual))
            elif field in ['subject','excluded_subject']:preserved=normalize(value) in set(map(normalize,plan.subjects if field=='subject' else plan.exclude_subjects))
            elif field=='format':
                expanded=lambda xs:{x for v in xs for x in (['ONLINE','PHYSICAL'] if v=='BOTH' else [v])}
                preserved=expanded([value]).issubset(expanded(plan.formats)) and (op!='ONLY' or value in plan.exclusive_formats)
            elif field=='excluded_format':preserved=value in plan.excluded_formats
            elif field=='exclude' and op=='TEXT_NOT':preserved=normalize(value) in set(map(normalize,plan.exclude_terms))
            elif field in ['rating','year']:
                from scratch.search_v2c_c5er.candidate_search_v4.query_numeric import valid_numeric_domain
                if any(not valid_numeric_domain(field,v) for v in (value if op=='RANGE' else [value])):
                    add(field,'UNSUPPORTED','Numeric operand is outside the established catalogue domain.',[a,b],value)
                    continue
                lo,hi=getattr(plan,field+'_min'),getattr(plan,field+'_max')
                if op=='RANGE':preserved=lo is not None and hi is not None and lo>=value[0] and hi<=value[1]
                elif op=='=':preserved=lo==hi==value
                elif op in ['>','>=']:preserved=lo is not None and (lo>value or lo==value and (op=='>=' or getattr(plan,field+'_min_exclusive')))
                elif op in ['<','<=']:preserved=hi is not None and (hi<value or hi==value and (op=='<=' or getattr(plan,field+'_max_exclusive')))
            add(field,'RESOLVED' if preserved else 'AMBIGUOUS','Source-backed candidate retained.' if preserved else 'Recognized required operand was lost or overwritten during composition.',[a,b],value)
    unresolved_fields={x['field'] for x in ledger if x['status'] in ['AMBIGUOUS','INCOMPLETE','UNSUPPORTED']}
    for requirement in ledger:
        requirement['ownership']='ADVISORY' if requirement['status']=='ADVISORY' else 'MANDATORY'
        if requirement['status']=='RESOLVED' and requirement['field'] in unresolved_fields:
            requirement['status']='UNRESOLVED_RELATIONSHIP'
            requirement['reason']='A recognized value does not resolve the field\x27s mandatory interpretation.'
    for s in plan.source_spans:
        a,b=s.get('start',0),s.get('end',0)
        start=offsets[a] if a<len(offsets) else len(original);end=offsets[b-1]+1 if b and b-1<len(offsets) else start
        s.update(start=start,end=end,text=original[start:end],source_query=original)
    plan.raw_query=original;plan.normalized_query=normalize(original)
    # A separate explicit topic clause is retained even alongside a title. Its
    # literal wording is never treated as a catalogue filter by this step.
    topics=[]
    for m in re.finditer(r';\s*(?:books?\s+)?about\s+([^;]+)',original,re.I):
        topics.append(m[1].strip(' .?!'))
    if topics and 'topic' not in omit:plan.semantic_text='; '.join(topics)
    elif plan.semantic_text:plan.semantic_text=re.sub(r'\s*;\s*','; ',plan.semantic_text).strip(' ;,') or None
    if plan.semantic_text and re.fullmatch(r'(?:(?:the|a|an|book|books|find|please)\s*)+',plan.semantic_text,re.I):plan.semantic_text=None
    repair_notices=[]
    for r in repairs:
        repair_notices.append({'from':r['from'],'to':r['to'],'source_span':[r['start'],r['end']],'kind':'bounded_grammar_repair'})
    for c in plan.constraint_candidates:
        if c['recognizer_id']=='literal.explicit_field_owner' and str(c.get('repair_provenance','')).startswith('scoped canonical'):
            literal=re.search(r'["“]([^"”]+)["”]',c['source_text'])
            if literal:
                correction={'from':literal[1],'to':c['normalized_value'],'kind':'typo' if 'typo' in c['repair_provenance'] else 'alias'}
                if correction not in plan.corrections:plan.corrections.append(correction)
                start=c['source_span_start']+literal.start(1)
                repair_notices.append({**correction,'source_span':[start,start+len(literal[1])]})
    plan.decision['repair_notices']=repair_notices
    # Cross-field constraints use the exact production normalization and word
    # boundaries; the earlier shadow substring counterexample stays executable.
    conflict=[]
    for term in plan.exclude_terms:
        literal=normalize(term)
        if literal and any(re.search(r'(?<!\w)'+re.escape(literal)+r'(?!\w)',normalize(getattr(plan,f) or '')) for f in ['author_text','title_text']):
            conflict.extend(['exclude_terms','author_text' if plan.author_text else 'title_text'])
    languages={normalize(c['normalized_value']) for c in plan.constraint_candidates if c['field']=='language' and c.get('support_status')=='SUPPORTED'}
    if len(languages)>1:conflict.append('language')
    checked=validate(plan)
    unresolved_relation=any(x['status']=='AMBIGUOUS' and x['field'] in ['relationship','author','title'] for x in ledger)
    if conflict and not (unresolved_relation and any(f in conflict for f in ['author_text','title_text'])):
        plan=decide(plan,'CONTRADICTORY','CROSS_FIELD_REQUIRED_EXCLUSION',fields=list(dict.fromkeys(conflict)))
    elif checked.decision.get('decision_type')=='CONTRADICTORY':plan=checked
    else:
        priority=next((status for status in ['CONTRADICTORY','INCOMPLETE','AMBIGUOUS','UNSUPPORTED'] if any(x['status']==status for x in ledger)),None)
        if priority:
            relevant=[x for x in ledger if x['status']==priority]
            plan=decide(plan,priority,'MANDATORY_'+priority,fields=sorted({x['field'] for x in relevant}),
                        unresolved=[{'field':x['field'],'reason':x['reason'],'source_span':x['source_span']} for x in relevant])
        elif executable(plan) and (repairs or any(c['recognizer_id']=='literal.explicit_field_owner' and c.get('repair_provenance') for c in plan.constraint_candidates)):
            plan=decide(plan,'EXECUTABLE_WITH_NOTICE','BOUNDED_GRAMMAR_REPAIR')
            if not any(c.get('repair_provenance') for c in plan.constraint_candidates):
                # A repaired cue with no recognized owner is not a resolved filter.
                plan=decide(plan,'INCOMPLETE','REPAIRED_REQUIREMENT_NOT_GROUNDED',fields=['requirement'])
    plan.decision['requirements']=ledger
    if plan.decision['decision_type']=='CONTRADICTORY':
        affected=plan.decision.get('affected_fields',[])
        aliases={'excluded_subject':'subject','exclude':'exclude_terms','author':'author_text','title':'title_text','excluded_format':'format'}
        for requirement in ledger:
            if requirement['status']=='RESOLVED' and aliases.get(requirement['field'],requirement['field']) in affected:
                requirement['status']='CONTRADICTORY'
                requirement['reason']='Resolved requirements conflict under the established predicate contract.'
    plan.decision['repair_notices']=repair_notices
    plan.decision['development_isolation']={'disabled_candidate':True,'native_authorization_required_externally':True,'confidence_is_probability':False}
    return plan
