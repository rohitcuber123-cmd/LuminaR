"""Postfix comparators on explicitly named numeric fields."""
import re

REQUEST_CUES={
    'rating':r'\brat(?:ing|ed)\s+(?:(?:must|should)\s+)?(?:be\s+)?(?:at\s+least|at\s+most|above|below|over|under|greater\s+than|less\s+than|exceed|>=|<=|>|<|=)\s*',
    'year':r'\b(?:published|publication\s+year)\s+(?:after|before|in|from|>=|<=|>|<|=)\s*'}
def recognize(source):
    fields={'year':r'publication(?:\s+year)?','rating':r'rat(?:ing|ed)'}
    postfix={'onward':'>=','or greater':'>=','or higher':'>=','or less':'<=','or lower':'<='}
    for field,cue in fields.items():
        for m in re.finditer(r'\b'+cue+r'\s+(\d+(?:\.\d+)?)\s+(onward|or greater|or higher|or less|or lower)\b',source.text):
            value=float(m[1]) if field=='rating' else int(m[1]) if '.' not in m[1] else float(m[1])
            source.add(field,postfix[m[2]],value,m,'numeric.owned_postfix')


def finalize(s):
    """An explicit domain/operator creates an operand obligation even if parsing fails."""
    for field,pattern in REQUEST_CUES.items():
        for m in re.finditer(pattern,s.remaining(protect=True)):
            end=next((i for i in range(m.end(),len(s.text)) if s.text[i] in ';!?\n'),len(s.text))
            operand=re.match(r'[^,;!?]*',s.text[m.end():end]);stop=m.end()+operand.end()
            if s.free(m.start(),stop):s.add_span(field,'INVALID_OR_OMITTED_OPERAND',None,m.start(),stop,'numeric.operand_obligation','INCOMPLETE')
    for m in re.finditer(r'\bno\s+(?:more|less|fewer)\s+than\s+\d+(?:\.\d+)?',s.remaining(protect=True)):
        if s.free(*m.span()):s.add_span('relationship','UNASSIGNED_NUMERIC_DOMAIN',{'fields':['rating','year']},*m.span(),'numeric.domain_obligation','AMBIGUOUS')
    for c in s.items:
        if c.field not in ['rating','year'] or c.support_status!='SUPPORTED':continue
        values=c.normalized_value if isinstance(c.normalized_value,(list,tuple)) else [c.normalized_value]
        low,high=(0,5) if c.field=='rating' else (1000,2100)
        if any(type(v) not in [int,float] or not low<=v<=high or c.field=='year' and int(v)!=v for v in values):c.support_status='UNSUPPORTED'
