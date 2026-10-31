"""Postfix comparators on explicitly named numeric fields."""
import re
def recognize(source):
    fields={'year':r'publication(?:\s+year)?','rating':r'rat(?:ing|ed)'}
    postfix={'onward':'>=','or greater':'>=','or higher':'>=','or less':'<=','or lower':'<='}
    for field,cue in fields.items():
        for m in re.finditer(r'\b'+cue+r'\s+(\d+(?:\.\d+)?)\s+(onward|or greater|or higher|or less|or lower)\b',source.text):
            value=float(m[1]) if field=='rating' else int(m[1]) if '.' not in m[1] else float(m[1])
            source.add(field,postfix[m[2]],value,m,'numeric.owned_postfix')
