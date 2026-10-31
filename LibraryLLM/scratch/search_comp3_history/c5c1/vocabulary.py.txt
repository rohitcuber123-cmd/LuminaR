"""The same scoped canonicalization contract for understanding and choices."""
from scratch.search_v2c_c5er.candidate_search_v4.query_plan import FacetVocabulary as NativeVocabulary,normalize
from scratch.search_v2c_c5er.candidate_search_v4.semantic_safety import distance_one

class FacetVocabulary(NativeVocabulary):
    def resolve(self,term,fuzzy=True):
        value,score,correction=super().resolve(term,fuzzy)
        if value or not fuzzy:return value,score,correction
        key=normalize(term)
        if not 4<=len(key)<=60:return None,0.,None
        choices={v for k,v in self.rows.items() if distance_one(key,k)}
        if len(choices)!=1:return None,0.,None
        value=choices.pop()
        # Normalized edit similarity, not a calibrated probability.
        similarity=1-1/max(len(key),len(normalize(value)))
        return value,similarity,{'from':term,'to':value,'kind':'typo'}
