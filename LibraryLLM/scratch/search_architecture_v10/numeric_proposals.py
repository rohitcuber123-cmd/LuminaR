"""Postfix comparators on explicitly named numeric fields."""
import re

REQUEST_CUES={
    'rating':r'\brat(?:ing|ed)\s+(?:(?:must|should)\s+)?(?:be\s+)?(?:at\s+least|at\s+most|above|below|over|under|greater\s+than|less\s+than|exceed|>=|<=|>|<|=)\s*',
    'year':r'\b(?:published|publication\s+year)\s+(?:after|before|in|from|>=|<=|>|<|=)\s*'}
def recognize(source):
    # Complement of a closed numeric boundary is an open boundary, retaining
    # domain and polarity instead of converting numeric negation to text.
    inverse={'below':'>','less':'>','lower':'>','above':'<','greater':'<','higher':'<'}
    for m in re.finditer(r'\bnot\s+(?:a\s+)?(rating|publication\s+year)\s+(?:of\s+)?(\d+(?:\.\d+)?)\s+or\s+(below|less|lower|above|greater|higher)\b',source.text):
        field='rating' if m[1]=='rating' else 'year'
        source.add(field,inverse[m[3]],float(m[2]) if field=='rating' else int(m[2]),m,'numeric.negated_boundary')
    domains=[f for f,cue in [('rating',r'\brating\b'),('year',r'\bpublication\s+year\b')] if re.search(cue,source.text)]
    if len(domains)==1:
        for m in re.finditer(r'\b(?:the\s+)?(?:lower|upper)\s+boundary\s+(?:is|must\s+be)\s+strictly\s+(above|below)\s+(\d+(?:\.\d+)?)',source.text):
            source.add(domains[0],'>' if m[1]=='above' else '<',float(m[2]) if domains[0]=='rating' else int(m[2]),m,'numeric.explicit_boundary')
    fields={'year':r'publication(?:\s+year)?','rating':r'rat(?:ing|ed)'}
    postfix={'onward':'>=','or greater':'>=','or higher':'>=','or less':'<=','or lower':'<='}
    for field,cue in fields.items():
        for m in re.finditer(r'\b'+cue+r'\s+(\d+(?:\.\d+)?)\s+(onward|or greater|or higher|or less|or lower)\b',source.text):
            value=float(m[1]) if field=='rating' else int(m[1]) if '.' not in m[1] else float(m[1])
            source.add(field,postfix[m[2]],value,m,'numeric.owned_postfix')


def finalize(s,unassigned=True):
    """An explicit domain/operator creates an operand obligation even if parsing fails."""
    quantity=r'\b(?:no\s+(?:more|less|fewer)\s+than|at\s+(?:least|most)|above|below|under|over)\s*(\d+(?:\.\d+)?\s*)?(pages?)\b'
    for m in re.finditer(quantity,s.remaining(protect=True)):
        s.add_span('pages','QUANTITY',m[1].strip() if m[1] else None,*m.span(),'numeric.unsupported_unit','UNSUPPORTED' if m[1] else 'INCOMPLETE')
    for field,pattern in REQUEST_CUES.items():
        for m in re.finditer(pattern,s.remaining(protect=True)):
            end=next((i for i in range(m.end(),len(s.text)) if s.text[i] in ';!?\n'),len(s.text))
            operand=re.match(r'[^,;!?]*',s.text[m.end():end]);stop=m.end()+operand.end()
            if s.free(m.start(),stop):s.add_span(field,'INVALID_OR_OMITTED_OPERAND',None,m.start(),stop,'numeric.operand_obligation','INCOMPLETE')
    for m in re.finditer(r'\bno\s+(?:more|less|fewer)\s+than\s+\d+(?:\.\d+)?',s.remaining(protect=True)):
        if s.free(*m.span()):s.add_span('relationship','UNASSIGNED_NUMERIC_DOMAIN',{'fields':['rating','year']},*m.span(),'numeric.domain_obligation','AMBIGUOUS')
    if unassigned and not re.search(r'\b(?:about|topic\s*:|require\w*|must|mandatory|strict)\b',s.text) and not any(c.support_status=='UNSUPPORTED' for c in s.items):
        for m in re.finditer(r'(?<![\w.])\d+(?:\.\d+)?(?![\w.])',s.remaining(protect=True)):
            prefix=s.remaining(protect=True)[:m.start()].strip()
            if not prefix:continue
            if re.search(r'\b(?:after|before)\s*$',prefix) and not re.fullmatch(r'\s*(?:books?\s+)?(?:after|before)\s*',prefix):continue
            s.add_span('ambiguous_number','UNASSIGNED',float(m[0]),*m.span(),'numeric.unassigned_operand','AMBIGUOUS')
    for c in s.items:
        if c.field not in ['rating','year'] or c.support_status!='SUPPORTED':continue
        values=c.normalized_value if isinstance(c.normalized_value,(list,tuple)) else [c.normalized_value]
        low,high=(0,5) if c.field=='rating' else (1000,2100)
        if any(type(v) not in [int,float] or not low<=v<=high or c.field=='year' and int(v)!=v for v in values):c.support_status='UNSUPPORTED'
