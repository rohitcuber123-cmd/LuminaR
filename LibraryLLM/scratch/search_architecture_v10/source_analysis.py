"""Source-first structural obligations, separate from proposed plan fields.

This is a bounded language analysis, not a general completeness oracle. Domain
identity and negative relation ownership precede spelling repair. Coverage is
reported by source units, not by claiming that every character implies meaning.
"""
import re
from dataclasses import asdict
from .ontology import DOMAINS, supports
from scratch.search_v2c_c5er.candidate_search_v4.requirement_ledger import outside, clauses

NEG=r'\b(?:exclude|excluding|without|except|reject|forbid|not)(?!\s+only\b)\b'
META=r'\b(?:label|field\s+name|spelling|typo)\b'
FIX=r'\b(?:repair|correct|means|typo|spelling)\b'


def label_repairs(query):
    """Explicit quoted label + named canonical domain, never inferred fuzzy domain."""
    found=[]
    for a,b,text in clauses(query):
        if not ((re.search(META,outside(text),re.I) and re.search(FIX,outside(text),re.I)) or (re.search(r'\bwrote\b',outside(text),re.I) and re.search(META,query,re.I) and re.search(FIX,query,re.I))):continue
        quotes=list(re.finditer(r'"([^"\n]+)"|“([^”\n]+)”',text))
        for q in quotes:
            value=q[1] or q[2]
            if not re.fullmatch(r'[A-Za-z]{3,18}',value):continue
            tail=outside(text[q.end():])
            domains=[d for d in DOMAINS.values() if d.native and any(re.search(r'\b'+re.escape(label)+r'\b',tail,re.I) for label in d.labels)]
            domains={d.name:d for d in domains}
            if len(domains)!=1:continue
            d=next(iter(domains.values()))
            from scratch.search_v2c_c5er.candidate_search_v4.semantic_safety import distance_one
            canonical=next((s for s in d.labels if distance_one(value.casefold(),s.casefold())),None)
            if canonical:
                found.append({'from':value,'to':canonical,'kind':'explicit_label','domain':d.name,'source_span':[a+q.start(1 if q[1] is not None else 2),a+q.end(1 if q[1] is not None else 2)]})
    return found


def unsupported_relations(query):
    """Detect explicit unsupported metadata/relationships on original unmodified source."""
    from .source_units import references
    reference_spans=references(query)
    results=[]
    for a,b,text in clauses(query):
        visible=list(outside(text))
        for x,y in reference_spans:
            for i in range(max(a,x),min(b,y)):visible[i-a]=' '
        visible=''.join(visible)
        # A negative relative clause owns the referenced metadata value too.
        n=re.search(NEG,visible,re.I)
        for d in DOMAINS.values():
            if d.enforcement!='UNSUPPORTED':continue
            aliases='|'.join(re.escape(x) for x in d.labels)
            hit=re.search(r'\b(?:'+aliases+r')\b',visible,re.I)
            if hit and (n or re.search(r'\b(?:must|require\w*|mandatory|only|where|whose|with)\b',visible,re.I)):
                start=n.start() if n and n.start()<hit.start() else hit.start()
                results.append((a+start,b,d.name,'NEGATIVE_METADATA' if n else 'UNSUPPORTED_FIELD'))
        if re.search(r'\b(?:same|different)\s+(?:publication\s+)?year\b|\bwithin\s+(?:\d+|one|two|three|four|five)\s+words?\b',visible,re.I):
            # Bibliographic references inside the relationship are not target fields.
            start=re.search(r'\b(?:published|publication|titled|title)\b',visible,re.I)
            begin=min(n.start(),start.start()) if n and start else n.start() if n else start.start() if start else 0
            results.append((a+begin,b,'relationship','CROSS_BOOK_OR_PROXIMITY'))
        if n and re.search(r'\b(?:whose|lacking|having)\b',visible[n.end():],re.I) and not re.search(r'\b(?:word|text|phrase)\b',visible[n.end():],re.I):
            results.append((a+n.start(),b,'relationship','UNSUPPORTED_NEGATIVE_RELATION'))
    return results


