"""Source proof for legacy facet proposals; no per-category exceptions."""
import re
from scratch.search_v2c_c5er.candidate_search_v4.query_plan import normalize

def owned_subjects(text,source,proposed,facets):
    from .vocabulary import FacetVocabulary
    candidates=source.items
    supported={normalize(c.normalized_value) for c in candidates if c.field=='subject' and c.support_status=='SUPPORTED'}
    # A complete remaining category expression is established native grammar.
    # Request verbs and descriptive nouns are deliberately not stripped here.
    vocab=FacetVocabulary(facets)
    remaining=source.remaining().strip(' ,;:.!?')
    residue=re.sub(r'\b(?:books?|with|and)\b',' ',remaining).strip(' ,;:.!?')
    residual_value,_,_=vocab.resolve(residue) if len(residue)<=60 else (None,0,None)
    whole_value,_,_=vocab.resolve(text) if len(text)<=60 else (None,0,None)
    # Category-first bibliographic or topical expression after consuming
    # independently owned conditions, including scoped aliases/corrections.
    prefix=re.split(r'\b(?:books?|novels?|about|on)\b',remaining,maxsplit=1)[0].strip()
    prefix_value,_,_=vocab.resolve(prefix) if prefix and len(prefix)<=60 else (None,0,None)
    kept=[]
    for value in proposed:
        term=re.escape(normalize(value))
        whole=whole_value==value or residual_value==value or prefix_value==value
        postfix=bool(re.search(r'\b'+term+r'\s+(?:category|subject|classification)\b',normalize(text)))
        unresolved_number=bool(re.fullmatch(term+r'\s+\d+(?:\.\d+)?',normalize(text)))
        # Established category-first grammar, rather than arbitrary nouns left
        # behind after removing other fields. Explicit owners are above.
        category_first=bool(re.match(r'^\s*'+term+r'\b(?:\s+books?\b|\s+(?:with|rated|rating|published|and|excluding|without)\b)',normalize(text)))
        if normalize(value) in supported or whole or category_first or postfix or unresolved_number:kept.append(value)
    return kept
