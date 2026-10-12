"""Source-span retrieval metrics. Independent of the retriever and gold creation."""

from statistics import mean

DEPTHS = (1, 3, 5, 10, 20, 40, 50)


def overlaps(chunk, passage):
    length = passage['source_end'] - passage['source_start']
    common = max(0, min(chunk['end'], passage['source_end'])
                 - max(chunk['start'], passage['source_start']))
    return common >= min(40, length) and common / length >= 0.8


def evaluate_query(query, ranked_ids, chunks):
    """One question; duplicate chunks covering one span cannot inflate recall."""
    spans = [p for p in query['accepted_passages'] if p['relevance_grade'] == 2]
    if not spans:
        return None
    seen = set()
    first_rank = None
    recall = {}
    hits = {}
    for rank, chunk_id in enumerate(ranked_ids, 1):
        chunk = chunks.get(chunk_id)
        if chunk is not None:
            matched = {i for i, span in enumerate(spans) if overlaps(chunk, span)}
            if matched and first_rank is None:
                first_rank = rank
            seen.update(matched)
        if rank in DEPTHS:
            recall[rank] = len(seen) / len(spans)
            hits[rank] = int(first_rank is not None)
    for depth in DEPTHS:
        recall.setdefault(depth, len(seen) / len(spans))
        hits.setdefault(depth, int(first_rank is not None))
    return {'first_rank': first_rank, 'mrr': 1 / first_rank if first_rank else 0,
            'hit': {str(k): hits[k] for k in DEPTHS},
            'recall': {str(k): recall[k] for k in DEPTHS},
            'accepted_span_count': len(spans)}


def aggregate(rows):
    valid = [row for row in rows if row is not None]
    if not valid:
        return {'evaluated': 0}
    return {'evaluated': len(valid), 'mrr': mean(x['mrr'] for x in valid),
            'hit': {str(k): mean(x['hit'][str(k)] for x in valid) for k in DEPTHS},
            'recall': {str(k): mean(x['recall'][str(k)] for x in valid) for k in DEPTHS}}


def oracle(rows, depth):
    """Perfect reorder of a candidate prefix: binary hit and reciprocal rank."""
    valid = [x for x in rows if x is not None]
    present = mean(x['hit'][str(depth)] for x in valid) if valid else 0
    return {'candidate_depth': depth, 'mrr': present,
            'hit_at_1': present, 'hit_at_3': present}