def seed(source,put,facets):
    """Own complete source structures before independent scalar recognizers."""
    text=source.text
    from .source_units import frames
    from .source_roles import partition,governing,Modality
    role_units=partition(text)
    for f in frames(text):
        unit=governing(role_units,f.start,f.end)
        if unit and unit.modality in [Modality.NON_OPERATIVE,Modality.SHOULD,Modality.MAY]:continue
        if put(f.field,f.operator,f.value,f.start,f.end,f.status,f.rule) and f.field=='label_reference':
            source.items[-1].representation='CONTEXT'
    # Numeric negative algebra owns its domain before generic exclusions.
    from .numeric_proposals import recognize
    from scratch.search_v2c_c5er.candidate_search_v4.query_constraints import Source
    probe=Source(text);recognize(probe)
    from .source_roles import partition,governing,Modality
    units=partition(text)
    for c in probe.items:
        u=governing(units,c.source_span_start,c.source_span_end)
        if c.recognizer_id=='numeric.negated_boundary' and u and u.modality in [Modality.MUST,Modality.MUST_NOT]:
            put(c.field,c.operator,c.normalized_value,c.source_span_start,c.source_span_end,rid=c.recognizer_id)
    for a,b,domain,rule in unsupported_relations(text):
        put(domain,'NOT' if 'NEGATIVE' in rule else 'CROSS_BOOK',None,a,b,'UNSUPPORTED','source.structure.'+rule,extra={'original_domain':domain})
    # Explicit whole-word operator owns the entire optional source frame in
    # both missing and completed forms, stabilizing accepted-source edits.
    for m in re.finditer(r'\b(?:exclude|without|not)\s+(?:the\s+)?whole\s+word\s+(\[[^\]]*\]|["“][^"”]*["”])(?:\s+from\s+(?:the\s+)?searchable\s+text)?',text,re.I):
        arg=m[1];missing=arg.startswith('[') or not arg.strip('"“”').strip()
        put('exclude','SLOT' if missing else 'TEXT_NOT',None if missing else arg.strip('"“”'),*m.span(),'INCOMPLETE' if missing else 'SUPPORTED','source.whole_word')
    repairs=label_repairs(text)
    # Contextual label declarations are non-operative; their later operand can
    # inherit a domain only from exactly one explicit declaration.
    for a,b,t in clauses(text):
        plain=outside(t)
        if (re.search(META,plain,re.I) and re.search(FIX,plain,re.I)) or any(a<=r['source_span'][0]<b for r in repairs):
            field_cue=re.search(r'\b(?:titled|books?\s+by|rated|published|sort\s*:)\b',plain,re.I)
            stop=a+field_cue.start() if field_cue else b
            # A numeric/ordering predicate is still operative after its frame.
            operand=re.search(r'\b(?:use\s+a\s+minimum|order\s+alphabetically)\b',plain,re.I)
            if operand:stop=min(stop,a+operand.start())
            if stop>a and put('label_reference','DECLARATION',text[a:stop],a,stop,rid='source.label_declaration'):
                source.items[-1].representation='CONTEXT'
    repair_domains={r['domain'] for r in repairs}
    for a,b,t in clauses(text):
        plain=outside(t)
        # Explicit comparator algebra; operand boundaries are independent of
        # framing prose. A domain reference can be inherited only unambiguously.
        domain='rating' if len(repair_domains)==1 and 'rating' in repair_domains else None
        if domain:
            for m in re.finditer(r'\b(?:minimum|maximum)\s+(?:of\s+)?(\d+(?:\.\d+)?)\b',plain,re.I):
                put(domain,'>=' if m[0].startswith('minimum') else '<=',float(m[1]),a+m.start(),a+m.end(),rid='source.declared_domain_comparator')
        for m in re.finditer(r'\b(?:sort|order)\s*:\s*(title|rating|newest|relevance)\b|\border\s+alphabetically\s+(?:on|by)\s+(title)\b',plain,re.I):
            value=(m[1] or m[2]).upper()
            put('sort','=',value,a+m.start(),a+m.end(),rid='source.explicit_operation')
        # Exact literal input uses existing exact-title/identifier enforcement,
        # not a semantic similarity predicate or arbitrary searchable phrase.
        for m in re.finditer(r'\b(?:search|find|look)\s+for\s+["“]([^"”]+)["”]',t,re.I):
            put('literal','EXACT',m[1],a+m.start(),a+m.end(),rid='source.literal_request')
        # Alternatives remain a relationship rather than multiple conjunctive bounds.
        if re.search(r'\beither\b.+\bor\b',plain,re.I):
            domains=[d for d in ['rating','year','author','title','subject','format'] if any(re.search(r'\b'+re.escape(label)+r'\b',plain,re.I) for label in DOMAINS[d].labels)]
            if domains:put('relationship','ALTERNATIVE',{'fields':domains},a,b,'AMBIGUOUS','source.required_alternative')
        if re.search(r'\bwhether\b',plain,re.I) and re.search(r'\bmandatory\b',plain,re.I) and re.search(r'\bpreference\b',plain,re.I):
            put('relationship','ALTERNATIVE',{'fields':['preference']},a,b,'AMBIGUOUS','source.unresolved_modality')


