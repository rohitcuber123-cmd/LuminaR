"""The same scoped canonicalization contract for understanding and choices."""
from scratch.search_v2c_c5er.candidate_search_v4.query_plan import FacetVocabulary as NativeVocabulary,normalize
from scratch.search_v2c_c5er.candidate_search_v4.semantic_safety import distance_one
from functools import lru_cache
from difflib import SequenceMatcher

@lru_cache(maxsize=8)
def buckets(facets):
    vocab=NativeVocabulary(facets)
    by_length={};by_shape={}
    for key in vocab.rows:by_length.setdefault(len(key),[]).append(key)
    for key in dict.fromkeys([*vocab.rows,*vocab.aliases]):
        by_shape.setdefault((len(key),len(key.split())),[]).append(key)
    return ({k:tuple(v) for k,v in by_length.items()},{k:tuple(v) for k,v in by_shape.items()})

class FacetVocabulary(NativeVocabulary):
    def __init__(self,facets):
        facets=tuple(facets);super().__init__(facets)
        self.by_length,self.by_shape=buckets(facets)

    def resolve(self,term,fuzzy=True):
        value,score,correction=super().resolve(term,False)
        if value or not fuzzy:return value,score,correction
        key=normalize(term)
        if not 4<=len(key)<=60:return None,0.,None
        # Same native candidate conditions, ratios, thresholds and tie margin;
        # enumerate immutable length/token buckets rather than the full scope.
        if len(key)>=6:
            targets=set()
            for i in range(len(key)-1):
                swapped=key[:i]+key[i+1]+key[i]+key[i+2:]
                if swapped==key:continue
                target=self.aliases.get(swapped,swapped)
                if target in self.rows:targets.add(target)
            if len(targets)==1:
                value=self.rows[targets.pop()]
                return value,.95,{'from':term,'to':value,'kind':'typo'}
        radius=max(2,len(key)//5);words=len(key.split())
        candidates=[(SequenceMatcher(None,key,k).ratio(),k)
            for length in range(len(key)-radius,len(key)+radius+1)
            for k in self.by_shape.get((length,words),())]
        candidates.sort(reverse=True)
        if candidates and candidates[0][0]>=.86 and (len(candidates)==1 or candidates[0][0]-candidates[1][0]>=.05):
            score,matched=candidates[0];value=self.rows[self.aliases.get(matched,matched)]
            return value,score,{'from':term,'to':value,'kind':'typo'}
        choices={self.rows[k] for length in [len(key)-1,len(key),len(key)+1]
            for k in self.by_length.get(length,()) if distance_one(key,k)}
        if len(choices)!=1:return None,0.,None
        value=choices.pop()
        # Normalized edit similarity, not a calibrated probability.
        similarity=1-1/max(len(key),len(normalize(value)))
        return value,similarity,{'from':term,'to':value,'kind':'typo'}
