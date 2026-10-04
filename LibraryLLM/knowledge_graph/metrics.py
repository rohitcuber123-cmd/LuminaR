"""Metadata diversity and set coverage; no inference about relevance quality."""
from itertools import combinations
from knowledge_graph.core import canonical,terms

def ids(books):return {b['work_id'] for b in books}
def diversity(books):
    subjects=[set(terms(b.get('subjects'))) for b in books]
    distances=[1-len(a&b)/len(a|b) for a,b in combinations(subjects,2) if a and b]
    authors={canonical(a) for b in books for a in terms(b.get('authors')).values()}
    return {'subject_pairwise_distance':sum(distances)/len(distances) if distances else None,
            'subject_pairs_evaluated':len(distances),'subject_pairs_missing':len(books)*(len(books)-1)//2-len(distances),
            'unique_authors':len(authors),'unique_subjects':len(set().union(*subjects)) if subjects else 0,
            'books_with_subjects':sum(bool(s) for s in subjects),'result_count':len(books)}
def compare(existing,kg):
    a,b=ids(existing),ids(kg)
    return {'intersection_count':len(a&b),'union_count':len(a|b),
            'overlap_at_k':len(a&b)/min(len(a),len(b)) if a and b else 0.0,
            'jaccard':len(a&b)/len(a|b) if a|b else 0.0,
            'existing_only_ids':sorted(a-b),'kg_only_ids':sorted(b-a),'shared_ids':sorted(a&b),
            'existing_diversity':diversity(existing),'kg_diversity':diversity(kg),
            'meaning':'Metadata diversity and set difference do not establish recommendation relevance.'}