def audit(ir):
    """Independent obligations are compared to represented supported domains.

    Background/advisory/topical units remain usable. Unknown mandatory intent
    safely blocks, while this bounded detector cannot certify arbitrary NLP.
    """
    from .source_roles import partition, Modality
    entries=[];violations=[]
    raw=ir.raw_query
    for unit in partition(raw):
        a,b=unit.span;text=raw[a:b];visible=outside(text)
        owned=[r for r in ir.requirements if r.source_span[0]<b and r.source_span[1]>a]
        states={r.state.value for r in owned}
        if unit.modality==Modality.NON_OPERATIVE:kind='BACKGROUND_NON_OPERATIVE'
        elif 'CONTRADICTORY_VALUE' in states:kind='CONTRADICTORY_REQUIREMENT'
        elif 'UNSUPPORTED_REQUIREMENT' in states:kind='UNSUPPORTED_OPERATION'
        elif 'AMBIGUOUS_ALTERNATIVE' in states:kind='UNRESOLVED_MANDATORY_RELATIONSHIP'
        elif states & {'EXPLICITLY_EMPTY','OMITTED_REQUIRED_VALUE','PLACEHOLDER_AWAITING_COMPLETION'}:kind='EXPLICIT_MISSING_INFORMATION'
        elif owned and all(r.ownership=='ADVISORY' for r in owned):kind='VALID_ADVISORY_CONTENT'
        elif any(r.field=='literal' for r in owned):kind='LITERAL_CONTENT'
        elif any(r.field in DOMAINS and r.field not in ['semantic','context','preference'] for r in owned):kind='RESOLVED_SUPPORTED_REQUIREMENT'
        elif owned:kind='SEMANTIC_RETRIEVAL_CONTENT'
        else:kind='UNKNOWN_UNCLASSIFIED'
        entry={'span':[a,b],'source_text':text,'classification':kind,'role':unit.role,'modality':unit.modality,'requirements':[r.requirement_id for r in owned],'independent_obligations':[]}
        if unit.modality not in [Modality.NON_OPERATIVE,Modality.SHOULD,Modality.MAY] and not re.search(META,visible,re.I):
            # Exact operation labels and mandatory field domains must be owned
            # by the same domain, not merely swallowed by semantic residue.
            for domain in ['sort','rating','year','publisher','price']:
                aliases='|'.join(re.escape(x) for x in DOMAINS[domain].labels)
                if not re.search(r'\b(?:'+aliases+r')\b',visible,re.I):continue
                operative=bool(re.search(r'\b(?:must|required?|mandatory|minimum|maximum|sort|order|exclude|whose|above|below|over|under|before|after|at\s+least|at\s+most)\b|[<>]=?',visible,re.I))
                if not operative:continue
                matches=[r for r in owned if r.field==domain or r.field=='sort' and domain in ['rating','year'] or r.field=='relationship' and r.state.value!='EXPLICITLY_SUPPLIED' or r.state.value=='UNSUPPORTED_REQUIREMENT']
                entry['independent_obligations'].append({'domain':domain,'represented':bool(matches)})
                if not matches:
                    violations.append({'span':[a,b],'domain':domain,'reason':'UNREPRESENTED_MANDATORY_SOURCE_DOMAIN','source_text':text})
        entries.append(entry)
    for a,b,domain,rule in unsupported_relations(raw):
        matches=[r for r in ir.requirements if r.state.value=='UNSUPPORTED_REQUIREMENT' and r.source_span[0]<=a<b<=r.source_span[1]]
        if not matches:violations.append({'span':[a,b],'domain':domain,'reason':'UNREPRESENTED_UNSUPPORTED_RELATION','source_text':raw[a:b]})
    from .source_units import frames
    from scratch.search_v2c_c5er.candidate_search_v4.query_plan import normalize
    for f in frames(raw):
        if f.field=='label_reference':continue
        unit=next((u for u in partition(raw) if u.span[0]<=f.start<f.end<=u.span[1]),None)
        if unit and unit.modality in [Modality.NON_OPERATIVE,Modality.SHOULD,Modality.MAY]:continue
        candidates=[r for r in ir.requirements if r.field==f.field and r.source_span[0]<=f.start<f.end<=r.source_span[1]]
        def equivalent(r):
            if r.state.value!='EXPLICITLY_SUPPLIED':return True
            return r.operator==f.operator and (normalize(r.value)==normalize(f.value) if isinstance(f.value,str) else r.value==f.value)
        if not any(equivalent(r) for r in candidates):
            violations.append({'span':[f.start,f.end],'domain':f.field,'reason':'LEXICAL_SOURCE_OBLIGATION_LOST','source_text':raw[f.start:f.end]})
    return {'version':1,'units':entries,'violations':violations,'complete_within_detected_obligations':not violations,
        'limitation':'Bounded independent domain/relationship detector; character coverage and internal proof do not establish arbitrary linguistic completeness.'}
