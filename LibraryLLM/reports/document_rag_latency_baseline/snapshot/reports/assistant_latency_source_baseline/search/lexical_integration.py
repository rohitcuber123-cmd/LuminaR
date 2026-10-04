"""Optional bounded lexical evidence for the existing semantic search pipeline."""
from search.typo_assistance import normalize_structured

# The flag is read at request time by the caller. These limits bound extra
# reranker pairs independently of the lexical store's own lookup budgets.
SIGNAL_LIMITS={
    'exact_title':10,
    'exact_author':10,
    'fuzzy_title':5,
    'fuzzy_author':5,
}
FUZZY_SCORE_BOOST={'fuzzy_title':0.02,'fuzzy_author':0.01}


def _current_value(book,value_type,target):
    if value_type=='TITLE':
        return normalize_structured(book.get('title'))==target
    authors=book.get('authors') or []
    if isinstance(authors,str): authors=[authors]
    return any(normalize_structured(author)==target for author in authors)


def merge_lexical_candidates(store,query,candidates,metadata,collection,current_books):
    """Return a new candidate set; never change the semantic inputs on failure.

    The store supplies IDs, but only current Mongo title/authors can confer a
    lexical signal. An exception anywhere discards the entire lexical merge.
    """
    semantic=[]
    evidence={}
    for candidate in candidates:
        wid=candidate['work_id']
        if wid not in evidence:
            semantic.append(candidate)
            evidence[wid]={'semantic'}
    if store is None or not store.health().get('lexical_available'):
        return semantic,metadata,evidence
    requested=[]
    signal_counts={signal:0 for signal in SIGNAL_LIMITS}
    for value_type,label in (('TITLE','title'),('AUTHOR','author')):
        result=store.fuzzy(value_type,query)
        if result['exact']:
            signal='exact_'+label
            target=result['normalized_query']
            ids=[wid for _,wid in result['exact']]
        elif result['match'] is not None:
            signal='fuzzy_'+label
            target=result['match']['value']
            ids=result['work_ids']
        else:
            continue
        for wid in dict.fromkeys(ids):
            if signal_counts[signal]>=SIGNAL_LIMITS[signal]:
                break
            requested.append((wid,signal,value_type,target))
            signal_counts[signal]+=1
    if not requested:
        return semantic,metadata,evidence
    lexical_ids=list(dict.fromkeys(item[0] for item in requested))
    lexical_metadata=current_books(collection,lexical_ids)
    merged=semantic
    merged_metadata=dict(metadata)
    seen=set(evidence)
    for wid,signal,value_type,target in requested:
        book=lexical_metadata.get(wid)
        if book is None or not _current_value(book,value_type,target):
            continue
        evidence.setdefault(wid,set()).add(signal)
        merged_metadata[wid]=book
        if wid not in seen:
            merged.append({'work_id':wid,'hnsw_score':0.0})
            seen.add(wid)
    return merged,merged_metadata,evidence


def lexical_rank_key(candidate,score,evidence,author_ids):
    signals=evidence.get(candidate['work_id'],set())
    exact_title='exact_title' in signals
    exact_author='exact_author' in signals or candidate['work_id'] in author_ids
    tier=2 if exact_title else 1 if exact_author else 0
    boost=sum(FUZZY_SCORE_BOOST[signal] for signal in FUZZY_SCORE_BOOST if signal in signals)
    return tier,float(score)+boost
